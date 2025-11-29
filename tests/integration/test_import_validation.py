"""Integration test for module import validation."""

import pytest
from pathlib import Path
import sys
import subprocess

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.package.fixtures import (
    build_wheel,
    install_wheel_in_temp_env,
    cleanup_installation
)


class TestImportValidation:
    """Integration tests for module import validation after installation."""

    def setup_method(self):
        """Clean up before each test."""
        cleanup_installation()

    def teardown_method(self):
        """Clean up after each test."""
        cleanup_installation()

    def test_entry_point_imports_work(self):
        """Test that entry point can import all required modules."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test that we can import the main CLI module
        import_test = subprocess.run([
            "python", "-c",
            "from src.cli.main import cli; print('Entry point import successful')"
        ], capture_output=True, text=True)

        assert import_test.returncode == 0, \
            f"Entry point import failed: {import_test.stderr}"

        assert "Entry point import successful" in import_test.stdout, \
            f"Import test didn't complete successfully: {import_test.stdout}"

    def test_lib_module_imports_work(self):
        """Test that lib module imports work correctly after installation."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test importing from the renamed logger module
        import_test = subprocess.run([
            "python", "-c",
            "from src.lib.logger import setup_logging, get_component_logger; print('Logger import successful')"
        ], capture_output=True, text=True)

        assert import_test.returncode == 0, \
            f"Logger module import failed: {import_test.stderr}"

        assert "Logger import successful" in import_test.stdout, \
            f"Logger import test didn't complete: {import_test.stdout}"

    def test_config_module_imports_work(self):
        """Test that config module imports work correctly after installation."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test importing config module
        import_test = subprocess.run([
            "python", "-c",
            "from src.lib.config import BablibConfig; print('Config import successful')"
        ], capture_output=True, text=True)

        assert import_test.returncode == 0, \
            f"Config module import failed: {import_test.stderr}"

        assert "Config import successful" in import_test.stdout, \
            f"Config import test didn't complete: {import_test.stdout}"

    def test_no_circular_imports(self):
        """Test that there are no circular import issues."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test importing the full lib package
        import_test = subprocess.run([
            "python", "-c",
            "import src.lib; print('Full lib package import successful')"
        ], capture_output=True, text=True)

        assert import_test.returncode == 0, \
            f"Full lib package import failed: {import_test.stderr}"

        # Check for circular import indicators
        assert "circular import" not in import_test.stderr.lower(), \
            f"Circular import detected: {import_test.stderr}"

        assert "Full lib package import successful" in import_test.stdout, \
            f"Full package import test didn't complete: {import_test.stdout}"

    def test_old_logging_module_not_importable(self):
        """Test that old logging module path is no longer accessible."""
        project_dir = Path(__file__).parent.parent.parent

        # Build and install
        wheel_path = build_wheel(project_dir)
        install_result = install_wheel_in_temp_env(wheel_path)

        assert install_result.returncode == 0, \
            f"Installation failed: {install_result.stderr}"

        # Test that old logging import path fails
        import_test = subprocess.run([
            "python", "-c",
            "from src.lib.logging import setup_logging; print('Old import worked - this should fail')"
        ], capture_output=True, text=True)

        # This SHOULD fail - we want the old import path to be unavailable
        assert import_test.returncode != 0, \
            f"Old logging import path should fail but succeeded: {import_test.stdout}"

        assert "ModuleNotFoundError" in import_test.stderr or "ImportError" in import_test.stderr, \
            f"Expected import error for old logging path: {import_test.stderr}"