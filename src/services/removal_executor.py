"""Removal executor service for performing removal operations."""

import shutil
import subprocess
from pathlib import Path

import docker.errors

import docker
from src.core.lib_logger import get_logger

logger = get_logger(__name__)


class RemovalExecutor:
    """Executes individual removal operations."""

    def __init__(self, docker_client: docker.DockerClient | None = None):
        """Initialize the removal executor."""
        self.docker_client = docker_client
        self._init_docker_client()

    def _init_docker_client(self) -> None:
        """Initialize Docker client if not provided."""
        if self.docker_client is None:
            try:
                self.docker_client = docker.from_env()
            except docker.errors.DockerException as e:
                logger.warning(f"Docker not available: {e}")
                self.docker_client = None

    async def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a running container."""
        if not self.docker_client:
            logger.warning(f"Docker client not available - skipping container stop for {container_id}")
            return True  # Skip Docker operations when Docker is not available

        try:
            container = self.docker_client.containers.get(container_id)
            if container.status == 'running':
                logger.info(f"Stopping container {container_id}")
                container.stop(timeout=timeout)
            return True
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
            return True  # Already gone
        except docker.errors.APIError as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False

    async def remove_container(self, container_id: str, force: bool = False) -> bool:
        """Remove a container."""
        if not self.docker_client:
            logger.warning(f"Docker client not available - skipping container removal for {container_id}")
            return True  # Skip Docker operations when Docker is not available

        try:
            container = self.docker_client.containers.get(container_id)
            logger.info(f"Removing container {container_id}")
            container.remove(force=force)
            return True
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
            return True  # Already gone
        except docker.errors.APIError as e:
            logger.error(f"Failed to remove container {container_id}: {e}")
            return False

    async def remove_volume(self, volume_name: str, force: bool = False) -> bool:
        """Remove a volume."""
        if not self.docker_client:
            logger.warning(f"Docker client not available - skipping volume removal for {volume_name}")
            return True  # Skip Docker operations when Docker is not available

        try:
            volume = self.docker_client.volumes.get(volume_name)

            # Check if volume is external
            if await self.is_external_volume(volume):
                logger.info(f"Skipping external volume {volume_name}")
                return True

            # Check if volume is in use
            if await self.is_volume_in_use(volume_name):
                if not force:
                    logger.warning(f"Volume {volume_name} is in use")
                    return False

            logger.info(f"Removing volume {volume_name}")
            volume.remove(force=force)
            return True
        except docker.errors.NotFound:
            logger.warning(f"Volume {volume_name} not found")
            return True  # Already gone
        except docker.errors.APIError as e:
            logger.error(f"Failed to remove volume {volume_name}: {e}")
            return False

    async def delete_directory(self, path: Path) -> bool:
        """Delete a directory recursively."""
        try:
            if not path.exists():
                logger.warning(f"Directory {path} does not exist")
                return True

            if not path.is_dir():
                logger.error(f"Path {path} is not a directory")
                return False

            logger.info(f"Deleting directory {path}")
            shutil.rmtree(path, ignore_errors=False)
            return True
        except PermissionError as e:
            logger.error(f"Permission denied deleting {path}: {e}")
            return False
        except OSError as e:
            logger.error(f"Failed to delete directory {path}: {e}")
            return False

    async def delete_file(self, path: Path) -> bool:
        """Delete a single file."""
        try:
            if not path.exists():
                logger.warning(f"File {path} does not exist")
                return True

            if not path.is_file():
                logger.error(f"Path {path} is not a file")
                return False

            logger.info(f"Deleting file {path}")
            path.unlink()
            return True
        except PermissionError as e:
            logger.error(f"Permission denied deleting {path}: {e}")
            return False
        except OSError as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return False

    async def uninstall_package(self) -> bool:
        """Uninstall Bablib package using UV."""
        try:
            logger.info("Uninstalling Bablib package")
            result = subprocess.run(
                ['uv', 'tool', 'uninstall', 'bablib'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("Package uninstalled successfully")
                return True
            else:
                logger.error(f"Package uninstall failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("Package uninstall timed out")
            return False
        except FileNotFoundError:
            logger.error("UV tool not found")
            return False
        except Exception as e:
            logger.error(f"Failed to uninstall package: {e}")
            return False

    async def is_external_volume(self, volume) -> bool:
        """Check if volume is external (not managed by Bablib)."""
        # Check explicit external label
        if volume.attrs.get('Labels', {}).get('external') == 'true':
            return True

        # Check mount point
        mountpoint = volume.attrs.get('Mountpoint', '')
        if mountpoint and not mountpoint.startswith('/var/lib/docker/volumes/'):
            return True

        # Check if name doesn't match Bablib pattern
        if not (volume.name.startswith('bablib_') or volume.name.startswith('bablib-')):
            # Not a Bablib volume, treat as external
            return True

        return False

    async def is_volume_in_use(self, volume_name: str) -> bool:
        """Check if a volume is currently in use by any container."""
        if not self.docker_client:
            return False

        try:
            containers = self.docker_client.containers.list(all=True)
            for container in containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume' and mount.get('Name') == volume_name:
                        return True
        except docker.errors.APIError:
            return False

        return False

    async def should_preserve_volume(self, volume_name: str) -> bool:
        """Check if volume should be preserved (shared with non-Bablib containers)."""
        if not self.docker_client:
            return True  # Preserve by default if we can't check

        try:
            containers = self.docker_client.containers.list(all=True)
            non_bablib_using = False

            for container in containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume' and mount.get('Name') == volume_name:
                        if not container.name.startswith('bablib-'):
                            non_bablib_using = True

            # Preserve if used by non-Bablib containers
            return non_bablib_using
        except docker.errors.APIError:
            return True  # Preserve by default on error

    async def is_anonymous_volume(self, volume) -> bool:
        """Check if volume is anonymous (64-char hex name)."""
        import re
        # Anonymous volumes have 64 hexadecimal character names
        return bool(re.match(r'^[a-f0-9]{64}$', volume.name))

    async def filter_removable_volumes(self, volumes: list) -> list:
        """Filter volumes to get only removable ones."""
        removable = []
        for volume in volumes:
            # Skip external volumes
            if await self.is_external_volume(volume):
                continue

            # Skip volumes shared with non-Bablib containers
            if await self.should_preserve_volume(volume.name):
                continue

            # Include Bablib-managed volumes
            if volume.name.startswith('bablib_') or volume.name.startswith('bablib-'):
                removable.append(volume)

        return removable

    async def remove_container_with_retry(self, container_id: str, max_retries: int = 3) -> bool:
        """Remove container with retry logic."""
        for attempt in range(max_retries):
            # First try to stop
            if await self.stop_container(container_id):
                # Then try to remove
                if await self.remove_container(container_id):
                    return True

            if attempt < max_retries - 1:
                logger.info(f"Retrying container removal (attempt {attempt + 2}/{max_retries})")
                await self._sleep(2)  # Wait before retry

        return False

    async def _sleep(self, seconds: int) -> None:
        """Sleep for specified seconds (async compatible)."""
        import asyncio
        await asyncio.sleep(seconds)
