"""Integration tests for many-to-many shelf-box relationships."""

import pytest
import tempfile
from pathlib import Path

from src.services.database import DatabaseManager
from src.core.config import BablibConfig


class TestManyToManyIntegration:
    """Test many-to-many relationships between shelves and boxes."""

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
    async def test_box_can_be_in_multiple_shelves(self):
        """Test that one box can belong to multiple shelves."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create two shelves
            shelf1_id = await db_manager.create_shelf("shelf1")
            shelf2_id = await db_manager.create_shelf("shelf2")

            # Create one box
            box_id = await db_manager.create_box("shared_box", "rag")

            # Add box to both shelves
            result1 = await db_manager.add_box_to_shelf(shelf1_id, box_id)
            result2 = await db_manager.add_box_to_shelf(shelf2_id, box_id)

            assert result1 is True
            assert result2 is True

            # Verify box appears in both shelves
            shelf1_boxes = await db_manager.list_boxes(shelf_id=shelf1_id)
            shelf2_boxes = await db_manager.list_boxes(shelf_id=shelf2_id)

            shelf1_box_ids = [box['id'] for box in shelf1_boxes]
            shelf2_box_ids = [box['id'] for box in shelf2_boxes]

            assert box_id in shelf1_box_ids
            assert box_id in shelf2_box_ids

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_shelf_can_contain_multiple_boxes(self):
        """Test that one shelf can contain multiple boxes."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create one shelf
            shelf_id = await db_manager.create_shelf("multi_box_shelf")

            # Create multiple boxes
            box1_id = await db_manager.create_box("box1", "drag", url="https://example.com")
            box2_id = await db_manager.create_box("box2", "rag")
            box3_id = await db_manager.create_box("box3", "bag")

            # Add all boxes to the shelf
            result1 = await db_manager.add_box_to_shelf(shelf_id, box1_id)
            result2 = await db_manager.add_box_to_shelf(shelf_id, box2_id)
            result3 = await db_manager.add_box_to_shelf(shelf_id, box3_id)

            assert result1 is True
            assert result2 is True
            assert result3 is True

            # Verify shelf contains all boxes
            shelf_boxes = await db_manager.list_boxes(shelf_id=shelf_id)
            shelf_box_ids = [box['id'] for box in shelf_boxes]

            assert len(shelf_boxes) == 3
            assert box1_id in shelf_box_ids
            assert box2_id in shelf_box_ids
            assert box3_id in shelf_box_ids

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_removing_box_from_one_shelf_keeps_it_in_others(self):
        """Test that removing a box from one shelf doesn't affect other shelves."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create three shelves
            shelf1_id = await db_manager.create_shelf("shelf1")
            shelf2_id = await db_manager.create_shelf("shelf2")
            shelf3_id = await db_manager.create_shelf("shelf3")

            # Create one box
            box_id = await db_manager.create_box("persistent_box", "rag")

            # Add box to all three shelves
            await db_manager.add_box_to_shelf(shelf1_id, box_id)
            await db_manager.add_box_to_shelf(shelf2_id, box_id)
            await db_manager.add_box_to_shelf(shelf3_id, box_id)

            # Add another box to shelf2 so we can remove the first one
            other_box_id = await db_manager.create_box("other_box", "bag")
            await db_manager.add_box_to_shelf(shelf2_id, other_box_id)

            # Remove box from shelf2 only
            result = await db_manager.remove_box_from_shelf(shelf2_id, box_id)
            assert result is True

            # Verify box is still in shelf1 and shelf3
            shelf1_boxes = await db_manager.list_boxes(shelf_id=shelf1_id)
            shelf2_boxes = await db_manager.list_boxes(shelf_id=shelf2_id)
            shelf3_boxes = await db_manager.list_boxes(shelf_id=shelf3_id)

            shelf1_box_ids = [box['id'] for box in shelf1_boxes]
            shelf2_box_ids = [box['id'] for box in shelf2_boxes]
            shelf3_box_ids = [box['id'] for box in shelf3_boxes]

            assert box_id in shelf1_box_ids  # Still in shelf1
            assert box_id not in shelf2_box_ids  # Removed from shelf2
            assert box_id in shelf3_box_ids  # Still in shelf3

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_deleting_box_removes_from_all_shelves(self):
        """Test that deleting a box removes it from all shelves."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create two shelves
            shelf1_id = await db_manager.create_shelf("shelf1")
            shelf2_id = await db_manager.create_shelf("shelf2")

            # Create two boxes
            box_to_delete_id = await db_manager.create_box("box_to_delete", "rag")
            keep_box_id = await db_manager.create_box("keep_box", "bag")

            # Add both boxes to both shelves
            await db_manager.add_box_to_shelf(shelf1_id, box_to_delete_id)
            await db_manager.add_box_to_shelf(shelf1_id, keep_box_id)
            await db_manager.add_box_to_shelf(shelf2_id, box_to_delete_id)
            await db_manager.add_box_to_shelf(shelf2_id, keep_box_id)

            # Delete the first box
            result = await db_manager.delete_box(box_to_delete_id)
            assert result is True

            # Verify box is removed from both shelves
            shelf1_boxes = await db_manager.list_boxes(shelf_id=shelf1_id)
            shelf2_boxes = await db_manager.list_boxes(shelf_id=shelf2_id)

            shelf1_box_ids = [box['id'] for box in shelf1_boxes]
            shelf2_box_ids = [box['id'] for box in shelf2_boxes]

            assert box_to_delete_id not in shelf1_box_ids
            assert box_to_delete_id not in shelf2_box_ids
            assert keep_box_id in shelf1_box_ids  # Other box still there
            assert keep_box_id in shelf2_box_ids  # Other box still there

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_deleting_shelf_removes_relationships_not_boxes(self):
        """Test that deleting a shelf removes relationships but not the boxes."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create two shelves
            shelf_to_delete_id = await db_manager.create_shelf("shelf_to_delete")
            keep_shelf_id = await db_manager.create_shelf("keep_shelf")

            # Create one box
            box_id = await db_manager.create_box("persistent_box", "rag")

            # Add box to both shelves
            await db_manager.add_box_to_shelf(shelf_to_delete_id, box_id)
            await db_manager.add_box_to_shelf(keep_shelf_id, box_id)

            # Delete the first shelf
            result = await db_manager.delete_shelf(shelf_to_delete_id)
            assert result is True

            # Verify box still exists
            box = await db_manager.get_box(box_id=box_id)
            assert box is not None

            # Verify box is still in the remaining shelf
            keep_shelf_boxes = await db_manager.list_boxes(shelf_id=keep_shelf_id)
            keep_shelf_box_ids = [box['id'] for box in keep_shelf_boxes]

            assert box_id in keep_shelf_box_ids

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_cannot_add_same_box_to_shelf_twice(self):
        """Test that adding the same box to a shelf twice fails gracefully."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create shelf and box
            shelf_id = await db_manager.create_shelf("test_shelf")
            box_id = await db_manager.create_box("test_box", "rag")

            # Add box to shelf first time
            result1 = await db_manager.add_box_to_shelf(shelf_id, box_id)
            assert result1 is True

            # Try to add same box to shelf again
            result2 = await db_manager.add_box_to_shelf(shelf_id, box_id)
            assert result2 is False  # Should fail gracefully

            # Verify box is still in shelf (only once)
            shelf_boxes = await db_manager.list_boxes(shelf_id=shelf_id)
            box_count = sum(1 for box in shelf_boxes if box['id'] == box_id)
            assert box_count == 1

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_position_ordering_in_shelf(self):
        """Test that boxes can be positioned within shelves."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create shelf and boxes
            shelf_id = await db_manager.create_shelf("ordered_shelf")
            box1_id = await db_manager.create_box("first_box", "rag")
            box2_id = await db_manager.create_box("second_box", "bag")
            box3_id = await db_manager.create_box("third_box", "drag", url="https://example.com")

            # Add boxes with specific positions
            await db_manager.add_box_to_shelf(shelf_id, box2_id, position=2)
            await db_manager.add_box_to_shelf(shelf_id, box1_id, position=1)
            await db_manager.add_box_to_shelf(shelf_id, box3_id, position=3)

            # Get boxes from shelf (should be ordered by position)
            shelf_boxes = await db_manager.list_boxes(shelf_id=shelf_id)

            # Find positions of our boxes
            box_positions = {}
            for box in shelf_boxes:
                if box['id'] in [box1_id, box2_id, box3_id]:
                    box_positions[box['id']] = box.get('position')

            # Verify positions are correct
            assert box_positions[box1_id] == 1
            assert box_positions[box2_id] == 2
            assert box_positions[box3_id] == 3

        finally:
            await db_manager.cleanup()

    @pytest.mark.asyncio
    async def test_global_box_name_uniqueness_across_shelves(self):
        """Test that box names must be globally unique."""
        db_manager = DatabaseManager(self.config)
        await db_manager.initialize()

        try:
            # Create two shelves
            shelf1_id = await db_manager.create_shelf("shelf1")
            shelf2_id = await db_manager.create_shelf("shelf2")

            # Create box in first shelf
            box1_id = await db_manager.create_box("unique_name", "rag")
            await db_manager.add_box_to_shelf(shelf1_id, box1_id)

            # Try to create box with same name (should fail)
            with pytest.raises(Exception):  # Should raise DatabaseError
                await db_manager.create_box("unique_name", "bag")

        finally:
            await db_manager.cleanup()