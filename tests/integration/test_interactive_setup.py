"""Integration tests for interactive setup flow.

Based on quickstart.md Scenario 1: Interactive Setup - Full Components Available
Tests the complete interactive setup workflow from start to finish.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from src.cli.main import main

pytestmark = [pytest.mark.integration, pytest.mark.async_test, pytest.mark.slow]


class TestInteractiveSetupFlow:
    """Integration tests for interactive setup workflow."""

    @pytest.fixture
    def cli_runner(self):
        """CLI runner for integration testing."""
        return CliRunner()

    @pytest.fixture
    def mock_components_all_available(self):
        """Mock all components as available for full setup test."""
        return {
            'docker': {
                'available': True,
                'version': '24.0.5',
                'health_status': 'healthy',
                'capabilities': {'api_version': '1.43', 'compose_support': True}
            },
            'ollama': {
                'available': True,
                'version': '0.1.17',
                'health_status': 'healthy',
                'capabilities': {'models': ['mxbai-embed-large'], 'api_version': 'v1'}
            },
            'claude_code': {
                'available': True,
                'version': '1.2.3',
                'health_status': 'healthy',
                'capabilities': {'config_path': '~/Library/Application Support/Claude'}
            }
        }

    @pytest.fixture
    def mock_setup_services(self):
        """Mock all setup services for integration test."""
        mocks = {}

        # Mock component detection
        with patch('src.services.docker_manager.DockerManager') as docker_mock:
            docker_instance = AsyncMock()
            docker_mock.return_value = docker_instance
            mocks['docker_manager'] = docker_instance

        with patch('src.services.ollama_manager.OllamaManager') as ollama_mock:
            ollama_instance = AsyncMock()
            ollama_mock.return_value = ollama_instance
            mocks['ollama_manager'] = ollama_instance

        with patch('src.services.mcp_detector.MCPDetector') as mcp_mock:
            mcp_instance = AsyncMock()
            mcp_mock.return_value = mcp_instance
            mocks['mcp_detector'] = mcp_instance

        with patch('src.services.setup_logic_service.SetupLogicService') as service_mock:
            service_instance = AsyncMock()
            service_mock.return_value = service_instance
            mocks['setup_service'] = service_instance

        yield mocks

    async def test_interactive_setup_full_workflow(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test complete interactive setup workflow with all components available."""
        # Configure mocks for successful setup
        setup_service = mock_setup_services['setup_service']

        # Mock component detection phase
        setup_service.detect_components.return_value = mock_components_all_available

        # Mock user choices for interactive prompts
        setup_service.get_user_vector_storage_choice.return_value = {'use_qdrant': True, 'container_name': 'bablib-memory-qdrant'}
        setup_service.get_user_embedding_model_choice.return_value = {'model': 'embeddinggemma:300m-qat-q4_0', 'download': True}
        setup_service.get_user_mcp_client_choice.return_value = {'configure_claude_code': True}

        # Mock setup execution phases
        setup_service.configure_vector_storage.return_value = {'status': 'success', 'container_id': 'abc123'}
        setup_service.setup_embedding_model.return_value = {'status': 'success', 'model_ready': True}
        setup_service.configure_mcp_clients.return_value = {'status': 'success', 'clients_configured': 1}

        # Mock final validation
        setup_service.validate_setup.return_value = {'status': 'success', 'all_healthy': True}

        # Mock overall setup orchestration
        setup_service.run_interactive_setup.return_value = True

        # Simulate user input for prompts
        user_inputs = [
            'y',  # Use Qdrant for vector storage
            'y',  # Download embeddinggemma model
            'y',  # Configure Claude Code MCP integration
        ]

        # Execute interactive setup
        result = cli_runner.invoke(main, ['setup'], input='\n'.join(user_inputs))

        # Verify successful completion
        assert result.exit_code == 0
        assert "✅" in result.output or "success" in result.output.lower()

        # Verify service interactions
        setup_service.run_interactive_setup.assert_called_once()

    async def test_interactive_setup_component_detection_display(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test that component detection results are properly displayed."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available
        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'])

        assert result.exit_code == 0

        # Should display component detection results
        output_lower = result.output.lower()
        assert "docker" in output_lower
        assert "ollama" in output_lower
        assert "available" in output_lower or "✅" in result.output

    async def test_interactive_setup_vector_storage_configuration(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test vector storage configuration prompts and execution."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available
        setup_service.run_interactive_setup.return_value = True

        # User chooses to use Qdrant
        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        assert result.exit_code == 0

        # Should contain vector storage configuration prompts
        assert "vector storage" in result.output.lower() or "qdrant" in result.output.lower()

    async def test_interactive_setup_embedding_model_download(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test embedding model download prompt and progress display."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available
        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        assert result.exit_code == 0

        # Should contain embedding model prompts
        assert "embedding" in result.output.lower() or "model" in result.output.lower()

    async def test_interactive_setup_mcp_client_configuration(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test MCP client configuration prompts."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available
        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        assert result.exit_code == 0

        # Should contain MCP client prompts
        assert "claude" in result.output.lower() or "mcp" in result.output.lower()

    async def test_interactive_setup_progress_tracking(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test that setup progress is displayed to user."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available

        # Mock progress callbacks
        progress_calls = []

        def mock_progress_callback(step, progress):
            progress_calls.append((step, progress))

        setup_service.run_interactive_setup.return_value = True
        setup_service.set_progress_callback = mock_progress_callback

        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        assert result.exit_code == 0

        # Should show progress indicators
        assert any(char in result.output for char in ['[', '|', '/', '-', '\\'])  # Progress indicators

    async def test_interactive_setup_completion_summary(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test setup completion summary is displayed."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available
        setup_service.run_interactive_setup.return_value = True

        # Mock completion status
        setup_service.get_setup_summary.return_value = {
            'vector_storage': 'Qdrant (running at localhost:6333)',
            'embedding_model': 'embeddinggemma:300m-qat-q4_0',
            'mcp_clients': ['Claude Code (configured)'],
            'setup_time': 23.4
        }

        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        assert result.exit_code == 0

        # Should display completion summary
        assert "completed" in result.output.lower() or "✅" in result.output
        assert "qdrant" in result.output.lower()
        assert "embeddinggemma" in result.output.lower()

    async def test_interactive_setup_user_cancellation(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test user can cancel setup during prompts."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available

        # Mock user cancellation
        from src.models.setup_types import UserCancellationError
        setup_service.run_interactive_setup.side_effect = UserCancellationError("User cancelled setup")

        # User cancels (Ctrl+C simulation)
        result = cli_runner.invoke(main, ['setup'])

        # Should handle cancellation gracefully
        assert result.exit_code == 4  # User cancellation exit code
        assert "cancelled" in result.output.lower() or "❌" in result.output

    async def test_interactive_setup_timing_performance(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test that interactive setup completes within performance target."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available
        setup_service.run_interactive_setup.return_value = True

        import time
        start_time = time.time()

        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        execution_time = time.time() - start_time

        assert result.exit_code == 0
        # Should complete quickly in test environment (allowing for test overhead)
        assert execution_time < 10  # 10 seconds max for test environment

    async def test_interactive_setup_error_recovery(self, cli_runner, mock_components_all_available, mock_setup_services):
        """Test error recovery during interactive setup."""
        setup_service = mock_setup_services['setup_service']
        setup_service.detect_components.return_value = mock_components_all_available

        # Mock a recoverable error during setup
        setup_service.configure_vector_storage.side_effect = [
            Exception("Docker not responding"),  # First attempt fails
            {'status': 'success', 'container_id': 'abc123'}  # Second attempt succeeds
        ]

        setup_service.run_interactive_setup.return_value = True

        result = cli_runner.invoke(main, ['setup'], input='y\ny\ny\n')

        # Should recover from error and complete
        assert result.exit_code == 0
        # Should show error message and recovery
        assert "error" in result.output.lower() or "retry" in result.output.lower()


# This test file should initially FAIL as the interactive setup functionality is not yet implemented.
# Tests will pass once the interactive setup workflow is properly implemented.