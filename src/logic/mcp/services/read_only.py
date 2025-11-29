"""Read-only MCP service for project listing and search."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.logic.mcp.models.response import McpResponse
from src.logic.mcp.models.file_access import FileAccessRequest, ProjectType, FileAccessType
from src.logic.projects.core.project_manager import ProjectManager
from src.logic.rag.core.search_service import RAGSearchService

logger = logging.getLogger(__name__)


class ReadOnlyMcpService:
    """Service providing read-only MCP operations for project access."""

    def __init__(self, project_service: ProjectManager, search_service: RAGSearchService):
        """Initialize with required services."""
        self.project_service = project_service
        self.search_service = search_service

    async def list_projects(
        self,
        status_filter: Optional[str] = None,
        limit: Optional[int] = None,
        shelf_name: Optional[str] = None,
        include_shelf_context: bool = False
    ) -> McpResponse:
        """List all Bablib projects with optional filtering."""
        try:
            # Convert filter parameters to proper types
            status_enum = None
            if status_filter:
                # Convert string to enum if needed
                from src.logic.projects.models.config import ProjectStatus
                status_enum = ProjectStatus.from_string(status_filter) if hasattr(ProjectStatus, 'from_string') else None

            # Get all projects from project service
            projects = await self.project_service.list_projects(
                status=status_enum,
                limit=limit
            )

            # Convert to response format
            project_data = []
            for project in projects:
                # Get description from metadata or use empty string
                description = project.metadata.get('description', '') if hasattr(project, 'metadata') else ''

                project_data.append({
                    "name": project.name,
                    "type": project.type,
                    "status": project.status,
                    "description": description,
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                    "last_updated": project.updated_at.isoformat() if hasattr(project, 'updated_at') and project.updated_at else None,
                    "file_count": getattr(project, 'file_count', 0)
                })

            metadata = {
                "total_count": len(projects),
                "filtered_count": len(project_data)
            }

            return McpResponse.success_response(
                data=project_data,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return McpResponse.error_response(
                error=f"Failed to list projects: {str(e)}"
            )

    async def search_projects(
        self,
        query: str,
        project_names: Optional[List[str]] = None,
        shelf_names: Optional[List[str]] = None,
        basket_types: Optional[List[str]] = None,
        include_shelf_context: bool = False,
        limit: int = 10
    ) -> McpResponse:
        """Search projects using embeddings."""
        try:
            start_time = datetime.now()

            # Perform search using search service
            search_results = await self.search_service.search(
                query=query,
                project_names=project_names,
                limit=limit
            )

            end_time = datetime.now()
            search_time_ms = (end_time - start_time).total_seconds() * 1000

            # Convert to response format
            results_data = []
            for result in search_results:
                results_data.append({
                    "project_name": result.project_name,
                    "file_path": result.file_path,
                    "content_snippet": result.content_snippet,
                    "similarity_score": result.similarity_score,
                    "metadata": result.metadata or {}
                })

            metadata = {
                "query": query,
                "total_results": len(results_data),
                "search_time_ms": search_time_ms
            }

            return McpResponse.success_response(
                data=results_data,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error searching projects: {e}")
            return McpResponse.error_response(
                error=f"Search failed: {str(e)}"
            )

    async def get_project_files(
        self,
        project_name: str,
        file_path: Optional[str] = None,
        include_content: bool = False
    ) -> McpResponse:
        """Get project file information with access control."""
        try:
            # Validate project exists
            project = await self.project_service.get_project(project_name)
            if not project:
                return McpResponse.error_response(
                    error=f"Project '{project_name}' not found"
                )

            # Determine access type based on request
            access_type = FileAccessType.CONTENT if include_content else FileAccessType.METADATA

            # Create access request
            access_request = FileAccessRequest(
                project_name=project_name,
                file_path=file_path,
                access_type=access_type
            )

            # Check access permissions based on project type
            project_type = ProjectType(project.type)
            if not access_request.is_access_allowed(project_type):
                return McpResponse.error_response(
                    error=f"Access denied: {project.type} projects only allow metadata access"
                )

            # Get file information
            if file_path:
                # Single file request
                file_info = await self._get_single_file_info(
                    project, file_path, include_content and project_type == ProjectType.STORAGE
                )
                files_data = [file_info] if file_info else []
            else:
                # List all files in project
                files_data = await self._get_project_file_list(
                    project, include_content and project_type == ProjectType.STORAGE
                )

            metadata = {
                "project_name": project_name,
                "project_type": project.type,
                "access_level": "content" if include_content and project_type == ProjectType.STORAGE else "metadata"
            }

            return McpResponse.success_response(
                data=files_data,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error getting project files: {e}")
            return McpResponse.error_response(
                error=f"Failed to get project files: {str(e)}"
            )

    async def _get_single_file_info(
        self,
        project: Any,
        file_path: str,
        include_content: bool
    ) -> Optional[Dict[str, Any]]:
        """Get information for a single file."""
        try:
            # This would integrate with the actual file system/storage
            # For now, return a placeholder structure
            file_info = {
                "path": file_path,
                "size": 0,
                "modified_at": datetime.now().isoformat(),
                "content_type": "text/plain"
            }

            if include_content:
                # Only for storage projects
                file_info["content"] = "File content would be loaded here"

            return file_info

        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None

    async def _get_project_file_list(
        self,
        project: Any,
        include_content: bool
    ) -> List[Dict[str, Any]]:
        """Get list of all files in project."""
        try:
            # This would integrate with the actual project file system
            # For now, return a placeholder structure
            files = []

            # Placeholder file list
            sample_files = ["README.md", "doc1.txt", "doc2.md"]
            for file_name in sample_files:
                file_info = {
                    "path": file_name,
                    "size": 1024,
                    "modified_at": datetime.now().isoformat(),
                    "content_type": "text/plain"
                }

                if include_content:
                    file_info["content"] = f"Content of {file_name}"

                files.append(file_info)

            return files

        except Exception as e:
            logger.error(f"Error getting project file list: {e}")
            return []