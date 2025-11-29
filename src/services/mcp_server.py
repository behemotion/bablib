"""MCP (Model Context Protocol) server for Bablib."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger
from src.models import ProjectStatus
from src.services.database import DatabaseManager
from src.services.decision_handler import (
    DecisionHandler,
    DecisionHandlerError,
    DecisionNotFoundError,
    InvalidDecisionError,
)
from src.services.embeddings import EmbeddingService
from src.services.installation_start import InstallationStartService
from src.services.installation_status import InstallationStatusService
from src.logic.rag.core.search_service import RAGSearchService
from src.services.service_endpoints import create_service_endpoints_router
from src.services.vector_store_factory import VectorStoreFactory

# Security
security = HTTPBearer()


class MCPServer:
    """MCP server for Bablib integration with coding agents."""

    def __init__(self, config: BablibConfig | None = None):
        """Initialize MCP server."""
        self.config = config or BablibConfig()
        self.logger = get_component_logger("mcp_server")

        # Services
        self.db_manager: DatabaseManager | None = None
        self.vector_store = None  # Will be created by factory
        self.embedding_service: EmbeddingService | None = None
        self.rag_service: RAGSearchService | None = None
        self.installation_service = InstallationStartService()
        self.installation_status_service = InstallationStatusService()

        # Session management
        self.sessions: dict[str, dict[str, Any]] = {}
        self.websocket_connections: dict[str, WebSocket] = {}

        # Create FastAPI app
        self.app = self._create_app()

    async def initialize_services(self) -> None:
        """Initialize all backend services."""
        try:
            self.db_manager = DatabaseManager(self.config)
            await self.db_manager.initialize()

            # Use factory to create appropriate vector store based on settings
            self.vector_store = VectorStoreFactory.create_vector_store(self.config)
            await self.vector_store.initialize()

            self.embedding_service = EmbeddingService(self.config)
            await self.embedding_service.initialize()

            self.rag_service = RAGSearchService(
                self.vector_store,
                self.embedding_service,
                self.config
            )

            self.logger.info("MCP services initialized")

        except Exception as e:
            self.logger.error("Failed to initialize MCP services", extra={
                "error": str(e)
            })
            raise

    async def cleanup_services(self) -> None:
        """Clean up all backend services."""
        if self.embedding_service:
            await self.embedding_service.cleanup()
        if self.vector_store:
            await self.vector_store.cleanup()
        if self.db_manager:
            await self.db_manager.cleanup()

        self.logger.info("MCP services cleaned up")

    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""
        app = FastAPI(
            title="Bablib MCP Server",
            description="Model Context Protocol server for Bablib",
            version="1.0.0"
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

        # Add startup and shutdown events
        @app.on_event("startup")
        async def startup_event():
            await self.initialize_services()

        @app.on_event("shutdown")
        async def shutdown_event():
            await self.cleanup_services()

        # Add routes
        self._add_routes(app)

        return app

    def _add_routes(self, app: FastAPI) -> None:
        """Add API routes to the FastAPI app."""

        # Include service endpoints router
        service_router = create_service_endpoints_router()
        app.include_router(service_router, tags=["Service Configuration"])

        # Authentication helper
        async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
            """Verify authentication token."""
            # Simple token validation - in production, use proper JWT
            if credentials.credentials == "valid-test-token":
                return "authenticated"
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        # Health check
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "services": {
                    "database": self.db_manager is not None,
                    "vector_store": self.vector_store is not None,
                    "embeddings": self.embedding_service is not None
                }
            }

        # MCP Connect endpoint
        @app.post("/mcp/connect", dependencies=[Depends(verify_token)])
        async def mcp_connect(session_data: dict[str, Any]):
            """Establish MCP connection."""
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "data": session_data,
                "active": True
            }

            self.logger.info("MCP session created", extra={
                "session_id": session_id
            })

            return {
                "session_id": session_id,
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        # MCP Projects endpoint
        @app.get("/mcp/projects", dependencies=[Depends(verify_token)])
        async def mcp_projects(
            status: str | None = None,
            limit: int = 100
        ):
            """List available projects."""
            try:
                # Parse status filter
                status_filter = None
                if status:
                    try:
                        status_filter = ProjectStatus(status)
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid status: {status}"
                        )

                # Get projects
                projects = await self.db_manager.list_projects(
                    status=status_filter,
                    limit=limit
                )

                # Format response
                return {
                    "projects": [
                        {
                            "name": p.name,
                            "source_url": p.source_url,
                            "status": p.status,
                            "last_updated": p.updated_at.isoformat(),
                            "page_count": p.total_pages,
                            "total_size": p.total_size_bytes,
                            "created_at": p.created_at.isoformat(),
                            "outdated": p.is_outdated()
                        }
                        for p in projects
                    ]
                }

            except Exception as e:
                self.logger.error("Failed to list projects", extra={
                    "error": str(e)
                })
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to list projects"
                )

        # MCP Search endpoint
        @app.post("/mcp/search", dependencies=[Depends(verify_token)])
        async def mcp_search(search_request: dict[str, Any]):
            """Search documentation."""
            try:
                # Extract parameters
                query = search_request.get("query")
                if not query:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Query parameter is required"
                    )

                projects = search_request.get("projects", [])
                limit = min(search_request.get("limit", 10), 100)
                strategy = search_request.get("strategy", "semantic")

                # Perform search
                if projects:
                    # Search specific projects
                    results = await self.rag_service.search_multi_project(
                        query=query,
                        project_names=projects,
                        limit=limit,
                        strategy=strategy
                    )
                else:
                    # Search all projects
                    all_projects = await self.db_manager.list_projects()
                    project_names = [p.name for p in all_projects]
                    results = await self.rag_service.search_multi_project(
                        query=query,
                        project_names=project_names,
                        limit=limit,
                        strategy=strategy
                    )

                # Format response
                return {
                    "query": query,
                    "results": [
                        {
                            "id": r.get("id"),
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "content": r.get("content", "")[:500],  # Limit content length
                            "score": r.get("score"),
                            "project": r.get("project")
                        }
                        for r in results
                    ],
                    "total": len(results)
                }

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Search failed", extra={
                    "query": query,
                    "error": str(e)
                })
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Search failed"
                )

        # MCP Project refresh endpoint
        @app.post("/mcp/projects/refresh", dependencies=[Depends(verify_token)])
        async def mcp_project_refresh(refresh_request: dict[str, Any]):
            """Refresh a project."""
            project_name = refresh_request.get("project_name")
            if not project_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project name is required"
                )

            # Get project
            project = await self.db_manager.get_project_by_name(project_name)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project '{project_name}' not found"
                )

            # TODO: Trigger crawl refresh
            return {
                "project_name": project_name,
                "status": "refresh_started",
                "message": "Project refresh not fully implemented yet"
            }

        # Installation start endpoint
        @app.post("/installation/start")
        async def installation_start(request_data: dict[str, Any]):
            """Start Bablib installation process."""
            try:
                response = await self.installation_service.start_installation(request_data)
                return response
            except HTTPException:
                # Re-raise HTTPExceptions as-is
                raise
            except Exception as e:
                self.logger.error("Installation start failed", extra={
                    "error": str(e)
                })
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )

        # Installation status endpoint
        @app.get("/installation/{installation_id}/status")
        async def get_installation_status(installation_id: str):
            """Get installation status by ID."""
            try:
                # Get installation status (service validates UUID internally)
                installation_status = await self.installation_status_service.get_installation_status(installation_id)

                if not installation_status:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Installation '{installation_id}' not found"
                    )

                # Convert to dict for JSON response
                return installation_status.model_dump()

            except ValueError as e:
                # UUID validation error from service
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error("Failed to get installation status", extra={
                    "installation_id": installation_id,
                    "error": str(e)
                })
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to get installation status"
                )

        # Installation Decision endpoints
        decision_handler = DecisionHandler()

        @app.get("/installation/{installation_id}/decisions")
        async def get_installation_decisions(installation_id: str):
            """Get critical decisions for an installation.

            Args:
                installation_id: UUID of the installation process

            Returns:
                Array of CriticalDecisionPoint objects
            """
            try:
                # Validate UUID format
                try:
                    uuid.UUID(installation_id)
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid installation ID format: {installation_id}"
                    )

                decisions = await decision_handler.get_installation_decisions(installation_id)
                return decisions

            except DecisionHandlerError as e:
                error_msg = str(e)
                if "not found" in error_msg.lower():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=error_msg
                    )
                elif "invalid installation id" in error_msg.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
            except Exception as e:
                # Check if this is actually an HTTPException being re-raised from the UUID validation
                if "400" in str(e) and "Invalid installation ID" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid installation ID format"
                    )
                self.logger.error(f"Failed to get installation decisions: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )

        @app.put("/installation/{installation_id}/decisions")
        async def put_installation_decisions(installation_id: str, decision_data: dict[str, Any]):
            """Submit user choice for a critical decision.

            Args:
                installation_id: UUID of the installation process
                decision_data: Dictionary containing decision_id and user_choice

            Returns:
                Success confirmation
            """
            try:
                # Validate UUID format
                try:
                    uuid.UUID(installation_id)
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid installation ID format: {installation_id}"
                    )

                success = await decision_handler.submit_installation_decision(
                    installation_id, decision_data
                )

                if success:
                    return {
                        "status": "success",
                        "message": "Decision submitted successfully",
                        "installation_id": installation_id,
                        "decision_id": decision_data.get("decision_id")
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to submit decision"
                    )

            except DecisionNotFoundError as e:
                # If no decisions file exists for installation, return 400 instead of 404
                if "No decisions found for installation" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No pending decisions for this installation. Decisions must be created by the system before they can be submitted."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=str(e)
                    )
            except InvalidDecisionError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(e)
                )
            except DecisionHandlerError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            except Exception as e:
                self.logger.error(f"Failed to submit installation decision: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal server error"
                )

        # WebSocket endpoint for real-time updates
        @app.websocket("/mcp/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            """WebSocket connection for real-time updates."""
            await websocket.accept()
            self.websocket_connections[session_id] = websocket

            try:
                # Send initial connection message
                await websocket.send_json({
                    "type": "connection",
                    "status": "connected",
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # Handle incoming messages
                while True:
                    data = await websocket.receive_text()
                    message = json.loads(data)

                    # Process message based on type
                    if message.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    elif message.get("type") == "search":
                        # Perform search and send results
                        query = message.get("query")
                        if query:
                            # Simplified search for WebSocket
                            await websocket.send_json({
                                "type": "search_results",
                                "query": query,
                                "results": [],
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })

            except WebSocketDisconnect:
                del self.websocket_connections[session_id]
                self.logger.info("WebSocket disconnected", extra={
                    "session_id": session_id
                })
            except Exception as e:
                self.logger.error("WebSocket error", extra={
                    "session_id": session_id,
                    "error": str(e)
                })
                del self.websocket_connections[session_id]

    def get_app(self) -> FastAPI:
        """Get FastAPI application instance."""
        return self.app

    async def send_update(self, session_id: str, message: dict[str, Any]) -> None:
        """Send update to a connected WebSocket client."""
        if session_id in self.websocket_connections:
            ws = self.websocket_connections[session_id]
            try:
                await ws.send_json(message)
            except Exception as e:
                self.logger.error("Failed to send WebSocket update", extra={
                    "session_id": session_id,
                    "error": str(e)
                })


def create_app(config: BablibConfig | None = None) -> FastAPI:
    """Create MCP server FastAPI application."""
    server = MCPServer(config)
    return server.get_app()


def run_mcp_server(
    host: str = "0.0.0.0",
    port: int = 9382,
    config: BablibConfig | None = None
) -> None:
    """Run MCP server."""
    app = create_app(config)

    # Run with uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    run_mcp_server()
