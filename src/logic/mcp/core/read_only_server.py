"""Read-only MCP server FastAPI application."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Dict, Any, Optional, List

from src.logic.mcp.models.response import McpResponse
from src.logic.mcp.services.read_only import ReadOnlyMcpService
from src.logic.mcp.services.shelf_mcp_service import ShelfMcpService
from src.logic.projects.core.project_manager import ProjectManager
from src.logic.rag.core.search_service import RAGSearchService
from src.models.shelf import ShelfNotFoundError

# MCP Protocol imports
from src.logic.mcp.protocol.handler import ProtocolHandler
from src.logic.mcp.protocol.transport import HttpTransport
from src.logic.mcp.protocol.capabilities import ServerCapabilities
from src.logic.mcp.services.tools_service import ToolsService
from src.logic.mcp.services.resources_service import ResourcesService

logger = logging.getLogger(__name__)


class McpReadOnlyServer:
    """MCP Read-Only Server class for testing compatibility."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9383):
        self.host = host
        self.port = port
        self.app = app
        self.project_service = None
        self.search_service = None
        self.read_only_service = None

    async def start(self):
        """Start the server."""
        await initialize_services()
        return self

    async def stop(self):
        """Stop the server."""
        pass

    def get_app(self):
        """Get the FastAPI app."""
        return self.app

# Create FastAPI app
app = FastAPI(
    title="Bablib MCP Read-Only Server",
    version="1.0.0",
    description="MCP server providing read-only access to Bablib projects and documentation"
)


# Dependency injection - these would be properly initialized in production
project_service = None  # Will be injected
search_service = None   # Will be injected
read_only_service = None  # Will be injected
shelf_mcp_service = None  # Will be injected

# MCP Protocol components
protocol_handler = None  # Will be initialized
http_transport = None  # Will be initialized
tools_service = None  # Will be initialized
resources_service = None  # Will be initialized


async def initialize_services():
    """Initialize services for the read-only server."""
    global project_service, search_service, read_only_service, shelf_mcp_service
    global protocol_handler, http_transport, tools_service, resources_service

    # Initialize services with proper dependencies
    from src.logic.projects.core.project_manager import ProjectManager
    from src.logic.rag.core.search_service import RAGSearchService
    from src.services.vector_store_factory import VectorStoreFactory
    from src.services.embeddings import EmbeddingService
    from src.core.config import get_config

    # Get configuration
    config = get_config()

    # Initialize dependencies
    vector_store = VectorStoreFactory.create_vector_store(config)
    embedding_service = EmbeddingService(config)

    # Initialize main services
    project_service = ProjectManager()
    logger.info(f"ProjectManager initialized with data directory: {project_service.data_directory}")
    logger.info(f"ProjectManager registry path: {project_service.registry_path}")
    await project_service._ensure_db_initialized()

    # Test project listing for debugging
    projects = await project_service.list_projects()
    logger.info(f"Projects found: {len(projects)}")
    for project in projects:
        logger.info(f"  - {project.name} ({project.type})")

    search_service = RAGSearchService(vector_store, embedding_service, config)
    read_only_service = ReadOnlyMcpService(project_service, search_service)

    # Initialize shelf MCP service
    shelf_mcp_service = ShelfMcpService()
    await shelf_mcp_service.initialize()
    logger.info("ShelfMcpService initialized")

    # Initialize MCP protocol components
    capabilities = ServerCapabilities.default_read_only()
    protocol_handler = ProtocolHandler(
        server_name="bablib",
        server_version="1.0.0",
        capabilities=capabilities,
    )
    http_transport = HttpTransport(protocol_handler)

    # Initialize MCP services
    tools_service = ToolsService(is_admin=False)  # Read-only
    resources_service = ResourcesService()

    # Register MCP protocol methods
    protocol_handler.register_method("tools/list", tools_service.handle_tools_list)
    protocol_handler.register_method("tools/call", tools_service.handle_tools_call)
    protocol_handler.register_method("resources/list", resources_service.handle_resources_list)
    protocol_handler.register_method("resources/read", resources_service.handle_resources_read)
    protocol_handler.register_method("resources/templates/list", resources_service.handle_resources_templates_list)

    logger.info("MCP protocol layer initialized with tools and resources endpoints")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await initialize_services()
    logger.info("Read-only MCP server started")


