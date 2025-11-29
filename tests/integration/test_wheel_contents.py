"""Integration test for wheel content inspection."""

import pytest
from pathlib import Path
import sys
import os

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.package.fixtures import build_wheel, inspect_wheel_contents


class TestWheelContents:
    """Integration tests for wheel content validation."""

    def test_wheel_includes_complete_source_tree(self):
        """Test that wheel includes complete source directory structure."""
        project_dir = Path(__file__).parent.parent.parent

        # Build wheel
        wheel_path = build_wheel(project_dir)

        # Get all contents
        contents = inspect_wheel_contents(wheel_path)

        # Define expected source structure
        expected_structure = {
            "src/__init__.py",
            "src/cli/__init__.py",
            "src/cli/main.py",
            "src/lib/__init__.py",
            "src/lib/config.py",
            "src/lib/docker_utils.py",
            "src/lib/logger.py",  # Renamed from logging.py
            "src/models/__init__.py",
            "src/services/__init__.py"
        }

        # Check each expected file
        for expected_file in expected_structure:
            found = any(expected_file in content for content in contents)
            assert found, f"Missing expected file {expected_file} in wheel. Contents: {contents}"

    def test_wheel_excludes_problematic_files(self):
        """Test that wheel excludes files that cause import conflicts."""
        project_dir = Path(__file__).parent.parent.parent

        # Build wheel
        wheel_path = build_wheel(project_dir)

        # Get all contents
        contents = inspect_wheel_contents(wheel_path)

        # Files that should NOT be in the wheel
        excluded_files = [
            "src/lib/logging.py",  # Should be renamed to logger.py
        ]

        for excluded_file in excluded_files:
            found = any(excluded_file in content for content in contents)
            assert not found, f"Found problematic file {excluded_file} in wheel - it should be excluded/renamed"

    def test_wheel_metadata_consistency(self):
        """Test that wheel metadata is consistent with package configuration."""
        project_dir = Path(__file__).parent.parent.parent

        # Build wheel
        wheel_path = build_wheel(project_dir)

        # Check wheel filename pattern
        assert wheel_path.name.startswith("bablib-"), \
            f"Wheel filename doesn't start with 'bablib-': {wheel_path.name}"

        assert wheel_path.name.endswith(".whl"), \
            f"Wheel file doesn't have .whl extension: {wheel_path.name}"

        # Get contents to check metadata
        contents = inspect_wheel_contents(wheel_path)

        # Should have dist-info metadata
        metadata_files = [content for content in contents if ".dist-info/" in content]
        assert metadata_files, f"No .dist-info metadata found in wheel. Contents: {contents}"

        # Should have entry points
        entry_points = [content for content in contents if "entry_points.txt" in content]
        assert entry_points, f"No entry_points.txt found in wheel metadata"