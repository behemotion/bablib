"""System validator service for health checks."""

import platform
import sys

from ..models.category import HealthCategory
from ..models.health_check import HealthCheck
from ..models.status import HealthStatus
from ..models.system_info import SystemInfo


class SystemValidator:
    """Service for validating system requirements and environment."""

    def __init__(self):
        """Initialize system validator."""
        self.minimum_python_version = (3, 13)
        self.minimum_memory_gb = 1.0
        self.minimum_disk_gb = 1.0

    async def get_system_info(self) -> SystemInfo:
        """Get comprehensive system information."""
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Get UV version if available
        uv_version = await self._get_uv_version()

        # Get memory and disk information
        memory_gb = await self._get_available_memory_gb()
        disk_space_gb = await self._get_available_disk_gb()

        # Get platform
        platform_name = platform.system().lower()

        # Check if all requirements are met
        requirements_met = (
            self._check_python_version(python_version) and
            memory_gb >= self.minimum_memory_gb and
            disk_space_gb >= self.minimum_disk_gb
        )

        return SystemInfo(
            python_version=python_version,
            uv_version=uv_version,
            memory_gb=memory_gb,
            disk_space_gb=disk_space_gb,
            platform=platform_name,
            requirements_met=requirements_met
        )

    async def validate_python_version(self) -> HealthCheck:
        """Validate Python version meets requirements."""
        execution_start = self._get_current_time()

        try:
            version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            major, minor = sys.version_info.major, sys.version_info.minor

            if major > 3 or (major == 3 and minor >= 13):
                status = HealthStatus.HEALTHY
                message = f"Python {version} (requirement: 3.13+)"
                details = f"Running Python {version}"
                resolution = None
            else:
                status = HealthStatus.ERROR
                message = f"Python {version} is too old"
                details = f"Current: {version}, Required: 3.13+"
                resolution = "Upgrade to Python 3.13+ and reinstall Bablib with UV"

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="system.python_version",
                category=HealthCategory.SYSTEM,
                name="Python Version",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="system.python_version",
                category=HealthCategory.SYSTEM,
                name="Python Version",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check Python version",
                details=str(e),
                resolution="Ensure Python is properly installed and accessible",
                execution_time=execution_time
            )

    async def validate_memory_requirements(self) -> HealthCheck:
        """Validate system memory meets requirements."""
        execution_start = self._get_current_time()

        try:
            memory_gb = await self._get_available_memory_gb()

            if memory_gb >= self.minimum_memory_gb:
                status = HealthStatus.HEALTHY
                message = f"{memory_gb:.1f}GB available (requirement: {self.minimum_memory_gb}GB+)"
                details = f"Available memory: {memory_gb:.1f}GB"
                resolution = None
            elif memory_gb >= 0.5:
                status = HealthStatus.WARNING
                message = f"{memory_gb:.1f}GB available, below recommended {self.minimum_memory_gb}GB"
                details = f"Available: {memory_gb:.1f}GB, Recommended: {self.minimum_memory_gb}GB"
                resolution = "Consider closing other applications or adding more RAM"
            else:
                status = HealthStatus.ERROR
                message = f"Insufficient memory: {memory_gb:.1f}GB"
                details = f"Available: {memory_gb:.1f}GB, Minimum: 0.5GB"
                resolution = "Free up memory or add more RAM before using Bablib"

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="system.memory",
                category=HealthCategory.SYSTEM,
                name="Available Memory",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="system.memory",
                category=HealthCategory.SYSTEM,
                name="Available Memory",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check memory",
                details=str(e),
                resolution="Ensure system monitoring tools are available",
                execution_time=execution_time
            )

    async def validate_disk_space(self) -> HealthCheck:
        """Validate disk space meets requirements."""
        execution_start = self._get_current_time()

        try:
            disk_gb = await self._get_available_disk_gb()

            if disk_gb >= self.minimum_disk_gb:
                status = HealthStatus.HEALTHY
                message = f"{disk_gb:.1f}GB free (requirement: {self.minimum_disk_gb}GB+)"
                details = f"Available disk space: {disk_gb:.1f}GB"
                resolution = None
            elif disk_gb >= 0.5:
                status = HealthStatus.WARNING
                message = f"{disk_gb:.1f}GB free, below recommended {self.minimum_disk_gb}GB"
                details = f"Available: {disk_gb:.1f}GB, Recommended: {self.minimum_disk_gb}GB"
                resolution = "Free up disk space to ensure smooth operation"
            else:
                status = HealthStatus.ERROR
                message = f"Insufficient disk space: {disk_gb:.1f}GB"
                details = f"Available: {disk_gb:.1f}GB, Minimum: 0.5GB"
                resolution = "Free up disk space before using Bablib"

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="system.disk_space",
                category=HealthCategory.SYSTEM,
                name="Available Disk Space",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="system.disk_space",
                category=HealthCategory.SYSTEM,
                name="Available Disk Space",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check disk space",
                details=str(e),
                resolution="Ensure system monitoring tools are available",
                execution_time=execution_time
            )

    async def validate_uv_installation(self) -> HealthCheck:
        """Validate UV package manager is available."""
        execution_start = self._get_current_time()

        try:
            uv_version = await self._get_uv_version()

            if uv_version:
                status = HealthStatus.HEALTHY
                message = f"UV {uv_version} installed"
                details = f"UV version: {uv_version}"
                resolution = None
            else:
                status = HealthStatus.WARNING
                message = "UV not found or not accessible"
                details = "UV package manager is not in PATH"
                resolution = "Install UV: curl -LsSf https://astral.sh/uv/install.sh | sh"

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="system.uv_version",
                category=HealthCategory.SYSTEM,
                name="UV Package Manager",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="system.uv_version",
                category=HealthCategory.SYSTEM,
                name="UV Package Manager",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check UV installation",
                details=str(e),
                resolution="Ensure UV is properly installed and accessible",
                execution_time=execution_time
            )

    async def validate_all_system_requirements(self) -> list[HealthCheck]:
        """Validate all system requirements."""
        import asyncio

        # Run all system checks in parallel
        checks = await asyncio.gather(
            self.validate_python_version(),
            self.validate_memory_requirements(),
            self.validate_disk_space(),
            self.validate_uv_installation(),
            return_exceptions=True
        )

        # Filter out any exceptions and convert to HealthCheck objects
        valid_checks = []
        for check in checks:
            if isinstance(check, HealthCheck):
                valid_checks.append(check)
            elif isinstance(check, Exception):
                # Create error health check for failed validation
                valid_checks.append(HealthCheck(
                    id="system.unknown_error",
                    category=HealthCategory.SYSTEM,
                    name="System Validation Error",
                    status=HealthStatus.ERROR,
                    message="System validation failed",
                    details=str(check),
                    resolution="Check system configuration and try again",
                    execution_time=0.0
                ))

        return valid_checks

    def _check_python_version(self, version_str: str) -> bool:
        """Check if Python version meets minimum requirement."""
        try:
            major, minor = version_str.split('.')[:2]
            return int(major) > 3 or (int(major) == 3 and int(minor) >= 13)
        except (ValueError, IndexError):
            return False

    async def _get_uv_version(self) -> str | None:
        """Get UV version if available."""
        import asyncio

        try:
            process = await asyncio.create_subprocess_exec(
                'uv', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()

            if process.returncode == 0:
                output = stdout.decode().strip()
                # Extract version from "uv 0.1.23" format
                if ' ' in output:
                    return output.split(' ', 1)[1]
                return output
            return None

        except (TimeoutError, FileNotFoundError):
            return None
        except Exception:
            return None

    async def _get_available_memory_gb(self) -> float:
        """Get available memory in GB."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.available / (1024 ** 3)  # Convert bytes to GB
        except ImportError:
            # Fallback for systems without psutil
            return 2.0  # Assume 2GB if we can't detect
        except Exception:
            return 2.0

    async def _get_available_disk_gb(self) -> float:
        """Get available disk space in GB."""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            return disk.free / (1024 ** 3)  # Convert bytes to GB
        except ImportError:
            # Fallback for systems without psutil
            return 5.0  # Assume 5GB if we can't detect
        except Exception:
            return 5.0

    def _get_current_time(self) -> float:
        """Get current time for execution timing."""
        import time
        return time.time()