@app.post("/mcp/v1/list_projects")
async def list_projects(request: Request):
    """List all Bablib projects with optional filtering."""
    try:
        # Parse request body
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "list_projects":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters
        status_filter = params.get("status_filter")
        limit = params.get("limit")
        shelf_name = params.get("shelf_name")
        include_shelf_context = params.get("include_shelf_context", False)

        # Validate limit
        if limit is not None and (limit < 1 or limit > 100):
            raise HTTPException(status_code=422, detail="Limit must be between 1 and 100")

        # Call service
        response = await read_only_service.list_projects(
            status_filter=status_filter,
            limit=limit,
            shelf_name=shelf_name,
            include_shelf_context=include_shelf_context
        )

        return JSONResponse(content=response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_projects: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/search_projects")
async def search_projects(request: Request):
    """Search projects using embeddings."""
    try:
        # Parse request body
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "search_projects":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract and validate parameters
        query = params.get("query")
        if not query:
            raise HTTPException(status_code=422, detail="Query parameter is required")

        project_names = params.get("project_names")
        shelf_names = params.get("shelf_names")
        basket_types = params.get("basket_types")
        include_shelf_context = params.get("include_shelf_context", False)
        limit = params.get("limit", 10)

        # Validate limit
        if limit < 1 or limit > 50:
            raise HTTPException(status_code=422, detail="Limit must be between 1 and 50")

        # Call service
        response = await read_only_service.search_projects(
            query=query,
            project_names=project_names,
            shelf_names=shelf_names,
            basket_types=basket_types,
            include_shelf_context=include_shelf_context,
            limit=limit
        )

        return JSONResponse(content=response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_projects: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/get_project_files")
async def get_project_files(request: Request):
    """Get project file information based on project type."""
    try:
        # Parse request body
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "get_project_files":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract and validate parameters
        project_name = params.get("project_name")
        if not project_name:
            raise HTTPException(status_code=422, detail="Project name is required")

        file_path = params.get("file_path")
        include_content = params.get("include_content", False)

        # Call service
        response = await read_only_service.get_project_files(
            project_name=project_name,
            file_path=file_path,
            include_content=include_content
        )

        return JSONResponse(content=response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_project_files: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/list_shelfs")
async def list_shelfs(request: Request):
    """List all shelves with optional basket details."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "list_shelfs":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters with defaults
        include_baskets = params.get("include_baskets", False)
        include_empty = params.get("include_empty", True)
        current_only = params.get("current_only", False)
        limit = params.get("limit", 50)

        # Validate parameters
        if not isinstance(include_baskets, bool):
            raise HTTPException(status_code=422, detail="include_baskets must be boolean")
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=422, detail="Limit must be between 1 and 1000")

        # Call service
        result = await shelf_mcp_service.list_shelfs(
            include_baskets=include_baskets,
            include_empty=include_empty,
            current_only=current_only,
            limit=limit
        )

        response = McpResponse.success_response(
            data=result.get("shelves", []),
            metadata=result.get("metadata")
        )
        return JSONResponse(content=response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_shelfs: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/get_shelf_structure")
async def get_shelf_structure(request: Request):
    """Get detailed structure of a specific shelf."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "get_shelf_structure":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters
        shelf_name = params.get("shelf_name")
        if not shelf_name:
            raise HTTPException(status_code=422, detail="shelf_name parameter is required")

        include_basket_details = params.get("include_basket_details", True)
        include_file_list = params.get("include_file_list", False)

        # Call service
        result = await shelf_mcp_service.get_shelf_structure(
            shelf_name=shelf_name,
            include_basket_details=include_basket_details,
            include_file_list=include_file_list
        )

        response = McpResponse.success_response(data=result)
        return JSONResponse(content=response.to_dict())

    except ShelfNotFoundError as e:
        error_response = McpResponse.error_response(
            error="shelf_not_found",
            message=str(e),
            data={"details": {"error_code": "shelf_not_found"}}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=404)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_shelf_structure: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/get_current_shelf")
async def get_current_shelf(request: Request):
    """Get information about the current active shelf."""
    try:
        body = await request.json()
        method = body.get("method")

        if method != "get_current_shelf":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Call service
        result = await shelf_mcp_service.get_current_shelf()

        response = McpResponse.success_response(data=result)
        return JSONResponse(content=response.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_shelf: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp")
async def mcp_protocol_endpoint(request: Request):
    """
    MCP protocol endpoint for JSON-RPC 2.0 messages.

    This endpoint implements the Model Context Protocol specification.
    All MCP-compliant clients should use this endpoint.
    """
    global http_transport

    if http_transport is None:
        error_response = McpResponse.error_response("MCP protocol not initialized")
        return JSONResponse(content=error_response.to_dict(), status_code=500)

    # Handle request using protocol transport layer
    response = await http_transport.handle_http_request(request)
    return response


@app.get("/mcp/v1/health")
async def health_check():
    """Health check endpoint using Bablib health command."""
    try:
        # Execute health check using existing Bablib health command
        import subprocess
        import json

        result = subprocess.run(
            ["uv", "run", "bablib", "health", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            try:
                health_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                health_data = {"raw_output": result.stdout}

            response = McpResponse.success_response(
                data={
                    "server_type": "read-only",
                    "status": "healthy",
                    "bablib_health": health_data
                }
            )
        else:
            response = McpResponse.success_response(
                data={
                    "server_type": "read-only",
                    "status": "degraded",
                    "bablib_health": {
                        "error": result.stderr,
                        "exit_code": result.returncode
                    }
                }
            )

        return JSONResponse(content=response.to_dict())

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        error_response = McpResponse.error_response(f"Health check failed: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors for undefined endpoints."""
    error_response = McpResponse.error_response("Endpoint not found")
    return JSONResponse(content=error_response.to_dict(), status_code=404)


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Handle validation errors."""
    error_response = McpResponse.error_response(f"Validation error: {str(exc)}")
    return JSONResponse(content=error_response.to_dict(), status_code=422)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9383)