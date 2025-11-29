"""Projects API router with unified schema support."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from ..models.compatibility_status import CompatibilityStatus
from ..models.unified_project import UnifiedProject, UnifiedProjectStatus
from ..logic.projects.models.project import ProjectType
from ..services.unified_project_service import (
    UnifiedProjectService,
    ProjectNotFoundError,
    IncompatibleProjectError,
    ProjectAlreadyExistsError
)
from ..services.compatibility_checker import CompatibilityChecker
from ..services.project_export_service import ProjectExportService


logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectCreateRequest(BaseModel):
    """Request model for creating a project."""
    name: str = Field(..., min_length=1, max_length=100, description="Project name")
    type: ProjectType = Field(..., description="Project type")
    source_url: Optional[str] = Field(None, description="Source URL for crawling projects")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Project settings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Project metadata")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate project name."""
        if not v.strip():
            raise ValueError("Project name cannot be empty")
        return v.strip()


class ProjectUpdateRequest(BaseModel):
    """Request model for updating a project."""
    settings: Optional[Dict[str, Any]] = Field(None, description="Updated project settings")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated project metadata")
    source_url: Optional[str] = Field(None, description="Updated source URL")


class ProjectListResponse(BaseModel):
    """Response model for project listing."""
    projects: List[Dict[str, Any]] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")
    compatible_count: int = Field(..., description="Number of compatible projects")
    incompatible_count: int = Field(..., description="Number of incompatible projects")


class ProjectRecreateRequest(BaseModel):
    """Request model for project recreation."""
    confirm: bool = Field(False, description="Confirmation flag")
    preserve_settings: bool = Field(True, description="Whether to preserve settings")
    export_first: bool = Field(True, description="Whether to export before recreation")


def get_unified_project_service() -> UnifiedProjectService:
    """Get unified project service instance."""
    return UnifiedProjectService()


def get_compatibility_checker() -> CompatibilityChecker:
    """Get compatibility checker instance."""
    return CompatibilityChecker()


def get_project_export_service() -> ProjectExportService:
    """Get project export service instance."""
    return ProjectExportService()


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    compatibility: Optional[str] = Query(None, description="Filter by compatibility status"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    type: Optional[str] = Query(None, description="Filter by project type"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
    service: UnifiedProjectService = Depends(get_unified_project_service)
):
    """
    List projects with compatibility filtering.

    Supports filtering by:
    - compatibility: compatible, incompatible, migrating
    - status: active, inactive, error, processing
    - type: crawling, data, storage
    - limit: maximum number of results
    """
    try:
        # Build filters
        filters = {}
        if compatibility:
            try:
                filters['compatibility_status'] = CompatibilityStatus(compatibility)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid compatibility status: {compatibility}"
                )

        if status:
            try:
                filters['status'] = UnifiedProjectStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid project status: {status}"
                )

        if type:
            try:
                filters['type'] = ProjectType(type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid project type: {type}"
                )

        # Get projects
        projects = await service.list_projects(**filters)

        # Apply limit if specified
        if limit is not None and limit > 0:
            projects = projects[:limit]

        # Convert to response format
        project_dicts = []
        compatible_count = 0
        incompatible_count = 0

        for project in projects:
            project_dict = project.to_dict()

            # Add computed fields for API response
            if 'statistics' in project_dict and 'total_pages' in project_dict['statistics']:
                project_dict['page_count'] = project_dict['statistics']['total_pages']
            else:
                project_dict['page_count'] = None

            project_dicts.append(project_dict)

            # Count compatibility
            if project.compatibility_status == CompatibilityStatus.COMPATIBLE:
                compatible_count += 1
            else:
                incompatible_count += 1

        return ProjectListResponse(
            projects=project_dicts,
            total=len(project_dicts),
            compatible_count=compatible_count,
            incompatible_count=incompatible_count
        )

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while listing projects"
        )


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreateRequest,
    service: UnifiedProjectService = Depends(get_unified_project_service)
):
    """Create a new project with unified schema."""
    try:
        # Create project
        project = await service.create_project(
            name=request.name,
            project_type=request.type,
            source_url=request.source_url,
            settings=request.settings,
            metadata=request.metadata
        )

        return project.to_dict()

    except ProjectAlreadyExistsError:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{request.name}' already exists"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating project"
        )


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    service: UnifiedProjectService = Depends(get_unified_project_service)
):
    """Get project details with compatibility status."""
    try:
        project = await service.get_project(project_id)
        return project.to_dict()

    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project with ID '{project_id}' not found"
        )
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting project"
        )


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    service: UnifiedProjectService = Depends(get_unified_project_service)
):
    """Update project with compatibility blocking."""
    try:
        # Get current project to check compatibility
        project = await service.get_project(project_id)

        # Block updates for incompatible projects
        if project.compatibility_status == CompatibilityStatus.INCOMPATIBLE:
            raise HTTPException(
                status_code=409,
                detail="Cannot update incompatible project. Use recreation endpoint instead."
            )

        # Prepare update data
        update_data = {}
        if request.settings is not None:
            update_data['settings'] = request.settings
        if request.metadata is not None:
            update_data['metadata'] = request.metadata
        if request.source_url is not None:
            update_data['source_url'] = request.source_url

        # Update project
        updated_project = await service.update_project(project_id, **update_data)
        return updated_project.to_dict()

    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project with ID '{project_id}' not found"
        )
    except IncompatibleProjectError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating project"
        )


