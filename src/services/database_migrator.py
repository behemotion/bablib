"""Database migration service for Bablib."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger
from src.models.box_type import BoxType


class DatabaseMigrator:
    """Handles database schema migrations."""

    def __init__(self, config: Optional[BablibConfig] = None):
        """Initialize database migrator."""
        self.config = config or BablibConfig()
        self.db_path = self.config.database_path
        self.logger = get_component_logger("database_migrator")

    def get_current_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version."""
        try:
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error:
            return 0

    def migrate_to_version_5(self, conn: sqlite3.Connection) -> None:
        """Migrate to version 5: Add shelf-box rhyme system tables."""
        self.logger.info("Migrating database to version 5: Shelf-Box Rhyme System")

        # Create schema_version table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create shelves table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shelves (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                is_default BOOLEAN DEFAULT FALSE,
                is_deletable BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create boxes table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS boxes (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('drag', 'rag', 'bag')),
                is_deletable BOOLEAN DEFAULT TRUE,
                url TEXT,
                max_pages INTEGER,
                rate_limit REAL,
                crawl_depth INTEGER,
                settings TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create shelf_boxes junction table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shelf_boxes (
                shelf_id TEXT NOT NULL,
                box_id TEXT NOT NULL,
                position INTEGER,
                added_at TEXT NOT NULL,
                PRIMARY KEY (shelf_id, box_id),
                FOREIGN KEY (shelf_id) REFERENCES shelves(id) ON DELETE CASCADE,
                FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shelves_name ON shelves(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shelves_is_default ON shelves(is_default)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boxes_name ON boxes(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boxes_type ON boxes(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shelf_boxes_shelf_id ON shelf_boxes(shelf_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shelf_boxes_box_id ON shelf_boxes(box_id)")

        # Create global_settings table if it doesn't exist and add current_shelf
        conn.execute("""
            CREATE TABLE IF NOT EXISTS global_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                current_shelf TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add current_shelf column if it doesn't exist
        try:
            conn.execute("ALTER TABLE global_settings ADD COLUMN current_shelf TEXT")
        except sqlite3.OperationalError:
            # Column might already exist
            pass

        # Create default data
        self._create_default_shelf_data(conn)

        # Update schema version
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (5)")
        conn.commit()

        self.logger.info("Migration to version 5 completed successfully")

    def _create_default_shelf_data(self, conn: sqlite3.Connection) -> None:
        """Create default shelf and box."""
        now = datetime.now(timezone.utc).isoformat()

        # Create default "common shelf"
        shelf_id = str(uuid.uuid4())
        conn.execute("""
            INSERT OR IGNORE INTO shelves (id, name, is_default, is_deletable, created_at, updated_at)
            VALUES (?, ?, TRUE, FALSE, ?, ?)
        """, (shelf_id, "common shelf", now, now))

        # Create default "new year" box
        box_id = str(uuid.uuid4())
        conn.execute("""
            INSERT OR IGNORE INTO boxes (id, name, type, is_deletable, created_at, updated_at)
            VALUES (?, ?, 'bag', FALSE, ?, ?)
        """, (box_id, "new year", now, now))

        # Add box to shelf
        conn.execute("""
            INSERT OR IGNORE INTO shelf_boxes (shelf_id, box_id, position, added_at)
            VALUES (?, ?, 1, ?)
        """, (shelf_id, box_id, now))

        # Set as current shelf in global settings
        try:
            conn.execute("""
                UPDATE global_settings SET current_shelf = ?
            """, (shelf_id,))
        except sqlite3.OperationalError:
            # Global settings might not exist yet
            pass

    def migrate_to_version_6(self, conn: sqlite3.Connection) -> None:
        """Migrate to version 6: Add context-aware command enhancement tables."""
        self.logger.info("Migrating database to version 6: Context-Aware Command Enhancement")

        # Create schema_version table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create command_contexts table (temporary/cache table)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS command_contexts (
                entity_name TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL CHECK (entity_type IN ('shelf', 'box')),
                entity_exists BOOLEAN NOT NULL,
                is_empty BOOLEAN,
                configuration_state TEXT,
                last_modified TEXT,
                content_summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        """)

        # Create wizard_states table (session management)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wizard_states (
                wizard_id TEXT PRIMARY KEY,
                wizard_type TEXT NOT NULL CHECK (wizard_type IN ('shelf', 'box', 'mcp')),
                target_entity TEXT NOT NULL,
                current_step INTEGER NOT NULL,
                total_steps INTEGER NOT NULL,
                collected_data TEXT NOT NULL,
                start_time TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                is_complete BOOLEAN DEFAULT FALSE
            )
        """)

        # Create flag_definitions table (configuration metadata)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flag_definitions (
                long_form TEXT PRIMARY KEY,
                short_form TEXT UNIQUE NOT NULL,
                flag_type TEXT NOT NULL CHECK (flag_type IN ('boolean', 'string', 'integer', 'choice')),
                description TEXT NOT NULL,
                choices TEXT,
                default_value TEXT,
                is_global BOOLEAN DEFAULT FALSE
            )
        """)

        # Add configuration_state column to existing tables
        try:
            conn.execute("ALTER TABLE shelves ADD COLUMN configuration_state TEXT")
        except sqlite3.OperationalError:
            # Column might already exist
            pass

        try:
            conn.execute("ALTER TABLE boxes ADD COLUMN configuration_state TEXT")
        except sqlite3.OperationalError:
            # Column might already exist
            pass

        # Check if mcp_configurations table exists and add column if it does
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='mcp_configurations'
        """)
        if cursor.fetchone():
            try:
                conn.execute("ALTER TABLE mcp_configurations ADD COLUMN configuration_state TEXT")
            except sqlite3.OperationalError:
                # Column might already exist
                pass

        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_command_contexts_entity_type ON command_contexts(entity_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_command_contexts_expires_at ON command_contexts(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wizard_states_wizard_type ON wizard_states(wizard_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wizard_states_target_entity ON wizard_states(target_entity)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wizard_states_is_complete ON wizard_states(is_complete)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flag_definitions_is_global ON flag_definitions(is_global)")

        # Populate flag_definitions with standard flags
        self._populate_standard_flags(conn)

        # Update schema version
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (6)")
        conn.commit()

        self.logger.info("Migration to version 6 completed successfully")

    def _populate_standard_flags(self, conn: sqlite3.Connection) -> None:
        """Populate flag_definitions table with standard flags."""
        standard_flags = [
            # Universal flags
            ("--help", "-h", "boolean", "Show help information", None, "false", True),
            ("--verbose", "-v", "boolean", "Enable verbose output", None, "false", True),
            ("--quiet", "-q", "boolean", "Suppress non-error output", None, "false", True),
            ("--config", "-c", "string", "Specify config file path", None, None, True),
            ("--format", "-f", "choice", "Output format", '["json", "yaml", "table"]', "table", True),

            # Common flags
            ("--init", "-i", "boolean", "Launch setup wizard", None, "false", True),
            ("--force", "-F", "boolean", "Force operation without prompts", None, "false", True),
            ("--dry-run", "-n", "boolean", "Show what would be done without executing", None, "false", True),
            ("--timeout", "-t", "integer", "Operation timeout in seconds", None, "30", True),
            ("--limit", "-l", "integer", "Limit number of results", None, "10", True),

            # File operations
            ("--recursive", "-r", "boolean", "Process directories recursively", None, "false", False),
            ("--pattern", "-p", "string", "File name pattern matching", None, None, False),
            ("--exclude", "-e", "string", "Exclude patterns", None, None, False),

            # Network operations
            ("--rate-limit", "-R", "string", "Requests per second limit", None, "1.0", False),
            ("--depth", "-d", "integer", "Maximum crawl depth", None, "3", False),

            # Processing options
            ("--chunk-size", "-C", "integer", "Text chunk size for processing", None, "500", False),
            ("--overlap", "-O", "integer", "Chunk overlap percentage", None, "50", False),
            ("--parallel", "-P", "integer", "Number of parallel workers", None, "1", False),
        ]

        for long_form, short_form, flag_type, description, choices, default_value, is_global in standard_flags:
            conn.execute("""
                INSERT OR IGNORE INTO flag_definitions
                (long_form, short_form, flag_type, description, choices, default_value, is_global)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (long_form, short_form, flag_type, description, choices, default_value, is_global))

    def run_migrations(self) -> None:
        """Run all pending migrations."""
        conn = sqlite3.connect(self.db_path)
        try:
            current_version = self.get_current_version(conn)
            target_version = 6

            if current_version < target_version:
                self.logger.info(f"Migrating database from version {current_version} to {target_version}")

                # Run migrations in sequence
                if current_version < 5:
                    self.migrate_to_version_5(conn)
                if current_version < 6:
                    self.migrate_to_version_6(conn)

                self.logger.info(f"Database migrated to version {target_version}")
            else:
                self.logger.debug(f"Database already at version {current_version}")

        finally:
            conn.close()