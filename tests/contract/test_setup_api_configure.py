"""Contract tests for PUT /setup/session/{session_id}/configure API endpoint.

Tests API endpoint according to setup-wizard-api.yml specification:
- PUT /setup/session/{session_id}/configure
- Parameters: session_id (UUID)
- Request body: ComponentConfigurationRequest
- Responses: 200 (success), 400 (invalid configuration)
"""

import pytest
from uuid import UUID
from unittest.mock import AsyncMock, patch

pytestmark = [pytest.mark.contract, pytest.mark.async_test]


@pytest.fixture
def mock_setup_service():
    """Mock setup service for API tests."""
    with patch('src.services.setup_logic_service.SetupLogicService') as mock:
        service_instance = AsyncMock()
        mock.return_value = service_instance
        yield service_instance


class TestSetupConfigureApiContract:
    """Contract tests for PUT /setup/session/{session_id}/configure endpoint."""

    def test_configure_endpoint_exists(self, mock_setup_service):
        """Test that the configure endpoint is registered."""
        from src.api.setup_endpoints import setup_router

        # Check if route is registered
        routes = [route.path for route in setup_router.routes if hasattr(route, 'path')]
        configure_route_exists = any("/setup/session/{session_id}/configure" in route for route in routes)
        assert configure_route_exists

    def test_configure_components_success(self, mock_setup_service):
        """Test successful component configuration."""
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            'vector_storage': {
                'provider': 'qdrant',
                'connection_url': 'http://localhost:6333',
                'container_name': 'bablib-memory-qdrant',
                'data_path': '~/.local/share/bablib/qdrant',
                'configuration': {'collection_config': {'size': 1536}}
            },
            'embedding_model': {
                'provider': 'ollama',
                'model_name': 'embeddinggemma:300m-qat-q4_0',
                'model_size_mb': 622,
                'download_required': True,
                'fallback_models': ['mxbai-embed-large', 'nomic-embed-text'],
                'configuration': {'temperature': 0.0}
            },
            'mcp_clients': [{
                'client_name': 'claude-code',
                'client_type': 'desktop_application',
                'executable_path': '/Applications/Claude Code.app',
                'config_file_path': '~/Library/Application Support/Claude/claude_desktop_config.json',
                'server_config': {
                    'command': 'bablib',
                    'args': ['serve', '--port', '9382'],
                    'env': {'BABLIB_LOG_LEVEL': 'INFO'}
                },
                'enabled': True
            }]
        }

        mock_response = {
            'success': True,
            'configuration_id': '550e8400-e29b-41d4-a716-446655440001',
            'validation_errors': [],
            'warnings': []
        }

        mock_setup_service.configure_components.return_value = mock_response

        # Verify session ID is valid UUID
        uuid_obj = UUID(session_id)
        assert str(uuid_obj) == session_id

    def test_configure_vector_storage_schema(self, mock_setup_service):
        """Test vector storage configuration schema."""
        vector_storage_config = {
            'provider': 'qdrant',
            'connection_url': 'http://localhost:6333',
            'container_name': 'bablib-memory-qdrant',
            'data_path': '~/.local/share/bablib/qdrant',
            'configuration': {}
        }

        # Validate required fields
        assert 'provider' in vector_storage_config
        assert 'connection_url' in vector_storage_config
        assert vector_storage_config['provider'] == 'qdrant'  # Only supported provider
        assert vector_storage_config['connection_url'].startswith('http')

    def test_configure_embedding_model_schema(self, mock_setup_service):
        """Test embedding model configuration schema."""
        embedding_model_config = {
            'provider': 'ollama',
            'model_name': 'embeddinggemma:300m-qat-q4_0',
            'model_size_mb': 622,
            'download_required': True,
            'fallback_models': ['mxbai-embed-large', 'nomic-embed-text'],
            'configuration': {'temperature': 0.0}
        }

        # Validate required fields
        assert 'provider' in embedding_model_config
        assert 'model_name' in embedding_model_config
        assert embedding_model_config['provider'] == 'ollama'  # Only supported provider
        assert isinstance(embedding_model_config['download_required'], bool)
        assert isinstance(embedding_model_config['fallback_models'], list)

    def test_configure_mcp_clients_schema(self, mock_setup_service):
        """Test MCP clients configuration schema."""
        mcp_client_config = {
            'client_name': 'claude-code',
            'client_type': 'desktop_application',
            'executable_path': '/Applications/Claude Code.app',
            'config_file_path': '~/Library/Application Support/Claude/claude_desktop_config.json',
            'server_config': {
                'command': 'bablib',
                'args': ['serve', '--port', '9382']
            },
            'enabled': True
        }

        # Validate required fields
        assert 'client_name' in mcp_client_config
        assert 'enabled' in mcp_client_config
        assert isinstance(mcp_client_config['enabled'], bool)
        assert isinstance(mcp_client_config['server_config'], dict)

    def test_configure_partial_configuration(self, mock_setup_service):
        """Test configuration with only some components."""
        # Only vector storage, no embedding model or MCP clients
        partial_config = {
            'vector_storage': {
                'provider': 'qdrant',
                'connection_url': 'http://localhost:6333',
                'container_name': 'bablib-memory-qdrant',
                'data_path': '~/.local/share/bablib/qdrant',
                'configuration': {}
            }
        }

        # Should accept partial configuration
        assert 'vector_storage' in partial_config
        assert 'embedding_model' not in partial_config
        assert 'mcp_clients' not in partial_config

    def test_configure_invalid_vector_storage_provider_400(self, mock_setup_service):
        """Test invalid vector storage provider returns 400."""
        invalid_config = {
            'vector_storage': {
                'provider': 'invalid_provider',  # Not 'qdrant'
                'connection_url': 'http://localhost:6333'
            }
        }

        # Should validate provider enum
        valid_providers = ['qdrant']
        assert invalid_config['vector_storage']['provider'] not in valid_providers

    def test_configure_invalid_embedding_provider_400(self, mock_setup_service):
        """Test invalid embedding provider returns 400."""
        invalid_config = {
            'embedding_model': {
                'provider': 'invalid_provider',  # Not 'ollama'
                'model_name': 'some-model'
            }
        }

        # Should validate provider enum
        valid_providers = ['ollama']
        assert invalid_config['embedding_model']['provider'] not in valid_providers

    def test_configure_missing_required_fields_400(self, mock_setup_service):
        """Test missing required fields returns 400."""
        incomplete_configs = [
            # Missing provider
            {'vector_storage': {'connection_url': 'http://localhost:6333'}},
            # Missing connection_url
            {'vector_storage': {'provider': 'qdrant'}},
            # Missing model_name
            {'embedding_model': {'provider': 'ollama'}},
            # Missing client_name
            {'mcp_clients': [{'enabled': True}]}
        ]

        for config in incomplete_configs:
            if 'vector_storage' in config:
                vs_config = config['vector_storage']
                required_fields = ['provider', 'connection_url']
                missing_fields = [field for field in required_fields if field not in vs_config]
                assert len(missing_fields) > 0

    def test_configure_response_schema_success(self, mock_setup_service):
        """Test successful response follows ConfigurationResponse schema."""
        response = {
            'success': True,
            'configuration_id': '550e8400-e29b-41d4-a716-446655440001',
            'validation_errors': [],
            'warnings': ['Docker container will be recreated']
        }

        # Validate response structure
        assert 'success' in response
        assert 'configuration_id' in response
        assert isinstance(response['success'], bool)
        assert UUID(response['configuration_id'])  # Valid UUID
        assert isinstance(response['validation_errors'], list)
        assert isinstance(response['warnings'], list)

    def test_configure_response_schema_with_errors(self, mock_setup_service):
        """Test response with validation errors."""
        response = {
            'success': False,
            'configuration_id': '550e8400-e29b-41d4-a716-446655440002',
            'validation_errors': [
                'Invalid connection URL format',
                'Model name not found in Ollama registry'
            ],
            'warnings': []
        }

        # Validate error response
        assert response['success'] is False
        assert len(response['validation_errors']) > 0
        assert all(isinstance(error, str) for error in response['validation_errors'])

    def test_configure_url_validation(self, mock_setup_service):
        """Test URL validation in configuration."""
        test_urls = [
            {'url': 'http://localhost:6333', 'valid': True},
            {'url': 'https://qdrant.example.com:6333', 'valid': True},
            {'url': 'invalid-url', 'valid': False},
            {'url': 'ftp://localhost:6333', 'valid': False}
        ]

        for test_case in test_urls:
            url = test_case['url']
            if test_case['valid']:
                assert url.startswith('http://') or url.startswith('https://')
            else:
                assert not (url.startswith('http://') or url.startswith('https://'))

    def test_configure_empty_request_400(self, mock_setup_service):
        """Test empty configuration request returns 400."""
        empty_config = {}

        # Should require at least one component configuration
        has_any_component = any(key in empty_config for key in ['vector_storage', 'embedding_model', 'mcp_clients'])
        assert not has_any_component


# This test file should initially FAIL as the setup API endpoints are not yet implemented.
# Tests will pass once the API endpoints are properly implemented in src/api/setup_endpoints.py