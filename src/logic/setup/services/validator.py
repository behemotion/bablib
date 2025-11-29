"""System validation service."""

import platform
import sys
from pathlib import Path
from typing import Any

import psutil

from src.core.lib_logger import get_logger

logger = get_logger(__name__)


class SetupValidator:
    """Service for validating system requirements."""

    def __init__(self):
        """Initialize the validator."""
        self.min_python_version = (3, 13, 0)
        self.min_memory_gb = 4.0
        self.min_disk_gb = 2.0

    def validate_system(self) -> dict[str, Any]:
        """Validate all system requirements.

        Returns:
            Validation results dictionary
        """
        results = {
            "valid": True,
            "checks": {},
            "warnings": [],
            "errors": []
        }

        # Check Python version
        python_check = self.check_python_version()
        results["checks"]["python_version"] = python_check
        if not python_check["valid"]:
            results["errors"].append(python_check["message"])
            results["valid"] = False

        # Check memory
        memory_check = self.check_memory()
        results["checks"]["memory"] = memory_check
        if not memory_check["valid"]:
            results["errors"].append(memory_check["message"])
            results["valid"] = False

        # Check disk space
        disk_check = self.check_disk_space()
        results["checks"]["disk_space"] = disk_check
        if not disk_check["valid"]:
            results["errors"].append(disk_check["message"])
            results["valid"] = False

        # Check platform
        platform_check = self.check_platform()
        results["checks"]["platform"] = platform_check
        if platform_check.get("warning"):
            results["warnings"].append(platform_check["message"])

        # Check optional dependencies
        uv_check = self.check_uv_installed()
        results["checks"]["uv"] = uv_check
        if not uv_check["valid"]:
            results["warnings"].append(uv_check["message"])

        # Summary
        results["python_version"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        results["memory_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        results["disk_gb"] = round(psutil.disk_usage(str(Path.home())).free / (1024**3), 1)
        results["platform"] = platform.system()

        return results

    def check_python_version(self) -> dict[str, Any]:
        """Check Python version requirement.

        Returns:
            Check result
        """
        current = sys.version_info[:3]
        valid = current >= self.min_python_version

        return {
            "valid": valid,
            "current": f"{current[0]}.{current[1]}.{current[2]}",
            "required": f"{self.min_python_version[0]}.{self.min_python_version[1]}+",
            "message": (
                f"Python {current[0]}.{current[1]}.{current[2]} detected"
                if valid else
                f"Python {self.min_python_version[0]}.{self.min_python_version[1]}+ required, "
                f"found {current[0]}.{current[1]}.{current[2]}"
            )
        }

    def check_memory(self) -> dict[str, Any]:
        """Check available memory.

        Returns:
            Check result
        """
        memory_gb = psutil.virtual_memory().total / (1024**3)
        valid = memory_gb >= self.min_memory_gb

        return {
            "valid": valid,
            "current_gb": round(memory_gb, 1),
            "required_gb": self.min_memory_gb,
            "message": (
                f"{round(memory_gb, 1)}GB RAM available"
                if valid else
                f"Insufficient memory: {round(memory_gb, 1)}GB available, "
                f"{self.min_memory_gb}GB required"
            )
        }

    def check_disk_space(self) -> dict[str, Any]:
        """Check available disk space.

        Returns:
            Check result
        """
        disk_free_gb = psutil.disk_usage(str(Path.home())).free / (1024**3)
        valid = disk_free_gb >= self.min_disk_gb

        return {
            "valid": valid,
            "current_gb": round(disk_free_gb, 1),
            "required_gb": self.min_disk_gb,
            "message": (
                f"{round(disk_free_gb, 1)}GB disk space available"
                if valid else
                f"Insufficient disk space: {round(disk_free_gb, 1)}GB available, "
                f"{self.min_disk_gb}GB required"
            )
        }

    def check_platform(self) -> dict[str, Any]:
        """Check platform compatibility.

        Returns:
            Check result
        """
        system = platform.system()
        supported = ["Linux", "Darwin", "Windows"]
        valid = system in supported

        result = {
            "valid": valid,
            "platform": system,
            "supported": supported,
            "message": f"Platform: {system}"
        }

        if system == "Windows":
            result["warning"] = True
            result["message"] += " (Limited support on Windows)"

        return result

    def check_uv_installed(self) -> dict[str, Any]:
        """Check if UV is installed.

        Returns:
            Check result
        """
        import shutil

        uv_path = shutil.which("uv")
        valid = uv_path is not None

        return {
            "valid": valid,
            "installed": valid,
            "path": uv_path,
            "message": (
                f"UV found at {uv_path}"
                if valid else
                "UV not found. Install from: https://github.com/astral-sh/uv"
            )
        }

    def check_write_permissions(self, path: Path) -> dict[str, Any]:
        """Check write permissions for a path.

        Args:
            path: Path to check

        Returns:
            Check result
        """
        try:
            # Try to create parent directories
            path.parent.mkdir(parents=True, exist_ok=True)

            # Try to write a test file
            test_file = path.parent / ".bablib_test"
            test_file.touch()
            test_file.unlink()

            return {
                "valid": True,
                "path": str(path),
                "message": f"Write permissions verified for {path.parent}"
            }
        except Exception as e:
            return {
                "valid": False,
                "path": str(path),
                "error": str(e),
                "message": f"No write permissions for {path.parent}: {e}"
            }
