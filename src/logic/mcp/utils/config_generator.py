"""Configuration file generator for MCP clients."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from src.logic.mcp.models.config import McpServerConfig
from src.logic.mcp.models.server_type import McpServerType

logger = logging.getLogger(__name__)


class McpConfigGenerator:
    """Generates MCP client configuration files."""

    def __init__(self, output_dir: Path):
        """Initialize config generator.

        Args:
            output_dir: Directory to write configuration files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_configs(self, configs: List[McpServerConfig]) -> Dict[str, Path]:
        """Generate configuration files for all enabled servers.

        Args:
            configs: List of server configurations

        Returns:
            Dict mapping server type to generated config file path
        """
        generated_files = {}

        for config in configs:
            if config.enabled:
                file_path = self.generate_config(config)
                generated_files[config.server_type.value] = file_path
                logger.info(f"Generated MCP config for {config.server_type.value}: {file_path}")

        return generated_files

    def generate_config(self, config: McpServerConfig) -> Path:
        """Generate configuration file for a single server.

        Args:
            config: Server configuration

        Returns:
            Path to generated configuration file
        """
        # Generate config data based on server type
        if config.server_type == McpServerType.READ_ONLY:
            config_data = self._generate_read_only_config(config)
            filename = "bablib.json"
        elif config.server_type == McpServerType.ADMIN:
            config_data = self._generate_admin_config(config)
            filename = "bablib-admin.json"
        else:
            raise ValueError(f"Unknown server type: {config.server_type}")

        # Write config file
        file_path = self.output_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)

        return file_path

    def _generate_read_only_config(self, config: McpServerConfig) -> Dict[str, Any]:
        """Generate configuration for read-only MCP server.

        Args:
            config: Server configuration

        Returns:
            Configuration data dictionary
        """
        return {
            "mcpServers": {
                "bablib": {
                    "command": "node",
                    "args": [],
                    "env": {
                        "BABLIB_MCP_URL": config.url
                    }
                }
            },
            "server": {
                "name": "Bablib Read-Only MCP Server",
                "version": "1.0.0",
                "description": "Read-only access to Bablib documentation projects",
                "url": config.url,
                "type": "read-only",
                "endpoints": {
                    "list_projects": f"{config.url}/mcp/v1/list_projects",
                    "search_projects": f"{config.url}/mcp/v1/search_projects",
                    "get_project_files": f"{config.url}/mcp/v1/get_project_files",
                    "health": f"{config.url}/mcp/v1/health"
                },
                "capabilities": [
                    "project_listing",
                    "project_search",
                    "file_metadata_access",
                    "semantic_search"
                ],
                "security": {
                    "write_access": False,
                    "command_execution": False,
                    "file_content_access": "project_type_restricted"
                }
            },
            "usage": {
                "examples": [
                    {
                        "description": "List all projects",
                        "method": "list_projects",
                        "params": {}
                    },
                    {
                        "description": "Search for documentation",
                        "method": "search_projects",
                        "params": {
                            "query": "API authentication",
                            "limit": 10
                        }
                    },
                    {
                        "description": "Get project files",
                        "method": "get_project_files",
                        "params": {
                            "project_name": "my-docs",
                            "include_content": True
                        }
                    }
                ]
            },
            "setup_instructions": {
                "claude_desktop": {
                    "description": "Add to Claude Desktop MCP configuration",
                    "config_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
                    "config_snippet": {
                        "mcpServers": {
                            "bablib": {
                                "command": "curl",
                                "args": [
                                    "-X", "POST",
                                    "-H", "Content-Type: application/json",
                                    "--data-raw", '{"method": "{method}", "params": {params}}',
                                    config.url
                                ]
                            }
                        }
                    }
                }
            }
        }

    def _generate_admin_config(self, config: McpServerConfig) -> Dict[str, Any]:
        """Generate configuration for admin MCP server.

        Args:
            config: Server configuration

        Returns:
            Configuration data dictionary
        """
        return {
            "mcpServers": {
                "bablib-admin": {
                    "command": "node",
                    "args": [],
                    "env": {
                        "BABLIB_MCP_ADMIN_URL": config.url
                    }
                }
            },
            "server": {
                "name": "Bablib Admin MCP Server",
                "version": "1.0.0",
                "description": "Full administrative control over Bablib operations",
                "url": config.url,
                "type": "admin",
                "security_notice": "LOCALHOST ONLY - Admin server restricted to 127.0.0.1 for security",
                "endpoints": {
                    "execute_command": f"{config.url}/mcp/v1/execute_command",
                    "project_create": f"{config.url}/mcp/v1/project_create",
                    "project_remove": f"{config.url}/mcp/v1/project_remove",
                    "crawl_project": f"{config.url}/mcp/v1/crawl_project",
                    "health": f"{config.url}/mcp/v1/health"
                },
                "capabilities": [
                    "full_command_execution",
                    "project_management",
                    "crawling_operations",
                    "system_administration"
                ],
                "security": {
                    "write_access": True,
                    "command_execution": True,
                    "localhost_only": True,
                    "trusted_clients_only": True
                }
            },
            "usage": {
                "examples": [
                    {
                        "description": "Create a new project",
                        "method": "project_create",
                        "params": {
                            "name": "my-new-project",
                            "type": "crawling",
                            "description": "My documentation project"
                        }
                    },
                    {
                        "description": "Start crawling a project",
                        "method": "crawl_project",
                        "params": {
                            "project_name": "my-project",
                            "url": "https://docs.example.com",
                            "max_pages": 100
                        }
                    },
                    {
                        "description": "Execute any Bablib command",
                        "method": "execute_command",
                        "params": {
                            "command": "project",
                            "arguments": ["--list", "--verbose"]
                        }
                    }
                ]
            },
            "security_warnings": [
                "This server has full access to Bablib operations",
                "Only use with trusted local AI assistants",
                "Server is restricted to localhost (127.0.0.1) only",
                "Do not expose this server to external networks",
                "Monitor usage and disable when not needed"
            ],
            "setup_instructions": {
                "claude_desktop": {
                    "description": "Add to Claude Desktop MCP configuration (LOCAL ONLY)",
                    "config_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
                    "security_note": "Ensure Claude Desktop is running locally and accessing 127.0.0.1 only",
                    "config_snippet": {
                        "mcpServers": {
                            "bablib-admin": {
                                "command": "curl",
                                "args": [
                                    "-X", "POST",
                                    "-H", "Content-Type: application/json",
                                    "--data-raw", '{"method": "{method}", "params": {params}}',
                                    config.url
                                ]
                            }
                        }
                    }
                }
            }
        }

    def generate_combined_config(self, configs: List[McpServerConfig]) -> Path:
        """Generate a combined configuration file with both servers.

        Args:
            configs: List of server configurations

        Returns:
            Path to generated combined configuration file
        """
        combined_config = {
            "mcpServers": {},
            "servers": [],
            "usage_guide": {
                "read_only_server": "Use for safe documentation access and search",
                "admin_server": "Use for project management and Bablib operations",
                "security": "Admin server is localhost-only for security"
            }
        }

        for config in configs:
            if not config.enabled:
                continue

            if config.server_type == McpServerType.READ_ONLY:
                server_config = self._generate_read_only_config(config)
                combined_config["mcpServers"]["bablib"] = server_config["mcpServers"]["bablib"]
                combined_config["servers"].append(server_config["server"])
            elif config.server_type == McpServerType.ADMIN:
                server_config = self._generate_admin_config(config)
                combined_config["mcpServers"]["bablib-admin"] = server_config["mcpServers"]["bablib-admin"]
                combined_config["servers"].append(server_config["server"])

        # Write combined config file
        file_path = self.output_dir / "bablib-mcp-combined.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_config, f, indent=2)

        logger.info(f"Generated combined MCP config: {file_path}")
        return file_path

    def clean_old_configs(self):
        """Remove old configuration files from output directory."""
        config_files = [
            "bablib.json",
            "bablib-admin.json",
            "bablib-mcp-combined.json"
        ]

        for filename in config_files:
            file_path = self.output_dir / filename
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Removed old config file: {file_path}")