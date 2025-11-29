"""Contract tests for Bablib setup CLI command.

Tests CLI command interface according to cli-commands.yml specification:
- `bablib setup [OPTIONS]`
- Exit codes: 0 (success), 1 (general error), 2 (config error), 3 (dependency error), 4 (user cancel)
- Supports --auto flag for automatic setup
- Supports --force flag to re-run setup
- Supports --verbose flag for detailed output
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from src.cli.main import main

pytestmark = [pytest.mark.contract, pytest.mark.async_test]


class TestSetupCliContract:
    """Contract tests for setup CLI command."""

    @pytest.fixture
    def cli_runner(self):
        """CLI runner for testing Click commands."""
        return CliRunner()

    @pytest.fixture
    def mock_setup_service(self):
        """Mock setup service that will be implemented later."""
        with patch('src.cli.setup.SetupLogicService') as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    def test_setup_command_exists(self, cli_runner):
        """Test that setup command is registered and callable."""
        # This test should pass once CLI command is implemented
        result = cli_runner.invoke(main, ['setup', '--help'])
        assert result.exit_code == 0
        assert 'setup' in result.output.lower()

    def test_setup_interactive_mode_success(self, cli_runner, mock_setup_service):
        """Test interactive setup mode returns exit code 0 on success."""
        mock_setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'])

        # Should succeed with exit code 0
        assert result.exit_code == 0
        mock_setup_service.run_interactive_setup.assert_called_once()

    def test_setup_auto_mode_success(self, cli_runner, mock_setup_service):
        """Test auto setup mode with --auto flag returns exit code 0 on success."""
        mock_setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        # Should succeed with exit code 0
        assert result.exit_code == 0
        mock_setup_service.run_auto_setup.assert_called_once()

    def test_setup_force_flag_accepted(self, cli_runner, mock_setup_service):
        """Test --force flag is accepted and passed to service."""
        mock_setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--force'])

        assert result.exit_code == 0
        mock_setup_service.run_interactive_setup.assert_called_once()

    def test_setup_verbose_flag_accepted(self, cli_runner, mock_setup_service):
        """Test --verbose flag is accepted."""
        mock_setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--verbose'])

        assert result.exit_code == 0

    def test_setup_general_error_exit_code_1(self, cli_runner, mock_setup_service):
        """Test general error returns exit code 1."""
        mock_setup_service.run_interactive_setup.side_effect = Exception("General error")

        result = cli_runner.invoke(main, ['setup'])

        # Should return exit code 1 for general errors
        assert result.exit_code == 1

    def test_setup_configuration_error_exit_code_2(self, cli_runner, mock_setup_service):
        """Test configuration error returns exit code 2."""
        from src.models.setup_types import SetupConfigurationError
        mock_setup_service.run_interactive_setup.side_effect = SetupConfigurationError("Config error")

        result = cli_runner.invoke(main, ['setup'])

        # Should return exit code 2 for configuration errors
        assert result.exit_code == 2

    def test_setup_dependency_error_exit_code_3(self, cli_runner, mock_setup_service):
        """Test external dependency error returns exit code 3."""
        from src.models.setup_types import ExternalDependencyError
        mock_setup_service.run_interactive_setup.side_effect = ExternalDependencyError("Docker not available")

        result = cli_runner.invoke(main, ['setup'])

        # Should return exit code 3 for dependency errors
        assert result.exit_code == 3

    def test_setup_user_cancellation_exit_code_4(self, cli_runner, mock_setup_service):
        """Test user cancellation returns exit code 4."""
        from src.models.setup_types import UserCancellationError
        mock_setup_service.run_interactive_setup.side_effect = UserCancellationError("User cancelled")

        result = cli_runner.invoke(main, ['setup'])

        # Should return exit code 4 for user cancellation
        assert result.exit_code == 4

    def test_setup_success_output_format(self, cli_runner, mock_setup_service):
        """Test successful setup output contains expected elements."""
        mock_setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'])

        assert result.exit_code == 0
        # Output should contain success indicator
        assert "✅" in result.output or "success" in result.output.lower()

    def test_setup_auto_combined_with_force(self, cli_runner, mock_setup_service):
        """Test --auto and --force flags can be used together."""
        mock_setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto', '--force'])

        assert result.exit_code == 0
        mock_setup_service.run_auto_setup.assert_called_once()

    def test_setup_error_output_format(self, cli_runner, mock_setup_service):
        """Test error output contains expected elements."""
        mock_setup_service.run_interactive_setup.side_effect = Exception("Test error")

        result = cli_runner.invoke(main, ['setup'])

        assert result.exit_code == 1
        # Error output should contain error indicator
        assert "❌" in result.output or "error" in result.output.lower()


# This test file should initially FAIL as the setup command is not yet implemented.
# Tests will pass once the CLI setup command is properly implemented in src/cli/setup.py