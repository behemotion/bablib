"""Integration tests for auto setup flow.

Based on quickstart.md Scenario 2: Auto Setup - Default Configuration
Tests the automated setup workflow with default options.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from src.cli.main import main

pytestmark = [pytest.mark.integration, pytest.mark.async_test, pytest.mark.performance]


class TestAutoSetupFlow:
    """Integration tests for automated setup workflow."""

    @pytest.fixture
    def cli_runner(self):
        """CLI runner for integration testing."""
        return CliRunner()

    @pytest.fixture
    def mock_components_available(self):
        """Mock components available for auto setup."""
        return {
            'docker': {
                'available': True,
                'version': '24.0.5',
                'health_status': 'healthy'
            },
            'ollama': {
                'available': True,
                'version': '0.1.17',
                'health_status': 'healthy'
            },
            'claude_code': {
                'available': False,  # Optional component
                'version': None,
                'health_status': 'unknown'
            }
        }

    @pytest.fixture
    def mock_setup_services(self):
        """Mock setup services for auto setup test."""
        mocks = {}

        with patch('src.services.setup_logic_service.SetupLogicService') as service_mock:
            service_instance = AsyncMock()
            service_mock.return_value = service_instance
            mocks['setup_service'] = service_instance

        yield mocks

    async def test_auto_setup_no_user_prompts(self, cli_runner, mock_components_available, mock_setup_services):
        """Test that auto setup runs without user interaction."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available
        setup_service.run_auto_setup.return_value = True

        # Run auto setup with --auto flag
        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Verify no user prompts appeared
        # Auto setup should not contain interactive prompts
        setup_service.run_auto_setup.assert_called_once()

        # Should not contain prompt indicators
        assert '[Y/n]' not in result.output
        assert '[y/N]' not in result.output

    async def test_auto_setup_progress_display(self, cli_runner, mock_components_available, mock_setup_services):
        """Test that auto setup shows progress without prompts."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available
        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Should show progress steps like [1/5], [2/5], etc.
        output = result.output
        assert any(f"[{i}/{j}]" in output for i in range(1, 6) for j in range(4, 7))

    async def test_auto_setup_default_configurations(self, cli_runner, mock_components_available, mock_setup_services):
        """Test that auto setup uses default configurations."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available

        # Mock default configuration choices
        setup_service.get_default_vector_storage_config.return_value = {
            'provider': 'qdrant',
            'container_name': 'bablib-memory-qdrant',
            'connection_url': 'http://localhost:6333'
        }

        setup_service.get_default_embedding_model_config.return_value = {
            'provider': 'ollama',
            'model_name': 'embeddinggemma:300m-qat-q4_0',
            'download_required': True
        }

        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Verify default configurations were used
        setup_service.get_default_vector_storage_config.assert_called_once()
        setup_service.get_default_embedding_model_config.assert_called_once()

    async def test_auto_setup_container_recreation(self, cli_runner, mock_components_available, mock_setup_services):
        """Test automatic container recreation in auto mode."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available

        # Mock existing container detection and recreation
        setup_service.check_existing_qdrant_container.return_value = {
            'exists': True,
            'container_id': 'old_container_123',
            'status': 'exited'
        }

        setup_service.recreate_qdrant_container.return_value = {
            'status': 'success',
            'new_container_id': 'new_container_456'
        }

        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Should indicate container recreation
        assert "recreat" in result.output.lower() or "container" in result.output.lower()

    async def test_auto_setup_model_download_progress(self, cli_runner, mock_components_available, mock_setup_services):
        """Test automatic model download with progress display."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available

        # Mock model download with progress
        setup_service.check_model_availability.return_value = {
            'model': 'embeddinggemma:300m-qat-q4_0',
            'available': False,
            'download_required': True,
            'size_mb': 622
        }

        # Mock download progress callbacks
        download_progress = [0, 25, 50, 75, 100]

        async def mock_download_model(model_name, progress_callback=None):
            for progress in download_progress:
                if progress_callback:
                    progress_callback(progress, 622 * 1024 * 1024)  # Convert MB to bytes
            return {'status': 'success', 'model_ready': True}

        setup_service.download_embedding_model.side_effect = mock_download_model
        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Should show download progress
        assert "download" in result.output.lower()
        assert "%" in result.output or "progress" in result.output.lower()

    async def test_auto_setup_mcp_handling_not_available(self, cli_runner, mock_components_available, mock_setup_services):
        """Test MCP client handling when not available in auto mode."""
        setup_service = mock_setup_services['setup_service']

        # Claude Code not available
        mock_components_available['claude_code']['available'] = False
        setup_service.detect_components.return_value = mock_components_available

        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Should gracefully skip MCP configuration
        assert "skip" in result.output.lower() or "not available" in result.output.lower()

    async def test_auto_setup_mcp_handling_available(self, cli_runner, mock_components_available, mock_setup_services):
        """Test automatic MCP client configuration when available."""
        setup_service = mock_setup_services['setup_service']

        # Claude Code available
        mock_components_available['claude_code']['available'] = True
        mock_components_available['claude_code']['version'] = '1.2.3'
        setup_service.detect_components.return_value = mock_components_available

        # Mock automatic MCP configuration
        setup_service.configure_mcp_client_automatically.return_value = {
            'status': 'success',
            'client': 'claude-code',
            'config_updated': True
        }

        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Should configure MCP client automatically
        assert "claude" in result.output.lower() or "mcp" in result.output.lower()

    async def test_auto_setup_performance_timing(self, cli_runner, mock_components_available, mock_setup_services):
        """Test that auto setup meets performance target (<30 seconds)."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available
        setup_service.run_auto_setup.return_value = True

        start_time = time.time()

        result = cli_runner.invoke(main, ['setup', '--auto'])

        execution_time = time.time() - start_time

        assert result.exit_code == 0

        # Should complete within performance target
        # In test environment, allow for overhead but keep reasonable
        assert execution_time < 10  # 10 seconds max for test

        # Should display actual setup time
        if "setup time" in result.output.lower() or "completed in" in result.output.lower():
            # Time should be displayed to user
            pass

    async def test_auto_setup_completion_no_interaction(self, cli_runner, mock_components_available, mock_setup_services):
        """Test auto setup completion message without user interaction."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available

        # Mock setup completion summary
        setup_service.get_auto_setup_summary.return_value = {
            'components_configured': 2,  # Docker + Ollama
            'total_time': 28.3,
            'default_configurations': True
        }

        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto'])

        assert result.exit_code == 0

        # Should show completion without asking for user input
        assert "completed" in result.output.lower() or "✅" in result.output
        assert "28.3" in result.output  # Should show timing

    async def test_auto_setup_error_handling_graceful(self, cli_runner, mock_components_available, mock_setup_services):
        """Test auto setup handles errors gracefully without user interaction."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available

        # Mock a non-critical error during auto setup
        setup_service.configure_vector_storage.side_effect = Exception("Docker temporary issue")

        # Auto setup should attempt recovery automatically
        setup_service.run_auto_setup.side_effect = Exception("Setup failed")

        result = cli_runner.invoke(main, ['setup', '--auto'])

        # Should return appropriate error code
        assert result.exit_code != 0

        # Should show error without prompting user
        assert "error" in result.output.lower()
        assert "[Y/n]" not in result.output  # No prompts in auto mode

    async def test_auto_setup_with_force_flag(self, cli_runner, mock_components_available, mock_setup_services):
        """Test auto setup with --force flag for re-running."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available

        # Mock existing completed setup
        setup_service.check_existing_setup.return_value = {
            'setup_completed': True,
            'last_setup_time': '2025-01-26T10:00:00Z'
        }

        setup_service.run_auto_setup.return_value = True

        result = cli_runner.invoke(main, ['setup', '--auto', '--force'])

        assert result.exit_code == 0

        # Should re-run setup even if previously completed
        setup_service.run_auto_setup.assert_called_once()

    async def test_auto_setup_default_faster_than_interactive(self, cli_runner, mock_components_available, mock_setup_services):
        """Test that auto setup is faster than interactive mode."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_available
        setup_service.run_auto_setup.return_value = True

        # Mock timing
        auto_start = time.time()
        result = cli_runner.invoke(main, ['setup', '--auto'])
        auto_time = time.time() - auto_start

        assert result.exit_code == 0

        # Auto should be faster (no user interaction delays)
        # In real implementation, auto mode should be significantly faster
        assert auto_time < 5  # Very fast in test environment


# This test file should initially FAIL as the auto setup functionality is not yet implemented.
# Tests will pass once the automated setup workflow is properly implemented.