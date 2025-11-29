"""
Performance tests for settings load time.
"""

import pytest
import time
import tempfile
from pathlib import Path
import yaml

from src.services.settings_service import SettingsService
from src.models.settings import GlobalSettings


class TestSettingsPerformance:
    """Test settings performance requirements."""

    def test_settings_load_time_under_100ms(self, tmp_path, monkeypatch):
        """Test that settings load in under 100ms."""
        # Create a realistic settings file
        settings_file = tmp_path / "settings.yaml"
        monkeypatch.setattr("src.services.settings_service.get_global_settings_path",
                          lambda: settings_file)

        service = SettingsService()
        service.global_settings_path = settings_file

        # Create settings with all fields
        settings = GlobalSettings(
            embedding_model="mxbai-embed-large",
            vector_storage="~/.local/share/bablib/vectors",
            crawl_depth=5,
            chunk_size=2000,
            qdrant_url="http://localhost:6333",
            ollama_url="http://localhost:11434",
            rag_top_k=10,
            rag_temperature=0.8,
            rate_limit=3.0,
            max_retries=5,
            timeout=60
        )

        # Save settings
        service.save_global_settings(settings)

        # Measure load time
        start_time = time.perf_counter()
        loaded_settings = service.get_global_settings()
        load_time_ms = (time.perf_counter() - start_time) * 1000

        # Verify loaded correctly
        assert loaded_settings.crawl_depth == 5
        assert loaded_settings.chunk_size == 2000

        # Check performance requirement
        assert load_time_ms < 100, f"Settings load took {load_time_ms:.2f}ms (requirement: <100ms)"

    def test_menu_navigation_response_time(self):
        """Test menu navigation response time is under 50ms."""
        from src.models.ui import MenuState, SettingsMenuItem

        # Create menu state with many items
        state = MenuState()
        state.items = [
            SettingsMenuItem(
                key=f"setting_{i}",
                display_name=f"Setting {i}",
                value=i,
                value_type="int",
                description=f"Description for setting {i}"
            )
            for i in range(20)
        ]

        # Measure navigation operations
        operations = [
            lambda: state.move_down(),
            lambda: state.move_up(),
            lambda: state.get_current_item(),
            lambda: state.start_editing(),
            lambda: state.cancel_editing()
        ]

        for operation in operations:
            start_time = time.perf_counter()
            operation()
            response_time_ms = (time.perf_counter() - start_time) * 1000

            assert response_time_ms < 50, f"Operation took {response_time_ms:.2f}ms (requirement: <50ms)"

    def test_project_settings_merge_performance(self, tmp_path):
        """Test that settings merging is performant."""
        from src.models.settings import ProjectSettings, EffectiveSettings

        # Create settings
        global_settings = GlobalSettings()

        # Create project settings with many overrides
        project_settings = ProjectSettings(
            crawl_depth=7,
            chunk_size=3000,
            rag_top_k=15,
            rag_temperature=0.9,
            rate_limit=5.0,
            max_retries=7,
            timeout=120
        )

        # Measure merge time
        start_time = time.perf_counter()
        for _ in range(100):  # Run 100 times to get measurable time
            effective = EffectiveSettings.from_configs(global_settings, project_settings)
        total_time_ms = (time.perf_counter() - start_time) * 1000
        avg_time_ms = total_time_ms / 100

        # Each merge should be very fast
        assert avg_time_ms < 10, f"Average merge time: {avg_time_ms:.2f}ms (requirement: <10ms)"

    def test_yaml_serialization_performance(self, tmp_path):
        """Test YAML serialization/deserialization performance."""
        settings = GlobalSettings()
        settings_dict = settings.model_dump()

        # Add metadata for realistic size
        full_data = {
            "version": "1.0.0",
            "settings": settings_dict,
            "metadata": {
                "created_at": "2025-01-26T10:00:00",
                "updated_at": "2025-01-26T10:00:00",
                "reset_count": 0
            }
        }

        file_path = tmp_path / "test_settings.yaml"

        # Test save performance
        start_time = time.perf_counter()
        with open(file_path, 'w') as f:
            yaml.dump(full_data, f, default_flow_style=False)
        save_time_ms = (time.perf_counter() - start_time) * 1000

        assert save_time_ms < 50, f"Save took {save_time_ms:.2f}ms"

        # Test load performance
        start_time = time.perf_counter()
        with open(file_path, 'r') as f:
            loaded_data = yaml.safe_load(f)
        load_time_ms = (time.perf_counter() - start_time) * 1000

        assert load_time_ms < 50, f"Load took {load_time_ms:.2f}ms"
        assert loaded_data["settings"]["crawl_depth"] == settings.crawl_depth

    @pytest.mark.benchmark
    def test_settings_validation_performance(self):
        """Test that settings validation is fast."""
        from src.services.settings_service import SettingsService

        service = SettingsService()

        test_settings = {
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

        # Measure validation time
        start_time = time.perf_counter()
        for _ in range(100):  # Run multiple times
            is_valid, errors = service.validate_settings(test_settings, is_project=False)
        total_time_ms = (time.perf_counter() - start_time) * 1000
        avg_time_ms = total_time_ms / 100

        assert is_valid
        assert avg_time_ms < 5, f"Average validation time: {avg_time_ms:.2f}ms"