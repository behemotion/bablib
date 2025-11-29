"""Contract test for admin server /mcp/v1/execute_command endpoint.

This test validates the MCP admin server's command execution endpoint
against the OpenAPI specification in contracts/mcp-admin-server.json.
"""

import pytest
import httpx


class TestMcpAdminExecuteCommand:
    """Contract tests for /mcp/v1/execute_command endpoint."""

    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for admin MCP server (localhost only)."""
        return "http://127.0.0.1:9384"

    @pytest.mark.contract
    async def test_execute_command_basic_request(self, base_url: str) -> None:
        """Test basic command execution request."""
        request_data = {
            "method": "execute_command",
            "params": {
                "command": "health"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Validate response structure according to OpenAPI spec
        assert response.status_code == 200
        data = response.json()

        # Check response schema
        assert "success" in data
        assert isinstance(data["success"], bool)
        assert "data" in data
        assert isinstance(data["data"], dict)

        # Check command execution data structure
        exec_data = data["data"]
        required_fields = ["command", "exit_code", "stdout", "stderr", "execution_time_ms"]
        for field in required_fields:
            assert field in exec_data

        assert exec_data["command"] == "health"
        assert isinstance(exec_data["exit_code"], int)
        assert isinstance(exec_data["stdout"], str)
        assert isinstance(exec_data["stderr"], str)
        assert isinstance(exec_data["execution_time_ms"], (int, float))

    @pytest.mark.contract
    async def test_execute_command_with_arguments(self, base_url: str) -> None:
        """Test command execution with arguments."""
        request_data = {
            "method": "execute_command",
            "params": {
                "command": "project",
                "arguments": ["--list"]
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()

        exec_data = data["data"]
        assert exec_data["command"] == "project"

    @pytest.mark.contract
    async def test_execute_command_with_options(self, base_url: str) -> None:
        """Test command execution with options/flags."""
        request_data = {
            "method": "execute_command",
            "params": {
                "command": "project",
                "arguments": ["--list"],
                "options": {
                    "verbose": True,
                    "limit": 10
                }
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()

        exec_data = data["data"]
        assert exec_data["command"] == "project"

    @pytest.mark.contract
    async def test_execute_command_with_timeout(self, base_url: str) -> None:
        """Test command execution with custom timeout."""
        request_data = {
            "method": "execute_command",
            "params": {
                "command": "health",
                "timeout": 60
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200

    @pytest.mark.contract
    async def test_execute_command_invalid_command(self, base_url: str) -> None:
        """Test command execution with invalid command fails."""
        request_data = {
            "method": "execute_command",
            "params": {
                "command": "invalid_command"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should handle invalid commands gracefully
        assert response.status_code == 200
        data = response.json()

        # Success may be false for invalid commands
        if not data["success"]:
            assert "error" in data
            assert isinstance(data["error"], str)

    @pytest.mark.contract
    async def test_execute_command_missing_command(self, base_url: str) -> None:
        """Test command execution without required command parameter fails."""
        request_data = {
            "method": "execute_command",
            "params": {}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should return an error for missing required parameter
        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_execute_command_allowed_commands_only(self, base_url: str) -> None:
        """Test that only allowed Bablib commands can be executed."""
        allowed_commands = ["project", "crawl", "setup", "health", "upload"]

        for command in allowed_commands:
            request_data = {
                "method": "execute_command",
                "params": {
                    "command": command
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/mcp/v1/execute_command",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )

            # Should accept allowed commands
            assert response.status_code == 200

    @pytest.mark.contract
    async def test_execute_command_serve_blocked(self, base_url: str) -> None:
        """Test that 'serve' command is blocked to prevent recursion."""
        request_data = {
            "method": "execute_command",
            "params": {
                "command": "serve"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp/v1/execute_command",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should reject serve command to prevent recursion
        # Could be 400 for validation error or 200 with success=false
        if response.status_code == 200:
            data = response.json()
            assert not data["success"]  # Should fail
        else:
            assert response.status_code in [400, 422]