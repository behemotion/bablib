"""Unit tests for uninstall models validation."""

import pytest
from pathlib import Path
from datetime import datetime
from pydantic import ValidationError
from src.models.uninstall_config import UninstallConfig
from src.models.component_status import ComponentStatus, ComponentType, RemovalStatus
from src.models.uninstall_progress import UninstallProgress
from src.models.removal_operation import RemovalOperation, OperationType
from src.models.backup_manifest import BackupManifest


class TestUninstallConfig:
    """Test UninstallConfig model validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = UninstallConfig()
        assert config.force is False
        assert config.backup is False
        assert config.backup_path is None
        assert config.verbose is False
        assert config.dry_run is False

    def test_config_with_backup(self, tmp_path):
        """Test configuration with backup enabled."""
        backup_path = tmp_path / "backup.tar.gz"
        backup_path.parent.mkdir(exist_ok=True)

        config = UninstallConfig(
            backup=True,
            backup_path=backup_path
        )
        assert config.backup is True
        assert config.backup_path == backup_path

    def test_invalid_backup_path(self):
        """Test validation error for non-existent backup path parent."""
        with pytest.raises(ValidationError) as exc_info:
            UninstallConfig(
                backup=True,
                backup_path=Path("/nonexistent/dir/backup.tar.gz")
            )
        assert "Parent directory does not exist" in str(exc_info.value)


class TestComponentStatus:
    """Test ComponentStatus model and state machine."""

    def test_component_creation(self):
        """Test component status creation."""
        component = ComponentStatus(
            component_type=ComponentType.CONTAINER,
            component_name="bablib-qdrant"
        )
        assert component.status == RemovalStatus.PENDING
        assert component.error_message is None
        assert component.is_external is False

    def test_state_transitions(self):
        """Test valid state transitions."""
        component = ComponentStatus(
            component_type=ComponentType.VOLUME,
            component_name="bablib_data"
        )

        # Valid transition: pending -> removing
        component.mark_as_removing()
        assert component.status == RemovalStatus.REMOVING

        # Valid transition: removing -> removed
        component.mark_as_removed()
        assert component.status == RemovalStatus.REMOVED
        assert component.is_terminal is True

    def test_invalid_state_transition(self):
        """Test invalid state transitions."""
        component = ComponentStatus(
            component_type=ComponentType.DIRECTORY,
            component_name="config_dir"
        )

        # Mark as removed
        component.status = RemovalStatus.REMOVED

        # Invalid transition: removed -> removing
        with pytest.raises(ValueError) as exc_info:
            component.transition_to(RemovalStatus.REMOVING)
        assert "Invalid status transition" in str(exc_info.value)

    def test_skip_with_reason(self):
        """Test skipping component with reason."""
        component = ComponentStatus(
            component_type=ComponentType.VOLUME,
            component_name="external_volume",
            is_external=True
        )

        component.mark_as_skipped("External volume")
        assert component.status == RemovalStatus.SKIPPED
        assert "External volume" in component.error_message


class TestUninstallProgress:
    """Test UninstallProgress tracking."""

    def test_progress_initialization(self):
        """Test progress tracker initialization."""
        progress = UninstallProgress()
        assert progress.total_components == 0
        assert progress.processed_components == 0
        assert progress.is_complete is True
        assert progress.success_rate == 0.0

    def test_progress_tracking(self):
        """Test progress increment operations."""
        progress = UninstallProgress(total_components=5)

        progress.increment_removed()
        progress.increment_removed()
        progress.increment_failed()
        progress.increment_skipped()

        assert progress.processed_components == 4
        assert progress.removed_components == 2
        assert progress.failed_components == 1
        assert progress.skipped_components == 1
        assert progress.is_complete is False
        assert progress.has_failures is True
        assert progress.is_partial_success is True

    def test_exit_codes(self):
        """Test exit code determination."""
        # No components
        progress = UninstallProgress()
        assert progress.get_exit_code() == 4

        # Complete success
        progress = UninstallProgress(total_components=3)
        progress.removed_components = 3
        assert progress.get_exit_code() == 0

        # Partial success
        progress = UninstallProgress(total_components=3)
        progress.removed_components = 2
        progress.failed_components = 1
        assert progress.get_exit_code() == 1

        # Complete failure
        progress = UninstallProgress(total_components=3)
        progress.failed_components = 3
        assert progress.get_exit_code() == 3


class TestRemovalOperation:
    """Test RemovalOperation queue model."""

    def test_operation_creation(self):
        """Test creation of removal operations."""
        op = RemovalOperation.create_stop_container("container123", "bablib-qdrant")
        assert op.operation_type == OperationType.STOP_CONTAINER
        assert op.target == "container123"
        assert op.priority == 10
        assert op.can_retry is True

    def test_operation_priorities(self):
        """Test operation priority ordering."""
        ops = [
            RemovalOperation.create_uninstall_package("bablib"),
            RemovalOperation.create_stop_container("c1", "container1"),
            RemovalOperation.create_remove_volume("volume1"),
            RemovalOperation.create_delete_directory("/path/to/dir"),
            RemovalOperation.create_remove_container("c1"),
        ]

        # Sort by priority
        ops.sort(key=lambda x: x.priority)

        # Check order
        assert ops[0].operation_type == OperationType.STOP_CONTAINER
        assert ops[1].operation_type == OperationType.REMOVE_CONTAINER
        assert ops[2].operation_type == OperationType.REMOVE_VOLUME
        assert ops[3].operation_type == OperationType.DELETE_DIRECTORY
        assert ops[4].operation_type == OperationType.UNINSTALL_PACKAGE

    def test_retry_logic(self):
        """Test retry count and logic."""
        op = RemovalOperation.create_remove_volume("test_volume")

        assert op.can_retry is True

        # Increment retries
        op.increment_retry()
        op.increment_retry()
        op.increment_retry()

        assert op.retry_count == 3
        assert op.can_retry is False  # Max retries reached

    def test_operation_dependencies(self):
        """Test operation dependencies."""
        stop_op = RemovalOperation.create_stop_container("c1", "container1")
        remove_op = RemovalOperation.create_remove_container("c1", stop_op.operation_id)

        assert stop_op.operation_id in remove_op.dependencies


class TestBackupManifest:
    """Test BackupManifest metadata model."""

    def test_manifest_creation(self):
        """Test backup manifest creation."""
        manifest = BackupManifest(bablib_version="1.0.0")
        assert manifest.bablib_version == "1.0.0"
        assert manifest.total_size_bytes == 0
        assert manifest.compression_ratio == 1.0
        assert manifest.backup_age_days >= 0

    def test_component_tracking(self):
        """Test adding components to manifest."""
        manifest = BackupManifest(bablib_version="1.0.0")

        manifest.add_component("containers", 3)
        manifest.add_component("volumes", 2)
        manifest.add_component("directory", 1)

        assert manifest.container_count == 3
        assert manifest.volume_count == 2
        assert manifest.directory_count == 1
        assert len(manifest.components_included) == 3

    def test_compression_stats(self):
        """Test compression statistics."""
        manifest = BackupManifest(bablib_version="1.0.0")

        manifest.set_compression_stats(
            original_size=1024 * 1024,  # 1MB
            compressed_size=512 * 1024   # 512KB
        )

        assert manifest.total_size_bytes == 1024 * 1024
        assert manifest.compression_ratio == 0.5
        assert manifest.compressed_size_bytes == 512 * 1024
        assert manifest.space_saved_bytes == 512 * 1024

    def test_manifest_serialization(self):
        """Test manifest JSON serialization."""
        manifest = BackupManifest(
            bablib_version="1.0.0",
            file_count=100,
            total_size_bytes=1024000
        )

        # Serialize to JSON
        json_str = manifest.to_json_string()
        assert "bablib_version" in json_str
        assert "1.0.0" in json_str

        # Deserialize from JSON
        restored = BackupManifest.from_json_string(json_str)
        assert restored.bablib_version == manifest.bablib_version
        assert restored.file_count == manifest.file_count

    def test_restore_validation(self):
        """Test backup restore validation."""
        # Fresh backup
        manifest = BackupManifest(
            bablib_version="1.0.0",
            file_count=10,
            container_count=2
        )
        valid, message = manifest.validate_restore()
        assert valid is True
        assert message is None

        # Old backup (simulate)
        manifest.created_at = datetime(2020, 1, 1)
        valid, message = manifest.validate_restore()
        assert valid is False
        assert "over 1 year old" in message

        # Empty backup
        manifest = BackupManifest(bablib_version="1.0.0")
        valid, message = manifest.validate_restore()
        assert valid is False
        assert "empty" in message