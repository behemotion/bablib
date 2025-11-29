"""Integration tests for reset operation flow."""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.setup]


class TestResetFlow:
    """Test complete reset (uninstall + reinstall) flow."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory with existing installation."""
        temp_dir = tempfile.mkdtemp()
        home = Path(temp_dir)

        # Create existing Bablib installation
        config_dir = home / ".config" / "bablib"
        data_dir = home / ".local" / "share" / "bablib"
        cache_dir = home / ".cache" / "bablib"

        config_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        # Write existing configuration
        config = {
            "vector_store_provider": "qdrant",
            "ollama_url": "http://custom:11434",
            "embedding_model": "custom-model"
        }
        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump(config, f)

        # Create some project data
        (data_dir / "projects" / "test-project").mkdir(parents=True)
        (data_dir / "projects" / "test-project" / "data.db").write_text("data")

        yield home
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_reset_preserves_configuration_backup(self, temp_home):
        """Test that reset creates backup of current configuration."""
        from src.logic.setup.services.reset_handler import ResetHandler

        handler = ResetHandler(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = True

            result = handler.execute()

            # Should create backup
            assert result.backup_created
            assert result.backup_path.exists()

            # Backup should contain old config
            with open(result.backup_path / "settings.yaml") as f:
                backup_config = yaml.safe_load(f)
                assert backup_config["vector_store_provider"] == "qdrant"

    def test_reset_requires_double_confirmation(self, temp_home):
        """Test that reset requires double confirmation."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.side_effect = [True, False]  # First yes, then no

            result = orchestrator.reset()

            # Should be cancelled after second confirmation
            assert result.status == "cancelled"
            assert (temp_home / ".config" / "bablib").exists()  # Still exists

    def test_reset_force_flag_skips_confirmations(self, temp_home):
        """Test that --force flag skips all confirmations."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        result = orchestrator.reset(force=True)

        # Should complete without confirmations
        assert result.status == "completed"

        # Old installation should be gone
        assert not (temp_home / ".cache" / "bablib").exists()

        # New installation should exist
        assert (temp_home / ".config" / "bablib").exists()
        assert (temp_home / ".local" / "share" / "bablib").exists()

    def test_reset_preserves_project_data_option(self, temp_home):
        """Test option to preserve project data during reset."""
        from src.logic.setup.services.reset_handler import ResetHandler

        handler = ResetHandler(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            with patch("src.logic.setup.utils.prompts.prompt_choice") as prompt:
                confirm.return_value = True
                prompt.return_value = "preserve"

                result = handler.execute(preserve_data=True)

                # Config should be reset
                with open(temp_home / ".config" / "bablib" / "settings.yaml") as f:
                    new_config = yaml.safe_load(f)
                    assert new_config["vector_store_provider"] != "qdrant"  # Reset to default

                # But project data should remain
                assert (temp_home / ".local" / "share" / "bablib" / "projects" / "test-project").exists()

    def test_reset_with_new_configuration(self, temp_home):
        """Test reset with different configuration options."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = True

            result = orchestrator.reset(
                force=True,
                vector_store="sqlite_vec"  # Switch from qdrant to sqlite_vec
            )

            # New configuration should use sqlite_vec
            with open(temp_home / ".config" / "bablib" / "settings.yaml") as f:
                new_config = yaml.safe_load(f)
                assert new_config["vector_store_provider"] == "sqlite_vec"

    def test_reset_rollback_on_failure(self, temp_home):
        """Test that reset can rollback on initialization failure."""
        from src.logic.setup.services.reset_handler import ResetHandler

        handler = ResetHandler(home_dir=temp_home)

        with patch("src.logic.setup.services.initializer.SetupInitializer") as init_mock:
            init_mock.return_value.execute.side_effect = RuntimeError("Init failed")

            with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
                confirm.return_value = True

                with pytest.raises(RuntimeError):
                    handler.execute()

                # Should restore from backup
                assert (temp_home / ".config" / "bablib").exists()
                with open(temp_home / ".config" / "bablib" / "settings.yaml") as f:
                    config = yaml.safe_load(f)
                    assert config["vector_store_provider"] == "qdrant"  # Original config

    def test_reset_state_transitions(self, temp_home):
        """Test that reset properly tracks state transitions."""
        from src.logic.setup.services.reset_handler import ResetHandler
        from src.logic.setup.models.operation import OperationStatus

        handler = ResetHandler(home_dir=temp_home)

        states_observed = []

        def track_state(state):
            states_observed.append(state)

        handler.on_state_change = track_state

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = True

            handler.execute(force=True)

            # Should go through expected states
            assert OperationStatus.PENDING in states_observed
            assert OperationStatus.IN_PROGRESS in states_observed
            assert OperationStatus.COMPLETED in states_observed