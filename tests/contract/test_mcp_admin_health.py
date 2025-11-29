"""Contract test for admin server /mcp/v1/health endpoint.

This test validates the MCP admin server's health endpoint
against the OpenAPI specification in contracts/mcp-admin-server.json.
"""

import pytest
import httpx


class TestMcpAdminHealth:
    """Contract tests for /mcp/v1/health endpoint."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for admin MCP server (localhost only)."""
        return "http://127.0.0.1:9384"

    @pytest.mark.contract
    async def test_health_endpoint_basic_request(self, base_url: str) -> None:
        """Test basic health check request."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        # Validate response structure according to OpenAPI spec
        assert response.status_code == 200
        data = response.json()

        # Check response schema
        assert "success" in data
        assert isinstance(data["success"], bool)
        assert "data" in data
        assert isinstance(data["data"], dict)

    @pytest.mark.contract
    async def test_health_response_schema(self, base_url: str) -> None:
        """Test that health response matches OpenAPI HealthResponse schema."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Validate HealthResponse schema
        health_data = data["data"]
        required_fields = ["server_type", "status", "bablib_health", "security_status"]
        for field in required_fields:
            assert field in health_data

        # Validate field types and constraints
        assert health_data["server_type"] == "admin"
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]
        assert isinstance(health_data["bablib_health"], dict)
        assert isinstance(health_data["security_status"], dict)

    @pytest.mark.contract
    async def test_health_security_status_schema(self, base_url: str) -> None:
        """Test that security status matches OpenAPI schema."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200
        data = response.json()

        security_status = data["data"]["security_status"]
        required_fields = ["localhost_only", "port"]
        for field in required_fields:
            assert field in security_status

        # Validate security status constraints
        assert isinstance(security_status["localhost_only"], bool)
        assert security_status["localhost_only"] is True  # Admin server must be localhost only
        assert isinstance(security_status["port"], int)
        assert security_status["port"] == 9384  # Default admin server port

    @pytest.mark.contract
    async def test_health_includes_bablib_health_output(self, base_url: str) -> None:
        """Test that health response includes Bablib health command output."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Should include output from `bablib health` command
        health_data = data["data"]
        bablib_health = health_data["bablib_health"]

        # Bablib health output should contain system information
        # The exact structure depends on the actual `bablib health` implementation
        assert isinstance(bablib_health, dict)
        assert len(bablib_health) > 0  # Should not be empty

    @pytest.mark.contract
    async def test_health_localhost_only_verification(self, base_url: str) -> None:
        """Test that admin server health endpoint is only accessible from localhost."""
        # This test verifies the admin server is properly bound to localhost only
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Verify security status indicates localhost-only binding
        security_status = data["data"]["security_status"]
        assert security_status["localhost_only"] is True

    @pytest.mark.contract
    async def test_health_endpoint_method_validation(self, base_url: str) -> None:
        """Test that health endpoint only accepts GET requests."""
        async with httpx.AsyncClient() as client:
            # POST should not be allowed
            post_response = await client.post(f"{base_url}/mcp/v1/health")
            assert post_response.status_code == 405  # Method Not Allowed

            # PUT should not be allowed
            put_response = await client.put(f"{base_url}/mcp/v1/health")
            assert put_response.status_code == 405  # Method Not Allowed

            # DELETE should not be allowed
            delete_response = await client.delete(f"{base_url}/mcp/v1/health")
            assert delete_response.status_code == 405  # Method Not Allowed

    @pytest.mark.contract
    async def test_health_response_headers(self, base_url: str) -> None:
        """Test that health response has correct headers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200

        # Should return JSON content type
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.contract
    async def test_health_admin_vs_read_only_distinction(self, base_url: str) -> None:
        """Test that admin health response clearly identifies server type."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200
        data = response.json()

        health_data = data["data"]
        # Admin server should clearly identify itself
        assert health_data["server_type"] == "admin"

        # Admin server should include security status
        assert "security_status" in health_data

        # Security status should indicate admin-specific restrictions
        security_status = health_data["security_status"]
        assert security_status["localhost_only"] is True