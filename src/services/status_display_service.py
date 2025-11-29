"""Status display service for entity status logic.

Provides logic for determining and formatting entity status information
for consistent presentation across CLI commands.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

from src.models.command_context import CommandContext
from src.models.configuration_state import ConfigurationState


class EntityStatus(Enum):
    """Entity status categories."""

    NOT_FOUND = "not_found"
    UNCONFIGURED = "unconfigured"
    EMPTY = "empty"
    CONFIGURED = "configured"
    NEEDS_MIGRATION = "needs_migration"
    ERROR = "error"


class StatusDisplayService:
    """Service for determining entity status and generating display information."""

    def __init__(self):
        """Initialize status display service."""
        pass

    def determine_status(self, context: CommandContext) -> EntityStatus:
        """Determine the primary status of an entity.

        Args:
            context: CommandContext with entity information

        Returns:
            Primary EntityStatus for the entity
        """
        if not context.exists:
            return EntityStatus.NOT_FOUND

        config_state = context.configuration_state

        # Check for migration needs first
        if config_state and config_state.needs_migration:
            return EntityStatus.NEEDS_MIGRATION

        # Check if configured
        if not config_state or not config_state.is_configured:
            return EntityStatus.UNCONFIGURED

        # Check if empty (only meaningful for existing, configured entities)
        if context.is_empty:
            return EntityStatus.EMPTY

        # Fully configured and has content
        return EntityStatus.CONFIGURED

    def get_status_message(self, context: CommandContext) -> str:
        """Get human-readable status message for entity.

        Args:
            context: CommandContext with entity information

        Returns:
            Human-readable status message
        """
        status = self.determine_status(context)
        entity_type = context.entity_type.title()
        entity_name = context.entity_name

        status_messages = {
            EntityStatus.NOT_FOUND: f"{entity_type} '{entity_name}' not found",
            EntityStatus.UNCONFIGURED: f"{entity_type} '{entity_name}' exists but is not configured",
            EntityStatus.EMPTY: f"{entity_type} '{entity_name}' is configured but empty",
            EntityStatus.CONFIGURED: f"{entity_type} '{entity_name}' is configured and has content",
            EntityStatus.NEEDS_MIGRATION: f"{entity_type} '{entity_name}' needs configuration migration",
            EntityStatus.ERROR: f"{entity_type} '{entity_name}' has an error"
        }

        return status_messages.get(status, f"{entity_type} '{entity_name}' status unknown")

    def get_status_details(self, context: CommandContext) -> Dict[str, Any]:
        """Get detailed status information for entity.

        Args:
            context: CommandContext with entity information

        Returns:
            Dictionary with detailed status information
        """
        status = self.determine_status(context)
        details = {
            "entity_name": context.entity_name,
            "entity_type": context.entity_type,
            "status": status.value,
            "exists": context.exists,
            "is_empty": context.is_empty,
        }

        if context.last_modified:
            details["last_modified"] = context.last_modified.isoformat()

        if context.content_summary:
            details["content_summary"] = context.content_summary

        # Add configuration state details
        if context.configuration_state:
            config_state = context.configuration_state
            details["configuration"] = {
                "is_configured": config_state.is_configured,
                "has_content": config_state.has_content,
                "configuration_version": config_state.configuration_version,
                "needs_migration": config_state.needs_migration
            }

            if config_state.setup_completed_at:
                details["configuration"]["setup_completed_at"] = config_state.setup_completed_at.isoformat()

        return details

    def get_suggested_actions(self, context: CommandContext) -> List[Dict[str, str]]:
        """Get suggested actions based on entity status.

        Args:
            context: CommandContext with entity information

        Returns:
            List of suggested actions with descriptions and commands
        """
        status = self.determine_status(context)
        entity_type = context.entity_type
        entity_name = context.entity_name

        actions = []

        if status == EntityStatus.NOT_FOUND:
            actions.append({
                "action": "create",
                "description": f"Create {entity_type} '{entity_name}'",
                "command": f"bablib {entity_type} create {entity_name}"
            })
            actions.append({
                "action": "create_with_wizard",
                "description": f"Create {entity_type} '{entity_name}' with setup wizard",
                "command": f"bablib {entity_type} create {entity_name} --init"
            })

        elif status == EntityStatus.UNCONFIGURED:
            actions.append({
                "action": "configure",
                "description": f"Run setup wizard for '{entity_name}'",
                "command": f"bablib {entity_type} {entity_name} --init"
            })
            actions.append({
                "action": "view",
                "description": f"View current {entity_type} details",
                "command": f"bablib {entity_type} {entity_name} --verbose"
            })

        elif status == EntityStatus.EMPTY:
            if entity_type == "shelf":
                actions.append({
                    "action": "create_boxes",
                    "description": "Create boxes in this shelf",
                    "command": f"bablib box create <name> --shelf {entity_name}"
                })
            elif entity_type == "box":
                # Box-type specific suggestions would be added here
                # For now, generic fill suggestion
                actions.append({
                    "action": "fill",
                    "description": f"Fill {entity_type} with content",
                    "command": f"bablib fill {entity_name} --source <source>"
                })

            actions.append({
                "action": "reconfigure",
                "description": f"Reconfigure {entity_type} settings",
                "command": f"bablib {entity_type} {entity_name} --init"
            })

        elif status == EntityStatus.CONFIGURED:
            actions.append({
                "action": "view",
                "description": f"View {entity_type} contents",
                "command": f"bablib {entity_type} {entity_name} --verbose"
            })
            if entity_type == "box":
                actions.append({
                    "action": "add_content",
                    "description": "Add more content",
                    "command": f"bablib fill {entity_name} --source <source>"
                })

        elif status == EntityStatus.NEEDS_MIGRATION:
            actions.append({
                "action": "migrate",
                "description": f"Migrate {entity_type} configuration",
                "command": f"bablib {entity_type} {entity_name} --migrate"
            })
            actions.append({
                "action": "backup_and_recreate",
                "description": f"Backup and recreate {entity_type}",
                "command": f"bablib {entity_type} {entity_name} --backup --recreate"
            })

        return actions

    def get_box_type_specific_actions(self, context: CommandContext, box_type: str) -> List[Dict[str, str]]:
        """Get box type specific suggested actions.

        Args:
            context: CommandContext for the box
            box_type: Type of box ('drag', 'rag', 'bag')

        Returns:
            List of type-specific suggested actions
        """
        if context.entity_type != "box":
            return []

        entity_name = context.entity_name
        actions = []

        if box_type == "drag":
            actions.extend([
                {
                    "action": "crawl_website",
                    "description": "Crawl a website",
                    "command": f"bablib fill {entity_name} --source https://example.com"
                },
                {
                    "action": "crawl_with_options",
                    "description": "Crawl with specific options",
                    "command": f"bablib fill {entity_name} --source https://example.com --depth 3 --max-pages 100"
                }
            ])

        elif box_type == "rag":
            actions.extend([
                {
                    "action": "upload_documents",
                    "description": "Upload document files",
                    "command": f"bablib fill {entity_name} --source /path/to/documents"
                },
                {
                    "action": "upload_with_chunking",
                    "description": "Upload with custom chunk settings",
                    "command": f"bablib fill {entity_name} --source /path/to/docs --chunk-size 1000 --overlap 100"
                }
            ])

        elif box_type == "bag":
            actions.extend([
                {
                    "action": "store_data",
                    "description": "Store raw data",
                    "command": f"bablib fill {entity_name} --source /path/to/data"
                },
                {
                    "action": "store_recursive",
                    "description": "Store data recursively",
                    "command": f"bablib fill {entity_name} --source /path/to/data --recursive"
                }
            ])

        return actions

    def format_status_summary(self, context: CommandContext) -> str:
        """Format a brief status summary for display.

        Args:
            context: CommandContext with entity information

        Returns:
            Brief status summary string
        """
        status = self.determine_status(context)

        if status == EntityStatus.NOT_FOUND:
            return "[NOT FOUND]"
        elif status == EntityStatus.UNCONFIGURED:
            return "[UNCONFIGURED]"
        elif status == EntityStatus.EMPTY:
            return "[EMPTY]"
        elif status == EntityStatus.CONFIGURED:
            return "[CONFIGURED]"
        elif status == EntityStatus.NEEDS_MIGRATION:
            return "[NEEDS MIGRATION]"
        else:
            return "[UNKNOWN]"

    def get_content_statistics(self, context: CommandContext) -> Optional[Dict[str, Any]]:
        """Get content statistics if available.

        Args:
            context: CommandContext with entity information

        Returns:
            Dictionary with content statistics or None
        """
        if not context.exists or context.is_empty:
            return None

        # This would typically query the database for actual statistics
        # For now, return basic information from context
        stats = {}

        if context.content_summary:
            stats["summary"] = context.content_summary

        if context.last_modified:
            stats["last_modified"] = context.last_modified.isoformat()

        # Add configuration state info
        if context.configuration_state:
            config = context.configuration_state
            stats["is_configured"] = config.is_configured
            stats["has_content"] = config.has_content

            if config.setup_completed_at:
                stats["configured_at"] = config.setup_completed_at.isoformat()

        return stats if stats else None

    def should_prompt_for_action(self, context: CommandContext) -> Tuple[bool, Optional[str]]:
        """Determine if user should be prompted for action.

        Args:
            context: CommandContext with entity information

        Returns:
            Tuple of (should_prompt, prompt_message)
        """
        status = self.determine_status(context)
        entity_type = context.entity_type
        entity_name = context.entity_name

        if status == EntityStatus.NOT_FOUND:
            return True, f"{entity_type.title()} '{entity_name}' not found. Create it? (y/n)"

        elif status == EntityStatus.UNCONFIGURED:
            return True, f"{entity_type.title()} '{entity_name}' is not configured. Run setup wizard? (y/n)"

        elif status == EntityStatus.EMPTY:
            if entity_type == "shelf":
                return True, f"Shelf '{entity_name}' is empty. Create some boxes? (y/n)"
            elif entity_type == "box":
                return True, f"Box '{entity_name}' is empty. Fill it with content? (y/n)"

        elif status == EntityStatus.NEEDS_MIGRATION:
            return True, f"{entity_type.title()} '{entity_name}' needs migration. Migrate now? (y/n)"

        return False, None