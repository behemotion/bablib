"""
ServiceConfiguration model with ServiceStatus enum.
Manages external service settings and health status.
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceStatus(Enum):
    """Service status enumeration"""
    NOT_DETECTED = "not_detected"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    RENAMED = "renamed"  # For container renaming scenario


class ServiceConfiguration(BaseModel):
    """External service configuration and status management"""
    model_config = ConfigDict(str_strip_whitespace=True)

    service_name: str = Field(..., description="Name of the service (e.g., 'qdrant', 'docker')")
    container_name: str = Field(..., description="Docker container name if applicable")
    port: int = Field(..., description="Service port number")
    image: str = Field(..., description="Docker image name if applicable")
    status: ServiceStatus = Field(..., description="Current service status")
    health_check_url: str | None = Field(None, description="URL for health checks")
    dependencies: list[str] = Field(default_factory=list, description="List of service dependencies")
    config_params: dict[str, Any] = Field(default_factory=dict, description="Service-specific configuration")

    # Status tracking
    last_checked: datetime = Field(default_factory=datetime.now, description="Last status check time")
    error_message: str | None = Field(None, description="Error message if status is ERROR")

    @field_validator('service_name')
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name is not empty"""
        if not v.strip():
            raise ValueError("service_name cannot be empty")
        return v.lower()

    @field_validator('container_name')
    @classmethod
    def validate_container_name(cls, v: str) -> str:
        """Validate container name follows Docker naming conventions"""
        if not v.strip():
            raise ValueError("container_name cannot be empty")

        # Docker container name validation
        if not v.replace('-', '').replace('_', '').replace('.', '').isalnum():
            raise ValueError("container_name must contain only alphanumeric characters, hyphens, underscores, and periods")

        return v

    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range"""
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v

    def is_qdrant_service(self) -> bool:
        """Check if this is a Qdrant service configuration"""
        return self.service_name == "qdrant"

    def enforce_standard_qdrant_naming(self) -> bool:
        """Enforce standard Qdrant container naming (FR-004)"""
        if self.is_qdrant_service():
            if self.container_name != "bablib-memory-qdrant":
                self.container_name = "bablib-memory-qdrant"
                self.status = ServiceStatus.RENAMED
                return True
        return False

    def is_running(self) -> bool:
        """Check if service is currently running"""
        return self.status == ServiceStatus.RUNNING

    def is_available(self) -> bool:
        """Check if service is available (running or can be started)"""
        return self.status in [ServiceStatus.RUNNING, ServiceStatus.STOPPED]

    def mark_as_running(self) -> None:
        """Mark service as running and update timestamp"""
        self.status = ServiceStatus.RUNNING
        self.last_checked = datetime.now()
        self.error_message = None

    def mark_as_stopped(self) -> None:
        """Mark service as stopped and update timestamp"""
        self.status = ServiceStatus.STOPPED
        self.last_checked = datetime.now()
        self.error_message = None

    def mark_as_error(self, error_message: str) -> None:
        """Mark service as error with message and update timestamp"""
        self.status = ServiceStatus.ERROR
        self.error_message = error_message
        self.last_checked = datetime.now()

    def mark_as_installing(self) -> None:
        """Mark service as currently installing"""
        self.status = ServiceStatus.INSTALLING
        self.last_checked = datetime.now()
        self.error_message = None

    def update_config_param(self, key: str, value: Any) -> None:
        """Update a configuration parameter"""
        self.config_params[key] = value

    def get_config_param(self, key: str, default: Any = None) -> Any:
        """Get a configuration parameter value"""
        return self.config_params.get(key, default)

    def get_health_check_info(self) -> dict[str, Any]:
        """Get health check information"""
        return {
            "url": self.health_check_url,
            "last_checked": self.last_checked.isoformat(),
            "status": self.status.value,
            "error_message": self.error_message
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "service_name": self.service_name,
            "container_name": self.container_name,
            "port": self.port,
            "image": self.image,
            "status": self.status.value,
            "health_check_url": self.health_check_url,
            "dependencies": self.dependencies,
            "config_params": self.config_params,
            "last_checked": self.last_checked.isoformat(),
            "error_message": self.error_message
        }

    @classmethod
    def create_qdrant_config(cls, port: int = 6333) -> "ServiceConfiguration":
        """Create standard Qdrant service configuration"""
        return cls(
            service_name="qdrant",
            container_name="bablib-memory-qdrant",  # Standard naming (FR-004)
            port=port,
            image="qdrant/qdrant:latest",
            status=ServiceStatus.NOT_DETECTED,
            health_check_url=f"http://localhost:{port}/health",
            dependencies=["docker"],
            config_params={
                "data_path": "/qdrant/storage",
                "log_level": "INFO"
            }
        )

    @classmethod
    def create_docker_config(cls) -> "ServiceConfiguration":
        """Create Docker service configuration"""
        return cls(
            service_name="docker",
            container_name="",  # Docker daemon doesn't have a container name
            port=0,  # Docker daemon port varies
            image="",
            status=ServiceStatus.NOT_DETECTED,
            health_check_url=None,
            dependencies=[],
            config_params={}
        )

    @classmethod
    def create_ollama_config(cls, port: int = 11434) -> "ServiceConfiguration":
        """Create Ollama service configuration"""
        return cls(
            service_name="ollama",
            container_name="ollama",
            port=port,
            image="ollama/ollama:latest",
            status=ServiceStatus.NOT_DETECTED,
            health_check_url=f"http://localhost:{port}/api/tags",
            dependencies=["docker"],
            config_params={
                "model": "mxbai-embed-large",
                "gpu_enabled": False
            }
        )


# Service relationship validation
class ServiceDependencyValidator:
    """Validates service dependencies and startup order"""

    KNOWN_SERVICES = {
        "docker": {"dependencies": []},
        "qdrant": {"dependencies": ["docker"]},
        "ollama": {"dependencies": ["docker"]},
        "mcp_server": {"dependencies": ["qdrant", "ollama"]}
    }

    @classmethod
    def validate_dependencies(cls, service_configs: list[ServiceConfiguration]) -> list[str]:
        """Validate all service dependencies are satisfied"""
        errors = []
        service_names = {config.service_name for config in service_configs}

        for config in service_configs:
            for dependency in config.dependencies:
                if dependency not in service_names:
                    errors.append(f"Service '{config.service_name}' depends on '{dependency}' which is not configured")

        return errors

    @classmethod
    def get_startup_order(cls, service_configs: list[ServiceConfiguration]) -> list[str]:
        """Get the correct startup order based on dependencies"""
        # Simple topological sort for dependency resolution
        remaining = {config.service_name: set(config.dependencies) for config in service_configs}
        ordered = []

        while remaining:
            # Find services with no remaining dependencies
            ready = [name for name, deps in remaining.items() if not deps]

            if not ready:
                # Circular dependency or missing dependency
                break

            # Add ready services to ordered list
            for name in ready:
                ordered.append(name)
                del remaining[name]

            # Remove satisfied dependencies
            for name in ready:
                for deps in remaining.values():
                    deps.discard(name)

        return ordered


# Example usage:
# qdrant_config = ServiceConfiguration.create_qdrant_config()
# qdrant_config.enforce_standard_qdrant_naming()  # Ensures "bablib-memory-qdrant"
# qdrant_config.mark_as_installing()
# qdrant_config.mark_as_running()
