"""Setup uninstaller service."""

import os
import shutil
import stat
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.lib_logger import get_logger
from src.logic.setup.models.uninstall_manifest import UninstallManifest

logger = get_logger(__name__)


class SetupUninstaller:
    """Service for uninstalling Bablib."""

    def __init__(self, home_dir: Path | None = None):
        """Initialize the uninstaller.

        Args:
            home_dir: Optional home directory for testing
        """
        self.home_dir = home_dir or Path.home()
        self.config_dir = self.home_dir / ".config" / "bablib"
        self.data_dir = self.home_dir / ".local" / "share" / "bablib"
        self.cache_dir = self.home_dir / ".cache" / "bablib"

    def generate_manifest(self, preserve_data: bool = False) -> UninstallManifest:
        """Generate uninstall manifest.

        Args:
            preserve_data: Whether to preserve user data

        Returns:
            UninstallManifest with items to remove
        """
        manifest = UninstallManifest()

        # Add directories
        if self.config_dir.exists():
            manifest.add_directory(self.config_dir)

        if self.cache_dir.exists():
            manifest.add_directory(self.cache_dir)

        if self.data_dir.exists():
            if preserve_data:
                # Only remove non-project directories
                for item in self.data_dir.iterdir():
                    if item.name != "projects":
                        if item.is_dir():
                            manifest.add_directory(item)
                        else:
                            manifest.add_file(item)
            else:
                manifest.add_directory(self.data_dir)

        # Add specific files and directories if they exist
        potential_items = [
            self.home_dir / ".bablib",  # Legacy directory or config file
            Path("/usr/local/bin/bablib"),  # Symlink if exists
        ]

        for item_path in potential_items:
            if item_path.exists():
                if item_path.is_dir():
                    manifest.add_directory(item_path)
                else:
                    manifest.add_file(item_path)

        # Add config entries to clear
        manifest.add_config_entry("BABLIB_HOME")
        manifest.add_config_entry("BABLIB_CONFIG")

        return manifest

    def create_backup(self, manifest: UninstallManifest) -> Path:
        """Create backup of items to be removed.

        Args:
            manifest: Items to backup

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.home_dir / ".local" / "share" / "bablib_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_path = backup_dir / f"bablib_backup_{timestamp}.tar.gz"

        with tarfile.open(backup_path, "w:gz") as tar:
            for directory in manifest.directories:
                if directory.exists():
                    tar.add(directory, arcname=directory.name)

            for file_path in manifest.files:
                if file_path.exists():
                    tar.add(file_path, arcname=file_path.name)

        logger.info(f"Created backup at {backup_path}")
        manifest.backup_location = backup_path
        return backup_path

    def _remove_directory_robust(self, directory: Path) -> bool:
        """Robustly remove a directory, handling permissions and attributes.

        Args:
            directory: Directory to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            # First try standard removal
            shutil.rmtree(directory)
            return True
        except PermissionError:
            try:
                # Handle permission issues by changing permissions recursively
                def handle_remove_readonly(func, path, exc):
                    """Error handler for shutil.rmtree to handle readonly files."""
                    if os.path.exists(path):
                        # Make the file/directory writable and try again
                        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                        func(path)

                shutil.rmtree(directory, onerror=handle_remove_readonly)
                return True
            except Exception as e:
                logger.error(f"Failed to remove directory {directory} with permission fix: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to remove directory {directory}: {e}")
            return False

    def _remove_file_robust(self, file_path: Path) -> bool:
        """Robustly remove a file, handling permissions.

        Args:
            file_path: File to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path.unlink()
            return True
        except PermissionError:
            try:
                # Change permissions and try again
                os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                file_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to remove file {file_path} with permission fix: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to remove file {file_path}: {e}")
            return False

    def execute(
        self,
        manifest: UninstallManifest | None = None,
        force: bool = False
    ) -> dict[str, Any]:
        """Execute uninstallation.

        Args:
            manifest: Optional manifest, generates if not provided
            force: Force removal without checks

        Returns:
            Uninstall results
        """
        if not manifest:
            manifest = self.generate_manifest()

        results = {
            "removed": [],
            "failed": [],
            "status": "completed"
        }

        # Remove directories
        for directory in manifest.directories:
            if directory.exists():
                if self._remove_directory_robust(directory):
                    results["removed"].append(str(directory))
                    logger.debug(f"Removed directory: {directory}")
                else:
                    results["failed"].append(str(directory))
                    if not force:
                        results["status"] = "partial"

        # Remove files
        for file_path in manifest.files:
            if file_path.exists():
                if self._remove_file_robust(file_path):
                    results["removed"].append(str(file_path))
                    logger.debug(f"Removed file: {file_path}")
                else:
                    results["failed"].append(str(file_path))
                    if not force:
                        results["status"] = "partial"

        logger.info(f"Uninstall completed: {len(results['removed'])} items removed")
        return results
