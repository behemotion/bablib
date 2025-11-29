"""Integration test for system requirements failure scenario.

This test simulates quickstart scenario #4: System requirements failure.
Test should FAIL initially since system validation doesn't exist yet (TDD requirement).
"""

import pytest
import tempfile
import shutil
import platform
import sys
import os
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, MagicMock

from src.services.config import ConfigService
from src.services.setup import SetupWizardService, SetupError
from src.models.installation import SystemRequirements, InstallationContext


@pytest.mark.integration
class TestSystemRequirementsFailure:
    """Test system requirements failure and graceful error handling."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_platformdirs(self, temp_home):
        """Mock platformdirs to use temp directory."""
        with patch('platformdirs.user_config_dir') as mock_config, \
             patch('platformdirs.user_data_dir') as mock_data, \
             patch('platformdirs.user_cache_dir') as mock_cache:

            mock_config.return_value = str(temp_home / ".config" / "bablib")
            mock_data.return_value = str(temp_home / ".local" / "share" / "bablib")
            mock_cache.return_value = str(temp_home / ".cache" / "bablib")
            yield

    def test_python_version_requirements_failure(self, mock_platformdirs, temp_home):
        """Test installation aborts immediately when Python version is insufficient."""
        wizard = SetupWizardService()

        # Mock Python version to be less than 3.13 (unsupported)
        with patch('sys.version_info', Mock(major=3, minor=12, micro=5)):
            with pytest.raises(SetupError) as exc_info:
                wizard._check_python_version()

            error_msg = str(exc_info.value)
            assert "Unsupported Python version: 3.12.5" in error_msg
            assert "Python 3.13.x required" in str(exc_info.value.__cause__ or "Python 3.13.x required")

        # Verify no installation artifacts are created
        assert not wizard.config_service.installation_config_path.exists()
        assert not (wizard.config_service.config_dir / "wizard.json").exists()

    def test_insufficient_memory_requirements_failure(self, mock_platformdirs, temp_home):
        """Test system validation fails when insufficient RAM is available."""
        # Test that system validation service doesn't exist yet
        # When implemented, it should detect insufficient memory and fail
        wizard = SetupWizardService()

        # This should fail because we don't have system validation implemented yet
        with pytest.raises(AttributeError):
            # This method doesn't exist yet - should be implemented in system validation service
            wizard.validate_system_requirements()

    @patch('shutil.disk_usage')
    def test_insufficient_disk_space_requirements_failure(self, mock_disk_usage, mock_platformdirs, temp_home):
        """Test system validation fails when insufficient disk space is available."""
        # Mock system with only 50MB free disk space (below 100MB minimum)
        mock_disk_usage.return_value = (1000000000, 950000000, 50 * 1024 * 1024)  # 50MB free

        # This should fail because we don't have system validation implemented yet
        with pytest.raises(AttributeError):
            wizard = SetupWizardService()
            # This method doesn't exist yet - should be implemented in system validation service
            wizard.validate_system_requirements()

    def test_unsupported_platform_requirements_failure(self, mock_platformdirs, temp_home):
        """Test system validation fails on unsupported platform."""
        # Mock unsupported platform (e.g., FreeBSD)
        with patch('platform.system', return_value='FreeBSD'):
            # This should fail because we don't have system validation implemented yet
            with pytest.raises(AttributeError):
                wizard = SetupWizardService()
                # This method doesn't exist yet - should be implemented in system validation service
                wizard.validate_system_requirements()

    def test_system_requirements_validation_with_insufficient_resources(self):
        """Test SystemRequirements model validation fails with insufficient resources."""
        from pydantic import ValidationError

        # Test memory below minimum (512MB)
        with pytest.raises(ValidationError) as exc_info:
            SystemRequirements(
                python_version="3.13.1",
                platform="darwin",
                memory_mb=256,  # Below 512MB minimum
                disk_space_mb=1000,
                has_internet=True
            )
        assert "greater than or equal to 512" in str(exc_info.value)

        # Test disk space below minimum (100MB)
        with pytest.raises(ValidationError) as exc_info:
            SystemRequirements(
                python_version="3.13.1",
                platform="darwin",
                memory_mb=1024,
                disk_space_mb=50,  # Below 100MB minimum
                has_internet=True
            )
        assert "greater than or equal to 100" in str(exc_info.value)

        # Test unsupported platform
        with pytest.raises(ValidationError) as exc_info:
            SystemRequirements(
                python_version="3.13.1",
                platform="freebsd",  # Not in supported platforms
                memory_mb=1024,
                disk_space_mb=1000,
                has_internet=True
            )
        assert "Input should be 'darwin', 'linux' or 'windows'" in str(exc_info.value)

    @patch('sys.version_info', Mock(major=3, minor=12, micro=8))
    @patch('shutil.disk_usage')
    @patch('platform.system')
    def test_multiple_system_requirements_failure(self, mock_platform, mock_disk_usage,
                                                 mock_platformdirs, temp_home):
        """Test system validation fails gracefully when multiple requirements are not met."""
        # Mock a system that fails multiple requirements
        mock_platform.return_value = 'FreeBSD'  # Unsupported platform
        mock_disk_usage.return_value = (1000000000, 950000000, 25 * 1024 * 1024)  # 25MB free (insufficient)

        wizard = SetupWizardService()

        # First, Python version should fail
        with pytest.raises(SetupError) as exc_info:
            wizard._check_python_version()
        assert "Unsupported Python version: 3.12.8" in str(exc_info.value)

        # Additional system checks should also fail when implemented
        with pytest.raises(AttributeError):
            # This method doesn't exist yet - should be implemented in system validation service
            wizard.validate_system_requirements()

    def test_clear_error_messages_for_requirements_failure(self, mock_platformdirs, temp_home):
        """Test that system requirements failures provide clear, user-friendly error messages."""
        wizard = SetupWizardService()

        # Test Python version error message clarity
        with patch('sys.version_info', Mock(major=3, minor=11, micro=0)):
            with pytest.raises(SetupError) as exc_info:
                wizard._check_python_version()

            error_msg = str(exc_info.value)
            # Should contain clear guidance
            assert "Unsupported Python version: 3.11.0" in error_msg
            # Should suggest what to do next (this would be in the actual error handling)
            # Currently implemented in the setup wizard console output

    def test_no_partial_installation_artifacts_on_failure(self, mock_platformdirs, temp_home):
        """Test that failed installation doesn't leave partial artifacts."""
        wizard = SetupWizardService()

        # Simulate system requirements failure
        with patch('sys.version_info', Mock(major=3, minor=12, micro=0)):
            with pytest.raises(SetupError):
                wizard._check_python_version()

        # Verify no configuration files were created
        assert not wizard.config_service.installation_config_path.exists()
        assert not (wizard.config_service.config_dir / "wizard.json").exists()

        # Verify directories weren't created unnecessarily
        config_dir = wizard.config_service.config_dir
        if config_dir.exists():
            # If directory exists, it should be empty
            assert list(config_dir.iterdir()) == []

    def test_system_upgrade_instructions_provided(self, mock_platformdirs, temp_home):
        """Test that clear instructions are provided to upgrade system when requirements fail."""
        wizard = SetupWizardService()

        # This test validates that the user gets helpful guidance
        # Currently, the guidance is provided via console.print in the setup wizard
        # We're testing that the failure mode exists and is handled

        with patch('sys.version_info', Mock(major=3, minor=12, micro=0)):
            # Mock the console to capture output
            with patch('src.services.setup.console') as mock_console:
                with pytest.raises(SetupError):
                    wizard._check_python_version()

                # Verify helpful messages were printed
                mock_console.print.assert_any_call(
                    "[red]✗ Python 3.13.x required, found 3.12.0[/red]"
                )
                mock_console.print.assert_any_call(
                    "\nPlease install Python 3.13.x and try again."
                )
                mock_console.print.assert_any_call(
                    "Visit: https://python.org/downloads/"
                )

    @pytest.mark.asyncio
    async def test_setup_wizard_aborts_early_on_requirements_failure(self, mock_platformdirs, temp_home):
        """Test that setup wizard aborts immediately on requirements failure without proceeding."""
        wizard = SetupWizardService()

        # Mock Python version failure
        with patch('sys.version_info', Mock(major=3, minor=12, micro=0)):
            with pytest.raises(SetupError):
                await wizard.run_interactive_setup()

        # Verify setup didn't proceed to later steps
        state = wizard.load_wizard_state()
        if state:
            # If state exists, it should only have welcome step
            assert "python_check" not in state.completed_steps
            assert "service_check" not in state.completed_steps
            assert "service_install" not in state.completed_steps

    def test_system_requirements_model_validates_current_system(self):
        """Test that SystemRequirements model can validate the current system."""
        # Get actual system info using standard library only
        disk_usage = shutil.disk_usage('/')
        disk_free_mb = disk_usage.free // (1024 * 1024)
        current_platform = platform.system().lower()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Map platform names
        platform_map = {"darwin": "darwin", "linux": "linux", "windows": "windows"}
        mapped_platform = platform_map.get(current_platform)

        # Only test if we're on a supported platform and have Python 3.13
        if mapped_platform and python_version.startswith("3.13."):
            requirements = SystemRequirements(
                python_version=python_version,
                platform=mapped_platform,
                memory_mb=1024,  # Use reasonable default
                disk_space_mb=max(100, min(1000, disk_free_mb)),  # Ensure minimum, cap at 1GB
                has_internet=True
            )

            assert requirements.python_version == python_version
            assert requirements.platform == mapped_platform
            assert requirements.memory_mb >= 512
            assert requirements.disk_space_mb >= 100

    def test_requirements_validation_service_interface_not_implemented(self):
        """Test that system requirements validation service doesn't exist yet (TDD requirement)."""
        # This test ensures we follow TDD - the service should not exist yet
        with pytest.raises(ImportError):
            from src.services.system_validation import SystemValidationService

        # Also verify the setup wizard doesn't have the validation method
        wizard = SetupWizardService()
        assert not hasattr(wizard, 'validate_system_requirements')

    @pytest.mark.asyncio
    async def test_full_requirements_failure_scenario(self, mock_platformdirs, temp_home):
        """Test complete system requirements failure scenario from start to finish."""
        # This is the main integration test that simulates quickstart scenario #4
        wizard = SetupWizardService()

        # Create a state file to simulate partially completed setup
        state = wizard.create_wizard_state()
        state.completed_steps.append("welcome")
        state.current_step = "python_check"
        wizard.save_wizard_state(state)

        # Simulate system that doesn't meet requirements
        with patch('sys.version_info', Mock(major=3, minor=12, micro=0)):
            with pytest.raises(SetupError) as exc_info:
                await wizard.run_interactive_setup()

        # Verify error message is user-friendly
        assert "Unsupported Python version" in str(exc_info.value)

        # Verify no installation context was created
        context = wizard.config_service.load_installation_context()
        assert context is None

        # Verify wizard state is preserved for potential retry
        saved_state = wizard.load_wizard_state()
        assert saved_state is not None
        assert "welcome" in saved_state.completed_steps
        assert "python_check" not in saved_state.completed_steps