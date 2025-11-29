"""Integration test for Bablib uninstall failure handling."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from click.testing import CliRunner
import docker.errors


class TestUninstallFailures:
    """Test partial failure handling during uninstall process."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        return {
            'containers': [
                {'Names': ['/bablib-qdrant'], 'Id': 'container1', 'State': 'running'},
                {'Names': ['/bablib-redis'], 'Id': 'container2', 'State': 'running'},
                {'Names': ['/bablib-ollama'], 'Id': 'container3', 'State': 'stopped'}
            ],
            'volumes': [
                {'Name': 'bablib_qdrant_data', 'Driver': 'local'},
                {'Name': 'bablib_redis_data', 'Driver': 'local'}
            ],
            'directories': [
                Path.home() / '.config/bablib',
                Path.home() / '.local/share/bablib',
                Path.home() / '.cache/bablib'
            ],
            'package': 'bablib'
        }

    @pytest.mark.asyncio
    async def test_container_removal_failure_with_prompt(self, cli_runner, mock_components):
        """Test handling of container removal failure with user prompt."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.removal_executor.RemovalExecutor') as mock_executor:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=mock_components)

                executor_instance = mock_executor.return_value
                # First container fails, others succeed
                executor_instance.remove_container = AsyncMock(
                    side_effect=[
                        docker.errors.APIError("Container is locked"),
                        True,
                        True
                    ]
                )
                executor_instance.remove_volume = AsyncMock(return_value=True)
                executor_instance.delete_directory = AsyncMock(return_value=True)

                # User chooses to continue after failure
                result = cli_runner.invoke(cli, ['uninstall'], input='yes\ny\n')

                assert 'Failed to remove' in result.output
                assert 'Continue with remaining' in result.output
                assert result.exit_code == 1  # Partial success

    @pytest.mark.asyncio
    async def test_container_removal_failure_with_force(self, cli_runner, mock_components):
        """Test handling of container removal failure with --force flag."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=mock_components)

                uninstall_instance = mock_uninstall.return_value
                uninstall_instance.execute = AsyncMock(return_value={
                    'success': False,  # Partial failure
                    'removed': 6,
                    'failed': 2,  # 2 components failed
                    'skipped': 0,
                    'errors': [
                        {'component': 'container:bablib-qdrant', 'error': 'Container is locked'},
                        {'component': 'volume:bablib_qdrant_data', 'error': 'Volume in use'}
                    ]
                })

                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                # Should not prompt with --force
                assert 'Continue with remaining' not in result.output
                # Should report failures
                assert 'Failed' in result.output or 'failed' in result.output
                assert result.exit_code == 1  # Partial success

    @pytest.mark.asyncio
    async def test_directory_removal_permission_error(self, cli_runner):
        """Test handling of permission errors during directory removal."""
        from src.cli.main import cli

        components = {
            'containers': [],
            'volumes': [],
            'directories': [
                Path('/etc/bablib'),  # System directory (permission error likely)
                Path.home() / '.config/bablib'
            ],
            'package': None
        }

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.removal_executor.RemovalExecutor') as mock_executor:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=components)

                executor_instance = mock_executor.return_value
                executor_instance.delete_directory = AsyncMock(
                    side_effect=[
                        PermissionError("Permission denied: /etc/bablib"),
                        True
                    ]
                )

                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                assert result.exit_code == 1  # Partial success
                assert 'Permission denied' in result.output or 'permission' in result.output.lower()

    @pytest.mark.asyncio
    async def test_volume_removal_external_skip(self, cli_runner):
        """Test that external volumes are skipped and reported."""
        from src.cli.main import cli

        components = {
            'containers': [],
            'volumes': [
                {'Name': 'bablib_internal', 'Driver': 'local', 'External': False},
                {'Name': 'external_data', 'Driver': 'local', 'External': True},
                {'Name': 'user_volume', 'Driver': 'local', 'External': True}
            ],
            'directories': [],
            'package': None
        }

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=components)

                uninstall_instance = mock_uninstall.return_value
                uninstall_instance.execute = AsyncMock(return_value={
                    'success': True,
                    'removed': 1,  # Only internal volume
                    'failed': 0,
                    'skipped': 2,  # External volumes
                    'skipped_items': ['external_data', 'user_volume']
                })

                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                assert result.exit_code == 0  # Success (skipping is ok)
                assert 'preserved' in result.output.lower() or 'skipped' in result.output.lower()

    @pytest.mark.asyncio
    async def test_package_uninstall_failure(self, cli_runner):
        """Test handling of package uninstall failure."""
        from src.cli.main import cli

        components = {
            'containers': [],
            'volumes': [],
            'directories': [],
            'package': 'bablib'
        }

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.removal_executor.RemovalExecutor') as mock_executor:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=components)

                executor_instance = mock_executor.return_value
                executor_instance.uninstall_package = AsyncMock(
                    side_effect=Exception("UV tool not found in PATH")
                )

                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                assert result.exit_code == 1  # Failure
                assert 'UV tool not found' in result.output or 'Failed' in result.output

    @pytest.mark.asyncio
    async def test_multiple_failures_abort_option(self, cli_runner, mock_components):
        """Test user choosing to abort after multiple failures."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.removal_executor.RemovalExecutor') as mock_executor:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=mock_components)

                executor_instance = mock_executor.return_value
                # Multiple failures
                executor_instance.remove_container = AsyncMock(
                    side_effect=[
                        docker.errors.APIError("Container 1 locked"),
                        docker.errors.APIError("Container 2 in use"),
                        True
                    ]
                )

                # User aborts after second failure
                result = cli_runner.invoke(cli, ['uninstall'], input='yes\ny\nn\n')

                assert result.exit_code == 2  # User aborted
                assert 'Aborted' in result.output or 'aborted' in result.output.lower()

    @pytest.mark.asyncio
    async def test_critical_failure_stops_process(self, cli_runner):
        """Test that critical failures stop the entire process."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            # Critical failure during detection
            detection_instance = mock_detection.return_value
            detection_instance.detect_all_components = AsyncMock(
                side_effect=Exception("Docker daemon not accessible")
            )

            result = cli_runner.invoke(cli, ['uninstall', '--force'])

            assert result.exit_code == 3  # Critical error
            assert 'Docker daemon not accessible' in result.output or 'Error' in result.output

    @pytest.mark.asyncio
    async def test_recovery_suggestions_on_failure(self, cli_runner):
        """Test that recovery suggestions are provided on failure."""
        from src.cli.main import cli

        components = {
            'containers': [
                {'Names': ['/bablib-qdrant'], 'Id': 'container1', 'State': 'running'}
            ],
            'volumes': [],
            'directories': [],
            'package': None
        }

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=components)

                uninstall_instance = mock_uninstall.return_value
                uninstall_instance.execute = AsyncMock(return_value={
                    'success': False,
                    'removed': 0,
                    'failed': 1,
                    'skipped': 0,
                    'errors': [
                        {
                            'component': 'container:bablib-qdrant',
                            'error': 'Container is being used by another process',
                            'suggestion': 'Try stopping the container manually: docker stop bablib-qdrant'
                        }
                    ]
                })

                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                assert result.exit_code == 1
                # Should provide recovery suggestion
                assert 'docker stop' in result.output or 'manually' in result.output.lower()

    @pytest.mark.asyncio
    async def test_partial_success_summary(self, cli_runner, mock_components):
        """Test that partial success provides detailed summary."""
        from src.cli.main import cli

        with patch('src.services.component_detection.ComponentDetectionService') as mock_detection:
            with patch('src.services.uninstall_service.UninstallService') as mock_uninstall:
                detection_instance = mock_detection.return_value
                detection_instance.detect_all_components = AsyncMock(return_value=mock_components)

                uninstall_instance = mock_uninstall.return_value
                uninstall_instance.execute = AsyncMock(return_value={
                    'success': False,
                    'removed': 5,
                    'failed': 2,
                    'skipped': 1,
                    'summary': {
                        'containers_removed': 2,
                        'containers_failed': 1,
                        'volumes_removed': 1,
                        'volumes_skipped': 1,
                        'directories_removed': 2,
                        'package_removed': False
                    }
                })

                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                assert result.exit_code == 1
                # Should show summary
                assert 'removed' in result.output.lower()
                assert 'failed' in result.output.lower()
                assert 'skipped' in result.output.lower() or 'preserved' in result.output.lower()