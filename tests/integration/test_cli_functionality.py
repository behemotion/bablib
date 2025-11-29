"""Integration test for CLI functionality after installation."""

import pytest
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.package.fixtures import (
    build_wheel,
    install_wheel_in_temp_env,
    test_cli_command,
    cleanup_installation
)


class TestCLIFunctionality:
    """Integration tests for CLI functionality after installation."""

    def setup_method(self):
        """Clean up before each test."""
        cleanup_installation()

    def teardown_method(self):
        """Clean up after each test."""
        cleanup_installation()

    def test_bablib_help_command_works(self):
        """Test that bablib --help works without import errors."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test help command
        help_result = test_cli_command(["bablib", "--help"])

        # Should execute successfully
        assert help_result.returncode == 0, \
            f"bablib --help failed. stderr: {help_result.stderr}, stdout: {help_result.stdout}"

        # Should not have import errors
        assert "ModuleNotFoundError" not in help_result.stderr, \
            f"Import error in help command: {help_result.stderr}"

        assert "No module named 'src.lib'" not in help_result.stderr, \
            f"Missing src.lib module in help command: {help_result.stderr}"

        # Should show expected help content
        assert "Usage:" in help_result.stdout or "usage:" in help_result.stdout.lower(), \
            f"Help output doesn't contain usage information: {help_result.stdout}"

    def test_bablib_version_command_works(self):
        """Test that bablib --version works without import errors."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test version command
        version_result = test_cli_command(["bablib", "--version"])

        # Should execute successfully
        assert version_result.returncode == 0, \
            f"bablib --version failed. stderr: {version_result.stderr}, stdout: {version_result.stdout}"

        # Should not have import errors
        assert "ModuleNotFoundError" not in version_result.stderr, \
            f"Import error in version command: {version_result.stderr}"

        # Should show version information
        output = version_result.stdout + version_result.stderr
        assert any(char.isdigit() for char in output), \
            f"Version output doesn't contain version number: {output}"

    def test_all_cli_imports_successful(self):
        """Test that CLI can import all required modules after installation."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test that we can run any command without import errors
        # Use --help as it's the safest command that loads all imports
        help_result = test_cli_command(["bablib", "--help"])

        # Common import error patterns
        error_patterns = [
            "ModuleNotFoundError",
            "ImportError",
            "No module named",
            "cannot import name",
            "circular import"
        ]

        error_output = help_result.stderr + help_result.stdout

        for pattern in error_patterns:
            assert pattern not in error_output, \
                f"Import error pattern '{pattern}' found in CLI output: {error_output}"

        # Should complete successfully (return code 0) or at least not crash with import error
        assert help_result.returncode == 0 or "usage" in help_result.stdout.lower(), \
            f"CLI failed to execute properly. Return code: {help_result.returncode}, Output: {error_output}"