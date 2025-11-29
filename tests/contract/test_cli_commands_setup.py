"""Contract tests for CLI commands in setup operations."""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch

pytestmark = [pytest.mark.contract, pytest.mark.setup]


class TestSetupCommandContract:
    """Test the unified setup command with various flags."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock the setup orchestrator."""
        with patch("src.cli.commands.setup.SetupOrchestrator") as mock:
            yield mock

    def test_setup_command_no_flags_launches_menu(self, runner, mock_orchestrator):
        """Test that setup without flags launches interactive menu."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, [])

        assert result.exit_code == 0
        mock_orchestrator.return_value.run_interactive_menu.assert_called_once()

    def test_setup_command_init_flag(self, runner, mock_orchestrator):
        """Test setup --init flag behavior."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--init"])

        assert result.exit_code == 0
        mock_orchestrator.return_value.initialize.assert_called_once()

    def test_setup_command_uninstall_flag(self, runner, mock_orchestrator):
        """Test setup --uninstall flag behavior."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--uninstall"])

        assert result.exit_code == 0
        mock_orchestrator.return_value.uninstall.assert_called_once()

    def test_setup_command_reset_flag(self, runner, mock_orchestrator):
        """Test setup --reset flag behavior."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--reset"])

        assert result.exit_code == 0
        mock_orchestrator.return_value.reset.assert_called_once()

    def test_setup_command_conflicting_flags(self, runner):
        """Test that conflicting flags are detected and rejected."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--init", "--uninstall"])

        assert result.exit_code != 0
        assert "conflicting" in result.output.lower()

    def test_setup_command_init_with_vector_store(self, runner, mock_orchestrator):
        """Test setup --init --vector-store sqlite_vec."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--init", "--vector-store", "sqlite_vec"])

        assert result.exit_code == 0
        mock_orchestrator.return_value.initialize.assert_called_once()
        call_args = mock_orchestrator.return_value.initialize.call_args
        assert call_args[1]["vector_store"] == "sqlite_vec"

    def test_setup_command_auto_mode(self, runner, mock_orchestrator):
        """Test setup --init --auto uses defaults without prompts."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--init", "--auto"])

        assert result.exit_code == 0
        mock_orchestrator.return_value.initialize.assert_called_once()
        call_args = mock_orchestrator.return_value.initialize.call_args
        assert call_args[1]["auto"] is True

    def test_setup_command_force_flag(self, runner, mock_orchestrator):
        """Test setup --uninstall --force skips confirmations."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--uninstall", "--force"])

        assert result.exit_code == 0
        mock_orchestrator.return_value.uninstall.assert_called_once()
        call_args = mock_orchestrator.return_value.uninstall.call_args
        assert call_args[1]["force"] is True


class TestLegacyCommandAliases:
    """Test backward compatibility with legacy commands."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_setup_command(self):
        """Mock the unified setup command."""
        with patch("src.cli.main.setup") as mock:
            yield mock


    def test_uninstall_command_alias(self, runner, mock_setup_command):
        """Test that 'bablib uninstall' maps to 'bablib setup --uninstall'."""
        from src.cli.main import uninstall

        result = runner.invoke(uninstall, [])

        assert result.exit_code == 0
        # Verify it calls setup command with --uninstall flag
        mock_setup_command.assert_called_once()

    def test_uninstall_command_with_force(self, runner, mock_setup_command):
        """Test 'bablib uninstall --force'."""
        from src.cli.main import uninstall

        result = runner.invoke(uninstall, ["--force"])

        assert result.exit_code == 0
        mock_setup_command.assert_called_once()


class TestFlagValidation:
    """Test command flag validation and conflict detection."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    def test_multiple_operation_flags_rejected(self, runner):
        """Test that multiple operation flags are rejected."""
        from src.cli.commands.setup import setup

        # Test all conflicting combinations
        conflicts = [
            ["--init", "--uninstall"],
            ["--init", "--reset"],
            ["--uninstall", "--reset"],
            ["--init", "--uninstall", "--reset"],
        ]

        for flags in conflicts:
            result = runner.invoke(setup, flags)
            assert result.exit_code != 0
            assert "conflicting" in result.output.lower() or "conflict" in result.output.lower()

    def test_invalid_vector_store_rejected(self, runner):
        """Test that invalid vector store values are rejected."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--init", "--vector-store", "invalid"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_non_interactive_without_operation(self, runner):
        """Test that non-interactive requires an operation flag."""
        from src.cli.commands.setup import setup

        result = runner.invoke(setup, ["--non-interactive"])

        assert result.exit_code != 0
        assert "operation" in result.output.lower() or "required" in result.output.lower()