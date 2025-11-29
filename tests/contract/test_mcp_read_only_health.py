"""Contract test for read-only server /mcp/v1/health endpoint.

This test validates the MCP read-only server's health endpoint
against the OpenAPI specification in contracts/mcp-read-only-server.json.
"""

import pytest
import httpx


class TestMcpReadOnlyHealth:
    """Contract tests for /mcp/v1/health endpoint."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for read-only MCP server."""
        return "http://localhost:9383"

    @pytest.mark.contract
    @pytest.mark.asyncio
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
    @pytest.mark.asyncio
    async def test_health_response_schema(self, base_url: str) -> None:
        """Test that health response matches OpenAPI HealthResponse schema."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Validate HealthResponse schema
        health_data = data["data"]
        required_fields = ["server_type", "status", "bablib_health"]
        for field in required_fields:
            assert field in health_data

        # Validate field types and constraints
        assert health_data["server_type"] == "read-only"
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]
        assert isinstance(health_data["bablib_health"], dict)

    @pytest.mark.contract
    @pytest.mark.asyncio
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
    @pytest.mark.asyncio
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
    @pytest.mark.asyncio
    async def test_health_response_headers(self, base_url: str) -> None:
        """Test that health response has correct headers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/mcp/v1/health")

        assert response.status_code == 200

        # Should return JSON content type
        assert "application/json" in response.headers.get("content-type", "")