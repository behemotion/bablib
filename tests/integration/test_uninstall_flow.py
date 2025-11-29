"""Integration tests for uninstall confirmation flow."""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch

pytestmark = [pytest.mark.integration, pytest.mark.setup]


class TestUninstallFlow:
    """Test complete uninstall flow with confirmations."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory with Bablib installation."""
        temp_dir = tempfile.mkdtemp()
        home = Path(temp_dir)

        # Create Bablib directory structure
        (home / ".config" / "bablib").mkdir(parents=True)
        (home / ".local" / "share" / "bablib" / "projects").mkdir(parents=True)
        (home / ".cache" / "bablib").mkdir(parents=True)

        # Create some files
        (home / ".config" / "bablib" / "settings.yaml").write_text("test: true")
        (home / ".local" / "share" / "bablib" / "data.db").write_text("data")

        yield home
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_uninstall_generates_manifest(self, temp_home):
        """Test that uninstall generates accurate manifest."""
        from src.logic.setup.services.uninstaller import SetupUninstaller

        uninstaller = SetupUninstaller(home_dir=temp_home)
        manifest = uninstaller.generate_manifest()

        # Verify manifest includes all directories
        assert any(".config/bablib" in str(d) for d in manifest.directories)
        assert any(".local/share/bablib" in str(d) for d in manifest.directories)
        assert any(".cache/bablib" in str(d) for d in manifest.directories)

        # Verify size calculation
        assert manifest.total_size_bytes > 0

    def test_uninstall_requires_confirmation(self, temp_home):
        """Test that uninstall requires user confirmation."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = False  # User cancels

            result = orchestrator.uninstall()

            # Should not proceed with uninstall
            assert result.status == "cancelled"
            assert (temp_home / ".config" / "bablib").exists()  # Still exists

    def test_uninstall_force_flag_skips_confirmation(self, temp_home):
        """Test that --force flag skips confirmation."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        result = orchestrator.uninstall(force=True)

        # Should proceed without confirmation
        assert result.status == "completed"
        assert not (temp_home / ".config" / "bablib").exists()

    def test_uninstall_creates_backup(self, temp_home):
        """Test that uninstall can create backup."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = True

            result = orchestrator.uninstall(backup=True)

            # Verify backup created
            assert result.backup_location is not None
            backup_path = Path(result.backup_location)
            assert backup_path.exists()

    def test_uninstall_dry_run(self, temp_home):
        """Test dry-run shows what would be removed."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        result = orchestrator.uninstall(dry_run=True)

        # Should not actually remove anything
        assert result.status == "dry_run"
        assert (temp_home / ".config" / "bablib").exists()  # Still exists

        # Should include list of what would be removed
        assert result.would_remove
        assert len(result.would_remove) > 0

    def test_uninstall_handles_partial_installation(self, temp_home):
        """Test uninstall handles missing directories gracefully."""
        from src.logic.setup.services.uninstaller import SetupUninstaller

        # Remove cache directory to simulate partial installation
        shutil.rmtree(temp_home / ".cache" / "bablib")

        uninstaller = SetupUninstaller(home_dir=temp_home)
        result = uninstaller.execute(force=True)

        # Should succeed even with missing directories
        assert result.status == "completed"
        assert not (temp_home / ".config" / "bablib").exists()

    def test_uninstall_preserves_user_data_option(self, temp_home):
        """Test option to preserve user project data."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            with patch("src.logic.setup.utils.prompts.prompt_choice") as prompt:
                confirm.return_value = True
                prompt.return_value = "preserve"

                result = orchestrator.uninstall(preserve_data=True)

                # Config should be removed
                assert not (temp_home / ".config" / "bablib").exists()

                # But project data should remain
                assert (temp_home / ".local" / "share" / "bablib" / "projects").exists()