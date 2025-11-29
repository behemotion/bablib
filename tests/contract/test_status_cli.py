"""Contract tests for Bablib setup status CLI command.

Tests CLI status command interface according to cli-commands.yml specification:
- `bablib setup --status`
- Shows configuration state and component health
- Returns JSON format with --json flag
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from src.cli.main import main

pytestmark = [pytest.mark.contract, pytest.mark.async_test]


class TestStatusCliContract:
    """Contract tests for setup status CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """CLI runner for testing Click commands."""
        return CliRunner()

    @pytest.fixture
    def mock_setup_service(self):
        """Mock setup service for status queries."""
        with patch('src.cli.setup.SetupLogicService') as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def mock_status_response(self):
        """Mock status response data."""
        return {
            'setup_completed': True,
            'setup_mode': 'interactive',
            'last_setup_time': '2025-01-26T14:30:15Z',
            'components_status': {
                'vector_storage': {
                    'name': 'qdrant',
                    'status': 'healthy',
                    'available': True,
                    'version': '1.7.0',
                    'last_checked': '2025-01-26T14:35:00Z',
                    'error_message': None
                },
                'embedding_model': {
                    'name': 'embeddinggemma',
                    'status': 'healthy',
                    'available': True,
                    'version': '300m-qat-q4_0',
                    'last_checked': '2025-01-26T14:35:00Z',
                    'error_message': None
                },
                'mcp_clients': [{
                    'name': 'claude-code',
                    'status': 'healthy',
                    'available': True,
                    'version': '1.2.3',
                    'last_checked': '2025-01-26T14:35:00Z',
                    'error_message': None
                }]
            },
            'configuration_file': '~/.config/bablib/setup-config.json',
            'warnings': []
        }

    def test_status_command_exists(self, cli_runner):
        """Test that status command is available via --status flag."""
        result = cli_runner.invoke(main, ['setup', '--help'])
        assert result.exit_code == 0
        assert '--status' in result.output or 'status' in result.output.lower()

    def test_status_command_success(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status command returns exit code 0 on success."""
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        mock_setup_service.get_setup_status.assert_called_once()

    def test_status_output_contains_setup_state(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status output contains setup completion state."""
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        assert "Setup State:" in result.output or "setup" in result.output.lower()
        assert "Completed" in result.output or "✅" in result.output

    def test_status_output_contains_components(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status output contains component information."""
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        # Should contain component names
        assert "Vector Storage" in result.output or "qdrant" in result.output.lower()
        assert "Embedding Model" in result.output or "embeddinggemma" in result.output.lower()

    def test_status_output_contains_component_health(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status output shows component health status."""
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        # Should show health indicators
        assert "✅" in result.output or "Healthy" in result.output

    def test_status_output_contains_configuration_file(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status output shows configuration file path."""
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        assert "Configuration:" in result.output
        assert "setup-config.json" in result.output

    def test_status_json_format(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status command with --json flag returns JSON format."""
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status', '--json'])

        assert result.exit_code == 0
        # Output should be valid JSON
        try:
            parsed = json.loads(result.output)
            assert parsed['setup_completed'] is True
            assert 'components_status' in parsed
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_status_no_setup_completed(self, cli_runner, mock_setup_service):
        """Test status when setup has not been completed."""
        mock_status_response = {
            'setup_completed': False,
            'setup_mode': None,
            'last_setup_time': None,
            'components_status': {
                'vector_storage': {
                    'name': 'qdrant',
                    'status': 'not_configured',
                    'available': False,
                    'version': None,
                    'last_checked': '2025-01-26T14:35:00Z',
                    'error_message': 'Not configured'
                }
            },
            'configuration_file': None,
            'warnings': ['Setup not completed']
        }
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        assert "Not completed" in result.output or "❌" in result.output

    def test_status_with_warnings(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status output includes warnings."""
        mock_status_response['warnings'] = ['Docker container not responding', 'Model download incomplete']
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        assert "warning" in result.output.lower() or "⚠️" in result.output

    def test_status_component_unhealthy(self, cli_runner, mock_setup_service, mock_status_response):
        """Test status shows unhealthy components."""
        mock_status_response['components_status']['vector_storage']['status'] = 'unhealthy'
        mock_status_response['components_status']['vector_storage']['available'] = False
        mock_status_response['components_status']['vector_storage']['error_message'] = 'Container not running'
        mock_setup_service.get_setup_status.return_value = mock_status_response

        result = cli_runner.invoke(main, ['setup', '--status'])

        assert result.exit_code == 0
        assert "❌" in result.output or "unhealthy" in result.output.lower()

    def test_status_error_handling(self, cli_runner, mock_setup_service):
        """Test status command handles service errors gracefully."""
        mock_setup_service.get_setup_status.side_effect = Exception("Service error")

        result = cli_runner.invoke(main, ['setup', '--status'])

        # Should not crash, but may return error code
        assert result.exit_code in [0, 1]  # Allow both success with error message or error code


# This test file should initially FAIL as the status command is not yet implemented.
# Tests will pass once the CLI status functionality is properly implemented.