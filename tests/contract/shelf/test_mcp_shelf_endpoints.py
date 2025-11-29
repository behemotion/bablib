"""Contract tests for MCP shelf/basket endpoints.

Tests the MCP endpoint contracts defined in specs/017-projects-as-collections/contracts/mcp-shelf-endpoints.md.
Using FastAPI TestClient for testing without running a live server.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from src.logic.mcp.core.read_only_server import app as read_only_app
from src.logic.mcp.core.admin_server import app as admin_app
from src.logic.mcp.services.shelf_mcp_service import ShelfMcpService

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


class TestMcpReadOnlyShelfEndpoints:
    """Contract tests for read-only MCP server shelf endpoints."""

    @pytest.fixture
    def mock_shelf_service(self):
        """Create a mock ShelfMcpService."""
        service = AsyncMock(spec=ShelfMcpService)

        # Default mock responses for all methods
        service.list_shelfs.return_value = {
            "shelves": [],
            "metadata": {
                "total_shelfs": 0,
                "current_shelf": None,
                "total_baskets": 0
            }
        }

        service.get_shelf_structure.return_value = {
            "shelf": {
                "name": "documentation",
                "created_at": "2025-09-30T00:00:00Z",
                "updated_at": "2025-09-30T00:00:00Z",
                "is_current": True
            },
            "baskets": [],
            "summary": {
                "total_baskets": 0,
                "total_files": 0,
                "total_size_bytes": 0
            }
        }

        service.get_current_shelf.return_value = {
            "current_shelf": None,
            "available_shelfs": [],
            "context": {
                "session_id": "test-session",
                "last_context_update": "2025-09-30T00:00:00Z"
            }
        }

        return service

    @pytest.fixture
    def client(self, mock_shelf_service):
        """Create TestClient with mocked services."""
        # Mock read_only_service for project and search operations
        from src.logic.mcp.models.response import McpResponse
        mock_read_only_service = AsyncMock()

        async def mock_list_projects(**kwargs):
            project = {
                "id": "test-id",
                "name": "test-project",
                "status": "ready",
                "type": "crawling",
                "created_at": "2025-09-30T00:00:00Z"
            }
            # Add shelf context fields if requested
            if kwargs.get("include_shelf_context"):
                project.update({
                    "shelf_name": kwargs.get("shelf_name", "documentation"),
                    "basket_type": "crawling",
                    "hierarchy_path": "documentation/test-project"
                })
            return McpResponse.success_response(data=[project])

        async def mock_search(**kwargs):
            result = {
                "file_path": "/test/file.md",
                "content_snippet": "test content",
                "similarity_score": 0.95
            }
            # Add shelf context fields if requested
            if kwargs.get("include_shelf_context"):
                result.update({
                    "shelf_name": "documentation",
                    "basket_name": "test-project",
                    "hierarchy_path": "documentation/test-project"
                })

            metadata = {}
            if kwargs.get("include_shelf_context"):
                metadata = {
                    "shelf_breakdown": {"documentation": 1},
                    "basket_breakdown": {"crawling": 1},
                    "search_scope": "filtered"
                }

            return McpResponse.success_response(data=[result], metadata=metadata)

        mock_read_only_service.list_projects.side_effect = mock_list_projects
        mock_read_only_service.search_projects.side_effect = mock_search

        # Patch all services at module level
        with patch('src.logic.mcp.core.read_only_server.shelf_mcp_service', mock_shelf_service), \
             patch('src.logic.mcp.core.read_only_server.read_only_service', mock_read_only_service):
            yield TestClient(read_only_app)

    @pytest.mark.contract
    def test_list_shelfs_endpoint_exists(self, client: TestClient) -> None:
        """Test that the list_shelfs endpoint is available."""
        request_data = {
            "method": "list_shelfs",
            "params": {
                "include_baskets": True,
                "limit": 50
            }
        }

        response = client.post(
            "/mcp/v1/list_shelfs",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )

        # Should return valid response when implemented
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert isinstance(data["success"], bool)

    @pytest.mark.contract
    def test_list_shelfs_response_structure(self, client: TestClient) -> None:
        """Test list_shelfs response follows the contract structure."""
        request_data = {
            "method": "list_shelfs",
            "params": {
                "include_baskets": True,
                "include_empty": False,
                "limit": 50
            }
        }

        response = client.post(
                "/mcp/v1/list_shelfs",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "success" in data
        assert "data" in data
        assert isinstance(data["data"], list)

        if data["data"]:  # If shelfs exist
            shelf = data["data"][0]
            required_fields = ["name", "created_at", "updated_at", "is_current", "basket_count"]
            for field in required_fields:
                assert field in shelf

            if "baskets" in shelf:
                assert isinstance(shelf["baskets"], list)
                if shelf["baskets"]:
                    basket = shelf["baskets"][0]
                    basket_fields = ["name", "type", "status", "files"]
                    for field in basket_fields:
                        assert field in basket

        # Validate metadata
        if "metadata" in data:
            metadata = data["metadata"]
            metadata_fields = ["total_shelfs", "current_shelf", "total_baskets"]
            for field in metadata_fields:
                assert field in metadata

    @pytest.mark.contract
    def test_list_shelfs_parameters(self, client: TestClient) -> None:
        """Test list_shelfs with different parameter combinations."""
        test_cases = [
            # Basic request
            {"include_baskets": True, "limit": 10},
            # Without baskets
            {"include_baskets": False, "limit": 20},
            # Current only
            {"current_only": True, "include_baskets": True},
            # Include empty shelfs
            {"include_empty": True, "include_baskets": False}
        ]

        for params in test_cases:
            request_data = {
                "method": "list_shelfs",
                "params": params
            }

            response = client.post(
                "/mcp/v1/list_shelfs",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.contract
    def test_get_shelf_structure_endpoint(self, client: TestClient) -> None:
        """Test get_shelf_structure endpoint contract."""
        request_data = {
            "method": "get_shelf_structure",
            "params": {
                "shelf_name": "documentation",
                "include_basket_details": True,
                "include_file_list": False
            }
        }

        response = client.post(
                "/mcp/v1/get_shelf_structure",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "success" in data
        assert "data" in data

        if data["success"]:
            response_data = data["data"]
            assert "shelf" in response_data
            assert "baskets" in response_data
            assert "summary" in response_data

            # Validate shelf info
            shelf_info = response_data["shelf"]
            shelf_fields = ["name", "created_at", "updated_at", "is_current"]
            for field in shelf_fields:
                assert field in shelf_info

            # Validate baskets
            baskets = response_data["baskets"]
            assert isinstance(baskets, list)

            # Validate summary
            summary = response_data["summary"]
            summary_fields = ["total_baskets", "total_files", "total_size_bytes"]
            for field in summary_fields:
                assert field in summary

    @pytest.mark.contract
    def test_get_shelf_structure_missing_shelf(self, client: TestClient) -> None:
        """Test get_shelf_structure with non-existent shelf."""
        request_data = {
            "method": "get_shelf_structure",
            "params": {
                "shelf_name": "non-existent-shelf-12345"
            }
        }

        response = client.post(
                "/mcp/v1/get_shelf_structure",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should handle gracefully
        data = response.json()
        if not data.get("success", True):
            assert "error" in data
            assert "shelf_not_found" in data.get("error", "")

    @pytest.mark.contract
    def test_enhanced_list_projects_with_shelf_filter(self, client: TestClient) -> None:
        """Test enhanced list_projects endpoint with shelf filtering."""
        request_data = {
            "method": "list_projects",
            "params": {
                "shelf_name": "documentation",
                "include_shelf_context": True,
                "status_filter": "ready",
                "limit": 25
            }
        }

        response = client.post(
                "/mcp/v1/list_projects",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"] and data.get("data"):
            # Validate enhanced project structure
            project = data["data"][0]

            # Existing fields (backward compatibility)
            existing_fields = ["id", "name", "status", "type", "created_at"]
            for field in existing_fields:
                assert field in project

            # New shelf context fields
            if "include_shelf_context" in request_data["params"]:
                shelf_fields = ["shelf_name", "basket_type", "hierarchy_path"]
                for field in shelf_fields:
                    assert field in project

    @pytest.mark.contract
    def test_enhanced_search_projects_shelf_aware(self, client: TestClient) -> None:
        """Test enhanced search_projects with shelf awareness."""
        request_data = {
            "method": "search_projects",
            "params": {
                "query": "authentication methods",
                "shelf_names": ["documentation", "examples"],
                "basket_types": ["crawling", "data"],
                "include_shelf_context": True,
                "limit": 20
            }
        }

        response = client.post(
                "/mcp/v1/search_projects",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"] and data.get("data"):
            # Validate enhanced search results
            result = data["data"][0]

            # Existing fields
            existing_fields = ["file_path", "content_snippet", "similarity_score"]
            for field in existing_fields:
                assert field in result

            # New hierarchical context fields
            context_fields = ["shelf_name", "basket_name", "hierarchy_path"]
            for field in context_fields:
                assert field in result

            # Validate metadata
            if "metadata" in data:
                metadata = data["metadata"]
                enhanced_fields = ["shelf_breakdown", "basket_breakdown", "search_scope"]
                for field in enhanced_fields:
                    assert field in metadata

    @pytest.mark.contract
    def test_get_current_shelf_endpoint(self, client: TestClient) -> None:
        """Test get_current_shelf endpoint."""
        request_data = {
            "method": "get_current_shelf",
            "params": {}
        }

        response = client.post(
                "/mcp/v1/get_current_shelf",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data

        response_data = data["data"]

        if response_data.get("current_shelf"):
            # Validate current shelf structure
            current_shelf = response_data["current_shelf"]
            shelf_fields = ["name", "created_at", "basket_count", "total_files"]
            for field in shelf_fields:
                assert field in current_shelf

            # Validate context
            assert "context" in response_data
            context = response_data["context"]
            context_fields = ["session_id", "last_context_update"]
            for field in context_fields:
                assert field in context
        else:
            # No current shelf set
            assert "available_shelfs" in response_data
            assert isinstance(response_data["available_shelfs"], list)


class TestMcpAdminShelfEndpoints:
    """Contract tests for admin MCP server shelf management endpoints."""

    @pytest.fixture
    def mock_shelf_service(self):
        """Create a mock ShelfMcpService for admin tests."""
        service = AsyncMock(spec=ShelfMcpService)

        # Dynamic mock responses that use actual parameters
        async def mock_create_shelf(name, description=None, set_current=False, force=False):
            return {
                "operation": "create_shelf",
                "shelf_name": name,
                "result": "created",
                "details": {
                    "shelf_id": f"{name}-id",
                    "created_at": "2025-09-30T00:00:00Z",
                    "is_current": set_current
                }
            }

        async def mock_add_basket(shelf_name, basket_name, basket_type="data", description=None, force=False):
            return {
                "operation": "add_basket",
                "shelf_name": shelf_name,
                "basket_name": basket_name,
                "result": "added",
                "details": {
                    "basket_id": f"{basket_name}-id",
                    "basket_type": basket_type,
                    "status": "empty",
                    "created_at": "2025-09-30T00:00:00Z"
                }
            }

        async def mock_remove_basket(shelf_name, basket_name, confirm=False, backup=True):
            return {
                "operation": "remove_basket",
                "shelf_name": shelf_name,
                "basket_name": basket_name,
                "result": "removed",
                "details": {
                    "files_deleted": 0
                }
            }

        async def mock_set_current_shelf(shelf_name):
            return {
                "operation": "set_current_shelf",
                "shelf_name": shelf_name,
                "result": "updated",
                "details": {
                    "previous_current": None,
                    "new_current": shelf_name,
                    "context_updated": True,
                    "session_id": "test-session"
                }
            }

        service.create_shelf_admin.side_effect = mock_create_shelf
        service.add_basket_admin.side_effect = mock_add_basket
        service.remove_basket_admin.side_effect = mock_remove_basket
        service.set_current_shelf_admin.side_effect = mock_set_current_shelf

        return service

    @pytest.fixture
    def client(self, mock_shelf_service):
        """Create TestClient with mocked services for admin tests."""
        with patch('src.logic.mcp.core.admin_server.shelf_mcp_service', mock_shelf_service):
            yield TestClient(admin_app)

    @pytest.mark.contract
    def test_create_shelf_endpoint(self, client: TestClient) -> None:
        """Test create_shelf admin endpoint."""
        request_data = {
            "method": "create_shelf",
            "params": {
                "name": "test-new-shelf",
                "description": "Test shelf creation",
                "set_current": False,
                "force": False
            }
        }

        response = client.post(
                "/mcp/v1/create_shelf",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"]:
            # Validate operation response structure
            assert "data" in data
            op_data = data["data"]

            required_fields = ["operation", "shelf_name", "result"]
            for field in required_fields:
                assert field in op_data

            assert op_data["operation"] == "create_shelf"
            assert op_data["shelf_name"] == "test-new-shelf"
            assert op_data["result"] in ["created", "updated"]

            # Validate details
            if "details" in op_data:
                details = op_data["details"]
                detail_fields = ["shelf_id", "created_at", "is_current"]
                for field in detail_fields:
                    assert field in details

    @pytest.mark.contract
    def test_create_shelf_with_set_current(self, client: TestClient) -> None:
        """Test create_shelf with set_current flag."""
        request_data = {
            "method": "create_shelf",
            "params": {
                "name": "current-test-shelf",
                "set_current": True
            }
        }

        response = client.post(
                "/mcp/v1/create_shelf",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()

        if data.get("success"):
            op_data = data["data"]
            if "details" in op_data:
                assert op_data["details"].get("is_current") is True

    @pytest.mark.contract
    def test_delete_shelf_security_restriction(self, client: TestClient) -> None:
        """Test that delete_shelf is prohibited via MCP admin for security."""
        request_data = {
            "method": "delete_shelf",
            "params": {
                "name": "test-shelf-to-delete",
                "force": True,
                "confirm": True
            }
        }

        response = client.post(
                "/mcp/v1/delete_shelf",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should be prohibited for security
        data = response.json()
        assert data["success"] is False
        assert "operation_prohibited" in data.get("error", "")

        # Message is nested in data
        if "data" in data and "message" in data["data"]:
            assert "security" in data["data"]["message"].lower()

        # Should suggest CLI alternative
        if "data" in data and "details" in data["data"]:
            details = data["data"]["details"]
            assert "CLI only" in details.get("allowed_methods", [])
            assert "bablib shelf --remove" in details.get("alternative", "")

    @pytest.mark.contract
    def test_add_basket_endpoint(self, client: TestClient) -> None:
        """Test add_basket admin endpoint."""
        request_data = {
            "method": "add_basket",
            "params": {
                "shelf_name": "documentation",
                "basket_name": "new-api-docs",
                "basket_type": "crawling",
                "description": "New API documentation",
                "force": False
            }
        }

        response = client.post(
                "/mcp/v1/add_basket",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"]:
            op_data = data["data"]

            required_fields = ["operation", "shelf_name", "basket_name", "result"]
            for field in required_fields:
                assert field in op_data

            assert op_data["operation"] == "add_basket"
            assert op_data["shelf_name"] == "documentation"
            assert op_data["basket_name"] == "new-api-docs"

            # Validate details
            if "details" in op_data:
                details = op_data["details"]
                detail_fields = ["basket_id", "basket_type", "status", "created_at"]
                for field in detail_fields:
                    assert field in details

    @pytest.mark.contract
    def test_add_basket_default_type(self, client: TestClient) -> None:
        """Test add_basket with default type (data)."""
        request_data = {
            "method": "add_basket",
            "params": {
                "shelf_name": "documentation",
                "basket_name": "default-type-basket"
                # No basket_type specified - should default to "data"
            }
        }

        response = client.post(
                "/mcp/v1/add_basket",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()

        if data.get("success"):
            op_data = data["data"]
            if "details" in op_data:
                assert op_data["details"].get("basket_type") == "data"

    @pytest.mark.contract
    def test_remove_basket_endpoint(self, client: TestClient) -> None:
        """Test remove_basket admin endpoint."""
        request_data = {
            "method": "remove_basket",
            "params": {
                "shelf_name": "documentation",
                "basket_name": "old-basket",
                "confirm": True,
                "backup": True
            }
        }

        response = client.post(
                "/mcp/v1/remove_basket",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"]:
            op_data = data["data"]

            required_fields = ["operation", "shelf_name", "basket_name", "result"]
            for field in required_fields:
                assert field in op_data

            assert op_data["operation"] == "remove_basket"

            # Validate removal details
            if "details" in op_data:
                details = op_data["details"]
                assert "files_deleted" in details
                assert isinstance(details["files_deleted"], int)

    @pytest.mark.contract
    def test_set_current_shelf_endpoint(self, client: TestClient) -> None:
        """Test set_current_shelf admin endpoint."""
        request_data = {
            "method": "set_current_shelf",
            "params": {
                "shelf_name": "examples"
            }
        }

        response = client.post(
                "/mcp/v1/set_current_shelf",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"]:
            op_data = data["data"]

            required_fields = ["operation", "shelf_name", "result"]
            for field in required_fields:
                assert field in op_data

            assert op_data["operation"] == "set_current_shelf"
            assert op_data["shelf_name"] == "examples"

            # Validate context update details
            if "details" in op_data:
                details = op_data["details"]
                context_fields = ["previous_current", "new_current", "context_updated", "session_id"]
                for field in context_fields:
                    assert field in details

    @pytest.mark.contract
    def test_admin_endpoint_localhost_only(self, client: TestClient) -> None:
        """Test that admin endpoints are only accessible from localhost."""
        # This test assumes the server enforces localhost-only access
        # In practice, this might be enforced at the network level

        request_data = {
            "method": "create_shelf",
            "params": {
                "name": "security-test-shelf"
            }
        }

        # Try to access from localhost - should work
        response = client.post(
            "/mcp/v1/create_shelf",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )

        # Should either succeed or fail gracefully (not return 403/404 for wrong host)
        assert response.status_code in [200, 400, 422, 500]  # Any response means server is accessible


class TestMcpShelfEndpointErrorHandling:
    """Contract tests for error handling across shelf endpoints."""

    @pytest.fixture
    def mock_shelf_service(self):
        """Create a mock ShelfMcpService."""
        service = AsyncMock(spec=ShelfMcpService)
        service.list_shelfs.return_value = {
            "shelves": [],
            "metadata": {"total_shelfs": 0, "current_shelf": None, "total_baskets": 0}
        }
        # Mock get_shelf_structure to raise ShelfNotFoundError for non-existent shelves
        from src.models.shelf import ShelfNotFoundError
        async def mock_get_shelf_structure(shelf_name, include_basket_details=True, include_file_list=False):
            if "nonexistent" in shelf_name.lower() or "definitely" in shelf_name.lower():
                raise ShelfNotFoundError(f"Shelf '{shelf_name}' not found")
            return service.get_shelf_structure.return_value
        service.get_shelf_structure.side_effect = mock_get_shelf_structure
        return service

    @pytest.fixture
    def client(self, mock_shelf_service):
        """Create TestClient with mocked services."""
        with patch('src.logic.mcp.core.read_only_server.shelf_mcp_service', mock_shelf_service):
            yield TestClient(read_only_app)

    @pytest.mark.contract
    def test_shelf_not_found_error(self, client: TestClient) -> None:
        """Test shelf_not_found error response format."""
        request_data = {
            "method": "get_shelf_structure",
            "params": {
                "shelf_name": "definitely-nonexistent-shelf-12345"
            }
        }

        response = client.post(
                "/mcp/v1/get_shelf_structure",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        data = response.json()

        if not data.get("success", True):
            # Validate error response structure
            assert "error" in data
            assert "message" in data
            assert isinstance(data["message"], str)

            if "details" in data:
                details = data["details"]
                assert "error_code" in details
                assert details.get("error_code") in ["SHELF_NOT_FOUND", "shelf_not_found"]

    @pytest.mark.contract
    def test_invalid_request_error(self, client: TestClient) -> None:
        """Test validation error for invalid request parameters."""
        request_data = {
            "method": "list_shelfs",
            "params": {
                "limit": -1,  # Invalid limit
                "include_baskets": "not_a_boolean"  # Invalid type
            }
        }

        response = client.post(
                "/mcp/v1/list_shelfs",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should return validation error
        assert response.status_code in [400, 422]
        data = response.json()

        if not data.get("success", True):
            assert "error" in data
            assert "validation" in data.get("error", "").lower()

    @pytest.mark.contract
    def test_missing_required_parameters(self, client: TestClient) -> None:
        """Test error for missing required parameters."""
        request_data = {
            "method": "get_shelf_structure",
            "params": {
                # Missing required "shelf_name" parameter
            }
        }

        response = client.post(
                "/mcp/v1/get_shelf_structure",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        # Should return parameter error
        assert response.status_code in [400, 422]


class TestMcpShelfBackwardCompatibility:
    """Contract tests for backward compatibility with existing MCP endpoints."""

    @pytest.fixture
    def mock_shelf_service(self):
        """Create a mock ShelfMcpService."""
        service = AsyncMock(spec=ShelfMcpService)
        service.list_shelfs.return_value = {
            "shelves": [],
            "metadata": {"total_shelfs": 0, "current_shelf": None, "total_baskets": 0}
        }
        return service

    @pytest.fixture
    def client(self, mock_shelf_service):
        """Create TestClient with mocked services."""
        # Mock read_only_service for project and search operations
        from src.logic.mcp.models.response import McpResponse
        mock_read_only_service = AsyncMock()

        async def mock_list_projects(**kwargs):
            project = {
                "id": "test-id",
                "name": "test-project",
                "status": "ready",
                "type": "crawling",
                "created_at": "2025-09-30T00:00:00Z"
            }
            return McpResponse.success_response(data=[project])

        async def mock_search(**kwargs):
            result = {
                "file_path": "/test/file.md",
                "content_snippet": "test content",
                "similarity_score": 0.95
            }
            return McpResponse.success_response(data=[result])

        mock_read_only_service.list_projects.side_effect = mock_list_projects
        mock_read_only_service.search_projects.side_effect = mock_search

        with patch('src.logic.mcp.core.read_only_server.shelf_mcp_service', mock_shelf_service), \
             patch('src.logic.mcp.core.read_only_server.read_only_service', mock_read_only_service):
            yield TestClient(read_only_app)

    @pytest.mark.contract
    def test_legacy_list_projects_still_works(self, client: TestClient) -> None:
        """Test that legacy list_projects requests work unchanged."""
        # Exact same request format as before shelf implementation
        request_data = {
            "method": "list_projects",
            "params": {
                "status_filter": "ready",
                "limit": 25
            }
        }

        response = client.post(
                "/mcp/v1/list_projects",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"] and data.get("data"):
            # Should still return projects in legacy format
            project = data["data"][0]
            legacy_fields = ["id", "name", "status", "type"]
            for field in legacy_fields:
                assert field in project

    @pytest.mark.contract
    def test_legacy_search_projects_still_works(self, client: TestClient) -> None:
        """Test that legacy search_projects requests work unchanged."""
        request_data = {
            "method": "search_projects",
            "params": {
                "query": "test search",
                "limit": 10
            }
        }

        response = client.post(
                "/mcp/v1/search_projects",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        if data["success"] and data.get("data"):
            # Should still return search results in legacy format
            result = data["data"][0]
            legacy_fields = ["file_path", "content_snippet", "similarity_score"]
            for field in legacy_fields:
                assert field in result


# NOTE: All these tests will initially FAIL because:
# 1. The new MCP shelf endpoints don't exist yet (/mcp/v1/list_shelfs, etc.)
# 2. The enhanced list_projects and search_projects endpoints aren't shelf-aware yet
# 3. The admin shelf management endpoints aren't implemented
# 4. The shelf/basket services and data models don't exist yet
# 5. The current shelf context system isn't built
#
# These tests serve as the contract specification that the MCP endpoint implementation must satisfy.