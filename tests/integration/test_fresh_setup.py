"""Integration test fresh system setup workflow."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from src.services.installation_wizard_service import InstallationWizardService
from src.services.system_requirements_service import SystemRequirementsService
from src.services.docker_service_manager import DockerServiceManager
from src.services.qdrant_container_service import QdrantContainerService
from src.models.service_configuration import ServiceStatus
from src.models.installation_profile import InstallationState


class TestFreshSetup:
    """Test fresh system setup workflow with no existing components."""

    @pytest.fixture
    def wizard_service(self):
        """Create installation wizard service for testing."""
        return InstallationWizardService()

    @pytest.fixture
    def mock_clean_system(self):
        """Mock a clean system with no existing Bablib components."""
        with patch('src.services.system_requirements_service.SystemRequirementsService.validate_all_requirements') as mock_validate, \
             patch('src.services.docker_service_manager.DockerServiceManager.validate_docker_availability') as mock_docker, \
             patch('src.services.docker_service_manager.DockerServiceManager.list_bablib_containers') as mock_containers, \
             patch('src.services.qdrant_container_service.QdrantContainerService._find_existing_qdrant_containers') as mock_existing:

            # Clean system with all requirements met
            mock_validate.return_value = {
                "python_version": True,
                "memory": True,
                "disk": True,
                "docker": True,
                "architecture": True
            }
            mock_docker.return_value = True
            mock_containers.return_value = []  # No existing containers
            mock_existing.return_value = []   # No existing Qdrant containers

            yield {
                'validate': mock_validate,
                'docker': mock_docker,
                'containers': mock_containers,
                'existing': mock_existing
            }

    @pytest.fixture
    def mock_qdrant_installation(self):
        """Mock successful Qdrant installation."""
        with patch('src.services.qdrant_container_service.QdrantContainerService.install_qdrant') as mock_install, \
             patch('src.services.qdrant_container_service.QdrantContainerService.get_qdrant_status') as mock_status, \
             patch('src.services.qdrant_container_service.QdrantContainerService._wait_for_qdrant_ready') as mock_ready:

            mock_install.return_value = {
                "success": True,
                "container_name": "bablib-memory-qdrant",
                "image": "qdrant/qdrant:v1.12.1",
                "port": 6333,
                "grpc_port": 6334,
                "ready": True,
                "url": "http://localhost:6333",
                "data_volume": "bablib-qdrant-data"
            }

            # Mock running status after installation
            mock_status_obj = MagicMock()
            mock_status_obj.status = ServiceStatus.RUNNING
            mock_status_obj.service_name = "qdrant"
            mock_status_obj.container_name = "bablib-memory-qdrant"
            mock_status_obj.port = 6333
            mock_status_obj.health_check_url = "http://localhost:6333/health"
            mock_status.return_value = mock_status_obj

            mock_ready.return_value = True

            yield {
                'install': mock_install,
                'status': mock_status,
                'ready': mock_ready
            }

    @pytest.fixture
    def mock_mcp_config(self):
        """Mock MCP configuration generation."""
        with patch('src.services.mcp_configuration_service.MCPConfigurationService.generate_universal_config') as mock_generate, \
             patch('src.services.mcp_configuration_service.MCPConfigurationService.validate_config') as mock_validate, \
             patch('src.services.mcp_configuration_service.MCPConfigurationService.save_config') as mock_save:

            mock_generate.return_value = {
                "server_name": "bablib",
                "server_url": "http://localhost:8765",
                "api_version": "1.0",
                "capabilities": ["search", "crawl", "embed", "status"]
            }
            mock_validate.return_value = True
            mock_save.return_value = True

            yield {
                'generate': mock_generate,
                'validate': mock_validate,
                'save': mock_save
            }

    @pytest.mark.asyncio
    async def test_fresh_setup_complete_workflow(self, wizard_service, mock_clean_system, mock_qdrant_installation, mock_mcp_config):
        """Test complete fresh installation workflow."""
        # Mock progress service to avoid UI issues in tests
        with patch.object(wizard_service.progress_service, 'start_live_display') as mock_display:
            mock_display.return_value = None

            # Run installation
            result = await wizard_service.start_installation(
                force_reinstall=False,
                custom_qdrant_port=None,
                custom_data_dir=None
            )

            # Verify successful installation
            assert result["success"] is True
            assert "profile" in result
            assert "results" in result
            assert "services" in result

            # Verify installation profile
            profile = result["profile"]
            assert profile["state"] == InstallationState.COMPLETED.value
            assert profile["installation_completed_at"] is not None

            # Verify services were configured
            services = result["services"]
            assert len(services) > 0

            qdrant_service = next((s for s in services if s["service_name"] == "qdrant"), None)
            assert qdrant_service is not None
            assert qdrant_service["status"] == "RUNNING"
            assert qdrant_service["container_name"] == "bablib-memory-qdrant"
            assert qdrant_service["port"] == 6333

    @pytest.mark.asyncio
    async def test_fresh_setup_system_requirements_check(self, wizard_service, mock_clean_system):
        """Test that system requirements are properly validated during fresh setup."""
        with patch.object(wizard_service.progress_service, 'start_live_display'):
            # Mock system service to test requirement validation
            with patch.object(wizard_service, 'system_service') as mock_system_service:
                mock_system_service._validate_python_version.return_value = True
                mock_system_service.validate_all_requirements = AsyncMock(return_value={
                    "python_version": True,
                    "memory": True,
                    "disk": True,
                    "docker": True,
                    "architecture": True
                })

                # Mock other services to avoid actual operations
                wizard_service.qdrant_service.install_qdrant = AsyncMock(return_value={"success": True, "container_name": "bablib-memory-qdrant"})
                wizard_service.qdrant_service.get_qdrant_status = AsyncMock()
                wizard_service.qdrant_service.get_qdrant_status.return_value.status = ServiceStatus.RUNNING
                wizard_service.mcp_service.generate_universal_config = MagicMock(return_value={})
                wizard_service.mcp_service.validate_config = MagicMock(return_value=True)
                wizard_service.mcp_service.save_config = MagicMock(return_value=True)
                wizard_service.mcp_service.get_default_config_path = MagicMock(return_value=Path("/tmp/test.json"))

                result = await wizard_service.start_installation()

                # Verify system requirements were checked
                mock_system_service._validate_python_version.assert_called_once()
                mock_system_service.validate_all_requirements.assert_called_once()

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fresh_setup_standardized_naming(self, wizard_service, mock_clean_system, mock_qdrant_installation):
        """Test that fresh setup uses standardized container naming."""
        with patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.mcp_service, 'generate_universal_config', return_value={}), \
             patch.object(wizard_service.mcp_service, 'validate_config', return_value=True), \
             patch.object(wizard_service.mcp_service, 'save_config', return_value=True), \
             patch.object(wizard_service.mcp_service, 'get_default_config_path', return_value=Path("/tmp/test.json")):

            Path("/tmp/test.json").touch()  # Create mock file

            result = await wizard_service.start_installation()

            # Verify Qdrant was installed with standard naming
            mock_qdrant_installation['install'].assert_called_once()
            call_args = mock_qdrant_installation['install'].call_args
            assert call_args.kwargs['force_rename'] is True

            # Verify result contains standardized container name
            assert result["success"] is True
            services = result["services"]
            qdrant_service = next((s for s in services if s["service_name"] == "qdrant"), None)
            assert qdrant_service["container_name"] == "bablib-memory-qdrant"

    @pytest.mark.asyncio
    async def test_fresh_setup_mcp_config_generation(self, wizard_service, mock_clean_system, mock_qdrant_installation, mock_mcp_config):
        """Test that MCP configuration is properly generated during fresh setup."""
        with patch.object(wizard_service.progress_service, 'start_live_display'):
            result = await wizard_service.start_installation()

            # Verify MCP config generation was called
            mock_mcp_config['generate'].assert_called_once()
            call_args = mock_mcp_config['generate'].call_args
            assert call_args.kwargs['server_url'] == "http://localhost:8765"
            assert "search" in call_args.kwargs['capabilities']
            assert "crawl" in call_args.kwargs['capabilities']
            assert "embed" in call_args.kwargs['capabilities']

            # Verify config validation and saving
            mock_mcp_config['validate'].assert_called_once()
            mock_mcp_config['save'].assert_called_once()

            assert result["success"] is True
            assert "mcp_config_path" in result

    @pytest.mark.asyncio
    async def test_fresh_setup_progress_tracking(self, wizard_service, mock_clean_system, mock_qdrant_installation, mock_mcp_config):
        """Test that progress tracking works correctly during fresh setup."""
        # Track progress service calls
        progress_calls = []

        def mock_execute_step(step_id, step_function, *args, **kwargs):
            progress_calls.append(step_id)
            return asyncio.create_task(step_function())

        with patch.object(wizard_service.progress_service, 'start_live_display') as mock_start, \
             patch.object(wizard_service.progress_service, 'run_installation_sequence') as mock_run, \
             patch.object(wizard_service.progress_service, 'display_final_summary') as mock_summary:

            # Mock sequence runner to capture step execution
            async def mock_sequence(step_functions, stop_on_failure=True):
                results = {"success": True, "completed_steps": [], "failed_steps": []}
                for step_id, step_function in step_functions.items():
                    try:
                        success = await step_function()
                        if success:
                            results["completed_steps"].append(step_id)
                        else:
                            results["failed_steps"].append(step_id)
                            if stop_on_failure:
                                results["success"] = False
                                break
                    except Exception:
                        results["failed_steps"].append(step_id)
                        if stop_on_failure:
                            results["success"] = False
                            break
                return results

            mock_run.side_effect = mock_sequence

            result = await wizard_service.start_installation()

            # Verify progress tracking components were called
            mock_start.assert_called_once()
            mock_run.assert_called_once()
            mock_summary.assert_called_once()

            # Verify sequence included expected steps
            call_args = mock_run.call_args[0][0]
            expected_steps = [
                "system_check",
                "docker_check",
                "requirements_validation",
                "docker_network_setup",
                "qdrant_installation",
                "qdrant_validation",
                "mcp_config_generation",
                "final_validation"
            ]

            for step in expected_steps:
                assert step in call_args, f"Missing step: {step}"

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fresh_setup_failure_handling(self, wizard_service, mock_clean_system):
        """Test that fresh setup handles failures gracefully."""
        with patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.progress_service, 'run_installation_sequence') as mock_run, \
             patch.object(wizard_service.progress_service, 'display_final_summary'):

            # Mock a failure during Qdrant installation
            async def mock_sequence_with_failure(step_functions, stop_on_failure=True):
                results = {"success": False, "completed_steps": ["system_check"], "failed_steps": ["qdrant_installation"]}
                return results

            mock_run.side_effect = mock_sequence_with_failure

            result = await wizard_service.start_installation()

            # Verify failure is properly handled
            assert result["success"] is False
            assert "results" in result
            assert len(result["results"]["failed_steps"]) > 0
            assert "profile" in result

            # Profile should show failed state
            profile = result["profile"]
            assert profile["state"] == InstallationState.FAILED.value

    @pytest.mark.asyncio
    async def test_fresh_setup_custom_configuration(self, wizard_service, mock_clean_system, mock_qdrant_installation, mock_mcp_config):
        """Test fresh setup with custom port and data directory configuration."""
        with patch.object(wizard_service.progress_service, 'start_live_display'):
            custom_port = 6334
            custom_data_dir = "/tmp/qdrant-data"

            result = await wizard_service.start_installation(
                force_reinstall=False,
                custom_qdrant_port=custom_port,
                custom_data_dir=custom_data_dir
            )

            # Verify custom configuration was passed to Qdrant installation
            mock_qdrant_installation['install'].assert_called_once()
            call_args = mock_qdrant_installation['install'].call_args
            assert call_args.kwargs['custom_port'] == custom_port
            assert call_args.kwargs['data_dir'] == custom_data_dir

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fresh_setup_installation_timing(self, wizard_service, mock_clean_system, mock_qdrant_installation, mock_mcp_config):
        """Test that fresh setup completes within performance targets (<30s)."""
        import time

        with patch.object(wizard_service.progress_service, 'start_live_display'):
            start_time = time.time()

            result = await wizard_service.start_installation()

            end_time = time.time()
            installation_time = end_time - start_time

            # Verify installation completes within 30 seconds (generous for mocked operations)
            assert installation_time < 30.0, f"Installation took {installation_time:.2f}s, expected <30s"
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fresh_setup_service_health_validation(self, wizard_service, mock_clean_system, mock_qdrant_installation, mock_mcp_config):
        """Test that fresh setup validates service health after installation."""
        with patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service, '_get_service_configurations') as mock_get_services:

            # Mock service configurations with healthy status
            mock_get_services.return_value = [{
                "service_name": "qdrant",
                "container_name": "bablib-memory-qdrant",
                "status": "RUNNING",
                "port": 6333
            }]

            result = await wizard_service.start_installation()

            # Verify service configurations were retrieved for validation
            mock_get_services.assert_called()

            assert result["success"] is True
            assert len(result["services"]) > 0

            # Verify service is in healthy state
            qdrant_service = result["services"][0]
            assert qdrant_service["status"] == "RUNNING"