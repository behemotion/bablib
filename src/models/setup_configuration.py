"""SetupConfiguration model for Bablib setup logic.

This model stores user configuration choices and preferences for the Bablib setup process.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from packaging import version
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .setup_types import (
    EmbeddingModelConfig,
    MCPClientConfig,
    SetupMode,
    SetupStatus,
    VectorStorageConfig
)


class SetupConfiguration(BaseModel):
    """Stores user configuration choices and preferences for the Bablib setup process.

    This model represents a complete setup configuration including all components
    (vector storage, embedding models, MCP clients) and metadata about when and
    how the setup was performed.
    """

    setup_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this setup configuration"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the configuration was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last modification timestamp"
    )
    setup_mode: SetupMode = Field(
        description="Interactive or auto setup mode used"
    )
    vector_storage: VectorStorageConfig | None = Field(
        default=None,
        description="Vector database configuration"
    )
    embedding_model: EmbeddingModelConfig | None = Field(
        default=None,
        description="Embedding model configuration"
    )
    mcp_clients: list[MCPClientConfig] = Field(
        default_factory=list,
        description="MCP client integration configurations"
    )
    setup_status: SetupStatus = Field(
        default=SetupStatus.PENDING,
        description="Current status of the setup process"
    )
    version: str = Field(
        description="Bablib version when setup was performed"
    )

    model_config = ConfigDict(
        use_enum_values=True)

    @field_validator('setup_id')
    @classmethod
    def validate_setup_id(cls, v: UUID) -> UUID:
        """Validate setup_id is a proper UUID v4."""
        if v.version != 4:
            raise ValueError("setup_id must be a UUID v4")
        return v

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version follows semantic versioning pattern."""
        try:
            version.parse(v)
        except version.InvalidVersion:
            raise ValueError(f"Invalid semantic version: {v}")
        return v

    @model_validator(mode='after')
    def validate_timestamps(self) -> 'SetupConfiguration':
        """Validate created_at <= updated_at."""
        if self.created_at > self.updated_at:
            raise ValueError("created_at must be <= updated_at")
        return self

    @model_validator(mode='after')
    def validate_at_least_one_component(self) -> 'SetupConfiguration':
        """Validate at least one component is configured."""
        if not self.vector_storage and not self.embedding_model:
            raise ValueError("At least one component must be configured (vector_storage or embedding_model)")
        return self

    @model_validator(mode='after')
    def validate_status_transitions(self) -> 'SetupConfiguration':
        """Validate setup status transitions are valid."""
        # Note: This is a basic validation. More complex transition validation
        # would require knowledge of the previous state, which isn't available here.
        valid_statuses = {status.value for status in SetupStatus}
        if self.setup_status not in valid_statuses:
            raise ValueError(f"Invalid setup status: {self.setup_status}")
        return self

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.now(UTC)

    def is_completed(self) -> bool:
        """Check if setup is completed successfully."""
        return self.setup_status == SetupStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if setup has failed."""
        return self.setup_status == SetupStatus.FAILED

    def is_in_progress(self) -> bool:
        """Check if setup is currently in progress."""
        return self.setup_status == SetupStatus.IN_PROGRESS

    def can_be_retried(self) -> bool:
        """Check if setup can be retried (failed or cancelled)."""
        return self.setup_status in {SetupStatus.FAILED, SetupStatus.CANCELLED}

    def get_configured_components(self) -> list[str]:
        """Get list of configured component names."""
        components = []
        if self.vector_storage:
            components.append(f"vector_storage ({self.vector_storage.provider})")
        if self.embedding_model:
            components.append(f"embedding_model ({self.embedding_model.provider})")
        if self.mcp_clients:
            components.extend([f"mcp_client ({client.client_name})" for client in self.mcp_clients])
        return components

    def get_configuration_summary(self) -> dict:
        """Get a summary of the current configuration."""
        return {
            "setup_id": str(self.setup_id),
            "mode": self.setup_mode,
            "status": self.setup_status,
            "created": self.created_at.isoformat(),
            "updated": self.updated_at.isoformat(),
            "version": self.version,
            "components": self.get_configured_components(),
            "vector_storage_configured": self.vector_storage is not None,
            "embedding_model_configured": self.embedding_model is not None,
            "mcp_clients_count": len(self.mcp_clients)
        }

    def mark_as_completed(self) -> None:
        """Mark setup as completed and update timestamp."""
        self.setup_status = SetupStatus.COMPLETED
        self.update_timestamp()

    def mark_as_failed(self) -> None:
        """Mark setup as failed and update timestamp."""
        self.setup_status = SetupStatus.FAILED
        self.update_timestamp()

    def mark_as_in_progress(self) -> None:
        """Mark setup as in progress and update timestamp."""
        self.setup_status = SetupStatus.IN_PROGRESS
        self.update_timestamp()

    def reset_for_retry(self) -> None:
        """Reset setup status to pending for retry."""
        if not self.can_be_retried():
            raise ValueError(f"Cannot retry setup in status: {self.setup_status}")
        self.setup_status = SetupStatus.PENDING
        self.update_timestamp()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict) -> 'SetupConfiguration':
        """Create instance from dictionary."""
        return cls(**data)
