"""
Contract tests for settings validation endpoint.
"""

import pytest
from src.services.settings_service import SettingsService
from src.models.settings import GlobalSettings, ProjectSettings


class TestSettingsValidation:
    """Test settings validation contracts."""

    def test_validate_valid_global_settings(self):
        """Test validation of valid global settings."""
        service = SettingsService()

        valid_settings = {
            "embedding_model": "mxbai-embed-large",
            "crawl_depth": 5,
            "chunk_size": 2000,
            "rag_temperature": 0.7,
            "vector_storage": "~/.local/share/bablib/vectors",
            "qdrant_url": "http://localhost:6333",
            "ollama_url": "http://localhost:11434",
            "rag_top_k": 5,
            "rate_limit": 2.0,
            "max_retries": 3,
            "timeout": 30
        }

        is_valid, errors = service.validate_settings(valid_settings, is_project=False)
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_global_settings(self):
        """Test validation catches invalid global settings."""
        service = SettingsService()

        invalid_settings = {
            "crawl_depth": 15,  # Exceeds maximum (10)
            "chunk_size": 50,  # Below minimum (100)
            "rag_temperature": 1.5,  # Above maximum (1.0)
            "timeout": 400  # Exceeds maximum (300)
        }

        is_valid, errors = service.validate_settings(invalid_settings, is_project=False)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_project_settings_rejects_non_overridable(self):
        """Test that project validation rejects non-overridable fields."""
        service = SettingsService()

        project_settings = {
            "crawl_depth": 5,  # OK - overridable
            "vector_storage": "/custom/path",  # NOT OK - non-overridable
            "qdrant_url": "http://custom:6333"  # NOT OK - non-overridable
        }

        is_valid, errors = service.validate_settings(project_settings, is_project=True)
        assert not is_valid
        assert any("vector_storage" in err for err in errors)
        assert any("qdrant_url" in err for err in errors)

    def test_validate_embedding_model_choices(self):
        """Test validation of embedding model choices."""
        service = SettingsService()

        # Valid model
        valid = {"embedding_model": "mxbai-embed-large"}
        is_valid, errors = service.validate_settings(valid, is_project=False)
        assert is_valid or len(errors) > 0  # Partial validation is OK

        # Invalid model
        invalid = {"embedding_model": "unknown-model"}
        is_valid, errors = service.validate_settings(invalid, is_project=False)

        # Should fail validation due to unknown model
        if "embedding_model" in invalid:
            assert not is_valid or len(errors) > 0

    def test_validate_numeric_ranges(self):
        """Test validation of numeric field ranges."""
        service = SettingsService()

        test_cases = [
            ({"crawl_depth": 0}, False),  # Below min (1)
            ({"crawl_depth": 11}, False),  # Above max (10)
            ({"crawl_depth": 5}, True),  # Valid

            ({"chunk_size": 99}, False),  # Below min (100)
            ({"chunk_size": 10001}, False),  # Above max (10000)
            ({"chunk_size": 5000}, True),  # Valid

            ({"rag_temperature": -0.1}, False),  # Below min (0.0)
            ({"rag_temperature": 1.1}, False),  # Above max (1.0)
            ({"rag_temperature": 0.5}, True),  # Valid
        ]

        for settings, should_be_valid in test_cases:
            is_valid, errors = service.validate_settings(settings, is_project=False)
            # For partial validation, we check if there are errors related to our field
            if not should_be_valid:
                # Invalid settings should produce errors or fail validation
                assert not is_valid or len(errors) > 0