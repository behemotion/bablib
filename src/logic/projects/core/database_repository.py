"""Database repository for project registry and data persistence."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from ..models.files import DataDocument, FileInventory, StorageFile
from ..models.project import Project, ProjectStatus, ProjectType
from ..models.upload import UploadSource, UploadSourceType, UploadStatus

logger = logging.getLogger(__name__)


class ProjectDatabaseRepository:
    """
    Database repository for project registry and data persistence.

    Manages project metadata in a global registry database and
    project-specific data in separate databases for each project.
    """

    def __init__(self, data_directory: str | None = None):
        """Initialize repository with data directory."""
        self.data_directory = data_directory or self._get_default_data_directory()
        self.registry_path = Path(self.data_directory) / "project_registry.db"
        self._connections: dict[str, aiosqlite.Connection] = {}
        self._initialized = False

    def _get_default_data_directory(self) -> str:
        """Get default data directory using XDG specification."""
        import os
        return os.environ.get(
            'BABLIB_DATA_DIR',
            str(Path.home() / '.local' / 'share' / 'bablib')
        )

    async def initialize(self) -> None:
        """Initialize database repository."""
        if self._initialized:
            return

        # Ensure directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Create registry database
        await self._ensure_registry_schema()
        self._initialized = True
        logger.info(f"Project database repository initialized at {self.registry_path}")

    async def _ensure_registry_schema(self) -> None:
        """Create or update project registry schema."""
        async with aiosqlite.connect(str(self.registry_path)) as conn:
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.execute("PRAGMA journal_mode = WAL")

            # Create projects table with new schema supporting project types
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    settings_json TEXT,
                    metadata_json TEXT
                )
            """)

            # Create indexes for performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_name ON projects (name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_type ON projects (type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status)")

            # Create upload operations tracking table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS upload_operations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_location TEXT NOT NULL,
                    files_processed INTEGER DEFAULT 0,
                    files_total INTEGER DEFAULT 0,
                    bytes_processed INTEGER DEFAULT 0,
                    bytes_total INTEGER DEFAULT 0,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    metadata_json TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                )
            """)

            # Create project settings table for hierarchical configuration
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS project_settings (
                    project_id TEXT PRIMARY KEY,
                    max_file_size INTEGER,
                    allowed_formats_json TEXT,
                    type_specific_json TEXT,
                    updated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                )
            """)

            await conn.commit()

    async def save_project(self, project: Project) -> None:
        """Save project to registry database."""
        async with aiosqlite.connect(str(self.registry_path)) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO projects
                (id, name, type, status, created_at, updated_at, settings_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                project.name,
                project.type.value if isinstance(project.type, ProjectType) else project.type,
                project.status.value if isinstance(project.status, ProjectStatus) else project.status,
                project.created_at.isoformat() if isinstance(project.created_at, datetime) else project.created_at,
                project.updated_at.isoformat() if isinstance(project.updated_at, datetime) else project.updated_at,
                json.dumps(project.settings),
                json.dumps(project.metadata)
            ))

            # Also save project-specific settings if they exist
            if project.settings:
                await conn.execute("""
                    INSERT OR REPLACE INTO project_settings
                    (project_id, max_file_size, allowed_formats_json, type_specific_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    project.id,
                    project.settings.get('max_file_size'),
                    json.dumps(project.settings.get('allowed_formats', [])),
                    json.dumps({k: v for k, v in project.settings.items()
                               if k not in ['max_file_size', 'allowed_formats']}),
                    datetime.now(timezone.utc).isoformat()
                ))

            await conn.commit()
            logger.debug(f"Saved project {project.name} to registry")

    async def get_project(self, name: str) -> Project | None:
        """Get project by name from registry."""
        async with aiosqlite.connect(str(self.registry_path)) as conn:
            cursor = await conn.execute(
                "SELECT * FROM projects WHERE name = ?", (name,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_project(row)

    async def list_projects(
        self,
        status: ProjectStatus | None = None,
        project_type: ProjectType | None = None,
        limit: int | None = None
    ) -> list[Project]:
        """List projects with optional filtering."""
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, ProjectStatus) else status)

        if project_type:
            query += " AND type = ?"
            params.append(project_type.value if isinstance(project_type, ProjectType) else project_type)

        query += " ORDER BY updated_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        async with aiosqlite.connect(str(self.registry_path)) as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

            return [self._row_to_project(row) for row in rows]

    async def delete_project(self, name: str) -> bool:
        """Delete project from registry and clean up project database."""
        project = await self.get_project(name)
        if not project:
            return False

        # Delete project database if it exists
        project_db_path = self._get_project_db_path(project.name)
        if project_db_path.exists():
            project_db_path.unlink()
            logger.debug(f"Deleted project database: {project_db_path}")

        # Delete from registry
        async with aiosqlite.connect(str(self.registry_path)) as conn:
            await conn.execute("DELETE FROM projects WHERE name = ?", (name,))
            await conn.commit()

        logger.info(f"Deleted project {name} from registry")
        return True

    async def update_project_status(self, name: str, status: ProjectStatus) -> None:
        """Update project status."""
        async with aiosqlite.connect(str(self.registry_path)) as conn:
            await conn.execute("""
                UPDATE projects
                SET status = ?, updated_at = ?
                WHERE name = ?
            """, (
                status.value if isinstance(status, ProjectStatus) else status,
                datetime.now(timezone.utc).isoformat(),
                name
            ))
            await conn.commit()

    def _row_to_project(self, row: tuple) -> Project:
        """Convert database row to Project instance."""
        return Project(
            id=row[0],
            name=row[1],
            type=row[2],  # Will be converted by Pydantic
            status=row[3],  # Will be converted by Pydantic
            created_at=row[4],  # Will be parsed by Pydantic
            updated_at=row[5],  # Will be parsed by Pydantic
            settings=json.loads(row[6]) if row[6] else {},
            metadata=json.loads(row[7]) if row[7] else {}
        )

    # Project-specific database operations

    def _get_project_db_path(self, project_name: str) -> Path:
        """Get database path for specific project."""
        projects_dir = Path(self.data_directory) / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        return projects_dir / f"{project_name}.db"

    async def _ensure_project_database(self, project: Project) -> None:
        """Create project-specific database with appropriate schema."""
        db_path = self._get_project_db_path(project.name)

        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.execute("PRAGMA journal_mode = WAL")

            # Schema based on project type
            if project.type == ProjectType.STORAGE:
                await self._create_storage_schema(conn)
            elif project.type == ProjectType.DATA:
                await self._create_data_schema(conn)
            elif project.type == ProjectType.CRAWLING:
                # Crawling projects use existing schema from database.py
                pass

            await conn.commit()

    async def _create_storage_schema(self, conn: aiosqlite.Connection) -> None:
        """Create schema for storage projects."""
        # Storage files table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS storage_files (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                upload_source_json TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT NOT NULL,
                tags_json TEXT,
                metadata_json TEXT,
                last_accessed TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                UNIQUE(project_id, filename)
            )
        """)

        # File inventory for search
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS file_inventory USING fts5(
                file_id,
                content_text,
                tags_concat,
                search_metadata,
                content='storage_files',
                tokenize='porter unicode61'
            )
        """)

        # Indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_filename ON storage_files (filename)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_checksum ON storage_files (checksum)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_mime ON storage_files (mime_type)")

    async def _create_data_schema(self, conn: aiosqlite.Connection) -> None:
        """Create schema for data projects."""
        # Data documents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS data_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_path TEXT NOT NULL,
                upload_source_json TEXT,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                chunk_count INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                character_count INTEGER DEFAULT 0,
                language TEXT,
                embedding_model TEXT,
                chunk_size INTEGER,
                chunk_overlap INTEGER,
                processing_success INTEGER DEFAULT 1,
                processing_errors_json TEXT,
                quality_score REAL,
                metadata_json TEXT
            )
        """)

        # Document chunks for vector storage reference
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                vector_id TEXT,
                metadata_json TEXT,
                FOREIGN KEY (document_id) REFERENCES data_documents (id) ON DELETE CASCADE,
                UNIQUE(document_id, chunk_index)
            )
        """)

        # Indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_title ON data_documents (title)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_source ON data_documents (source_path)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks (document_id)")

    # Storage project operations

    async def save_storage_file(self, project_name: str, file: StorageFile) -> None:
        """Save storage file to project database."""
        db_path = self._get_project_db_path(project_name)

        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO storage_files
                (id, project_id, filename, file_path, file_size, mime_type, upload_source_json,
                upload_date, checksum, tags_json, metadata_json, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file.id,
                file.project_id,
                file.filename,
                file.file_path,
                file.file_size,
                file.mime_type,
                json.dumps(file.upload_source.dict()),
                file.upload_date.isoformat(),
                file.checksum,
                json.dumps(file.tags),
                json.dumps(file.metadata),
                file.last_accessed.isoformat() if file.last_accessed else None,
                file.access_count
            ))

            # Update search inventory
            inventory = FileInventory.from_storage_file(file)
            await conn.execute("""
                INSERT OR REPLACE INTO file_inventory
                (file_id, content_text, tags_concat, search_metadata)
                VALUES (?, ?, ?, ?)
            """, (
                inventory.file_id,
                inventory.content_text or '',
                inventory.tags_concat,
                inventory.search_metadata
            ))

            await conn.commit()

    async def get_storage_files(
        self,
        project_name: str,
        limit: int | None = None
    ) -> list[StorageFile]:
        """Get storage files from project database."""
        db_path = self._get_project_db_path(project_name)

        if not db_path.exists():
            return []

        query = "SELECT * FROM storage_files ORDER BY upload_date DESC"
        if limit:
            query += f" LIMIT {limit}"

        async with aiosqlite.connect(str(db_path)) as conn:
            cursor = await conn.execute(query)
            rows = await cursor.fetchall()

            files = []
            for row in rows:
                upload_source = UploadSource(**json.loads(row[6]))
                file = StorageFile(
                    id=row[0],
                    project_id=row[1],
                    filename=row[2],
                    file_path=row[3],
                    file_size=row[4],
                    mime_type=row[5],
                    upload_source=upload_source,
                    upload_date=row[7],
                    checksum=row[8],
                    tags=json.loads(row[9]) if row[9] else [],
                    metadata=json.loads(row[10]) if row[10] else {},
                    last_accessed=row[11],
                    access_count=row[12]
                )
                files.append(file)

            return files

    # Data project operations

    async def save_data_document(self, project_name: str, document: DataDocument) -> None:
        """Save data document to project database."""
        db_path = self._get_project_db_path(project_name)

        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO data_documents
                (id, project_id, title, content, source_path, upload_source_json, processed_date,
                chunk_count, word_count, character_count, language, embedding_model, chunk_size,
                chunk_overlap, processing_success, processing_errors_json, quality_score, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                document.id,
                document.project_id,
                document.title,
                document.content,
                document.source_path,
                json.dumps(document.upload_source.dict()),
                document.processed_date.isoformat(),
                document.chunk_count,
                document.word_count,
                document.character_count,
                document.language,
                document.embedding_model,
                document.chunk_size,
                document.chunk_overlap,
                1 if document.processing_success else 0,
                json.dumps(document.processing_errors),
                document.quality_score,
                json.dumps(document.metadata)
            ))

            await conn.commit()

    async def get_data_documents(
        self,
        project_name: str,
        limit: int | None = None
    ) -> list[DataDocument]:
        """Get data documents from project database."""
        db_path = self._get_project_db_path(project_name)

        if not db_path.exists():
            return []

        query = "SELECT * FROM data_documents ORDER BY processed_date DESC"
        if limit:
            query += f" LIMIT {limit}"

        async with aiosqlite.connect(str(db_path)) as conn:
            cursor = await conn.execute(query)
            rows = await cursor.fetchall()

            documents = []
            for row in rows:
                upload_source = UploadSource(**json.loads(row[5]))
                doc = DataDocument(
                    id=row[0],
                    project_id=row[1],
                    title=row[2],
                    content=row[3],
                    source_path=row[4],
                    upload_source=upload_source,
                    processed_date=row[6],
                    chunk_count=row[7],
                    word_count=row[8],
                    character_count=row[9],
                    language=row[10],
                    embedding_model=row[11],
                    chunk_size=row[12],
                    chunk_overlap=row[13],
                    processing_success=bool(row[14]),
                    processing_errors=json.loads(row[15]) if row[15] else [],
                    quality_score=row[16],
                    metadata=json.loads(row[17]) if row[17] else {}
                )
                documents.append(doc)

            return documents

    # Upload operation tracking

    async def save_upload_operation(
        self,
        operation_id: str,
        project_id: str,
        source: UploadSource,
        status: UploadStatus
    ) -> None:
        """Save upload operation to registry."""
        async with aiosqlite.connect(str(self.registry_path)) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO upload_operations
                (id, project_id, status, source_type, source_location, started_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                operation_id,
                project_id,
                status.value if isinstance(status, UploadStatus) else status,
                source.type.value if isinstance(source.type, UploadSourceType) else source.type,
                source.location,
                datetime.now(timezone.utc).isoformat(),
                json.dumps({})
            ))
            await conn.commit()

    async def update_upload_operation(
        self,
        operation_id: str,
        status: UploadStatus | None = None,
        files_processed: int | None = None,
        files_total: int | None = None,
        bytes_processed: int | None = None,
        bytes_total: int | None = None,
        error_message: str | None = None
    ) -> None:
        """Update upload operation status."""
        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status.value if isinstance(status, UploadStatus) else status)

        if files_processed is not None:
            updates.append("files_processed = ?")
            params.append(files_processed)

        if files_total is not None:
            updates.append("files_total = ?")
            params.append(files_total)

        if bytes_processed is not None:
            updates.append("bytes_processed = ?")
            params.append(bytes_processed)

        if bytes_total is not None:
            updates.append("bytes_total = ?")
            params.append(bytes_total)

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if status in [UploadStatus.COMPLETE, UploadStatus.FAILED, UploadStatus.CANCELLED]:
            updates.append("completed_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())

        if not updates:
            return

        params.append(operation_id)
        query = f"UPDATE upload_operations SET {', '.join(updates)} WHERE id = ?"

        async with aiosqlite.connect(str(self.registry_path)) as conn:
            await conn.execute(query, params)
            await conn.commit()

    async def get_upload_operations(
        self,
        project_id: str | None = None,
        status: UploadStatus | None = None
    ) -> list[dict[str, Any]]:
        """Get upload operations with optional filtering."""
        query = "SELECT * FROM upload_operations WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, UploadStatus) else status)

        query += " ORDER BY started_at DESC"

        async with aiosqlite.connect(str(self.registry_path)) as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

            operations = []
            for row in rows:
                op = {
                    'id': row[0],
                    'project_id': row[1],
                    'status': row[2],
                    'source_type': row[3],
                    'source_location': row[4],
                    'files_processed': row[5],
                    'files_total': row[6],
                    'bytes_processed': row[7],
                    'bytes_total': row[8],
                    'started_at': row[9],
                    'completed_at': row[10],
                    'error_message': row[11],
                    'metadata': json.loads(row[12]) if row[12] else {}
                }
                operations.append(op)

            return operations

    async def cleanup(self) -> None:
        """Close all database connections."""
        for conn in self._connections.values():
            await conn.close()
        self._connections.clear()
        logger.info("Project database repository cleaned up")
