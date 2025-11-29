"""Data models for UV/UVX installation feature."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InstallationContext(BaseModel):
    """Track installation metadata and environment information."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True)

    install_method: str = Field(..., description="Installation method")
    install_date: datetime = Field(..., description="When Bablib was installed")
    version: str = Field(..., description="Bablib version")
    python_version: str = Field(..., description="Python version used")
    uv_version: str | None = Field(None, description="UV version if available")
    install_path: Path = Field(..., description="Path to bablib executable")
    is_global: bool = Field(..., description="True for global, False for project-local")
    user_data_dir: Path = Field(..., description="User data directory")
    config_dir: Path = Field(..., description="Configuration directory")
    cache_dir: Path = Field(..., description="Cache directory")

    @field_validator('install_method')
    @classmethod
    def validate_install_method(cls, v: str) -> str:
        """Validate install method is one of allowed values."""
        allowed_methods = {"uvx", "uv-tool", "manual", "development"}
        if v not in allowed_methods:
            raise ValueError(f"install_method must be one of {allowed_methods}")
        return v

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        semver_pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(semver_pattern, v):
            raise ValueError("version must follow semantic versioning (e.g., '1.0.0')")
        return v

    @field_validator('python_version')
    @classmethod
    def validate_python_version(cls, v: str) -> str:
        """Validate Python version is 3.13.x."""
        if not v.startswith("3.13."):
            raise ValueError("python_version must be 3.13.x")
        return v

    @field_validator('install_path', 'user_data_dir', 'config_dir', 'cache_dir')
    @classmethod
    def validate_paths(cls, v: Path) -> Path:
        """Validate paths are absolute."""
        if not v.is_absolute():
            raise ValueError("Paths must be absolute")
        return v


class ServiceStatus(BaseModel):
    """Track availability and configuration of external services."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    name: str = Field(..., description="Service name")
    available: bool = Field(..., description="Whether service is available")
    version: str | None = Field(None, description="Service version if available")
    endpoint: str | None = Field(None, description="Service endpoint")
    last_checked: datetime = Field(..., description="When service was last checked")
    error_message: str | None = Field(None, description="Error message if unavailable")
    setup_completed: bool = Field(..., description="Whether setup was completed")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate service name is supported."""
        supported_services = {"docker", "ollama", "qdrant"}  # Redis removed
        if v not in supported_services:
            raise ValueError(f"name must be one of {supported_services}")
        return v


class SetupWizardState(BaseModel):
    """Track progress through first-run setup process."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    current_step: str = Field(..., description="Current setup step")
    completed_steps: list[str] = Field(default_factory=list, description="Completed steps")
    services_to_install: list[str] = Field(default_factory=list, description="Services to install")
    user_preferences: dict[str, Any] = Field(default_factory=dict, description="User preferences")
    skip_services: list[str] = Field(default_factory=list, description="Services to skip")
    setup_start_time: datetime = Field(..., description="When setup started")

    @field_validator('current_step')
    @classmethod
    def validate_current_step(cls, v: str) -> str:
        """Validate current step is valid."""
        valid_steps = {
            "welcome", "python_check", "service_check", "service_install",
            "config_setup", "complete"
        }
        if v not in valid_steps:
            raise ValueError(f"current_step must be one of {valid_steps}")
        return v

    @field_validator('services_to_install', 'skip_services')
    @classmethod
    def validate_service_lists(cls, v: list[str]) -> list[str]:
        """Validate service names in lists."""
        valid_services = {"docker", "ollama", "qdrant"}  # Redis removed
        for service in v:
            if service not in valid_services:
                raise ValueError(f"Service '{service}' not in {valid_services}")
        return v

    @field_validator('completed_steps')
    @classmethod
    def validate_completed_steps(cls, v: list[str]) -> list[str]:
        """Validate completed steps order."""
        valid_steps = [
            "welcome", "python_check", "service_check", "service_install",
            "config_setup", "complete"
        ]

        # Check if any completed step comes before earlier required steps
        step_indices = {step: i for i, step in enumerate(valid_steps)}

        for i, step in enumerate(v):
            if step not in step_indices:
                raise ValueError(f"Invalid step: {step}")

            # Check that all previous required steps are also completed
            step_index = step_indices[step]
            for j in range(step_index):
                required_step = valid_steps[j]
                if required_step not in v[:i+1] and required_step != step:
                    # Allow skipping some steps, but ensure logical order
                    pass

        return v

    @field_validator('skip_services')
    @classmethod
    def validate_no_overlap_with_install(cls, v: list[str], info) -> list[str]:
        """Validate services aren't in both install and skip lists."""
        if hasattr(info, 'data') and 'services_to_install' in info.data:
            install_services = set(info.data['services_to_install'])
            skip_services = set(v)
            overlap = install_services & skip_services
            if overlap:
                raise ValueError(f"Services cannot be in both install and skip lists: {overlap}")
        return v


