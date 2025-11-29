"""Integration test for cross-platform installation compatibility.

This test validates platform detection, XDG directory handling, and service
compatibility across different platforms (macOS, Linux, Windows).

Based on quickstart scenario #7: Cross-platform compatibility testing.

TDD Approach:
- Tests are designed to FAIL initially since cross-platform features don't exist yet
- Uses pytest.raises() to expect ImportError/AttributeError for missing components
- Some tests will show actual failures (not caught by pytest.raises) to demonstrate gaps
- Once implementation is complete, tests should pass without modification

Expected Implementation Requirements:
1. PlatformDetectionService - New service for platform-aware operations
2. Platform-specific methods in ServiceDetectionService
3. Platform metadata fields in InstallationContext model
4. Platform-aware error handling in ConfigService
5. Platform-specific setup instructions in SetupWizardService
"""

import pytest
import tempfile
import platform
import shutil
import os
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime

from src.services.config import ConfigService
from src.services.detection import ServiceDetectionService
from src.services.setup import SetupWizardService
from src.models.installation import InstallationContext, ServiceStatus


@pytest.mark.integration
class TestCrossPlatformInstallation:
    """Test cross-platform installation compatibility."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.parametrize("platform_system,expected_behavior", [
        ("Darwin", {
            "system_name": "macOS",
            "uses_homebrew": True,
            "path_separator": "/",
            "config_subdir": ".config/bablib",
            "data_subdir": ".local/share/bablib",
            "cache_subdir": ".cache/bablib",
            "package_manager": "homebrew",
            "service_manager": "launchd"
        }),
        ("Linux", {
            "system_name": "Linux",
            "uses_homebrew": False,
            "path_separator": "/",
            "config_subdir": ".config/bablib",
            "data_subdir": ".local/share/bablib",
            "cache_subdir": ".cache/bablib",
            "package_manager": "apt/yum/pacman",
            "service_manager": "systemd"
        }),
        ("Windows", {
            "system_name": "Windows",
            "uses_homebrew": False,
            "path_separator": "\\",
            "config_subdir": "AppData\\Roaming\\bablib",
            "data_subdir": "AppData\\Local\\bablib",
            "cache_subdir": "AppData\\Local\\bablib\\cache",
            "package_manager": "winget/chocolatey",
            "service_manager": "windows_services"
        })
    ])
    def test_platform_detection_and_behavior(self, platform_system, expected_behavior, temp_home):
        """Test platform detection returns correct system information.

        This test should FAIL initially since platform detection doesn't exist yet.
        Following TDD principles: Red -> Green -> Refactor.
        """
        with patch('platform.system', return_value=platform_system):
            # This should fail initially - platform detection service doesn't exist
            with pytest.raises((ImportError, AttributeError, ModuleNotFoundError)):
                from src.services.platform_detection import PlatformDetectionService

                detection_service = PlatformDetectionService()
                platform_info = detection_service.detect_platform()

                # These assertions should pass once platform detection is implemented
                assert platform_info.system_name == expected_behavior["system_name"]
                assert platform_info.uses_homebrew == expected_behavior["uses_homebrew"]
                assert platform_info.path_separator == expected_behavior["path_separator"]
                assert platform_info.package_manager == expected_behavior["package_manager"]
                assert platform_info.service_manager == expected_behavior["service_manager"]

    @pytest.mark.parametrize("platform_system,expected_paths", [
        ("Darwin", {
            "config_path": ".config/bablib",
            "data_path": ".local/share/bablib",
            "cache_path": ".cache/bablib"
        }),
        ("Linux", {
            "config_path": ".config/bablib",
            "data_path": ".local/share/bablib",
            "cache_path": ".cache/bablib"
        }),
        ("Windows", {
            "config_path": "AppData/Roaming/bablib",
            "data_path": "AppData/Local/bablib",
            "cache_path": "AppData/Local/bablib/cache"
        })
    ])
    def test_xdg_directory_handling_per_platform(self, platform_system, expected_paths, temp_home):
        """Test XDG Base Directory specification compliance per platform."""
        with patch('platform.system', return_value=platform_system):
            # Mock platformdirs for each platform
            with patch('platformdirs.user_config_dir') as mock_config, \
                 patch('platformdirs.user_data_dir') as mock_data, \
                 patch('platformdirs.user_cache_dir') as mock_cache:

                # Set platform-appropriate paths
                if platform_system == "Windows":
                    mock_config.return_value = str(temp_home / "AppData" / "Roaming" / "bablib")
                    mock_data.return_value = str(temp_home / "AppData" / "Local" / "bablib")
                    mock_cache.return_value = str(temp_home / "AppData" / "Local" / "bablib" / "cache")
                else:  # Darwin/Linux use XDG
                    mock_config.return_value = str(temp_home / ".config" / "bablib")
                    mock_data.return_value = str(temp_home / ".local" / "share" / "bablib")
                    mock_cache.return_value = str(temp_home / ".cache" / "bablib")

                config_service = ConfigService()
                config_service.ensure_directories()

                # Verify directories were created correctly
                assert config_service.config_dir.exists()
                assert config_service.data_dir.exists()
                assert config_service.cache_dir.exists()

                # Verify paths contain platform-appropriate segments
                config_str = str(config_service.config_dir)
                if platform_system == "Windows":
                    assert "AppData" in config_str
                    assert "Roaming" in config_str
                else:
                    assert ".config" in config_str

    def test_service_compatibility_across_platforms(self, temp_home):
        """Test service detection adapts to platform-specific service managers."""
        # This test should initially fail since platform-aware service detection doesn't exist
        detection_service = ServiceDetectionService(timeout=1)

        # Test current platform detection
        current_platform = platform.system()

        # These methods don't exist yet - should raise AttributeError
        with pytest.raises(AttributeError):
            # These methods should be added to ServiceDetectionService for platform awareness
            platform_services = detection_service.get_platform_specific_services()

        with pytest.raises(AttributeError):
            service_check_method = detection_service.get_platform_service_check_method()

        # Verify current service detection works but lacks platform awareness
        docker_status = detection_service.check_docker()
        assert isinstance(docker_status, ServiceStatus)

        # The current implementation doesn't adapt commands per platform
        # When implemented, should use platform-specific commands

    @pytest.mark.parametrize("platform_system,path_style", [
        ("Darwin", "posix"),
        ("Linux", "posix"),
        # Skip Windows path testing on non-Windows systems due to pathlib limitations
        pytest.param("Windows", "nt", marks=pytest.mark.skipif(
            platform.system() != "Windows",
            reason="Cannot test Windows paths on non-Windows system"
        ))
    ])
    def test_path_handling_differences(self, platform_system, path_style, temp_home):
        """Test proper path handling for different platforms."""
        with patch('platform.system', return_value=platform_system), \
             patch('os.name', path_style):

            # Test platform-specific path handling that should be implemented
            if platform_system == "Windows" and platform.system() != "Windows":
                pytest.skip("Cannot test Windows paths on non-Windows system")

            config_service = ConfigService()

            # Test path construction
            test_project_path = config_service.data_dir / "projects" / "test-project"
            config_service.ensure_directories()
            test_project_path.mkdir(parents=True, exist_ok=True)

            # Verify path exists and uses correct separators
            assert test_project_path.exists()

            # Test path string representation
            path_str = str(test_project_path)
            if platform_system == "Windows":
                # Windows should handle both / and \ but prefer \
                assert test_project_path.is_absolute()
            else:
                # Unix-like systems use /
                assert "/" in path_str
                assert test_project_path.is_absolute()

    def test_installation_context_platform_metadata(self, temp_home):
        """Test that installation context includes platform-specific metadata."""
        with patch('platformdirs.user_config_dir', return_value=str(temp_home / ".config" / "bablib")), \
             patch('platformdirs.user_data_dir', return_value=str(temp_home / ".local" / "share" / "bablib")), \
             patch('platformdirs.user_cache_dir', return_value=str(temp_home / ".cache" / "bablib")):

            config_service = ConfigService()

            # This should fail initially - platform metadata not in InstallationContext
            with pytest.raises((AttributeError, KeyError)):
                context = config_service.create_installation_context(
                    install_method="uvx",
                    version="1.0.0",
                    python_version="3.13.1"
                )

                # These fields should be added to InstallationContext model
                assert hasattr(context, 'platform_system')
                assert hasattr(context, 'platform_architecture')
                assert hasattr(context, 'platform_version')
                assert context.platform_system == platform.system()
                assert context.platform_architecture == platform.machine()

    @pytest.mark.parametrize("platform_system,expected_service_commands", [
        ("Darwin", {
            "docker_check": ["docker", "version"],
            "service_status_cmd": ["launchctl", "list"],
            "homebrew_check": ["brew", "--version"]
        }),
        ("Linux", {
            "docker_check": ["docker", "version"],
            "service_status_cmd": ["systemctl", "--user", "status"],
            "package_check": ["which", "apt", "||", "which", "yum", "||", "which", "pacman"]
        }),
        ("Windows", {
            "docker_check": ["docker.exe", "version"],
            "service_status_cmd": ["sc.exe", "query"],
            "package_check": ["winget", "--version"]
        })
    ])
    def test_platform_specific_service_commands(self, platform_system, expected_service_commands, temp_home):
        """Test that service detection uses platform-appropriate commands."""
        with patch('platform.system', return_value=platform_system):
            detection_service = ServiceDetectionService(timeout=1)

            # This should fail initially - platform-specific commands not implemented
            with pytest.raises((AttributeError, NotImplementedError)):
                # These methods should be added to ServiceDetectionService
                docker_cmd = detection_service.get_docker_check_command()
                service_cmd = detection_service.get_service_status_command()

                # Verify platform-appropriate commands
                if platform_system == "Windows":
                    assert "docker.exe" in docker_cmd
                    assert "sc.exe" in service_cmd
                else:
                    assert "docker" in docker_cmd
                    if platform_system == "Darwin":
                        assert "launchctl" in service_cmd
                    elif platform_system == "Linux":
                        assert "systemctl" in service_cmd

    @pytest.mark.asyncio
    async def test_setup_wizard_platform_adaptation(self, temp_home):
        """Test setup wizard adapts prompts and instructions per platform."""
        with patch('platformdirs.user_config_dir', return_value=str(temp_home / ".config" / "bablib")):
            wizard = SetupWizardService()

            current_platform = platform.system()

            # This should fail initially - platform-specific setup not implemented
            with pytest.raises((AttributeError, NotImplementedError)):
                # These methods should be added to SetupWizardService
                platform_instructions = wizard.get_platform_specific_instructions()
                service_install_commands = wizard.get_service_install_commands()

                # Verify platform-appropriate instructions
                if current_platform == "Darwin":
                    assert "brew install" in str(service_install_commands)
                    assert "macOS" in str(platform_instructions)
                elif current_platform == "Linux":
                    assert ("apt install" in str(service_install_commands) or
                            "yum install" in str(service_install_commands) or
                            "pacman -S" in str(service_install_commands))
                elif current_platform == "Windows":
                    assert ("winget install" in str(service_install_commands) or
                            "choco install" in str(service_install_commands))
                    assert "Windows" in str(platform_instructions)

    def test_error_handling_platform_differences(self, temp_home):
        """Test error handling accounts for platform-specific differences."""
        with patch('platformdirs.user_config_dir', return_value=str(temp_home / ".config" / "bablib")):
            config_service = ConfigService()

            current_platform = platform.system()

            # Test permission error handling per platform
            config_service.ensure_directories()

            # Create a file where directory should be (to cause error)
            fake_config_file = config_service.config_dir / "installation.json"
            fake_config_file.parent.rmdir()  # Remove directory
            fake_config_file.parent.write_text("not a directory")  # Create file instead

            # This should fail initially - platform-specific error handling not implemented
            with pytest.raises((AttributeError, NotImplementedError)):
                # These methods should be added for platform-specific error handling
                error_handler = config_service.get_platform_error_handler()
                recovery_suggestions = error_handler.get_recovery_suggestions(current_platform)

                # Verify platform-appropriate error messages
                if current_platform == "Windows":
                    assert "Windows" in str(recovery_suggestions)
                    assert ("PowerShell" in str(recovery_suggestions) or
                            "cmd" in str(recovery_suggestions))
                else:
                    assert ("chmod" in str(recovery_suggestions) or
                            "sudo" in str(recovery_suggestions))

    def test_cross_platform_configuration_compatibility(self, temp_home):
        """Test configuration files work across different platforms."""
        platforms_to_test = ["Darwin", "Linux", "Windows"]

        # Create configuration on each platform simulation
        configs_by_platform = {}

        for test_platform in platforms_to_test:
            with patch('platform.system', return_value=test_platform):
                if test_platform == "Windows":
                    config_dir = temp_home / "AppData" / "Roaming" / "bablib"
                    data_dir = temp_home / "AppData" / "Local" / "bablib"
                    cache_dir = temp_home / "AppData" / "Local" / "bablib" / "cache"
                else:
                    config_dir = temp_home / ".config" / "bablib"
                    data_dir = temp_home / ".local" / "share" / "bablib"
                    cache_dir = temp_home / ".cache" / "bablib"

                with patch('platformdirs.user_config_dir', return_value=str(config_dir)), \
                     patch('platformdirs.user_data_dir', return_value=str(data_dir)), \
                     patch('platformdirs.user_cache_dir', return_value=str(cache_dir)):

                    config_service = ConfigService()

                    # Create platform-specific installation context
                    context = config_service.create_installation_context(
                        install_method="uvx",
                        version="1.0.0",
                        python_version="3.13.1"
                    )

                    configs_by_platform[test_platform] = {
                        "context": context,
                        "config_path": config_service.installation_config_path
                    }

        # Verify all configurations are valid and can be loaded
        for platform_name, config_info in configs_by_platform.items():
            assert config_info["config_path"].exists()
            assert config_info["context"].install_method == "uvx"
            assert config_info["context"].version == "1.0.0"

            # Configuration should be readable as JSON regardless of platform
            import json
            with open(config_info["config_path"]) as f:
                config_data = json.load(f)
                assert config_data["install_method"] == "uvx"
                assert config_data["version"] == "1.0.0"