"""Context response formatters for MCP endpoints."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.models.command_context import CommandContext
from src.models.configuration_state import ConfigurationState
from src.core.lib_logger import get_component_logger

logger = get_component_logger("mcp_context_formatter")


class ContextFormatter:
    """Formats context information for MCP responses."""

    def format_shelf_context(
        self,
        context: CommandContext,
        box_count: int = 0,
        empty_box_count: int = 0,
        boxes: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Format shelf context for API response.

        Args:
            context: CommandContext with shelf information
            box_count: Number of boxes in the shelf
            empty_box_count: Number of empty boxes
            boxes: Optional list of box details

        Returns:
            Formatted shelf context dictionary
        """
        try:
            response = {
                "name": context.entity_name,
                "exists": context.entity_exists,
                "configuration_state": self._format_configuration_state(context.configuration_state),
                "content_summary": context.content_summary,
                "box_count": box_count,
                "empty_box_count": empty_box_count,
                "last_modified": context.last_modified.isoformat() if context.last_modified else None
            }

            if boxes:
                response["boxes"] = boxes

            return response

        except Exception as e:
            logger.error(f"Error formatting shelf context: {e}")
            raise

    def format_box_context(
        self,
        context: CommandContext,
        box_type: str,
        content_count: int = 0,
        last_filled: Optional[datetime] = None,
        suggested_actions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Format box context for API response.

        Args:
            context: CommandContext with box information
            box_type: Type of box (drag/rag/bag)
            content_count: Number of content items in box
            last_filled: Last time box was filled
            suggested_actions: List of suggested actions

        Returns:
            Formatted box context dictionary
        """
        try:
            response = {
                "name": context.entity_name,
                "exists": context.entity_exists,
                "type": box_type,
                "configuration_state": self._format_configuration_state(context.configuration_state),
                "content_summary": context.content_summary,
                "content_count": content_count,
                "last_filled": last_filled.isoformat() if last_filled else None,
                "suggested_actions": suggested_actions or []
            }

            return response

        except Exception as e:
            logger.error(f"Error formatting box context: {e}")
            raise

    def format_not_found_error(
        self,
        entity_name: str,
        entity_type: str,
        suggestions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Format entity not found error response.

        Args:
            entity_name: Name of the missing entity
            entity_type: Type of entity (shelf/box)
            suggestions: Optional list of suggested actions

        Returns:
            Formatted error response
        """
        try:
            return {
                "error": "entity_not_found",
                "message": f"{entity_type.title()} '{entity_name}' not found",
                "entity_type": entity_type,
                "entity_name": entity_name,
                "suggestions": suggestions or []
            }

        except Exception as e:
            logger.error(f"Error formatting not found error: {e}")
            raise

    def format_empty_entity_error(
        self,
        entity_name: str,
        entity_type: str,
        box_type: Optional[str] = None,
        suggestions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Format empty entity error response.

        Args:
            entity_name: Name of the empty entity
            entity_type: Type of entity (shelf/box)
            box_type: Type of box if entity is a box
            suggestions: Optional list of suggested actions

        Returns:
            Formatted error response
        """
        try:
            response = {
                "error": "entity_empty",
                "message": f"{entity_type.title()} '{entity_name}' exists but contains no content",
                "entity_type": entity_type,
                "entity_name": entity_name,
                "suggestions": suggestions or []
            }

            if box_type:
                response["box_type"] = box_type

            return response

        except Exception as e:
            logger.error(f"Error formatting empty entity error: {e}")
            raise

    def format_suggested_actions(
        self,
        entity_type: str,
        entity_name: str,
        box_type: Optional[str] = None,
        is_empty: bool = True,
        is_configured: bool = False
    ) -> List[Dict[str, Any]]:
        """Generate suggested actions based on entity state.

        Args:
            entity_type: Type of entity (shelf/box)
            entity_name: Name of the entity
            box_type: Type of box if entity is a box
            is_empty: Whether entity is empty
            is_configured: Whether entity is configured

        Returns:
            List of suggested action dictionaries
        """
        try:
            actions = []

            if entity_type == "shelf":
                if is_empty:
                    actions.append({
                        "action": "create_box",
                        "description": "Create a box to store content",
                        "command": f"bablib box create <box-name> --shelf {entity_name} --type <drag|rag|bag>"
                    })

                if not is_configured:
                    actions.append({
                        "action": "configure",
                        "description": "Configure shelf settings",
                        "command": f"bablib shelf {entity_name} --init"
                    })

                actions.append({
                    "action": "view",
                    "description": "View shelf details and contents",
                    "command": f"bablib shelf {entity_name} --verbose"
                })

            elif entity_type == "box":
                if is_empty and box_type:
                    if box_type == "drag":
                        actions.append({
                            "action": "fill",
                            "description": "Crawl a website to fill this drag box",
                            "command": f"bablib fill {entity_name} --source <website_url>"
                        })
                    elif box_type == "rag":
                        actions.append({
                            "action": "fill",
                            "description": "Upload documents to fill this rag box",
                            "command": f"bablib fill {entity_name} --source <file_path>"
                        })
                    elif box_type == "bag":
                        actions.append({
                            "action": "fill",
                            "description": "Add files to fill this bag box",
                            "command": f"bablib fill {entity_name} --source <content_path>"
                        })

                if not is_configured:
                    actions.append({
                        "action": "configure",
                        "description": "Configure box settings",
                        "command": f"bablib box {entity_name} --init"
                    })

                actions.append({
                    "action": "view",
                    "description": "View box details and content",
                    "command": f"bablib box {entity_name} --verbose"
                })

            return actions

        except Exception as e:
            logger.error(f"Error formatting suggested actions: {e}")
            return []

    def format_wizard_response(
        self,
        wizard_id: str,
        wizard_type: str,
        target_entity: str,
        current_step: Dict[str, Any],
        total_steps: int,
        estimated_time: str
    ) -> Dict[str, Any]:
        """Format wizard session response.

        Args:
            wizard_id: Unique wizard session identifier
            wizard_type: Type of wizard (shelf/box/mcp)
            target_entity: Target entity name
            current_step: Current step information
            total_steps: Total number of steps
            estimated_time: Estimated completion time

        Returns:
            Formatted wizard response
        """
        try:
            return {
                "wizard_id": wizard_id,
                "session_info": {
                    "type": wizard_type,
                    "target": target_entity,
                    "total_steps": total_steps,
                    "estimated_time": estimated_time
                },
                "current_step": current_step
            }

        except Exception as e:
            logger.error(f"Error formatting wizard response: {e}")
            raise

    def format_flag_definitions(
        self,
        global_flags: List[Dict[str, Any]],
        command_specific: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Format flag definitions response.

        Args:
            global_flags: List of global flag definitions
            command_specific: Command-specific flag definitions

        Returns:
            Formatted flag definitions
        """
        try:
            return {
                "global_flags": global_flags,
                "command_specific": command_specific,
                "total_global_flags": len(global_flags),
                "total_command_flags": sum(len(flags) for flags in command_specific.values()),
                "supported_commands": list(command_specific.keys())
            }

        except Exception as e:
            logger.error(f"Error formatting flag definitions: {e}")
            raise

    def _format_configuration_state(self, config_state: ConfigurationState) -> Dict[str, Any]:
        """Format configuration state for API response.

        Args:
            config_state: ConfigurationState object

        Returns:
            Formatted configuration state dictionary
        """
        try:
            return {
                "is_configured": config_state.is_configured,
                "has_content": config_state.has_content,
                "configuration_version": config_state.configuration_version,
                "setup_completed_at": config_state.setup_completed_at.isoformat() if config_state.setup_completed_at else None,
                "needs_migration": config_state.needs_migration
            }

        except Exception as e:
            logger.error(f"Error formatting configuration state: {e}")
            return {
                "is_configured": False,
                "has_content": False,
                "configuration_version": "unknown",
                "setup_completed_at": None,
                "needs_migration": False
            }

    def format_creation_suggestions(
        self,
        entity_name: str,
        entity_type: str,
        shelf_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Format entity creation suggestions.

        Args:
            entity_name: Name of entity to create
            entity_type: Type of entity (shelf/box)
            shelf_context: Optional shelf context for box creation

        Returns:
            List of creation suggestion dictionaries
        """
        try:
            if entity_type == "shelf":
                return [
                    {
                        "action": "create",
                        "description": f"Create shelf '{entity_name}'",
                        "endpoint": "/admin/context/create-shelf",
                        "parameters": {"name": entity_name}
                    },
                    {
                        "action": "create_with_wizard",
                        "description": f"Create shelf '{entity_name}' with setup wizard",
                        "endpoint": "/admin/context/create-shelf",
                        "parameters": {"name": entity_name, "run_wizard": True}
                    },
                    {
                        "action": "list",
                        "description": "View available shelves",
                        "endpoint": "/shelves",
                        "parameters": {}
                    }
                ]

            elif entity_type == "box":
                suggestions = []
                box_types = ["drag", "rag", "bag"]
                descriptions = {
                    "drag": "for website crawling",
                    "rag": "for document upload",
                    "bag": "for file storage"
                }

                for box_type in box_types:
                    params = {"name": entity_name, "type": box_type}
                    if shelf_context:
                        params["shelf"] = shelf_context

                    suggestions.append({
                        "action": "create",
                        "description": f"Create {box_type} box '{entity_name}' {descriptions[box_type]}",
                        "endpoint": "/admin/context/create-box",
                        "parameters": params
                    })

                return suggestions

            return []

        except Exception as e:
            logger.error(f"Error formatting creation suggestions: {e}")
            return []