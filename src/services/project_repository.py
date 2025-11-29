"""Project repository with unified schema support."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from ..models.compatibility_status import CompatibilityStatus
from ..models.schema_version import SchemaVersion
from ..models.unified_project import UnifiedProject, UnifiedProjectStatus
from ..logic.projects.models.project import ProjectType


logger = logging.getLogger(__name__)


class ProjectRepositoryError(Exception):
    """Base exception for project repository errors."""
    pass


class ProjectRepository:
    """Repository for persisting and retrieving projects with unified schema."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize project repository.

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

        # Database connection
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and ensure schema exists."""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Open database connection
            self._connection = await aiosqlite.connect(str(self.db_path))

            # Enable foreign keys and optimize settings
            await self._connection.execute("PRAGMA foreign_keys = ON")
            await self._connection.execute("PRAGMA journal_mode = WAL")
            await self._connection.execute("PRAGMA synchronous = NORMAL")

            # Create schema
            await self._create_schema()

            self.logger.info(f"Initialized project repository with database: {self.db_path}")

        except Exception as e:
            self.logger.error(f"Failed to initialize project repository: {e}")
            raise ProjectRepositoryError(f"Failed to initialize repository: {e}")

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_schema(self) -> None:
        """Create database schema for unified projects."""
        # Main projects table with unified schema
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 3,
                type TEXT,
                status TEXT NOT NULL,
                compatibility_status TEXT NOT NULL DEFAULT 'compatible',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_crawl_at TEXT,
                source_url TEXT,
                settings_json TEXT NOT NULL DEFAULT '{}',
                statistics_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
        """)

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)",
            "CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type)",
            "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)",
            "CREATE INDEX IF NOT EXISTS idx_projects_compatibility ON projects(compatibility_status)",
            "CREATE INDEX IF NOT EXISTS idx_projects_schema_version ON projects(schema_version)",
            "CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at)"
        ]

        for index_sql in indexes:
            await self._connection.execute(index_sql)

        await self._connection.commit()

    async def save(self, project: UnifiedProject) -> None:
        """
        Save project to database.

        Args:
            project: Project to save

        Raises:
            ProjectRepositoryError: If save operation fails
        """
        try:
            await self._connection.execute("""
                INSERT OR REPLACE INTO projects (
                    id, name, schema_version, type, status, compatibility_status,
                    created_at, updated_at, last_crawl_at, source_url,
                    settings_json, statistics_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                project.name,
                project.schema_version,
                project.type.value if project.type else None,
                project.status.value,
                project.compatibility_status.value,
                project.created_at.isoformat(),
                project.updated_at.isoformat(),
                project.last_crawl_at.isoformat() if project.last_crawl_at else None,
                project.source_url,
                json.dumps(project.settings),
                json.dumps(project.statistics),
                json.dumps(project.metadata)
            ))
            await self._connection.commit()

            self.logger.debug(f"Saved project '{project.name}' (ID: {project.id})")

        except Exception as e:
            self.logger.error(f"Failed to save project '{project.name}': {e}")
            raise ProjectRepositoryError(f"Failed to save project: {e}")

    async def find_by_id(self, project_id: str) -> Optional[UnifiedProject]:
        """
        Find project by ID.

        Args:
            project_id: Project ID to search for

        Returns:
            UnifiedProject if found, None otherwise

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,)
            )
            row = await cursor.fetchone()
            await cursor.close()

            if row:
                return self._row_to_project(row)
            return None

        except Exception as e:
            self.logger.error(f"Failed to find project by ID '{project_id}': {e}")
            raise ProjectRepositoryError(f"Failed to find project by ID: {e}")

    async def find_by_name(self, name: str) -> Optional[UnifiedProject]:
        """
        Find project by name.

        Args:
            name: Project name to search for

        Returns:
            UnifiedProject if found, None otherwise

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute(
                "SELECT * FROM projects WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()
            await cursor.close()

            if row:
                return self._row_to_project(row)
            return None

        except Exception as e:
            self.logger.error(f"Failed to find project by name '{name}': {e}")
            raise ProjectRepositoryError(f"Failed to find project by name: {e}")

    async def find_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "updated_at",
        order_direction: str = "DESC"
    ) -> list[UnifiedProject]:
        """
        Find all projects with optional pagination and ordering.

        Args:
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            order_by: Field to order by
            order_direction: Order direction (ASC or DESC)

        Returns:
            List of UnifiedProject objects

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            # Validate order parameters
            valid_order_fields = [
                'name', 'created_at', 'updated_at', 'status', 'type', 'schema_version'
            ]
            if order_by not in valid_order_fields:
                order_by = 'updated_at'

            if order_direction.upper() not in ['ASC', 'DESC']:
                order_direction = 'DESC'

            query = f"SELECT * FROM projects ORDER BY {order_by} {order_direction.upper()}"
            params = []

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            if offset:
                query += " OFFSET ?" if limit else " LIMIT -1 OFFSET ?"
                params.append(offset)

            cursor = await self._connection.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()

            return [self._row_to_project(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Failed to find all projects: {e}")
            raise ProjectRepositoryError(f"Failed to find all projects: {e}")

    async def find_by_filters(
        self,
        status: Optional[UnifiedProjectStatus] = None,
        project_type: Optional[ProjectType] = None,
        compatibility_status: Optional[CompatibilityStatus] = None,
        schema_version: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[UnifiedProject]:
        """
        Find projects by various filters.

        Args:
            status: Filter by project status
            project_type: Filter by project type
            compatibility_status: Filter by compatibility status
            schema_version: Filter by schema version
            limit: Maximum number of projects to return

        Returns:
            List of matching UnifiedProject objects

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            query = "SELECT * FROM projects WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if project_type:
                query += " AND type = ?"
                params.append(project_type.value)

            if compatibility_status:
                query += " AND compatibility_status = ?"
                params.append(compatibility_status.value)

            if schema_version is not None:
                query += " AND schema_version = ?"
                params.append(schema_version)

            query += " ORDER BY updated_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = await self._connection.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()

            return [self._row_to_project(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Failed to find projects by filters: {e}")
            raise ProjectRepositoryError(f"Failed to find projects by filters: {e}")

    async def find_incompatible_projects(self) -> list[UnifiedProject]:
        """
        Find all projects with incompatible schema versions.

        Returns:
            List of incompatible projects

        Raises:
            ProjectRepositoryError: If query fails
        """
        return await self.find_by_filters(
            compatibility_status=CompatibilityStatus.INCOMPATIBLE
        )

    async def find_projects_by_name_pattern(self, pattern: str) -> list[UnifiedProject]:
        """
        Find projects matching name pattern.

        Args:
            pattern: Name pattern (supports SQL LIKE wildcards)

        Returns:
            List of matching projects

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute(
                "SELECT * FROM projects WHERE name LIKE ? ORDER BY name",
                (pattern,)
            )
            rows = await cursor.fetchall()
            await cursor.close()

            return [self._row_to_project(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Failed to find projects by name pattern '{pattern}': {e}")
            raise ProjectRepositoryError(f"Failed to find projects by name pattern: {e}")

    async def delete_by_id(self, project_id: str) -> bool:
        """
        Delete project by ID.

        Args:
            project_id: Project ID to delete

        Returns:
            True if project was deleted, False if not found

        Raises:
            ProjectRepositoryError: If delete operation fails
        """
        try:
            cursor = await self._connection.execute(
                "DELETE FROM projects WHERE id = ?",
                (project_id,)
            )

            deleted = cursor.rowcount > 0
            await self._connection.commit()
            await cursor.close()

            if deleted:
                self.logger.info(f"Deleted project with ID: {project_id}")

            return deleted

        except Exception as e:
            self.logger.error(f"Failed to delete project by ID '{project_id}': {e}")
            raise ProjectRepositoryError(f"Failed to delete project: {e}")

    async def delete_by_name(self, name: str) -> bool:
        """
        Delete project by name.

        Args:
            name: Project name to delete

        Returns:
            True if project was deleted, False if not found

        Raises:
            ProjectRepositoryError: If delete operation fails
        """
        try:
            cursor = await self._connection.execute(
                "DELETE FROM projects WHERE name = ?",
                (name,)
            )

            deleted = cursor.rowcount > 0
            await self._connection.commit()
            await cursor.close()

            if deleted:
                self.logger.info(f"Deleted project with name: {name}")

            return deleted

        except Exception as e:
            self.logger.error(f"Failed to delete project by name '{name}': {e}")
            raise ProjectRepositoryError(f"Failed to delete project: {e}")

    async def count_all(self) -> int:
        """
        Count total number of projects.

        Returns:
            Total project count

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute("SELECT COUNT(*) FROM projects")
            row = await cursor.fetchone()
            await cursor.close()

            return row[0]

        except Exception as e:
            self.logger.error(f"Failed to count projects: {e}")
            raise ProjectRepositoryError(f"Failed to count projects: {e}")

    async def count_by_status(self, status: UnifiedProjectStatus) -> int:
        """
        Count projects by status.

        Args:
            status: Project status to count

        Returns:
            Number of projects with the specified status

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute(
                "SELECT COUNT(*) FROM projects WHERE status = ?",
                (status.value,)
            )
            row = await cursor.fetchone()
            await cursor.close()

            return row[0]

        except Exception as e:
            self.logger.error(f"Failed to count projects by status '{status.value}': {e}")
            raise ProjectRepositoryError(f"Failed to count projects by status: {e}")

    async def exists_by_name(self, name: str) -> bool:
        """
        Check if project exists by name.

        Args:
            name: Project name to check

        Returns:
            True if project exists, False otherwise

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute(
                "SELECT 1 FROM projects WHERE name = ? LIMIT 1",
                (name,)
            )
            row = await cursor.fetchone()
            await cursor.close()

            return row is not None

        except Exception as e:
            self.logger.error(f"Failed to check if project exists by name '{name}': {e}")
            raise ProjectRepositoryError(f"Failed to check project existence: {e}")

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get repository statistics.

        Returns:
            Dictionary with repository statistics

        Raises:
            ProjectRepositoryError: If query fails
        """
        try:
            cursor = await self._connection.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN compatibility_status = 'compatible' THEN 1 END) as compatible,
                    COUNT(CASE WHEN compatibility_status = 'incompatible' THEN 1 END) as incompatible,
                    COUNT(CASE WHEN type = 'crawling' THEN 1 END) as crawling_projects,
                    COUNT(CASE WHEN type = 'data' THEN 1 END) as data_projects,
                    COUNT(CASE WHEN type = 'storage' THEN 1 END) as storage_projects,
                    AVG(schema_version) as avg_schema_version,
                    MIN(created_at) as oldest_project,
                    MAX(updated_at) as last_updated
                FROM projects
            """)
            row = await cursor.fetchone()
            await cursor.close()

            return {
                "total_projects": row[0],
                "compatible_projects": row[1],
                "incompatible_projects": row[2],
                "crawling_projects": row[3],
                "data_projects": row[4],
                "storage_projects": row[5],
                "compatibility_rate": round(row[1] / row[0] * 100, 1) if row[0] > 0 else 0,
                "average_schema_version": round(row[6], 1) if row[6] else 0,
                "oldest_project_date": row[7],
                "last_updated_date": row[8]
            }

        except Exception as e:
            self.logger.error(f"Failed to get repository statistics: {e}")
            raise ProjectRepositoryError(f"Failed to get statistics: {e}")

    async def update_compatibility_status(
        self,
        project_id: str,
        new_status: CompatibilityStatus
    ) -> bool:
        """
        Update project compatibility status.

        Args:
            project_id: Project ID to update
            new_status: New compatibility status

        Returns:
            True if project was updated, False if not found

        Raises:
            ProjectRepositoryError: If update fails
        """
        try:
            cursor = await self._connection.execute("""
                UPDATE projects
                SET compatibility_status = ?, updated_at = ?
                WHERE id = ?
            """, (
                new_status.value,
                datetime.now(timezone.utc).isoformat(),
                project_id
            ))

            updated = cursor.rowcount > 0
            await self._connection.commit()
            await cursor.close()

            if updated:
                self.logger.info(f"Updated compatibility status for project {project_id} to {new_status.value}")

            return updated

        except Exception as e:
            self.logger.error(f"Failed to update compatibility status for project {project_id}: {e}")
            raise ProjectRepositoryError(f"Failed to update compatibility status: {e}")

    def _row_to_project(self, row) -> UnifiedProject:
        """Convert database row to UnifiedProject."""
        # Parse JSON fields
        settings = json.loads(row[10]) if row[10] else {}
        statistics = json.loads(row[11]) if row[11] else {}
        metadata = json.loads(row[12]) if row[12] else {}

        # Parse datetime fields
        created_at = datetime.fromisoformat(row[6])
        updated_at = datetime.fromisoformat(row[7])
        last_crawl_at = datetime.fromisoformat(row[8]) if row[8] else None

        # Create project
        project = UnifiedProject(
            id=row[0],
            name=row[1],
            schema_version=row[2],
            type=ProjectType(row[3]) if row[3] else None,
            status=UnifiedProjectStatus(row[4]),
            compatibility_status=CompatibilityStatus(row[5]),
            created_at=created_at,
            updated_at=updated_at,
            last_crawl_at=last_crawl_at,
            source_url=row[9],
            settings=settings,
            statistics=statistics,
            metadata=metadata
        )

        return project

    async def begin_transaction(self):
        """Begin database transaction."""
        await self._connection.execute("BEGIN")

    async def commit_transaction(self):
        """Commit database transaction."""
        await self._connection.commit()

    async def rollback_transaction(self):
        """Rollback database transaction."""
        await self._connection.rollback()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()