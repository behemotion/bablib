"""BackupManifest model for backup archive metadata."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class BackupManifest(BaseModel):
    """Metadata about a backup archive."""

    backup_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID)"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When backup was created"
    )
    bablib_version: str = Field(
        description="Version of Bablib being uninstalled"
    )
    components_included: list[str] = Field(
        default_factory=list,
        description="What was backed up"
    )
    total_size_bytes: int = Field(
        default=0,
        description="Total size of backed up data"
    )
    compression_ratio: float = Field(
        default=1.0,
        description="Compression achieved (0-1, lower is better)"
    )
    file_count: int = Field(
        default=0,
        description="Number of files in backup"
    )
    container_count: int = Field(
        default=0,
        description="Number of container configs backed up"
    )
    volume_count: int = Field(
        default=0,
        description="Number of volumes backed up"
    )
    directory_count: int = Field(
        default=0,
        description="Number of directories backed up"
    )

    @computed_field
    @property
    def compressed_size_bytes(self) -> int:
        """Calculate compressed size from total size and compression ratio."""
        return int(self.total_size_bytes * self.compression_ratio)

    @computed_field
    @property
    def space_saved_bytes(self) -> int:
        """Calculate space saved by compression."""
        return self.total_size_bytes - self.compressed_size_bytes

    @computed_field
    @property
    def backup_age_days(self) -> float:
        """Calculate age of backup in days."""
        age = datetime.now() - self.created_at
        return age.total_seconds() / 86400  # Convert to days

    def add_component(self, component_type: str, count: int = 1) -> None:
        """Add a component to the backup manifest."""
        component_desc = f"{count} {component_type}" if count != 1 else f"1 {component_type}"
        self.components_included.append(component_desc)

        # Update specific counters
        if component_type == "container" or component_type == "containers":
            self.container_count += count
        elif component_type == "volume" or component_type == "volumes":
            self.volume_count += count
        elif component_type == "directory" or component_type == "directories":
            self.directory_count += count

    def add_files(self, file_count: int, total_size: int) -> None:
        """Add file information to the manifest."""
        self.file_count += file_count
        self.total_size_bytes += total_size

    def set_compression_stats(self, original_size: int, compressed_size: int) -> None:
        """Set compression statistics."""
        if original_size > 0:
            self.total_size_bytes = original_size
            self.compression_ratio = compressed_size / original_size
        else:
            self.compression_ratio = 1.0

    def get_size_display(self, size_bytes: int | None = None) -> str:
        """Get human-readable size display."""
        if size_bytes is None:
            size_bytes = self.compressed_size_bytes

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def get_summary(self) -> dict:
        """Get a summary of the backup."""
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at.isoformat(),
            "age_days": f"{self.backup_age_days:.1f}",
            "bablib_version": self.bablib_version,
            "components": {
                "containers": self.container_count,
                "volumes": self.volume_count,
                "directories": self.directory_count,
                "files": self.file_count
            },
            "size": {
                "original": self.get_size_display(self.total_size_bytes),
                "compressed": self.get_size_display(self.compressed_size_bytes),
                "saved": self.get_size_display(self.space_saved_bytes),
                "compression_ratio": f"{self.compression_ratio:.1%}"
            }
        }

    def to_json_string(self) -> str:
        """Convert manifest to JSON string for storage."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json_string(cls, json_str: str) -> "BackupManifest":
        """Create manifest from JSON string."""
        return cls.model_validate_json(json_str)

    def validate_restore(self) -> tuple[bool, str | None]:
        """Validate if backup can be restored."""
        if self.backup_age_days > 365:
            return False, "Backup is over 1 year old and may be incompatible"

        if self.file_count == 0 and self.container_count == 0:
            return False, "Backup appears to be empty"

        if self.compression_ratio > 0.99:
            return True, "Warning: Backup has minimal compression, may be corrupted"

        return True, None

    class Config:
        """Pydantic configuration."""
        validate_assignment = True
