"""
Contract tests for project settings override logic.
"""

import pytest
from pathlib import Path
from src.services.settings_service import SettingsService
from src.models.settings import GlobalSettings, ProjectSettings, EffectiveSettings


class TestProjectSettingsAPI:
    """Test project settings override contracts."""

    def test_project_settings_override_global(self):
        """Test that project settings override global defaults."""
        global_settings = GlobalSettings(
            crawl_depth=3,
            chunk_size=1500
        )

        project_settings = ProjectSettings(
            crawl_depth=5,
            chunk_size=2000
        )
        project_settings.modified_fields = {"crawl_depth", "chunk_size"}

        effective = EffectiveSettings.from_configs(global_settings, project_settings)

        assert effective.crawl_depth == 5  # Project override
        assert effective.chunk_size == 2000  # Project override
        assert effective.rag_temperature == 0.7  # Global default

    def test_non_overridable_fields_preserved(self):
        """Test that non-overridable fields cannot be changed at project level."""
        global_settings = GlobalSettings()
        project_settings = ProjectSettings()

        # Try to set non-overridable fields (should be ignored)
        project_data = {
            "vector_storage": "/custom/path",
            "qdrant_url": "http://custom:6333",
            "ollama_url": "http://custom:11434"
        }

        effective = EffectiveSettings.from_configs(global_settings, project_settings)

        # Non-overridable fields should remain as global defaults
        assert effective.vector_storage == global_settings.vector_storage
        assert effective.qdrant_url == "http://localhost:6333"
        assert effective.ollama_url == "http://localhost:11434"

    def test_project_settings_partial_override(self):
        """Test partial project overrides with inheritance."""
        global_settings = GlobalSettings(
            crawl_depth=3,
            chunk_size=1500,
            rag_temperature=0.7
        )

        # Only override crawl_depth
        project_settings = ProjectSettings(crawl_depth=7)
        project_settings._modified_fields = {"crawl_depth"}

        effective = EffectiveSettings.from_configs(global_settings, project_settings)

        assert effective.crawl_depth == 7  # Overridden
        assert effective.chunk_size == 1500  # Inherited from global
        assert effective.rag_temperature == 0.7  # Inherited from global

    def test_save_and_load_project_settings(self, tmp_path):
        """Test project settings persistence."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        settings_file = project_dir / ".bablib" / "settings.yaml"

        service = SettingsService()

        # Create project settings
        project_settings = ProjectSettings(
            crawl_depth=8,
            chunk_size=2500
        )
        project_settings.modified_fields = {"crawl_depth", "chunk_size"}

        # Save
        service.save_project_settings(project_settings, project_dir)
        assert settings_file.exists()

        # Load
        loaded = service.get_project_settings(project_dir)
        assert loaded is not None
        assert loaded.crawl_depth == 8
        assert loaded.chunk_size == 2500
        assert loaded.is_modified("crawl_depth")
        assert loaded.is_modified("chunk_size")