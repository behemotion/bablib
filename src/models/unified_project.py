"""Unified project model consolidating all project schemas."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schema_version import SchemaVersion

# Import both project types and status enums to unify them
from .project import ProjectStatus as CrawlerProjectStatus
from ..logic.projects.models.project import ProjectType, ProjectStatus as LogicProjectStatus


class UnifiedProjectStatus(str, Enum):
    """Unified project status combining both schemas."""
    # From crawler schema
    CREATED = "created"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"

    # From logic schema (mapped to compatible values)
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    # PROCESSING already covered above


class UnifiedProject(BaseModel):
    """
    Unified project model consolidating all project schemas.

    This model combines:
    - Original crawler schema (src/models/project.py)
    - Project logic schema (src/logic/projects/models/project.py)

    Provides full backward compatibility while supporting unified operations.
    """

    # Identity & Schema
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique project identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable project name")
    schema_version: int = Field(default=SchemaVersion.CURRENT_VERSION, description="Schema version for compatibility")

    # Type & Status (from project logic schema)
    type: Optional[ProjectType] = Field(default=None, description="Project type determining behavior")
    status: UnifiedProjectStatus = Field(default=UnifiedProjectStatus.ACTIVE, description="Current project status")

    # Timestamps (from both schemas)
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Project creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    last_crawl_at: Optional[datetime] = Field(default=None, description="Last crawl timestamp")

    # Configuration (type-specific, from project logic)
    settings: dict[str, Any] = Field(default_factory=dict, description="Type-specific project settings")

    # Statistics (operational, from crawler schema)
    statistics: dict[str, Any] = Field(default_factory=dict, description="Operational statistics")

    # Metadata (user-defined, from both schemas)
    metadata: dict[str, Any] = Field(default_factory=dict, description="User-defined metadata")

    # Crawler-specific (optional, from crawler schema)
    source_url: Optional[str] = Field(default=None, description="Base URL for crawling projects")

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate project name format."""
        if not v.strip():
            raise ValueError("Project name cannot be empty or whitespace")

        # Check for invalid characters that could cause filesystem issues
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"Project name cannot contain '{char}'")

        # Only allow alphanumeric, hyphens, underscores, spaces
        import re
        if not re.match(r'^[a-zA-Z0-9\-_ ]+$', v):
            raise ValueError("Project name can only contain letters, numbers, hyphens, underscores, and spaces")

        return v.strip()

    @field_validator('source_url')
    @classmethod
    def validate_source_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate source URL format."""
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError("Source URL must be a valid HTTP/HTTPS URL")
        return v

    @field_validator('schema_version')
    @classmethod
    def validate_schema_version(cls, v: int) -> int:
        """Validate schema version is positive."""
        if v < 1:
            raise ValueError("Schema version must be positive")
        return v

    @field_validator('settings')
    @classmethod
    def validate_settings(cls, v: dict[str, Any], info) -> dict[str, Any]:
        """Validate settings are appropriate for project type."""
        if hasattr(info, 'data') and 'type' in info.data:
            project_type = info.data['type']
            if project_type:
                cls._validate_type_specific_settings(v, project_type)
        return v


    @model_validator(mode='after')
    def validate_statistics_consistency(self) -> 'UnifiedProject':
        """Validate statistics are internally consistent."""
        stats = self.statistics
        if 'total_pages' in stats and 'successful_pages' in stats and 'failed_pages' in stats:
            total = stats.get('total_pages', 0)
            successful = stats.get('successful_pages', 0)
            failed = stats.get('failed_pages', 0)

            if successful + failed > total:
                raise ValueError("Sum of successful and failed pages cannot exceed total pages")

        return self

    @staticmethod
    def _validate_type_specific_settings(settings: dict[str, Any], project_type) -> None:
        """Validate settings are appropriate for project type."""
        # Handle both enum and string types
        type_value = project_type if isinstance(project_type, str) else (project_type.value if hasattr(project_type, 'value') else str(project_type))

        if type_value == 'crawling':
            if 'crawl_depth' in settings:
                depth = settings['crawl_depth']
                if not isinstance(depth, int) or depth < 1 or depth > 10:
                    raise ValueError("crawl_depth must be an integer between 1 and 10")

            if 'rate_limit' in settings:
                rate = settings['rate_limit']
                if not isinstance(rate, (int, float)) or rate <= 0:
                    raise ValueError("rate_limit must be a positive number")

        elif type_value == 'data':
            if 'chunk_size' in settings:
                chunk_size = settings['chunk_size']
                if not isinstance(chunk_size, int) or chunk_size < 100 or chunk_size > 5000:
                    raise ValueError("chunk_size must be an integer between 100 and 5000")

            if 'embedding_model' in settings:
                model = settings['embedding_model']
                if not isinstance(model, str) or not model.strip():
                    raise ValueError("embedding_model must be a non-empty string")

        elif type_value == 'storage':
            if 'enable_compression' in settings:
                if not isinstance(settings['enable_compression'], bool):
                    raise ValueError("enable_compression must be a boolean")

    def update_status(self, status: UnifiedProjectStatus) -> None:
        """Update project status and timestamp."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)

    def update_settings(self, new_settings: dict[str, Any]) -> None:
        """Update project settings with validation."""
        # Merge with existing settings
        merged_settings = {**self.settings, **new_settings}

        # Validate merged settings if type is set
        if self.type:
            self._validate_type_specific_settings(merged_settings, self.type)

        # Update if validation passes
        self.settings = merged_settings
        self.updated_at = datetime.now(timezone.utc)

    def update_statistics(self, **stats) -> None:
        """Update project statistics."""
        # Update statistics dictionary
        self.statistics.update(stats)
        self.updated_at = datetime.now(timezone.utc)

    def is_compatible(self) -> bool:
        """Check if project is compatible with current schema."""
        return True  # All projects are compatible after migration removal

    def allows_modification(self) -> bool:
        """Check if project allows modifications."""
        return True  # All projects allow modification after migration removal

    def needs_recreation(self) -> bool:
        """Check if project needs recreation."""
        return False  # No projects need recreation after migration removal

    def is_ready_for_search(self) -> bool:
        """Check if project is ready for search operations."""
        return self.status in [UnifiedProjectStatus.READY, UnifiedProjectStatus.ACTIVE]

    def is_outdated(self, max_age_hours: int = 24) -> bool:
        """Check if project data is outdated."""
        if not self.last_crawl_at:
            return True

        age = datetime.now(timezone.utc) - self.last_crawl_at
        return age.total_seconds() > (max_age_hours * 3600)

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
        if not self.type:
            return False

        compatibility_matrix = {
            ProjectType.CRAWLING: ['crawl', 'search', 'vector_operations'],
            ProjectType.DATA: ['upload', 'search', 'vector_operations', 'document_processing'],
            ProjectType.STORAGE: ['upload', 'download', 'file_management', 'tagging']
        }

        return operation in compatibility_matrix.get(self.type, [])

    def get_default_settings(self) -> dict[str, Any]:
        """Get default settings for project type."""
        if not self.type:
            return {}

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

    @classmethod
    def from_crawler_project(cls, crawler_project) -> 'UnifiedProject':
        """Create UnifiedProject from crawler schema project."""
        # Map crawler statistics to unified statistics
        statistics = {
            'total_pages': crawler_project.total_pages,
            'total_size_bytes': crawler_project.total_size_bytes,
            'successful_pages': crawler_project.successful_pages,
            'failed_pages': crawler_project.failed_pages,
        }

        # Map crawler settings to unified settings
        settings = {
            'crawl_depth': crawler_project.crawl_depth,
            'embedding_model': crawler_project.embedding_model,
            'chunk_size': crawler_project.chunk_size,
            'chunk_overlap': crawler_project.chunk_overlap,
        }

        # Map status (crawler uses different enum)
        status_mapping = {
            'created': UnifiedProjectStatus.CREATED,
            'crawling': UnifiedProjectStatus.CRAWLING,
            'processing': UnifiedProjectStatus.PROCESSING,
            'indexing': UnifiedProjectStatus.INDEXING,
            'ready': UnifiedProjectStatus.READY,
            'failed': UnifiedProjectStatus.FAILED,
            'archived': UnifiedProjectStatus.ARCHIVED,
        }

        unified_status = status_mapping.get(crawler_project.status.value, UnifiedProjectStatus.ACTIVE)

        return cls(
            id=crawler_project.id,
            name=crawler_project.name,
            schema_version=1,  # Crawler schema was version 1
            type=ProjectType.CRAWLING,  # Infer type from crawler project
            status=unified_status,
            created_at=crawler_project.created_at,
            updated_at=crawler_project.updated_at,
            last_crawl_at=crawler_project.last_crawl_at,
            source_url=crawler_project.source_url,
            settings=settings,
            statistics=statistics,
            metadata=crawler_project.metadata,
        )

    @classmethod
    def from_logic_project(cls, logic_project) -> 'UnifiedProject':
        """Create UnifiedProject from logic schema project."""
        # Map logic status to unified status
        status_mapping = {
            'active': UnifiedProjectStatus.ACTIVE,
            'inactive': UnifiedProjectStatus.INACTIVE,
            'error': UnifiedProjectStatus.ERROR,
            'processing': UnifiedProjectStatus.PROCESSING,
        }

        unified_status = status_mapping.get(logic_project.status.value, UnifiedProjectStatus.ACTIVE)

        return cls(
            id=logic_project.id,
            name=logic_project.name,
            schema_version=2,  # Logic schema was version 2
            type=logic_project.type,
            status=unified_status,
            created_at=logic_project.created_at,
            updated_at=logic_project.updated_at,
            settings=logic_project.settings,
            statistics={},  # Logic schema didn't have statistics
            metadata=logic_project.metadata,
        )

    def to_summary(self) -> dict[str, Any]:
        """Get a summary representation of the project."""
        page_count = None
        if 'total_pages' in self.statistics:
            page_count = self.statistics['total_pages']

        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value if self.type else None,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'page_count': page_count,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "schema_version": self.schema_version,
            "type": self.type.value if self.type else None,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_crawl_at": self.last_crawl_at.isoformat() if self.last_crawl_at else None,
            "source_url": self.source_url,
            "settings": self.settings,
            "statistics": self.statistics,
            "metadata": self.metadata,
            "is_compatible": self.is_compatible(),
            "allows_modification": self.allows_modification(),
            "needs_recreation": self.needs_recreation(),
            "is_outdated": self.is_outdated(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'UnifiedProject':
        """Create UnifiedProject from dictionary."""
        # Handle datetime fields
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        if 'last_crawl_at' in data and data['last_crawl_at']:
            data['last_crawl_at'] = datetime.fromisoformat(data['last_crawl_at'].replace('Z', '+00:00'))

        # Remove computed fields
        for computed_field in ['is_compatible', 'allows_modification', 'needs_recreation', 'is_outdated']:
            data.pop(computed_field, None)

        return cls(**data)

    def __str__(self) -> str:
        """String representation of project."""
        type_str = self.type.value if self.type else "unknown"
        return f"UnifiedProject(name='{self.name}', type={type_str}, status={self.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        type_str = self.type.value if self.type else "unknown"
        return (f"UnifiedProject(id='{self.id}', name='{self.name}', type={type_str}, "
                f"status={self.status.value}, schema_v{self.schema_version})")