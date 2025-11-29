"""MCPConfiguration model for universal MCP client configuration."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectionSettings(BaseModel):
    """Connection settings for MCP client"""
    model_config = ConfigDict(str_strip_whitespace=True)

    timeout_seconds: int = Field(default=30, description="Connection timeout")
    retry_attempts: int = Field(default=3, description="Retry attempts")
    keepalive: bool = Field(default=True, description="Keep connection alive")


class AuthConfig(BaseModel):
    """Authentication configuration"""
    model_config = ConfigDict(str_strip_whitespace=True)

    method: str = Field(..., description="Auth method: bearer_token, api_key, none")
    credentials: dict[str, str] | None = Field(None, description="Auth credentials")


class MCPConfiguration(BaseModel):
    """Universal MCP client configuration"""
    model_config = ConfigDict(str_strip_whitespace=True)

    server_name: str = Field(default="bablib", description="Server name")
    server_url: str = Field(..., description="Server URL")
    api_version: str = Field(default="1.0", description="API version")
    capabilities: list[str] = Field(default_factory=lambda: ["search", "crawl", "embed"])
    authentication: AuthConfig | None = Field(None, description="Authentication config")
    connection_settings: ConnectionSettings = Field(default_factory=ConnectionSettings)

    def generate_mcp_config(self) -> dict[str, Any]:
        """Generate universal MCP config dict"""
        config = {
            "server_name": self.server_name,
            "server_url": self.server_url,
            "api_version": self.api_version,
            "capabilities": self.capabilities
        }

        if self.authentication:
            config["authentication"] = {
                "method": self.authentication.method
            }
            if self.authentication.credentials:
                config["authentication"]["credentials"] = self.authentication.credentials

        config["connection_settings"] = {
            "timeout_seconds": self.connection_settings.timeout_seconds,
            "retry_attempts": self.connection_settings.retry_attempts,
            "keepalive": self.connection_settings.keepalive
        }

        return config
