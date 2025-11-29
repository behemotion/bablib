"""
Integration tests for MCP protocol implementation.

Tests the /mcp endpoint with JSON-RPC 2.0 messages.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from src.logic.mcp.core.read_only_server import app as read_only_app
from src.logic.mcp.core.admin_server import app as admin_app


class TestMcpProtocolInitialize:
    """Test MCP protocol initialization handshake."""

    @pytest.mark.asyncio
    async def test_initialize_read_only_server(self):
        """Test initialize request on read-only server."""
        transport = ASGITransport(app=read_only_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send initialize request
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0",
                    },
                },
            }

            response = await client.post("/mcp", json=request)

            assert response.status_code == 200
            data = response.json()

            # Validate JSON-RPC response
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 1
            assert "result" in data
            assert data["error"] is None

            # Validate MCP initialize response
            result = data["result"]
            assert result["protocolVersion"] == "2024-11-05"
            assert "capabilities" in result
            assert result["serverInfo"]["name"] == "bablib"
            assert result["serverInfo"]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_initialize_admin_server(self):
        """Test initialize request on admin server."""
        async with AsyncClient(app=admin_app, base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0",
                    },
                },
            }

            response = await client.post("/mcp", json=request)

            assert response.status_code == 200
            data = response.json()

            assert data["jsonrpc"] == "2.0"
            result = data["result"]
            assert result["serverInfo"]["name"] == "bablib-admin"


class TestMcpProtocolPing:
    """Test MCP ping endpoint."""

    @pytest.mark.asyncio
    async def test_ping_without_initialization(self):
        """Test that ping works without initialization."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "ping",
            }

            response = await client.post("/mcp", json=request)

            assert response.status_code == 200
            data = response.json()

            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 1
            assert data["result"] == {}
            assert data["error"] is None


class TestMcpToolsEndpoints:
    """Test MCP tools/list and tools/call endpoints."""

    @pytest.mark.asyncio
    async def test_tools_list_requires_initialization(self):
        """Test that tools/list requires server initialization."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
            }

            response = await client.post("/mcp", json=request)

            assert response.status_code == 200
            data = response.json()

            # Should return error - server not initialized
            assert data["error"] is not None
            assert data["error"]["code"] == -32002  # SERVER_NOT_INITIALIZED

    @pytest.mark.asyncio
    async def test_tools_list_after_initialization(self):
        """Test tools/list returns Bablib commands."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            # First, initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
            await client.post("/mcp", json=init_request)

            # Now request tools list
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }

            response = await client.post("/mcp", json=tools_request)

            assert response.status_code == 200
            data = response.json()

            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 2
            assert "result" in data

            # Validate tools list
            result = data["result"]
            assert "tools" in result
            tools = result["tools"]

            # Should have shelf, box, and search tools
            tool_names = [tool["name"] for tool in tools]
            assert "bablib_shelf_list" in tool_names
            assert "bablib_box_list" in tool_names
            assert "bablib_search" in tool_names

    @pytest.mark.asyncio
    async def test_admin_server_has_more_tools(self):
        """Test that admin server exposes admin tools."""
        async with AsyncClient(app=admin_app, base_url="http://test") as client:
            # Initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
            await client.post("/mcp", json=init_request)

            # Get tools list
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }

            response = await client.post("/mcp", json=tools_request)
            data = response.json()

            tools = data["result"]["tools"]
            tool_names = [tool["name"] for tool in tools]

            # Admin server should have create/modify tools
            assert "bablib_shelf_create" in tool_names
            assert "bablib_box_create" in tool_names
            assert "bablib_fill" in tool_names


class TestMcpResourcesEndpoints:
    """Test MCP resources endpoints."""

    @pytest.mark.asyncio
    async def test_resources_list_requires_initialization(self):
        """Test that resources/list requires initialization."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/list",
            }

            response = await client.post("/mcp", json=request)
            data = response.json()

            assert data["error"] is not None
            assert data["error"]["code"] == -32002

    @pytest.mark.asyncio
    async def test_resources_templates_list(self):
        """Test resources/templates/list returns URI templates."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            # Initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
            await client.post("/mcp", json=init_request)

            # Get templates
            templates_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/templates/list",
            }

            response = await client.post("/mcp", json=templates_request)
            data = response.json()

            assert response.status_code == 200
            assert "result" in data

            result = data["result"]
            assert "resourceTemplates" in result
            templates = result["resourceTemplates"]

            # Should have shelf and box templates
            template_uris = [t["uriTemplate"] for t in templates]
            assert "bablib://shelf/{name}" in template_uris
            assert "bablib://box/{name}" in template_uris


class TestMcpErrorHandling:
    """Test MCP protocol error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_rpc_request(self):
        """Test handling of invalid JSON-RPC request."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            # Missing required field
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                # Missing "method"
            }

            response = await client.post("/mcp", json=request)
            data = response.json()

            assert data["error"] is not None
            assert data["error"]["code"] == -32600  # INVALID_REQUEST

    @pytest.mark.asyncio
    async def test_method_not_found(self):
        """Test handling of unknown method."""
        async with AsyncClient(app=read_only_app, base_url="http://test") as client:
            # Initialize first
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
            await client.post("/mcp", json=init_request)

            # Try unknown method
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "unknown/method",
            }

            response = await client.post("/mcp", json=request)
            data = response.json()

            assert data["error"] is not None
            assert data["error"]["code"] == -32601  # METHOD_NOT_FOUND
