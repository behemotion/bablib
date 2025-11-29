"""McpMethodDefinition model for MCP method metadata and validation."""

from typing import Dict, Any
from pydantic import BaseModel, Field, field_validator
from .server_type import McpServerType


class McpMethodDefinition(BaseModel):
    """Defines an MCP method with its metadata and validation.

    Attributes:
        name: Method name (e.g., "bablib_project_list")
        description: Human-readable description
        parameters: JSON schema for method parameters
        server_type: Which server type exposes this method
    """

    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    server_type: McpServerType

    @field_validator("name")
    @classmethod
    def validate_method_name(cls, v: str) -> str:
        """Validate method name follows MCP conventions."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Method name must contain only alphanumeric characters and underscores")

        # Check for MCP naming patterns
        valid_prefixes = ["list_", "search_", "get_", "execute_", "project_", "crawl_", "health"]
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"Method name should start with one of: {', '.join(valid_prefixes)}")

        return v

    @field_validator("parameters")
    @classmethod
    def validate_json_schema(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that parameters form a valid JSON schema."""
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a dictionary (JSON schema)")

        # Basic JSON schema validation
        if v and "type" not in v:
            # If parameters are specified, they should have a type
            v["type"] = "object"

        return v

    @classmethod
    def create_read_only_method(
        cls,
        name: str,
        description: str,
        parameters: Dict[str, Any] | None = None
    ) -> "McpMethodDefinition":
        """Create a method definition for the read-only server."""
        return cls(
            name=name,
            description=description,
            parameters=parameters or {},
            server_type=McpServerType.READ_ONLY
        )

    @classmethod
    def create_admin_method(
        cls,
        name: str,
        description: str,
        parameters: Dict[str, Any] | None = None
    ) -> "McpMethodDefinition":
        """Create a method definition for the admin server."""
        return cls(
            name=name,
            description=description,
            parameters=parameters or {},
            server_type=McpServerType.ADMIN
        )