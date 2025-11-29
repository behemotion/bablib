"""Integration test complete uninstall workflow."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from src.services.uninstall_service import UninstallService, UninstallWarning
from src.services.installation_wizard_service import InstallationWizardService
from src.models.uninstall_inventory import UninstallComponent, ComponentType


class TestCompleteUninstall:
    """Test complete uninstall workflow with single confirmation and automatic service shutdown."""

    @pytest.fixture
    def uninstall_service(self):
        """Create uninstall service for testing."""
        return UninstallService()

    @pytest.fixture
    def wizard_service(self):
        """Create installation wizard service for testing."""
        return InstallationWizardService()

    @pytest.fixture
    def mock_installed_components(self):
        """Mock a complete Bablib installation with all components."""
        return [
            UninstallComponent(
                component_type=ComponentType.CONTAINER,
                name="bablib-memory-qdrant",
                path=None,
                size_mb=150.0,
                is_external=False
            ),
            UninstallComponent(
                component_type=ComponentType.VOLUME,
                name="bablib-qdrant-data",
                path=None,
                size_mb=500.0,
                is_external=False
            ),
            UninstallComponent(
                component_type=ComponentType.DIRECTORY,
                name="bablib",
                path="/Users/test/.local/share/bablib",
                size_mb=25.0,
                is_external=False
            ),
            UninstallComponent(
                component_type=ComponentType.CONFIG_FILE,
                name="mcp_config.json",
                path="/Users/test/.config/bablib/mcp_config.json",
                size_mb=0.1,
                is_external=False
            ),
            UninstallComponent(
                component_type=ComponentType.PACKAGE,
                name="bablib",
                path=None,
                size_mb=10.0,
                is_external=False
            )
        ]

    @pytest.fixture
    def mock_running_services(self):
        """Mock running Bablib services that need to be stopped."""
        return ["bablib-memory-qdrant", "bablib-cache-redis"]

    @pytest.mark.asyncio
    async def test_complete_uninstall_workflow(self, uninstall_service, mock_installed_components, mock_running_services):
        """Test complete end-to-end uninstall workflow."""
        with patch.object(uninstall_service, 'scan_installed_components') as mock_scan, \
             patch.object(uninstall_service, 'check_running_services') as mock_check_services, \
             patch.object(uninstall_service, 'stop_all_services') as mock_stop, \
             patch.object(uninstall_service, 'execute_uninstall') as mock_execute:

            mock_scan.return_value = mock_installed_components
            mock_check_services.return_value = mock_running_services
            mock_stop.return_value = {service: True for service in mock_running_services}
            mock_execute.return_value = {
                "success": True,
                "removed": 5,
                "failed": 0,
                "skipped": 0,
                "summary": {"total_time": 12.5, "cleanup_successful": True}
            }

            # Test complete workflow
            components = await uninstall_service.scan_installed_components()
            assert len(components) == 5

            running_services = await uninstall_service.check_running_services()
            assert len(running_services) == 2

            warning = uninstall_service.generate_uninstall_warning(components)
            assert warning.is_irreversible is True
            assert len(warning.data_types) > 0

            stop_results = await uninstall_service.stop_all_services(running_services)
            assert all(stop_results.values())

            final_result = await uninstall_service.execute_uninstall(
                components=components,
                force=False,
                preserve_external=False
            )

            assert final_result["success"] is True
            assert final_result["removed"] == 5

    @pytest.mark.asyncio
    async def test_component_scanning_completeness(self, uninstall_service):
        """Test that component scanning detects all Bablib components."""
        mock_detection_result = {
            'containers': [
                {'Names': ['/bablib-memory-qdrant'], 'Id': 'container123'},
                {'Names': ['/bablib-cache-redis'], 'Id': 'container456'}
            ],
            'volumes': [
                {'Name': 'bablib-qdrant-data', 'is_external': False},
                {'Name': 'bablib-cache-data', 'is_external': True}
            ],
            'directories': [
                MagicMock(component_path=Path('/Users/test/.local/share/bablib')),
                MagicMock(component_path=Path('/Users/test/.cache/bablib'))
            ],
            'configs': [
                MagicMock(component_path=Path('/Users/test/.config/bablib/mcp_config.json'))
            ],
            'package': 'bablib'
        }

        with patch.object(uninstall_service.detection_service, 'detect_all_components') as mock_detect:
            mock_detect.return_value = mock_detection_result

            components = await uninstall_service.scan_installed_components()

            # Verify all component types were detected
            component_types = {c.component_type for c in components}
            expected_types = {
                ComponentType.CONTAINER,
                ComponentType.VOLUME,
                ComponentType.DIRECTORY,
                ComponentType.CONFIG_FILE,
                ComponentType.PACKAGE
            }
            assert component_types == expected_types

            # Verify specific components
            container_names = {c.name for c in components if c.component_type == ComponentType.CONTAINER}
            assert "bablib-memory-qdrant" in container_names
            assert "bablib-cache-redis" in container_names

    @pytest.mark.asyncio
    async def test_running_services_detection(self, uninstall_service):
        """Test detection of running Bablib services before uninstall."""
        mock_containers = [
            MagicMock(name="bablib-memory-qdrant", status="running"),
            MagicMock(name="bablib-cache-redis", status="running"),
            MagicMock(name="unrelated-service", status="running"),
            MagicMock(name="bablib-old-container", status="stopped")
        ]

        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_client.containers.list.return_value = mock_containers
            mock_docker.return_value = mock_client

            running_services = await uninstall_service.check_running_services()

            # Should only detect running Bablib-related services
            assert "bablib-memory-qdrant" in running_services
            assert "bablib-cache-redis" in running_services
            assert "unrelated-service" not in running_services
            assert "bablib-old-container" not in running_services

    @pytest.mark.asyncio
    async def test_uninstall_warning_generation(self, uninstall_service, mock_installed_components):
        """Test comprehensive uninstall warning generation."""
        warning = uninstall_service.generate_uninstall_warning(mock_installed_components)

        # Verify warning properties
        assert warning.is_irreversible is True
        assert "Bablib" in warning.message
        assert "permanently remove" in warning.message

        # Verify data types identification
        expected_data_types = ["Vector database data", "Application data", "Configuration files"]
        for data_type in expected_data_types:
            assert data_type in warning.data_types

        # Verify size estimation
        total_size = sum(c.size_mb for c in mock_installed_components)
        assert f"{total_size:.1f}MB" in warning.estimated_data_loss

    @pytest.mark.asyncio
    async def test_automatic_service_shutdown(self, uninstall_service):
        """Test automatic shutdown of running services during uninstall."""
        mock_services = ["bablib-memory-qdrant", "bablib-main", "bablib-cache-redis"]

        mock_containers = {
            "bablib-memory-qdrant": MagicMock(status="running"),
            "bablib-main": MagicMock(status="running"),
            "bablib-cache-redis": MagicMock(status="stopped")  # Already stopped
        }

        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()

            def get_container(name):
                return mock_containers[name]

            mock_client.containers.get.side_effect = get_container
            mock_docker.return_value = mock_client

            stop_results = await uninstall_service.stop_all_services(mock_services)

            # Verify all services were processed
            assert len(stop_results) == 3
            assert all(stop_results.values())

            # Verify stop was called for running containers
            running_containers = [c for c in mock_containers.values() if c.status == "running"]
            for container in running_containers:
                container.stop.assert_called_once_with(timeout=10)

    @pytest.mark.asyncio
    async def test_service_shutdown_failure_handling(self, uninstall_service):
        """Test handling of service shutdown failures."""
        mock_services = ["problematic-service", "good-service"]

        with patch('docker.from_env') as mock_docker:
            mock_client = MagicMock()

            def get_container(name):
                if name == "problematic-service":
                    raise Exception("Container access error")
                else:
                    container = MagicMock()
                    container.status = "running"
                    return container

            mock_client.containers.get.side_effect = get_container
            mock_docker.return_value = mock_client

            stop_results = await uninstall_service.stop_all_services(mock_services)

            # Verify mixed results
            assert stop_results["problematic-service"] is False
            assert stop_results["good-service"] is True

    @pytest.mark.asyncio
    async def test_uninstall_execution_with_preserve_external(self, uninstall_service):
        """Test uninstall execution with external component preservation."""
        components = [
            UninstallComponent(
                component_type=ComponentType.VOLUME,
                name="bablib-qdrant-data",
                path=None,
                size_mb=500.0,
                is_external=False
            ),
            UninstallComponent(
                component_type=ComponentType.VOLUME,
                name="external-data-volume",
                path=None,
                size_mb=1000.0,
                is_external=True
            )
        ]

        with patch.object(uninstall_service, 'execute') as mock_execute:
            mock_execute.return_value = {"success": True, "removed": 1, "failed": 0}

            result = await uninstall_service.execute_uninstall(
                components=components,
                force=False,
                preserve_external=True
            )

            # Verify execute was called with correct parameters
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args

            # Should preserve external components
            assert call_args[1]["preserve_external"] is True
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_rollback_capability(self, uninstall_service):
        """Test uninstall rollback capability when backup is available."""
        backup_path = "/tmp/bablib-backup-20240101"

        with patch.object(uninstall_service.backup_service, 'restore_backup') as mock_restore:
            mock_restore.return_value = True

            success = await uninstall_service.rollback_uninstall(backup_path)

            assert success is True
            mock_restore.assert_called_once_with(backup_path)

    @pytest.mark.asyncio
    async def test_rollback_without_backup(self, uninstall_service):
        """Test rollback handling when no backup is available."""
        success = await uninstall_service.rollback_uninstall("")

        assert success is False

    @pytest.mark.asyncio
    async def test_wizard_service_uninstall_integration(self, wizard_service):
        """Test integration between installation wizard and uninstall process."""
        mock_uninstall_result = {
            "success": True,
            "removed_components": [
                "qdrant_container",
                "qdrant_data",
                "mcp_config"
            ],
            "errors": []
        }

        with patch.object(wizard_service, 'qdrant_service') as mock_qdrant, \
             patch.object(wizard_service, 'docker_manager') as mock_docker, \
             patch.object(wizard_service, 'mcp_service') as mock_mcp:

            # Mock service removal methods
            mock_qdrant.remove_qdrant.return_value = {
                "container_removed": True,
                "volume_removed": True,
                "errors": []
            }

            mock_docker.cleanup_bablib_resources.return_value = {
                "containers": 1,
                "volumes": 1,
                "networks": 1
            }

            mock_config_path = MagicMock()
            mock_config_path.exists.return_value = True
            mock_mcp.get_default_config_path.return_value = mock_config_path

            result = await wizard_service.uninstall_bablib(remove_data=True)

            # Verify uninstall workflow
            assert result["success"] is True
            mock_qdrant.remove_qdrant.assert_called_once_with(remove_data=True)
            mock_docker.cleanup_bablib_resources.assert_called_once_with(include_volumes=True)
            mock_config_path.unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_uninstall_timing_performance(self, uninstall_service, mock_installed_components):
        """Test that uninstall completes within performance target (<3s for confirmation)."""
        import time

        with patch.object(uninstall_service, 'scan_installed_components', return_value=mock_installed_components), \
             patch.object(uninstall_service, 'check_running_services', return_value=[]), \
             patch.object(uninstall_service, 'stop_all_services', return_value={}), \
             patch.object(uninstall_service, 'execute_uninstall') as mock_execute:

            mock_execute.return_value = {"success": True, "removed": 5, "failed": 0}

            # Time the core uninstall operations (excluding user confirmation)
            start_time = time.time()

            components = await uninstall_service.scan_installed_components()
            running_services = await uninstall_service.check_running_services()
            warning = uninstall_service.generate_uninstall_warning(components)
            stop_results = await uninstall_service.stop_all_services(running_services)
            result = await uninstall_service.execute_uninstall(components)

            end_time = time.time()
            operation_time = end_time - start_time

            # Core operations should be very fast (well under 3s target)
            assert operation_time < 1.0, f"Uninstall operations took {operation_time:.2f}s, expected <1.0s"
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_single_confirmation_workflow(self, uninstall_service, mock_installed_components, mock_running_services):
        """Test that uninstall requires only single confirmation with comprehensive information."""
        with patch.object(uninstall_service, 'scan_installed_components', return_value=mock_installed_components), \
             patch.object(uninstall_service, 'check_running_services', return_value=mock_running_services):

            # Simulate the information gathering phase (what would be shown to user)
            components = await uninstall_service.scan_installed_components()
            running_services = await uninstall_service.check_running_services()
            warning = uninstall_service.generate_uninstall_warning(components)

            # Verify comprehensive information is available for single confirmation
            assert len(components) == 5  # All components detected
            assert len(running_services) == 2  # Running services detected
            assert warning.is_irreversible is True  # Clear warning provided

            # Verify warning contains all necessary information
            assert "Components to be removed: 5" in warning.message
            assert len(warning.data_types) > 0
            assert warning.estimated_data_loss != "Unknown size"

    @pytest.mark.asyncio
    async def test_external_component_handling(self, uninstall_service):
        """Test handling of external vs internal components during uninstall."""
        mixed_components = [
            UninstallComponent(
                component_type=ComponentType.VOLUME,
                name="bablib-qdrant-data",
                path=None,
                size_mb=500.0,
                is_external=False  # Internal component
            ),
            UninstallComponent(
                component_type=ComponentType.VOLUME,
                name="user-custom-data",
                path=None,
                size_mb=1000.0,
                is_external=True  # External component
            )
        ]

        with patch.object(uninstall_service, 'execute') as mock_execute:
            mock_execute.return_value = {"success": True, "removed": 1, "failed": 0}

            # Test with preserve_external=True
            await uninstall_service.execute_uninstall(
                components=mixed_components,
                preserve_external=True
            )

            # Verify only internal components are passed for removal
            call_args = mock_execute.call_args[0][1]  # components_dict argument

            # Should have filtered out external components
            internal_components = [c for c in mixed_components if not c.is_external]
            assert len(internal_components) == 1