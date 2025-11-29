"""Integration test for Bablib uninstall backup functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import tarfile
import tempfile
import json
from click.testing import CliRunner
from datetime import datetime


class TestUninstallBackup:
    """Test backup creation during uninstall process."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_installation(self, tmp_path):
        """Create a temporary installation with test data."""
        # Create directories
        config_dir = tmp_path / ".config" / "bablib"
        data_dir = tmp_path / ".local" / "share" / "bablib"
        cache_dir = tmp_path / ".cache" / "bablib"

        for dir_path in [config_dir, data_dir, cache_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Create test files with known content
        config_content = {"api_key": "test123", "port": 8765}
        (config_dir / "config.json").write_text(json.dumps(config_content))

        (data_dir / "bablib.db").write_bytes(b"SQLite test database content")
        (data_dir / "embeddings.idx").write_bytes(b"Vector embeddings index")

        (cache_dir / "temp.cache").write_text("temporary cache data")

        return {
            'config_dir': config_dir,
            'data_dir': data_dir,
            'cache_dir': cache_dir,
            'home': tmp_path,
            'config_content': config_content
        }

    @pytest.mark.asyncio
    async def test_backup_creation_with_default_path(self, cli_runner, temp_installation, tmp_path):
        """Test backup creation with default path."""
        from src.cli.main import cli

        backup_path = tmp_path / "bablib-backup.tar.gz"

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                    # Setup mocks
                    detection_instance = mock_detection.return_value
                    detection_instance.detect_all_components = AsyncMock(return_value={
                        'containers': [],
                        'volumes': [],
                        'directories': [
                            temp_installation['config_dir'],
                            temp_installation['data_dir']
                        ],
                        'package': 'bablib'
                    })

                    backup_instance = mock_backup.return_value
                    backup_instance.create_backup = AsyncMock(return_value={
                        'path': backup_path,
                        'size_bytes': 10240,
                        'file_count': 5,
                        'manifest': {
                            'backup_id': 'test-backup-123',
                            'created_at': datetime.now().isoformat(),
                            'bablib_version': '1.0.0',
                            'components_included': ['config', 'data'],
                            'compression_ratio': 0.65
                        }
                    })

                    uninstall_instance = mock_uninstall.return_value
                    uninstall_instance.execute = AsyncMock(return_value={
                        'success': True,
                        'removed': 3,
                        'failed': 0,
                        'skipped': 0
                    })

                    result = cli_runner.invoke(cli, ['uninstall', '--force', '--backup'])

                    assert result.exit_code == 0
                    assert 'Backup created' in result.output
                    backup_instance.create_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_creation_with_custom_path(self, cli_runner, temp_installation, tmp_path):
        """Test backup creation with custom path specified."""
        from src.cli.main import cli

        custom_backup_path = tmp_path / "custom" / "backup.tar.gz"
        custom_backup_path.parent.mkdir(parents=True, exist_ok=True)

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                    detection_instance = mock_detection.return_value
                    detection_instance.detect_all_components = AsyncMock(return_value={
                        'containers': [{'Names': ['/bablib-qdrant'], 'Id': 'container1'}],
                        'volumes': [{'Name': 'bablib_data', 'Driver': 'local'}],
                        'directories': [temp_installation['data_dir']],
                        'package': 'bablib'
                    })

                    backup_instance = mock_backup.return_value
                    backup_instance.create_backup = AsyncMock(return_value={
                        'path': custom_backup_path,
                        'size_bytes': 20480,
                        'file_count': 10,
                        'manifest': {
                            'backup_id': 'custom-backup-456',
                            'created_at': datetime.now().isoformat(),
                            'bablib_version': '1.0.0',
                            'components_included': ['containers', 'volumes', 'data'],
                            'compression_ratio': 0.55
                        }
                    })

                    uninstall_instance = mock_uninstall.return_value
                    uninstall_instance.execute = AsyncMock(return_value={
                        'success': True,
                        'removed': 4,
                        'failed': 0,
                        'skipped': 0
                    })

                    result = cli_runner.invoke(cli, [
                        'uninstall', '--force', '--backup',
                        '--backup-path', str(custom_backup_path)
                    ])

                    assert result.exit_code == 0
                    assert str(custom_backup_path) in result.output
                    # Verify custom path was used
                    call_args = backup_instance.create_backup.call_args
                    assert call_args[1]['path'] == custom_backup_path

    @pytest.mark.asyncio
    async def test_backup_failure_handling(self, cli_runner):
        """Test handling of backup creation failure."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value={
                    'containers': [],
                    'volumes': [],
                    'directories': [Path.home() / '.config/bablib'],
                    'package': 'bablib'
                })

                backup_instance = mock_backup.return_value
                backup_instance.create_backup = AsyncMock(
                    side_effect=Exception("Insufficient disk space")
                )

                # Without --force, should prompt user
                result = cli_runner.invoke(cli, ['uninstall', '--backup'], input='no\n')

                assert result.exit_code == 3  # Error during backup
                assert 'Failed to create backup' in result.output
                assert 'Insufficient disk space' in result.output

    @pytest.mark.asyncio
    async def test_backup_size_estimation(self, cli_runner, temp_installation):
        """Test backup size estimation before creation."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                    detection_instance = mock_detection.return_value
                    detection_instance.detect_all_components = AsyncMock(return_value={
                        'containers': [],
                        'volumes': [],
                        'directories': [
                            temp_installation['config_dir'],
                            temp_installation['data_dir']
                        ],
                        'package': None
                    })

                    backup_instance = mock_backup.return_value
                    backup_instance.estimate_backup_size = AsyncMock(return_value=1048576)  # 1MB
                    backup_instance.create_backup = AsyncMock(return_value={
                        'path': temp_installation['home'] / 'backup.tar.gz',
                        'size_bytes': 524288,  # 512KB compressed
                        'file_count': 3,
                        'manifest': {
                            'backup_id': 'size-test-789',
                            'compression_ratio': 0.5
                        }
                    })

                    uninstall_instance = mock_uninstall.return_value
                    uninstall_instance.execute = AsyncMock(return_value={
                        'success': True,
                        'removed': 2,
                        'failed': 0,
                        'skipped': 0
                    })

                    result = cli_runner.invoke(cli, ['uninstall', '--force', '--backup', '--verbose'])

                    assert result.exit_code == 0
                    # Should estimate size before backup
                    backup_instance.estimate_backup_size.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_verification(self, cli_runner, tmp_path):
        """Test backup archive verification after creation."""
        from src.cli.main import cli

        backup_path = tmp_path / "verified-backup.tar.gz"

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                    detection_instance = mock_detection.return_value
                    detection_instance.detect_all_components = AsyncMock(return_value={
                        'containers': [],
                        'volumes': [],
                        'directories': [Path.home() / '.config/bablib'],
                        'package': None
                    })

                    backup_instance = mock_backup.return_value
                    backup_instance.create_backup = AsyncMock(return_value={
                        'path': backup_path,
                        'size_bytes': 2048,
                        'file_count': 2,
                        'manifest': {'backup_id': 'verify-test'}
                    })
                    backup_instance.verify_backup = AsyncMock(return_value=True)

                    uninstall_instance = mock_uninstall.return_value
                    uninstall_instance.execute = AsyncMock(return_value={
                        'success': True,
                        'removed': 1,
                        'failed': 0,
                        'skipped': 0
                    })

                    result = cli_runner.invoke(cli, [
                        'uninstall', '--force', '--backup',
                        '--backup-path', str(backup_path)
                    ])

                    assert result.exit_code == 0
                    # Verify backup should be called
                    backup_instance.verify_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_manifest_contents(self, cli_runner, tmp_path):
        """Test that backup manifest contains correct metadata."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                    components = {
                        'containers': [
                            {'Names': ['/bablib-qdrant'], 'Id': 'c1'},
                            {'Names': ['/bablib-redis'], 'Id': 'c2'}
                        ],
                        'volumes': [
                            {'Name': 'bablib_qdrant_data'},
                            {'Name': 'bablib_redis_data'}
                        ],
                        'directories': [
                            Path.home() / '.config/bablib',
                            Path.home() / '.local/share/bablib'
                        ],
                        'package': 'bablib'
                    }

                    detection_instance = mock_detection.return_value
                    detection_instance.detect_all_components = AsyncMock(return_value=components)

                    expected_manifest = {
                        'backup_id': 'manifest-test-123',
                        'created_at': datetime.now().isoformat(),
                        'bablib_version': '1.0.0',
                        'components_included': [
                            '2 containers',
                            '2 volumes',
                            '2 directories',
                            '1 package'
                        ],
                        'total_size_bytes': 104857,
                        'compression_ratio': 0.6,
                        'file_count': 25,
                        'container_count': 2
                    }

                    backup_instance = mock_backup.return_value
                    backup_instance.create_backup = AsyncMock(return_value={
                        'path': tmp_path / 'manifest-backup.tar.gz',
                        'manifest': expected_manifest
                    })

                    uninstall_instance = mock_uninstall.return_value
                    uninstall_instance.execute = AsyncMock(return_value={
                        'success': True,
                        'removed': 7,
                        'failed': 0,
                        'skipped': 0
                    })

                    result = cli_runner.invoke(cli, ['uninstall', '--force', '--backup'])

                    assert result.exit_code == 0
                    # Verify manifest was created with components
                    call_args = backup_instance.create_backup.call_args
                    assert call_args[1]['components'] == components

    @pytest.mark.asyncio
    async def test_backup_dry_run_no_creation(self, cli_runner):
        """Test that backup is not created during dry run."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.backup_service.BackupService') as mock_backup:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value={
                    'containers': [],
                    'volumes': [],
                    'directories': [Path.home() / '.config/bablib'],
                    'package': None
                })

                backup_instance = mock_backup.return_value

                result = cli_runner.invoke(cli, ['uninstall', '--dry-run', '--backup'])

                assert result.exit_code == 0
                assert 'would be removed' in result.output.lower()
                # Backup should not be created in dry run
                backup_instance.create_backup.assert_not_called()