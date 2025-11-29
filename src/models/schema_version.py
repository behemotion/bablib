"""Schema version tracking for migration management."""

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class SchemaVersion(BaseModel):
    """Schema version tracking for migration management."""

    version: int = Field(..., ge=1, description="Schema version number")
    name: str = Field(..., min_length=1, description="Human-readable version name")
    description: str = Field(..., description="Changes introduced in this version")
    introduced_at: datetime = Field(default_factory=datetime.utcnow, description="When this version was introduced")
    fields_added: list[str] = Field(default_factory=list, description="Fields added in this version")
    fields_removed: list[str] = Field(default_factory=list, description="Fields removed in this version")
    fields_changed: list[str] = Field(default_factory=list, description="Fields modified in this version")

    CURRENT_VERSION: ClassVar[int] = 4

    @classmethod
    def get_current_version(cls) -> int:
        """Get the current schema version."""
        return cls.CURRENT_VERSION

    @classmethod
    def get_version_history(cls) -> list["SchemaVersion"]:
        """Get all schema versions in order."""
        return [
            cls(
                version=1,
                name="Original Crawler Schema",
                description="Initial crawler-focused schema with statistics",
                fields_added=[
                    "total_pages", "total_size_bytes", "successful_pages",
                    "failed_pages", "crawl_depth", "embedding_model",
                    "chunk_size", "chunk_overlap"
                ]
            ),
            cls(
                version=2,
                name="Project Logic Schema",
                description="Type-based project schema with settings",
                fields_added=["type", "settings"],
                fields_removed=["total_pages", "total_size_bytes", "successful_pages", "failed_pages"],
                fields_changed=["metadata"]
            ),
            cls(
                version=3,
                name="Unified Schema",
                description="Combined schema supporting all operations with compatibility tracking",
                fields_added=[
                    "schema_version", "compatibility_status",
                    "statistics", "last_crawl_at", "source_url"
                ],
                fields_changed=["settings", "metadata"]
            ),
            cls(
                version=4,
                name="Shelf/Basket Schema",
                description="Hierarchical project organization with shelfs containing baskets",
                fields_added=[
                    "shelfs table", "baskets table", "shelf_id", "is_current",
                    "last_operation_at", "crawl_depth", "embedding_model",
                    "chunk_size", "chunk_overlap", "total_pages", "total_size_bytes",
                    "successful_pages", "failed_pages"
                ],
                fields_changed=["project organization model"]
            )
        ]

    @classmethod
    def get_version_info(cls, version: int) -> "SchemaVersion | None":
        """Get information about a specific schema version."""
        history = cls.get_version_history()
        for schema_version in history:
            if schema_version.version == version:
                return schema_version
        return None

    @classmethod
    def is_current_version(cls, version: int) -> bool:
        """Check if the given version is the current version."""
        return version == cls.CURRENT_VERSION

    @classmethod
    def is_compatible_version(cls, version: int) -> bool:
        """Check if the given version is compatible with current implementation."""
        return version == cls.CURRENT_VERSION

    @classmethod
    def can_migrate_from(cls, from_version: int) -> bool:
        """Check if migration is possible from the given version."""
        # For now, we only support recreation (no automatic migration)
        return False

    @classmethod
    def requires_recreation(cls, from_version: int) -> bool:
        """Check if recreation is required for the given version."""
        return from_version != cls.CURRENT_VERSION

    def to_summary(self) -> dict[str, Any]:
        """Get a summary of this schema version."""
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "introduced_at": self.introduced_at.isoformat(),
            "is_current": self.version == self.CURRENT_VERSION,
            "changes": {
                "added": self.fields_added,
                "removed": self.fields_removed,
                "changed": self.fields_changed
            }
        }