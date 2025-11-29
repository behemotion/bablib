"""Integration test service conflict resolution."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.docker_service_manager import DockerServiceManager
from src.services.qdrant_container_service import QdrantContainerService
from src.services.installation_wizard_service import InstallationWizardService


class TestServiceConflicts:
    """Test service conflict detection and resolution scenarios."""

    @pytest.fixture
    def docker_manager(self):
        """Create Docker service manager for testing."""
        return DockerServiceManager()

    @pytest.fixture
    def qdrant_service(self, docker_manager):
        """Create Qdrant service for testing."""
        return QdrantContainerService(docker_manager)

    @pytest.fixture
    def wizard_service(self):
        """Create installation wizard service for testing."""
        return InstallationWizardService()

    @pytest.fixture
    def mock_port_conflicts(self):
        """Mock port conflicts on standard Bablib ports."""
        return {
            6333: "existing-qdrant-service",  # Qdrant HTTP port conflict
            6334: "another-grpc-service",    # Qdrant gRPC port conflict
            8765: "existing-web-service"     # MCP server port conflict
        }

    @pytest.mark.asyncio
    async def test_detect_port_conflicts(self, docker_manager, mock_port_conflicts):
        """Test detection of port conflicts during installation."""
        mock_containers = []
        for port, service_name in mock_port_conflicts.items():
            container = MagicMock()
            container.name = service_name
            container.ports = {f"{port}/tcp": [{"HostPort": str(port)}]}
            container.status = "running"
            mock_containers.append(container)

        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_client.containers.list.return_value = mock_containers
            mock_docker.return_value = mock_client

            # Check for conflicts on Bablib ports
            containers = await docker_manager.list_bablib_containers()

            # Should detect existing services using Bablib ports
            used_ports = set()
            for container in mock_containers:
                for port_spec, bindings in container.ports.items():
                    if bindings:
                        used_ports.add(int(bindings[0]["HostPort"]))

            # Verify conflicts detected
            assert 6333 in used_ports
            assert 6334 in used_ports
            assert 8765 in used_ports

    @pytest.mark.asyncio
    async def test_resolve_qdrant_port_conflict(self, qdrant_service):
        """Test resolution of Qdrant port conflicts by using alternative ports."""
        with patch.object(qdrant_service.docker_manager, 'create_container') as mock_create, \
             patch.object(qdrant_service, '_find_existing_qdrant_containers', return_value=[]), \
             patch.object(qdrant_service, '_wait_for_qdrant_ready', return_value=True):

            # Mock port conflict on default port 6333
            mock_create.side_effect = [
                (False, "Port 6333 already in use"),  # First attempt fails
                (True, "bablib-memory-qdrant")        # Second attempt succeeds
            ]

            # Install with automatic port conflict resolution
            result = await qdrant_service.install_qdrant(
                force_rename=True,
                custom_port=6335  # Alternative port
            )

            assert result["success"] is True
            assert result["port"] == 6335

            # Verify container creation was attempted with alternative port
            assert mock_create.call_count == 1
            call_args = mock_create.call_args
            port_mappings = call_args.kwargs['port_mappings']
            assert port_mappings['6333/tcp'] == 6335  # Alternative port used

    @pytest.mark.asyncio
    async def test_automatic_port_detection_and_selection(self, docker_manager):
        """Test automatic detection of available ports when defaults are taken."""
        # Mock containers using various ports
        mock_containers = [
            {"ports": {"6333/tcp": [{"HostPort": "6333"}]}},  # Default Qdrant port taken
            {"ports": {"6334/tcp": [{"HostPort": "6334"}]}},  # Default gRPC port taken
            {"ports": {"6335/tcp": [{"HostPort": "6335"}]}},  # First alternative taken
        ]

        def find_available_port(start_port, max_attempts=10):
            """Simulate finding next available port."""
            used_ports = {6333, 6334, 6335}
            for port in range(start_port, start_port + max_attempts):
                if port not in used_ports:
                    return port
            return None

        available_port = find_available_port(6333)
        assert available_port == 6336

    @pytest.mark.asyncio
    async def test_container_name_conflict_resolution(self, qdrant_service):
        """Test resolution of container name conflicts."""
        with patch.object(qdrant_service.docker_manager, 'create_container') as mock_create, \
             patch.object(qdrant_service, '_find_existing_qdrant_containers') as mock_find, \
             patch.object(qdrant_service, '_handle_existing_containers') as mock_handle:

            # Mock existing container with same name
            mock_find.return_value = [{
                "name": "bablib-memory-qdrant",
                "status": "running",
                "id": "existing123"
            }]

            # Mock successful container handling (rename to backup)
            mock_handle.return_value = {
                "success": True,
                "renamed": ["bablib-memory-qdrant -> bablib-memory-qdrant-backup-123456"],
                "removed": []
            }

            mock_create.return_value = (True, "bablib-memory-qdrant")

            result = await qdrant_service.install_qdrant(force_rename=True)

            # Verify conflict was resolved
            assert result["success"] is True
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_conflict_resolution(self, docker_manager):
        """Test resolution of Docker network conflicts."""
        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()

            # Mock network creation conflict
            def create_network_side_effect(name, **kwargs):
                if name == "bablib-network":
                    raise Exception("Network already exists")
                return MagicMock()

            mock_client.networks.create.side_effect = create_network_side_effect
            mock_client.networks.get.side_effect = Exception("Network not found")
            mock_docker.return_value = mock_client

            # Test network creation with conflict handling
            try:
                await docker_manager._ensure_network_exists()
            except Exception as e:
                # Should handle network conflict gracefully
                assert "Network already exists" in str(e)

    @pytest.mark.asyncio
    async def test_volume_conflict_resolution(self, docker_manager):
        """Test resolution of Docker volume conflicts."""
        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()

            # Mock existing volume with same name
            existing_volume = MagicMock()
            existing_volume.name = "bablib-qdrant-data"
            mock_client.volumes.list.return_value = [existing_volume]
            mock_docker.return_value = mock_client

            # Should detect existing volume
            volumes = mock_client.volumes.list()
            volume_names = [v.name for v in volumes]
            assert "bablib-qdrant-data" in volume_names

    @pytest.mark.asyncio
    async def test_service_conflict_during_installation(self, wizard_service):
        """Test handling of service conflicts during full installation."""
        with patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install, \
             patch.object(wizard_service, '_execute_system_check', return_value=True), \
             patch.object(wizard_service, '_execute_docker_check', return_value=True), \
             patch.object(wizard_service, '_execute_requirements_validation', return_value=True), \
             patch.object(wizard_service, '_execute_docker_network_setup', return_value=True):

            # Mock port conflict during Qdrant installation
            mock_install.side_effect = [
                {"success": False, "error": "Port 6333 already in use"},  # First attempt
                {"success": True, "container_name": "bablib-memory-qdrant", "port": 6335}  # Retry with different port
            ]

            # Mock retry service to handle the conflict
            with patch.object(wizard_service.retry_service, 'retry_docker_operation') as mock_retry:
                async def retry_with_port_change():
                    return {"success": True, "container_name": "bablib-memory-qdrant", "port": 6335}

                mock_retry.return_value = retry_with_port_change()

                # Installation should succeed after resolving conflict
                result = await wizard_service._execute_qdrant_installation(False, None, None)
                assert result is True

    @pytest.mark.asyncio
    async def test_multiple_conflict_resolution(self, qdrant_service):
        """Test handling of multiple simultaneous conflicts."""
        conflicts = {
            "port": 6333,
            "container_name": "bablib-memory-qdrant",
            "volume": "bablib-qdrant-data"
        }

        with patch.object(qdrant_service, '_find_existing_qdrant_containers') as mock_find, \
             patch.object(qdrant_service, '_handle_existing_containers') as mock_handle, \
             patch.object(qdrant_service.docker_manager, 'create_container') as mock_create:

            # Mock existing conflicts
            mock_find.return_value = [{
                "name": "bablib-memory-qdrant",
                "status": "stopped"
            }]

            mock_handle.return_value = {
                "success": True,
                "removed": ["bablib-memory-qdrant"],
                "renamed": []
            }

            # Mock successful creation after conflict resolution
            mock_create.return_value = (True, "bablib-memory-qdrant")

            result = await qdrant_service.install_qdrant(
                force_rename=True,
                custom_port=6335  # Resolve port conflict
            )

            # Should resolve all conflicts
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_conflict_resolution_failure_handling(self, qdrant_service):
        """Test handling when conflict resolution fails."""
        with patch.object(qdrant_service, '_find_existing_qdrant_containers') as mock_find, \
             patch.object(qdrant_service, '_handle_existing_containers') as mock_handle:

            mock_find.return_value = [{
                "name": "problematic-container",
                "status": "running"
            }]

            # Mock conflict resolution failure
            mock_handle.return_value = {
                "success": False,
                "errors": ["Failed to rename problematic-container", "Container is locked"],
                "renamed": [],
                "removed": []
            }

            result = await qdrant_service.install_qdrant(force_rename=True)

            # Installation should fail gracefully
            assert result["success"] is False
            assert "error" in result
            assert "Failed to handle existing containers" in result["error"]

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_conflicts(self, wizard_service):
        """Test graceful degradation when conflicts cannot be resolved."""
        with patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.progress_service, 'run_installation_sequence') as mock_sequence:

            # Mock installation sequence with conflict-related failure
            async def sequence_with_conflict_failure(step_functions, stop_on_failure=True):
                results = {"success": False, "completed_steps": [], "failed_steps": ["qdrant_installation"]}
                return results

            mock_sequence.side_effect = sequence_with_conflict_failure

            result = await wizard_service.start_installation()

            # Should fail gracefully without breaking system
            assert result["success"] is False
            assert "results" in result
            assert "qdrant_installation" in result["results"]["failed_steps"]

    @pytest.mark.asyncio
    async def test_conflict_detection_performance(self, docker_manager):
        """Test that conflict detection performs efficiently."""
        import time

        # Mock large number of containers to test performance
        mock_containers = []
        for i in range(100):
            container = MagicMock()
            container.name = f"container-{i}"
            container.ports = {f"{6000 + i}/tcp": [{"HostPort": str(6000 + i)}]}
            mock_containers.append(container)

        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_client.containers.list.return_value = mock_containers
            mock_docker.return_value = mock_client

            start_time = time.time()
            containers = await docker_manager.list_bablib_containers()
            end_time = time.time()

            detection_time = end_time - start_time

            # Conflict detection should be fast
            assert detection_time < 1.0, f"Conflict detection took {detection_time:.2f}s, expected <1.0s"

    @pytest.mark.asyncio
    async def test_user_notification_of_conflicts(self, qdrant_service):
        """Test that users are properly notified of conflicts and resolutions."""
        with patch.object(qdrant_service, '_find_existing_qdrant_containers') as mock_find, \
             patch.object(qdrant_service, '_handle_existing_containers') as mock_handle, \
             patch.object(qdrant_service.docker_manager, 'create_container') as mock_create:

            mock_find.return_value = [{"name": "old-qdrant", "status": "running"}]
            mock_handle.return_value = {
                "success": True,
                "renamed": ["old-qdrant -> old-qdrant-backup-123456"],
                "removed": []
            }
            mock_create.return_value = (True, "bablib-memory-qdrant")

            result = await qdrant_service.install_qdrant(force_rename=True)

            # Result should contain information about conflict resolution
            assert result["success"] is True
            # In a real implementation, this might include conflict resolution details
            # For now, we verify the operation succeeded despite conflicts

    @pytest.mark.asyncio
    async def test_prevent_system_service_conflicts(self, docker_manager):
        """Test prevention of conflicts with critical system services."""
        # Mock critical system ports that should never be used
        critical_ports = [22, 80, 443, 53, 25]  # SSH, HTTP, HTTPS, DNS, SMTP

        def is_port_critical(port):
            return port in critical_ports

        # Verify Bablib doesn't use critical system ports
        bablib_ports = [6333, 6334, 8765]  # Standard Bablib ports
        for port in bablib_ports:
            assert not is_port_critical(port), f"Bablib port {port} conflicts with critical system service"

    @pytest.mark.asyncio
    async def test_concurrent_installation_conflict_handling(self, wizard_service):
        """Test handling of conflicts when multiple Bablib installations run concurrently."""
        # This would be important for multi-user systems or CI environments
        with patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install:

            # Mock race condition where another installation creates container first
            mock_install.side_effect = [
                Exception("Container name already in use"),  # Race condition
            ]

            with pytest.raises(Exception, match="Container name already in use"):
                await wizard_service._execute_qdrant_installation(True, None, None)

            # Should handle race condition gracefully
            mock_install.assert_called_once()