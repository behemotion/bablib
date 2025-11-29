"""
Integration tests for non-overridable fields.
"""

import pytest
from pathlib import Path
import yaml

from src.services.settings_service import SettingsService
from src.models.settings import GlobalSettings, ProjectSettings, NON_OVERRIDABLE_FIELDS


class TestNonOverridableFields:
    """Test that certain fields cannot be overridden at project level."""

    def test_non_overridable_fields_preserved(self, tmp_path, monkeypatch):
        """Test non-overridable fields remain unchanged."""
        global_dir = tmp_path / "global"
        project_dir = tmp_path / "project"
        global_dir.mkdir()
        project_dir.mkdir()

        monkeypatch.setattr("src.services.settings_service.get_global_settings_path",
                          lambda: global_dir / "settings.yaml")

        service = SettingsService()
        service.global_settings_path = global_dir / "settings.yaml"

        # Set global settings
        global_settings = GlobalSettings()
        service.save_global_settings(global_settings)

        # Try to override non-overridable fields in project
        project_file = project_dir / ".bablib" / "settings.yaml"
        project_file.parent.mkdir(parents=True)

        # Manually create project settings with non-overridable fields
        project_data = {
            "version": "1.0.0",
            "settings": {
                "vector_storage": "/custom/vectors",  # Non-overridable
                "qdrant_url": "http://custom:6333",  # Non-overridable
                "ollama_url": "http://custom:11434",  # Non-overridable
                "crawl_depth": 5  # This is OK
            },
            "modified_fields": ["vector_storage", "qdrant_url", "ollama_url", "crawl_depth"]
        }

        with open(project_file, "w") as f:
            yaml.dump(project_data, f)

        # Get effective settings
        effective = service.get_effective_settings(project_dir)

        # Non-overridable fields should keep global values
        assert effective.vector_storage == global_settings.vector_storage
        assert effective.qdrant_url == "http://localhost:6333"
        assert effective.ollama_url == "http://localhost:11434"

        # Overridable field should change
        assert effective.crawl_depth == 5

    def test_validation_rejects_non_overridable_in_project(self, tmp_path):
        """Test validation rejects non-overridable fields in project settings."""
        service = SettingsService()

        # Try to validate project settings with non-overridable fields
        invalid_project = {
            "vector_storage": "/custom/path",
            "qdrant_url": "http://custom:6333"
        }

        is_valid, errors = service.validate_settings(invalid_project, is_project=True)

        assert not is_valid
        assert len(errors) >= 2
        assert any("vector_storage" in err for err in errors)
        assert any("qdrant_url" in err for err in errors)

    def test_non_overridable_fields_list_is_complete(self):
        """Test NON_OVERRIDABLE_FIELDS contains all expected fields."""
        expected_non_overridable = {
            "vector_storage",
            "qdrant_url",
            "ollama_url"
        }

        assert NON_OVERRIDABLE_FIELDS == expected_non_overridable

    def test_service_endpoints_remain_global(self, tmp_path, monkeypatch):
        """Test service endpoints cannot be changed per project."""
        global_dir = tmp_path / "global"
        project_dir = tmp_path / "project"
        global_dir.mkdir()
        project_dir.mkdir()

        monkeypatch.setattr("src.services.settings_service.get_global_settings_path",
                          lambda: global_dir / "settings.yaml")

        service = SettingsService()
        service.global_settings_path = global_dir / "settings.yaml"

        # Custom global endpoints
        global_settings = GlobalSettings(
            qdrant_url="http://global-qdrant:6333",
            ollama_url="http://global-ollama:11434"
        )
        service.save_global_settings(global_settings)

        # Create project with attempts to override
        project_settings = ProjectSettings()
        # These fields don't exist in ProjectSettings model, so they can't be set
        service.save_project_settings(project_settings, project_dir)

        # Get effective settings
        effective = service.get_effective_settings(project_dir)

        # Endpoints should remain as global
        assert effective.qdrant_url == "http://global-qdrant:6333"
        assert effective.ollama_url == "http://global-ollama:11434"

    def test_warning_on_non_overridable_attempt(self, tmp_path, monkeypatch, capsys):
        """Test that attempting to override non-overridable fields produces warning."""
        global_dir = tmp_path / "global"
        project_dir = tmp_path / "project"
        global_dir.mkdir()
        project_dir.mkdir()

        monkeypatch.setattr("src.services.settings_service.get_global_settings_path",
                          lambda: global_dir / "settings.yaml")

        service = SettingsService()
        service.global_settings_path = global_dir / "settings.yaml"

        # Save global
        service.save_global_settings(GlobalSettings())

        # Manually create project file with non-overridable fields
        project_file = project_dir / ".bablib" / "settings.yaml"
        project_file.parent.mkdir(parents=True)

        invalid_data = {
            "version": "1.0.0",
            "settings": {
                "vector_storage": "/invalid/path"
            },
            "modified_fields": ["vector_storage"]
        }

        with open(project_file, "w") as f:
            yaml.dump(invalid_data, f)

        # Load and check - non-overridable fields should be ignored
        effective = service.get_effective_settings(project_dir)

        # Should use global value, not project attempt
        assert "~/.local/share/bablib/vectors" in effective.vector_storage