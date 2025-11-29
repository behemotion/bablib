"""Reset handler service."""

from dataclasses import dataclass
from pathlib import Path

from src.core.lib_logger import get_logger
from src.logic.setup.services.configurator import SetupConfigurator
from src.logic.setup.services.initializer import SetupInitializer
from src.logic.setup.services.uninstaller import SetupUninstaller

logger = get_logger(__name__)


@dataclass
class ResetResult:
    """Result of a reset operation."""

    status: str
    backup_created: bool = False
    backup_path: Path | None = None
    warnings: list = None
    errors: list = None

    def __post_init__(self):
        """Initialize default values."""
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


class ResetHandler:
    """Handler for reset operations."""

    def __init__(self, home_dir: Path | None = None):
        """Initialize the reset handler.

        Args:
            home_dir: Optional home directory for testing
        """
        self.home_dir = home_dir or Path.home()
        self.initializer = SetupInitializer(home_dir=home_dir)
        self.uninstaller = SetupUninstaller(home_dir=home_dir)
        self.configurator = SetupConfigurator(home_dir=home_dir)

        # For state tracking
        self.on_state_change = None

    def execute(
        self,
        preserve_data: bool = False,
        vector_store: str | None = None,
        force: bool = False
    ) -> ResetResult:
        """Execute reset operation.

        Args:
            preserve_data: Whether to preserve user data
            vector_store: Vector store for new installation
            force: Skip confirmations

        Returns:
            ResetResult with operation details
        """
        result = ResetResult(status="pending")

        try:
            # Notify state change if handler is set
            if self.on_state_change:
                from src.logic.setup.models.operation import OperationStatus
                self.on_state_change(OperationStatus.PENDING)

            # Step 1: Create backup of current configuration
            logger.info("Creating backup of current configuration...")
            try:
                current_config = self.configurator.load_config()
                backup_manifest = self.uninstaller.generate_manifest(preserve_data=preserve_data)
                backup_path = self.uninstaller.create_backup(backup_manifest)
                result.backup_created = True
                result.backup_path = backup_path
            except FileNotFoundError:
                logger.warning("No existing configuration to backup")
                result.warnings.append("No existing configuration found")

            # Notify in progress
            if self.on_state_change:
                self.on_state_change(OperationStatus.IN_PROGRESS)

            # Step 2: Uninstall existing installation
            logger.info("Removing existing installation...")
            uninstall_manifest = self.uninstaller.generate_manifest(preserve_data=preserve_data)
            uninstall_result = self.uninstaller.execute(manifest=uninstall_manifest, force=True)

            if uninstall_result.get("failed"):
                result.warnings.append(f"Some items could not be removed: {uninstall_result['failed']}")

            # Step 3: Reinitialize with new configuration
            logger.info("Initializing fresh installation...")

            # Determine vector store
            if not vector_store and result.backup_created:
                # Try to use previous vector store
                vector_store = current_config.get("vector_store_provider", "sqlite_vec")

            init_result = self.initializer.execute(
                vector_store=vector_store or "sqlite_vec",
                auto=True
            )

            # Step 4: Save new configuration
            new_config = init_result["config"]
            new_config["vector_store_provider"] = vector_store or "sqlite_vec"
            self.configurator.save_config(new_config)

            # Mark as completed
            result.status = "completed"

            # Notify completion
            if self.on_state_change:
                self.on_state_change(OperationStatus.COMPLETED)

            logger.info("Reset completed successfully")

        except Exception as e:
            logger.error(f"Reset failed: {e}")
            result.status = "failed"
            result.errors.append(str(e))

            # Try to restore from backup if we have one
            if result.backup_created and result.backup_path:
                try:
                    logger.info("Attempting to restore from backup...")
                    self._restore_from_backup(result.backup_path)
                    result.warnings.append("Reset failed, restored from backup")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")
                    result.errors.append(f"Restore failed: {restore_error}")

            # Notify failure
            if self.on_state_change:
                from src.logic.setup.models.operation import OperationStatus
                self.on_state_change(OperationStatus.FAILED)

            raise

        return result

    def _restore_from_backup(self, backup_path: Path) -> None:
        """Restore from backup.

        Args:
            backup_path: Path to backup archive
        """
        import tarfile

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        # Extract backup to temporary location
        temp_dir = backup_path.parent / "restore_temp"
        temp_dir.mkdir(exist_ok=True)

        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            # Move restored files back
            # This is simplified - in production would need more careful handling
            for item in temp_dir.iterdir():
                if item.name == "bablib":
                    # Move config back
                    target = self.home_dir / ".config" / "bablib"
                    if item.is_dir():
                        import shutil
                        shutil.move(str(item), str(target))

            logger.info("Restored from backup successfully")

        finally:
            # Clean up temp directory
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
