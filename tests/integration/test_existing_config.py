"""Integration tests for existing configuration handling.

Based on quickstart.md Scenario 4: Existing Configuration - Reconfiguration
Tests setup behavior with existing configuration files and components.
"""

import pytest
from unittest.mock import AsyncMock, patch, mock_open
from click.testing import CliRunner

from src.cli.main import main

pytestmark = [pytest.mark.integration, pytest.mark.async_test]


class TestExistingConfigurationFlow:
    """Integration tests for existing configuration scenarios."""

    @pytest.fixture
    def cli_runner(self):
        """CLI runner for integration testing."""
        return CliRunner()

    @pytest.fixture
    def mock_existing_config(self):
        """Mock existing setup configuration."""
        return {
            'setup_completed': True,
            'setup_mode': 'interactive',
            'last_setup_time': '2025-01-26T10:00:00Z',
            'components_status': {
                'vector_storage': {
                    'name': 'qdrant',
                    'status': 'healthy',
                    'available': True,
                    'version': '1.7.0',
                    'container_id': 'existing_container_123'
                },
                'embedding_model': {
                    'name': 'mxbai-embed-large',  # Different model than current default
                    'status': 'healthy',
                    'available': True,
                    'version': 'latest'
                },
                'mcp_clients': []  # No MCP clients configured
            },
            'configuration_file': '~/.config/bablib/setup-config.json'
        }

    @pytest.fixture
    def mock_setup_services(self):
        """Mock setup services for existing config tests."""
        mocks = {}

        with patch('src.services.setup_logic_service.SetupLogicService') as service_mock:
            service_instance = AsyncMock()
            service_mock.return_value = service_instance
            mocks['setup_service'] = service_instance

        with patch('src.services.config_service.ConfigService') as config_mock:
            config_instance = AsyncMock()
            config_mock.return_value = config_instance
            mocks['config_service'] = config_instance

        yield mocks

    async def test_status_check_existing_setup(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test status check displays existing setup correctly."""
        setup_service = mock_setup_services['setup_service']
        setup_service.get_setup_status.return_value = mock_existing_config

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0

        # Should display existing setup information
        output = result.output
        assert "Completed" in output or "✅" in output
        assert "2025-01-26" in output  # Setup date
        assert "qdrant" in output.lower()
        assert "mxbai-embed-large" in output.lower()

    async def test_status_check_shows_current_configuration(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test status check shows detailed component configuration."""
        setup_service = mock_setup_services['setup_service']
        setup_service.get_setup_status.return_value = mock_existing_config

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0

        # Should show component details
        output = result.output.lower()
        assert "vector storage" in output or "qdrant" in output
        assert "embedding model" in output or "mxbai" in output
        assert "healthy" in output or "✅" in result.output

    async def test_rerun_setup_detects_existing_configuration(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test that rerunning setup detects existing configuration."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config
        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'])

        assert result.exit_code == 0

        # Should detect and mention existing setup
        output = result.output.lower()
        assert "existing" in output or "previous" in output or "already" in output

        # Should offer reconfiguration options
        setup_service.check_existing_setup.assert_called_once()

    async def test_reconfigure_vector_storage(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test reconfiguring vector storage while keeping other components."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock user choosing to reconfigure vector storage
        setup_service.get_reconfiguration_choices.return_value = {
            'reconfigure_vector_storage': True,
            'reconfigure_embedding_model': False,
            'reconfigure_mcp_clients': False
        }

        # Mock new vector storage configuration
        setup_service.reconfigure_vector_storage.return_value = {
            'status': 'success',
            'new_container_id': 'new_container_456',
            'old_container_removed': True
        }

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='y\nn\nn\n')  # Yes to vector storage, no to others

        assert result.exit_code == 0

        # Should preserve other configurations
        output = result.output.lower()
        assert "reconfigur" in output or "updat" in output

    async def test_reconfigure_embedding_model_only(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test reconfiguring only embedding model."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock user choosing to reconfigure embedding model
        setup_service.get_reconfiguration_choices.return_value = {
            'reconfigure_vector_storage': False,
            'reconfigure_embedding_model': True,
            'reconfigure_mcp_clients': False
        }

        # Mock new embedding model setup (switch to embeddinggemma)
        setup_service.reconfigure_embedding_model.return_value = {
            'status': 'success',
            'new_model': 'embeddinggemma:300m-qat-q4_0',
            'download_completed': True
        }

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='n\ny\nn\n')  # No, yes, no

        assert result.exit_code == 0

        # Should update embedding model configuration
        output = result.output.lower()
        assert "embedding" in output or "model" in output

    async def test_add_mcp_client_to_existing_setup(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test adding MCP client to existing setup without MCP clients."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock MCP client detection (now available)
        setup_service.detect_components.return_value = {
            'claude_code': {
                'available': True,
                'version': '1.2.3',
                'health_status': 'healthy'
            }
        }

        setup_service.get_reconfiguration_choices.return_value = {
            'reconfigure_vector_storage': False,
            'reconfigure_embedding_model': False,
            'reconfigure_mcp_clients': True
        }

        setup_service.configure_mcp_clients.return_value = {
            'status': 'success',
            'clients_configured': 1
        }

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='n\nn\ny\n')  # No, no, yes

        assert result.exit_code == 0

        # Should add MCP client configuration
        output = result.output.lower()
        assert "claude" in output or "mcp" in output

    async def test_preserve_working_configuration(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test that working configurations are preserved when not changed."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock user choosing to keep all existing configurations
        setup_service.get_reconfiguration_choices.return_value = {
            'reconfigure_vector_storage': False,
            'reconfigure_embedding_model': False,
            'reconfigure_mcp_clients': False
        }

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='n\nn\nn\n')  # Keep all existing

        assert result.exit_code == 0

        # Should not modify existing working configurations
        output = result.output.lower()
        assert "preserved" in output or "kept" in output or "no changes" in output

    async def test_mixed_reconfiguration_scenario(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test mixed reconfiguration (change some components, keep others)."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock mixed reconfiguration choices
        setup_service.get_reconfiguration_choices.return_value = {
            'reconfigure_vector_storage': True,   # Change this
            'reconfigure_embedding_model': False, # Keep this
            'reconfigure_mcp_clients': True       # Add this
        }

        # Mock successful mixed reconfiguration
        setup_service.reconfigure_vector_storage.return_value = {'status': 'success'}
        setup_service.configure_mcp_clients.return_value = {'status': 'success'}
        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='y\nn\ny\n')  # Yes, no, yes

        assert result.exit_code == 0

        # Should show mixed configuration results
        output = result.output.lower()
        assert "updated" in output or "modified" in output

    async def test_configuration_file_backup_on_change(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test that configuration file is backed up before changes."""
        setup_service = mock_setup_services['setup_service']
        config_service = mock_setup_services['config_service']

        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock configuration backup
        config_service.backup_configuration.return_value = {
            'backup_path': '~/.config/bablib/setup-config.json.backup.2025-01-26T14:30:15Z',
            'backup_created': True
        }

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='y\nn\nn\n')

        assert result.exit_code == 0

        # Should mention backup creation
        output = result.output.lower()
        assert "backup" in output or "saved" in output

    async def test_rollback_on_reconfiguration_failure(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test rollback to previous configuration on failure."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # Mock reconfiguration failure
        setup_service.get_reconfiguration_choices.return_value = {
            'reconfigure_vector_storage': True,
            'reconfigure_embedding_model': False,
            'reconfigure_mcp_clients': False
        }

        setup_service.reconfigure_vector_storage.side_effect = Exception("Docker container failed to start")

        # Mock rollback capability
        setup_service.rollback_to_previous_config.return_value = {
            'status': 'success',
            'rollback_completed': True
        }

        from src.models.setup_types import SetupConfigurationError
        setup_service.run_interactive_setup.side_effect = SetupConfigurationError("Reconfiguration failed")

        result = cli_runner.invoke(main, ['setup'], input='y\nn\nn\n')

        # Should handle failure and rollback
        assert result.exit_code == 2  # Configuration error

        # Should mention rollback
        output = result.output.lower()
        assert "rollback" in output or "restored" in output or "error" in output

    async def test_force_reconfigure_all_components(self, cli_runner, mock_existing_config, mock_setup_services):
        """Test force reconfiguration of all components with --force flag."""
        setup_service = mock_setup_services['setup_service']
        setup_service.check_existing_setup.return_value = mock_existing_config

        # With --force, should reconfigure everything without prompts
        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--force'])

        assert result.exit_code == 0

        # Should reconfigure all components
        setup_service.run_interactive_setup.assert_called_once()
        # Force should bypass existing configuration checks
        output = result.output.lower()
        assert "force" in output or "reconfigur" in output

    async def test_configuration_version_compatibility(self, cli_runner, mock_setup_services):
        """Test handling of outdated configuration file versions."""
        setup_service = mock_setup_services['setup_service']

        # Mock outdated configuration format
        outdated_config = {
            'setup_completed': True,
            'version': '0.1.0',  # Old version
            'last_setup_time': '2024-12-01T10:00:00Z',
            # Missing new fields, outdated structure
        }

        setup_service.check_existing_setup.return_value = outdated_config
        setup_service.is_config_compatible.return_value = False

        # Should handle outdated config gracefully
        setup_service.migrate_configuration.return_value = {
            'migration_successful': True,
            'backup_created': True
        }

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'])

        assert result.exit_code == 0

        # Should mention configuration migration
        output = result.output.lower()
        assert "migrat" in output or "upgrad" in output or "outdated" in output


# This test file should initially FAIL as the existing configuration handling is not yet implemented.
# Tests will pass once reconfiguration and configuration management are properly implemented.