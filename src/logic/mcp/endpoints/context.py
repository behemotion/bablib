"""Context endpoints for read-only MCP server."""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

from src.services.context_service import ContextService
from src.services.shelf_service import ShelfService
from src.services.box_service import BoxService
from src.logic.mcp.formatters.context_formatter import ContextFormatter
from src.core.lib_logger import get_component_logger

logger = get_component_logger("mcp_context_endpoints")

router = APIRouter(prefix="/context", tags=["context"])


@router.get("/shelf/{name}")
async def get_shelf_context(
    name: str,
    include_boxes: bool = Query(False, description="Include box details in response")
) -> Dict[str, Any]:
    """Get shelf context information for AI assistants.

    Provides comprehensive shelf information including existence status,
    configuration state, content summary, and optionally box details.
    """
    try:
        context_service = ContextService()
        shelf_service = ShelfService()
        formatter = ContextFormatter()

        # Check shelf context
        context = await context_service.check_shelf_exists(name)

        if not context.entity_exists:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "entity_not_found",
                    "message": f"Shelf '{name}' not found",
                    "suggestions": [
                        {
                            "action": "create",
                            "description": f"Create shelf '{name}'",
                            "endpoint": "/admin/context/create-shelf",
                            "parameters": {"name": name}
                        },
                        {
                            "action": "list",
                            "description": "View available shelves",
                            "endpoint": "/shelves",
                            "parameters": {}
                        }
                    ]
                }
            )

        # Build response
        response = {
            "name": name,
            "exists": context.entity_exists,
            "configuration_state": {
                "is_configured": context.configuration_state.is_configured,
                "has_content": context.configuration_state.has_content,
                "setup_completed_at": context.configuration_state.setup_completed_at.isoformat() if context.configuration_state.setup_completed_at else None,
                "needs_migration": context.configuration_state.needs_migration
            },
            "content_summary": context.content_summary,
            "last_modified": context.last_modified.isoformat(),
        }

        # Get box count information
        try:
            shelf = await shelf_service.get_shelf_by_name(name)
            box_service = BoxService()
            boxes = await box_service.list_boxes(shelf_name=name)

            response.update({
                "box_count": len(boxes),
                "empty_box_count": len([box for box in boxes if not box.content_count])
            })

            # Include box details if requested
            if include_boxes:
                response["boxes"] = [
                    {
                        "name": box.name,
                        "type": box.box_type,
                        "is_empty": not bool(box.content_count),
                        "content_count": box.content_count or 0
                    }
                    for box in boxes
                ]
        except Exception as e:
            logger.warning(f"Could not load box information for shelf '{name}': {e}")
            response.update({
                "box_count": 0,
                "empty_box_count": 0
            })

        return response

    except Exception as e:
        logger.error(f"Error getting shelf context for '{name}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/box/{name}")
