"""DataProject handler for document upload and vector storage projects."""

import logging
from pathlib import Path
from typing import Any

from ...contracts.service_interfaces import DataProjectContract
from ..models.config import ProjectConfig
from ..models.files import DataDocument, ValidationResult
from ..models.project import Project

logger = logging.getLogger(__name__)


class DataProject(DataProjectContract):
    """
    Handler for data projects that specialize in document processing and vector storage.

    Integrates with vector storage systems to provide document indexing,
    search, and retrieval capabilities.
    """

    def __init__(self):
        """Initialize DataProject handler."""
        pass

    async def initialize_project(self, project: Project) -> bool:
        """
        Initialize data project with vector storage and document processing setup.

        Args:
            project: Project instance to initialize

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info(f"Initializing data project: {project.name}")

            project_dir = Path(project.get_project_directory())

            # Create project-specific directories
            directories = [
                project_dir / "documents",
                project_dir / "processed",
                project_dir / "vectors",
                project_dir / "temp",
                project_dir / "logs"
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            # Initialize vector store for the project
            await self._initialize_vector_store(project)

            # Create document processing configuration
            processing_config = {
                'project_name': project.name,
                'project_type': 'data',
                'embedding_model': project.settings.get('embedding_model', 'mxbai-embed-large'),
                'chunk_size': project.settings.get('chunk_size', 500),
                'chunk_overlap': project.settings.get('chunk_overlap', 50),
                'vector_store_type': project.settings.get('vector_store_type', 'sqlite_vec'),
                'created_at': project.created_at.isoformat(),
                'status': 'initialized'
            }

            config_file = project_dir / "processing_config.json"
            import json
            with open(config_file, 'w') as f:
                json.dump(processing_config, f, indent=2)

            # Initialize document database
            await self._initialize_document_database(project)

            logger.info(f"Successfully initialized data project: {project.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize data project {project.name}: {e}")
            return False

    async def cleanup_project(self, project: Project) -> bool:
        """
        Clean up data project resources including vector stores.

        Args:
            project: Project instance to clean up

        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            logger.info(f"Cleaning up data project: {project.name}")

            # Stop any active processing operations
            await self._stop_active_processing(project)

            # Archive processed documents if requested
            backup_enabled = project.settings.get('backup_on_cleanup', True)
            if backup_enabled:
                await self._archive_project_data(project)

            # Clean up vector store
            await self._cleanup_vector_store(project)

            # Clean up temporary files
            project_dir = Path(project.get_project_directory())
            temp_dir = project_dir / "temp"
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info(f"Successfully cleaned up data project: {project.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup data project {project.name}: {e}")
            return False

    async def validate_settings(self, settings: ProjectConfig) -> ValidationResult:
        """
        Validate settings for data projects.

        Args:
            settings: ProjectConfig to validate

        Returns:
            ValidationResult indicating validation status
        """
        errors = []
        warnings = []

        # Required settings for data projects
        if settings.chunk_size is None:
            errors.append("chunk_size is required for data projects")
        elif not (100 <= settings.chunk_size <= 2000):
            errors.append("chunk_size must be between 100 and 2000")

        if settings.embedding_model is None:
            errors.append("embedding_model is required for data projects")
        elif not isinstance(settings.embedding_model, str) or not settings.embedding_model.strip():
            errors.append("embedding_model must be a non-empty string")

        # Validate chunk overlap
        if settings.chunk_overlap is not None:
            if settings.chunk_size is not None and settings.chunk_overlap >= settings.chunk_size:
                errors.append("chunk_overlap must be less than chunk_size")

        # Validate allowed formats include document types
        if settings.allowed_formats:
            doc_formats = ['pdf', 'txt', 'md', 'html', 'docx', 'json']
            if not any(fmt in settings.allowed_formats for fmt in doc_formats):
                warnings.append("Consider including document formats for better data processing")

        # Check for incompatible settings
        incompatible_settings = [
            'crawl_depth', 'rate_limit', 'user_agent', 'enable_compression', 'auto_tagging'
        ]
        for setting in incompatible_settings:
            if hasattr(settings, setting) and getattr(settings, setting) is not None:
                warnings.append(f"Setting '{setting}' is not used by data projects")

        # Validate vector store type
        valid_vector_stores = ['sqlite_vec', 'qdrant']
        if settings.vector_store_type and settings.vector_store_type not in valid_vector_stores:
            errors.append(f"vector_store_type must be one of: {valid_vector_stores}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    async def get_default_settings(self) -> ProjectConfig:
        """
        Get default settings for data projects.

        Returns:
            ProjectConfig with data-specific defaults
        """
        return ProjectConfig(
            max_file_size=52428800,  # 50MB
            allowed_formats=['pdf', 'docx', 'txt', 'md', 'html', 'json', 'csv', 'xml'],
            chunk_size=500,
            chunk_overlap=50,
            embedding_model='mxbai-embed-large',
            vector_store_type='sqlite_vec',
            concurrent_uploads=5,
            retry_attempts=3,
            timeout_seconds=60
        )

    async def process_document(self, project: Project, file_path: str) -> bool:
        """
        Process document for vector storage.

        Args:
            project: Project instance
            file_path: Path to document to process

        Returns:
            True if processing successful, False otherwise

        Raises:
            ValueError: If file doesn't exist or is invalid format
            RuntimeError: If processing fails
        """
        logger.info(f"Processing document for project {project.name}: {file_path}")

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise ValueError(f"File does not exist: {file_path}")

        try:
            # Extract text content from document
            content = await self._extract_document_content(file_path_obj)
            if not content:
                raise ValueError("No text content could be extracted from document")

            # Create document record
            from ..models.upload import UploadSource, UploadSourceType

            local_source = UploadSource(
                type=UploadSourceType.LOCAL,
                location=str(file_path_obj.parent)
            )

            document = DataDocument.from_file(
                project_id=project.id,
                title=file_path_obj.name,
                content=content,
                source_path=file_path,
                upload_source=local_source,
                processing_config=project.settings
            )

            # Create chunks for vector processing
            chunk_size = project.settings.get('chunk_size', 500)
            chunk_overlap = project.settings.get('chunk_overlap', 50)
            chunks = document.create_chunks(chunk_size, chunk_overlap)

            # Process chunks through vector store
            await self._process_document_chunks(project, document, chunks)

            # Save document record
            await self._save_document_record(project, document)

            # Calculate and update quality score
            quality_score = document.calculate_quality_score()

            logger.info(f"Successfully processed document {file_path_obj.name}: "
                       f"{len(chunks)} chunks, quality score: {quality_score:.2f}")

            return True

        except Exception as e:
            logger.error(f"Failed to process document {file_path}: {e}")
            raise RuntimeError(f"Document processing failed: {e}")

    async def search_documents(
        self,
        project: Project,
        query: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search documents in project using vector similarity.

        Args:
            project: Project instance
            query: Search query
            limit: Maximum number of results

        Returns:
            List of search results with relevance scores
        """
        try:
            logger.info(f"Searching documents in project {project.name}: '{query}'")

            # Get vector store for project
            vector_store = await self._get_vector_store(project)

            # Perform vector search
            search_results = await vector_store.search(
                query=query,
                limit=limit,
                project_name=project.name
            )

            # Load document metadata for results
            documents = await self._load_project_documents(project)
            document_map = {doc.id: doc for doc in documents}

            # Format results
            results = []
            for result in search_results:
                document_id = result.get('document_id')
                if document_id in document_map:
                    document = document_map[document_id]
                    result_data = document.to_search_result(
                        relevance_score=result.get('score', 0.0)
                    )
                    result_data.update({
                        'chunk_text': result.get('text', ''),
                        'chunk_index': result.get('chunk_index', 0)
                    })
                    results.append(result_data)

            logger.info(f"Found {len(results)} search results for query: '{query}'")
            return results

        except Exception as e:
            logger.error(f"Search failed for project {project.name}: {e}")
            return []

    async def get_document_stats(self, project: Project) -> dict[str, Any]:
        """
        Get document processing statistics.

        Args:
            project: Project instance

        Returns:
            Dictionary containing document statistics
        """
        try:
            documents = await self._load_project_documents(project)

            stats = {
                'total_documents': len(documents),
                'total_words': sum(doc.word_count for doc in documents),
                'total_chunks': sum(doc.chunk_count for doc in documents),
                'avg_quality_score': 0.0,
                'processing_errors': 0,
                'languages_detected': set(),
                'document_formats': {},
                'largest_document': None,
                'most_recent': None
            }

            if documents:
                # Calculate average quality score
                quality_scores = [doc.quality_score for doc in documents if doc.quality_score is not None]
                if quality_scores:
                    stats['avg_quality_score'] = sum(quality_scores) / len(quality_scores)

                # Count processing errors
                stats['processing_errors'] = len([doc for doc in documents if not doc.processing_success])

                # Collect languages
                for doc in documents:
                    if doc.language:
                        stats['languages_detected'].add(doc.language)

                # Count document formats
                for doc in documents:
                    file_ext = Path(doc.source_path).suffix.lower()
                    stats['document_formats'][file_ext] = stats['document_formats'].get(file_ext, 0) + 1

                # Find largest document
                largest_doc = max(documents, key=lambda d: d.character_count)
                stats['largest_document'] = {
                    'title': largest_doc.title,
                    'character_count': largest_doc.character_count,
                    'word_count': largest_doc.word_count
                }

                # Find most recent
                most_recent = max(documents, key=lambda d: d.processed_date)
                stats['most_recent'] = {
                    'title': most_recent.title,
                    'processed_date': most_recent.processed_date.isoformat()
                }

            stats['languages_detected'] = list(stats['languages_detected'])

            return stats

        except Exception as e:
            logger.error(f"Failed to get document stats for project {project.name}: {e}")
            return {'error': str(e)}

    async def get_project_stats(self, project: Project) -> dict[str, Any]:
        """
        Get project-specific statistics for data projects.

        Args:
            project: Project instance

        Returns:
            Dictionary containing project statistics
        """
        try:
            document_stats = await self.get_document_stats(project)

            # Add vector store specific stats
            vector_store_stats = await self._get_vector_store_stats(project)

            stats = {
                'type_specific_stats': {
                    **document_stats,
                    **vector_store_stats,
                    'embedding_model': project.settings.get('embedding_model'),
                    'chunk_size': project.settings.get('chunk_size'),
                    'vector_store_type': project.settings.get('vector_store_type')
                }
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get project stats for {project.name}: {e}")
            return {'type_specific_stats': {}}

    # Private helper methods

    async def _initialize_vector_store(self, project: Project) -> None:
        """Initialize vector store for the project."""
        try:
            # Get vector store configuration
            vector_store_type = project.settings.get('vector_store_type', 'sqlite_vec')

            if vector_store_type == 'sqlite_vec':
                await self._initialize_sqlite_vec_store(project)
            elif vector_store_type == 'qdrant':
                await self._initialize_qdrant_store(project)
            else:
                raise ValueError(f"Unsupported vector store type: {vector_store_type}")

        except Exception as e:
            logger.error(f"Failed to initialize vector store for project {project.name}: {e}")
            raise

    async def _initialize_sqlite_vec_store(self, project: Project) -> None:
        """Initialize SQLite vector store."""
        # Create SQLite vector database
        db_path = Path(project.get_project_directory()) / "vectors" / "vectors.db"
        db_path.parent.mkdir(exist_ok=True)

        # In a real implementation, this would create the vector tables
        # For now, just create an empty file
        if not db_path.exists():
            db_path.touch()

    async def _initialize_qdrant_store(self, project: Project) -> None:
        """Initialize Qdrant vector store."""
        # In a real implementation, this would create Qdrant collection
        # For now, just create a configuration file
        config_path = Path(project.get_project_directory()) / "vectors" / "qdrant_config.json"
        config_path.parent.mkdir(exist_ok=True)

        config = {
            'collection_name': f"bablib_{project.name}",
            'vector_size': 1024,  # Size for mxbai-embed-large
            'distance': 'cosine'
        }

        import json
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

    async def _initialize_document_database(self, project: Project) -> None:
        """Initialize database for document metadata."""
        # Create document metadata database
        db_path = Path(project.get_project_directory()) / "documents.db"

        # In a real implementation, this would create database tables
        # For now, create a simple JSON file for document storage
        documents_file = Path(project.get_project_directory()) / "documents.json"
        if not documents_file.exists():
            import json
            with open(documents_file, 'w') as f:
                json.dump([], f)

    async def _cleanup_vector_store(self, project: Project) -> None:
        """Clean up vector store resources."""
        try:
            vector_store_type = project.settings.get('vector_store_type', 'sqlite_vec')

            if vector_store_type == 'sqlite_vec':
                # Archive SQLite database
                db_path = Path(project.get_project_directory()) / "vectors" / "vectors.db"
                if db_path.exists():
                    archive_path = db_path.with_suffix('.db.archive')
                    db_path.rename(archive_path)

            elif vector_store_type == 'qdrant':
                # In a real implementation, this would drop Qdrant collection
                config_path = Path(project.get_project_directory()) / "vectors" / "qdrant_config.json"
                if config_path.exists():
                    config_path.unlink()

        except Exception as e:
            logger.warning(f"Failed to cleanup vector store for project {project.name}: {e}")

    async def _stop_active_processing(self, project: Project) -> None:
        """Stop any active document processing operations."""
        # In a real implementation, this would coordinate with processing tasks
        # For now, just log the operation
        logger.info(f"Stopping active processing for project {project.name}")

    async def _archive_project_data(self, project: Project) -> None:
        """Archive project data before cleanup."""
        try:
            import shutil
            from datetime import datetime

            project_dir = Path(project.get_project_directory())
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f"{project.name}_data_{timestamp}"

            # Archive documents and vectors
            for subdir in ['documents', 'processed', 'vectors']:
                source_dir = project_dir / subdir
                if source_dir.exists():
                    archive_path = project_dir / f"{archive_name}_{subdir}.tar.gz"
                    shutil.make_archive(
                        str(project_dir / f"{archive_name}_{subdir}"),
                        'gztar',
                        str(source_dir)
                    )

            logger.info(f"Archived data for project: {project.name}")

        except Exception as e:
            logger.warning(f"Failed to archive data for project {project.name}: {e}")

    async def _extract_document_content(self, file_path: Path) -> str:
        """Extract text content from document based on file type."""
        try:
            file_ext = file_path.suffix.lower()

            if file_ext in ['.txt', '.md']:
                with open(file_path, encoding='utf-8') as f:
                    return f.read()

            elif file_ext == '.html':
                # Simple HTML text extraction
                with open(file_path, encoding='utf-8') as f:
                    html_content = f.read()
                # In a real implementation, would use BeautifulSoup
                import re
                text = re.sub(r'<[^>]+>', '', html_content)
                return text.strip()

            elif file_ext == '.json':
                # Extract text from JSON values
                import json
                with open(file_path, encoding='utf-8') as f:
                    data = json.load(f)
                return str(data)

            else:
                # For other formats, return filename as placeholder
                return f"Content of {file_path.name} (format: {file_ext})"

        except Exception as e:
            logger.warning(f"Failed to extract content from {file_path}: {e}")
            return ""

    async def _process_document_chunks(
        self,
        project: Project,
        document: DataDocument,
        chunks: list[dict[str, Any]]
    ) -> None:
        """Process document chunks through vector store."""
        # In a real implementation, this would:
        # 1. Generate embeddings for each chunk
        # 2. Store embeddings in vector database
        # 3. Create search indexes
        logger.info(f"Processing {len(chunks)} chunks for document {document.title}")

    async def _save_document_record(self, project: Project, document: DataDocument) -> None:
        """Save document record to project database."""
        try:
            documents_file = Path(project.get_project_directory()) / "documents.json"

            # Load existing documents
            documents_data = []
            if documents_file.exists():
                import json
                with open(documents_file) as f:
                    documents_data = json.load(f)

            # Add new document
            document_dict = document.dict()
            # Convert datetime objects to strings for JSON serialization
            for key, value in document_dict.items():
                if hasattr(value, 'isoformat'):
                    document_dict[key] = value.isoformat()

            documents_data.append(document_dict)

            # Save updated documents
            import json
            with open(documents_file, 'w') as f:
                json.dump(documents_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save document record for {document.title}: {e}")

    async def _load_project_documents(self, project: Project) -> list[DataDocument]:
        """Load all documents for the project."""
        try:
            documents_file = Path(project.get_project_directory()) / "documents.json"

            if not documents_file.exists():
                return []

            import json
            with open(documents_file) as f:
                documents_data = json.load(f)

            documents = []
            for doc_data in documents_data:
                # Convert string dates back to datetime
                if 'processed_date' in doc_data and isinstance(doc_data['processed_date'], str):
                    from datetime import datetime
                    doc_data['processed_date'] = datetime.fromisoformat(doc_data['processed_date'])

                document = DataDocument(**doc_data)
                documents.append(document)

            return documents

        except Exception as e:
            logger.error(f"Failed to load documents for project {project.name}: {e}")
            return []

    async def _get_vector_store(self, project: Project) -> Any:
        """Get vector store instance for the project."""
        # In a real implementation, this would return actual vector store client
        return MockVectorStore()

    async def _get_vector_store_stats(self, project: Project) -> dict[str, Any]:
        """Get vector store specific statistics."""
        return {
            'vector_count': 0,  # Would be actual count from vector store
            'index_size': 0,    # Would be actual index size
            'last_indexed': None  # Would be last indexing timestamp
        }

    def __str__(self) -> str:
        """String representation of DataProject handler."""
        return "DataProject(document processing and vector storage)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return "DataProject(type=data, capabilities=[document_processing, vector_search, text_extraction])"


class MockVectorStore:
    """Mock vector store for development."""

    async def search(self, query: str, limit: int, project_name: str) -> list[dict[str, Any]]:
        """Mock search implementation."""
        return []
