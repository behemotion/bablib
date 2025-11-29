"""Contract tests for bablib uninstall command."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from click.testing import CliRunner
import sys

# These tests will fail until implementation is complete (TDD approach)

class TestUninstallCommandContract:
    """Contract tests for the uninstall command interface."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_components(self):
        """Mock detected components."""
        return {
            'containers': ['bablib-qdrant', 'bablib-redis'],
            'volumes': ['bablib_qdrant_data', 'bablib_redis_data'],
            'directories': [Path.home() / '.config/bablib', Path.home() / '.local/share/bablib'],
            'package': 'bablib'
        }

    def test_uninstall_command_exists(self, cli_runner):
        """Test that uninstall command is registered."""
        from src.cli.main import cli
        result = cli_runner.invoke(cli, ['uninstall', '--help'])
        assert result.exit_code == 0
        assert 'uninstall' in result.output.lower()
        assert 'remove bablib' in result.output.lower()

    def test_uninstall_requires_confirmation_by_default(self, cli_runner, mock_components):
        """Test that uninstall asks for confirmation without --force."""
        from src.cli.main import cli

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            result = cli_runner.invoke(cli, ['uninstall'], input='no\n')
            assert result.exit_code == 2  # Aborted
            assert 'WARNING' in result.output
            assert 'IRREVERSIBLE' in result.output
            assert 'Are you sure' in result.output

    def test_uninstall_force_flag_skips_confirmation(self, cli_runner, mock_components):
        """Test that --force flag bypasses confirmation."""
        from src.cli.main import cli

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            with patch('src.cli.uninstall.execute_removal', return_value=True):
                result = cli_runner.invoke(cli, ['uninstall', '--force'])
                assert 'Are you sure' not in result.output
                assert result.exit_code == 0

    def test_uninstall_backup_flag_creates_archive(self, cli_runner, mock_components, tmp_path):
        """Test that --backup flag creates backup archive."""
        from src.cli.main import cli

        backup_path = tmp_path / 'backup.tar.gz'

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            with patch('src.cli.uninstall.create_backup', return_value=backup_path) as mock_backup:
                with patch('src.cli.uninstall.execute_removal', return_value=True):
                    result = cli_runner.invoke(cli, ['uninstall', '--force', '--backup'])

                    mock_backup.assert_called_once()
                    assert 'Backup created' in result.output
                    assert result.exit_code == 0

    def test_uninstall_dry_run_shows_preview(self, cli_runner, mock_components):
        """Test that --dry-run shows what would be removed without removing."""
        from src.cli.main import cli

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            result = cli_runner.invoke(cli, ['uninstall', '--dry-run'])

            assert 'would be removed' in result.output.lower()
            assert 'bablib-qdrant' in result.output
            assert 'bablib-redis' in result.output
            assert result.exit_code == 0

    def test_uninstall_handles_partial_installation(self, cli_runner):
        """Test graceful handling of partial installations."""
        from src.cli.main import cli

        partial_components = {
            'containers': [],
            'volumes': ['bablib_data'],
            'directories': [Path.home() / '.config/bablib'],
            'package': 'bablib'
        }

        with patch('src.cli.uninstall.detect_components', return_value=partial_components):
            with patch('src.cli.uninstall.execute_removal', return_value=True):
                result = cli_runner.invoke(cli, ['uninstall', '--force'])
                assert result.exit_code == 0

    def test_uninstall_prompts_on_failure_without_force(self, cli_runner, mock_components):
        """Test that failures prompt for continuation without --force."""
        from src.cli.main import cli

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            with patch('src.cli.uninstall.remove_container', side_effect=[True, False]):
                result = cli_runner.invoke(cli, ['uninstall'], input='yes\ny\n')

                assert 'Failed to remove' in result.output
                assert 'Continue with remaining' in result.output

    def test_uninstall_continues_on_failure_with_force(self, cli_runner, mock_components):
        """Test that --force continues on failure without prompting."""
        from src.cli.main import cli

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            with patch('src.cli.uninstall.remove_container', side_effect=[True, False, True]):
                result = cli_runner.invoke(cli, ['uninstall', '--force'])

                assert 'Continue with remaining' not in result.output
                assert result.exit_code == 1  # Partial success

    def test_uninstall_preserves_external_volumes(self, cli_runner):
        """Test that external volumes are preserved."""
        from src.cli.main import cli

        components = {
            'containers': ['bablib-qdrant'],
            'volumes': ['bablib_data', 'external_volume'],
            'directories': [],
            'package': 'bablib'
        }

        with patch('src.cli.uninstall.detect_components', return_value=components):
            with patch('src.cli.uninstall.is_external_volume', side_effect=[False, True]):
                with patch('src.cli.uninstall.remove_volume') as mock_remove:
                    result = cli_runner.invoke(cli, ['uninstall', '--force', '--dry-run'])

                    assert 'external_volume' in result.output
                    assert 'preserved' in result.output.lower()

    def test_uninstall_shows_progress_feedback(self, cli_runner, mock_components):
        """Test that progress feedback is displayed during uninstall."""
        from src.cli.main import cli

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            with patch('src.cli.uninstall.execute_removal', return_value=True):
                result = cli_runner.invoke(cli, ['uninstall', '--force', '--verbose'])

                assert 'Progress' in result.output or 'Removing' in result.output
                assert result.exit_code == 0

    def test_uninstall_returns_correct_exit_codes(self, cli_runner):
        """Test that correct exit codes are returned."""
        from src.cli.main import cli

        # Test: Not installed
        with patch('src.cli.uninstall.is_bablib_installed', return_value=False):
            result = cli_runner.invoke(cli, ['uninstall', '--force'])
            assert result.exit_code == 4

        # Test: User cancelled
        with patch('src.cli.uninstall.detect_components', return_value={'containers': ['test']}):
            result = cli_runner.invoke(cli, ['uninstall'], input='no\n')
            assert result.exit_code == 2

        # Test: Partial success
        with patch('src.cli.uninstall.detect_components', return_value={'containers': ['test']}):
            with patch('src.cli.uninstall.execute_removal', return_value=False):
                result = cli_runner.invoke(cli, ['uninstall', '--force'])
                assert result.exit_code == 1

    def test_uninstall_custom_backup_path(self, cli_runner, mock_components, tmp_path):
        """Test that custom backup path is used when specified."""
        from src.cli.main import cli

        custom_path = tmp_path / 'custom-backup.tar.gz'

        with patch('src.cli.uninstall.detect_components', return_value=mock_components):
            with patch('src.cli.uninstall.create_backup', return_value=custom_path) as mock_backup:
                with patch('src.cli.uninstall.execute_removal', return_value=True):
                    result = cli_runner.invoke(cli, [
                        'uninstall', '--force', '--backup',
                        '--backup-path', str(custom_path)
                    ])

                    mock_backup.assert_called_with(components=mock_components, path=custom_path)
                    assert str(custom_path) in result.output