async def get_box_context(
    name: str,
    shelf: Optional[str] = Query(None, description="Shelf context for disambiguation")
) -> Dict[str, Any]:
    """Get box context information for AI assistants.

    Provides comprehensive box information including existence status,
    type, configuration state, content summary, and suggested actions.
    """
    try:
        context_service = ContextService()
        box_service = BoxService()
        formatter = ContextFormatter()

        # Check box context
        context = await context_service.check_box_exists(name, shelf_context=shelf)

        if not context.entity_exists:
            # Suggest creation with type selection
            suggestions = [
                {
                    "action": "create",
                    "description": f"Create drag box '{name}' for website crawling",
                    "endpoint": "/admin/context/create-box",
                    "parameters": {"name": name, "type": "drag"}
                },
                {
                    "action": "create",
                    "description": f"Create rag box '{name}' for document upload",
                    "endpoint": "/admin/context/create-box",
                    "parameters": {"name": name, "type": "rag"}
                },
                {
                    "action": "create",
                    "description": f"Create bag box '{name}' for file storage",
                    "endpoint": "/admin/context/create-box",
                    "parameters": {"name": name, "type": "bag"}
                }
            ]

            if shelf:
                for suggestion in suggestions:
                    suggestion["parameters"]["shelf"] = shelf

            raise HTTPException(
                status_code=404,
                detail={
                    "error": "entity_not_found",
                    "message": f"Box '{name}' not found",
                    "suggestions": suggestions
                }
            )

        # Get box details
        box = await box_service.get_box_by_name(name, shelf_name=shelf)

        # Build suggested actions based on box state
        suggested_actions = []

        if context.is_empty:
            if box.box_type == "drag":
                suggested_actions.append({
                    "action": "fill",
                    "description": "Crawl a website to fill this drag box",
                    "command": f"bablib fill {name} --source <website_url>"
                })
            elif box.box_type == "rag":
                suggested_actions.append({
                    "action": "fill",
                    "description": "Upload documents to fill this rag box",
                    "command": f"bablib fill {name} --source <file_path>"
                })
            elif box.box_type == "bag":
                suggested_actions.append({
                    "action": "fill",
                    "description": "Add files to fill this bag box",
                    "command": f"bablib fill {name} --source <content_path>"
                })

        if not context.configuration_state.is_configured:
            suggested_actions.append({
                "action": "configure",
                "description": "Run box setup wizard",
                "command": f"bablib box {name} --init"
            })

        suggested_actions.append({
            "action": "view",
            "description": "View box details and content",
            "command": f"bablib box {name} --verbose"
        })

        response = {
            "name": name,
            "exists": context.entity_exists,
            "type": box.box_type,
            "configuration_state": {
                "is_configured": context.configuration_state.is_configured,
                "has_content": context.configuration_state.has_content,
                "setup_completed_at": context.configuration_state.setup_completed_at.isoformat() if context.configuration_state.setup_completed_at else None
            },
            "content_summary": context.content_summary,
            "content_count": box.content_count or 0,
            "last_filled": box.updated_at.isoformat() if box.updated_at else None,
            "suggested_actions": suggested_actions
        }

        return response

    except Exception as e:
        logger.error(f"Error getting box context for '{name}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/wizards/available")
async def get_available_wizards() -> Dict[str, Any]:
    """List available setup wizards and their status.

    Provides information about all available wizard types including
    their description, step count, and estimated completion time.
    """
    try:
        # Define available wizards with their metadata
        wizards = [
            {
                "type": "shelf",
                "name": "Shelf Setup Wizard",
                "description": "Configure shelf with description, auto-fill settings, default box type, and tags",
                "steps": 5,
                "estimated_time": "2-3 minutes",
                "is_active": False  # Would check WizardState for active sessions
            },
            {
                "type": "box",
                "name": "Box Setup Wizard",
                "description": "Configure box with type-specific settings, file patterns, and initial content source",
                "steps": 6,
                "estimated_time": "3-4 minutes",
                "is_active": False
            },
            {
                "type": "mcp",
                "name": "MCP Server Setup Wizard",
                "description": "Configure MCP servers with ports, authentication, and auto-start settings",
                "steps": 6,
                "estimated_time": "2-3 minutes",
                "is_active": False
            }
        ]

        return {"wizards": wizards}

    except Exception as e:
        logger.error(f"Error getting available wizards: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/flags/definitions")
async def get_flag_definitions() -> Dict[str, Any]:
    """Get standardized flag definitions for command consistency.

    Provides comprehensive flag information including global flags
    and command-specific flags with their types, descriptions, and defaults.
    """
    try:
        from src.services.flag_standardizer import FlagStandardizer

        standardizer = FlagStandardizer()

        # Get global flags
        global_flags = standardizer.get_global_flags()
        global_flag_list = [
            {
                "long_form": mapping.long_form,
                "short_form": mapping.short_form,
                "type": mapping.flag_type,
                "description": mapping.description,
                "default_value": mapping.default_value,
                "choices": mapping.choices
            }
            for mapping in global_flags.values()
        ]

        # Get command-specific flags
        command_specific = {}
        commands = ["shelf", "box", "fill", "serve", "setup"]

        for command in commands:
            command_flags = standardizer.get_command_flags(command)
            command_specific[command] = [
                {
                    "long_form": mapping.long_form,
                    "short_form": mapping.short_form,
                    "type": mapping.flag_type,
                    "description": mapping.description,
                    "default_value": mapping.default_value,
                    "choices": mapping.choices
                }
                for mapping in command_flags.values()
            ]

        return {
            "global_flags": global_flag_list,
            "command_specific": command_specific
        }

    except Exception as e:
        logger.error(f"Error getting flag definitions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")