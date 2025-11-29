"""Database service for managing project data."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger
from src.models import (
    CrawlSession,
    CrawlStatus,
    Page,
    PageStatus,
    Project,
    ProjectStatus,
)
from src.models.schema_version import SchemaVersion
from src.lib.exceptions import DatabaseSchemaError


class DatabaseError(Exception):
    """Database operation error."""
    pass


class DatabaseManager:
    """Manages SQLite database operations for Bablib."""

    # Class-level cache to avoid repeated migration checks
    _migrations_checked: dict[str, bool] = {}

    def __init__(self, config: BablibConfig | None = None):
        """Initialize database manager."""
        self.config = config or BablibConfig()
        self.db_path = self.config.database_path
        self.logger = get_component_logger("database")

        # Connection pool
        self._connection: aiosqlite.Connection | None = None  # Main DB connection
        self._project_connections: dict[str, aiosqlite.Connection] = {}  # Project-specific connections
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database connection and schema."""
        if self._initialized:
            return

        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Run synchronous migrations first (but only once per database path)
            db_path_str = str(self.db_path)
            if db_path_str not in DatabaseManager._migrations_checked:
                from src.services.database_migrator import DatabaseMigrator
                migrator = DatabaseMigrator(self.config)
                migrator.run_migrations()
                DatabaseManager._migrations_checked[db_path_str] = True

            # Create connection
            self._connection = await aiosqlite.connect(str(self.db_path))

            # Enable foreign keys and WAL mode
            await self._connection.execute("PRAGMA foreign_keys = ON")
            await self._connection.execute("PRAGMA journal_mode = WAL")

            # Create schema
            await self._create_schema()

            self._initialized = True
            self.logger.info("Database initialized", extra={
                "db_path": str(self.db_path),
                "schema_version": await self._get_schema_version()
            })

        except Exception as e:
            self.logger.error("Failed to initialize database", extra={
                "error": str(e),
                "db_path": str(self.db_path)
            })
            raise DatabaseError(f"Failed to initialize database: {e}")

    async def cleanup(self) -> None:
        """Clean up database connections."""
        # Close project-specific connections
        for project_id, conn in self._project_connections.items():
            await conn.close()
        self._project_connections.clear()

        # Close main connection
        if self._connection:
            await self._connection.close()
            self._connection = None
        self._initialized = False
        self.logger.info("Database connections closed")

    def get_connection(self):
        """Get database connection as async context manager.

        Returns:
            AsyncContextManager that yields aiosqlite.Connection
        """
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _connection_context():
            if not self._initialized:
                await self.initialize()
            yield self._connection

        return _connection_context()

    async def _create_schema(self) -> None:
        """Create main database schema with unified project structure."""
        schema_sql = """
        -- Schema version tracking
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Unified projects table supporting all project types
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            schema_version INTEGER NOT NULL DEFAULT 3,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_crawl_at TEXT,
            source_url TEXT,
            settings_json TEXT NOT NULL DEFAULT '{}',
            statistics_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        -- Shelfs table for organizing projects into collections
        CREATE TABLE IF NOT EXISTS shelfs (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_current BOOLEAN DEFAULT FALSE,
            metadata_json TEXT DEFAULT '{}'
        );

        -- Baskets table (projects within shelfs)
        CREATE TABLE IF NOT EXISTS baskets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            shelf_id TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'data',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_operation_at TEXT,

            -- Preserve all existing project fields
            status TEXT NOT NULL DEFAULT 'created',
            source_url TEXT,
            crawl_depth INTEGER DEFAULT 2,
            embedding_model TEXT DEFAULT 'mxbai-embed-large',
            chunk_size INTEGER DEFAULT 1000,
            chunk_overlap INTEGER DEFAULT 100,

            -- Statistics
            total_pages INTEGER DEFAULT 0,
            total_size_bytes INTEGER DEFAULT 0,
            successful_pages INTEGER DEFAULT 0,
            failed_pages INTEGER DEFAULT 0,

            -- Configuration
            settings_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',

            -- Schema compatibility
            schema_version INTEGER DEFAULT 4,

            FOREIGN KEY (shelf_id) REFERENCES shelfs (id) ON DELETE CASCADE,
            UNIQUE(shelf_id, name)
        );


        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
        CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type);
        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
        CREATE INDEX IF NOT EXISTS idx_projects_schema_version ON projects(schema_version);

        -- Shelf indexes
        CREATE INDEX IF NOT EXISTS idx_shelfs_name ON shelfs(name);
        CREATE INDEX IF NOT EXISTS idx_shelfs_is_current ON shelfs(is_current);

        -- Basket indexes
        CREATE INDEX IF NOT EXISTS idx_baskets_shelf_id ON baskets(shelf_id);
        CREATE INDEX IF NOT EXISTS idx_baskets_name ON baskets(name);
        CREATE INDEX IF NOT EXISTS idx_baskets_type ON baskets(type);
        CREATE INDEX IF NOT EXISTS idx_baskets_status ON baskets(status);


        -- Insert current schema version
        INSERT OR REPLACE INTO schema_version (version) VALUES (4);
        """

        await self._connection.executescript(schema_sql)
        await self._connection.commit()

    async def _get_schema_version(self) -> int:
        """Get current schema version."""
        try:
            cursor = await self._connection.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = await cursor.fetchone()
            return row[0] if row else 0
        except (aiosqlite.Error, ValueError, TypeError):
            return 0

    def _get_project_db_path(self, project_name: str) -> Path:
        """Get database path for a specific project."""
        projects_dir = Path.home() / ".local" / "share" / "bablib" / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        return projects_dir / f"{project_name}.db"

    def _get_box_db_path(self, box_name: str) -> Path:
        """Get database path for a specific box."""
        boxes_dir = Path.home() / ".local" / "share" / "bablib" / "boxes"
        boxes_dir.mkdir(parents=True, exist_ok=True)
        return boxes_dir / f"{box_name}.db"

    async def _get_box_connection(self, box_name: str) -> aiosqlite.Connection:
        """Get or create database connection for a specific box."""
        cache_key = f"box_{box_name}"
        if cache_key in self._project_connections:
            return self._project_connections[cache_key]

        # Create box database path
        box_db_path = self._get_box_db_path(box_name)

        # Create connection
        conn = await aiosqlite.connect(str(box_db_path))
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")

        # Create box-specific schema (sessions and pages)
        box_schema_sql = """
        -- Schema version tracking
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Crawl sessions table
        CREATE TABLE IF NOT EXISTS crawl_sessions (
            id TEXT PRIMARY KEY,
            box_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            crawl_depth INTEGER NOT NULL,
            current_depth INTEGER NOT NULL DEFAULT 0,
            current_url TEXT,
            user_agent TEXT NOT NULL DEFAULT 'Bablib/1.0',
            rate_limit REAL NOT NULL DEFAULT 1.0,
            timeout INTEGER NOT NULL DEFAULT 30,
            created_at TIMESTAMP NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL,
            pages_discovered INTEGER NOT NULL DEFAULT 0,
            pages_crawled INTEGER NOT NULL DEFAULT 0,
            pages_failed INTEGER NOT NULL DEFAULT 0,
            pages_skipped INTEGER NOT NULL DEFAULT 0,
            total_size_bytes INTEGER NOT NULL DEFAULT 0,
            queue_size INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            error_count INTEGER NOT NULL DEFAULT 0,
            max_errors INTEGER NOT NULL DEFAULT 50,
            metadata TEXT,
            archived INTEGER NOT NULL DEFAULT 0
        );

        -- Pages table
        CREATE TABLE IF NOT EXISTS pages (
            id TEXT PRIMARY KEY,
            box_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'discovered',
            title TEXT,
            content_html TEXT,
            content_text TEXT,
            content_hash TEXT,
            mime_type TEXT NOT NULL DEFAULT 'text/html',
            charset TEXT NOT NULL DEFAULT 'utf-8',
            language TEXT,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            crawl_depth INTEGER NOT NULL,
            parent_url TEXT,
            response_code INTEGER,
            response_time_ms INTEGER,
            discovered_at TIMESTAMP NOT NULL,
            crawled_at TIMESTAMP,
            processed_at TIMESTAMP,
            indexed_at TIMESTAMP,
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            outbound_links TEXT,
            internal_links TEXT,
            external_links TEXT,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES crawl_sessions (id) ON DELETE CASCADE
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_sessions_box_id ON crawl_sessions (box_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON crawl_sessions (status);
        CREATE INDEX IF NOT EXISTS idx_pages_box_id ON pages (box_id);
        CREATE INDEX IF NOT EXISTS idx_pages_session_id ON pages (session_id);
        CREATE INDEX IF NOT EXISTS idx_pages_url ON pages (url);
        CREATE INDEX IF NOT EXISTS idx_pages_status ON pages (status);
        CREATE INDEX IF NOT EXISTS idx_pages_content_hash ON pages (content_hash);

        -- Insert current schema version
        INSERT OR REPLACE INTO schema_version (version) VALUES (1);
        """

        await conn.executescript(box_schema_sql)
        await conn.commit()

        # Cache the connection
        self._project_connections[cache_key] = conn

        self.logger.info("Box database initialized", extra={
            "box_name": box_name,
            "db_path": str(box_db_path)
        })

        return conn

    async def _get_project_connection(self, project_name: str) -> aiosqlite.Connection:
        """Get or create database connection for a specific project."""
        if project_name in self._project_connections:
            return self._project_connections[project_name]

        # Create project database path
        project_db_path = self._get_project_db_path(project_name)

        # Create connection
        conn = await aiosqlite.connect(str(project_db_path))
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")

        # Create project-specific schema (only sessions and pages)
        project_schema_sql = """
        -- Schema version tracking
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Crawl sessions table
        CREATE TABLE IF NOT EXISTS crawl_sessions (
            id TEXT PRIMARY KEY,
            box_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            crawl_depth INTEGER NOT NULL,
            current_depth INTEGER NOT NULL DEFAULT 0,
            current_url TEXT,
            user_agent TEXT NOT NULL DEFAULT 'Bablib/1.0',
            rate_limit REAL NOT NULL DEFAULT 1.0,
            timeout INTEGER NOT NULL DEFAULT 30,
            created_at TIMESTAMP NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL,
            pages_discovered INTEGER NOT NULL DEFAULT 0,
            pages_crawled INTEGER NOT NULL DEFAULT 0,
            pages_failed INTEGER NOT NULL DEFAULT 0,
            pages_skipped INTEGER NOT NULL DEFAULT 0,
            total_size_bytes INTEGER NOT NULL DEFAULT 0,
            queue_size INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            error_count INTEGER NOT NULL DEFAULT 0,
            max_errors INTEGER NOT NULL DEFAULT 50,
            metadata TEXT,
            archived INTEGER NOT NULL DEFAULT 0
        );

        -- Pages table
        CREATE TABLE IF NOT EXISTS pages (
            id TEXT PRIMARY KEY,
            box_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'discovered',
            title TEXT,
            content_html TEXT,
            content_text TEXT,
            content_hash TEXT,
            mime_type TEXT NOT NULL DEFAULT 'text/html',
            charset TEXT NOT NULL DEFAULT 'utf-8',
            language TEXT,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            crawl_depth INTEGER NOT NULL,
            parent_url TEXT,
            response_code INTEGER,
            response_time_ms INTEGER,
            discovered_at TIMESTAMP NOT NULL,
            crawled_at TIMESTAMP,
            processed_at TIMESTAMP,
            indexed_at TIMESTAMP,
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            outbound_links TEXT,
            internal_links TEXT,
            external_links TEXT,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES crawl_sessions (id) ON DELETE CASCADE
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_sessions_box_id ON crawl_sessions (box_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON crawl_sessions (status);
        CREATE INDEX IF NOT EXISTS idx_pages_box_id ON pages (box_id);
        CREATE INDEX IF NOT EXISTS idx_pages_session_id ON pages (session_id);
        CREATE INDEX IF NOT EXISTS idx_pages_url ON pages (url);
        CREATE INDEX IF NOT EXISTS idx_pages_status ON pages (status);
        CREATE INDEX IF NOT EXISTS idx_pages_content_hash ON pages (content_hash);

        -- Insert current schema version
        INSERT OR REPLACE INTO schema_version (version) VALUES (3);
        """

        await conn.executescript(project_schema_sql)
        await conn.commit()

        # Cache the connection
        self._project_connections[project_name] = conn

        self.logger.info("Project database initialized", extra={
            "project_name": project_name,
            "db_path": str(project_db_path)
        })

        return conn


    def _ensure_initialized(self) -> None:
        """Ensure database is initialized."""
        if not self._initialized:
            raise DatabaseError("Database not initialized. Call initialize() first.")

    # Project operations


    async def create_project(
        self,
        name: str,
        source_url: str | None = None,
        crawl_depth: int = 2,
        embedding_model: str = "mxbai-embed-large",
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        metadata: dict[str, Any] | None = None
    ) -> Project:
        """Create a new project."""
        self._ensure_initialized()

        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        project = Project(
            id=project_id,
            name=name,
            source_url=source_url,
            crawl_depth=crawl_depth,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )

        try:
            # Convert project-specific settings to JSON for unified schema
            settings = {
                "crawl_depth": project.crawl_depth,
                "embedding_model": project.embedding_model,
                "chunk_size": project.chunk_size,
                "chunk_overlap": project.chunk_overlap
            }

            statistics = {
                "total_pages": project.total_pages,
                "total_size_bytes": project.total_size_bytes,
                "successful_pages": project.successful_pages,
                "failed_pages": project.failed_pages
            }

            await self._connection.execute("""
                INSERT INTO projects (
                    id, name, source_url, status, type, created_at, updated_at,
                    settings_json, statistics_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id, project.name, project.source_url, project.status.value,
                "crawling",  # Default type for legacy projects
                project.created_at.isoformat(), project.updated_at.isoformat(),
                json.dumps(settings), json.dumps(statistics), json.dumps(project.metadata)
            ))
            await self._connection.commit()

            self.logger.info("Project created", extra={
                "project_id": project.id,
                "project_name": project.name,
                "source_url": project.source_url
            })

            return project

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: projects.name" in str(e):
                raise DatabaseError(f"Project with name '{name}' already exists")
            raise DatabaseError(f"Failed to create project: {e}")

    async def get_project(self, project_id: str) -> Project | None:
        """Get project by ID."""
        self._ensure_initialized()

        cursor = await self._connection.execute("""
            SELECT id, name, source_url, status, type, created_at, updated_at, last_crawl_at,
                   settings_json, statistics_json, metadata_json
            FROM projects WHERE id = ?
        """, (project_id,))

        row = await cursor.fetchone()
        if not row:
            return None

        return self._project_from_row(row)

    async def get_project_by_name(self, name: str) -> Project | None:
        """Get project by name."""
        self._ensure_initialized()

        cursor = await self._connection.execute("""
            SELECT id, name, source_url, status, type, created_at, updated_at, last_crawl_at,
                   settings_json, statistics_json, metadata_json
            FROM projects WHERE name = ?
        """, (name,))

        row = await cursor.fetchone()
        if not row:
            return None

        return self._project_from_row(row)

    async def list_projects(
        self,
        status: ProjectStatus | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> list[Project]:
        """List projects with optional filtering."""
        self._ensure_initialized()

        sql = """
            SELECT id, name, source_url, status, type, created_at, updated_at, last_crawl_at,
                   settings_json, statistics_json, metadata_json
            FROM projects
        """
        params = []

        if status:
            sql += " WHERE status = ?"
            params.append(status.value)

        sql += " ORDER BY created_at DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)
            if offset:
                sql += " OFFSET ?"
                params.append(offset)

        cursor = await self._connection.execute(sql, params)
        rows = await cursor.fetchall()

        return [self._project_from_row(row) for row in rows]

    async def update_project_status(self, project_id: str, status: ProjectStatus) -> Project:
        """Update project status."""
        self._ensure_initialized()

        now = datetime.now(timezone.utc)
        await self._connection.execute("""
            UPDATE projects SET status = ?, updated_at = ?
            WHERE id = ?
        """, (status.value, now.isoformat(), project_id))

        if status == ProjectStatus.READY:
            await self._connection.execute("""
                UPDATE projects SET last_crawl_at = ?
                WHERE id = ?
            """, (now.isoformat(), project_id))

        await self._connection.commit()

        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        return project

    async def update_project(
        self,
        project_id: str,
        source_url: str | None = None,
        crawl_depth: int | None = None,
        embedding_model: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        metadata: dict[str, Any] | None = None
    ) -> Project:
        """Update project fields."""
        self._ensure_initialized()

        # Build dynamic update query
        update_fields = []
        update_params = []

        if source_url is not None:
            update_fields.append("source_url = ?")
            update_params.append(source_url)

        if crawl_depth is not None:
            update_fields.append("crawl_depth = ?")
            update_params.append(crawl_depth)

        if embedding_model is not None:
            update_fields.append("embedding_model = ?")
            update_params.append(embedding_model)

        if chunk_size is not None:
            update_fields.append("chunk_size = ?")
            update_params.append(chunk_size)

        if chunk_overlap is not None:
            update_fields.append("chunk_overlap = ?")
            update_params.append(chunk_overlap)

        if metadata is not None:
            update_fields.append("metadata = ?")
            update_params.append(json.dumps(metadata))

        if not update_fields:
            # No fields to update, just return the current project
            project = await self.get_project(project_id)
            if not project:
                raise DatabaseError(f"Project {project_id} not found")
            return project

        # Always update the updated_at timestamp
        update_fields.append("updated_at = ?")
        update_params.append(datetime.now(timezone.utc).isoformat())
        update_params.append(project_id)

        sql = f"UPDATE projects SET {', '.join(update_fields)} WHERE id = ?"

        await self._connection.execute(sql, update_params)
        await self._connection.commit()

        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        self.logger.info("Project updated", extra={
            "project_id": project_id,
            "updated_fields": update_fields
        })

        return project

    async def update_project_statistics(
        self,
        project_id: str,
        total_pages: int,
        successful_pages: int,
        failed_pages: int,
        last_crawl_at: datetime
    ) -> Project:
        """Update project crawl statistics."""
        self._ensure_initialized()

        await self._connection.execute("""
            UPDATE projects SET
                total_pages = ?,
                successful_pages = ?,
                failed_pages = ?,
                last_crawl_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            total_pages,
            successful_pages,
            failed_pages,
            last_crawl_at.isoformat(),
            datetime.now(timezone.utc).isoformat(),
            project_id
        ))

        await self._connection.commit()

        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        return project

    async def delete_project(self, project_id: str) -> bool:
        """Delete project and all associated data."""
        self._ensure_initialized()

        cursor = await self._connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await self._connection.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            self.logger.info("Project deleted", extra={"project_id": project_id})

        return deleted

    # Crawl session operations

    async def create_crawl_session(
        self,
        box_id: str,
        crawl_depth: int,
        user_agent: str = "Bablib/1.0",
        rate_limit: float = 1.0,
        timeout: int = 30,
        max_errors: int = 50
    ) -> CrawlSession:
        """Create a new crawl session for a box."""
        self._ensure_initialized()

        # Get box to find box name
        box = await self.get_box(box_id=box_id)
        if not box:
            raise DatabaseError(f"Box {box_id} not found")

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        session = CrawlSession(
            id=session_id,
            box_id=box_id,
            crawl_depth=crawl_depth,
            user_agent=user_agent,
            rate_limit=rate_limit,
            timeout=timeout,
            max_errors=max_errors,
            created_at=now,
            updated_at=now
        )

        # Use box-specific database connection
        box_conn = await self._get_box_connection(box['name'])
        await box_conn.execute("""
            INSERT INTO crawl_sessions (
                id, box_id, status, crawl_depth, current_depth, user_agent, rate_limit,
                timeout, created_at, updated_at, pages_discovered, pages_crawled,
                pages_failed, pages_skipped, total_size_bytes, queue_size, error_count,
                max_errors, archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id, session.box_id, session.status.value, session.crawl_depth,
            session.current_depth, session.user_agent, session.rate_limit, session.timeout,
            session.created_at.isoformat(), session.updated_at.isoformat(),
            session.pages_discovered, session.pages_crawled, session.pages_failed,
            session.pages_skipped, session.total_size_bytes, session.queue_size, session.error_count,
            session.max_errors, session.archived
        ))
        await box_conn.commit()

        self.logger.info("Crawl session created", extra={
            "session_id": session.id,
            "box_id": box_id,
            "box_name": box['name']
        })

        return session

    async def get_crawl_session(self, session_id: str) -> CrawlSession | None:
        """Get crawl session by ID from any project database."""
        self._ensure_initialized()

        # First, try to find which project this session belongs to
        # Check all project databases
        for project_name, project_conn in self._project_connections.items():
            cursor = await project_conn.execute("""
                SELECT id, project_id, status, crawl_depth, current_depth, current_url, user_agent, rate_limit,
                       timeout, created_at, started_at, completed_at, updated_at,
                       pages_discovered, pages_crawled, pages_failed, pages_skipped,
                       total_size_bytes, queue_size, error_message, error_count, max_errors,
                       metadata, archived
                FROM crawl_sessions WHERE id = ?
            """, (session_id,))

            row = await cursor.fetchone()
            if row:
                return self._session_from_row(row)

        # If not found in cached connections, check all projects
        projects_cursor = await self._connection.execute("SELECT id, name FROM projects")
        projects = await projects_cursor.fetchall()

        for project_id, project_name in projects:
            project_conn = await self._get_project_connection(project_name)
            cursor = await project_conn.execute("""
                SELECT id, project_id, status, crawl_depth, current_depth, current_url, user_agent, rate_limit,
                       timeout, created_at, started_at, completed_at, updated_at,
                       pages_discovered, pages_crawled, pages_failed, pages_skipped,
                       total_size_bytes, queue_size, error_message, error_count, max_errors,
                       metadata, archived
                FROM crawl_sessions WHERE id = ?
            """, (session_id,))

            row = await cursor.fetchone()
            if row:
                return self._session_from_row(row)

        return None

    def _project_from_row(self, row: tuple) -> Project:
        """Create Project from database row (unified schema)."""
        (id, name, source_url, status, project_type, created_at, updated_at, last_crawl_at,
         settings_json, statistics_json, metadata_json) = row

        # Parse JSON fields
        settings = json.loads(settings_json) if settings_json else {}
        statistics = json.loads(statistics_json) if statistics_json else {}
        metadata = json.loads(metadata_json) if metadata_json else {}

        return Project(
            id=id,
            name=name,
            source_url=source_url,
            status=ProjectStatus(status),
            crawl_depth=settings.get("crawl_depth", 3),
            embedding_model=settings.get("embedding_model", "mxbai-embed-large"),
            chunk_size=settings.get("chunk_size", 500),
            chunk_overlap=settings.get("chunk_overlap", 50),
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            last_crawl_at=datetime.fromisoformat(last_crawl_at) if last_crawl_at else None,
            total_pages=statistics.get("total_pages", 0),
            total_size_bytes=statistics.get("total_size_bytes", 0),
            successful_pages=statistics.get("successful_pages", 0),
            failed_pages=statistics.get("failed_pages", 0),
            metadata=metadata
        )

    def _session_from_row(self, row: tuple) -> CrawlSession:
        """Create CrawlSession from database row."""
        (id, box_id, status, crawl_depth, current_depth, current_url, user_agent, rate_limit,
         timeout, created_at, started_at, completed_at, updated_at,
         pages_discovered, pages_crawled, pages_failed, pages_skipped,
         total_size_bytes, queue_size, error_message, error_count, max_errors,
         metadata, archived) = row

        return CrawlSession(
            id=id,
            box_id=box_id,
            status=CrawlStatus(status),
            crawl_depth=crawl_depth,
            current_depth=current_depth,
            current_url=current_url,
            user_agent=user_agent,
            rate_limit=rate_limit,
            timeout=timeout,
            created_at=datetime.fromisoformat(created_at),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
            updated_at=datetime.fromisoformat(updated_at),
            pages_discovered=pages_discovered,
            pages_crawled=pages_crawled,
            pages_failed=pages_failed,
            pages_skipped=pages_skipped,
            total_size_bytes=total_size_bytes,
            queue_size=queue_size,
            error_message=error_message,
            error_count=error_count,
            max_errors=max_errors,
            metadata=json.loads(metadata) if metadata else {},
            archived=bool(archived)
        )

    async def update_crawl_session(self, session: CrawlSession) -> CrawlSession:
        """Update crawl session."""
        self._ensure_initialized()

        # Get box to find box name
        box = await self.get_box(box_id=session.box_id)
        if not box:
            raise DatabaseError(f"Box {session.box_id} not found")

        # Use box-specific database connection
        box_conn = await self._get_box_connection(box['name'])
        await box_conn.execute("""
            UPDATE crawl_sessions SET
                status = ?, current_depth = ?, current_url = ?, started_at = ?, completed_at = ?, updated_at = ?,
                pages_discovered = ?, pages_crawled = ?, pages_failed = ?,
                pages_skipped = ?, total_size_bytes = ?, queue_size = ?, error_message = ?,
                error_count = ?, metadata = ?
            WHERE id = ?
        """, (
            session.status.value, session.current_depth, session.current_url,
            session.started_at.isoformat() if session.started_at else None,
            session.completed_at.isoformat() if session.completed_at else None,
            session.updated_at.isoformat(),
            session.pages_discovered, session.pages_crawled, session.pages_failed,
            session.pages_skipped, session.total_size_bytes, session.queue_size, session.error_message,
            session.error_count, json.dumps(session.metadata), session.id
        ))
        await box_conn.commit()

        return session

    async def get_project_sessions(
        self,
        project_id: str,
        status: CrawlStatus | None = None,
        archived: bool = False
    ) -> list[CrawlSession]:
        """Get sessions for a project."""
        self._ensure_initialized()

        # Get project to find project name
        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        # Use project-specific database connection
        project_conn = await self._get_project_connection(project.name)

        sql = """
            SELECT id, project_id, status, crawl_depth, current_depth, current_url, user_agent, rate_limit,
                   timeout, created_at, started_at, completed_at, updated_at,
                   pages_discovered, pages_crawled, pages_failed, pages_skipped,
                   total_size_bytes, queue_size, error_message, error_count, max_errors,
                   metadata, archived
            FROM crawl_sessions WHERE project_id = ? AND archived = ?
        """
        params = [project_id, archived]

        if status:
            sql += " AND status = ?"
            params.append(status.value)

        sql += " ORDER BY created_at DESC"

        cursor = await project_conn.execute(sql, params)
        rows = await cursor.fetchall()

        return [self._session_from_row(row) for row in rows]

    async def cleanup_incomplete_sessions(self, project_id: str, reset_pages: bool = False) -> dict[str, int]:
        """Clean up incomplete crawl sessions and optionally reset pages for fresh crawl."""
        self._ensure_initialized()

        # Get project to find project name
        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        # Use project-specific database connection
        project_conn = await self._get_project_connection(project.name)

        # Find incomplete sessions (running, paused, or created)
        incomplete_statuses = [CrawlStatus.RUNNING.value, CrawlStatus.PAUSED.value, CrawlStatus.CREATED.value]

        # Get count of incomplete sessions
        cursor = await project_conn.execute("""
            SELECT COUNT(*) FROM crawl_sessions
            WHERE project_id = ? AND status IN ({})
        """.format(','.join('?' * len(incomplete_statuses))), [project_id] + incomplete_statuses)

        incomplete_count = (await cursor.fetchone())[0]

        # Mark incomplete sessions as failed with cleanup reason
        if incomplete_count > 0:
            await project_conn.execute("""
                UPDATE crawl_sessions
                SET status = ?, error_message = ?, updated_at = ?
                WHERE project_id = ? AND status IN ({})
            """.format(','.join('?' * len(incomplete_statuses))),
            [CrawlStatus.FAILED.value, "Session interrupted - cleaned up for new crawl",
             datetime.now(timezone.utc).isoformat(), project_id] + incomplete_statuses)

        pages_reset = 0
        if reset_pages:
            # Reset all pages to discovered status for fresh crawl
            cursor = await project_conn.execute("""
                SELECT COUNT(*) FROM pages WHERE project_id = ?
            """, (project_id,))
            pages_reset = (await cursor.fetchone())[0]

            if pages_reset > 0:
                await project_conn.execute("""
                    UPDATE pages
                    SET status = ?, session_id = NULL,
                        crawled_at = NULL, response_code = NULL, response_time_ms = NULL,
                        content_html = NULL, content_text = NULL, content_hash = NULL,
                        outbound_links = NULL, internal_links = NULL, external_links = NULL,
                        updated_at = ?
                    WHERE project_id = ?
                """, (PageStatus.DISCOVERED.value, datetime.now(timezone.utc).isoformat(), project_id))

        await project_conn.commit()

        self.logger.info("Cleaned up incomplete crawl sessions", extra={
            "project_id": project_id,
            "incomplete_sessions": incomplete_count,
            "pages_reset": pages_reset,
            "reset_pages": reset_pages
        })

        return {
            "incomplete_sessions_cleaned": incomplete_count,
            "pages_reset": pages_reset
        }

    # Page operations

    async def create_page(
        self,
        box_id: str,
        session_id: str,
        url: str,
        crawl_depth: int,
        parent_url: str | None = None
    ) -> Page:
        """Create a new page record for a box."""
        self._ensure_initialized()

        # Get box to find box name
        box = await self.get_box(box_id=box_id)
        if not box:
            raise DatabaseError(f"Box {box_id} not found")

        page_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        page = Page(
            id=page_id,
            box_id=box_id,
            session_id=session_id,
            url=url,
            crawl_depth=crawl_depth,
            parent_url=parent_url,
            discovered_at=now
        )

        # Use box-specific database connection
        box_conn = await self._get_box_connection(box['name'])
        await box_conn.execute("""
            INSERT INTO pages (
                id, box_id, session_id, url, status, crawl_depth,
                parent_url, discovered_at, retry_count, max_retries
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            page.id, page.box_id, page.session_id, page.url,
            page.status.value, page.crawl_depth, page.parent_url,
            page.discovered_at.isoformat(), page.retry_count, page.max_retries
        ))
        await box_conn.commit()

        return page

    async def get_page(self, page_id: str) -> Page | None:
        """Get page by ID from any project database."""
        self._ensure_initialized()

        # First, try to find which project this page belongs to
        # Check all project databases
        for project_name, project_conn in self._project_connections.items():
            cursor = await project_conn.execute("""
                SELECT id, project_id, session_id, url, status, title, content_html,
                       content_text, content_hash, mime_type, charset, language,
                       size_bytes, crawl_depth, parent_url, response_code,
                       response_time_ms, discovered_at, crawled_at, processed_at,
                       indexed_at, error_message, retry_count, max_retries,
                       outbound_links, internal_links, external_links, metadata
                FROM pages WHERE id = ?
            """, (page_id,))

            row = await cursor.fetchone()
            if row:
                return self._page_from_row(row)

        # If not found in cached connections, check all projects
        projects_cursor = await self._connection.execute("SELECT id, name FROM projects")
        projects = await projects_cursor.fetchall()

        for project_id, project_name in projects:
            project_conn = await self._get_project_connection(project_name)
            cursor = await project_conn.execute("""
                SELECT id, project_id, session_id, url, status, title, content_html,
                       content_text, content_hash, mime_type, charset, language,
                       size_bytes, crawl_depth, parent_url, response_code,
                       response_time_ms, discovered_at, crawled_at, processed_at,
                       indexed_at, error_message, retry_count, max_retries,
                       outbound_links, internal_links, external_links, metadata
                FROM pages WHERE id = ?
            """, (page_id,))

            row = await cursor.fetchone()
            if row:
                return self._page_from_row(row)

        return None

    async def update_page(self, page: Page) -> Page:
        """Update page record."""
        self._ensure_initialized()

        # Get box to find box name
        box = await self.get_box(box_id=page.box_id)
        if not box:
            raise DatabaseError(f"Box {page.box_id} not found")

        # Use box-specific database connection
        box_conn = await self._get_box_connection(box['name'])
        await box_conn.execute("""
            UPDATE pages SET
                status = ?, title = ?, content_html = ?, content_text = ?,
                content_hash = ?, mime_type = ?, charset = ?, language = ?,
                size_bytes = ?, response_code = ?, response_time_ms = ?,
                crawled_at = ?, processed_at = ?, indexed_at = ?,
                error_message = ?, retry_count = ?, outbound_links = ?,
                internal_links = ?, external_links = ?, metadata = ?
            WHERE id = ?
        """, (
            page.status.value, page.title, page.content_html, page.content_text,
            page.content_hash, page.mime_type, page.charset, page.language,
            page.size_bytes, page.response_code, page.response_time_ms,
            page.crawled_at.isoformat() if page.crawled_at else None,
            page.processed_at.isoformat() if page.processed_at else None,
            page.indexed_at.isoformat() if page.indexed_at else None,
            page.error_message, page.retry_count,
            json.dumps(page.outbound_links),
            json.dumps(page.internal_links),
            json.dumps(page.external_links),
            json.dumps(page.metadata),
            page.id
        ))
        await box_conn.commit()

        return page

    async def get_page_by_url(self, box_id: str, url: str) -> Page | None:
        """Get page by URL for a specific box."""
        self._ensure_initialized()

        # Get box to find box name
        box = await self.get_box(box_id=box_id)
        if not box:
            raise DatabaseError(f"Box {box_id} not found")

        # Use box-specific database connection
        box_conn = await self._get_box_connection(box['name'])
        cursor = await box_conn.execute("""
            SELECT id, box_id, session_id, url, status, title, content_html,
                   content_text, content_hash, mime_type, charset, language,
                   size_bytes, crawl_depth, parent_url, response_code,
                   response_time_ms, discovered_at, crawled_at, processed_at,
                   indexed_at, error_message, retry_count, max_retries,
                   outbound_links, internal_links, external_links, metadata
            FROM pages WHERE box_id = ? AND url = ?
        """, (box_id, url))

        row = await cursor.fetchone()
        if not row:
            return None

        return self._page_from_row(row)

    async def get_project_pages(
        self,
        project_id: str,
        status: PageStatus | None = None,
        limit: int | None = None
    ) -> list[Page]:
        """Get pages for a project."""
        self._ensure_initialized()

        # Get project to find project name
        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        # Use project-specific database connection
        project_conn = await self._get_project_connection(project.name)

        sql = """
            SELECT id, project_id, session_id, url, status, title, content_html,
                   content_text, content_hash, mime_type, charset, language,
                   size_bytes, crawl_depth, parent_url, response_code,
                   response_time_ms, discovered_at, crawled_at, processed_at,
                   indexed_at, error_message, retry_count, max_retries,
                   outbound_links, internal_links, external_links, metadata
            FROM pages WHERE project_id = ?
        """
        params = [project_id]

        if status:
            sql += " AND status = ?"
            params.append(status.value)

        sql += " ORDER BY discovered_at"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = await project_conn.execute(sql, params)
        rows = await cursor.fetchall()

        return [self._page_from_row(row) for row in rows]

    async def get_box_pages(
        self,
        box_id: str,
        status: PageStatus | None = None,
        limit: int | None = None
    ) -> list[Page]:
        """Get pages for a box."""
        self._ensure_initialized()

        # Get box to find box name
        box = await self.get_box(box_id=box_id)
        if not box:
            raise DatabaseError(f"Box {box_id} not found")

        # Use box-specific database connection
        box_conn = await self._get_box_connection(box['name'])

        sql = """
            SELECT id, box_id, session_id, url, status, title, content_html,
                   content_text, content_hash, mime_type, charset, language,
                   size_bytes, crawl_depth, parent_url, response_code,
                   response_time_ms, discovered_at, crawled_at, processed_at,
                   indexed_at, error_message, retry_count, max_retries,
                   outbound_links, internal_links, external_links, metadata
            FROM pages WHERE box_id = ?
        """
        params = [box_id]

        if status:
            sql += " AND status = ?"
            params.append(status.value)

        sql += " ORDER BY discovered_at"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = await box_conn.execute(sql, params)
        rows = await cursor.fetchall()

        return [self._page_from_row(row) for row in rows]

    async def get_pages_by_hash(self, content_hash: str) -> list[Page]:
        """Get pages with matching content hash."""
        self._ensure_initialized()

        cursor = await self._connection.execute("""
            SELECT id, project_id, session_id, url, status, title, content_html,
                   content_text, content_hash, mime_type, charset, language,
                   size_bytes, crawl_depth, parent_url, response_code,
                   response_time_ms, discovered_at, crawled_at, processed_at,
                   indexed_at, error_message, retry_count, max_retries,
                   outbound_links, internal_links, external_links, metadata
            FROM pages WHERE content_hash = ?
        """, (content_hash,))

        rows = await cursor.fetchall()
        return [self._page_from_row(row) for row in rows]

    def _page_from_row(self, row: tuple) -> Page:
        """Create Page from database row."""
        (id, box_id, session_id, url, status, title, content_html,
         content_text, content_hash, mime_type, charset, language,
         size_bytes, crawl_depth, parent_url, response_code,
         response_time_ms, discovered_at, crawled_at, processed_at,
         indexed_at, error_message, retry_count, max_retries,
         outbound_links, internal_links, external_links, metadata) = row

        return Page(
            id=id,
            box_id=box_id,
            session_id=session_id,
            url=url,
            status=PageStatus(status),
            title=title,
            content_html=content_html,
            content_text=content_text,
            content_hash=content_hash,
            mime_type=mime_type,
            charset=charset,
            language=language,
            size_bytes=size_bytes,
            crawl_depth=crawl_depth,
            parent_url=parent_url,
            response_code=response_code,
            response_time_ms=response_time_ms,
            discovered_at=datetime.fromisoformat(discovered_at),
            crawled_at=datetime.fromisoformat(crawled_at) if crawled_at else None,
            processed_at=datetime.fromisoformat(processed_at) if processed_at else None,
            indexed_at=datetime.fromisoformat(indexed_at) if indexed_at else None,
            error_message=error_message,
            retry_count=retry_count,
            max_retries=max_retries,
            outbound_links=json.loads(outbound_links) if outbound_links else [],
            internal_links=json.loads(internal_links) if internal_links else [],
            external_links=json.loads(external_links) if external_links else [],
            metadata=json.loads(metadata) if metadata else {}
        )

    # Statistics and utility operations

    async def get_project_metrics(self, project_id: str) -> dict[str, Any]:
        """Get comprehensive project metrics."""
        self._ensure_initialized()

        # Get project info
        project = await self.get_project(project_id)
        if not project:
            raise DatabaseError(f"Project {project_id} not found")

        # Use project-specific database connection
        project_conn = await self._get_project_connection(project.name)

        # Get page statistics
        cursor = await project_conn.execute("""
            SELECT
                COUNT(*) as total_pages,
                SUM(size_bytes) as total_size,
                AVG(size_bytes) as avg_size,
                COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_pages,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_pages,
                COUNT(CASE WHEN status = 'indexed' THEN 1 END) as indexed_pages,
                COUNT(DISTINCT content_hash) as unique_pages
            FROM pages WHERE project_id = ?
        """, (project_id,))

        stats = await cursor.fetchone()

        # Get latest session info
        sessions = await self.get_project_sessions(project_id)
        latest_session = sessions[0] if sessions else None

        return {
            "total_pages": stats[0] or 0,
            "total_size_bytes": stats[1] or 0,
            "average_page_size": stats[2] or 0,
            "processed_pages": stats[3] or 0,
            "failed_pages": stats[4] or 0,
            "indexed_pages": stats[5] or 0,
            "unique_pages": stats[6] or 0,
            "successful_pages": project.successful_pages,
            "crawl_duration_seconds": latest_session.get_duration() if latest_session else 0,
            "last_crawl_date": project.last_crawl_at.isoformat() if project.last_crawl_at else None,
            "indexing_status": "indexed" if stats[5] > 0 else "not_indexed"
        }

    async def recreate_project(
        self,
        name: str,
        source_url: str,
        crawl_depth: int = 2,
        embedding_model: str = "mxbai-embed-large",
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        metadata: dict[str, Any] | None = None
    ) -> Project:
        """Recreate project (archive old data and create new)."""
        self._ensure_initialized()

        # Check if project exists
        existing = await self.get_project_by_name(name)
        if existing:
            # Archive old sessions
            await self._connection.execute("""
                UPDATE crawl_sessions SET archived = TRUE
                WHERE project_id = ?
            """, (existing.id,))

            # Delete old project
            await self.delete_project(existing.id)
            await self._connection.commit()

        # Create new project
        return await self.create_project(
            name=name,
            source_url=source_url,
            crawl_depth=crawl_depth,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            metadata=metadata
        )


    async def cleanup_project(self, project_id: str) -> dict[str, Any]:
        """Clean up all project data."""
        self._ensure_initialized()

        try:
            # First get project info to get the project name
            project = await self.get_project(project_id)
            if not project:
                return {"success": False, "error": "Project not found"}

            pages_count = 0
            sessions_count = 0

            # Try to get counts from project database if it exists
            try:
                project_conn = await self._get_project_connection(project.name)

                pages_cursor = await project_conn.execute("SELECT COUNT(*) FROM pages")
                pages_count = (await pages_cursor.fetchone())[0]

                sessions_cursor = await project_conn.execute("SELECT COUNT(*) FROM crawl_sessions")
                sessions_count = (await sessions_cursor.fetchone())[0]

                # Close project connection
                await project_conn.close()
                if project.name in self._project_connections:
                    del self._project_connections[project.name]

            except Exception as e:
                self.logger.warning("Could not get project data counts", extra={
                    "project_name": project.name,
                    "error": str(e)
                })

            # Delete project-specific database file if it exists
            try:
                project_db_path = self._get_project_db_path(project.name)
                if project_db_path.exists():
                    project_db_path.unlink()
                    self.logger.info("Deleted project database file", extra={
                        "project_name": project.name,
                        "path": str(project_db_path)
                    })
            except Exception as e:
                self.logger.warning("Could not delete project database file", extra={
                    "project_name": project.name,
                    "error": str(e)
                })

            # Delete project from main database
            deleted = await self.delete_project(project_id)

            return {
                "success": deleted,
                "pages_deleted": pages_count,
                "sessions_deleted": sessions_count
            }

        except Exception as e:
            self.logger.error("Failed to cleanup project", extra={
                "project_id": project_id,
                "error": str(e)
            })
            return {"success": False, "error": str(e)}

    # Shelf operations

    async def create_shelf(self, name: str, is_default: bool = False, is_deletable: bool = True) -> str:
        """Create a new shelf."""
        self._ensure_initialized()

        shelf_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        try:
            await self._connection.execute("""
                INSERT INTO shelves (id, name, is_default, is_deletable, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (shelf_id, name, is_default, is_deletable, now, now))
            await self._connection.commit()

            self.logger.info("Created shelf", extra={"shelf_id": shelf_id, "name": name})
            return shelf_id

        except sqlite3.IntegrityError:
            raise DatabaseError(f"Shelf with name '{name}' already exists")

    async def get_shelf(self, shelf_id: str = None, name: str = None) -> dict | None:
        """Get shelf by ID or name."""
        self._ensure_initialized()

        if shelf_id:
            cursor = await self._connection.execute(
                "SELECT * FROM shelves WHERE id = ?", (shelf_id,)
            )
        elif name:
            cursor = await self._connection.execute(
                "SELECT * FROM shelves WHERE name = ?", (name,)
            )
        else:
            return None

        row = await cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in cursor.description], row))
        return None

    async def list_shelves(self) -> list[dict]:
        """List all shelves."""
        self._ensure_initialized()

        cursor = await self._connection.execute("""
            SELECT s.*, COUNT(sb.box_id) as box_count
            FROM shelves s
            LEFT JOIN shelf_boxes sb ON s.id = sb.shelf_id
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """)

        rows = await cursor.fetchall()
        return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

    async def delete_shelf(self, shelf_id: str) -> bool:
        """Delete a shelf."""
        self._ensure_initialized()

        # Check if shelf is deletable
        shelf = await self.get_shelf(shelf_id=shelf_id)
        if not shelf:
            return False
        if not shelf['is_deletable']:
            raise DatabaseError("Cannot delete protected shelf")

        await self._connection.execute("DELETE FROM shelves WHERE id = ?", (shelf_id,))
        await self._connection.commit()

        self.logger.info("Deleted shelf", extra={"shelf_id": shelf_id})
        return True

    # Box operations

    async def create_box(self, name: str, box_type: str, is_deletable: bool = True, **kwargs) -> str:
        """Create a new box."""
        self._ensure_initialized()

        box_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        try:
            await self._connection.execute("""
                INSERT INTO boxes (
                    id, name, type, is_deletable, url, max_pages,
                    rate_limit, crawl_depth, settings, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                box_id, name, box_type, is_deletable,
                kwargs.get('url'), kwargs.get('max_pages'),
                kwargs.get('rate_limit'), kwargs.get('crawl_depth'),
                json.dumps(kwargs.get('settings', {})) if kwargs.get('settings') else None,
                now, now
            ))
            await self._connection.commit()

            self.logger.info("Created box", extra={"box_id": box_id, "name": name, "type": box_type})
            return box_id

        except sqlite3.IntegrityError:
            raise DatabaseError(f"Box with name '{name}' already exists")

    async def get_box(self, box_id: str = None, name: str = None) -> dict | None:
        """Get box by ID or name."""
        self._ensure_initialized()

        if box_id:
            cursor = await self._connection.execute(
                "SELECT * FROM boxes WHERE id = ?", (box_id,)
            )
        elif name:
            cursor = await self._connection.execute(
                "SELECT * FROM boxes WHERE name = ?", (name,)
            )
        else:
            return None

        row = await cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in cursor.description], row))
        return None

    async def get_box_by_name(self, name: str) -> dict | None:
        """Get box by name (convenience wrapper)."""
        return await self.get_box(name=name)

    async def list_boxes(self, shelf_id: str = None, box_type: str = None) -> list[dict]:
        """List boxes, optionally filtered by shelf or type."""
        self._ensure_initialized()

        # Handle all combinations of filters
        if shelf_id and box_type:
            # Both filters: shelf AND type
            cursor = await self._connection.execute("""
                SELECT b.*, sb.position, sb.added_at
                FROM boxes b
                JOIN shelf_boxes sb ON b.id = sb.box_id
                WHERE sb.shelf_id = ? AND b.type = ?
                ORDER BY sb.position, b.created_at DESC
            """, (shelf_id, box_type))
        elif shelf_id:
            # Only shelf filter
            cursor = await self._connection.execute("""
                SELECT b.*, sb.position, sb.added_at
                FROM boxes b
                JOIN shelf_boxes sb ON b.id = sb.box_id
                WHERE sb.shelf_id = ?
                ORDER BY sb.position, b.created_at DESC
            """, (shelf_id,))
        elif box_type:
            # Only type filter
            cursor = await self._connection.execute("""
                SELECT * FROM boxes WHERE type = ? ORDER BY created_at DESC
            """, (box_type,))
        else:
            # No filters: all boxes
            cursor = await self._connection.execute("""
                SELECT * FROM boxes ORDER BY created_at DESC
            """)

        rows = await cursor.fetchall()
        return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

    async def delete_box(self, box_id: str) -> bool:
        """Delete a box."""
        self._ensure_initialized()

        # Check if box is deletable
        box = await self.get_box(box_id=box_id)
        if not box:
            return False
        if not box['is_deletable']:
            raise DatabaseError("Cannot delete protected box")

        await self._connection.execute("DELETE FROM boxes WHERE id = ?", (box_id,))
        await self._connection.commit()

        self.logger.info("Deleted box", extra={"box_id": box_id})
        return True

    # Shelf-Box relationship operations

    async def add_box_to_shelf(self, shelf_id: str, box_id: str, position: int = None) -> bool:
        """Add a box to a shelf."""
        self._ensure_initialized()

        now = datetime.now(timezone.utc).isoformat()

        try:
            await self._connection.execute("""
                INSERT INTO shelf_boxes (shelf_id, box_id, position, added_at)
                VALUES (?, ?, ?, ?)
            """, (shelf_id, box_id, position, now))
            await self._connection.commit()

            self.logger.info("Added box to shelf", extra={"shelf_id": shelf_id, "box_id": box_id})
            return True

        except sqlite3.IntegrityError:
            self.logger.warning("Box already in shelf", extra={"shelf_id": shelf_id, "box_id": box_id})
            return False

    async def remove_box_from_shelf(self, shelf_id: str, box_id: str) -> bool:
        """Remove a box from a shelf."""
        self._ensure_initialized()

        # Check if this is the last box in the shelf
        cursor = await self._connection.execute("""
            SELECT COUNT(*) FROM shelf_boxes WHERE shelf_id = ?
        """, (shelf_id,))
        count = (await cursor.fetchone())[0]

        if count <= 1:
            raise DatabaseError("Cannot remove last box from shelf")

        cursor = await self._connection.execute("""
            DELETE FROM shelf_boxes WHERE shelf_id = ? AND box_id = ?
        """, (shelf_id, box_id))
        await self._connection.commit()

        if cursor.rowcount > 0:
            self.logger.info("Removed box from shelf", extra={"shelf_id": shelf_id, "box_id": box_id})
            return True
        return False

    async def get_current_shelf_id(self) -> str | None:
        """Get the current shelf ID from global settings."""
        self._ensure_initialized()

        try:
            cursor = await self._connection.execute(
                "SELECT current_shelf FROM global_settings LIMIT 1"
            )
            row = await cursor.fetchone()
            return row[0] if row else None
        except sqlite3.OperationalError:
            # Table or column might not exist
            return None

    async def set_current_shelf(self, shelf_id: str) -> bool:
        """Set the current shelf in global settings."""
        self._ensure_initialized()

        try:
            # First ensure global_settings exists
            await self._connection.execute("""
                INSERT OR IGNORE INTO global_settings (id, current_shelf)
                VALUES (1, ?)
            """, (shelf_id,))

            # Update current shelf
            await self._connection.execute("""
                UPDATE global_settings SET current_shelf = ? WHERE id = 1
            """, (shelf_id,))
            await self._connection.commit()

            self.logger.info("Set current shelf", extra={"shelf_id": shelf_id})
            return True

        except Exception as e:
            self.logger.error("Failed to set current shelf", extra={"error": str(e)})
            return False
