"""Unit tests for volume filtering (external vs internal)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestVolumeFilter:
    """Test volume filtering to distinguish external vs internal volumes."""

    @pytest.mark.asyncio
    async def test_identify_internal_volume(self):
        """Test identification of Bablib-managed internal volumes."""
        from src.services.removal_executor import RemovalExecutor

        mock_volume = Mock()
        mock_volume.name = 'bablib_qdrant_data'
        mock_volume.attrs = {
            'Driver': 'local',
            'Labels': {'bablib.managed': 'true'},
            'Mountpoint': '/var/lib/docker/volumes/bablib_qdrant_data/_data'
        }

        executor = RemovalExecutor()
        is_external = await executor.is_external_volume(mock_volume)

        assert is_external is False  # Internal volume

    @pytest.mark.asyncio
    async def test_identify_external_volume_by_mount(self):
        """Test identification of external volume by mount point."""
        from src.services.removal_executor import RemovalExecutor

        mock_volume = Mock()
        mock_volume.name = 'external_data'
        mock_volume.attrs = {
            'Driver': 'local',
            'Labels': {},
            'Mountpoint': '/mnt/external/data'  # External mount point
        }

        executor = RemovalExecutor()
        is_external = await executor.is_external_volume(mock_volume)

        assert is_external is True  # External volume

    @pytest.mark.asyncio
    async def test_identify_external_volume_by_label(self):
        """Test identification of external volume by label."""
        from src.services.removal_executor import RemovalExecutor

        mock_volume = Mock()
        mock_volume.name = 'user_volume'
        mock_volume.attrs = {
            'Driver': 'local',
            'Labels': {'external': 'true'},  # Explicit external label
            'Mountpoint': '/var/lib/docker/volumes/user_volume/_data'
        }

        executor = RemovalExecutor()
        is_external = await executor.is_external_volume(mock_volume)

        assert is_external is True  # External volume

    @pytest.mark.asyncio
    async def test_filter_volumes_for_removal(self):
        """Test filtering volumes to get only removable ones."""
        from src.services.removal_executor import RemovalExecutor

        volumes = [
            Mock(
                name='bablib_internal',
                attrs={
                    'Labels': {'bablib.managed': 'true'},
                    'Mountpoint': '/var/lib/docker/volumes/bablib_internal/_data'
                }
            ),
            Mock(
                name='external_volume',
                attrs={
                    'Labels': {'external': 'true'},
                    'Mountpoint': '/mnt/external'
                }
            ),
            Mock(
                name='bablib_data',
                attrs={
                    'Labels': {'bablib.managed': 'true'},
                    'Mountpoint': '/var/lib/docker/volumes/bablib_data/_data'
                }
            ),
            Mock(
                name='user_data',
                attrs={
                    'Labels': {},
                    'Mountpoint': '/home/user/data'  # User directory mount
                }
            )
        ]

        executor = RemovalExecutor()
        removable_volumes = await executor.filter_removable_volumes(volumes)

        assert len(removable_volumes) == 2
        assert 'bablib_internal' in [v.name for v in removable_volumes]
        assert 'bablib_data' in [v.name for v in removable_volumes]
        assert 'external_volume' not in [v.name for v in removable_volumes]
        assert 'user_data' not in [v.name for v in removable_volumes]

    @pytest.mark.asyncio
    async def test_volume_in_use_detection(self):
        """Test detection of volumes currently in use."""
        from src.services.removal_executor import RemovalExecutor

        mock_docker_client = Mock()
        mock_container = Mock()
        mock_container.attrs = {
            'Mounts': [
                {
                    'Type': 'volume',
                    'Name': 'bablib_data',
                    'Destination': '/data'
                }
            ]
        }
        mock_docker_client.containers.list.return_value = [mock_container]

        executor = RemovalExecutor(docker_client=mock_docker_client)
        in_use = await executor.is_volume_in_use('bablib_data')

        assert in_use is True

        # Test volume not in use
        in_use = await executor.is_volume_in_use('unused_volume')
        assert in_use is False

    @pytest.mark.asyncio
    async def test_volume_naming_pattern(self):
        """Test identification of Bablib volumes by naming pattern."""
        from src.services.component_detection import ComponentDetectionService

        service = ComponentDetectionService()

        # Bablib managed volumes
        assert service.is_bablib_volume_name('bablib_qdrant_data') is True
        assert service.is_bablib_volume_name('bablib_redis_data') is True
        assert service.is_bablib_volume_name('bablib_backup') is True

        # Non-Bablib volumes
        assert service.is_bablib_volume_name('postgres_data') is False
        assert service.is_bablib_volume_name('user_volume') is False
        assert service.is_bablib_volume_name('external_data') is False

    @pytest.mark.asyncio
    async def test_preserve_shared_volumes(self):
        """Test that volumes shared with non-Bablib containers are preserved."""
        from src.services.removal_executor import RemovalExecutor

        mock_docker_client = Mock()

        # Bablib container using the volume
        bablib_container = Mock()
        bablib_container.name = 'bablib-qdrant'
        bablib_container.attrs = {
            'Mounts': [
                {'Type': 'volume', 'Name': 'shared_volume'}
            ]
        }

        # Non-Bablib container also using the volume
        other_container = Mock()
        other_container.name = 'postgres'
        other_container.attrs = {
            'Mounts': [
                {'Type': 'volume', 'Name': 'shared_volume'}
            ]
        }

        mock_docker_client.containers.list.return_value = [bablib_container, other_container]

        executor = RemovalExecutor(docker_client=mock_docker_client)
        should_preserve = await executor.should_preserve_volume('shared_volume')

        assert should_preserve is True  # Shared with non-Bablib container

    @pytest.mark.asyncio
    async def test_volume_metadata_extraction(self):
        """Test extraction of volume metadata for reporting."""
        from src.services.component_detection import ComponentDetectionService

        mock_volume = Mock()
        mock_volume.name = 'bablib_data'
        mock_volume.attrs = {
            'Driver': 'local',
            'Labels': {'bablib.managed': 'true', 'version': '1.0'},
            'Mountpoint': '/var/lib/docker/volumes/bablib_data/_data',
            'CreatedAt': '2024-01-01T00:00:00Z',
            'Options': {'type': 'tmpfs'},
            'Scope': 'local'
        }

        service = ComponentDetectionService()
        metadata = await service.extract_volume_metadata(mock_volume)

        assert metadata['name'] == 'bablib_data'
        assert metadata['driver'] == 'local'
        assert metadata['managed'] is True
        assert metadata['version'] == '1.0'
        assert metadata['created_at'] == '2024-01-01T00:00:00Z'

    @pytest.mark.asyncio
    async def test_anonymous_volume_detection(self):
        """Test detection of anonymous Docker volumes."""
        from src.services.removal_executor import RemovalExecutor

        # Anonymous volume (64-char hex name)
        anonymous_volume = Mock()
        anonymous_volume.name = 'a' * 64  # 64 hex characters
        anonymous_volume.attrs = {
            'Labels': {},
            'Mountpoint': '/var/lib/docker/volumes/aaaa/_data'
        }

        # Named volume
        named_volume = Mock()
        named_volume.name = 'bablib_data'
        named_volume.attrs = {
            'Labels': {'bablib.managed': 'true'},
            'Mountpoint': '/var/lib/docker/volumes/bablib_data/_data'
        }

        executor = RemovalExecutor()

        assert await executor.is_anonymous_volume(anonymous_volume) is True
        assert await executor.is_anonymous_volume(named_volume) is False

    @pytest.mark.asyncio
    async def test_volume_size_estimation(self):
        """Test estimation of volume sizes."""
        from src.services.component_detection import ComponentDetectionService

        with patch('os.statvfs') as mock_statvfs:
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = True

                # Mock statvfs result
                mock_stat = Mock()
                mock_stat.f_blocks = 1000000  # Total blocks
                mock_stat.f_bavail = 500000   # Available blocks
                mock_stat.f_frsize = 4096      # Block size
                mock_statvfs.return_value = mock_stat

                service = ComponentDetectionService()
                volume_info = Mock()
                volume_info.attrs = {'Mountpoint': '/var/lib/docker/volumes/test/_data'}

                size = await service.estimate_volume_size(volume_info)

                # Used space = (total - available) * block_size
                expected_size = (1000000 - 500000) * 4096
                assert size == expected_size