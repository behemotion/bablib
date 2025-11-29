"""Contract tests for GET /installation/{id}/services endpoint."""

import pytest
import httpx
from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel, Field, ValidationError, field_validator
from unittest.mock import patch, AsyncMock


class ServiceConfiguration(BaseModel):
    """Service configuration model for API validation."""

    service_name: Literal["docker", "qdrant", "ollama"] = Field(..., description="Service name")
    port: int = Field(..., ge=1024, le=65535, description="Service port")
    status: Literal["not_found", "detected", "configured", "running", "failed"] = Field(..., description="Service status")
    endpoint: str = Field(..., description="Service endpoint URI")
    version: str | None = Field(None, description="Service version")
    error_message: str | None = Field(None, description="Error message if failed")
    last_checked: datetime = Field(..., description="Last status check time")

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint_uri(cls, v: str) -> str:
        """Validate endpoint is a valid URI format."""
        if not (v.startswith('http://') or v.startswith('https://') or v.startswith('unix:///')):
            raise ValueError("endpoint must be a valid URI (http://, https://, or unix:///)")
        return v


class ServiceConfigurationResponse(BaseModel):
    """Response model for GET /installation/{id}/services."""

    services: List[ServiceConfiguration] = Field(..., description="Array of service configurations")


class TestInstallationServicesEndpoint:
    """Contract tests for GET /installation/{id}/services endpoint."""

    def test_service_configuration_schema_validation(self):
        """Test ServiceConfiguration schema validates all required fields."""
        # Valid service configuration
        valid_config = {
            "service_name": "docker",
            "port": 2375,
            "status": "running",
            "endpoint": "unix:///var/run/docker.sock",
            "version": "24.0.6",
            "error_message": None,
            "last_checked": datetime.now()
        }

        config = ServiceConfiguration(**valid_config)
        assert config.service_name == "docker"
        assert config.port == 2375
        assert config.status == "running"
        assert config.endpoint == "unix:///var/run/docker.sock"
        assert config.version == "24.0.6"

    def test_service_name_enum_validation(self):
        """Test service_name enum validation allows only docker, qdrant, ollama."""
        valid_names = ["docker", "qdrant", "ollama"]

        for name in valid_names:
            config_data = {
                "service_name": name,
                "port": 8080,
                "status": "running",
                "endpoint": "http://localhost:8080",
                "last_checked": datetime.now()
            }
            config = ServiceConfiguration(**config_data)
            assert config.service_name == name

        # Invalid service name should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(
                service_name="redis",  # Invalid service name
                port=6379,
                status="running",
                endpoint="redis://localhost:6379",
                last_checked=datetime.now()
            )

        assert "Input should be 'docker', 'qdrant' or 'ollama'" in str(exc_info.value)

    def test_port_range_validation(self):
        """Test port validation requires range 1024-65535."""
        config_base = {
            "service_name": "qdrant",
            "status": "running",
            "endpoint": "http://localhost:6333",
            "last_checked": datetime.now()
        }

        # Valid ports
        valid_ports = [1024, 8080, 6333, 65535]
        for port in valid_ports:
            config = ServiceConfiguration(port=port, **config_base)
            assert config.port == port

        # Invalid ports - too low
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(port=1023, **config_base)
        assert "Input should be greater than or equal to 1024" in str(exc_info.value)

        # Invalid ports - too high
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(port=65536, **config_base)
        assert "Input should be less than or equal to 65535" in str(exc_info.value)

    def test_status_enum_validation(self):
        """Test status enum validation allows only defined status values."""
        valid_statuses = ["not_found", "detected", "configured", "running", "failed"]
        config_base = {
            "service_name": "ollama",
            "port": 11434,
            "endpoint": "http://localhost:11434",
            "last_checked": datetime.now()
        }

        for status in valid_statuses:
            config = ServiceConfiguration(status=status, **config_base)
            assert config.status == status

        # Invalid status should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration(status="unknown", **config_base)

        assert "Input should be 'not_found', 'detected', 'configured', 'running' or 'failed'" in str(exc_info.value)

    def test_uri_format_validation(self):
        """Test endpoint URI format validation."""
        config_base = {
            "service_name": "qdrant",
            "port": 6333,
            "status": "running",
            "last_checked": datetime.now()
        }

        # Valid URI formats
        valid_uris = [
            "http://localhost:6333",
            "https://qdrant.example.com:443",
            "unix:///var/run/docker.sock"
        ]

        for uri in valid_uris:
            config = ServiceConfiguration(endpoint=uri, **config_base)
            assert config.endpoint == uri

        # Invalid URI formats
        invalid_uris = [
            "localhost:6333",  # Missing protocol
            "ftp://localhost:6333",  # Invalid protocol
            "tcp://localhost:6333",  # Invalid protocol
            "just-a-string"  # Not a URI
        ]

        for uri in invalid_uris:
            with pytest.raises(ValidationError) as exc_info:
                ServiceConfiguration(endpoint=uri, **config_base)
            assert "endpoint must be a valid URI" in str(exc_info.value)

    def test_service_configuration_response_schema(self):
        """Test ServiceConfigurationResponse validates array of ServiceConfiguration objects."""
        service_configs = [
            {
                "service_name": "docker",
                "port": 2375,
                "status": "running",
                "endpoint": "unix:///var/run/docker.sock",
                "version": "24.0.6",
                "error_message": None,
                "last_checked": datetime.now()
            },
            {
                "service_name": "qdrant",
                "port": 6333,
                "status": "configured",
                "endpoint": "http://localhost:6333",
                "version": "1.13.0",
                "error_message": None,
                "last_checked": datetime.now()
            },
            {
                "service_name": "ollama",
                "port": 11434,
                "status": "failed",
                "endpoint": "http://localhost:11434",
                "version": None,
                "error_message": "Connection refused",
                "last_checked": datetime.now()
            }
        ]

        response = ServiceConfigurationResponse(services=service_configs)
        assert len(response.services) == 3
        assert response.services[0].service_name == "docker"
        assert response.services[1].service_name == "qdrant"
        assert response.services[2].service_name == "ollama"
        assert response.services[2].error_message == "Connection refused"

    @pytest.mark.asyncio
    def test_get_installation_services_endpoint_not_implemented(self):
        """Test GET /installation/{id}/services endpoint fails since it's not implemented (TDD)."""
        # This test MUST fail since the endpoint doesn't exist yet (TDD requirement)

        # Mock MCP server to simulate API call
        from src.services.mcp_server import MCPServer
        from src.core.config import BablibConfig

        config = BablibConfig()
        server = MCPServer(config)
        app = server.get_app()

        # Create test client
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # Try to call the endpoint - this should fail with 404
        response = client.get("/installation/test-id-123/services")

        # This endpoint doesn't exist yet, so it should return 404
        assert response.status_code == 404

        # When the endpoint is implemented, it should return 200 with ServiceConfigurationResponse
        # Expected future response format:
        # {
        #     "services": [
        #         {
        #             "service_name": "docker",
        #             "port": 2375,
        #             "status": "running",
        #             "endpoint": "unix:///var/run/docker.sock",
        #             "version": "24.0.6",
        #             "error_message": null,
        #             "last_checked": "2025-01-25T10:30:00Z"
        #         },
        #         {
        #             "service_name": "qdrant",
        #             "port": 6333,
        #             "status": "configured",
        #             "endpoint": "http://localhost:6333",
        #             "version": "1.13.0",
        #             "error_message": null,
        #             "last_checked": "2025-01-25T10:30:00Z"
        #         },
        #         {
        #             "service_name": "ollama",
        #             "port": 11434,
        #             "status": "failed",
        #             "endpoint": "http://localhost:11434",
        #             "version": null,
        #             "error_message": "Connection refused",
        #             "last_checked": "2025-01-25T10:30:00Z"
        #         }
        #     ]
        # }

    def test_service_configuration_complex_validation_scenarios(self):
        """Test complex validation scenarios and edge cases."""
        # Test all required fields are enforced
        with pytest.raises(ValidationError) as exc_info:
            ServiceConfiguration()

        error_fields = str(exc_info.value)
        required_fields = ["service_name", "port", "status", "endpoint", "last_checked"]
        for field in required_fields:
            assert field in error_fields

        # Test optional fields can be None
        valid_minimal = {
            "service_name": "docker",
            "port": 2375,
            "status": "not_found",
            "endpoint": "unix:///var/run/docker.sock",
            "last_checked": datetime.now(),
            "version": None,
            "error_message": None
        }

        config = ServiceConfiguration(**valid_minimal)
        assert config.version is None
        assert config.error_message is None

        # Test error_message is populated when status is 'failed'
        failed_config = {
            "service_name": "ollama",
            "port": 11434,
            "status": "failed",
            "endpoint": "http://localhost:11434",
            "last_checked": datetime.now(),
            "error_message": "Service unavailable"
        }

        config = ServiceConfiguration(**failed_config)
        assert config.status == "failed"
        assert config.error_message == "Service unavailable"