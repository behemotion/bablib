"""Installation Profile model for UV/UVX installation feature and setup wizard."""

import os
import platform
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from packaging import version
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InstallationState(Enum):
    """Installation state enumeration for setup wizard"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class SystemInfo(BaseModel):
    """System information for installation validation"""
    model_config = ConfigDict(str_strip_whitespace=True)

    python_version: str = Field(..., description="Current Python version")
    platform: str = Field(..., description="Operating system platform")
    available_memory_gb: float = Field(..., description="Available memory in GB")
    available_disk_gb: float = Field(..., description="Available disk space in GB")
    docker_available: bool = Field(..., description="Docker daemon availability")

    @classmethod
    def detect_current_system(cls) -> "SystemInfo":
        """Detect current system information"""
        import shutil

        import psutil

        # Get Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Get platform
        system_platform = platform.system().lower()

        # Get available memory in GB
        memory = psutil.virtual_memory()
        available_memory_gb = memory.available / (1024**3)

        # Get available disk space in GB
        disk = shutil.disk_usage('/')
        available_disk_gb = disk.free / (1024**3)

        # Check Docker availability
        docker_available = False
        try:
            import docker
            client = docker.from_env()
            client.ping()
            docker_available = True
        except Exception:
            docker_available = False

        return cls(
            python_version=python_version,
            platform=system_platform,
            available_memory_gb=available_memory_gb,
            available_disk_gb=available_disk_gb,
            docker_available=docker_available
        )

    def validate_requirements(self) -> dict[str, bool]:
        """Validate system requirements against installation criteria"""
        return {
            "python_version": self._validate_python_version(),
            "memory": self.available_memory_gb >= 4.0,  # ≥4GB RAM requirement
            "disk": self.available_disk_gb >= 2.0,      # ≥2GB disk requirement
            "docker": self.docker_available             # Docker availability
        }

    def _validate_python_version(self) -> bool:
        """Validate Python version is 3.13+"""
        try:
            version_parts = self.python_version.split('.')
            major = int(version_parts[0])
            minor = int(version_parts[1])

            # Python 3.13+ requirement
            return major > 3 or (major == 3 and minor >= 13)
        except (ValueError, IndexError):
            return False


class InstallationProfile(BaseModel):
    """Complete configuration state during installation process."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True)

    # Core identification and metadata
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for installation session")
    install_method: str = Field(..., description="Installation method (uvx, uv-tool, development)")
    version: str = Field(..., description="Bablib version being installed")
    python_version: str = Field(..., description="Python version (must be 3.13+)")
    uv_version: str = Field(..., description="UV version detected")

    # Installation paths and configuration
    install_path: Path = Field(..., description="Installation directory path")
    is_global: bool = Field(..., description="Whether installed globally via UV tool")
    config_dir: Path = Field(..., description="Configuration directory (XDG compliant)")
    data_dir: Path = Field(..., description="Data directory (XDG compliant)")
    cache_dir: Path = Field(..., description="Cache directory (XDG compliant)")

    # Setup wizard enhancements
    system_info: SystemInfo | None = Field(None, description="System information for validation")
    service_statuses: dict[str, Any] = Field(
        default_factory=dict,
        description="Status of external services (Docker, Qdrant, etc.)"
    )
    installation_state: InstallationState = Field(
        default=InstallationState.NOT_STARTED,
        description="Current installation state"
    )
    configuration_path: Path | None = Field(None, description="Path to configuration file")

    # User configuration and preferences
    user_preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="User-selected configuration options"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Installation start timestamp"
    )
    completed_at: datetime | None = Field(
        None,
        description="Installation completion timestamp"
    )

    # Error tracking
    error_message: str | None = Field(None, description="Error message if installation failed")

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
        try:
            # Use packaging library for robust semantic version validation
            version.Version(v)
        except Exception:
            raise ValueError("version must follow semantic versioning (e.g., '1.0.0')")
        return v

    @field_validator('python_version')
    @classmethod
    def validate_python_version(cls, v: str) -> str:
        """Validate Python version is >= 3.13.0."""
        try:
            parsed_version = version.Version(v)
            min_version = version.Version("3.13.0")
            if parsed_version < min_version:
                raise ValueError("python_version must be >= 3.13.0")
        except Exception as e:
            if "python_version must be >= 3.13.0" in str(e):
                raise
            raise ValueError("python_version must be a valid version string (e.g., '3.13.0')")
        return v

    @field_validator('uv_version')
    @classmethod
    def validate_uv_version(cls, v: str) -> str:
        """Validate UV version is a valid version string."""
        try:
            version.Version(v)
        except Exception:
            raise ValueError("uv_version must be a valid version string")
        return v

    @field_validator('install_path')
    @classmethod
    def validate_install_path_writable(cls, v: Path) -> Path:
        """Validate install path is absolute and writable."""
        if not v.is_absolute():
            raise ValueError("install_path must be absolute")

        # Check if path exists and is writable, or if parent directory exists and is writable
        if v.exists():
            if not os.access(v, os.W_OK):
                raise ValueError("install_path must be writable")
        else:
            parent = v.parent
            if not parent.exists() or not os.access(parent, os.W_OK):
                raise ValueError("install_path parent directory must exist and be writable")

        return v

    @field_validator('config_dir', 'data_dir', 'cache_dir')
    @classmethod
    def validate_directory_creatable(cls, v: Path) -> Path:
        """Validate directories are absolute and can be created."""
        if not v.is_absolute():
            raise ValueError("Directory paths must be absolute")

        # Check if directory exists or can be created
        if v.exists():
            if not v.is_dir():
                raise ValueError(f"Path {v} exists but is not a directory")
            if not os.access(v, os.W_OK):
                raise ValueError(f"Directory {v} is not writable")
        else:
            # Check if we can create the directory by testing parent writability
            try:
                # Find the first existing parent directory
                parent = v
                while parent and not parent.exists():
                    parent = parent.parent

                if not parent or not os.access(parent, os.W_OK):
                    raise ValueError(f"Cannot create directory {v} - parent not writable")

            except Exception as e:
                raise ValueError(f"Directory {v} cannot be created: {str(e)}")

        return v

    @field_validator('completed_at')
    @classmethod
    def validate_completed_after_created(cls, v: datetime | None, info) -> datetime | None:
        """Validate completed_at is after created_at if both are set."""
        if v is not None and hasattr(info, 'data') and 'created_at' in info.data:
            created_at = info.data['created_at']
            if isinstance(created_at, datetime) and v <= created_at:
                raise ValueError("completed_at must be after created_at")
        return v

    def is_completed(self) -> bool:
        """Check if installation is completed."""
        return self.completed_at is not None

    def mark_completed(self) -> None:
        """Mark installation as completed with current timestamp."""
        self.completed_at = datetime.now()

    def get_duration(self) -> float | None:
        """Get installation duration in seconds if completed."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.created_at).total_seconds()

    def to_summary(self) -> dict[str, Any]:
        """Generate a summary of the installation profile."""
        return {
            "id": str(self.id),
            "install_method": self.install_method,
            "version": self.version,
            "python_version": self.python_version,
            "is_global": self.is_global,
            "install_path": str(self.install_path),
            "completed": self.is_completed(),
            "duration_seconds": self.get_duration(),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "installation_state": self.installation_state.value,
            "error_message": self.error_message
        }

    # Setup wizard specific methods
    def start_installation(self) -> None:
        """Mark installation as started"""
        self.installation_state = InstallationState.IN_PROGRESS

    def complete_installation(self) -> None:
        """Mark installation as completed successfully"""
        self.installation_state = InstallationState.COMPLETED
        self.mark_completed()

    def fail_installation(self, error_message: str) -> None:
        """Mark installation as failed with error message"""
        self.installation_state = InstallationState.FAILED
        self.error_message = error_message
        self.mark_completed()

    def rollback_installation(self) -> None:
        """Mark installation as rolled back"""
        self.installation_state = InstallationState.ROLLED_BACK
        self.mark_completed()

    def is_requirements_valid(self) -> bool:
        """Check if system requirements are valid for installation"""
        if not self.system_info:
            return False
        requirements = self.system_info.validate_requirements()
        return all(requirements.values())

    def get_failed_requirements(self) -> list[str]:
        """Get list of failed requirement names"""
        if not self.system_info:
            return ["system_info_missing"]
        requirements = self.system_info.validate_requirements()
        return [name for name, passed in requirements.items() if not passed]

    def update_service_status(self, service_name: str, status: Any) -> None:
        """Update status for a specific service"""
        self.service_statuses[service_name] = status

    def get_service_status(self, service_name: str) -> Any | None:
        """Get status for a specific service"""
        return self.service_statuses.get(service_name)

    def set_configuration_path(self, path: Path) -> None:
        """Set the configuration directory path"""
        self.configuration_path = path

    def detect_system_info(self) -> None:
        """Detect and set current system information"""
        self.system_info = SystemInfo.detect_current_system()


class InstallationStateTransitions:
    """Validates installation state transitions"""

    VALID_TRANSITIONS = {
        InstallationState.NOT_STARTED: [InstallationState.IN_PROGRESS],
        InstallationState.IN_PROGRESS: [
            InstallationState.COMPLETED,
            InstallationState.FAILED,
            InstallationState.ROLLED_BACK
        ],
        InstallationState.FAILED: [InstallationState.ROLLED_BACK, InstallationState.IN_PROGRESS],
        InstallationState.COMPLETED: [],  # Terminal state
        InstallationState.ROLLED_BACK: [InstallationState.IN_PROGRESS]  # Can restart
    }

    @classmethod
    def is_valid_transition(cls, from_state: InstallationState, to_state: InstallationState) -> bool:
        """Check if state transition is valid"""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])

    @classmethod
    def get_valid_next_states(cls, current_state: InstallationState) -> list[InstallationState]:
        """Get list of valid next states from current state"""
        return cls.VALID_TRANSITIONS.get(current_state, [])
