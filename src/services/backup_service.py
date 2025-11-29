"""Backup service for creating pre-uninstall backups."""

import json
import os
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.lib_logger import get_logger
from src.models.backup_manifest import BackupManifest
from src.models.component_status import ComponentStatus

logger = get_logger(__name__)


class BackupService:
    """Handles backup creation before uninstall."""

    def __init__(self):
        """Initialize the backup service."""
        self.temp_dir = Path('/tmp/bablib-backup-temp')

    async def create_backup(
        self,
        components: dict[str, Any],
        path: Path | None = None,
        bablib_version: str = "1.0.0"
    ) -> dict[str, Any]:
        """Create a backup archive of all components."""
        # Use default path if not specified
        if path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = Path.home() / f"bablib-backup-{timestamp}.tar.gz"

        # Create manifest
        manifest = BackupManifest(bablib_version=bablib_version)

        try:
            # Create temporary directory for backup staging
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Backup directories
            total_size = 0
            file_count = 0

            for directory in components.get('directories', []):
                if isinstance(directory, ComponentStatus):
                    dir_path = directory.component_path
                elif isinstance(directory, Path):
                    dir_path = directory
                else:
                    continue

                if dir_path and dir_path.exists():
                    dir_size, dir_files = await self._backup_directory(dir_path)
                    total_size += dir_size
                    file_count += dir_files
                    manifest.add_component('directory')

            # Backup config files
            for config in components.get('configs', []):
                if isinstance(config, ComponentStatus):
                    config_path = config.component_path
                elif isinstance(config, Path):
                    config_path = config
                else:
                    continue

                if config_path and config_path.exists():
                    config_size = await self._backup_file(config_path)
                    total_size += config_size
                    file_count += 1

            # Export container configurations
            container_count = await self._export_container_configs(
                components.get('containers', [])
            )
            manifest.add_component('containers', container_count)

            # Note volumes (metadata only, not actual data)
            volume_count = len(components.get('volumes', []))
            if volume_count > 0:
                await self._export_volume_metadata(components['volumes'])
                manifest.add_component('volumes', volume_count)

            # Update manifest
            manifest.add_files(file_count, total_size)

            # Create compressed archive
            compressed_size = await self._create_archive(path, manifest)
            manifest.set_compression_stats(total_size, compressed_size)

            # Clean up temp directory
            shutil.rmtree(self.temp_dir, ignore_errors=True)

            logger.info(f"Backup created at {path} ({manifest.get_size_display()})")

            return {
                'path': path,
                'size_bytes': compressed_size,
                'file_count': file_count,
                'manifest': manifest.get_summary()
            }

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            # Clean up on failure
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            if path.exists():
                path.unlink()
            raise

    async def estimate_backup_size(self, components: dict[str, Any]) -> int:
        """Estimate the size of the backup before creation."""
        total_size = 0

        # Estimate directory sizes
        for directory in components.get('directories', []):
            if isinstance(directory, ComponentStatus):
                dir_path = directory.component_path
            elif isinstance(directory, Path):
                dir_path = directory
            else:
                continue

            if dir_path and dir_path.exists():
                total_size += await self._calculate_directory_size(dir_path)

        # Estimate config file sizes
        for config in components.get('configs', []):
            if isinstance(config, ComponentStatus):
                config_path = config.component_path
            elif isinstance(config, Path):
                config_path = config
            else:
                continue

            if config_path and config_path.exists():
                total_size += config_path.stat().st_size

        # Add estimate for container/volume metadata (usually small)
        total_size += 10240  # 10KB for metadata

        return total_size

    async def verify_backup(self, backup_path: Path) -> bool:
        """Verify backup archive integrity."""
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                # Check if manifest exists
                try:
                    manifest_info = tar.getmember('manifest.json')
                    if manifest_info.size == 0:
                        logger.error("Manifest is empty")
                        return False
                except KeyError:
                    logger.error("Manifest not found in backup")
                    return False

                # Verify archive is readable
                tar.getmembers()

            logger.info(f"Backup verified: {backup_path}")
            return True

        except (OSError, tarfile.TarError) as e:
            logger.error(f"Backup verification failed: {e}")
            return False

    async def _backup_directory(self, dir_path: Path) -> tuple[int, int]:
        """Backup a directory to the temp location."""
        dest_path = self.temp_dir / dir_path.name
        total_size = 0
        file_count = 0

        try:
            # Copy directory to temp location
            shutil.copytree(dir_path, dest_path, dirs_exist_ok=True)

            # Calculate size and count files
            for root, dirs, files in os.walk(dest_path):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.exists():
                        total_size += file_path.stat().st_size
                        file_count += 1

            logger.info(f"Backed up directory {dir_path.name}: {file_count} files")
            return total_size, file_count

        except (OSError, PermissionError) as e:
            logger.warning(f"Could not backup directory {dir_path}: {e}")
            return 0, 0

    async def _backup_file(self, file_path: Path) -> int:
        """Backup a single file to the temp location."""
        dest_path = self.temp_dir / 'configs' / file_path.name
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(file_path, dest_path)
            return file_path.stat().st_size
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not backup file {file_path}: {e}")
            return 0

    async def _export_container_configs(self, containers: list) -> int:
        """Export container configurations to JSON."""
        if not containers:
            return 0

        configs_path = self.temp_dir / 'container_configs.json'
        container_data = []

        for container in containers:
            if hasattr(container, '__dict__'):
                # ComponentStatus object
                container_data.append({
                    'name': container.component_name,
                    'type': 'container'
                })
            else:
                # Dictionary
                container_data.append(container)

        try:
            with open(configs_path, 'w') as f:
                json.dump(container_data, f, indent=2)
            return len(container_data)
        except Exception as e:
            logger.warning(f"Could not export container configs: {e}")
            return 0

    async def _export_volume_metadata(self, volumes: list) -> int:
        """Export volume metadata to JSON."""
        if not volumes:
            return 0

        metadata_path = self.temp_dir / 'volume_metadata.json'
        volume_data = []

        for volume in volumes:
            if hasattr(volume, '__dict__'):
                # ComponentStatus object
                volume_data.append({
                    'name': volume.component_name,
                    'external': volume.is_external
                })
            else:
                # Dictionary
                volume_data.append(volume)

        try:
            with open(metadata_path, 'w') as f:
                json.dump(volume_data, f, indent=2)
            return len(volume_data)
        except Exception as e:
            logger.warning(f"Could not export volume metadata: {e}")
            return 0

    async def _create_archive(self, archive_path: Path, manifest: BackupManifest) -> int:
        """Create compressed tar archive from temp directory."""
        # Save manifest
        manifest_path = self.temp_dir / 'manifest.json'
        with open(manifest_path, 'w') as f:
            f.write(manifest.to_json_string())

        # Create tar.gz archive
        with tarfile.open(archive_path, 'w:gz') as tar:
            for item in self.temp_dir.iterdir():
                tar.add(item, arcname=item.name)

        # Return compressed size
        return archive_path.stat().st_size

    async def _calculate_directory_size(self, path: Path) -> int:
        """Calculate total size of a directory."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.exists():
                        total_size += filepath.stat().st_size
        except (OSError, PermissionError):
            pass
        return total_size
