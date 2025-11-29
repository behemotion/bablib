"""
MCP Tools Service

Implements tools/list and tools/call endpoints for MCP protocol.
Maps Bablib CLI commands to MCP tool definitions.
"""

import logging
from typing import Any

from src.logic.mcp.models.mcp_types import Tool, ToolsList
from src.logic.mcp.services.command_executor import CommandExecutor
from src.logic.mcp.models.command_execution import CommandExecutionRequest

logger = logging.getLogger(__name__)


class ToolsService:
    """
    Service for MCP tools endpoints.

    Provides Bablib commands as MCP tools that can be discovered and called.
    """

    def __init__(self, is_admin: bool = False):
        """
        Initialize tools service.

        Args:
            is_admin: Whether this is for admin server (full command access)
        """
        self.is_admin = is_admin
        self.command_executor = CommandExecutor()

    def get_tool_definitions(self) -> list[Tool]:
        """
        Get all available tool definitions.

        Returns:
            List of Tool objects representing Bablib commands
        """
        tools = []

        # Shelf management tools
        tools.extend(self._get_shelf_tools())

        # Box management tools
        tools.extend(self._get_box_tools())

        # Search and query tools (read-only)
        tools.extend(self._get_search_tools())

        # Admin-only tools
        if self.is_admin:
            tools.extend(self._get_admin_tools())

        return tools

    def _get_shelf_tools(self) -> list[Tool]:
        """Get shelf management tools."""
        return [
            Tool.create(
                name="bablib_shelf_list",
                description="List all documentation shelves",
                input_schema={
                    "type": "object",
                    "properties": {
                        "verbose": {
                            "type": "boolean",
                            "description": "Enable verbose output",
                        },
                        "current_only": {
                            "type": "boolean",
                            "description": "Show only current shelf",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                        },
                    },
                },
            ),
            Tool.create(
                name="bablib_shelf_current",
                description="Get or set the current shelf",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Shelf name to set as current (optional)",
                        },
                    },
                },
            ),
        ]

    def _get_box_tools(self) -> list[Tool]:
        """Get box management tools."""
        return [
            Tool.create(
                name="bablib_box_list",
                description="List documentation boxes",
                input_schema={
                    "type": "object",
                    "properties": {
                        "shelf": {
                            "type": "string",
                            "description": "Filter by shelf name",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["drag", "rag", "bag"],
                            "description": "Filter by box type",
                        },
                        "verbose": {
                            "type": "boolean",
                            "description": "Enable verbose output",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                        },
                    },
                },
            ),
            Tool.create(
                name="bablib_box_inspect",
                description="Inspect a documentation box",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Box name to inspect",
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    def _get_search_tools(self) -> list[Tool]:
        """Get search and query tools."""
        return [
            Tool.create(
                name="bablib_search",
                description="Search documentation content",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "shelf": {
                            "type": "string",
                            "description": "Search in specific shelf",
                        },
                        "box": {
                            "type": "string",
                            "description": "Search in specific box",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    def _get_admin_tools(self) -> list[Tool]:
        """Get admin-only tools."""
        return [
            Tool.create(
                name="bablib_shelf_create",
                description="Create a new documentation shelf",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Shelf name",
                        },
                        "description": {
                            "type": "string",
                            "description": "Shelf description",
                        },
                        "set_current": {
                            "type": "boolean",
                            "description": "Set as current shelf",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool.create(
                name="bablib_box_create",
                description="Create a new documentation box",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Box name",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["drag", "rag", "bag"],
                            "description": "Box type",
                        },
                        "shelf": {
                            "type": "string",
                            "description": "Shelf to add box to",
                        },
                        "description": {
                            "type": "string",
                            "description": "Box description",
                        },
                    },
                    "required": ["name", "type"],
                },
            ),
            Tool.create(
                name="bablib_fill",
                description="Fill a box with content (crawl, upload, or store)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "box_name": {
                            "type": "string",
                            "description": "Box name to fill",
                        },
                        "source": {
                            "type": "string",
                            "description": "Source URL or path",
                        },
                        "shelf": {
                            "type": "string",
                            "description": "Shelf name",
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "Maximum pages to crawl (drag boxes)",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Maximum crawl depth (drag boxes)",
                        },
                    },
                    "required": ["box_name", "source"],
                },
            ),
        ]

    async def handle_tools_list(self, params: dict) -> dict:
        """
        Handle tools/list request.

        Args:
            params: Request parameters (unused for tools/list)

        Returns:
            ToolsList response
        """
        tools = self.get_tool_definitions()
        tools_list = ToolsList(tools=tools)
        return tools_list.model_dump(by_alias=True)

    async def handle_tools_call(self, params: dict) -> dict:
        """
        Handle tools/call request.

        Args:
            params: Must contain 'name' (tool name) and 'arguments' (tool args)

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool name is missing or tool not found
        """
        tool_name = params.get("name")
        if not tool_name:
            raise ValueError("Tool name is required")

        arguments = params.get("arguments", {})

        # Map tool name to Bablib command
        command_parts = self._tool_to_command(tool_name, arguments)

        # Execute command
        exec_request = CommandExecutionRequest(
            command=command_parts[0],
            args=command_parts[1:],
            timeout=30.0,
        )

        result = await self.command_executor.execute(exec_request)

        # Return result in MCP format
        return {
            "content": [
                {
                    "type": "text",
                    "text": result.stdout if result.exit_code == 0 else result.stderr,
                }
            ],
            "isError": result.exit_code != 0,
        }

    def _tool_to_command(self, tool_name: str, arguments: dict) -> list[str]:
        """
        Convert MCP tool call to Bablib command.

        Args:
            tool_name: MCP tool name (e.g., 'bablib_shelf_list')
            arguments: Tool arguments

        Returns:
            Command parts as list of strings

        Raises:
            ValueError: If tool name is not recognized
        """
        # Remove 'bablib_' prefix
        if not tool_name.startswith("bablib_"):
            raise ValueError(f"Unknown tool: {tool_name}")

        command_name = tool_name[7:]  # Remove 'bablib_'

        # Map to Bablib CLI command
        parts = command_name.split("_")

        if len(parts) < 2:
            raise ValueError(f"Invalid tool name format: {tool_name}")

        # Build command: bablib <entity> <action> [args]
        cmd = ["bablib", parts[0], parts[1]]

        # Add arguments based on tool
        cmd.extend(self._format_arguments(parts[0], parts[1], arguments))

        return cmd

    def _format_arguments(
        self, entity: str, action: str, arguments: dict
    ) -> list[str]:
        """
        Format tool arguments as CLI flags.

        Args:
            entity: Entity type (shelf, box, etc.)
            action: Action name (list, create, etc.)
            arguments: Tool arguments

        Returns:
            List of CLI argument strings
        """
        args = []

        # Handle positional arguments first
        if entity == "shelf":
            if action == "current" and "name" in arguments:
                args.append(arguments["name"])
            elif action == "create" and "name" in arguments:
                args.append(arguments["name"])

        elif entity == "box":
            if action == "inspect" and "name" in arguments:
                args.append(arguments["name"])
            elif action == "create" and "name" in arguments:
                args.append(arguments["name"])

        elif entity == "fill":
            if "box_name" in arguments:
                args.append(arguments["box_name"])

        # Handle flags
        for key, value in arguments.items():
            if key in ["name", "box_name"]:
                continue  # Already handled as positional

            # Convert to CLI flag
            flag_name = key.replace("_", "-")

            if isinstance(value, bool):
                if value:
                    args.append(f"--{flag_name}")
            else:
                args.extend([f"--{flag_name}", str(value)])

        return args
