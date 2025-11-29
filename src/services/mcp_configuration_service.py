"""MCPConfigurationService for universal MCP client configuration generation."""
import json
from pathlib import Path
from typing import Any

from src.core.lib_logger import get_logger
from src.models.mcp_configuration import (
    AuthConfig,
    ConnectionSettings,
    MCPConfiguration,
)

logger = get_logger(__name__)


class MCPConfigurationService:
    """Service for generating and managing universal MCP configurations."""

    def __init__(self):
        """Initialize MCP configuration service."""
        self.default_server_url = "http://localhost:8765"
        self.default_server_name = "bablib"

    def generate_universal_config(
        self,
        server_url: str | None = None,
        server_name: str | None = None,
        capabilities: list[str] | None = None,
        auth_method: str = "none",
        connection_timeout: int = 30
    ) -> dict[str, Any]:
        """Generate universal MCP config removing Claude Code specifics."""
        # Use defaults if not provided
        server_url = server_url or self.default_server_url
        server_name = server_name or self.default_server_name
        capabilities = capabilities or ["search", "crawl", "embed", "status"]

        # Create authentication config
        auth_config = None
        if auth_method != "none":
            auth_config = AuthConfig(
                method=auth_method,
                credentials=None  # Will be populated if needed
            )

        # Create connection settings
        connection_settings = ConnectionSettings(
            timeout_seconds=connection_timeout,
            retry_attempts=3,
            keepalive=True
        )

        # Create MCP configuration
        mcp_config = MCPConfiguration(
            server_name=server_name,
            server_url=server_url,
            api_version="1.0",
            capabilities=capabilities,
            authentication=auth_config,
            connection_settings=connection_settings
        )

        # Generate config dict
        config = mcp_config.generate_mcp_config()

        # Remove any Claude Code specific configurations
        self._remove_claude_specific_keys(config)

        return config

    def _remove_claude_specific_keys(self, config: dict[str, Any]) -> None:
        """Remove Claude Code specific keys from configuration."""
        claude_specific_keys = [
            "claude_code",
            "anthropic",
            "claude_config",
            "claude_api_key",
            "anthropic_api_key",
            "claude_client_config",
            "claude_mcp_config"
        ]

        for key in claude_specific_keys:
            if key in config:
                logger.info(f"Removing Claude Code specific key: {key}")
                del config[key]

    def save_config(self, config: dict[str, Any], config_path: Path) -> bool:
        """Save MCP configuration to file."""
        try:
            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write configuration
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info(f"MCP configuration saved to: {config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save MCP configuration: {e}")
            return False

    def load_config(self, config_path: Path) -> dict[str, Any] | None:
        """Load MCP configuration from file."""
        try:
            if not config_path.exists():
                logger.warning(f"MCP configuration file not found: {config_path}")
                return None

            with open(config_path) as f:
                config = json.load(f)

            logger.info(f"MCP configuration loaded from: {config_path}")
            return config

        except Exception as e:
            logger.error(f"Failed to load MCP configuration: {e}")
            return None

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate MCP configuration structure."""
        required_fields = ["server_name", "server_url", "api_version", "capabilities"]

        try:
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field in MCP config: {field}")
                    return False

            # Validate capabilities
            if not isinstance(config["capabilities"], list):
                logger.error("Capabilities must be a list")
                return False

            # Validate server_url format
            server_url = config["server_url"]
            if not (server_url.startswith("http://") or server_url.startswith("https://")):
                logger.error(f"Invalid server URL format: {server_url}")
                return False

            logger.info("MCP configuration validation passed")
            return True

        except Exception as e:
            logger.error(f"MCP configuration validation failed: {e}")
            return False

    def get_default_config_path(self) -> Path:
        """Get default MCP configuration file path."""
        # Use XDG-compliant path
        config_dir = Path.home() / ".config" / "bablib"
        return config_dir / "mcp_config.json"

    def create_client_specific_config(
        self,
        client_type: str,
        base_config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create client-specific MCP configuration."""
        # Start with base config or generate universal one
        if base_config is None:
            base_config = self.generate_universal_config()

        client_config = base_config.copy()

        # Add client-specific adjustments
        if client_type == "vscode":
            client_config["client_info"] = {
                "name": "vscode",
                "version": "1.0.0"
            }
        elif client_type == "cursor":
            client_config["client_info"] = {
                "name": "cursor",
                "version": "1.0.0"
            }
        elif client_type == "zed":
            client_config["client_info"] = {
                "name": "zed",
                "version": "1.0.0"
            }
        elif client_type == "generic":
            client_config["client_info"] = {
                "name": "generic_mcp_client",
                "version": "1.0.0"
            }

        return client_config

    def get_server_status_config(self) -> dict[str, Any]:
        """Get configuration for server status checking."""
        return {
            "server_url": self.default_server_url,
            "endpoints": {
                "health": "/health",
                "status": "/status",
                "capabilities": "/capabilities"
            },
            "timeout_seconds": 5,
            "retry_attempts": 2
        }
