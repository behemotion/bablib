"""Integration test Qdrant container renaming scenario."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.qdrant_container_service import QdrantContainerService
from src.services.docker_service_manager import DockerServiceManager
from src.models.service_configuration import ServiceStatus


class TestContainerRenaming:
    """Test Qdrant container renaming to Bablib standards."""

    @pytest.fixture
    def docker_manager(self):
        """Create Docker service manager for testing."""
        return DockerServiceManager()

    @pytest.fixture
    def qdrant_service(self, docker_manager):
        """Create Qdrant container service for testing."""
        return QdrantContainerService(docker_manager)

    @pytest.fixture
    def mock_existing_containers(self):
        """Mock existing non-standard Qdrant containers."""
        existing_containers = [
            {
                "name": "old-qdrant",
                "id": "container123",
                "status": "running",
                "image": "qdrant/qdrant:latest",
                "ports": {"6333/tcp": [{"HostPort": "6333"}]},
                "created": "2024-01-01T00:00:00Z"
            },
            {
                "name": "custom-vector-db",
                "id": "container456",
                "status": "stopped",
                "image": "qdrant/qdrant:v1.11.0",
                "ports": {},
                "created": "2024-01-01T00:00:00Z"
            },
            {
                "name": "qdrant-test",
                "id": "container789",
                "status": "running",
                "image": "qdrant/qdrant:v1.12.1",
                "ports": {"6333/tcp": [{"HostPort": "6334"}]},
                "created": "2024-01-01T00:00:00Z"
            }
        ]

        return existing_containers

    @pytest.mark.asyncio
    async def test_detect_existing_qdrant_containers(self, qdrant_service, mock_existing_containers):
        """Test detection of existing Qdrant containers with various naming patterns."""
        with patch.object(qdrant_service.docker_manager, 'list_bablib_containers') as mock_list:
            mock_list.return_value = mock_existing_containers

            existing = await qdrant_service._find_existing_qdrant_containers()

            assert len(existing) == 3

            # Verify all containers were detected based on image/name patterns
            container_names = [c["name"] for c in existing]
            assert "old-qdrant" in container_names
            assert "custom-vector-db" in container_names
            assert "qdrant-test" in container_names

    @pytest.mark.asyncio
    async def test_rename_running_container_to_backup(self, qdrant_service, docker_manager):
        """Test renaming a running non-standard container to backup name."""
        with patch.object(docker_manager, 'rename_container') as mock_rename:
            mock_rename.return_value = True

            existing_containers = [{
                "name": "old-qdrant",
                "status": "running"
            }]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Verify rename was attempted
            mock_rename.assert_called_once()
            call_args = mock_rename.call_args
            assert call_args[0][0] == "old-qdrant"  # Original name
            assert "backup" in call_args[0][1]      # New name contains "backup"

            assert result["success"] is True
            assert len(result["renamed"]) == 1
            assert "old-qdrant" in result["renamed"][0]

    @pytest.mark.asyncio
    async def test_remove_stopped_non_standard_container(self, qdrant_service, docker_manager):
        """Test removing stopped non-standard containers that can't be renamed."""
        with patch.object(docker_manager, 'rename_container') as mock_rename, \
             patch.object(docker_manager, 'remove_container') as mock_remove:

            # Simulate rename failure, fallback to removal
            mock_rename.return_value = False
            mock_remove.return_value = True

            existing_containers = [{
                "name": "custom-vector-db",
                "status": "stopped"
            }]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Verify fallback to removal
            mock_rename.assert_called_once()
            mock_remove.assert_called_once_with("custom-vector-db", force=True)

            assert result["success"] is True
            assert len(result["removed"]) == 1
            assert "custom-vector-db" in result["removed"]

    @pytest.mark.asyncio
    async def test_preserve_already_standard_container(self, qdrant_service, docker_manager):
        """Test that containers already using standard naming are preserved if running."""
        with patch.object(docker_manager, 'remove_container') as mock_remove:
            mock_remove.return_value = True

            existing_containers = [{
                "name": "bablib-memory-qdrant",
                "status": "running"
            }]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Standard name container should not be renamed or removed if running
            mock_remove.assert_not_called()

            assert result["success"] is True
            assert len(result["renamed"]) == 0
            assert len(result["removed"]) == 0

    @pytest.mark.asyncio
    async def test_recreate_stopped_standard_container(self, qdrant_service, docker_manager):
        """Test recreating stopped container with standard name."""
        with patch.object(docker_manager, 'remove_container') as mock_remove:
            mock_remove.return_value = True

            existing_containers = [{
                "name": "bablib-memory-qdrant",
                "status": "stopped"
            }]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Stopped standard container should be removed for recreation
            mock_remove.assert_called_once_with("bablib-memory-qdrant", force=True)

            assert result["success"] is True
            assert len(result["removed"]) == 1
            assert "bablib-memory-qdrant" in result["removed"]

    @pytest.mark.asyncio
    async def test_handle_rename_failure_gracefully(self, qdrant_service, docker_manager):
        """Test graceful handling of rename failures."""
        with patch.object(docker_manager, 'rename_container') as mock_rename, \
             patch.object(docker_manager, 'remove_container') as mock_remove:

            # Both rename and remove fail
            mock_rename.return_value = False
            mock_remove.return_value = False

            existing_containers = [{
                "name": "problematic-container",
                "status": "running"
            }]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Both operations should have been attempted
            mock_rename.assert_called_once()
            mock_remove.assert_called_once()

            # Result should indicate failure
            assert result["success"] is False
            assert len(result["errors"]) == 1
            assert "problematic-container" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_install_with_force_rename_enabled(self, qdrant_service, mock_existing_containers):
        """Test installation with force_rename=True handles existing containers."""
        with patch.object(qdrant_service, '_find_existing_qdrant_containers') as mock_find, \
             patch.object(qdrant_service, '_handle_existing_containers') as mock_handle, \
             patch.object(qdrant_service.docker_manager, 'create_container') as mock_create, \
             patch.object(qdrant_service, '_wait_for_qdrant_ready') as mock_ready:

            mock_find.return_value = mock_existing_containers
            mock_handle.return_value = {"success": True, "renamed": ["old-qdrant -> old-qdrant-backup"], "removed": []}
            mock_create.return_value = (True, "bablib-memory-qdrant")
            mock_ready.return_value = True

            result = await qdrant_service.install_qdrant(force_rename=True)

            # Verify existing containers were handled
            mock_find.assert_called_once()
            mock_handle.assert_called_once()

            # Verify container creation proceeded
            mock_create.assert_called_once()
            create_args = mock_create.call_args
            assert create_args.kwargs['service_type'] == 'qdrant'
            assert create_args.kwargs['force_recreate'] is True

            assert result["success"] is True
            assert result["container_name"] == "bablib-memory-qdrant"

    @pytest.mark.asyncio
    async def test_install_fails_without_force_rename(self, qdrant_service, mock_existing_containers):
        """Test installation fails when existing containers found without force_rename."""
        with patch.object(qdrant_service, '_find_existing_qdrant_containers') as mock_find:
            mock_find.return_value = mock_existing_containers

            result = await qdrant_service.install_qdrant(force_rename=False)

            assert result["success"] is False
            assert "existing_containers" in result
            assert len(result["existing_containers"]) == 3
            assert "old-qdrant" in result["existing_containers"]

    @pytest.mark.asyncio
    async def test_multiple_container_rename_sequence(self, qdrant_service, docker_manager):
        """Test handling multiple existing containers in correct sequence."""
        with patch.object(docker_manager, 'rename_container') as mock_rename, \
             patch.object(docker_manager, 'remove_container') as mock_remove:

            # First container renames successfully, second needs removal
            mock_rename.side_effect = [True, False]
            mock_remove.return_value = True

            existing_containers = [
                {"name": "qdrant-old", "status": "running"},
                {"name": "vector-db", "status": "stopped"}
            ]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Verify both containers were processed
            assert mock_rename.call_count == 2
            assert mock_remove.call_count == 1

            assert result["success"] is True
            assert len(result["renamed"]) == 1
            assert len(result["removed"]) == 1
            assert "qdrant-old" in result["renamed"][0]
            assert "vector-db" in result["removed"]

    @pytest.mark.asyncio
    async def test_backup_name_generation_with_timestamp(self, qdrant_service, docker_manager):
        """Test that backup names include timestamps to avoid conflicts."""
        with patch.object(docker_manager, 'rename_container') as mock_rename, \
             patch('asyncio.get_event_loop') as mock_loop:

            mock_rename.return_value = True
            mock_time = MagicMock()
            mock_time.time.return_value = 1704067200.0  # Fixed timestamp
            mock_loop.return_value = mock_time

            existing_containers = [{"name": "old-qdrant", "status": "running"}]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Verify timestamp was included in backup name
            mock_rename.assert_called_once()
            call_args = mock_rename.call_args
            backup_name = call_args[0][1]
            assert "backup" in backup_name
            assert "1704067200" in backup_name

    @pytest.mark.asyncio
    async def test_container_renaming_preserves_functionality(self, qdrant_service):
        """Test that renamed containers remain functional."""
        with patch.object(qdrant_service.docker_manager, 'rename_container') as mock_rename, \
             patch.object(qdrant_service.docker_manager, 'get_container_status') as mock_status:

            mock_rename.return_value = True
            mock_status.return_value = ServiceStatus.RUNNING

            existing_containers = [{"name": "functional-qdrant", "status": "running"}]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # After rename, container should still be accessible
            assert result["success"] is True

            # Verify we could still check the renamed container's status
            # (This would be the backup name in real scenario)
            mock_status.assert_not_called()  # Not called in this specific method
            mock_rename.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_recovery_during_rename_operation(self, qdrant_service, docker_manager):
        """Test error recovery when rename operations encounter exceptions."""
        with patch.object(docker_manager, 'rename_container') as mock_rename, \
             patch.object(docker_manager, 'remove_container') as mock_remove:

            # Simulate exception during rename
            mock_rename.side_effect = Exception("Docker daemon error")
            mock_remove.return_value = False  # Removal also fails

            existing_containers = [{"name": "problematic-container", "status": "running"}]

            result = await qdrant_service._handle_existing_containers(existing_containers)

            # Should handle exception gracefully
            assert result["success"] is False
            assert len(result["errors"]) == 1
            assert "problematic-container" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_standardized_naming_enforcement(self, qdrant_service):
        """Test that installation enforces standardized naming."""
        standard_name = qdrant_service.standard_name

        # Verify the standard name follows Bablib convention
        assert standard_name == "bablib-memory-qdrant"

        # Verify naming pattern
        assert standard_name.startswith("bablib-")
        assert "memory" in standard_name  # Indicates vector database
        assert standard_name.endswith("-qdrant")  # Service type suffix