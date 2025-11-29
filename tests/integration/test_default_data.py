"""Integration tests for default data creation."""

import pytest
import tempfile
from pathlib import Path

from src.services.database_migrator import DatabaseMigrator
from src.services.database import DatabaseManager
from src.core.config import BablibConfig


class TestDefaultDataIntegration:
    """Test default data creation during system initialization."""

    def setup_method(self):
        """Setup test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = Path(self.temp_db.name)

        # Create config with test database path
        self.config = BablibConfig()
        self.config.database_path = self.db_path

    def teardown_method(self):
        """Clean up test database."""
        if self.db_path.exists():
            self.db_path.unlink()

    @pytest.mark.asyncio
    async def test_fresh_installation_creates_default_data(self):
        """Test that fresh installation creates default shelf and box."""
        # Initialize database (should trigger migration)
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Check that default shelf exists
            shelves = await db_manager.list_shelves()
            assert len(shelves) >= 1

            default_shelf = None
            for shelf in shelves:
                if shelf['name'] == 'common shelf':
                    default_shelf = shelf
                    break

            assert default_shelf is not None
            assert default_shelf['is_default'] == 1  # True in SQLite
            assert default_shelf['is_deletable'] == 0  # False in SQLite

            # Check that default box exists
            boxes = await db_manager.list_boxes()
            assert len(boxes) >= 1

            default_box = None
            for box in boxes:
                if box['name'] == 'new year':
                    default_box = box
                    break

            assert default_box is not None
            assert default_box['type'] == 'bag'
            assert default_box['is_deletable'] == 0  # False in SQLite

            # Check that box is in the shelf
            shelf_boxes = await db_manager.list_boxes(shelf_id=default_shelf['id'])
            assert len(shelf_boxes) >= 1

            box_in_shelf = False
            for box in shelf_boxes:
                if box['id'] == default_box['id']:
                    box_in_shelf = True
                    break

            assert box_in_shelf

            # Check current shelf is set
            current_shelf_id = await db_manager.get_current_shelf_id()
            assert current_shelf_id == default_shelf['id']

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_default_data_is_protected(self):
        """Test that default data cannot be deleted."""
        # Initialize database
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Get default shelf and box
            shelves = await db_manager.list_shelves()
            default_shelf = None
            for shelf in shelves:
                if shelf['name'] == 'common shelf':
                    default_shelf = shelf
                    break

            boxes = await db_manager.list_boxes()
            default_box = None
            for box in boxes:
                if box['name'] == 'new year':
                    default_box = box
                    break

            assert default_shelf is not None
            assert default_box is not None

            # Try to delete default shelf (should fail)
            with pytest.raises(Exception):  # Should raise DatabaseError
                await db_manager.delete_shelf(default_shelf['id'])

            # Try to delete default box (should fail)
            with pytest.raises(Exception):  # Should raise DatabaseError
                await db_manager.delete_box(default_box['id'])

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_default_shelf_has_one_box(self):
        """Test that default shelf starts with exactly one box."""
        # Initialize database
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Get default shelf
            shelves = await db_manager.list_shelves()
            default_shelf = None
            for shelf in shelves:
                if shelf['name'] == 'common shelf':
                    default_shelf = shelf
                    break

            assert default_shelf is not None

            # Check box count
            shelf_boxes = await db_manager.list_boxes(shelf_id=default_shelf['id'])
            assert len(shelf_boxes) == 1

            # Check it's the default box
            assert shelf_boxes[0]['name'] == 'new year'
            assert shelf_boxes[0]['type'] == 'bag'

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_multiple_initializations_dont_duplicate_data(self):
        """Test that multiple initializations don't create duplicate data."""
        # First initialization
        db_manager1 = DatabaseManager(self.config)
        await db_manager1.initialize()

        try:
            # Get initial counts
            initial_shelves = await db_manager1.list_shelves()
            initial_boxes = await db_manager1.list_boxes()

        finally:
            await db_manager1.cleanup()

        # Second initialization
        db_manager2 = DatabaseManager(self.config)
        await db_manager2.initialize()

        try:
            # Get final counts
            final_shelves = await db_manager2.list_shelves()
            final_boxes = await db_manager2.list_boxes()

            # Counts should be the same
            assert len(final_shelves) == len(initial_shelves)
            assert len(final_boxes) == len(initial_boxes)

            # Default items should still exist
            default_shelf_exists = any(s['name'] == 'common shelf' for s in final_shelves)
            default_box_exists = any(b['name'] == 'new year' for b in final_boxes)

            assert default_shelf_exists
            assert default_box_exists

        finally:
            await db_manager2.cleanup()

    @pytest.mark.asyncio
    async def test_current_shelf_points_to_default(self):
        """Test that current_shelf initially points to default shelf."""
        # Initialize database
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Get current shelf ID
            current_shelf_id = await db_manager.get_current_shelf_id()
            assert current_shelf_id is not None

            # Get default shelf
            default_shelf = await db_manager.get_shelf(name='common shelf')
            assert default_shelf is not None

            # Current shelf should be the default shelf
            assert current_shelf_id == default_shelf['id']

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_default_box_type_is_bag(self):
        """Test that default box is of type 'bag' as specified."""
        # Initialize database
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Get default box
            boxes = await db_manager.list_boxes()
            default_box = None
            for box in boxes:
                if box['name'] == 'new year':
                    default_box = box
                    break

            assert default_box is not None
            assert default_box['type'] == 'bag'

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_default_data_has_proper_timestamps(self):
        """Test that default data has proper creation timestamps."""
        # Initialize database
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Get default shelf and box
            default_shelf = await db_manager.get_shelf(name='common shelf')
            default_box = await db_manager.get_box(name='new year')

            assert default_shelf is not None
            assert default_box is not None

            # Check timestamps exist and are reasonable
            assert default_shelf['created_at'] is not None
            assert default_shelf['updated_at'] is not None
            assert default_box['created_at'] is not None
            assert default_box['updated_at'] is not None

            # Timestamps should be ISO format strings
            assert 'T' in default_shelf['created_at']
            assert 'T' in default_box['created_at']

        finally:
            await db_manager.cleanup()