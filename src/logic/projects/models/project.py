"""Project entity model with type definitions and validation."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectType(Enum):
    """Project type enumeration defining behavior and capabilities."""
    CRAWLING = "crawling"
    DATA = "data"
    STORAGE = "storage"


class ProjectStatus(Enum):
    """Project status enumeration for lifecycle management."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PROCESSING = "processing"


class Project(BaseModel):
    """
    Core project entity representing a work unit with type-specific behavior.

    Each project has a unique identifier, name, type, and settings that
    determine its behavior and capabilities.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique project identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable project name")
    type: ProjectType = Field(..., description="Project type determining behavior")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE, description="Current project status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Project creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    settings: dict[str, Any] = Field(default_factory=dict, description="Type-specific project settings")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional project metadata")

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate project name format."""
        if not v.strip():
            raise ValueError("Project name cannot be empty or whitespace")

        # Check for invalid characters that could cause filesystem issues
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"Project name cannot contain '{char}'")

        return v.strip()

    @field_validator('settings')
    @classmethod
    def validate_settings(cls, v, info):
        """Validate settings are appropriate for project type."""
        # Handle both Pydantic ValidationInfo and plain dict
        if hasattr(info, 'data'):
            data = info.data
        elif isinstance(info, dict):
            data = info
        else:
            return v

        if 'type' not in data:
            return v

        project_type = data['type']

        # Type-specific validation
        if project_type == ProjectType.CRAWLING:
            cls._validate_crawling_settings(v)
        elif project_type == ProjectType.DATA:
            cls._validate_data_settings(v)
        elif project_type == ProjectType.STORAGE:
            cls._validate_storage_settings(v)

        return v

    @staticmethod
    def _validate_crawling_settings(settings: dict[str, Any]) -> None:
        """Validate crawling project settings."""
        if 'crawl_depth' in settings:
            depth = settings['crawl_depth']
            if not isinstance(depth, int) or depth < 1 or depth > 10:
                raise ValueError("crawl_depth must be an integer between 1 and 10")

        if 'rate_limit' in settings:
            rate = settings['rate_limit']
            if not isinstance(rate, (int, float)) or rate <= 0:
                raise ValueError("rate_limit must be a positive number")

    @staticmethod
    def _validate_data_settings(settings: dict[str, Any]) -> None:
        """Validate data project settings."""
        if 'chunk_size' in settings:
            chunk_size = settings['chunk_size']
            if not isinstance(chunk_size, int) or chunk_size < 100 or chunk_size > 2000:
                raise ValueError("chunk_size must be an integer between 100 and 2000")

        if 'embedding_model' in settings:
            model = settings['embedding_model']
            if not isinstance(model, str) or not model.strip():
                raise ValueError("embedding_model must be a non-empty string")

    @staticmethod
    def _validate_storage_settings(settings: dict[str, Any]) -> None:
        """Validate storage project settings."""
        if 'enable_compression' in settings:
            if not isinstance(settings['enable_compression'], bool):
                raise ValueError("enable_compression must be a boolean")

        if 'auto_tagging' in settings:
            if not isinstance(settings['auto_tagging'], bool):
                raise ValueError("auto_tagging must be a boolean")

    def update_status(self, status: ProjectStatus) -> None:
        """Update project status and timestamp."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)

    def update_settings(self, new_settings: dict[str, Any]) -> None:
        """Update project settings with validation."""
        # Merge with existing settings
        merged_settings = {**self.settings, **new_settings}

        # Validate merged settings
        self.__class__.validate_settings(merged_settings, {'type': self.type})

        # Update if validation passes
        self.settings = merged_settings
        self.updated_at = datetime.now(timezone.utc)

    def get_project_directory(self) -> str:
        """Get project-specific directory path."""
        import os
        from pathlib import Path

        # Use XDG-compliant data directory
        data_dir = os.environ.get('BABLIB_DATA_DIR',
                                  str(Path.home() / '.local' / 'share' / 'bablib'))
        return str(Path(data_dir) / 'projects' / self.name)

    def get_database_path(self) -> str:
        """Get project-specific database path."""
        from pathlib import Path
        return str(Path(self.get_project_directory()) / f"{self.name}.db")

    def is_compatible_with_operation(self, operation: str) -> bool:
        """Check if project type supports specific operation."""
        compatibility_matrix = {
            ProjectType.CRAWLING: ['crawl', 'search', 'vector_operations'],
            ProjectType.DATA: ['upload', 'search', 'vector_operations', 'document_processing'],
            ProjectType.STORAGE: ['upload', 'download', 'file_management', 'tagging']
        }

        return operation in compatibility_matrix.get(self.type, [])

    def get_default_settings(self) -> dict[str, Any]:
        """Get default settings for project type."""
        defaults = {
            ProjectType.CRAWLING: {
                'crawl_depth': 3,
                'rate_limit': 1.0,
                'user_agent': 'Bablib/1.0',
                'max_file_size': 10485760,  # 10MB
                'allowed_formats': ['html', 'pdf', 'txt', 'md']
            },
            ProjectType.DATA: {
                'chunk_size': 500,
                'chunk_overlap': 50,
                'embedding_model': 'mxbai-embed-large',
                'vector_store_type': 'sqlite_vec',
                'max_file_size': 52428800,  # 50MB
                'allowed_formats': ['pdf', 'docx', 'txt', 'md', 'html', 'json']
            },
            ProjectType.STORAGE: {
                'enable_compression': True,
                'auto_tagging': True,
                'full_text_indexing': True,
                'max_file_size': 104857600,  # 100MB
                'allowed_formats': ['*']  # All formats allowed
            }
        }

        return defaults.get(self.type, {})

    def __str__(self) -> str:
        """String representation of project."""
        return f"Project(name='{self.name}', type={self.type.value}, status={self.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"Project(id='{self.id}', name='{self.name}', type={self.type.value}, "
                f"status={self.status.value}, created_at={self.created_at.isoformat()})")
