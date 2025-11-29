"""Unit tests for database migration functionality."""

import pytest
import sqlite3
import uuid
from pathlib import Path
import tempfile
from unittest.mock import patch

from src.services.database_migrator import DatabaseMigrator
from src.core.config import BablibConfig


class TestDatabaseMigration:
    """Test database migration functionality."""

    def setup_method(self):
        """Setup test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = Path(self.temp_db.name)

        # Create migrator with mocked config
        with patch.object(BablibConfig, 'database_path', self.db_path):
            self.config = BablibConfig()
            self.migrator = DatabaseMigrator(self.config)

    def teardown_method(self):
        """Clean up test database."""
        if hasattr(self, 'db_path') and self.db_path.exists():
            self.db_path.unlink()

    def test_get_current_version_no_table(self):
        """Test getting version when schema_version table doesn't exist."""
        conn = sqlite3.connect(self.db_path)

        version = self.migrator.get_current_version(conn)
        assert version == 0

        conn.close()

    def test_get_current_version_with_data(self):
        """Test getting version when schema_version table exists."""
        conn = sqlite3.connect(self.db_path)

        # Create table and insert version
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO schema_version (version) VALUES (3)")
        conn.commit()

        version = self.migrator.get_current_version(conn)
        assert version == 3

        conn.close()

    def test_migrate_to_version_5_creates_tables(self):
        """Test that migration to version 5 creates required tables."""
        conn = sqlite3.connect(self.db_path)

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Check that tables were created
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'shelves' in tables
        assert 'boxes' in tables
        assert 'shelf_boxes' in tables
        assert 'global_settings' in tables

        conn.close()

    def test_migrate_to_version_5_creates_indexes(self):
        """Test that migration creates appropriate indexes."""
        conn = sqlite3.connect(self.db_path)

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Check that indexes were created
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'idx_shelves_name',
            'idx_shelves_is_default',
            'idx_boxes_name',
            'idx_boxes_type',
            'idx_shelf_boxes_shelf_id',
            'idx_shelf_boxes_box_id'
        ]

        for expected_index in expected_indexes:
            assert expected_index in indexes

        conn.close()

    def test_migrate_to_version_5_creates_default_data(self):
        """Test that migration creates default shelf and box."""
        conn = sqlite3.connect(self.db_path)

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Check default shelf exists
        cursor = conn.execute("SELECT name, is_default, is_deletable FROM shelves")
        shelf_row = cursor.fetchone()
        assert shelf_row is not None
        assert shelf_row[0] == "common shelf"
        assert shelf_row[1] == 1  # is_default = True
        assert shelf_row[2] == 0  # is_deletable = False

        # Check default box exists
        cursor = conn.execute("SELECT name, type, is_deletable FROM boxes")
        box_row = cursor.fetchone()
        assert box_row is not None
        assert box_row[0] == "new year"
        assert box_row[1] == "bag"
        assert box_row[2] == 0  # is_deletable = False

        # Check box is in shelf
        cursor = conn.execute("SELECT COUNT(*) FROM shelf_boxes")
        count = cursor.fetchone()[0]
        assert count == 1

        conn.close()

    def test_migrate_to_version_5_updates_schema_version(self):
        """Test that migration updates schema version to 5."""
        conn = sqlite3.connect(self.db_path)

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Check version was updated
        cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        version = cursor.fetchone()[0]
        assert version == 5

        conn.close()

    def test_run_migrations_from_version_0(self):
        """Test running migrations from version 0 to latest."""
        # Empty database (version 0)
        self.migrator.run_migrations()

        conn = sqlite3.connect(self.db_path)

        # Check that we're at version 6 (current schema version)
        version = self.migrator.get_current_version(conn)
        assert version == 6

        # Check that default data exists
        cursor = conn.execute("SELECT COUNT(*) FROM shelves")
        shelf_count = cursor.fetchone()[0]
        assert shelf_count >= 1

        cursor = conn.execute("SELECT COUNT(*) FROM boxes")
        box_count = cursor.fetchone()[0]
        assert box_count >= 1

        conn.close()

    def test_run_migrations_no_op_when_current(self):
        """Test that migrations are no-op when already at current version."""
        # First migration
        self.migrator.run_migrations()

        conn = sqlite3.connect(self.db_path)
        initial_shelf_count = conn.execute("SELECT COUNT(*) FROM shelves").fetchone()[0]
        conn.close()

        # Second migration should be no-op
        with patch.object(self.migrator, 'migrate_to_version_5') as mock_migrate:
            self.migrator.run_migrations()
            mock_migrate.assert_not_called()

        # Verify data didn't change
        conn = sqlite3.connect(self.db_path)
        final_shelf_count = conn.execute("SELECT COUNT(*) FROM shelves").fetchone()[0]
        assert final_shelf_count == initial_shelf_count
        conn.close()

    def test_box_type_constraints(self):
        """Test that box type constraints are enforced."""
        conn = sqlite3.connect(self.db_path)

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Valid types should work
        for box_type in ['drag', 'rag', 'bag']:
            conn.execute("""
                INSERT INTO boxes (id, name, type, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
            """, (f"test-{box_type}", f"test-{box_type}", box_type))

        # Invalid type should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO boxes (id, name, type, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
            """, ("invalid", "invalid", "invalid_type"))

        conn.close()

    def test_foreign_key_constraints(self):
        """Test that foreign key constraints work properly."""
        conn = sqlite3.connect(self.db_path)

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Create a new shelf and box for testing (avoiding default data relationships)
        test_shelf_id = str(uuid.uuid4())
        test_box_id = str(uuid.uuid4())

        conn.execute("""
            INSERT INTO shelves (id, name, created_at, updated_at)
            VALUES (?, 'test-shelf-fk', datetime('now'), datetime('now'))
        """, (test_shelf_id,))

        conn.execute("""
            INSERT INTO boxes (id, name, type, created_at, updated_at)
            VALUES (?, 'test-box-fk', 'drag', datetime('now'), datetime('now'))
        """, (test_box_id,))

        conn.commit()

        # Valid relationship should work
        conn.execute("""
            INSERT INTO shelf_boxes (shelf_id, box_id, added_at)
            VALUES (?, ?, datetime('now'))
        """, (test_shelf_id, test_box_id))

        # Invalid shelf_id should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO shelf_boxes (shelf_id, box_id, added_at)
                VALUES ('nonexistent', ?, datetime('now'))
            """, (test_box_id,))

        conn.close()

    def test_unique_constraints(self):
        """Test that unique constraints are enforced."""
        conn = sqlite3.connect(self.db_path)

        # Create initial schema_version table
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        self.migrator.migrate_to_version_5(conn)

        # Duplicate shelf name should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO shelves (id, name, created_at, updated_at)
                VALUES ('test-shelf-2', 'common shelf', datetime('now'), datetime('now'))
            """)

        # Duplicate box name should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO boxes (id, name, type, created_at, updated_at)
                VALUES ('test-box-2', 'new year', 'rag', datetime('now'), datetime('now'))
            """)

        conn.close()