"""Contract tests for CLI help display functionality."""

import pytest
from click.testing import CliRunner
from src.cli.main import main


class TestCliHelp:
    """Test CLI help system improvements."""

    def test_bare_command_shows_help_suggestion(self):
        """Test that running bablib without arguments shows help suggestion."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        assert "--help" in result.output
        assert "available commands" in result.output.lower()

    def test_comprehensive_help_display(self):
        """Test that --help shows all commands and options."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0

        # Check for all main commands
        expected_commands = [
            "create", "crawl", "list", "search",
            "remove", "serve", "status", "setup"
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in help output"

        # Check for global options
        assert "--debug" in result.output
        assert "--config-file" in result.output
        assert "--verbose" in result.output

    def test_command_specific_help(self):
        """Test that command-specific help includes all options."""
        runner = CliRunner()

        # Test crawl command help
        result = runner.invoke(main, ["crawl", "--help"])
        assert result.exit_code == 0
        assert "--update" in result.output
        assert "--all" in result.output
        assert "--max-pages" in result.output
        assert "--rate-limit" in result.output
        assert "--debug" in result.output

        # Test create command help
        result = runner.invoke(main, ["create", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--depth" in result.output
        assert "--model" in result.output

    def test_help_formatting(self):
        """Test that help output is well-formatted and readable."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        lines = result.output.split('\n')

        # Check for proper structure
        assert any("Usage:" in line for line in lines)
        assert any("Commands:" in line for line in lines)
        assert any("Options:" in line for line in lines)

        # Check indentation for readability
        command_lines = [l for l in lines if l.strip() and not l.startswith(' ')]
        description_lines = [l for l in lines if l.startswith('  ') and l.strip()]
        assert len(description_lines) > 0, "Command descriptions should be indented"

    def test_all_commands_have_help(self):
        """Test that all commands have their own help text."""
        runner = CliRunner()

        commands_to_test = [
            "create", "crawl", "list", "search",
            "remove", "serve", "status", "setup"
        ]

        for cmd in commands_to_test:
            result = runner.invoke(main, [cmd, "--help"])
            assert result.exit_code == 0, f"Command '{cmd}' help failed"
            assert "Usage:" in result.output, f"Command '{cmd}' missing usage"
            assert cmd in result.output.lower(), f"Command name not in '{cmd}' help"