"""McpServerType enum for defining MCP server types."""

from enum import Enum


class McpServerType(str, Enum):
    """Enumeration defining the type of MCP server to start.

    Attributes:
        READ_ONLY: bablib server with read-only operations
        ADMIN: bablib-admin server with full command control
    """

    READ_ONLY = "read-only"
    ADMIN = "admin"

    def __str__(self) -> str:
        """Return string representation of the server type."""
        return self.value

    @property
    def default_port(self) -> int:
        """Get the default port for this server type."""
        return {
            self.READ_ONLY: 9383,
            self.ADMIN: 9384,
        }[self]

    @property
    def default_host(self) -> str:
        """Get the default host for this server type."""
        return {
            self.READ_ONLY: "0.0.0.0",
            self.ADMIN: "127.0.0.1",  # Admin server restricted to localhost
        }[self]