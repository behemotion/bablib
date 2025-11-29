"""Unit tests for component detection service."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import docker.errors


class TestComponentDetection:
    """Test component detection functionality."""

    @pytest.mark.asyncio
    async def test_detect_docker_containers(self):
        """Test detection of Bablib Docker containers."""
        from src.services.component_detection import ComponentDetectionService

        mock_docker_client = Mock()
        mock_docker_client.containers.list.return_value = [
            Mock(
                id='container1',
                name='bablib-qdrant',
                status='running',
                labels={'bablib.managed': 'true'}
            ),
            Mock(
                id='container2',
                name='bablib-redis',
                status='running',
                labels={'bablib.managed': 'true'}
            ),
            Mock(
                id='container3',
                name='other-container',
                status='running',
                labels={}
            )
        ]

        service = ComponentDetectionService(docker_client=mock_docker_client)
        containers = await service.find_docker_containers()

        assert len(containers) == 2
        assert all(c.component_type == 'container' for c in containers)
        assert any(c.component_name == 'bablib-qdrant' for c in containers)
        assert any(c.component_name == 'bablib-redis' for c in containers)
        assert not any(c.component_name == 'other-container' for c in containers)

    @pytest.mark.asyncio
    async def test_detect_docker_volumes(self):
        """Test detection of Bablib Docker volumes."""
        from src.services.component_detection import ComponentDetectionService

        mock_docker_client = Mock()
        mock_docker_client.volumes.list.return_value = [
            Mock(
                name='bablib_qdrant_data',
                attrs={'Driver': 'local', 'Labels': {'bablib.managed': 'true'}}
            ),
            Mock(
                name='bablib_redis_data',
                attrs={'Driver': 'local', 'Labels': {'bablib.managed': 'true'}}
            ),
            Mock(
                name='external_volume',
                attrs={'Driver': 'local', 'Labels': {}}
            )
        ]

        service = ComponentDetectionService(docker_client=mock_docker_client)
        volumes = await service.find_docker_volumes()

        assert len(volumes) == 2
        assert all(v.component_type == 'volume' for v in volumes)
        assert any(v.component_name == 'bablib_qdrant_data' for v in volumes)
        assert any(v.component_name == 'bablib_redis_data' for v in volumes)
        assert not any(v.component_name == 'external_volume' for v in volumes)

    @pytest.mark.asyncio
    async def test_detect_data_directories(self):
        """Test detection of Bablib data directories."""
        from src.services.component_detection import ComponentDetectionService

        with patch('pathlib.Path.exists') as mock_exists:
            with patch('pathlib.Path.is_dir') as mock_is_dir:
                with patch('os.path.getsize') as mock_getsize:
                    # Setup mocks
                    mock_exists.side_effect = lambda: True
                    mock_is_dir.side_effect = lambda: True
                    mock_getsize.return_value = 1024

                    service = ComponentDetectionService()
                    directories = await service.find_data_directories()

                    # Should find standard XDG directories
                    assert len(directories) > 0
                    assert any(
                        '.config/bablib' in str(d.component_path)
                        for d in directories
                    )
                    assert any(
                        '.local/share/bablib' in str(d.component_path)
                        for d in directories
                    )
                    assert all(d.component_type == 'directory' for d in directories)

    @pytest.mark.asyncio
    async def test_detect_config_files(self):
        """Test detection of Bablib configuration files."""
        from src.services.component_detection import ComponentDetectionService

        test_files = [
            Path.home() / '.config/bablib/config.yaml',
            Path.home() / '.config/bablib/settings.json',
            Path.home() / '.local/share/bablib/bablib.db'
        ]

        with patch('pathlib.Path.glob') as mock_glob:
            with patch('pathlib.Path.exists') as mock_exists:
                mock_glob.return_value = test_files
                mock_exists.return_value = True

                service = ComponentDetectionService()
                config_files = await service.find_config_files()

                assert len(config_files) > 0
                assert all(c.component_type == 'config' for c in config_files)

    @pytest.mark.asyncio
    async def test_check_package_installation(self):
        """Test checking if Bablib package is installed."""
        from src.services.component_detection import ComponentDetectionService

        with patch('subprocess.run') as mock_run:
            # Package is installed
            mock_run.return_value = Mock(returncode=0, stdout='bablib==1.0.0')

            service = ComponentDetectionService()
            package_status = await service.check_package_installation()

            assert package_status.component_type == 'package'
            assert package_status.component_name == 'bablib'
            assert package_status.status == 'pending'

            # Package not installed
            mock_run.return_value = Mock(returncode=1, stdout='')

            package_status = await service.check_package_installation()
            assert package_status is None

    @pytest.mark.asyncio
    async def test_detect_all_components(self):
        """Test detection of all components combined."""
        from src.services.component_detection import ComponentDetectionService

        with patch.object(ComponentDetectionService, 'find_docker_containers') as mock_containers:
            with patch.object(ComponentDetectionService, 'find_docker_volumes') as mock_volumes:
                with patch.object(ComponentDetectionService, 'find_data_directories') as mock_dirs:
                    with patch.object(ComponentDetectionService, 'find_config_files') as mock_configs:
                        with patch.object(ComponentDetectionService, 'check_package_installation') as mock_package:
                            # Setup mocks
                            mock_containers.return_value = [
                                Mock(component_name='bablib-qdrant', component_type='container')
                            ]
                            mock_volumes.return_value = [
                                Mock(component_name='bablib_data', component_type='volume')
                            ]
                            mock_dirs.return_value = [
                                Mock(component_path=Path.home() / '.config/bablib', component_type='directory')
                            ]
                            mock_configs.return_value = [
                                Mock(component_path=Path.home() / '.config/bablib/config.yaml', component_type='config')
                            ]
                            mock_package.return_value = Mock(component_name='bablib', component_type='package')

                            service = ComponentDetectionService()
                            all_components = await service.detect_all_components()

                            assert 'containers' in all_components
                            assert 'volumes' in all_components
                            assert 'directories' in all_components
                            assert 'configs' in all_components
                            assert 'package' in all_components

                            assert len(all_components['containers']) == 1
                            assert len(all_components['volumes']) == 1
                            assert len(all_components['directories']) == 1
                            assert len(all_components['configs']) == 1
                            assert all_components['package'] is not None

    @pytest.mark.asyncio
    async def test_docker_not_available(self):
        """Test handling when Docker is not available."""
        from src.services.component_detection import ComponentDetectionService

        mock_docker_client = Mock()
        mock_docker_client.containers.list.side_effect = docker.errors.DockerException("Docker daemon not running")

        service = ComponentDetectionService(docker_client=mock_docker_client)
        containers = await service.find_docker_containers()

        assert containers == []  # Should return empty list, not crash

    @pytest.mark.asyncio
    async def test_filter_bablib_components(self):
        """Test filtering to only include Bablib-managed components."""
        from src.services.component_detection import ComponentDetectionService

        mock_docker_client = Mock()
        mock_docker_client.containers.list.return_value = [
            Mock(
                id='c1',
                name='bablib-qdrant',
                labels={'bablib.managed': 'true'}
            ),
            Mock(
                id='c2',
                name='postgres',  # Not a Bablib container
                labels={}
            ),
            Mock(
                id='c3',
                name='bablib-test',  # Has bablib in name
                labels={}
            )
        ]

        service = ComponentDetectionService(docker_client=mock_docker_client)
        containers = await service.find_docker_containers()

        # Should include containers with label or name pattern
        assert len(containers) == 2
        assert any(c.component_name == 'bablib-qdrant' for c in containers)
        assert any(c.component_name == 'bablib-test' for c in containers)
        assert not any(c.component_name == 'postgres' for c in containers)

    @pytest.mark.asyncio
    async def test_component_size_calculation(self):
        """Test calculation of component sizes."""
        from src.services.component_detection import ComponentDetectionService

        with patch('os.walk') as mock_walk:
            with patch('os.path.getsize') as mock_getsize:
                # Mock directory structure
                mock_walk.return_value = [
                    ('/test/dir', [], ['file1.txt', 'file2.txt']),
                    ('/test/dir/subdir', [], ['file3.txt'])
                ]
                mock_getsize.side_effect = [1024, 2048, 512]  # File sizes

                service = ComponentDetectionService()
                size = await service.calculate_directory_size(Path('/test/dir'))

                assert size == 3584  # Sum of all file sizes

    @pytest.mark.asyncio
    async def test_detect_custom_data_paths(self):
        """Test detection of custom data paths from environment."""
        from src.services.component_detection import ComponentDetectionService

        custom_path = '/custom/bablib/data'

        with patch.dict('os.environ', {'BABLIB_DATABASE_PATH': custom_path}):
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = True

                service = ComponentDetectionService()
                directories = await service.find_data_directories()

                # Should include custom path from environment
                assert any(
                    custom_path in str(d.component_path)
                    for d in directories
                )