@router.get("/projects/{project_id}/compatibility")
async def check_project_compatibility(
    project_id: str,
    service: UnifiedProjectService = Depends(get_unified_project_service),
    checker: CompatibilityChecker = Depends(get_compatibility_checker)
):
    """Check project compatibility status."""
    try:
        project = await service.get_project(project_id)
        result = await checker.check_project_compatibility(project)

        return {
            "project_id": project_id,
            "project_name": project.name,
            "is_compatible": result.is_compatible,
            "status": result.status.value,
            "current_version": result.current_version,
            "project_version": result.project_version,
            "issues": result.issues,
            "missing_fields": result.missing_fields,
            "extra_fields": result.extra_fields,
            "can_be_migrated": result.can_be_migrated,
            "migration_required": result.migration_required,
            "needs_recreation": result.needs_recreation,
            "summary": result.to_summary()
        }

    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project with ID '{project_id}' not found"
        )
    except Exception as e:
        logger.error(f"Error checking compatibility for project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while checking compatibility"
        )


@router.post("/projects/{project_id}/recreate")
async def recreate_project(
    project_id: str,
    request: ProjectRecreateRequest,
    service: UnifiedProjectService = Depends(get_unified_project_service),
    export_service: ProjectExportService = Depends(get_project_export_service)
):
    """Recreate incompatible project with settings preservation."""
    try:
        # Require confirmation
        if not request.confirm:
            raise HTTPException(
                status_code=400,
                detail="Recreation requires confirmation. Set 'confirm' to true."
            )

        # Get current project
        project = await service.get_project(project_id)

        # Export first if requested
        export_data = None
        if request.export_first:
            export_data = await export_service.export_project(project)

        # Recreate project
        recreated_project = await service.recreate_project(
            project_id,
            preserve_settings=request.preserve_settings
        )

        response_data = {
            "recreated_project": recreated_project.to_dict(),
            "original_schema_version": project.schema_version,
            "new_schema_version": recreated_project.schema_version,
            "settings_preserved": request.preserve_settings
        }

        if export_data:
            response_data["export_backup"] = {
                "exported_at": export_data.exported_at.isoformat(),
                "export_type": export_data.export_type,
                "schema_version": export_data.schema_version
            }

        return response_data

    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project with ID '{project_id}' not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error recreating project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while recreating project"
        )


@router.get("/projects/{project_id}/export")
async def export_project(
    project_id: str,
    export_type: str = Query("full", description="Export type: full or settings-only"),
    include_statistics: bool = Query(True, description="Include statistics in export"),
    service: UnifiedProjectService = Depends(get_unified_project_service),
    export_service: ProjectExportService = Depends(get_project_export_service)
):
    """Export project for backup and recreation support."""
    try:
        # Validate export type
        if export_type not in ["full", "settings-only"]:
            raise HTTPException(
                status_code=400,
                detail="Export type must be 'full' or 'settings-only'"
            )

        project = await service.get_project(project_id)

        # Create export
        export_data = await export_service.export_project(
            project=project,
            export_type=export_type,
            include_statistics=include_statistics
        )

        # Return export data as JSON
        return {
            "export": export_data.model_dump(mode='json'),
            "suggested_filename": export_data.get_filename(),
            "export_info": {
                "project_id": project_id,
                "project_name": project.name,
                "export_type": export_type,
                "exported_at": export_data.exported_at.isoformat(),
                "schema_version": export_data.schema_version,
                "bablib_version": export_data.bablib_version
            }
        }

    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project with ID '{project_id}' not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error exporting project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while exporting project"
        )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    service: UnifiedProjectService = Depends(get_unified_project_service)
):
    """Delete a project."""
    try:
        await service.delete_project(project_id)
        return {"message": f"Project '{project_id}' deleted successfully"}

    except ProjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Project with ID '{project_id}' not found"
        )
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while deleting project"
        )