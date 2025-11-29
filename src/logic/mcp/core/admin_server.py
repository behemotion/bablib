"""Admin MCP server FastAPI application."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import logging

from src.logic.mcp.models.response import McpResponse
from src.logic.mcp.models.command_execution import CommandExecutionRequest, AllowedCommand
from src.logic.mcp.services.admin import AdminMcpService
from src.logic.mcp.services.command_executor import CommandExecutor
from src.logic.mcp.services.shelf_mcp_service import ShelfMcpService
from src.models.shelf import ShelfNotFoundError, ShelfExistsError
from src.models.box import BoxNotFoundError, BoxExistsError

# MCP Protocol imports
from src.logic.mcp.protocol.handler import ProtocolHandler
from src.logic.mcp.protocol.transport import HttpTransport
from src.logic.mcp.protocol.capabilities import ServerCapabilities
from src.logic.mcp.services.tools_service import ToolsService
from src.logic.mcp.services.resources_service import ResourcesService

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Bablib MCP Admin Server",
    version="1.0.0",
    description="MCP server providing full administrative control over Bablib operations"
)

# Services
command_executor = None
admin_service = None
shelf_mcp_service = None

# MCP Protocol components
protocol_handler = None
http_transport = None
tools_service = None
resources_service = None


async def initialize_services():
    """Initialize services for the admin server."""
    global command_executor, admin_service, shelf_mcp_service
    global protocol_handler, http_transport, tools_service, resources_service

    command_executor = CommandExecutor()
    admin_service = AdminMcpService(command_executor)

    # Initialize shelf MCP service
    shelf_mcp_service = ShelfMcpService()
    await shelf_mcp_service.initialize()
    logger.info("ShelfMcpService initialized for admin server")

    # Initialize MCP protocol components
    capabilities = ServerCapabilities.default_admin()
    protocol_handler = ProtocolHandler(
        server_name="bablib-admin",
        server_version="1.0.0",
        capabilities=capabilities,
    )
    http_transport = HttpTransport(protocol_handler)

    # Initialize MCP services (admin mode enabled)
    tools_service = ToolsService(is_admin=True)  # Admin with full command access
    resources_service = ResourcesService()

    # Register MCP protocol methods
    protocol_handler.register_method("tools/list", tools_service.handle_tools_list)
    protocol_handler.register_method("tools/call", tools_service.handle_tools_call)
    protocol_handler.register_method("resources/list", resources_service.handle_resources_list)
    protocol_handler.register_method("resources/read", resources_service.handle_resources_read)
    protocol_handler.register_method("resources/templates/list", resources_service.handle_resources_templates_list)

    logger.info("MCP protocol layer initialized for admin server with full tool access")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await initialize_services()
    logger.info("Admin MCP server started")


@app.post("/mcp/v1/execute_command")
async def execute_command(request: Request):
    """Execute Bablib CLI command."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "execute_command":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Create command execution request
        cmd_request = CommandExecutionRequest(
            command=AllowedCommand(params.get("command")),
            arguments=params.get("arguments", []),
            options=params.get("options", {}),
            timeout=params.get("timeout", 30)
        )

        response = await admin_service.execute_command(cmd_request)
        return JSONResponse(content=response.to_dict())

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        error_response = McpResponse.error_response(f"Command execution failed: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/project_create")
async def project_create(request: Request):
    """Create a new project."""
    try:
        body = await request.json()
        params = body.get("params", {})

        response = await admin_service.project_create(
            name=params.get("name"),
            project_type=params.get("type"),
            description=params.get("description"),
            settings=params.get("settings")
        )
        return JSONResponse(content=response.to_dict())

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        error_response = McpResponse.error_response(f"Project creation failed: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/create_shelf")
async def create_shelf(request: Request):
    """Create a new shelf via admin MCP."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "create_shelf":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters
        name = params.get("name")
        if not name:
            raise HTTPException(status_code=422, detail="name parameter is required")

        description = params.get("description")
        set_current = params.get("set_current", False)
        force = params.get("force", False)

        # Call service
        result = await shelf_mcp_service.create_shelf_admin(
            name=name,
            description=description,
            set_current=set_current,
            force=force
        )

        response = McpResponse.success_response(data=result)
        return JSONResponse(content=response.to_dict())

    except ShelfExistsError as e:
        error_response = McpResponse.error_response(
            error="shelf_exists",
            data={"message": str(e)}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=400)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating shelf: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/add_basket")
async def add_basket(request: Request):
    """Add a basket (box) to a shelf via admin MCP."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "add_basket":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters
        shelf_name = params.get("shelf_name")
        basket_name = params.get("basket_name")
        if not shelf_name or not basket_name:
            raise HTTPException(status_code=422, detail="shelf_name and basket_name are required")

        basket_type = params.get("basket_type", "data")
        description = params.get("description")
        force = params.get("force", False)

        # Call service
        result = await shelf_mcp_service.add_basket_admin(
            shelf_name=shelf_name,
            basket_name=basket_name,
            basket_type=basket_type,
            description=description,
            force=force
        )

        response = McpResponse.success_response(data=result)
        return JSONResponse(content=response.to_dict())

    except ShelfNotFoundError as e:
        error_response = McpResponse.error_response(
            error="shelf_not_found",
            data={"message": str(e)}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=404)
    except BoxExistsError as e:
        error_response = McpResponse.error_response(
            error="basket_exists",
            data={"message": str(e)}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=400)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding basket: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/remove_basket")
