"""
MCP Core Types

Models for MCP tools, resources, and prompts according to the protocol spec.
https://modelcontextprotocol.io/
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class Tool(BaseModel):
    """
    MCP Tool definition.

    Tools represent callable functions/commands that can be invoked by clients.
    """

    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Human-readable tool description")
    input_schema: dict[str, Any] = Field(
        ...,
        alias="inputSchema",
        description="JSON Schema for tool parameters",
    )

    class Config:
        populate_by_name = True

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        input_schema: Optional[dict[str, Any]] = None,
    ) -> "Tool":
        """
        Create a tool with optional input schema.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON Schema for parameters (defaults to empty object)

        Returns:
            Tool instance
        """
        if input_schema is None:
            input_schema = {"type": "object", "properties": {}}
        return cls(name=name, description=description, input_schema=input_schema)


class Resource(BaseModel):
    """
    MCP Resource definition.

    Resources represent data that can be read by clients (files, documents, etc).
    """

    uri: str = Field(..., description="Unique resource URI")
    name: str = Field(..., description="Human-readable resource name")
    description: Optional[str] = Field(
        None,
        description="Optional resource description",
    )
    mime_type: Optional[str] = Field(
        None,
        alias="mimeType",
        description="MIME type of the resource content",
    )

    class Config:
        populate_by_name = True

    @classmethod
    def create(
        cls,
        uri: str,
        name: str,
        description: Optional[str] = None,
        mime_type: Optional[str] = "application/json",
    ) -> "Resource":
        """
        Create a resource with sensible defaults.

        Args:
            uri: Resource URI (e.g., "bablib://shelf/my-shelf")
            name: Display name
            description: Optional description
            mime_type: MIME type (defaults to application/json)

        Returns:
            Resource instance
        """
        return cls(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
        )


class ResourceContents(BaseModel):
    """
    MCP Resource contents returned when reading a resource.
    """

    uri: str = Field(..., description="Resource URI")
    mime_type: Optional[str] = Field(
        None,
        alias="mimeType",
        description="MIME type of the content",
    )
    text: Optional[str] = Field(
        None,
        description="Text content (for text-based resources)",
    )
    blob: Optional[str] = Field(
        None,
        description="Base64-encoded binary content",
    )

    class Config:
        populate_by_name = True


class ResourceTemplate(BaseModel):
    """
    MCP Resource template for dynamic resource URIs.

    Templates allow clients to construct URIs programmatically.
    """

    uri_template: str = Field(
        ...,
        alias="uriTemplate",
        description="URI template with placeholders (e.g., 'bablib://shelf/{name}')",
    )
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(
        None,
        description="Template description",
    )
    mime_type: Optional[str] = Field(
        None,
        alias="mimeType",
        description="MIME type of resources created from this template",
    )

    class Config:
        populate_by_name = True


class Prompt(BaseModel):
    """
    MCP Prompt template.

    Prompts are reusable message templates that clients can use.
    """

    name: str = Field(..., description="Unique prompt identifier")
    description: Optional[str] = Field(
        None,
        description="Prompt description",
    )
    arguments: Optional[list[dict[str, Any]]] = Field(
        None,
        description="List of prompt arguments",
    )

    class Config:
        populate_by_name = True


class PromptMessage(BaseModel):
    """
    Message within a prompt template.
    """

    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")


class PromptResult(BaseModel):
    """
    Result when retrieving a prompt.
    """

    description: Optional[str] = Field(None, description="Prompt description")
    messages: list[PromptMessage] = Field(..., description="Prompt messages")


# List response models
class ToolsList(BaseModel):
    """Response for tools/list method."""

    tools: list[Tool] = Field(..., description="Available tools")


class ResourcesList(BaseModel):
    """Response for resources/list method."""

    resources: list[Resource] = Field(..., description="Available resources")


class ResourceTemplatesList(BaseModel):
    """Response for resources/templates/list method."""

    resource_templates: list[ResourceTemplate] = Field(
        ...,
        alias="resourceTemplates",
        description="Available resource templates",
    )

    class Config:
        populate_by_name = True


class PromptsList(BaseModel):
    """Response for prompts/list method."""

    prompts: list[Prompt] = Field(..., description="Available prompts")
