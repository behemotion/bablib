"""Supporting types and enums for setup logic models.

This module defines all the enums, exceptions, and supporting data types
used by the setup logic data models.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Enums
# ============================================================================

class SetupMode(str, Enum):
    """Setup mode - interactive with user prompts or automatic with defaults."""
    INTERACTIVE = "interactive"
    AUTO = "auto"


class SetupStatus(str, Enum):
    """Current status of the setup process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComponentType(str, Enum):
    """Type of external component."""
    DOCKER = "docker"
    OLLAMA = "ollama"
    MCP_CLIENT = "mcp_client"


class HealthStatus(str, Enum):
    """Health status of a component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SetupStep(str, Enum):
    """Individual setup steps in order of execution."""
    DETECT_COMPONENTS = "detect_components"
    CONFIGURE_VECTOR_STORAGE = "configure_vector_storage"
    SETUP_EMBEDDING_MODEL = "setup_embedding_model"
    CONFIGURE_MCP_CLIENTS = "configure_mcp_clients"
    VALIDATE_CONFIGURATION = "validate_configuration"
    PERSIST_SETTINGS = "persist_settings"


class SessionStatus(str, Enum):
    """Overall session status."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Nested Configuration Objects
# ============================================================================

class VectorStorageConfig(BaseModel):
    """Configuration for vector database setup (currently Qdrant only)."""

    provider: str = Field(default="qdrant", description="Vector storage provider")
    connection_url: str = Field(description="Connection URL (e.g., 'http://localhost:6333')")
    container_name: str = Field(default="bablib-memory-qdrant", description="Docker container name")
    data_path: Path = Field(description="Local data storage path")
    configuration: dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that provider is supported."""
        if v not in ["qdrant", "sqlite_vec"]:
            raise ValueError(f"Unsupported vector storage provider: {v}")
        return v

    @field_validator('connection_url')
    @classmethod
    def validate_connection_url(cls, v: str) -> str:
        """Validate connection URL format."""
        if not (v.startswith('http://') or v.startswith('https://') or v.startswith('sqlite://')):
            raise ValueError("Connection URL must start with http://, https://, or sqlite://")
        return v


class EmbeddingModelConfig(BaseModel):
    """Configuration for embedding model setup."""

    provider: str = Field(default="ollama", description="Embedding provider")
    model_name: str = Field(description="Model identifier (e.g., 'embeddinggemma:300m-qat-q4_0')")
    model_size_mb: int | None = Field(default=None, description="Model size in megabytes")
    download_required: bool = Field(description="Whether model needs to be downloaded")
    fallback_models: list[str] = Field(default_factory=list, description="Fallback model names in priority order")
    configuration: dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that provider is supported."""
        if v != "ollama":
            raise ValueError(f"Unsupported embedding provider: {v}")
        return v

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """Validate model name is not empty."""
        if not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()


class MCPClientConfig(BaseModel):
    """Configuration for MCP client integration."""

    client_name: str = Field(description="Client identifier (e.g., 'claude-code')")
    client_type: str = Field(description="Type of MCP client")
    executable_path: Path | None = Field(default=None, description="Path to client executable")
    config_file_path: Path | None = Field(default=None, description="Path to client configuration file")
    server_config: dict[str, Any] = Field(default_factory=dict, description="MCP server configuration for this client")
    enabled: bool = Field(description="Whether integration is enabled")

    @field_validator('client_name')
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        """Validate client name is not empty."""
        if not v.strip():
            raise ValueError("Client name cannot be empty")
        return v.strip()


class SetupStepFailure(BaseModel):
    """Detailed information about setup step failures."""

    step: SetupStep = Field(description="Which step failed")
    error_type: str = Field(description="Category of error (e.g., 'network', 'permission', 'configuration')")
    error_message: str = Field(description="Human-readable error description")
    technical_details: str | None = Field(default=None, description="Technical error details for debugging")
    retry_possible: bool = Field(description="Whether this step can be retried")
    suggested_action: str | None = Field(default=None, description="Suggested user action to resolve")

    @field_validator('error_type')
    @classmethod
    def validate_error_type(cls, v: str) -> str:
        """Validate error type is recognized."""
        valid_types = {"network", "permission", "configuration", "dependency", "timeout"}
        if v not in valid_types:
            raise ValueError(f"Error type must be one of: {', '.join(valid_types)}")
        return v


class RollbackPoint(BaseModel):
    """Checkpoint for rollback during setup failures."""

    step: SetupStep = Field(description="Step where rollback point was created")
    timestamp: datetime = Field(description="When rollback point was created")
    state_data: dict[str, Any] = Field(description="Serialized state for rollback")
    description: str = Field(description="Human-readable description of rollback point")


# ============================================================================
# Custom Exceptions
# ============================================================================

class SetupBaseException(Exception):
    """Base exception for setup-related errors."""
    pass


class SetupConfigurationError(SetupBaseException):
    """Configuration error during setup."""
    pass


class ExternalDependencyError(SetupBaseException):
    """External dependency (Docker, Ollama) not available."""
    pass


class UserCancellationError(SetupBaseException):
    """User cancelled the setup process."""
    pass


class SetupSessionExistsError(SetupBaseException):
    """Setup session already exists and is in progress."""
    pass


class SessionNotFoundError(SetupBaseException):
    """Setup session not found."""
    pass


class SetupInProgressError(SetupBaseException):
    """Setup execution already in progress."""
    pass


class SetupAlreadyCompletedError(SetupBaseException):
    """Setup has already been completed."""
    pass


class PermissionError(SetupBaseException):
    """Permission error during setup operations."""
    pass


class DiskSpaceError(SetupBaseException):
    """Insufficient disk space for setup operations."""
    pass


class TimeoutError(SetupBaseException):
    """Timeout during setup operations."""
    pass


# ============================================================================
# Helper Functions
# ============================================================================

def get_valid_setup_steps() -> list[SetupStep]:
    """Get all valid setup steps in execution order."""
    return [
        SetupStep.DETECT_COMPONENTS,
        SetupStep.CONFIGURE_VECTOR_STORAGE,
        SetupStep.SETUP_EMBEDDING_MODEL,
        SetupStep.CONFIGURE_MCP_CLIENTS,
        SetupStep.VALIDATE_CONFIGURATION,
        SetupStep.PERSIST_SETTINGS
    ]


def is_step_before(step1: SetupStep, step2: SetupStep) -> bool:
    """Check if step1 comes before step2 in the execution order."""
    steps = get_valid_setup_steps()
    try:
        return steps.index(step1) < steps.index(step2)
    except ValueError:
        return False


def get_next_step(current_step: SetupStep) -> SetupStep | None:
    """Get the next step after the current step."""
    steps = get_valid_setup_steps()
    try:
        current_index = steps.index(current_step)
        if current_index < len(steps) - 1:
            return steps[current_index + 1]
        return None
    except ValueError:
        return None
