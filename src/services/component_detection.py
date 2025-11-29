"""Component detection service for identifying Bablib components to remove."""

import os
import subprocess
from pathlib import Path
from typing import Any

import docker.errors

import docker
from src.core.lib_logger import get_logger
from src.models.component_status import ComponentStatus, ComponentType, RemovalStatus

logger = get_logger(__name__)


class ComponentDetectionService:
    """Service for detecting Bablib components on the system."""

    def __init__(self, docker_client: docker.DockerClient | None = None):
        """Initialize the detection service."""
        self.docker_client = docker_client
        self._init_docker_client()

    def _init_docker_client(self) -> None:
        """Initialize Docker client if not provided."""
        if self.docker_client is None:
            try:
                # Try auto version negotiation first
                self.docker_client = docker.from_env(version='auto')
            except docker.errors.DockerException as e:
                # If auto fails, try with explicit version
                if "api version" in str(e).lower() or "500" in str(e):
                    try:
                        import os
                        # Try with older API version
                        os.environ['DOCKER_API_VERSION'] = '1.41'
                        self.docker_client = docker.from_env()
                        os.environ.pop('DOCKER_API_VERSION', None)
                        logger.info("Connected to Docker using API v1.41")
                    except docker.errors.DockerException:
                        logger.warning(f"Docker not available even with compatibility mode: {e}")
                        self.docker_client = None
                else:
                    logger.warning(f"Docker not available: {e}")
                    self.docker_client = None

    async def detect_all_components(self) -> dict[str, Any]:
        """Detect all Bablib components on the system."""
        components = {
            'containers': await self.find_docker_containers(),
            'volumes': await self.find_docker_volumes(),
            'directories': await self.find_data_directories(),
            'configs': await self.find_config_files(),
            'package': await self.check_package_installation()
        }
        return components

    async def find_docker_containers(self) -> list[ComponentStatus]:
        """Find Bablib Docker containers."""
        if not self.docker_client:
            return []

        containers = []
        try:
            all_containers = self.docker_client.containers.list(all=True)
            for container in all_containers:
                # Check if it's a Bablib container by name or label
                if self._is_bablib_container(container):
                    containers.append(ComponentStatus(
                        component_type=ComponentType.CONTAINER,
                        component_name=container.name,
                        status=RemovalStatus.PENDING
                    ))
        except docker.errors.DockerException as e:
            logger.error(f"Error listing containers: {e}")

        return containers

    async def find_docker_volumes(self) -> list[ComponentStatus]:
        """Find Bablib Docker volumes."""
        if not self.docker_client:
            return []

        volumes = []
        try:
            all_volumes = self.docker_client.volumes.list()
            for volume in all_volumes:
                if self._is_bablib_volume(volume):
                    volumes.append(ComponentStatus(
                        component_type=ComponentType.VOLUME,
                        component_name=volume.name,
                        status=RemovalStatus.PENDING,
                        is_external=self._is_external_volume(volume)
                    ))
        except docker.errors.DockerException as e:
            logger.error(f"Error listing volumes: {e}")

        return volumes

    async def find_data_directories(self) -> list[ComponentStatus]:
        """Find Bablib data directories."""
        directories = []

        # Standard XDG directories
        paths_to_check = [
            Path.home() / '.config' / 'bablib',
            Path.home() / '.local' / 'share' / 'bablib',
            Path.home() / '.cache' / 'bablib',
        ]

        # Also check for project-specific directories
        data_dir = Path.home() / '.local' / 'share' / 'bablib'
        if data_dir.exists():
            # Check for projects directory
            projects_dir = data_dir / 'projects'
            if projects_dir.exists() and projects_dir not in paths_to_check:
                paths_to_check.append(projects_dir)

        # Check environment variables for custom paths
        if 'BABLIB_DATABASE_PATH' in os.environ:
            custom_path = Path(os.environ['BABLIB_DATABASE_PATH']).parent
            if custom_path not in paths_to_check:
                paths_to_check.append(custom_path)

        if 'BABLIB_DATA_DIR' in os.environ:
            paths_to_check.append(Path(os.environ['BABLIB_DATA_DIR']))

        for path in paths_to_check:
            if path.exists() and path.is_dir():
                size = await self.calculate_directory_size(path)
                directories.append(ComponentStatus(
                    component_type=ComponentType.DIRECTORY,
                    component_name=f"Directory: {path.name}",
                    component_path=path,
                    size_bytes=size,
                    status=RemovalStatus.PENDING
                ))

        return directories

    async def find_config_files(self) -> list[ComponentStatus]:
        """Find Bablib configuration files."""
        configs = []

        config_patterns = [
            '*.yaml', '*.yml', '*.json', '*.toml', '*.ini', '*.conf'
        ]

        config_dir = Path.home() / '.config' / 'bablib'
        if config_dir.exists():
            for pattern in config_patterns:
                for config_file in config_dir.glob(pattern):
                    configs.append(ComponentStatus(
                        component_type=ComponentType.CONFIG,
                        component_name=f"Config: {config_file.name}",
                        component_path=config_file,
                        size_bytes=config_file.stat().st_size if config_file.exists() else 0,
                        status=RemovalStatus.PENDING
                    ))

        return configs

    async def check_package_installation(self) -> ComponentStatus | None:
        """Check if Bablib package is installed."""
        try:
            # Check with UV tool
            result = subprocess.run(
                ['uv', 'tool', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and 'bablib' in result.stdout.lower():
                return ComponentStatus(
                    component_type=ComponentType.PACKAGE,
                    component_name='bablib',
                    status=RemovalStatus.PENDING
                )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.warning(f"Could not check package installation: {e}")

        return None

    async def calculate_directory_size(self, path: Path) -> int:
        """Calculate total size of a directory."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.exists():
                        total_size += filepath.stat().st_size
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not calculate size for {path}: {e}")

        return total_size

    def _is_bablib_container(self, container) -> bool:
        """Check if container is managed by Bablib."""
        # Check by label
        if container.labels.get('bablib.managed') == 'true':
            return True

        # Check by name pattern
        if container.name.startswith('bablib-'):
            return True

        return False

    def _is_bablib_volume(self, volume) -> bool:
        """Check if volume is managed by Bablib."""
        # Check by label
        if volume.attrs.get('Labels', {}).get('bablib.managed') == 'true':
            return True

        # Check by name pattern
        if self.is_bablib_volume_name(volume.name):
            return True

        return False

    def is_bablib_volume_name(self, name: str) -> bool:
        """Check if volume name matches Bablib pattern."""
        return name.startswith('bablib_') or name.startswith('bablib-')

    def _is_external_volume(self, volume) -> bool:
        """Check if volume is external (not managed by Bablib)."""
        # Check explicit external label
        if volume.attrs.get('Labels', {}).get('external') == 'true':
            return True

        # Check mount point
        mountpoint = volume.attrs.get('Mountpoint', '')
        if mountpoint and not mountpoint.startswith('/var/lib/docker/volumes/'):
            return True

        return False

    async def estimate_volume_size(self, volume_info) -> int:
        """Estimate the size of a Docker volume."""
        mountpoint = volume_info.attrs.get('Mountpoint')
        if not mountpoint or not os.path.exists(mountpoint):
            return 0

        try:
            stat = os.statvfs(mountpoint)
            # Used space = (total - available) * block_size
            used_blocks = stat.f_blocks - stat.f_bavail
            return used_blocks * stat.f_frsize
        except OSError:
            return 0

    async def extract_volume_metadata(self, volume) -> dict:
        """Extract metadata from a Docker volume."""
        return {
            'name': volume.name,
            'driver': volume.attrs.get('Driver', 'unknown'),
            'managed': self._is_bablib_volume(volume),
            'version': volume.attrs.get('Labels', {}).get('version'),
            'created_at': volume.attrs.get('CreatedAt')
        }

    async def filter_removable_volumes(self, volumes: list) -> list:
        """Filter volumes to get only removable ones."""
        removable = []
        for volume in volumes:
            if not self._is_external_volume(volume) and self._is_bablib_volume(volume):
                removable.append(volume)
        return removable
