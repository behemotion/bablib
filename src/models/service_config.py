"""Service configuration models for Bablib."""

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceName(str, Enum):
    """Supported service names."""
    DOCKER = "docker"
    QDRANT = "qdrant"
    OLLAMA = "ollama"


class ServiceStatusType(str, Enum):
    """Service status with proper state transitions."""
    NOT_FOUND = "not_found"
    DETECTED = "detected"
    CONFIGURED = "configured"
    RUNNING = "running"
    FAILED = "failed"


class ServiceConfiguration(BaseModel):
    """Configuration model for external services with validation and state management."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )

    # Core service identification
    service_name: ServiceName = Field(
        ...,
        description="Name of the service (docker, qdrant, ollama)"
    )

    # Service configuration
    enabled: bool = Field(
        default=True,
        description="Whether this service is enabled"
    )

    endpoint: str = Field(
        ...,
        description="Service endpoint URL"
    )

    port: int = Field(
        ...,
        description="Service port number",
        ge=1024,
        le=65535
    )

    auto_start: bool = Field(
        default=False,
        description="Whether to automatically start this service"
    )

    # Service status and detection
    detected_version: str | None = Field(
        None,
        description="Detected version of the service"
    )

    version: str | None = Field(
        None,
        description="Service version (alias for detected_version for API compatibility)"
    )

    status: ServiceStatusType = Field(
        default=ServiceStatusType.NOT_FOUND,
        description="Current status of the service"
    )

    error_message: str | None = Field(
        None,
        description="Error message if service is in failed state"
    )

    last_checked: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of last status check"
    )

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint_url(cls, v: str) -> str:
        """Validate endpoint is a valid URL format."""
        url_pattern = r'^https?://[a-zA-Z0-9.-]+(:\d+)?(/.*)?$|^unix:///.+$'
        if not re.match(url_pattern, v):
            raise ValueError(
                "endpoint must be a valid HTTP/HTTPS URL or Unix socket path"
            )
        return v

    @field_validator('port')
    @classmethod
    def validate_port_range(cls, v: int) -> int:
        """Validate port is in acceptable range for services."""
        if v < 1024:
            raise ValueError("port must be >= 1024 (reserved ports not allowed)")
        if v > 65535:
            raise ValueError("port must be <= 65535 (maximum port number)")

        # Check for common conflicting ports
        reserved_ports = {22, 80, 443, 3306, 5432, 27017}
        if v in reserved_ports:
            raise ValueError(f"port {v} is commonly used by other services")

        return v

    @field_validator('detected_version')
    @classmethod
    def validate_version_format(cls, v: str | None) -> str | None:
        """Validate version follows semantic versioning or common patterns."""
        if v is None:
            return v

        # Allow various version patterns
        version_patterns = [
            r'^\d+\.\d+\.\d+$',  # Semantic versioning: 1.2.3
            r'^\d+\.\d+$',       # Major.minor: 1.2
            r'^\d+$',            # Major only: 1
            r'^v\d+\.\d+\.\d+$', # With v prefix: v1.2.3
            r'^[\w\.-]+$'        # Generic: allows alphanumeric, dots, dashes
        ]

        if not any(re.match(pattern, v) for pattern in version_patterns):
            raise ValueError("detected_version must follow a recognized version format")

        return v

    @field_validator('version')
    @classmethod
    def validate_api_version_format(cls, v: str | None) -> str | None:
        """Validate API version field follows same patterns as detected_version."""
        if v is None:
            return v

        # Use same validation as detected_version
        version_patterns = [
            r'^\d+\.\d+\.\d+$',  # Semantic versioning: 1.2.3
            r'^\d+\.\d+$',       # Major.minor: 1.2
            r'^\d+$',            # Major only: 1
            r'^v\d+\.\d+\.\d+$', # With v prefix: v1.2.3
            r'^[\w\.-]+$'        # Generic: allows alphanumeric, dots, dashes
        ]

        if not any(re.match(pattern, v) for pattern in version_patterns):
            raise ValueError("version must follow a recognized version format")

        return v

    def __init__(self, **data):
        """Initialize ServiceConfiguration with version synchronization."""
        # If detected_version is provided but version is not, sync them
        if 'detected_version' in data and 'version' not in data:
            data['version'] = data['detected_version']
        elif 'version' in data and 'detected_version' not in data:
            data['detected_version'] = data['version']

        super().__init__(**data)

    @field_validator('status')
    @classmethod
    def validate_status_transitions(cls, v: ServiceStatusType) -> ServiceStatusType:
        """Validate status is a proper enum value."""
        # The Pydantic enum validation handles the basic validation
        # Additional transition logic can be implemented in service methods
        return v

    @field_validator('error_message')
    @classmethod
    def validate_error_message_consistency(cls, v: str | None, info) -> str | None:
        """Validate error message is consistent with status."""
        if hasattr(info, 'data') and 'status' in info.data:
            status = info.data['status']

            # If status is failed, error_message should be provided
            if status == ServiceStatusType.FAILED and not v:
                raise ValueError("error_message is required when status is 'failed'")

            # If status is not failed, error_message should typically be None
            if status in {ServiceStatusType.RUNNING, ServiceStatusType.CONFIGURED} and v:
                # Allow warning messages, but validate they're not critical errors
                if any(word in v.lower() for word in ['error', 'failed', 'critical']):
                    raise ValueError(
                        f"error_message with critical errors not allowed for status '{status}'"
                    )

        return v

    def can_transition_to(self, new_status: ServiceStatusType) -> bool:
        """Check if service can transition to the new status."""
        valid_transitions = {
            ServiceStatusType.NOT_FOUND: {
                ServiceStatusType.DETECTED,
                ServiceStatusType.FAILED
            },
            ServiceStatusType.DETECTED: {
                ServiceStatusType.CONFIGURED,
                ServiceStatusType.NOT_FOUND,
                ServiceStatusType.FAILED
            },
            ServiceStatusType.CONFIGURED: {
                ServiceStatusType.RUNNING,
                ServiceStatusType.DETECTED,
                ServiceStatusType.FAILED
            },
            ServiceStatusType.RUNNING: {
                ServiceStatusType.CONFIGURED,
                ServiceStatusType.DETECTED,
                ServiceStatusType.FAILED
            },
            ServiceStatusType.FAILED: {
                ServiceStatusType.NOT_FOUND,
                ServiceStatusType.DETECTED,
                ServiceStatusType.CONFIGURED,
                ServiceStatusType.RUNNING
            }
        }

        return new_status in valid_transitions.get(self.status, set())

    def get_default_endpoint(self) -> str:
        """Get default endpoint for the service."""
        defaults = {
            ServiceName.DOCKER: "unix:///var/run/docker.sock",
            ServiceName.QDRANT: f"http://localhost:{self.get_default_port()}",
            ServiceName.OLLAMA: f"http://localhost:{self.get_default_port()}"
        }
        return defaults.get(self.service_name, f"http://localhost:{self.port}")

    def get_default_port(self) -> int:
        """Get default port for the service."""
        defaults = {
            ServiceName.DOCKER: 2376,  # Docker daemon port (though usually unix socket)
            ServiceName.QDRANT: 6333,
            ServiceName.OLLAMA: 11434
        }
        return defaults.get(self.service_name, 9382)

    @classmethod
    def create_default_config(
        cls,
        service_name: ServiceName,
        custom_port: int | None = None,
        custom_endpoint: str | None = None
    ) -> "ServiceConfiguration":
        """Create a default configuration for a service."""
        # Create temporary instance to get defaults
        temp_config = cls(
            service_name=service_name,
            endpoint="http://localhost:9382",  # Temporary for validation
            port=9382  # Temporary for validation
        )

        port = custom_port or temp_config.get_default_port()
        endpoint = custom_endpoint or temp_config.get_default_endpoint()

        return cls(
            service_name=service_name,
            enabled=True,
            endpoint=endpoint,
            port=port,
            auto_start=False,
            detected_version=None,
            version=None,  # API compatibility field
            status=ServiceStatusType.NOT_FOUND,
            error_message=None,
            last_checked=datetime.now()
        )

    def is_healthy(self) -> bool:
        """Check if service is in a healthy state."""
        return self.status in {
            ServiceStatusType.RUNNING,
            ServiceStatusType.CONFIGURED
        }

    def needs_attention(self) -> bool:
        """Check if service needs attention (failed or not found when enabled)."""
        if not self.enabled:
            return False

        return self.status in {
            ServiceStatusType.FAILED,
            ServiceStatusType.NOT_FOUND
        }

    def to_summary_dict(self) -> dict:
        """Convert to summary dictionary for display purposes."""
        return {
            "service_name": self.service_name,
            "enabled": self.enabled,
            "status": self.status,
            "endpoint": self.endpoint,
            "port": self.port,
            "version": self.detected_version,
            "healthy": self.is_healthy(),
            "needs_attention": self.needs_attention(),
            "error": self.error_message
        }
