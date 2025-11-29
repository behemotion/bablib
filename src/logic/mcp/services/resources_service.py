"""
MCP Resources Service

Implements resources/list, resources/read, and resources/templates/list endpoints
for MCP protocol. Exposes shelves and boxes as MCP resources.
"""

import json
import logging
from typing import Optional

from src.logic.mcp.models.mcp_types import (
    Resource,
    ResourceContents,
    ResourcesList,
    ResourceTemplate,
    ResourceTemplatesList,
)
from src.services.shelf_service import ShelfService
from src.services.box_service import BoxService

logger = logging.getLogger(__name__)


class ResourcesService:
    """
    Service for MCP resources endpoints.

    Exposes Bablib shelves and boxes as MCP resources that can be
    discovered and read by MCP clients.
    """

    def __init__(self):
        """Initialize resources service."""
        self.shelf_service = ShelfService()
        self.box_service = BoxService()

    async def handle_resources_list(self, params: dict) -> dict:
        """
        Handle resources/list request.

        Lists all shelves and boxes as MCP resources.

        Args:
            params: Request parameters (unused)

        Returns:
            ResourcesList response
        """
        resources = []

        # List all shelves
        await self.shelf_service.initialize()
        shelves = await self.shelf_service.list_shelves()

        for shelf in shelves:
            resources.append(
                Resource.create(
                    uri=f"bablib://shelf/{shelf.name}",
                    name=f"Shelf: {shelf.name}",
                    description=f"Documentation shelf with {shelf.box_count} boxes",
                    mime_type="application/json",
                )
            )

        # List all boxes
        await self.box_service.initialize()
        boxes = await self.box_service.list_boxes()

        for box in boxes:
            # Get box type info
            box_type = box.box_type if hasattr(box, 'box_type') else "unknown"
            resources.append(
                Resource.create(
                    uri=f"bablib://box/{box.name}",
                    name=f"Box: {box.name}",
                    description=f"Documentation box ({box_type} type)",
                    mime_type="application/json",
                )
            )

        resources_list = ResourcesList(resources=resources)
        return resources_list.model_dump(by_alias=True)

    async def handle_resources_read(self, params: dict) -> dict:
        """
        Handle resources/read request.

        Reads the content of a specific shelf or box.

        Args:
            params: Must contain 'uri' (resource URI)

        Returns:
            ResourceContents response

        Raises:
            ValueError: If URI is missing or invalid
        """
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        # Parse URI
        if not uri.startswith("bablib://"):
            raise ValueError(f"Invalid Bablib resource URI: {uri}")

        # Remove scheme
        path = uri[10:]  # Remove 'bablib://'

        # Parse resource type and name
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid resource path: {path}")

        resource_type, resource_name = parts

        # Read resource based on type
        if resource_type == "shelf":
            content = await self._read_shelf(resource_name)
        elif resource_type == "box":
            content = await self._read_box(resource_name)
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")

        # Return as ResourceContents
        return ResourceContents(
            uri=uri,
            mime_type="application/json",
            text=json.dumps(content, indent=2),
        ).model_dump(by_alias=True)

    async def handle_resources_templates_list(self, params: dict) -> dict:
        """
        Handle resources/templates/list request.

        Returns URI templates for dynamically accessing resources.

        Args:
            params: Request parameters (unused)

        Returns:
            ResourceTemplatesList response
        """
        templates = [
            ResourceTemplate(
                uri_template="bablib://shelf/{name}",
                name="Shelf by name",
                description="Access any shelf by its name",
                mime_type="application/json",
            ),
            ResourceTemplate(
                uri_template="bablib://box/{name}",
                name="Box by name",
                description="Access any box by its name",
                mime_type="application/json",
            ),
        ]

        templates_list = ResourceTemplatesList(resource_templates=templates)
        return templates_list.model_dump(by_alias=True)

    async def _read_shelf(self, shelf_name: str) -> dict:
        """
        Read shelf details and its boxes.

        Args:
            shelf_name: Name of the shelf

        Returns:
            Dict with shelf data

        Raises:
            ValueError: If shelf not found
        """
        await self.shelf_service.initialize()

        # Get shelf by name
        shelf = await self.shelf_service.get_shelf_by_name(shelf_name)
        if not shelf:
            raise ValueError(f"Shelf not found: {shelf_name}")

        # Get boxes in this shelf
        await self.box_service.initialize()
        boxes = await self.box_service.list_boxes(shelf_name=shelf_name)

        # Build response
        return {
            "type": "shelf",
            "name": shelf.name,
            "box_count": shelf.box_count,
            "is_current": shelf.is_current,
            "is_default": shelf.is_default,
            "is_deletable": shelf.is_deletable,
            "boxes": [
                {
                    "name": box.name,
                    "type": box.box_type if hasattr(box, 'box_type') else "unknown",
                }
                for box in boxes
            ],
        }

    async def _read_box(self, box_name: str) -> dict:
        """
        Read box details and metadata.

        Args:
            box_name: Name of the box

        Returns:
            Dict with box data

        Raises:
            ValueError: If box not found
        """
        await self.box_service.initialize()

        # Get box by name
        box = await self.box_service.get_box_by_name(box_name)
        if not box:
            raise ValueError(f"Box not found: {box_name}")

        # Build response
        return {
            "type": "box",
            "name": box.name,
            "box_type": box.box_type if hasattr(box, 'box_type') else "unknown",
            "created_at": box.created_at.isoformat() if hasattr(box, 'created_at') and box.created_at else None,
            "updated_at": box.updated_at.isoformat() if hasattr(box, 'updated_at') and box.updated_at else None,
        }
