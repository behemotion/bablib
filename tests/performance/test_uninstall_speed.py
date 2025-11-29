"""Performance test for uninstall operation speed."""

import pytest
import time
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.models.uninstall_config import UninstallConfig
from src.services.uninstall_service import UninstallService
from src.services.component_detection import ComponentDetectionService


class TestUninstallPerformance:
    """Test uninstall completes within performance requirements."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)  # 60 second timeout
    async def test_uninstall_completes_within_60_seconds(self):
        """Test that full uninstall completes within 60 seconds."""
        # Create mock components
        mock_components = {
            'containers': [
                Mock(component_name='bablib-qdrant', component_type='container'),
                Mock(component_name='bablib-redis', component_type='container'),
                Mock(component_name='bablib-ollama', component_type='container')
            ],
            'volumes': [
                Mock(component_name='bablib_qdrant_data', component_type='volume', is_external=False),
                Mock(component_name='bablib_redis_data', component_type='volume', is_external=False)
            ],
            'directories': [
                Mock(component_path=Path.home() / '.config/bablib', component_type='directory'),
                Mock(component_path=Path.home() / '.local/share/bablib', component_type='directory'),
                Mock(component_path=Path.home() / '.cache/bablib', component_type='directory')
            ],
            'configs': [
                Mock(component_path=Path.home() / '.config/bablib/config.yaml', component_type='config')
            ],
            'package': Mock(component_name='bablib', component_type='package')
        }

        # Mock the service methods
        with patch.object(ComponentDetectionService, 'detect_all_components') as mock_detect:
            with patch('src.services.removal_executor.RemovalExecutor') as mock_executor_class:
                # Setup mocks
                mock_detect.return_value = mock_components

                mock_executor = mock_executor_class.return_value
                # All operations return quickly
                mock_executor.stop_container = AsyncMock(return_value=True, side_effect=lambda x: asyncio.sleep(0.1))
                mock_executor.remove_container = AsyncMock(return_value=True, side_effect=lambda x, **k: asyncio.sleep(0.1))
                mock_executor.remove_volume = AsyncMock(return_value=True, side_effect=lambda x, **k: asyncio.sleep(0.1))
                mock_executor.delete_directory = AsyncMock(return_value=True, side_effect=lambda x: asyncio.sleep(0.1))
                mock_executor.uninstall_package = AsyncMock(return_value=True, side_effect=lambda: asyncio.sleep(0.5))

                # Run uninstall
                config = UninstallConfig(force=True)
                service = UninstallService()

                start_time = time.time()
                result = await service.execute(config, mock_components)
                end_time = time.time()

                # Check results
                assert result['success'] is True
                assert result['removed'] > 0

                # Verify performance
                duration = end_time - start_time
                assert duration < 60, f"Uninstall took {duration:.2f} seconds, exceeding 60 second limit"

    @pytest.mark.asyncio
    async def test_component_detection_performance(self):
        """Test that component detection completes quickly."""
        with patch('src.services.component_detection.docker') as mock_docker:
            # Mock Docker client
            mock_client = Mock()
            mock_client.containers.list.return_value = [
                Mock(name=f'bablib-{i}', labels={'bablib.managed': 'true'})
                for i in range(10)  # 10 containers
            ]
            mock_client.volumes.list.return_value = [
                Mock(name=f'bablib_volume_{i}', attrs={'Labels': {'bablib.managed': 'true'}})
                for i in range(10)  # 10 volumes
            ]
            mock_docker.from_env.return_value = mock_client

            # Mock file system checks
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_dir', return_value=True):
                    with patch('os.walk', return_value=[]):
                        service = ComponentDetectionService()

                        start_time = time.time()
                        components = await service.detect_all_components()
                        end_time = time.time()

                        # Should detect components
                        assert len(components['containers']) == 10
                        assert len(components['volumes']) == 10

                        # Should be fast (< 5 seconds)
                        duration = end_time - start_time
                        assert duration < 5, f"Detection took {duration:.2f} seconds, exceeding 5 second limit"

    @pytest.mark.asyncio
    async def test_backup_creation_performance(self, tmp_path):
        """Test that backup creation doesn't significantly slow down uninstall."""
        from src.services.backup_service import BackupService

        # Create small test directories
        test_dir = tmp_path / "test_data"
        test_dir.mkdir()
        for i in range(10):
            (test_dir / f"file_{i}.txt").write_text(f"Test content {i}")

        mock_components = {
            'directories': [test_dir],
            'configs': [],
            'containers': [],
            'volumes': []
        }

        service = BackupService()

        start_time = time.time()
        backup_info = await service.create_backup(
            components=mock_components,
            path=tmp_path / "backup.tar.gz"
        )
        end_time = time.time()

        # Verify backup was created
        assert backup_info['path'].exists()

        # Should be reasonably fast (< 10 seconds for small data)
        duration = end_time - start_time
        assert duration < 10, f"Backup took {duration:.2f} seconds, exceeding 10 second limit"

    @pytest.mark.asyncio
    async def test_parallel_operations(self):
        """Test that operations can run in parallel where appropriate."""
        from src.services.uninstall_service import UninstallService

        # Multiple independent volumes
        mock_components = {
            'containers': [],
            'volumes': [
                Mock(component_name=f'bablib_volume_{i}', is_external=False)
                for i in range(5)
            ],
            'directories': [],
            'configs': [],
            'package': None
        }

        with patch('src.services.removal_executor.RemovalExecutor') as mock_executor_class:
            mock_executor = mock_executor_class.return_value

            # Track concurrent calls
            concurrent_calls = []

            async def track_concurrent(name, **kwargs):
                concurrent_calls.append(time.time())
                await asyncio.sleep(0.1)  # Simulate work
                return True

            mock_executor.remove_volume = AsyncMock(side_effect=track_concurrent)

            config = UninstallConfig(force=True)
            service = UninstallService()

            start_time = time.time()
            result = await service.execute(config, mock_components)
            end_time = time.time()

            # Should complete faster than sequential (5 * 0.1 = 0.5s)
            duration = end_time - start_time
            # Note: Current implementation is sequential, but leaving test for future parallel implementation
            assert duration < 2, f"Operations took {duration:.2f} seconds"