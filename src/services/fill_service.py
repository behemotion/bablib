"""Service for unified fill command with type-based routing."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.core.config import BablibConfig
from src.models.box_type import BoxType
from src.services.box_service import BoxService
from src.services.database import DatabaseError, DatabaseManager
from src.core.lib_logger import get_component_logger

logger = get_component_logger("fill_service")


class FillService:
    """
    Service for filling boxes with content using type-based routing.

    Routes fill operations to appropriate underlying services:
    - DRAG boxes -> Crawler service
    - RAG boxes -> Upload service
    - BAG boxes -> Storage service
    """

    def __init__(self, box_service: Optional[BoxService] = None):
        """Initialize fill service."""
        self.box_service = box_service or BoxService()

    async def initialize(self) -> None:
        """Initialize the fill service."""
        await self.box_service.initialize()

    async def fill(
        self,
        box_name: str,
        source: str,
        shelf_name: Optional[str] = None,
        **options
    ) -> Dict[str, Any]:
        """
        Fill a box with content based on its type.

        Args:
            box_name: Name of the box to fill
            source: Source URL or path
            shelf_name: Optional shelf context
            **options: Type-specific options

        Returns:
            Dictionary with operation result

        Raises:
            BoxNotFoundError: If box not found
            DatabaseError: If operation fails
        """
        await self.initialize()

        # Get the box to determine type
        box = await self.box_service.get_box_by_name(box_name)
        if not box:
            from src.models.box import BoxNotFoundError
            raise BoxNotFoundError(f"Box '{box_name}' not found")

        logger.info(f"Filling {box.type.value} box '{box_name}' from source: {source}")

        # Route based on box type
        try:
            if box.type == BoxType.DRAG:
                return await self._fill_drag(box, source, **options)
            elif box.type == BoxType.RAG:
                return await self._fill_rag(box, source, **options)
            elif box.type == BoxType.BAG:
                return await self._fill_bag(box, source, **options)
            else:
                raise DatabaseError(f"Unknown box type: {box.type}")

        except Exception as e:
            logger.error(f"Failed to fill box '{box_name}': {e}")
            return {
                'success': False,
                'box_name': box_name,
                'box_type': box.type.value,
                'source': source,
                'error': str(e)
            }

    async def _fill_drag(self, box, source: str, **options) -> Dict[str, Any]:
        """
        Fill a drag box using crawler service.

        Args:
            box: Box model
            source: Source URL
            **options: Crawler-specific options (max_pages, rate_limit, depth)

        Returns:
            Operation result
        """
        from src.logic.crawler.core.crawler import DocumentationCrawler

        logger.info(f"Starting crawl operation for drag box '{box.name}'")

        # Extract drag-specific options
        max_pages = options.get('max_pages', box.max_pages or 100)
        rate_limit = options.get('rate_limit', box.rate_limit or 1.0)
        depth = options.get('depth', box.crawl_depth or 3)

        try:
            # Update box URL if different
            if box.url != source:
                await self._update_box_url(box, source)

            # Initialize database manager and crawler
            config = BablibConfig()
            db_manager = DatabaseManager(config)
            await db_manager.initialize()

            crawler = DocumentationCrawler(db_manager, config)
            await crawler.initialize()

            try:
                # Start the crawl with box_id
                session = await crawler.start_crawl(
                    box_id=box.id,
                    max_pages=max_pages,
                    rate_limit=rate_limit
                )

                # Wait for crawl to complete
                final_session = await crawler.wait_for_completion()

                return {
                    'success': True,
                    'box_name': box.name,
                    'box_type': 'drag',
                    'source': source,
                    'operation': 'crawl',
                    'session_id': session.id,
                    'pages_crawled': final_session.pages_crawled if final_session else 0,
                    'pages_failed': final_session.pages_failed if final_session else 0,
                    'max_pages': max_pages,
                    'rate_limit': rate_limit,
                    'depth': depth,
                    'message': f"Crawled {source} into drag box '{box.name}'"
                }

            finally:
                await crawler.cleanup()
                await db_manager.cleanup()

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            raise DatabaseError(f"Failed to crawl {source}: {e}")

    async def _fill_rag(self, box, source: str, **options) -> Dict[str, Any]:
        """
        Fill a rag box using uploader service.

        Args:
            box: Box model
            source: Source path or URL
            **options: RAG-specific options (chunk_size, overlap)

        Returns:
            Operation result
        """
        from src.logic.projects.upload.upload_manager import UploadManager
        from src.logic.projects.models.upload import UploadSource, ConflictResolution

        logger.info(f"Starting document import for rag box '{box.name}'")

        # Extract rag-specific options
        chunk_size = options.get('chunk_size', 500)
        overlap = options.get('overlap', 50)
        recursive = options.get('recursive', True)
        conflict_resolution = options.get('conflict_resolution', ConflictResolution.OVERWRITE)

        try:
            # Parse source string into UploadSource
            upload_source = UploadSource.parse(source)

            # Initialize upload manager and start upload
            upload_manager = UploadManager()
            operation = await upload_manager.upload_files(
                box=box,
                source=upload_source,
                recursive=recursive,
                conflict_resolution=conflict_resolution
            )

            # Wait for operation to complete (poll status)
            import asyncio
            while operation.is_active():
                await asyncio.sleep(0.5)
                operation = await upload_manager.get_upload_status(operation.id)
                if operation is None:
                    break

            return {
                'success': operation is not None and operation.files_failed == 0,
                'box_name': box.name,
                'box_type': 'rag',
                'source': source,
                'operation': 'import',
                'operation_id': operation.id if operation else None,
                'files_uploaded': operation.files_succeeded if operation else 0,
                'files_failed': operation.files_failed if operation else 0,
                'chunk_size': chunk_size,
                'overlap': overlap,
                'message': f"Imported {operation.files_succeeded if operation else 0} files into rag box '{box.name}'"
            }

        except Exception as e:
            logger.error(f"RAG import failed: {e}")
            raise DatabaseError(f"Failed to import {source}: {e}")

    async def _fill_bag(self, box, source: str, **options) -> Dict[str, Any]:
        """
        Fill a bag box using storage service (UploadManager).

        Args:
            box: Box model
            source: Source path
            **options: Storage-specific options (recursive, pattern)

        Returns:
            Operation result
        """
        from src.logic.projects.upload.upload_manager import UploadManager
        from src.logic.projects.models.upload import UploadSource, ConflictResolution

        logger.info(f"Starting file storage for bag box '{box.name}'")

        # Extract bag-specific options
        recursive = options.get('recursive', False)
        pattern = options.get('pattern', '*')
        conflict_resolution = options.get('conflict_resolution', ConflictResolution.RENAME)

        try:
            # Parse source string into UploadSource
            upload_source = UploadSource.parse(source)

            # Build exclude patterns from pattern (inverse matching)
            exclude_patterns = []
            if pattern != '*':
                # If pattern is specified, exclude everything that doesn't match
                # For now, we'll pass it through and let the handler filter
                pass

            # Initialize upload manager and start upload
            upload_manager = UploadManager()
            operation = await upload_manager.upload_files(
                box=box,
                source=upload_source,
                recursive=recursive,
                exclude_patterns=exclude_patterns,
                conflict_resolution=conflict_resolution
            )

            # Wait for operation to complete (poll status)
            import asyncio
            while operation.is_active():
                await asyncio.sleep(0.5)
                operation = await upload_manager.get_upload_status(operation.id)
                if operation is None:
                    break

            return {
                'success': operation is not None and operation.files_failed == 0,
                'box_name': box.name,
                'box_type': 'bag',
                'source': source,
                'operation': 'store',
                'operation_id': operation.id if operation else None,
                'files_stored': operation.files_succeeded if operation else 0,
                'files_failed': operation.files_failed if operation else 0,
                'recursive': recursive,
                'pattern': pattern,
                'message': f"Stored {operation.files_succeeded if operation else 0} files into bag box '{box.name}'"
            }

        except Exception as e:
            logger.error(f"BAG storage failed: {e}")
            raise DatabaseError(f"Failed to store {source}: {e}")

    async def _update_box_url(self, box, new_url: str) -> None:
        """Update box URL if it has changed."""
        try:
            conn = self.box_service.db._connection
            await conn.execute(
                "UPDATE boxes SET url = ?, updated_at = ? WHERE id = ?",
                (new_url, datetime.now(timezone.utc).isoformat(), box.id)
            )
            await conn.commit()
            logger.info(f"Updated box '{box.name}' URL to: {new_url}")

        except Exception as e:
            logger.warning(f"Failed to update box URL: {e}")

    async def get_fill_options(self, box_name: str) -> Dict[str, Any]:
        """
        Get available fill options for a box based on its type.

        Args:
            box_name: Name of the box

        Returns:
            Dictionary of available options

        Raises:
            BoxNotFoundError: If box not found
        """
        await self.initialize()

        box = await self.box_service.get_box_by_name(box_name)
        if not box:
            from src.models.box import BoxNotFoundError
            raise BoxNotFoundError(f"Box '{box_name}' not found")

        if box.type == BoxType.DRAG:
            return {
                'type': 'drag',
                'description': 'Website crawling options',
                'options': {
                    'max_pages': {
                        'type': 'int',
                        'default': box.max_pages or 100,
                        'description': 'Maximum pages to crawl'
                    },
                    'rate_limit': {
                        'type': 'float',
                        'default': box.rate_limit or 1.0,
                        'description': 'Requests per second'
                    },
                    'depth': {
                        'type': 'int',
                        'default': box.crawl_depth or 3,
                        'description': 'Maximum crawl depth'
                    }
                }
            }

        elif box.type == BoxType.RAG:
            return {
                'type': 'rag',
                'description': 'Document import options',
                'options': {
                    'chunk_size': {
                        'type': 'int',
                        'default': 500,
                        'description': 'Text chunk size for processing'
                    },
                    'overlap': {
                        'type': 'int',
                        'default': 50,
                        'description': 'Chunk overlap in characters'
                    }
                }
            }

        elif box.type == BoxType.BAG:
            return {
                'type': 'bag',
                'description': 'File storage options',
                'options': {
                    'recursive': {
                        'type': 'bool',
                        'default': False,
                        'description': 'Include subdirectories'
                    },
                    'pattern': {
                        'type': 'str',
                        'default': '*',
                        'description': 'File pattern filter'
                    }
                }
            }

        else:
            return {
                'type': 'unknown',
                'description': 'Unknown box type',
                'options': {}
            }