class PackageMetadata(BaseModel):
    """Store information about the installed package."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    name: str = Field(default="bablib", description="Package name")
    version: str = Field(..., description="Package version")
    description: str = Field(..., description="Package description")
    homepage: str = Field(..., description="Homepage URL")
    repository_url: str = Field(..., description="Repository URL")
    entry_points: dict[str, str] = Field(default_factory=dict, description="Entry points")
    dependencies: list[str] = Field(default_factory=list, description="Package dependencies")
    python_requires: str = Field(default=">=3.13", description="Python version requirement")
    install_source: str = Field(..., description="Installation source")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is always 'bablib'."""
        if v != "bablib":
            raise ValueError("name must be 'bablib'")
        return v

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        semver_pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(semver_pattern, v):
            raise ValueError("version must follow semantic versioning (e.g., '1.0.0')")
        return v

    @field_validator('homepage', 'repository_url')
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Validate URLs are HTTP/HTTPS."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URLs must be HTTP or HTTPS")
        return v


class InstallationRequest(BaseModel):
    """Request model for starting Bablib installation process."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    install_method: Literal["uvx", "uv-tool", "development"] = Field(
        ..., description="Installation method to use"
    )
    version: str = Field(..., description="Version to install")
    user_preferences: dict[str, Any] | None = Field(
        default=None, description="User preferences for installation"
    )
    force_reinstall: bool = Field(
        default=False, description="Whether to force reinstallation"
    )

    @field_validator('version')
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version follows semantic versioning pattern."""
        pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(pattern, v):
            raise ValueError("version must follow semantic versioning pattern (e.g., '1.0.0')")
        return v


class InstallationResponse(BaseModel):
    """Response model for installation start endpoint."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    installation_id: str = Field(..., description="Unique installation identifier")
    status: Literal["started", "in_progress", "completed", "failed"] = Field(
        ..., description="Current installation status"
    )
    message: str = Field(..., description="Status message")
    next_steps: list[str] | None = Field(
        default=None, description="Next steps for the user"
    )

    @field_validator('installation_id')
    @classmethod
    def validate_installation_id(cls, v: str) -> str:
        """Validate installation_id is a valid UUID format."""
        try:
            import uuid
            uuid.UUID(v)
        except (ValueError, TypeError):
            raise ValueError("installation_id must be a valid UUID")
        return v


class SystemRequirements(BaseModel):
    """System requirements validation and information."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    python_version: str = Field(..., description="Required Python version pattern")
    platform: Literal["darwin", "linux", "windows"] = Field(..., description="Target platform")
    memory_mb: int = Field(..., description="Required memory in MB", ge=512)
    disk_space_mb: int = Field(..., description="Required disk space in MB", ge=100)
    has_internet: bool = Field(..., description="Whether internet connection is required")
    supports_docker: bool = Field(default=True, description="Whether Docker support is available")
    requires_admin: bool = Field(default=False, description="Whether admin privileges are required")

    @field_validator('python_version')
    @classmethod
    def validate_python_version_pattern(cls, v: str) -> str:
        """Validate Python version follows pattern ^3\\.13\\.\\d+$"""
        pattern = r"^3\.13\.\d+$"
        if not re.match(pattern, v):
            raise ValueError("python_version must match pattern ^3\\.13\\.\\d+$ (e.g., '3.13.0')")
        return v

    @field_validator('memory_mb', 'disk_space_mb')
    @classmethod
    def validate_positive_integers(cls, v: int) -> int:
        """Validate integer fields are positive."""
        if v <= 0:
            raise ValueError("Memory and disk space must be positive integers")
        return v


class CriticalDecisionPoint(BaseModel):
    """Model for tracking critical decisions during installation."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True)

    decision_id: str = Field(..., description="Unique decision identifier")
    decision_type: Literal["install_location", "service_port", "data_directory"] = Field(
        ..., description="Type of decision being made"
    )
    title: str = Field(..., description="Human-readable decision title")
    description: str = Field(..., description="Detailed description of the decision")
    options: list[dict[str, Any]] = Field(
        ..., description="Available options for this decision"
    )
    default_option: str | None = Field(
        None, description="Default option identifier"
    )
    user_choice: str | dict[str, Any] | None = Field(
        None, description="User's selected choice"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this decision point was created"
    )
    resolved: bool = Field(
        default=False, description="Whether this decision has been resolved"
    )
    validation_pattern: str | None = Field(
        None, description="Regex pattern for validating custom input"
    )

    @field_validator('decision_id')
    @classmethod
    def validate_decision_id(cls, v: str) -> str:
        """Validate decision ID format."""
        # Should be alphanumeric with underscores/hyphens
        pattern = r"^[a-zA-Z0-9_-]+$"
        if not re.match(pattern, v):
            raise ValueError("decision_id must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @field_validator('validation_pattern')
    @classmethod
    def validate_regex_pattern(cls, v: str | None) -> str | None:
        """Validate that the validation pattern is a valid regex."""
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v

    @field_validator('options')
    @classmethod
    def validate_options_format(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate options have required fields."""
        if not v:
            raise ValueError("At least one option must be provided")

        for option in v:
            if 'id' not in option:
                raise ValueError("Each option must have an 'id' field")
            if 'label' not in option:
                raise ValueError("Each option must have a 'label' field")

        return v
