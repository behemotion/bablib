#!/usr/bin/env python3
"""
Bablib MCP Client Example

This example shows how to connect to the Bablib MCP server.

IMPORTANT: MCP uses a custom protocol, not standard REST/HTTP.
Standard HTTP clients (requests, curl) will NOT work for MCP endpoints.

Server Information:
- Read-Only Server: http://0.0.0.0:9383
- Admin Server: http://127.0.0.1:9384 (localhost only)
- Health Endpoint: GET /mcp/v1/health (standard HTTP - only exception)

Requirements:
    pip install httpx asyncio
"""

import asyncio
import json
from typing import Dict, Any, Optional
import httpx


class BablibMCPClient:
    """
    Basic MCP client for Bablib server.

    Note: This is a simplified example. Full MCP protocol implementation
    requires handling request/response framing, session management, and
    capability negotiation.

    For production use, consider:
    1. Using Claude Desktop (official MCP client)
    2. Using Claude Code CLI (has built-in MCP tools)
    3. Implementing full MCP protocol from https://modelcontextprotocol.io
    """

    def __init__(self, base_url: str = "http://0.0.0.0:9383"):
        """
        Initialize MCP client.

        Args:
            base_url: Base URL of the MCP server (default: read-only server)
        """
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check server health (standard HTTP endpoint).

        This is the ONLY endpoint that works with standard HTTP.
        All other endpoints require MCP protocol.

        Returns:
            Health status dictionary
        """
        response = await self.client.get(f"{self.base_url}/mcp/v1/health")
        response.raise_for_status()
        return response.json()

    async def mcp_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send MCP protocol request.

        WARNING: This is a simplified placeholder. Real MCP protocol requires:
        - Request/response framing
        - Session management
        - Capability negotiation
        - Proper error handling

        For production use, use an MCP-compliant client like Claude Desktop.

        Args:
            method: MCP method name (e.g., "search", "list_projects")
            params: Method parameters

        Returns:
            Response dictionary
        """
        # This is a placeholder - MCP protocol requires special formatting
        # Standard HTTP POST will return: {"detail": "Invalid method"}

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }

        response = await self.client.post(
            f"{self.base_url}/mcp/v1/rpc",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        return response.json()


async def main():
    """Example usage of Bablib MCP client."""

    # Initialize client
    client = BablibMCPClient("http://0.0.0.0:9383")

    try:
        # 1. Health Check (Works with standard HTTP)
        print("=" * 60)
        print("1. Health Check (Standard HTTP - Works)")
        print("=" * 60)

        health = await client.health_check()
        print(f"Server Status: {health.get('status')}")
        print(f"Server Version: {health.get('version', 'N/A')}")
        print(f"Health: {json.dumps(health, indent=2)}")
        print()

        # 2. MCP Protocol Request (Requires MCP client)
        print("=" * 60)
        print("2. MCP Protocol Request (Standard HTTP - Will Fail)")
        print("=" * 60)
        print("Attempting to call MCP endpoint with standard HTTP...")
        print("Expected result: {'detail': 'Invalid method'}")
        print()

        try:
            result = await client.mcp_request("list_projects")
            print(f"Response: {json.dumps(result, indent=2)}")
        except httpx.HTTPStatusError as e:
            print(f"Error (expected): {e}")
            print("This is normal - MCP endpoints don't work with standard HTTP")

        print()
        print("=" * 60)
        print("How to Use MCP Endpoints Properly")
        print("=" * 60)
        print("""
For actual MCP operations (search, list, execute), use:

1. Claude Desktop:
   - Official MCP client with built-in integration
   - Auto-discovers MCP servers
   - Handles protocol automatically

2. Claude Code CLI:
   - Official CLI with dedicated MCP tools
   - File access capabilities
   - Command execution support

3. Custom MCP Implementation:
   - Follow spec: https://modelcontextprotocol.io
   - Implement request/response framing
   - Handle session management
   - Support capability negotiation

Example MCP operations available:
- list_projects: Get all documentation projects
- search: Semantic search across documents
- get_file: Read file contents
- list_files: List files in project
        """)

    finally:
        await client.close()


async def example_with_claude_desktop():
    """
    Example of how MCP works with Claude Desktop.

    This is for documentation purposes - shows the proper way
    to use MCP endpoints.
    """
    print("=" * 60)
    print("Claude Desktop MCP Configuration")
    print("=" * 60)

    config = {
        "mcpServers": {
            "bablib": {
                "command": "bablib",
                "args": ["serve"],
                "env": {}
            }
        }
    }

    print("Add this to Claude Desktop config:")
    print(f"Location: ~/Library/Application Support/Claude/claude_desktop_config.json")
    print()
    print(json.dumps(config, indent=2))
    print()
    print("Then restart Claude Desktop to enable MCP integration.")
    print()
    print("Available MCP commands in Claude Desktop:")
    print("  - 'Search my documentation for...'")
    print("  - 'List all my projects'")
    print("  - 'Show me the content of...'")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║          Bablib MCP Client Connection Example               ║
║                                                              ║
║  Server: http://0.0.0.0:9383 (Read-Only MCP Server)        ║
║  Protocol: MCP (Model Context Protocol)                     ║
║                                                              ║
║  Note: Only health endpoint works with standard HTTP        ║
║        All other endpoints require MCP protocol client      ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Run the example
    asyncio.run(main())

    print()
    asyncio.run(example_with_claude_desktop())
