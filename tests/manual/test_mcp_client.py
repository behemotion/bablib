#!/usr/bin/env python3
"""Test MCP client for Bablib server."""

import asyncio
import httpx
import json
from typing import Dict, Any, List


class BablibMCPClient:
    """Simple MCP client for Bablib server."""

    def __init__(self, base_url: str = "http://localhost:9382"):
        self.base_url = base_url
        # Use test token for authentication
        self.token = "valid-test-token"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {self.token}"}
        )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def connect(self):
        """Establish MCP connection and get session."""
        try:
            response = await self.client.post(
                f"{self.base_url}/mcp/connect",
                json={
                    "client_name": "test_client",
                    "client_version": "1.0.0",
                    "capabilities": ["search", "projects"]
                }
            )
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id", "")
                return True
        except Exception as e:
            print(f"Connection error: {e}")
        return False

    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects."""
        response = await self.client.get(f"{self.base_url}/mcp/projects")
        response.raise_for_status()
        return response.json()

    async def search(self, query: str, project: str = None, limit: int = 5) -> Dict[str, Any]:
        """Search documents."""
        params = {
            "query": query,
            "limit": limit
        }
        if project:
            params["project"] = project

        response = await self.client.post(
            f"{self.base_url}/mcp/search",
            json=params
        )
        response.raise_for_status()
        return response.json()

    async def get_project_info(self, project_name: str) -> Dict[str, Any]:
        """Get project information."""
        response = await self.client.get(f"{self.base_url}/mcp/projects/{project_name}")
        response.raise_for_status()
        return response.json()


async def test_mcp_connection():
    """Test MCP server connectivity and functionality."""
    print("Testing Bablib MCP Server Connection...")
    print("=" * 50)

    async with BablibMCPClient() as client:
        # Connection status
        print("\n0. MCP Connection:")
        if client.token:
            print(f"   ✓ Connected with session: {client.token[:20]}...")
        else:
            print(f"   ✗ Failed to establish MCP connection")

        # Test 1: Health Check
        print("\n1. Health Check:")
        try:
            health = await client.health_check()
            print(f"   ✓ Server is healthy")
            print(f"   - Database: {'✓' if health['services']['database'] else '✗'}")
            print(f"   - Vector Store: {'✓' if health['services']['vector_store'] else '✗'}")
            print(f"   - Embeddings: {'✓' if health['services']['embeddings'] else '✗'}")
        except Exception as e:
            print(f"   ✗ Health check failed: {e}")
            return

        # Test 2: List Projects
        print("\n2. List Projects:")
        try:
            projects = await client.list_projects()
            print(f"   ✓ Found {len(projects)} projects")
            for proj in projects[:3]:  # Show first 3
                print(f"   - {proj['name']}: {proj['status']} ({proj['total_pages']} pages)")
        except Exception as e:
            print(f"   ✗ Failed to list projects: {e}")

        # Test 3: Search in UV Docs
        print("\n3. Search Test (UV Docs):")
        try:
            results = await client.search(
                query="python package manager rust",
                project="uv-docs",
                limit=3
            )
            print(f"   ✓ Found {len(results.get('results', []))} results")
            for i, result in enumerate(results.get('results', [])[:3], 1):
                print(f"   {i}. Score: {result['score']:.3f}")
                print(f"      Title: {result['metadata'].get('title', 'N/A')}")
                print(f"      URL: {result['metadata'].get('url', 'N/A')}")
                content = result['metadata'].get('content', '')[:100]
                print(f"      Content: {content}...")
        except Exception as e:
            print(f"   ✗ Search failed: {e}")

        # Test 4: Get Project Info
        print("\n4. Project Info (UV Docs):")
        try:
            info = await client.get_project_info("uv-docs")
            print(f"   ✓ Project: {info['name']}")
            print(f"   - Status: {info['status']}")
            print(f"   - Pages: {info['total_pages']}")
            print(f"   - Source: {info['source_url']}")
            print(f"   - Created: {info['created_at']}")
        except Exception as e:
            print(f"   ✗ Failed to get project info: {e}")

    print("\n" + "=" * 50)
    print("MCP Server Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())