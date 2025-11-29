"""Unified project service with CRUD operations for unified schema."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from ..models.schema_version import SchemaVersion
from ..models.unified_project import UnifiedProject, UnifiedProjectStatus
from ..logic.projects.models.project import ProjectType
from .project_export_service import ProjectExportService


logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""
    pass


class ProjectAlreadyExistsError(Exception):
    """Raised when trying to create a project that already exists."""
    pass



class UnifiedProjectService:
    """Service for managing projects with unified schema."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize unified project service.

        Args:
            db_path: Optional database path, defaults to standard location
        """
        self.logger = logging.getLogger(__name__)

        # Database path
        if db_path is None:
            from pathlib import Path
            import os
            data_dir = os.environ.get('BABLIB_DATA_DIR',
                                      str(Path.home() / '.local' / 'share' / 'bablib'))
            self.db_path = Path(data_dir) / 'project_registry.db'
        else:
            self.db_path = db_path

        # Services
        self.export_service = ProjectExportService()

        # Database connection
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database and ensure schema is created."""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Open database connection
            self._connection = await aiosqlite.connect(str(self.db_path))

            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys = ON")

            # Create unified schema
            await self._create_unified_schema()

            self.logger.info(f"Initialized unified project service with database: {self.db_path}")

        except Exception as e:
            self.logger.error(f"Failed to initialize unified project service: {e}")
            raise

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_unified_schema(self) -> None:
        """Create unified database schema for projects and migrations."""
        # Main projects table with unified schema
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 3,
                type TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_crawl_at TEXT,
                source_url TEXT,
                settings_json TEXT NOT NULL DEFAULT '{}',
                statistics_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
        """)

        # Migration records table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS project_migrations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                from_schema_version INTEGER NOT NULL,
                to_schema_version INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                success BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                preserved_settings_json TEXT DEFAULT '{}',
                preserved_metadata_json TEXT DEFAULT '{}',
                data_size_bytes INTEGER DEFAULT 0,
                user_initiated BOOLEAN DEFAULT TRUE,
                initiated_by_command TEXT DEFAULT 'unknown'
            )
        """)

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)",
            "CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type)",
            "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)",
            "CREATE INDEX IF NOT EXISTS idx_projects_schema_version ON projects(schema_version)",
            "CREATE INDEX IF NOT EXISTS idx_migrations_project_id ON project_migrations(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_migrations_operation ON project_migrations(operation)"
        ]

        for index_sql in indexes:
            await self._connection.execute(index_sql)

        await self._connection.commit()

    async def create_project(
        self,
        name: str,
        project_type: ProjectType,
        settings: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        source_url: Optional[str] = None
    ) -> UnifiedProject:
        """
        Create a new project with unified schema.

        Args:
            name: Project name
            project_type: Type of project
            settings: Project-specific settings
            metadata: User-defined metadata
            source_url: Source URL for crawling projects

        Returns:
            Created UnifiedProject

        Raises:
            ProjectAlreadyExistsError: If project with same name exists
        """
        # Check if project already exists
        existing = await self.get_project_by_name(name)
        if existing:
            raise ProjectAlreadyExistsError(f"Project '{name}' already exists")

        # Create unified project
        project = UnifiedProject(
            name=name,
            type=project_type,
            status=UnifiedProjectStatus.ACTIVE,
            settings=settings or {},
            metadata=metadata or {},
            source_url=source_url
        )

        # Apply default settings
        default_settings = project.get_default_settings()
        for key, value in default_settings.items():
            if key not in project.settings:
                project.settings[key] = value

        # Store in database
        await self._store_project(project)

        self.logger.info(f"Created project '{name}' with unified schema (type: {project_type.value})")
        return project

    async def get_project_by_id(self, project_id: str) -> Optional[UnifiedProject]:
        """
        Get project by ID.

        Args:
            project_id: Project ID

        Returns:
            UnifiedProject if found, None otherwise
        """
        cursor = await self._connection.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()

        if row:
            return await self._row_to_project(row)
        return None

    async def get_project_by_name(self, name: str) -> Optional[UnifiedProject]:
        """
        Get project by name.

        Args:
            name: Project name

        Returns:
            UnifiedProject if found, None otherwise
        """
        cursor = await self._connection.execute(
            "SELECT * FROM projects WHERE name = ?",
            (name,)
        )
        row = await cursor.fetchone()
        await cursor.close()

        if row:
            return await self._row_to_project(row)
        return None

    async def list_projects(
        self,
        status_filter: Optional[UnifiedProjectStatus] = None,
        type_filter: Optional[ProjectType] = None,
        limit: Optional[int] = None
    ) -> list[UnifiedProject]:
        """
        List projects with optional filtering.

        Args:
            status_filter: Filter by project status
            type_filter: Filter by project type
            compatibility_filter: Filter by compatibility status
            limit: Maximum number of projects to return

        Returns:
            List of UnifiedProject objects
        """
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter.value)

        if type_filter:
            query += " AND type = ?"
            params.append(type_filter.value)


        query += " ORDER BY updated_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

        projects = []
        for row in rows:
            project = await self._row_to_project(row)
            projects.append(project)

        return projects

    async def update_project(
        self,
        project_id: str,
        settings: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        source_url: Optional[str] = None,
        force: bool = False
    ) -> UnifiedProject:
        """
        Update project settings and metadata.

        Args:
            project_id: Project ID to update
            settings: New settings to merge
            metadata: New metadata to merge
            source_url: New source URL
            force: Force update even for incompatible projects

        Returns:
            Updated UnifiedProject

        Raises:
            ProjectNotFoundError: If project not found
        """
        # Get existing project
        project = await self.get_project_by_id(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project with ID '{project_id}' not found")

        # No compatibility checks needed anymore

        # Update fields
        if settings:
            project.update_settings(settings)

        if metadata:
            project.metadata.update(metadata)
            project.updated_at = datetime.now(timezone.utc)

        if source_url is not None:
            project.source_url = source_url
            project.updated_at = datetime.now(timezone.utc)

        # Store updated project
        await self._store_project(project)

        self.logger.info(f"Updated project '{project.name}' (ID: {project_id})")
        return project

    async def delete_project(self, project_id: str) -> bool:
        """
        Delete project by ID.

        Args:
            project_id: Project ID to delete

        Returns:
            True if project was deleted, False if not found
        """
        # Get project for logging
        project = await self.get_project_by_id(project_id)
        if not project:
            return False

        # Delete from database
        cursor = await self._connection.execute(
            "DELETE FROM projects WHERE id = ?",
            (project_id,)
        )

        deleted = cursor.rowcount > 0
        await self._connection.commit()
        await cursor.close()

        if deleted:
            self.logger.info(f"Deleted project '{project.name}' (ID: {project_id})")

        return deleted

    async def get_project_statistics(self) -> dict[str, Any]:
        """
        Get overall project statistics.

        Returns:
            Dictionary with project statistics
        """
        cursor = await self._connection.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN type = 'crawling' THEN 1 END) as crawling_projects,
                COUNT(CASE WHEN type = 'data' THEN 1 END) as data_projects,
                COUNT(CASE WHEN type = 'storage' THEN 1 END) as storage_projects
            FROM projects
        """)
        row = await cursor.fetchone()
        await cursor.close()

        return {
            "total_projects": row[0],
            "crawling_projects": row[1],
            "data_projects": row[2],
            "storage_projects": row[3]
        }

    async def _store_project(self, project: UnifiedProject) -> None:
        """Store project in database."""
        await self._connection.execute("""
            INSERT OR REPLACE INTO projects (
                id, name, schema_version, type, status,
                created_at, updated_at, last_crawl_at, source_url,
                settings_json, statistics_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project.id,
            project.name,
            project.schema_version,
            project.type.value if hasattr(project.type, 'value') else project.type,
            project.status.value if hasattr(project.status, 'value') else project.status,
            project.created_at.isoformat(),
            project.updated_at.isoformat(),
            project.last_crawl_at.isoformat() if project.last_crawl_at else None,
            project.source_url,
            json.dumps(project.settings),
            json.dumps(project.statistics),
            json.dumps(project.metadata)
        ))
        await self._connection.commit()

    async def _row_to_project(self, row) -> UnifiedProject:
        """Convert database row to UnifiedProject."""
        # Parse JSON fields
        settings = json.loads(row[9]) if row[9] else {}
        statistics = json.loads(row[10]) if row[10] else {}
        metadata = json.loads(row[11]) if row[11] else {}

        # Parse datetime fields
        created_at = datetime.fromisoformat(row[5])
        updated_at = datetime.fromisoformat(row[6])
        last_crawl_at = datetime.fromisoformat(row[7]) if row[7] else None

        # Create project
        project = UnifiedProject(
            id=row[0],
            name=row[1],
            schema_version=row[2],
            type=ProjectType(row[3]) if row[3] else None,
            status=UnifiedProjectStatus(row[4]),
            created_at=created_at,
            updated_at=updated_at,
            last_crawl_at=last_crawl_at,
            source_url=row[8],
            settings=settings,
            statistics=statistics,
            metadata=metadata
        )

        return project

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()