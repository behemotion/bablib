"""ProjectConfig model with hierarchical settings and validation."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .project import ProjectType


class ProjectConfig(BaseModel):
    """
    Project configuration with hierarchical inheritance from global settings.

    Provides type-specific validation and default value management for projects.
    Supports global defaults with project-specific overrides.
    """

    # Base settings (all project types)
    max_file_size: int = Field(default=10485760, description="Maximum file size in bytes (10MB default)")
    allowed_formats: list[str] = Field(default_factory=list, description="Allowed file formats for project")

    # Crawling-specific settings
    crawl_depth: int | None = Field(default=None, description="Maximum crawl depth for web crawling")
    rate_limit: float | None = Field(default=None, description="Rate limit for requests (requests per second)")
    user_agent: str | None = Field(default=None, description="User agent string for web requests")
    follow_redirects: bool | None = Field(default=None, description="Whether to follow HTTP redirects")
    respect_robots_txt: bool | None = Field(default=None, description="Whether to respect robots.txt")

    # Data-specific settings
    chunk_size: int | None = Field(default=None, description="Chunk size for document processing")
    chunk_overlap: int | None = Field(default=None, description="Overlap between chunks")
    embedding_model: str | None = Field(default=None, description="Embedding model for vector storage")
    vector_store_type: str | None = Field(default=None, description="Vector store provider")

    # Storage-specific settings
    enable_compression: bool | None = Field(default=None, description="Enable file compression")
    auto_tagging: bool | None = Field(default=None, description="Enable automatic file tagging")
    full_text_indexing: bool | None = Field(default=None, description="Enable full-text search indexing")
    storage_encryption: bool | None = Field(default=None, description="Enable file encryption")

    # Advanced settings
    concurrent_uploads: int | None = Field(default=None, description="Maximum concurrent upload operations")
    retry_attempts: int | None = Field(default=None, description="Number of retry attempts for failed operations")
    timeout_seconds: int | None = Field(default=None, description="Operation timeout in seconds")

    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

    @field_validator('max_file_size')
    @classmethod
    def validate_max_file_size(cls, v):
        """Validate maximum file size."""
        if v <= 0:
            raise ValueError("max_file_size must be positive")
        if v > 1073741824:  # 1GB
            raise ValueError("max_file_size cannot exceed 1GB")
        return v

    @field_validator('allowed_formats')
    @classmethod
    def validate_allowed_formats(cls, v):
        """Validate allowed formats list."""
        if not v:
            return v

        # Normalize formats to lowercase
        normalized = []
        for fmt in v:
            if not isinstance(fmt, str):
                raise ValueError("All format entries must be strings")
            normalized.append(fmt.lower().strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_formats = []
        for fmt in normalized:
            if fmt not in seen:
                seen.add(fmt)
                unique_formats.append(fmt)

        return unique_formats

    @field_validator('crawl_depth')
    @classmethod
    def validate_crawl_depth(cls, v):
        """Validate crawl depth."""
        if v is not None:
            if not isinstance(v, int) or v < 1 or v > 10:
                raise ValueError("crawl_depth must be an integer between 1 and 10")
        return v

    @field_validator('rate_limit')
    @classmethod
    def validate_rate_limit(cls, v):
        """Validate rate limit."""
        if v is not None:
            if not isinstance(v, (int, float)) or v <= 0:
                raise ValueError("rate_limit must be a positive number")
            if v > 100:
                raise ValueError("rate_limit cannot exceed 100 requests per second")
        return v

    @field_validator('chunk_size')
    @classmethod
    def validate_chunk_size(cls, v):
        """Validate chunk size."""
        if v is not None:
            if not isinstance(v, int) or v < 100 or v > 2000:
                raise ValueError("chunk_size must be an integer between 100 and 2000")
        return v

    @field_validator('chunk_overlap')
    @classmethod
    def validate_chunk_overlap_value(cls, v):
        """Validate chunk overlap value."""
        if v is not None:
            if not isinstance(v, int) or v < 0:
                raise ValueError("chunk_overlap must be a non-negative integer")
        return v

    @model_validator(mode='after')
    def validate_chunk_overlap_size_relationship(self) -> 'ProjectConfig':
        """Validate chunk overlap is less than chunk size."""
        if self.chunk_overlap is not None and self.chunk_size is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError("chunk_overlap must be less than chunk_size")
        return self

    @field_validator('concurrent_uploads')
    @classmethod
    def validate_concurrent_uploads(cls, v):
        """Validate concurrent uploads."""
        if v is not None:
            if not isinstance(v, int) or v < 1 or v > 10:
                raise ValueError("concurrent_uploads must be an integer between 1 and 10")
        return v

    @field_validator('retry_attempts')
    @classmethod
    def validate_retry_attempts(cls, v):
        """Validate retry attempts."""
        if v is not None:
            if not isinstance(v, int) or v < 0 or v > 10:
                raise ValueError("retry_attempts must be an integer between 0 and 10")
        return v

    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout_seconds(cls, v):
        """Validate timeout seconds."""
        if v is not None:
            if not isinstance(v, int) or v < 1 or v > 3600:
                raise ValueError("timeout_seconds must be an integer between 1 and 3600")
        return v

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ProjectConfig':
        """Create ProjectConfig from dictionary."""
        return cls(**data)

    def to_dict(self, exclude_none: bool = True) -> dict[str, Any]:
        """Convert to dictionary, optionally excluding None values."""
        data = self.dict()
        if exclude_none:
            return {k: v for k, v in data.items() if v is not None}
        return data

    def merge_with_global(self, global_config: dict[str, Any]) -> 'ProjectConfig':
        """Merge project config with global defaults."""
        # Start with global config
        merged_data = global_config.copy()

        # Override with project-specific settings (excluding None values)
        project_data = self.to_dict(exclude_none=True)
        merged_data.update(project_data)

        return self.__class__.from_dict(merged_data)

    def get_effective_config(self, project_type: ProjectType, global_config: dict[str, Any]) -> dict[str, Any]:
        """Get effective configuration for a project type."""
        # Start with type-specific defaults
        type_defaults = self.get_type_defaults(project_type)

        # Merge with global config
        merged = {**type_defaults, **global_config}

        # Apply project-specific overrides
        project_overrides = self.to_dict(exclude_none=True)
        merged.update(project_overrides)

        return merged

    @staticmethod
    def get_type_defaults(project_type: ProjectType) -> dict[str, Any]:
        """Get default configuration for project type."""
        defaults = {
            ProjectType.CRAWLING: {
                'max_file_size': 10485760,  # 10MB
                'allowed_formats': ['html', 'pdf', 'txt', 'md', 'rst'],
                'crawl_depth': 3,
                'rate_limit': 1.0,
                'user_agent': 'Bablib/1.0',
                'follow_redirects': True,
                'respect_robots_txt': True,
                'concurrent_uploads': 3,
                'retry_attempts': 3,
                'timeout_seconds': 30
            },
            ProjectType.DATA: {
                'max_file_size': 52428800,  # 50MB
                'allowed_formats': ['pdf', 'docx', 'txt', 'md', 'html', 'json', 'csv', 'xml'],
                'chunk_size': 500,
                'chunk_overlap': 50,
                'embedding_model': 'mxbai-embed-large',
                'vector_store_type': 'sqlite_vec',
                'concurrent_uploads': 5,
                'retry_attempts': 3,
                'timeout_seconds': 60
            },
            ProjectType.STORAGE: {
                'max_file_size': 104857600,  # 100MB
                'allowed_formats': ['*'],  # All formats
                'enable_compression': True,
                'auto_tagging': True,
                'full_text_indexing': True,
                'storage_encryption': False,
                'concurrent_uploads': 5,
                'retry_attempts': 3,
                'timeout_seconds': 120
            }
        }

        return defaults.get(project_type, {})

    def validate_for_type(self, project_type: ProjectType) -> list[str]:
        """Validate configuration for specific project type."""
        errors = []

        # Type-specific validation
        if project_type == ProjectType.CRAWLING:
            errors.extend(self._validate_crawling_config())
        elif project_type == ProjectType.DATA:
            errors.extend(self._validate_data_config())
        elif project_type == ProjectType.STORAGE:
            errors.extend(self._validate_storage_config())

        return errors

    def _validate_crawling_config(self) -> list[str]:
        """Validate crawling-specific configuration."""
        errors = []

        # Required settings for crawling
        if self.crawl_depth is None:
            errors.append("crawl_depth is required for crawling projects")

        if self.rate_limit is None:
            errors.append("rate_limit is required for crawling projects")

        # Format validation
        if self.allowed_formats and 'html' not in self.allowed_formats:
            errors.append("HTML format must be allowed for crawling projects")

        return errors

    def _validate_data_config(self) -> list[str]:
        """Validate data-specific configuration."""
        errors = []

        # Required settings for data projects
        if self.chunk_size is None:
            errors.append("chunk_size is required for data projects")

        if self.embedding_model is None:
            errors.append("embedding_model is required for data projects")

        # Format validation
        if self.allowed_formats and not any(fmt in ['pdf', 'txt', 'md', 'html', 'docx']
                                           for fmt in self.allowed_formats):
            errors.append("At least one document format must be allowed for data projects")

        return errors

    def _validate_storage_config(self) -> list[str]:
        """Validate storage-specific configuration."""
        errors = []

        # Storage projects are flexible, minimal validation needed
        if self.allowed_formats == []:
            errors.append("At least one format must be allowed for storage projects")

        return errors

    def get_incompatible_settings(self, project_type: ProjectType) -> list[str]:
        """Get list of settings that are incompatible with project type."""
        incompatible = []

        if project_type == ProjectType.CRAWLING:
            # Data/storage specific settings not applicable
            if self.chunk_size is not None:
                incompatible.append("chunk_size")
            if self.enable_compression is not None:
                incompatible.append("enable_compression")

        elif project_type == ProjectType.DATA:
            # Crawling/storage specific settings not applicable
            if self.crawl_depth is not None:
                incompatible.append("crawl_depth")
            if self.enable_compression is not None:
                incompatible.append("enable_compression")

        elif project_type == ProjectType.STORAGE:
            # Crawling/data specific settings not applicable
            if self.crawl_depth is not None:
                incompatible.append("crawl_depth")
            if self.chunk_size is not None:
                incompatible.append("chunk_size")

        return incompatible

    def __str__(self) -> str:
        """String representation of config."""
        non_none_settings = {k: v for k, v in self.to_dict().items() if v is not None}
        return f"ProjectConfig({len(non_none_settings)} settings configured)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"ProjectConfig({self.to_dict()})"
