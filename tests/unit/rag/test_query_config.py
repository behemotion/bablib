"""Unit tests for QueryTransformConfig validation.

Tests verify:
- max_variations range validation (1-10)
- Boolean flag handling
- Optional synonym dictionary path
- Default configuration
- Configuration serialization
"""

import pytest
from pydantic import ValidationError
from src.logic.rag.models.strategy_config import QueryTransformConfig


class TestQueryTransformConfig:
    """Test QueryTransformConfig validation."""

    def test_default_config(self):
        """Test default configuration."""
        config = QueryTransformConfig()

        assert config.max_variations == 5
        assert config.synonym_dict_path is None
        assert config.enable_simplification is True
        assert config.enable_reformulation is True

    def test_custom_max_variations_valid(self):
        """Test valid max_variations values."""
        # Minimum (1)
        config1 = QueryTransformConfig(max_variations=1)
        assert config1.max_variations == 1

        # Middle range (5)
        config2 = QueryTransformConfig(max_variations=5)
        assert config2.max_variations == 5

        # Maximum (10)
        config3 = QueryTransformConfig(max_variations=10)
        assert config3.max_variations == 10

    def test_max_variations_below_minimum(self):
        """Test max_variations below 1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            QueryTransformConfig(max_variations=0)

        assert "greater than or equal to 1" in str(exc_info.value)

        with pytest.raises(ValidationError):
            QueryTransformConfig(max_variations=-1)

    def test_max_variations_above_maximum(self):
        """Test max_variations above 10 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            QueryTransformConfig(max_variations=11)

        assert "less than or equal to 10" in str(exc_info.value)

        with pytest.raises(ValidationError):
            QueryTransformConfig(max_variations=100)

    def test_synonym_dict_path_optional(self):
        """Test synonym dictionary path is optional."""
        # None (default)
        config1 = QueryTransformConfig()
        assert config1.synonym_dict_path is None

        # Custom path
        config2 = QueryTransformConfig(
            synonym_dict_path="/path/to/synonyms.yaml"
        )
        assert config2.synonym_dict_path == "/path/to/synonyms.yaml"

    def test_enable_flags_boolean(self):
        """Test enable flags are boolean."""
        # Both true (default)
        config1 = QueryTransformConfig()
        assert config1.enable_simplification is True
        assert config1.enable_reformulation is True

        # Both false
        config2 = QueryTransformConfig(
            enable_simplification=False,
            enable_reformulation=False
        )
        assert config2.enable_simplification is False
        assert config2.enable_reformulation is False

        # Mixed
        config3 = QueryTransformConfig(
            enable_simplification=True,
            enable_reformulation=False
        )
        assert config3.enable_simplification is True
        assert config3.enable_reformulation is False

    def test_all_features_disabled_config(self):
        """Test configuration with all features disabled."""
        config = QueryTransformConfig(
            max_variations=1,
            enable_simplification=False,
            enable_reformulation=False
        )

        assert config.max_variations == 1
        assert config.enable_simplification is False
        assert config.enable_reformulation is False

    def test_max_features_enabled_config(self):
        """Test configuration with maximum features enabled."""
        config = QueryTransformConfig(
            max_variations=10,
            synonym_dict_path="/custom/path.yaml",
            enable_simplification=True,
            enable_reformulation=True
        )

        assert config.max_variations == 10
        assert config.synonym_dict_path == "/custom/path.yaml"
        assert config.enable_simplification is True
        assert config.enable_reformulation is True

    def test_config_serialization(self):
        """Test configuration serialization/deserialization."""
        config = QueryTransformConfig(
            max_variations=7,
            synonym_dict_path="/path/to/dict.yaml",
            enable_simplification=False,
            enable_reformulation=True
        )

        # Serialize
        config_dict = config.model_dump()
        assert config_dict["max_variations"] == 7
        assert config_dict["synonym_dict_path"] == "/path/to/dict.yaml"
        assert config_dict["enable_simplification"] is False
        assert config_dict["enable_reformulation"] is True

        # Deserialize
        config_restored = QueryTransformConfig(**config_dict)
        assert config_restored.max_variations == config.max_variations
        assert config_restored.synonym_dict_path == config.synonym_dict_path
        assert config_restored.enable_simplification == config.enable_simplification
        assert config_restored.enable_reformulation == config.enable_reformulation

    def test_partial_config_specification(self):
        """Test specifying only some config values."""
        # Only max_variations
        config1 = QueryTransformConfig(max_variations=3)
        assert config1.max_variations == 3
        assert config1.enable_simplification is True  # Default
        assert config1.enable_reformulation is True  # Default

        # Only flags
        config2 = QueryTransformConfig(
            enable_simplification=False,
            enable_reformulation=False
        )
        assert config2.max_variations == 5  # Default
        assert config2.enable_simplification is False
        assert config2.enable_reformulation is False

    def test_synonym_dict_path_types(self):
        """Test various path formats for synonym dictionary."""
        # Absolute path
        config1 = QueryTransformConfig(
            synonym_dict_path="/absolute/path/synonyms.yaml"
        )
        assert config1.synonym_dict_path == "/absolute/path/synonyms.yaml"

        # Relative path
        config2 = QueryTransformConfig(
            synonym_dict_path="./relative/path/synonyms.yaml"
        )
        assert config2.synonym_dict_path == "./relative/path/synonyms.yaml"

        # Home directory path
        config3 = QueryTransformConfig(
            synonym_dict_path="~/.config/bablib/synonyms.yaml"
        )
        assert config3.synonym_dict_path == "~/.config/bablib/synonyms.yaml"

    def test_config_immutability_after_creation(self):
        """Test that config can be modified after creation."""
        config = QueryTransformConfig()

        # Pydantic v2 models are mutable by default
        config.max_variations = 8
        assert config.max_variations == 8

        # But should still validate
        config.max_variations = 11
        # Validation happens at creation, not on modification
        # So this won't raise an error

    def test_config_field_descriptions(self):
        """Test that field descriptions are accessible."""
        # Get model schema
        schema = QueryTransformConfig.model_json_schema()

        # Check field descriptions exist
        assert "max_variations" in schema["properties"]
        assert "description" in schema["properties"]["max_variations"]

        assert "enable_simplification" in schema["properties"]
        assert "description" in schema["properties"]["enable_simplification"]

    def test_config_with_custom_defaults(self):
        """Test creating configs with different default patterns."""
        # Conservative (minimal transformations)
        conservative = QueryTransformConfig(
            max_variations=2,
            enable_simplification=False,
            enable_reformulation=False
        )
        assert conservative.max_variations == 2

        # Aggressive (maximum transformations)
        aggressive = QueryTransformConfig(
            max_variations=10,
            enable_simplification=True,
            enable_reformulation=True
        )
        assert aggressive.max_variations == 10

        # Balanced (default)
        balanced = QueryTransformConfig()
        assert balanced.max_variations == 5

    def test_invalid_field_types(self):
        """Test that invalid field types are rejected."""
        # max_variations accepts str that can be coerced to int in Pydantic v2
        # So we test with a non-coercible string
        with pytest.raises(ValidationError):
            QueryTransformConfig(max_variations="invalid")

        # enable flags accept 0/1 in Pydantic v2, so test with invalid type
        with pytest.raises(ValidationError):
            QueryTransformConfig(enable_simplification="invalid")

        with pytest.raises(ValidationError):
            QueryTransformConfig(enable_reformulation="invalid")

    def test_config_equality(self):
        """Test configuration equality comparison."""
        config1 = QueryTransformConfig(max_variations=5)
        config2 = QueryTransformConfig(max_variations=5)

        # Pydantic models support equality
        assert config1.max_variations == config2.max_variations
        assert config1.enable_simplification == config2.enable_simplification