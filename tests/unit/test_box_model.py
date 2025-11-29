"""Unit tests for Box model."""

import pytest
from datetime import datetime
from uuid import UUID
from pydantic import ValidationError

from src.models.box import Box, BoxValidationError
from src.models.box_type import BoxType


class TestBoxModel:
    """Test Box model functionality."""

    def test_box_creation_defaults(self):
        """Test box creation with default values."""
        box = Box(name="test box", type=BoxType.RAG)

        assert box.name == "test box"
        assert isinstance(UUID(box.id), UUID)  # Valid UUID
        assert box.type == BoxType.RAG
        assert box.is_deletable is True
        assert isinstance(box.created_at, datetime)
        assert isinstance(box.updated_at, datetime)
        assert box.url is None
        assert box.max_pages is None
        assert box.rate_limit is None
        assert box.crawl_depth is None
        assert box.settings == {}

    def test_box_creation_drag_type(self):
        """Test creating a drag box with URL."""
        box = Box(
            name="crawler box",
            type=BoxType.DRAG,
            url="https://example.com",
            max_pages=100,
            rate_limit=2.0,
            crawl_depth=3
        )

        assert box.name == "crawler box"
        assert box.type == BoxType.DRAG
        assert box.url == "https://example.com"
        assert box.max_pages == 100
        assert box.rate_limit == 2.0
        assert box.crawl_depth == 3

    def test_box_creation_custom_values(self):
        """Test box creation with custom values."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        settings = {"key": "value"}

        box = Box(
            id="custom-id",
            name="Custom Box",
            type=BoxType.BAG,
            is_deletable=False,
            created_at=now,
            updated_at=now,
            settings=settings
        )

        assert box.id == "custom-id"
        assert box.name == "Custom Box"
        assert box.type == BoxType.BAG
        assert box.is_deletable is False
        assert box.created_at == now
        assert box.updated_at == now
        assert box.settings == settings

    def test_name_validation_valid(self):
        """Test valid box names."""
        valid_names = [
            "simple",
            "with spaces",
            "with-hyphens",
            "with_underscores",
            "Mixed123",
            "box1",
            "a" + "b" * 98 + "c",  # Max length (100)
            "123name"  # Starting with number is ok
        ]

        for name in valid_names:
            box = Box(name=name, type=BoxType.RAG)
            assert box.name == name

    def test_name_validation_invalid_empty(self):
        """Test that empty names are rejected."""
        # Pydantic's min_length validation triggers first for empty string
        with pytest.raises(ValidationError, match="at least 1 character"):
            Box(name="", type=BoxType.RAG)

        # Whitespace gets stripped, then caught by our custom validator
        with pytest.raises(BoxValidationError, match="Box name cannot be empty"):
            Box(name="   ", type=BoxType.RAG)  # Only whitespace

    def test_name_validation_invalid_length(self):
        """Test that names exceeding max length are rejected."""
        long_name = "a" * 101  # Exceeds MAX_NAME_LENGTH
        # Pydantic's max_length validation triggers first
        with pytest.raises(ValidationError, match="at most 100 characters"):
            Box(name=long_name, type=BoxType.RAG)

    def test_name_validation_invalid_characters(self):
        """Test that names with invalid characters are rejected."""
        invalid_names = [
            "box@name",
            "box#name",
            "box$name",
            "box%name",
            "box!name",
            "box/name",
            "box\\name",
            "box|name"
        ]

        for name in invalid_names:
            with pytest.raises(BoxValidationError, match="must start with alphanumeric"):
                Box(name=name, type=BoxType.RAG)

    def test_name_validation_reserved_names(self):
        """Test that reserved names are rejected."""
        reserved_names = ["default", "system", "temp", "tmp", "test"]

        for name in reserved_names:
            with pytest.raises(BoxValidationError, match=f"'{name}' is a reserved box name"):
                Box(name=name, type=BoxType.RAG)

            # Test case insensitive
            with pytest.raises(BoxValidationError, match=f"'{name.upper()}' is a reserved box name"):
                Box(name=name.upper(), type=BoxType.RAG)

    def test_name_trimming(self):
        """Test that box names are trimmed of whitespace."""
        box = Box(name="  spaced name  ", type=BoxType.RAG)
        assert box.name == "spaced name"

    def test_url_validation_valid(self):
        """Test valid URL formats."""
        valid_urls = [
            "https://example.com",
            "http://test.org",
            "https://subdomain.example.com/path",
            "http://localhost:8080"
        ]

        for url in valid_urls:
            box = Box(name="my-box", type=BoxType.DRAG, url=url)
            assert box.url == url

    def test_url_validation_invalid(self):
        """Test invalid URL formats."""
        invalid_urls = [
            "ftp://example.com",
            "example.com",
            "www.example.com",
            "not-a-url"
        ]

        for url in invalid_urls:
            with pytest.raises(BoxValidationError, match="URL must start with http"):
                Box(name="my-box", type=BoxType.DRAG, url=url)

    def test_url_validation_empty(self):
        """Test that empty URLs are converted to None."""
        box = Box(name="my-box", type=BoxType.RAG, url="")
        assert box.url is None

        box2 = Box(name="my-box2", type=BoxType.RAG, url="   ")
        assert box2.url is None

    def test_drag_box_without_url_allowed(self):
        """Test that drag boxes can be created without URL.

        URL requirement is enforced at fill/crawl operation level, not at
        box creation level. This allows the Shelf-Box Rhyme System pattern:
        create empty box → fill later with content.
        """
        # Creating drag box without URL is allowed
        box = Box(name="crawler", type=BoxType.DRAG)
        assert box.url is None

        # Empty string URL becomes None
        box2 = Box(name="crawler2", type=BoxType.DRAG, url="")
        assert box2.url is None

    def test_non_drag_box_no_url_requirement(self):
        """Test that non-drag boxes don't require URLs."""
        rag_box = Box(name="documents", type=BoxType.RAG)
        assert rag_box.url is None

        bag_box = Box(name="storage", type=BoxType.BAG)
        assert bag_box.url is None

    def test_numeric_field_validation(self):
        """Test validation of numeric fields."""
        # Valid values
        box = Box(
            name="my-box",
            type=BoxType.DRAG,
            url="https://example.com",
            max_pages=100,
            rate_limit=2.5,
            crawl_depth=3
        )
        assert box.max_pages == 100
        assert box.rate_limit == 2.5
        assert box.crawl_depth == 3

        # Invalid max_pages (must be >= 1)
        with pytest.raises(ValueError):
            Box(name="my-box", type=BoxType.DRAG, url="https://example.com", max_pages=0)

        # Invalid rate_limit (must be > 0)
        with pytest.raises(ValueError):
            Box(name="my-box", type=BoxType.DRAG, url="https://example.com", rate_limit=0)

        # Invalid crawl_depth (must be >= 1)
        with pytest.raises(ValueError):
            Box(name="my-box", type=BoxType.DRAG, url="https://example.com", crawl_depth=0)

    def test_timestamp_validation(self):
        """Test that updated_at is adjusted if before created_at."""
        earlier = datetime(2023, 1, 1)
        later = datetime(2023, 1, 2)

        box = Box(name="my-box", type=BoxType.RAG, created_at=later, updated_at=earlier)
        assert box.updated_at == box.created_at  # Should be adjusted

    def test_to_dict_basic(self):
        """Test basic dictionary conversion."""
        box = Box(
            id="test-id",
            name="Test Box",
            type=BoxType.DRAG,
            url="https://example.com",
            is_deletable=False
        )

        data = box.to_dict()
        expected_keys = {
            "id", "name", "type", "is_deletable",
            "created_at", "updated_at", "url"
        }

        assert set(data.keys()).issuperset(expected_keys)
        assert data["id"] == "test-id"
        assert data["name"] == "Test Box"
        assert data["type"] == "drag"
        assert data["is_deletable"] is False
        assert data["url"] == "https://example.com"

    def test_to_dict_exclude_type_fields(self):
        """Test dictionary conversion excluding type-specific fields."""
        box = Box(
            name="Test Box",
            type=BoxType.DRAG,
            url="https://example.com",
            max_pages=100
        )

        data = box.to_dict(include_type_fields=False)
        assert "url" not in data
        assert "max_pages" not in data

    def test_to_summary(self):
        """Test summary generation."""
        box = Box(
            name="Test Box",
            type=BoxType.BAG,
            is_deletable=False
        )

        summary = box.to_summary()
        expected_keys = {"name", "type", "is_deletable", "created_at"}

        assert set(summary.keys()) == expected_keys
        assert summary["name"] == "Test Box"
        assert summary["type"] == "bag"
        assert summary["is_deletable"] is False

    def test_type_check_methods(self):
        """Test type checking convenience methods."""
        drag_box = Box(name="crawler", type=BoxType.DRAG, url="https://example.com")
        rag_box = Box(name="documents", type=BoxType.RAG)
        bag_box = Box(name="storage", type=BoxType.BAG)

        # Test drag box
        assert drag_box.is_drag_box() is True
        assert drag_box.is_rag_box() is False
        assert drag_box.is_bag_box() is False

        # Test rag box
        assert rag_box.is_drag_box() is False
        assert rag_box.is_rag_box() is True
        assert rag_box.is_bag_box() is False

        # Test bag box
        assert bag_box.is_drag_box() is False
        assert bag_box.is_rag_box() is False
        assert bag_box.is_bag_box() is True

    def test_get_type_description(self):
        """Test type description retrieval."""
        box = Box(name="my-box", type=BoxType.DRAG, url="https://example.com")
        description = box.get_type_description()

        assert isinstance(description, str)
        assert len(description) > 0
        assert "crawling" in description.lower()

    def test_settings_management(self):
        """Test settings update and retrieval."""
        box = Box(name="my-box", type=BoxType.RAG)

        # Initially empty
        assert box.get_setting("key") is None
        assert box.get_setting("key", "default") == "default"

        # Update settings
        original_time = box.updated_at
        box.update_settings({"key1": "value1", "key2": 42})

        assert box.get_setting("key1") == "value1"
        assert box.get_setting("key2") == 42
        assert box.updated_at > original_time

        # Update again (should merge)
        box.update_settings({"key3": "value3"})
        assert box.get_setting("key1") == "value1"  # Still there
        assert box.get_setting("key3") == "value3"  # New one

    def test_string_representation(self):
        """Test string representation."""
        # Regular box
        box1 = Box(name="Regular Box", type=BoxType.RAG)
        str_repr1 = str(box1)
        assert "Regular Box" in str_repr1
        assert "(rag)" in str_repr1
        assert "protected" not in str_repr1

        # Protected box
        box2 = Box(name="Protected Box", type=BoxType.BAG, is_deletable=False)
        str_repr2 = str(box2)
        assert "Protected Box" in str_repr2
        assert "(protected)" in str_repr2

        # Box with URL
        box3 = Box(name="Crawler", type=BoxType.DRAG, url="https://example.com")
        str_repr3 = str(box3)
        assert "Crawler" in str_repr3
        assert "https://example.com" in str_repr3

    def test_repr(self):
        """Test developer representation."""
        box = Box(
            id="test-id",
            name="Test Box",
            type=BoxType.DRAG,
            url="https://example.com",
            is_deletable=False
        )

        repr_str = repr(box)
        assert "Box(" in repr_str
        assert "id='test-id'" in repr_str
        assert "name='Test Box'" in repr_str
        assert "type='drag'" in repr_str
        assert "is_deletable=False" in repr_str

    def test_config_json_encoders(self):
        """Test that datetime objects and enums are properly encoded."""
        box = Box(name="Test Box", type=BoxType.RAG)
        data = box.model_dump(mode='json')

        # Dates should be ISO format strings
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)
        assert "T" in data["created_at"]  # ISO format indicator

        # Enum should be string value
        assert data["type"] == "rag"

    def test_immutable_constants(self):
        """Test that class constants are accessible."""
        assert Box.MAX_NAME_LENGTH == 100
        assert "default" in Box.RESERVED_NAMES
        assert "system" in Box.RESERVED_NAMES
        assert len(Box.RESERVED_NAMES) == 5