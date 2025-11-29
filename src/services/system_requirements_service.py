"""SystemRequirementsService for dependency validation (Python 3.13+, memory, disk)."""
import platform
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil

from src.core.lib_logger import get_logger
from src.models.installation_profile import SystemInfo

logger = get_logger(__name__)

# Try importing sqlite-vec for detection
try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    sqlite_vec = None
    SQLITE_VEC_AVAILABLE = False


class SystemRequirementsService:
    """Service for validating system requirements and dependencies."""

    def __init__(self):
        """Initialize system requirements service."""
        self.min_python_version = (3, 13)
        self.min_memory_gb = 4.0
        self.min_disk_gb = 2.0

    async def validate_all_requirements(self) -> dict[str, bool]:
        """Validate all system requirements."""
        results = {}

        try:
            # Python version validation
            results["python_version"] = self._validate_python_version()

            # Memory validation
            results["memory"] = self._validate_memory()

            # Disk space validation
            results["disk"] = self._validate_disk_space()

            # Docker availability
            results["docker"] = await self._validate_docker()

            # System architecture
            results["architecture"] = self._validate_architecture()

            # SQLite-vec availability
            results["sqlite_vec"] = self._validate_sqlite_vec()

            logger.info(f"System requirements validation completed: {results}")
            return results

        except Exception as e:
            logger.error(f"System requirements validation failed: {e}")
            return {"error": False}

    def _validate_python_version(self) -> bool:
        """Validate Python version is 3.13+."""
        try:
            current_version = sys.version_info[:2]
            is_valid = current_version >= self.min_python_version

            if is_valid:
                logger.info(f"Python version valid: {sys.version}")
            else:
                logger.warning(f"Python version {current_version} < required {self.min_python_version}")

            return is_valid

        except Exception as e:
            logger.error(f"Python version validation failed: {e}")
            return False

    def _validate_memory(self) -> bool:
        """Validate available memory is >= 4GB."""
        try:
            memory = psutil.virtual_memory()
            total_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)

            is_valid = total_gb >= self.min_memory_gb

            if is_valid:
                logger.info(f"Memory valid: {total_gb:.1f}GB total, {available_gb:.1f}GB available")
            else:
                logger.warning(f"Insufficient memory: {total_gb:.1f}GB < required {self.min_memory_gb}GB")

            return is_valid

        except Exception as e:
            logger.error(f"Memory validation failed: {e}")
            return False

    def _validate_disk_space(self, path: Path | None = None) -> bool:
        """Validate available disk space is >= 2GB."""
        try:
            # Use current directory or specified path
            check_path = path or Path.cwd()
            disk_usage = shutil.disk_usage(check_path)

            free_gb = disk_usage.free / (1024**3)
            total_gb = disk_usage.total / (1024**3)

            is_valid = free_gb >= self.min_disk_gb

            if is_valid:
                logger.info(f"Disk space valid: {free_gb:.1f}GB free of {total_gb:.1f}GB total")
            else:
                logger.warning(f"Insufficient disk space: {free_gb:.1f}GB < required {self.min_disk_gb}GB")

            return is_valid

        except Exception as e:
            logger.error(f"Disk space validation failed: {e}")
            return False

    async def _validate_docker(self) -> bool:
        """Validate Docker is available and running."""
        try:
            # Check if docker command exists
            docker_path = shutil.which("docker")
            if not docker_path:
                logger.warning("Docker command not found in PATH")
                return False

            # Check if Docker daemon is running
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.info("Docker is available and running")
                return True
            else:
                logger.warning(f"Docker daemon not running: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.warning("Docker validation timed out")
            return False
        except Exception as e:
            logger.error(f"Docker validation failed: {e}")
            return False

    def _validate_architecture(self) -> bool:
        """Validate system architecture compatibility."""
        try:
            arch = platform.machine().lower()
            supported_archs = ["x86_64", "amd64", "arm64", "aarch64"]

            is_valid = arch in supported_archs

            if is_valid:
                logger.info(f"Architecture supported: {arch}")
            else:
                logger.warning(f"Unsupported architecture: {arch}")

            return is_valid

        except Exception as e:
            logger.error(f"Architecture validation failed: {e}")
            return False

    def _validate_sqlite_vec(self) -> bool:
        """Validate SQLite-vec extension availability."""
        try:
            if not SQLITE_VEC_AVAILABLE:
                logger.info("SQLite-vec extension not installed")
                return False

            # Try to load the extension
            conn = sqlite3.connect(":memory:")
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            # Get version if available
            cursor = conn.execute("SELECT vec_version()")
            version = cursor.fetchone()[0]
            conn.close()

            logger.info(f"SQLite-vec extension available: version {version}")
            return True

        except Exception as e:
            error_msg = str(e)
            if "compiled without extension support" in error_msg or "enable_load_extension" in error_msg:
                logger.info(f"SQLite-vec unavailable: {error_msg}")
            else:
                logger.warning(f"SQLite-vec validation failed: {e}")
            return False

    def detect_sqlite_vec(self) -> tuple[bool, str]:
        """Detect SQLite-vec extension availability with detailed message."""
        if not SQLITE_VEC_AVAILABLE:
            return False, "sqlite-vec not installed. Run: uv pip install --system sqlite-vec"

        try:
            conn = sqlite3.connect(":memory:")
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            cursor = conn.execute("SELECT vec_version()")
            version = cursor.fetchone()[0]
            conn.close()

            return True, f"sqlite-vec {version} available"

        except Exception as e:
            return False, f"Failed to load sqlite-vec: {e}"

    def check_sqlite_version(self) -> tuple[bool, str]:
        """Check SQLite version compatibility for sqlite-vec."""
        try:
            version = sqlite3.sqlite_version_info

            if version >= (3, 41, 0):
                return True, f"SQLite {sqlite3.sqlite_version} is fully compatible"
            elif version >= (3, 37, 0):
                return True, f"SQLite {sqlite3.sqlite_version} is compatible with limited features"
            else:
                return False, f"SQLite {sqlite3.sqlite_version} is too old. Requires 3.37+"

        except Exception as e:
            return False, f"Failed to check SQLite version: {e}"

    def get_system_info(self) -> SystemInfo:
        """Get comprehensive system information."""
        try:
            # Basic system info
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)

            disk_usage = shutil.disk_usage(Path.cwd())
            disk_gb = disk_usage.free / (1024**3)

            # Create system info
            system_info = SystemInfo(
                python_version=python_version,
                memory_gb=memory_gb,
                disk_gb=disk_gb,
                architecture=platform.machine(),
                operating_system=platform.system(),
                os_version=platform.release(),
                docker_available=False  # Will be updated by async validation
            )

            return system_info

        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            # Return minimal system info
            return SystemInfo(
                python_version="unknown",
                memory_gb=0.0,
                disk_gb=0.0,
                architecture="unknown",
                operating_system=platform.system(),
                os_version="unknown",
                docker_available=False
            )

    def generate_requirements_report(self, validation_results: dict[str, bool]) -> dict[str, Any]:
        """Generate detailed requirements validation report."""
        try:
            system_info = self.get_system_info()

            report = {
                "timestamp": str(system_info.detection_timestamp),
                "system": {
                    "python_version": system_info.python_version,
                    "memory_gb": system_info.memory_gb,
                    "disk_gb": system_info.disk_gb,
                    "architecture": system_info.architecture,
                    "os": f"{system_info.operating_system} {system_info.os_version}",
                    "docker_available": validation_results.get("docker", False)
                },
                "requirements": {
                    "python_version": {
                        "required": f"{'.'.join(map(str, self.min_python_version))}+",
                        "current": system_info.python_version,
                        "passed": validation_results.get("python_version", False)
                    },
                    "memory": {
                        "required": f"{self.min_memory_gb}GB",
                        "current": f"{system_info.memory_gb:.1f}GB",
                        "passed": validation_results.get("memory", False)
                    },
                    "disk": {
                        "required": f"{self.min_disk_gb}GB",
                        "current": f"{system_info.disk_gb:.1f}GB",
                        "passed": validation_results.get("disk", False)
                    },
                    "docker": {
                        "required": "Available and running",
                        "current": "Available" if validation_results.get("docker", False) else "Not available",
                        "passed": validation_results.get("docker", False)
                    },
                    "architecture": {
                        "required": "x86_64, amd64, arm64, or aarch64",
                        "current": system_info.architecture,
                        "passed": validation_results.get("architecture", False)
                    }
                },
                "overall_passed": all(validation_results.values()) if validation_results else False,
                "failed_requirements": [
                    req for req, passed in validation_results.items()
                    if not passed and req != "error"
                ] if validation_results else []
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate requirements report: {e}")
            return {"error": f"Report generation failed: {e}"}

    def get_installation_recommendations(self, validation_results: dict[str, bool]) -> list[str]:
        """Get recommendations for failed requirements."""
        recommendations = []

        try:
            if not validation_results.get("python_version", True):
                recommendations.append(
                    f"Install Python {'.'.join(map(str, self.min_python_version))} or higher from python.org"
                )

            if not validation_results.get("memory", True):
                recommendations.append(
                    f"Ensure at least {self.min_memory_gb}GB of RAM is available"
                )

            if not validation_results.get("disk", True):
                recommendations.append(
                    f"Free up at least {self.min_disk_gb}GB of disk space"
                )

            if not validation_results.get("docker", True):
                recommendations.append(
                    "Install Docker Desktop or Docker Engine from docker.com"
                )

            if not validation_results.get("architecture", True):
                recommendations.append(
                    "Bablib requires x86_64/amd64 or arm64/aarch64 architecture"
                )

            return recommendations

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return ["Please check system requirements manually"]

    async def quick_validation(self) -> bool:
        """Quick validation for essential requirements only."""
        try:
            python_ok = self._validate_python_version()
            docker_ok = await self._validate_docker()

            return python_ok and docker_ok

        except Exception as e:
            logger.error(f"Quick validation failed: {e}")
            return False
