"""MCP service layer for shelf operations."""

import uuid
from datetime import UTC, datetime
from typing import Any

from src.core.lib_logger import get_component_logger
from src.models.box import BoxNotFoundError
from src.models.box_type import BoxType
from src.models.shelf import ShelfNotFoundError
from src.services.box_service import BoxService
from src.services.database import DatabaseManager
from src.services.shelf_service import ShelfService

logger = get_component_logger("shelf_mcp_service")


class ShelfMcpService:
    """Service layer for shelf-related MCP operations."""

    def __init__(
        self,
        shelf_service: ShelfService | None = None,
        box_service: BoxService | None = None,
        db_manager: DatabaseManager | None = None
    ):
        """Initialize shelf MCP service."""
        self.shelf_service = shelf_service or ShelfService()
        self.box_service = box_service or BoxService()
        self.db_manager = db_manager or DatabaseManager()
        self._session_id = str(uuid.uuid4())

    async def initialize(self) -> None:
        """Initialize services."""
        await self.shelf_service.initialize()
        await self.box_service.initialize()
        await self.db_manager.initialize()

    async def _get_box_file_count(self, box_name: str, box_type: BoxType) -> int:
        """
        Get file/page count for a box based on its type.

        Args:
            box_name: Name of the box
            box_type: Type of the box (DRAG/RAG/BAG)

        Returns:
            Count of files/pages in the box
        """
        try:
            if box_type == BoxType.DRAG:
                # For crawling boxes, count pages from box
                box = await self.box_service.get_box_by_name(box_name)
                if box:
                    pages = await self.db_manager.get_box_pages(box.id)
                    return len(pages)
            # RAG and BAG boxes don't have file tracking yet
            return 0
        except Exception as e:
            logger.debug(f"Could not get file count for box '{box_name}': {e}")
            return 0

    async def _get_box_total_size(self, box_name: str, box_type: BoxType) -> int:
        """
        Get total size in bytes for a box based on its type.

        Args:
            box_name: Name of the box
            box_type: Type of the box (DRAG/RAG/BAG)

        Returns:
            Total size in bytes
        """
        try:
            if box_type == BoxType.DRAG:
                # For crawling boxes, sum page sizes from box
                box = await self.box_service.get_box_by_name(box_name)
                if box:
                    pages = await self.db_manager.get_box_pages(box.id)
                    return sum(p.size_bytes or 0 for p in pages)
            return 0
        except Exception as e:
            logger.debug(f"Could not get size for box '{box_name}': {e}")
            return 0

    async def _get_box_file_list(self, box_name: str, box_type: BoxType) -> list[dict[str, Any]]:
        """
        Get list of files/pages for a box.

        Args:
            box_name: Name of the box
            box_type: Type of the box (DRAG/RAG/BAG)

        Returns:
            List of file/page info dictionaries
        """
        try:
            if box_type == BoxType.DRAG:
                # For crawling boxes, return page URLs
                box = await self.box_service.get_box_by_name(box_name)
                if box:
                    pages = await self.db_manager.get_box_pages(box.id)
                    return [
                        {
                            "url": p.url,
                            "title": p.title,
                            "status": p.status.value if hasattr(p.status, 'value') else str(p.status),
                            "size_bytes": p.size_bytes or 0,
                            "crawled_at": p.crawled_at.isoformat() if p.crawled_at else None
                        }
                        for p in pages[:100]  # Limit to 100 files
                    ]
            # RAG and BAG boxes don't have file tracking yet
            return []
        except Exception as e:
            logger.debug(f"Could not get file list for box '{box_name}': {e}")
            return []

    async def list_shelfs(
        self,
        include_baskets: bool = False,
        include_empty: bool = True,
        current_only: bool = False,
        limit: int = 50
    ) -> dict[str, Any]:
        """
        List all shelves with optional basket details.

        Args:
            include_baskets: Include basket details for each shelf
            include_empty: Include empty shelves
            current_only: Only return current shelf
            limit: Maximum number of results

        Returns:
            Dictionary with shelves list and metadata
        """
        await self.initialize()

        # Get current shelf
        current_shelf = await self.shelf_service.get_current_shelf()
        current_shelf_name = current_shelf.name if current_shelf else None

        # Get all shelves or just current
        if current_only and current_shelf:
            shelves = [current_shelf]
        else:
            shelves = await self.shelf_service.list_shelves()

        # Apply limit
        shelves = shelves[:limit]

        # Build response
        shelves_data = []
        total_baskets = 0

        for shelf in shelves:
            # Skip empty shelves if requested
            if not include_empty and shelf.box_count == 0:
                continue

            shelf_dict = {
                "name": shelf.name,
                "created_at": shelf.created_at.isoformat() if shelf.created_at else None,
                "updated_at": shelf.updated_at.isoformat() if shelf.updated_at else None,
                "is_current": shelf.name == current_shelf_name,
                "basket_count": shelf.box_count
            }

            # Include baskets if requested
            if include_baskets:
                boxes = await self.box_service.list_boxes(shelf_name=shelf.name)
                baskets = []
                for box in boxes:
                    box_type = box.type if isinstance(box.type, BoxType) else BoxType(box.type)
                    file_count = await self._get_box_file_count(box.name, box_type)
                    baskets.append({
                        "name": box.name,
                        "type": box_type.value,
                        "status": "ready" if file_count > 0 else "empty",
                        "files": file_count
                    })
                shelf_dict["baskets"] = baskets
                total_baskets += len(baskets)
            else:
                total_baskets += shelf.box_count

            shelves_data.append(shelf_dict)

        # Build metadata
        metadata = {
            "total_shelfs": len(shelves_data),
            "current_shelf": current_shelf_name,
            "total_baskets": total_baskets
        }

        return {
            "shelves": shelves_data,
            "metadata": metadata
        }

    async def get_shelf_structure(
        self,
        shelf_name: str,
        include_basket_details: bool = True,
        include_file_list: bool = False
    ) -> dict[str, Any]:
        """
        Get detailed structure of a specific shelf.

        Args:
            shelf_name: Name of the shelf
            include_basket_details: Include detailed basket information
            include_file_list: Include file lists for baskets

        Returns:
            Dictionary with shelf structure

        Raises:
            ShelfNotFoundError: If shelf doesn't exist
        """
        await self.initialize()

        # Get shelf
        shelf = await self.shelf_service.get_shelf_by_name(shelf_name)
        if not shelf:
            raise ShelfNotFoundError(f"Shelf '{shelf_name}' not found")

        # Get current shelf
        current_shelf = await self.shelf_service.get_current_shelf()

        # Build shelf info
        shelf_info = {
            "name": shelf.name,
            "created_at": shelf.created_at.isoformat() if shelf.created_at else None,
            "updated_at": shelf.updated_at.isoformat() if shelf.updated_at else None,
            "is_current": shelf.name == (current_shelf.name if current_shelf else None)
        }

        # Get baskets
        boxes = await self.box_service.list_boxes(shelf_name=shelf_name)
        baskets = []
        total_files = 0
        total_size = 0

        for box in boxes:
            box_type = box.type if isinstance(box.type, BoxType) else BoxType(box.type)
            file_count = await self._get_box_file_count(box.name, box_type)
            box_size = await self._get_box_total_size(box.name, box_type)

            basket_dict = {
                "name": box.name,
                "type": box_type.value,
            }

            if include_basket_details:
                basket_dict.update({
                    "created_at": box.created_at.isoformat() if box.created_at else None,
                    "status": "ready" if file_count > 0 else "empty",
                    "file_count": file_count
                })

            if include_file_list:
                # File listing for DRAG boxes returns page URLs
                basket_dict["files"] = await self._get_box_file_list(box.name, box_type)

            total_files += file_count
            total_size += box_size
            baskets.append(basket_dict)

        # Build summary
        summary = {
            "total_baskets": len(baskets),
            "total_files": total_files,
            "total_size_bytes": total_size
        }

        return {
            "shelf": shelf_info,
            "baskets": baskets,
            "summary": summary
        }

    async def get_current_shelf(self) -> dict[str, Any]:
        """
        Get information about the current active shelf.

        Returns:
            Dictionary with current shelf info or available shelves
        """
        await self.initialize()

        current_shelf = await self.shelf_service.get_current_shelf()

        if current_shelf:
            # Get boxes in current shelf
            boxes = await self.box_service.list_boxes(shelf_name=current_shelf.name)

            # Calculate total files across all boxes
            total_files = 0
            for box in boxes:
                box_type = box.type if isinstance(box.type, BoxType) else BoxType(box.type)
                total_files += await self._get_box_file_count(box.name, box_type)

            return {
                "current_shelf": {
                    "name": current_shelf.name,
                    "created_at": current_shelf.created_at.isoformat() if current_shelf.created_at else None,
                    "basket_count": len(boxes),
                    "total_files": total_files
                },
                "context": {
                    "session_id": self._session_id,
                    "last_context_update": datetime.now(UTC).isoformat()
                }
            }
        else:
            # No current shelf - list available
            shelves = await self.shelf_service.list_shelves()
            return {
                "current_shelf": None,
                "available_shelfs": [s.name for s in shelves],
                "context": {
                    "session_id": self._session_id,
                    "last_context_update": datetime.now(UTC).isoformat()
                }
            }

    # Admin operations

    async def create_shelf_admin(
        self,
        name: str,
        description: str | None = None,
        set_current: bool = False,
        force: bool = False
    ) -> dict[str, Any]:
        """
        Create a new shelf via admin MCP.

        Args:
            name: Shelf name
            description: Optional description
            set_current: Set as current shelf
            force: Force creation (update if exists)

        Returns:
            Operation result dictionary
        """
        await self.initialize()

        # Check if exists
        existing = await self.shelf_service.get_shelf_by_name(name)

        if existing and not force:
            return {
                "operation": "create_shelf",
                "shelf_name": name,
                "result": "already_exists",
                "details": {
                    "shelf_id": existing.id,
                    "created_at": existing.created_at.isoformat() if existing.created_at else None,
                    "is_current": False
                }
            }

        # Create new shelf
        shelf = await self.shelf_service.create_shelf(
            name=name,
            description=description,
            set_current=set_current
        )

        return {
            "operation": "create_shelf",
            "shelf_name": name,
            "result": "created",
            "details": {
                "shelf_id": shelf.id,
                "created_at": shelf.created_at.isoformat() if shelf.created_at else None,
                "is_current": set_current
            }
        }

    async def add_basket_admin(
        self,
        shelf_name: str,
        basket_name: str,
        basket_type: str = "data",
        description: str | None = None,
        force: bool = False
    ) -> dict[str, Any]:
        """
        Add a basket (box) to a shelf via admin MCP.

        Args:
            shelf_name: Target shelf name
            basket_name: Basket name
            basket_type: Type (crawling/data/storage maps to drag/rag/bag)
            description: Optional description
            force: Force creation if exists

        Returns:
            Operation result dictionary
        """
        await self.initialize()

        # Verify shelf exists
        shelf = await self.shelf_service.get_shelf_by_name(shelf_name)
        if not shelf:
            raise ShelfNotFoundError(f"Shelf '{shelf_name}' not found")

        # Map basket type to box type
        type_mapping = {
            "crawling": BoxType.DRAG,
            "data": BoxType.RAG,
            "storage": BoxType.BAG
        }
        box_type = type_mapping.get(basket_type, BoxType.RAG)

        # Create box
        box = await self.box_service.create_box(
            name=basket_name,
            box_type=box_type,
            shelf_name=shelf_name,
            description=description
        )

        return {
            "operation": "add_basket",
            "shelf_name": shelf_name,
            "basket_name": basket_name,
            "result": "created",
            "details": {
                "basket_id": box.id,
                "basket_type": basket_type,
                "status": "ready",
                "created_at": box.created_at.isoformat() if box.created_at else None
            }
        }

    async def remove_basket_admin(
        self,
        shelf_name: str,
        basket_name: str,
        confirm: bool = False,
        backup: bool = True
    ) -> dict[str, Any]:
        """
        Remove a basket from a shelf via admin MCP.

        Args:
            shelf_name: Shelf name
            basket_name: Basket name
            confirm: Confirmation required
            backup: Create backup before removal

        Returns:
            Operation result dictionary
        """
        await self.initialize()

        if not confirm:
            return {
                "operation": "remove_basket",
                "shelf_name": shelf_name,
                "basket_name": basket_name,
                "result": "confirmation_required",
                "details": {
                    "message": "Set confirm=true to proceed"
                }
            }

        # Verify shelf and box exist
        shelf = await self.shelf_service.get_shelf_by_name(shelf_name)
        if not shelf:
            raise ShelfNotFoundError(f"Shelf '{shelf_name}' not found")

        box = await self.box_service.get_box_by_name(basket_name)
        if not box:
            raise BoxNotFoundError(f"Basket '{basket_name}' not found")

        # Get file count before deletion
        box_type = box.type if isinstance(box.type, BoxType) else BoxType(box.type)
        files_count = await self._get_box_file_count(basket_name, box_type)

        # Create backup if requested (using same pattern as shelf backup)
        backup_created = False
        if backup:
            try:
                import json

                from src.lib.paths import get_bablib_data_dir

                backup_dir = get_bablib_data_dir() / "backups" / "boxes"
                backup_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"box_{basket_name}_{timestamp}.json"

                backup_data = {
                    "backup_version": "1.0",
                    "backup_timestamp": datetime.now(UTC).isoformat(),
                    "box": {
                        "id": box.id,
                        "name": box.name,
                        "type": box_type.value,
                        "description": getattr(box, 'description', None),
                        "shelf_name": shelf_name,
                        "file_count": files_count
                    }
                }

                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)

                backup_created = True
                logger.info(f"Created box backup: {backup_file}")
            except Exception as e:
                logger.warning(f"Failed to create backup for box '{basket_name}': {e}")

        # Remove box from shelf first, then delete box
        await self.box_service.remove_box_from_shelf(basket_name, shelf_name)
        await self.box_service.delete_box(basket_name, force=True)

        return {
            "operation": "remove_basket",
            "shelf_name": shelf_name,
            "basket_name": basket_name,
            "result": "removed",
            "details": {
                "files_deleted": files_count,
                "backup_created": backup_created
            }
        }

    async def set_current_shelf_admin(self, shelf_name: str) -> dict[str, Any]:
        """
        Set current shelf via admin MCP.

        Args:
            shelf_name: Shelf name to set as current

        Returns:
            Operation result dictionary
        """
        await self.initialize()

        # Get previous current
        previous = await self.shelf_service.get_current_shelf()
        previous_name = previous.name if previous else None

        # Set new current
        await self.shelf_service.set_current_shelf(shelf_name)

        return {
            "operation": "set_current_shelf",
            "shelf_name": shelf_name,
            "result": "updated",
            "details": {
                "previous_current": previous_name,
                "new_current": shelf_name,
                "context_updated": True,
                "session_id": self._session_id
            }
        }
