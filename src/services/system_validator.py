"""System requirements validation service.

This service validates the current system against Bablib's installation requirements.
It provides async methods to check Python version, memory, disk space, platform support,
and UV availability. Returns SystemRequirements model instances with validation results.
"""

import asyncio
import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from packaging import version

from src.models.system_requirements import SystemRequirements

logger = logging.getLogger(__name__)


class SystemRequirementsService:
    """Service for validating system requirements for Bablib installation."""

    def __init__(self, timeout: int = 5):
        """Initialize the system requirements service.

        Args:
            timeout: Timeout in seconds for subprocess calls
        """
        self.timeout = timeout

    async def validate_system_requirements(self) -> SystemRequirements:
        """Validate all system requirements and return comprehensive status.

        Returns:
            SystemRequirements: Complete validation results

        Raises:
            Exception: If validation encounters unexpected errors
        """
        try:
            logger.info("Starting comprehensive system requirements validation")

            # Run all validation checks concurrently where possible
            python_version = self._get_python_version()
            python_valid = self._validate_python_version(python_version)

            memory_gb = self._get_available_memory_gb()
            memory_valid = memory_gb >= 4

            disk_gb = self._get_available_disk_gb()
            disk_valid = disk_gb >= 2

            platform_name = self._get_platform()
            platform_supported = self._is_platform_supported(platform_name)

            # UV check needs to run asynchronously
            uv_available, uv_version = await self._check_uv_availability()

            requirements = SystemRequirements(
                python_version=python_version,
                python_valid=python_valid,
                available_memory=memory_gb,
                memory_valid=memory_valid,
                available_disk=disk_gb,
                disk_valid=disk_valid,
                platform=platform_name,
                platform_supported=platform_supported,
                uv_available=uv_available,
                uv_version=uv_version
            )

            logger.info(f"System requirements validation completed: ready={requirements.is_system_ready()}")

            if not requirements.is_system_ready():
                missing = requirements.get_missing_requirements()
                logger.warning(f"System requirements not met: {missing}")

            return requirements

        except Exception as e:
            logger.error(f"System requirements validation failed: {e}")
            raise

    def _get_python_version(self) -> str:
        """Get current Python version as string.

        Returns:
            str: Python version in semantic version format (e.g., "3.13.1")
        """
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _validate_python_version(self, python_version: str) -> bool:
        """Validate Python version meets minimum requirement.

        Args:
            python_version: Python version string to validate

        Returns:
            bool: True if Python >= 3.13.0, False otherwise
        """
        try:
            current_version = version.Version(python_version)
            required_version = version.Version("3.13.0")
            return current_version >= required_version
        except version.InvalidVersion:
            logger.error(f"Invalid Python version format: {python_version}")
            return False

    def _get_available_memory_gb(self) -> int:
        """Get available system memory in GB.

        Returns:
            int: Available memory in GB (rounded down)
        """
        try:
            system_name = platform.system().lower()

            if system_name == "linux":
                # Read /proc/meminfo for Linux
                return self._get_linux_memory()
            elif system_name == "darwin":
                # Use vm_stat for macOS
                return self._get_darwin_memory()
            elif system_name == "windows":
                # Use wmic for Windows
                return self._get_windows_memory()
            else:
                logger.warning(f"Memory detection not implemented for platform: {system_name}")
                # Return a reasonable default for unsupported platforms
                return 8  # 8GB default assumption

        except Exception as e:
            logger.error(f"Failed to get memory info: {e}")
            # Return a reasonable default if detection fails
            return 8  # 8GB default assumption

    def _get_linux_memory(self) -> int:
        """Get available memory on Linux from /proc/meminfo."""
        try:
            with open('/proc/meminfo') as f:
                meminfo = f.read()

            # Parse MemAvailable (preferred) or calculate from MemFree + Buffers + Cached
            for line in meminfo.split('\n'):
                if line.startswith('MemAvailable:'):
                    # MemAvailable is in kB
                    mem_kb = int(line.split()[1])
                    return max(1, mem_kb // (1024 * 1024))  # Convert to GB, minimum 1GB

            # Fallback: parse individual components
            mem_free = mem_buffers = mem_cached = 0
            for line in meminfo.split('\n'):
                if line.startswith('MemFree:'):
                    mem_free = int(line.split()[1])
                elif line.startswith('Buffers:'):
                    mem_buffers = int(line.split()[1])
                elif line.startswith('Cached:'):
                    mem_cached = int(line.split()[1])

            # Approximate available memory
            available_kb = mem_free + mem_buffers + mem_cached
            return max(1, available_kb // (1024 * 1024))  # Convert to GB, minimum 1GB

        except Exception as e:
            logger.error(f"Failed to read Linux memory info: {e}")
            return 8  # Default assumption

    def _get_darwin_memory(self) -> int:
        """Get available memory on macOS using vm_stat."""
        try:
            result = subprocess.run(
                ['vm_stat'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                # Parse vm_stat output
                free_pages = inactive_pages = 0
                page_size = 4096  # Default page size

                for line in result.stdout.split('\n'):
                    if 'page size of' in line:
                        # Extract page size
                        page_size = int(line.split()[-2])
                    elif line.startswith('Pages free:'):
                        free_pages = int(line.split()[-1].rstrip('.'))
                    elif line.startswith('Pages inactive:'):
                        inactive_pages = int(line.split()[-1].rstrip('.'))

                # Calculate available memory (free + inactive pages)
                available_bytes = (free_pages + inactive_pages) * page_size
                return max(1, available_bytes // (1024 ** 3))  # Convert to GB, minimum 1GB
            else:
                logger.error(f"vm_stat command failed: {result.stderr}")
                return 8  # Default assumption

        except Exception as e:
            logger.error(f"Failed to get macOS memory info: {e}")
            return 8  # Default assumption

    def _get_windows_memory(self) -> int:
        """Get available memory on Windows using wmic."""
        try:
            result = subprocess.run(
                ['wmic', 'OS', 'get', 'FreePhysicalMemory', '/value'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                # Parse wmic output
                for line in result.stdout.split('\n'):
                    if line.startswith('FreePhysicalMemory='):
                        mem_kb = int(line.split('=')[1])
                        return max(1, mem_kb // (1024 * 1024))  # Convert to GB, minimum 1GB

            logger.error(f"wmic command failed: {result.stderr}")
            return 8  # Default assumption

        except Exception as e:
            logger.error(f"Failed to get Windows memory info: {e}")
            return 8  # Default assumption

    def _get_available_disk_gb(self, path: Path | None = None) -> int:
        """Get available disk space in GB.

        Args:
            path: Path to check disk space for (defaults to current directory)

        Returns:
            int: Available disk space in GB (rounded down)
        """
        try:
            check_path = path or Path.cwd()
            disk_usage = shutil.disk_usage(check_path)
            # Convert bytes to GB (rounded down)
            disk_gb = int(disk_usage.free / (1024 ** 3))
            logger.debug(f"Available disk space: {disk_gb}GB")
            return disk_gb
        except Exception as e:
            logger.error(f"Failed to get disk space info: {e}")
            # Return 0 to indicate no disk space available
            return 0

    def _get_platform(self) -> str:
        """Get current operating system platform.

        Returns:
            str: Platform name (darwin, linux, windows, or other)
        """
        system = platform.system()
        platform_map = {
            "Darwin": "darwin",
            "Linux": "linux",
            "Windows": "windows"
        }
        return platform_map.get(system, system.lower())

    def _is_platform_supported(self, platform_name: str) -> bool:
        """Check if platform is supported by Bablib.

        Args:
            platform_name: Platform name to check

        Returns:
            bool: True if platform is supported, False otherwise
        """
        supported_platforms = {"darwin", "linux", "windows"}
        return platform_name.lower() in supported_platforms

    async def _check_uv_availability(self) -> tuple[bool, str | None]:
        """Check if UV package manager is available and get version.

        Returns:
            tuple: (is_available: bool, version: Optional[str])
        """
        try:
            # Run UV version check in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_uv_version_command
            )

            if result is not None:
                logger.debug(f"UV available: {result}")
                return True, result
            else:
                logger.debug("UV not available")
                return False, None

        except Exception as e:
            logger.error(f"UV availability check failed: {e}")
            return False, None

    def _run_uv_version_command(self) -> str | None:
        """Run UV version command synchronously.

        Returns:
            Optional[str]: UV version string if available, None if not available
        """
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                # Parse version from output like "uv 0.8.9 (68c0bf8a2 2025-08-11)"
                output = result.stdout.strip()
                parts = output.split()
                if len(parts) >= 2:
                    # Take the second part which should be the version number
                    return parts[1]
                return output
            else:
                logger.debug(f"UV version command failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning("UV version command timed out")
            return None
        except FileNotFoundError:
            logger.debug("UV not found in PATH")
            return None
        except Exception as e:
            logger.error(f"UV version command error: {e}")
            return None

    async def check_python_requirements(self) -> tuple[bool, str]:
        """Check only Python version requirements.

        Returns:
            tuple: (is_valid: bool, version: str)
        """
        python_version = self._get_python_version()
        is_valid = self._validate_python_version(python_version)
        return is_valid, python_version

    async def check_memory_requirements(self) -> tuple[bool, int]:
        """Check only memory requirements.

        Returns:
            tuple: (is_valid: bool, available_memory_gb: int)
        """
        memory_gb = self._get_available_memory_gb()
        is_valid = memory_gb >= 4
        return is_valid, memory_gb

    async def check_disk_requirements(self, path: Path | None = None) -> tuple[bool, int]:
        """Check only disk space requirements.

        Args:
            path: Path to check disk space for

        Returns:
            tuple: (is_valid: bool, available_disk_gb: int)
        """
        disk_gb = self._get_available_disk_gb(path)
        is_valid = disk_gb >= 2
        return is_valid, disk_gb

    async def check_platform_requirements(self) -> tuple[bool, str]:
        """Check only platform support requirements.

        Returns:
            tuple: (is_supported: bool, platform: str)
        """
        platform_name = self._get_platform()
        is_supported = self._is_platform_supported(platform_name)
        return is_supported, platform_name

    async def check_uv_requirements(self) -> tuple[bool, str | None]:
        """Check only UV availability requirements.

        Returns:
            tuple: (is_available: bool, version: Optional[str])
        """
        return await self._check_uv_availability()

    def get_requirements_summary(self, requirements: SystemRequirements) -> dict:
        """Get a summary of requirements validation for display.

        Args:
            requirements: SystemRequirements instance

        Returns:
            dict: Summary information for display
        """
        return {
            "system_ready": requirements.is_system_ready(),
            "python": {
                "version": requirements.python_version,
                "valid": requirements.python_valid,
                "required": ">=3.13.0"
            },
            "memory": {
                "available_gb": requirements.available_memory,
                "valid": requirements.memory_valid,
                "required_gb": 4
            },
            "disk": {
                "available_gb": requirements.available_disk,
                "valid": requirements.disk_valid,
                "required_gb": 2
            },
            "platform": {
                "current": requirements.platform,
                "supported": requirements.platform_supported,
                "allowed": ["darwin", "linux", "windows"]
            },
            "uv": {
                "available": requirements.uv_available,
                "version": requirements.uv_version
            },
            "missing_requirements": requirements.get_missing_requirements()
        }
