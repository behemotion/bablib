"""
Test fixtures for package installation and CLI testing.
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Generator


def build_wheel() -> Path:
    """Build a wheel from the current project."""
    import os
    import sys

    # Get project root
    project_root = Path(__file__).parent.parent.parent

    # Build wheel using uv
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        cwd=project_root,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to build wheel: {result.stderr}")

    # Find the built wheel
    dist_dir = project_root / "dist"
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("No wheel found in dist directory")

    return wheels[-1]  # Return latest wheel


def install_wheel_in_temp_env(wheel_path: Path) -> Generator[Path, None, None]:
    """Install wheel in a temporary environment."""
    import venv
    import sys

    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = Path(temp_dir) / "test_env"

        # Create virtual environment
        venv.create(venv_path, with_pip=True)

        # Get Python executable in venv
        if sys.platform == "win32":
            python_exe = venv_path / "Scripts" / "python.exe"
        else:
            python_exe = venv_path / "bin" / "python"

        # Install wheel
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", str(wheel_path)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to install wheel: {result.stderr}")

        yield venv_path


def test_cli_command(venv_path: Path, command: list[str]) -> subprocess.CompletedProcess:
    """Test a CLI command in the given virtual environment."""
    import sys

    # Get Python executable in venv
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    # Run the command
    result = subprocess.run(
        [str(python_exe), "-m"] + command,
        capture_output=True,
        text=True
    )

    return result


def cleanup_installation(venv_path: Path) -> None:
    """Clean up the test installation."""
    if venv_path.exists():
        shutil.rmtree(venv_path)


def inspect_wheel_contents(wheel_path: Path) -> dict:
    """Inspect the contents of a wheel file."""
    import zipfile

    contents = {
        "files": [],
        "entry_points": {},
        "metadata": {}
    }

    with zipfile.ZipFile(wheel_path, 'r') as wheel:
        # Get file list
        contents["files"] = wheel.namelist()

        # Try to read entry points
        try:
            entry_points_text = wheel.read("bablib.dist-info/entry_points.txt").decode()
            contents["entry_points"] = entry_points_text
        except KeyError:
            pass

        # Try to read metadata
        try:
            metadata_text = wheel.read("bablib.dist-info/METADATA").decode()
            contents["metadata"] = metadata_text
        except KeyError:
            pass

    return contents