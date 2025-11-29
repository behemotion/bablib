"""
Settings models for backward compatibility with test suite.

This module provides compatibility models that wrap the unified BablibConfig
from src.core.config to maintain existing test contracts.
"""

from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import List, Dict, Any

from src.core.config import BablibConfig
from src.models.vector_store_types import VectorStoreProvider


class GlobalSettings(BaseModel):
    """Global settings model for backward compatibility."""

    # Crawling configuration
    crawl_depth: int = Field(default=3, ge=1, le=10)
    rate_limit: float = Field(default=2.0, ge=0.1, le=10.0)
    max_page_size_mb: float = Field(default=10.0)
    outdated_days: int = Field(default=60)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=30, ge=5, le=300)

    # Embedding configuration
    embedding_model: str = Field(default="mxbai-embed-large")
    chunk_size: int = Field(default=1500, ge=100, le=10000)  # Test expects 1500
    chunk_overlap: int = Field(default=100, ge=0, le=1000)

    # RAG Configuration
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_temperature: float = Field(default=0.7, ge=0.0, le=1.0)

    # Vector store configuration
    vector_store_provider: VectorStoreProvider = Field(default=VectorStoreProvider.SQLITE_VEC)
    vector_storage: str = Field(default="~/.local/share/bablib/vectors")

    # Service URLs
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_timeout: int = Field(default=300)

    # Legacy MCP Server configuration (kept for backward compatibility)
    mcp_host: str = Field(default="localhost")
    mcp_port: int = Field(default=9382)
    mcp_auth_token: str | None = Field(default=None)

    # Shelf-Box System
    current_shelf: str | None = Field(default=None, description="Current active shelf ID")

    # MCP Server Configurations (structured approach)
    mcp_server_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "read-only": {
                "server_type": "read-only",
                "host": "0.0.0.0",
                "port": 9383,
                "enabled": True
            },
            "admin": {
                "server_type": "admin",
                "host": "127.0.0.1",
                "port": 9384,
                "enabled": True
            }
        }
    )

    # Individual MCP settings for backward compatibility
    mcp_read_only_host: str = Field(default="0.0.0.0")
    mcp_read_only_port: int = Field(default=9383, ge=1024, le=65535)
    mcp_admin_host: str = Field(default="127.0.0.1")
    mcp_admin_port: int = Field(default=9384, ge=1024, le=65535)
    mcp_read_only_enabled: bool = Field(default=True)
    mcp_admin_enabled: bool = Field(default=True)

    # Logging configuration
    log_level: str = Field(default="WARNING")

    @field_validator("mcp_server_configs")
    @classmethod
    def validate_mcp_server_configs(cls, v: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Validate MCP server configurations."""
        if not isinstance(v, dict):
            raise ValueError("mcp_server_configs must be a dictionary")

        # Check for required server types
        required_types = {"read-only", "admin"}
        existing_types = set(v.keys())

        if not required_types.issubset(existing_types):
            missing = required_types - existing_types
            raise ValueError(f"Missing required server configurations: {missing}")

        # Validate each server configuration
        for server_name, config in v.items():
            if not isinstance(config, dict):
                raise ValueError(f"Server config for '{server_name}' must be a dictionary")

            # Validate required fields
            required_fields = {"server_type", "host", "port", "enabled"}
            missing_fields = required_fields - set(config.keys())
            if missing_fields:
                raise ValueError(f"Server '{server_name}' missing required fields: {missing_fields}")

            # Validate port range
            port = config.get("port")
            if not isinstance(port, int) or port < 1024 or port > 65535:
                raise ValueError(f"Server '{server_name}' port must be an integer between 1024 and 65535")

            # Validate admin server localhost restriction
            if config.get("server_type") == "admin":
                host = config.get("host")
                if host not in ["127.0.0.1", "localhost"]:
                    raise ValueError("Admin server must be bound to localhost (127.0.0.1) for security")

        return v

    @field_validator("mcp_admin_host")
    @classmethod
    def validate_admin_host(cls, v: str) -> str:
        """Validate that admin host is localhost for security."""
        if v not in ["127.0.0.1", "localhost"]:
            raise ValueError("Admin server must be bound to localhost (127.0.0.1 or localhost) for security")
        return v

    def get_mcp_server_configs(self) -> List[Dict[str, Any]]:
        """Get MCP server configurations as a list."""
        configs = []
        for server_name, config in self.mcp_server_configs.items():
            # Add server name to config for identification
            config_with_name = config.copy()
            config_with_name["name"] = server_name
            configs.append(config_with_name)
        return configs

    def validate_port_conflicts(self) -> bool:
        """Check for port conflicts between MCP servers."""
        ports = []
        for config in self.mcp_server_configs.values():
            if config.get("enabled", False):
                ports.append(config.get("port"))

        # Check for duplicates
        return len(ports) == len(set(ports))

    def get_enabled_mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get only enabled MCP server configurations."""
        return {
            name: config for name, config in self.mcp_server_configs.items()
            if config.get("enabled", False)
        }


class VectorStoreSettings(BaseModel):
    """Vector store settings model for testing compatibility."""

    provider: VectorStoreProvider
    qdrant_config: Dict[str, Any] | None = None
    sqlite_vec_config: Dict[str, Any] | None = None

    @field_validator("qdrant_config", mode="before")
    @classmethod
    def validate_qdrant_config(cls, v, info: ValidationInfo):
        """Validate Qdrant config when provider is QDRANT."""
        provider = info.data.get("provider") if info.data else None
        if provider == VectorStoreProvider.QDRANT:
            if not v:
                return {"url": "http://localhost:6333", "api_key": None}
        return v

    @field_validator("sqlite_vec_config", mode="before")
    @classmethod
    def validate_sqlite_vec_config(cls, v, info: ValidationInfo):
        """Validate SQLite-vec config when provider is SQLITE_VEC."""
        provider = info.data.get("provider") if info.data else None
        if provider == VectorStoreProvider.SQLITE_VEC:
            if not v:
                return {"database_path": "~/.local/share/bablib/vectors.db"}
        return v

    @classmethod
    def from_config(cls, config: BablibConfig) -> "GlobalSettings":
        """Create GlobalSettings from BablibConfig."""
        # Create with defaults first, then override with config values
        data = {}
        for field_name in cls.model_fields:
            if hasattr(config, field_name):
                data[field_name] = getattr(config, field_name)

        return cls(**data)


# Define fields that cannot be overridden in project settings
NON_OVERRIDABLE_FIELDS = [
    "vector_store_provider",
    "storage_dir",
    "config_dir",
    "cache_dir"
]


class ProjectSettings(BaseModel):
    """Project-specific settings that can override global settings."""

    # Only overridable fields
    crawl_depth: int | None = Field(default=None, ge=1, le=10)
    rate_limit: float | None = Field(default=None, ge=0.1, le=10.0)
    max_page_size_mb: float | None = Field(default=None)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    timeout: int | None = Field(default=None, ge=5, le=300)
    embedding_model: str | None = Field(default=None)
    chunk_size: int | None = Field(default=None, ge=100, le=10000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=1000)
    rag_top_k: int | None = Field(default=None, ge=1, le=20)
    rag_temperature: float | None = Field(default=None, ge=0.0, le=1.0)

    # Track which fields have been explicitly set
    modified_fields: set[str] = Field(default_factory=set, exclude=True)


class EffectiveSettings(BaseModel):
    """Effective settings after applying project overrides to global settings."""

    # All fields from GlobalSettings
    crawl_depth: int = Field(ge=1, le=10)
    rate_limit: float = Field(ge=0.1, le=10.0)
    max_page_size_mb: float
    outdated_days: int
    max_retries: int = Field(ge=0, le=10)
    timeout: int = Field(ge=5, le=300)
    embedding_model: str
    chunk_size: int = Field(ge=100, le=10000)
    chunk_overlap: int = Field(ge=0, le=1000)
    rag_top_k: int = Field(ge=1, le=20)
    rag_temperature: float = Field(ge=0.0, le=1.0)
    vector_store_provider: VectorStoreProvider
    vector_storage: str
    qdrant_url: str
    qdrant_api_key: str | None
    ollama_url: str
    ollama_timeout: int
    # Legacy MCP configuration
    mcp_host: str
    mcp_port: int
    mcp_auth_token: str | None

    # Structured MCP configuration
    mcp_server_configs: Dict[str, Dict[str, Any]]

    # Individual MCP settings (for backward compatibility)
    mcp_read_only_host: str
    mcp_read_only_port: int
    mcp_admin_host: str
    mcp_admin_port: int
    mcp_read_only_enabled: bool
    mcp_admin_enabled: bool
    log_level: str

    @classmethod
    def from_configs(
        cls,
        global_settings: GlobalSettings,
        project_settings: ProjectSettings | None = None
    ) -> "EffectiveSettings":
        """Create effective settings by merging global and project settings."""
        # Start with global settings
        data = global_settings.model_dump()

        # Apply project overrides for overridable fields only
        if project_settings:
            overridable_fields = {
                'crawl_depth', 'rate_limit', 'max_page_size_mb', 'max_retries',
                'timeout', 'embedding_model', 'chunk_size', 'chunk_overlap',
                'rag_top_k', 'rag_temperature'
            }

            for field in overridable_fields:
                project_value = getattr(project_settings, field, None)
                if project_value is not None and field in getattr(project_settings, 'modified_fields', set()):
                    data[field] = project_value

        return cls(**data)