async def remove_basket(request: Request):
    """Remove a basket from a shelf via admin MCP."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "remove_basket":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters
        shelf_name = params.get("shelf_name")
        basket_name = params.get("basket_name")
        if not shelf_name or not basket_name:
            raise HTTPException(status_code=422, detail="shelf_name and basket_name are required")

        confirm = params.get("confirm", False)
        backup = params.get("backup", True)

        # Call service
        result = await shelf_mcp_service.remove_basket_admin(
            shelf_name=shelf_name,
            basket_name=basket_name,
            confirm=confirm,
            backup=backup
        )

        response = McpResponse.success_response(data=result)
        return JSONResponse(content=response.to_dict())

    except ShelfNotFoundError as e:
        error_response = McpResponse.error_response(
            error="shelf_not_found",
            data={"message": str(e)}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=404)
    except BoxNotFoundError as e:
        error_response = McpResponse.error_response(
            error="basket_not_found",
            data={"message": str(e)}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=404)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing basket: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/set_current_shelf")
async def set_current_shelf(request: Request):
    """Set current shelf via admin MCP."""
    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})

        if method != "set_current_shelf":
            raise HTTPException(status_code=400, detail="Invalid method")

        # Extract parameters
        shelf_name = params.get("shelf_name")
        if not shelf_name:
            raise HTTPException(status_code=422, detail="shelf_name parameter is required")

        # Call service
        result = await shelf_mcp_service.set_current_shelf_admin(shelf_name)

        response = McpResponse.success_response(data=result)
        return JSONResponse(content=response.to_dict())

    except ShelfNotFoundError as e:
        error_response = McpResponse.error_response(
            error="shelf_not_found",
            data={"message": str(e)}
        )
        return JSONResponse(content=error_response.to_dict(), status_code=404)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting current shelf: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp/v1/delete_shelf")
async def delete_shelf(request: Request):
    """Delete shelf endpoint - PROHIBITED via MCP for security."""
    try:
        body = await request.json()

        # Always return prohibited response
        error_response = McpResponse.error_response(
            error="operation_prohibited",
            data={
                "message": "Shelf deletion is prohibited via MCP admin for security reasons",
                "details": {
                    "allowed_methods": ["CLI only"],
                    "alternative": "bablib shelf --remove <name> --force"
                }
            }
        )
        return JSONResponse(content=error_response.to_dict(), status_code=403)

    except Exception as e:
        logger.error(f"Error in delete_shelf: {e}")
        error_response = McpResponse.error_response(f"Internal server error: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


@app.post("/mcp")
async def mcp_protocol_endpoint(request: Request):
    """
    MCP protocol endpoint for JSON-RPC 2.0 messages.

    This endpoint implements the Model Context Protocol specification.
    All MCP-compliant clients should use this endpoint for admin operations.
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
    """Health check endpoint."""
    try:
        import subprocess
        import json

        result = subprocess.run(
            ["uv", "run", "bablib", "health", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )

        health_data = {}
        if result.returncode == 0:
            try:
                health_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                health_data = {"raw_output": result.stdout}

        response = McpResponse.success_response(
            data={
                "server_type": "admin",
                "status": "healthy" if result.returncode == 0 else "degraded",
                "bablib_health": health_data,
                "security_status": {
                    "localhost_only": True,
                    "port": 9384
                }
            }
        )

        return JSONResponse(content=response.to_dict())

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        error_response = McpResponse.error_response(f"Health check failed: {str(e)}")
        return JSONResponse(content=error_response.to_dict(), status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9384)