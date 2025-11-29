"""Integration test upgrade existing installation."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from src.services.installation_wizard_service import InstallationWizardService
from src.models.service_configuration import ServiceStatus
from src.models.installation_profile import InstallationState


class TestUpgradeSetup:
    """Test upgrade scenarios over existing Bablib installations."""

    @pytest.fixture
    def wizard_service(self):
        """Create installation wizard service for testing."""
        return InstallationWizardService()

    @pytest.fixture
    def mock_existing_installation(self):
        """Mock existing Bablib installation with some components."""
        return {
            'status': 'PARTIAL',
            'services': [
                {
                    'service_name': 'qdrant',
                    'container_name': 'old-qdrant-container',  # Non-standard naming
                    'status': 'RUNNING',
                    'port': 6333
                }
            ],
            'mcp_config_exists': False,  # Missing MCP config
            'timestamp': '2024-01-01T12:00:00'
        }

    @pytest.fixture
    def mock_partial_installation(self):
        """Mock partially failed installation state."""
        return {
            'status': 'PARTIAL',
            'services': [
                {
                    'service_name': 'qdrant',
                    'container_name': 'bablib-memory-qdrant',
                    'status': 'STOPPED',  # Service stopped
                    'port': 6333
                }
            ],
            'mcp_config_exists': True,
            'timestamp': '2024-01-01T12:00:00'
        }

    @pytest.mark.asyncio
    async def test_upgrade_with_non_standard_container_naming(self, wizard_service, mock_existing_installation):
        """Test upgrade scenario where existing containers use non-standard naming."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install, \
             patch.object(wizard_service.qdrant_service, 'get_qdrant_status') as mock_get_status, \
             patch.object(wizard_service.mcp_service, 'generate_universal_config') as mock_generate, \
             patch.object(wizard_service.mcp_service, 'validate_config', return_value=True), \
             patch.object(wizard_service.mcp_service, 'save_config', return_value=True), \
             patch.object(wizard_service.mcp_service, 'get_default_config_path', return_value=Path("/tmp/mcp.json")):

            # Mock existing installation status
            mock_status.return_value = mock_existing_installation

            # Mock successful upgrade with container renaming
            mock_install.return_value = {
                "success": True,
                "container_name": "bablib-memory-qdrant",
                "image": "qdrant/qdrant:v1.12.1",
                "port": 6333,
                "ready": True
            }

            mock_status_obj = MagicMock()
            mock_status_obj.status = ServiceStatus.RUNNING
            mock_status_obj.service_name = "qdrant"
            mock_status_obj.container_name = "bablib-memory-qdrant"
            mock_get_status.return_value = mock_status_obj

            mock_generate.return_value = {"server_name": "bablib", "server_url": "http://localhost:8765"}

            Path("/tmp/mcp.json").touch()  # Create mock file

            # Run upgrade installation
            result = await wizard_service.start_installation(force_reinstall=True)

            # Verify upgrade was successful
            assert result["success"] is True

            # Verify Qdrant was installed with force_rename=True (handles non-standard naming)
            mock_install.assert_called_once()
            call_args = mock_install.call_args
            assert call_args.kwargs['force_rename'] is True

            # Verify MCP config was generated (was missing)
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_upgrade_stopped_services(self, wizard_service, mock_partial_installation):
        """Test upgrade scenario where services exist but are stopped."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'start_qdrant') as mock_start, \
             patch.object(wizard_service.qdrant_service, 'get_qdrant_status') as mock_get_status, \
             patch.object(wizard_service.system_service, '_validate_python_version', return_value=True), \
             patch.object(wizard_service.system_service, 'validate_all_requirements') as mock_validate, \
             patch.object(wizard_service.docker_manager, 'validate_docker_availability', return_value=True), \
             patch.object(wizard_service.mcp_service, 'get_default_config_path', return_value=Path("/tmp/mcp.json")):

            mock_status.return_value = mock_partial_installation
            mock_validate.return_value = {"python_version": True, "memory": True, "disk": True, "docker": True}

            # Mock service restart
            mock_start.return_value = True

            mock_status_obj = MagicMock()
            mock_status_obj.status = ServiceStatus.RUNNING
            mock_get_status.return_value = mock_status_obj

            Path("/tmp/mcp.json").touch()

            result = await wizard_service.start_installation(force_reinstall=False)

            # Should succeed by starting existing stopped services
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upgrade_preserves_user_data(self, wizard_service):
        """Test that upgrade preserves existing user data and configurations."""
        existing_data_paths = [
            Path("/tmp/bablib/user_docs"),
            Path("/tmp/bablib/custom_config.json"),
            Path("/tmp/bablib/vector_data")
        ]

        # Create mock existing data
        for path in existing_data_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install:

            mock_status.return_value = {'status': 'PARTIAL', 'services': [], 'mcp_config_exists': False}

            mock_install.return_value = {"success": True, "container_name": "bablib-memory-qdrant"}

            # Run upgrade
            await wizard_service.start_installation(force_reinstall=True)

            # Verify user data paths still exist
            for path in existing_data_paths:
                assert path.exists(), f"User data should be preserved: {path}"

            # Clean up
            for path in existing_data_paths:
                if path.exists():
                    path.unlink()

    @pytest.mark.asyncio
    async def test_upgrade_handles_version_conflicts(self, wizard_service):
        """Test upgrade handling when there are version conflicts."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install, \
             patch.object(wizard_service.qdrant_service, '_find_existing_qdrant_containers') as mock_find:

            mock_status.return_value = {'status': 'PARTIAL', 'services': [], 'mcp_config_exists': True}

            # Mock existing containers with older version
            mock_find.return_value = [{
                "name": "qdrant-old-version",
                "image": "qdrant/qdrant:v1.10.0",  # Older version
                "status": "running"
            }]

            mock_install.return_value = {
                "success": True,
                "container_name": "bablib-memory-qdrant",
                "image": "qdrant/qdrant:v1.12.1"  # Newer version
            }

            result = await wizard_service.start_installation(force_reinstall=True)

            # Should handle version upgrade successfully
            assert result["success"] is True

            # Verify force_rename was used to handle version conflict
            mock_install.assert_called_once()
            call_args = mock_install.call_args
            assert call_args.kwargs['force_rename'] is True

    @pytest.mark.asyncio
    async def test_upgrade_missing_mcp_configuration(self, wizard_service):
        """Test upgrade when MCP configuration is missing or corrupted."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.mcp_service, 'generate_universal_config') as mock_generate, \
             patch.object(wizard_service.mcp_service, 'validate_config') as mock_validate, \
             patch.object(wizard_service.mcp_service, 'save_config') as mock_save, \
             patch.object(wizard_service.mcp_service, 'get_default_config_path') as mock_get_path:

            # Existing installation missing MCP config
            mock_status.return_value = {
                'status': 'PARTIAL',
                'services': [{'service_name': 'qdrant', 'status': 'RUNNING'}],
                'mcp_config_exists': False
            }

            mock_generate.return_value = {"server_name": "bablib"}
            mock_validate.return_value = True
            mock_save.return_value = True
            mock_get_path.return_value = Path("/tmp/new_mcp.json")

            # Mock other services to avoid complex setup
            with patch.object(wizard_service.system_service, '_validate_python_version', return_value=True), \
                 patch.object(wizard_service.system_service, 'validate_all_requirements', return_value={"python_version": True, "docker": True}), \
                 patch.object(wizard_service.docker_manager, 'validate_docker_availability', return_value=True), \
                 patch.object(wizard_service.qdrant_service, 'get_qdrant_status') as mock_qdrant_status:

                mock_status_obj = MagicMock()
                mock_status_obj.status = ServiceStatus.RUNNING
                mock_qdrant_status.return_value = mock_status_obj

                Path("/tmp/new_mcp.json").touch()

                result = await wizard_service.start_installation(force_reinstall=False)

                # Should regenerate missing MCP configuration
                assert result["success"] is True
                mock_generate.assert_called_once()
                mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_upgrade_port_conflicts_resolution(self, wizard_service):
        """Test upgrade handling when there are port conflicts."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install:

            mock_status.return_value = {
                'status': 'PARTIAL',
                'services': [
                    {'service_name': 'qdrant', 'port': 6333, 'status': 'STOPPED'}
                ]
            }

            # Simulate port conflict resolution
            mock_install.return_value = {
                "success": True,
                "container_name": "bablib-memory-qdrant",
                "port": 6334,  # Different port due to conflict resolution
                "original_port": 6333
            }

            result = await wizard_service.start_installation(force_reinstall=True, custom_qdrant_port=6334)

            assert result["success"] is True

            # Verify custom port was used
            mock_install.assert_called_once()
            call_args = mock_install.call_args
            assert call_args.kwargs['custom_port'] == 6334

    @pytest.mark.asyncio
    async def test_upgrade_rollback_on_failure(self, wizard_service):
        """Test upgrade rollback when upgrade process fails."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.progress_service, 'run_installation_sequence') as mock_sequence:

            mock_status.return_value = {
                'status': 'COMPLETED',  # Had working installation
                'services': [{'service_name': 'qdrant', 'status': 'RUNNING'}],
                'mcp_config_exists': True
            }

            # Mock upgrade failure
            mock_sequence.return_value = {
                "success": False,
                "completed_steps": ["system_check"],
                "failed_steps": ["qdrant_installation"],
                "summary": {"error": "Container creation failed"}
            }

            result = await wizard_service.start_installation(force_reinstall=True)

            # Upgrade should fail gracefully
            assert result["success"] is False
            assert "profile" in result
            assert result["profile"]["state"] == InstallationState.FAILED.value

    @pytest.mark.asyncio
    async def test_upgrade_incremental_improvements(self, wizard_service):
        """Test incremental upgrade improvements (e.g., adding missing features)."""
        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.mcp_service, 'generate_universal_config') as mock_generate, \
             patch.object(wizard_service.mcp_service, 'validate_config', return_value=True), \
             patch.object(wizard_service.mcp_service, 'save_config', return_value=True), \
             patch.object(wizard_service.mcp_service, 'get_default_config_path', return_value=Path("/tmp/mcp.json")):

            # Installation exists but with older configuration
            mock_status.return_value = {
                'status': 'COMPLETED',
                'services': [{'service_name': 'qdrant', 'status': 'RUNNING'}],
                'mcp_config_exists': True
            }

            # Mock new universal config with additional capabilities
            mock_generate.return_value = {
                "server_name": "bablib",
                "server_url": "http://localhost:8765",
                "capabilities": ["search", "crawl", "embed", "status"]  # Added "status"
            }

            with patch.object(wizard_service.system_service, '_validate_python_version', return_value=True), \
                 patch.object(wizard_service.system_service, 'validate_all_requirements', return_value={"python_version": True, "docker": True}), \
                 patch.object(wizard_service.docker_manager, 'validate_docker_availability', return_value=True), \
                 patch.object(wizard_service.qdrant_service, 'get_qdrant_status') as mock_qdrant_status:

                mock_status_obj = MagicMock()
                mock_status_obj.status = ServiceStatus.RUNNING
                mock_qdrant_status.return_value = mock_status_obj

                Path("/tmp/mcp.json").touch()

                result = await wizard_service.start_installation(force_reinstall=False)

                # Should update configuration with new capabilities
                assert result["success"] is True
                mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_upgrade_preserves_custom_settings(self, wizard_service):
        """Test that upgrade preserves user's custom settings and configurations."""
        custom_settings = {
            "custom_qdrant_port": 6334,
            "custom_data_dir": "/custom/data/path"
        }

        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.qdrant_service, 'install_qdrant') as mock_install:

            mock_status.return_value = {
                'status': 'COMPLETED',
                'services': [
                    {
                        'service_name': 'qdrant',
                        'port': 6334,  # Custom port
                        'status': 'RUNNING'
                    }
                ]
            }

            mock_install.return_value = {"success": True, "port": 6334}

            # Run upgrade with existing custom settings
            result = await wizard_service.start_installation(
                force_reinstall=True,
                custom_qdrant_port=custom_settings["custom_qdrant_port"],
                custom_data_dir=custom_settings["custom_data_dir"]
            )

            # Verify custom settings were preserved
            assert result["success"] is True
            mock_install.assert_called_once()
            call_args = mock_install.call_args
            assert call_args.kwargs['custom_port'] == custom_settings["custom_qdrant_port"]
            assert call_args.kwargs['data_dir'] == custom_settings["custom_data_dir"]

    @pytest.mark.asyncio
    async def test_upgrade_timing_performance(self, wizard_service):
        """Test that upgrade completes within performance targets."""
        import time

        with patch.object(wizard_service, 'check_installation_status') as mock_status, \
             patch.object(wizard_service.progress_service, 'start_live_display'), \
             patch.object(wizard_service.progress_service, 'run_installation_sequence') as mock_sequence:

            mock_status.return_value = {'status': 'PARTIAL', 'services': [], 'mcp_config_exists': False}

            # Mock fast successful upgrade
            async def fast_sequence(step_functions, stop_on_failure=True):
                return {"success": True, "completed_steps": list(step_functions.keys()), "failed_steps": []}

            mock_sequence.side_effect = fast_sequence

            start_time = time.time()
            result = await wizard_service.start_installation(force_reinstall=True)
            end_time = time.time()

            upgrade_time = end_time - start_time

            # Upgrade should be fast (well under 30s target)
            assert upgrade_time < 5.0, f"Upgrade took {upgrade_time:.2f}s, expected <5.0s"
            assert result["success"] is True