"""Upload operation models for tracking file uploads from various sources."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UploadSourceType(Enum):
    """Upload source type enumeration."""
    LOCAL = "local"
    FTP = "ftp"
    SFTP = "sftp"
    SMB = "smb"
    HTTP = "http"
    HTTPS = "https"


class UploadStatus(Enum):
    """Upload operation status enumeration."""
    INITIATED = "initiated"
    VALIDATING = "validating"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    REJECTED = "rejected"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class ConflictResolution(Enum):
    """File conflict resolution strategy."""
    ASK = "ask"
    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"


class UploadSource(BaseModel):
    """
    Upload source configuration with authentication and connection parameters.

    Represents a source location from which files can be uploaded, including
    credentials and connection parameters for network sources.
    """

    type: UploadSourceType = Field(..., description="Source type (local, FTP, SFTP, etc.)")
    location: str = Field(..., min_length=1, description="Source path, URL, or connection string")
    credentials: dict[str, Any] | None = Field(default=None, description="Authentication credentials")
    connection_params: dict[str, Any] | None = Field(default=None, description="Additional connection parameters")
    last_accessed: datetime | None = Field(default=None, description="Last successful access time")
    success_count: int = Field(default=0, description="Number of successful operations")
    failure_count: int = Field(default=0, description="Number of failed operations")

    model_config = ConfigDict(
        use_enum_values=False,
        validate_assignment=True
    )

    @field_validator('location')
    @classmethod
    def validate_location_not_empty(cls, v):
        """Validate location is not empty."""
        if not v or not v.strip():
            raise ValueError("Location cannot be empty")
        return v.strip()

    @model_validator(mode='after')
    def validate_source_configuration(self) -> 'UploadSource':
        """Validate location format and credentials based on source type."""
        source_type = self.type

        # Validate location format based on source type
        if source_type == UploadSourceType.LOCAL:
            # Local paths can be relative or absolute - just ensure not empty
            pass

        elif source_type in [UploadSourceType.HTTP, UploadSourceType.HTTPS]:
            # URL validation
            if not (self.location.startswith('http://') or self.location.startswith('https://')):
                raise ValueError("HTTP/HTTPS URLs must start with http:// or https://")

        elif source_type == UploadSourceType.FTP:
            # FTP URL validation
            if not (self.location.startswith('ftp://') or '/' in self.location):
                raise ValueError("FTP location must be a URL or host/path format")

        elif source_type == UploadSourceType.SFTP:
            # SFTP can be URL or host:path format
            if not (self.location.startswith('sftp://') or ':' in self.location or '/' in self.location):
                raise ValueError("SFTP location must be URL or host:path format")

        elif source_type == UploadSourceType.SMB:
            # SMB path validation
            if not (self.location.startswith('\\\\') or self.location.startswith('smb://') or '/' in self.location):
                raise ValueError("SMB location must be UNC path or smb:// URL")

        # Validate credentials based on source type
        if source_type == UploadSourceType.LOCAL:
            if self.credentials:
                raise ValueError("Local sources do not require credentials")

        # Network sources may need credentials
        if self.credentials and source_type in [UploadSourceType.FTP, UploadSourceType.SFTP, UploadSourceType.SMB]:
            if 'username' in self.credentials and not isinstance(self.credentials['username'], str):
                raise ValueError("Username must be a string")

            if 'password' in self.credentials and not isinstance(self.credentials['password'], str):
                raise ValueError("Password must be a string")

        return self

    def get_display_location(self) -> str:
        """Get location string safe for display (without credentials)."""
        if self.type == UploadSourceType.LOCAL:
            return self.location

        # For network sources, mask credentials if present in URL
        location = self.location
        if '://' in location and '@' in location:
            # Extract and mask credentials from URL
            protocol, rest = location.split('://', 1)
            if '@' in rest:
                creds, host_path = rest.split('@', 1)
                return f"{protocol}://***@{host_path}"

        return location

    def requires_authentication(self) -> bool:
        """Check if source type requires authentication."""
        return self.type in [UploadSourceType.FTP, UploadSourceType.SFTP, UploadSourceType.SMB]

    def record_success(self) -> None:
        """Record successful operation."""
        self.success_count += 1
        self.last_accessed = datetime.now(timezone.utc)

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1

    def get_reliability_score(self) -> float:
        """Get reliability score (0.0 to 1.0) based on success/failure ratio."""
        total_operations = self.success_count + self.failure_count
        if total_operations == 0:
            return 1.0  # No operations yet, assume reliable
        return self.success_count / total_operations

    @classmethod
    def parse(cls, source_str: str) -> 'UploadSource':
        """Parse a source string and detect its type."""
        source_str = source_str.strip()

        # Detect source type based on string pattern
        if source_str.startswith('http://'):
            source_type = UploadSourceType.HTTP
        elif source_str.startswith('https://'):
            source_type = UploadSourceType.HTTPS
        elif source_str.startswith('ftp://'):
            source_type = UploadSourceType.FTP
        elif source_str.startswith('sftp://'):
            source_type = UploadSourceType.SFTP
        elif source_str.startswith('smb://') or source_str.startswith('\\\\'):
            source_type = UploadSourceType.SMB
        else:
            # Default to local for file paths
            source_type = UploadSourceType.LOCAL

        return cls(type=source_type, location=source_str)


class UploadOperation(BaseModel):
    """
    Upload operation tracking with progress and status information.

    Tracks the state and progress of file upload operations from various sources.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique operation identifier")
    box_id: str = Field(..., description="Target box identifier")
    source: UploadSource = Field(..., description="Upload source configuration")
    status: UploadStatus = Field(default=UploadStatus.INITIATED, description="Current operation status")

    # Progress tracking
    files_total: int = Field(default=0, description="Total number of files to upload")
    files_processed: int = Field(default=0, description="Number of files processed")
    files_succeeded: int = Field(default=0, description="Number of files successfully uploaded")
    files_failed: int = Field(default=0, description="Number of files that failed")
    files_skipped: int = Field(default=0, description="Number of files skipped")

    bytes_total: int = Field(default=0, description="Total bytes to upload")
    bytes_processed: int = Field(default=0, description="Bytes processed so far")

    # Current operation details
    current_file: str | None = Field(default=None, description="Currently processing file")
    current_stage: str = Field(default="initiating", description="Current processing stage")

    # Timing information
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Operation start time")
    completed_at: datetime | None = Field(default=None, description="Operation completion time")
    estimated_completion: datetime | None = Field(default=None, description="Estimated completion time")

    # Configuration
    recursive: bool = Field(default=False, description="Recursive directory upload")
    exclude_patterns: list[str] = Field(default_factory=list, description="File exclusion patterns")
    conflict_resolution: ConflictResolution = Field(default=ConflictResolution.ASK, description="Conflict resolution strategy")
    dry_run: bool = Field(default=False, description="Dry run mode (no actual uploads)")

    # Results and errors
    errors: list[dict[str, Any]] = Field(default_factory=list, description="Error details")
    warnings: list[dict[str, Any]] = Field(default_factory=list, description="Warning messages")
    uploaded_files: list[dict[str, Any]] = Field(default_factory=list, description="Successfully uploaded files")

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True
    )

    @model_validator(mode='after')
    def validate_progress_consistency(self) -> 'UploadOperation':
        """Validate progress metrics are consistent."""
        # Validate files processed doesn't exceed total
        if self.files_processed > self.files_total and self.files_total > 0:
            raise ValueError("files_processed cannot exceed files_total")

        # Validate bytes processed doesn't exceed total
        if self.bytes_processed > self.bytes_total and self.bytes_total > 0:
            raise ValueError("bytes_processed cannot exceed bytes_total")

        return self

    def get_progress_percentage(self) -> float:
        """Get overall progress percentage (0.0 to 100.0)."""
        if self.files_total == 0:
            return 0.0
        return (self.files_processed / self.files_total) * 100.0

    def get_bytes_progress_percentage(self) -> float:
        """Get bytes progress percentage (0.0 to 100.0)."""
        if self.bytes_total == 0:
            return 0.0
        return (self.bytes_processed / self.bytes_total) * 100.0

    def get_estimated_remaining_time(self) -> float | None:
        """Get estimated remaining time in seconds."""
        if self.files_processed == 0 or self.status not in [UploadStatus.DOWNLOADING, UploadStatus.PROCESSING]:
            return None

        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        if elapsed == 0:
            return None

        rate = self.files_processed / elapsed
        if rate == 0:
            return None

        remaining_files = self.files_total - self.files_processed
        return remaining_files / rate

    def update_progress(self, current_file: str | None = None, stage: str | None = None) -> None:
        """Update current progress information."""
        if current_file is not None:
            self.current_file = current_file
        if stage is not None:
            self.current_stage = stage

        # Update estimated completion
        remaining_time = self.get_estimated_remaining_time()
        if remaining_time is not None:
            self.estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=remaining_time)

    def record_file_success(self, filename: str, file_size: int, metadata: dict[str, Any] | None = None) -> None:
        """Record successful file upload."""
        self.files_succeeded += 1
        self.files_processed += 1
        self.bytes_processed += file_size

        file_record = {
            'filename': filename,
            'size': file_size,
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata or {}
        }
        self.uploaded_files.append(file_record)

    def record_file_failure(self, filename: str, error: str, error_code: str | None = None) -> None:
        """Record failed file upload."""
        self.files_failed += 1
        self.files_processed += 1

        error_record = {
            'filename': filename,
            'error': error,
            'error_code': error_code,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.errors.append(error_record)

    def record_file_skip(self, filename: str, reason: str) -> None:
        """Record skipped file."""
        self.files_skipped += 1
        self.files_processed += 1

        warning_record = {
            'filename': filename,
            'reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.warnings.append(warning_record)

    def complete_operation(self, status: UploadStatus) -> None:
        """Mark operation as complete with final status."""
        self.status = status
        self.completed_at = datetime.now(timezone.utc)
        self.current_file = None

        # Update source statistics
        if status == UploadStatus.COMPLETE:
            self.source.record_success()
        else:
            self.source.record_failure()

    def get_summary(self) -> dict[str, Any]:
        """Get operation summary."""
        duration = None
        if self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()

        return {
            'operation_id': self.id,
            'box_id': self.box_id,
            'source_type': self.source.type.value,
            'source_location': self.source.get_display_location(),
            'status': self.status.value,
            'progress': {
                'files_total': self.files_total,
                'files_processed': self.files_processed,
                'files_succeeded': self.files_succeeded,
                'files_failed': self.files_failed,
                'files_skipped': self.files_skipped,
                'bytes_total': self.bytes_total,
                'bytes_processed': self.bytes_processed,
                'percentage': self.get_progress_percentage()
            },
            'timing': {
                'started_at': self.started_at.isoformat(),
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'duration_seconds': duration,
                'estimated_remaining': self.get_estimated_remaining_time()
            },
            'results': {
                'errors': len(self.errors),
                'warnings': len(self.warnings),
                'uploaded_files': len(self.uploaded_files)
            }
        }

    def is_active(self) -> bool:
        """Check if operation is currently active."""
        return self.status in [
            UploadStatus.INITIATED,
            UploadStatus.VALIDATING,
            UploadStatus.DOWNLOADING,
            UploadStatus.PROCESSING,
            UploadStatus.RETRYING
        ]

    def can_be_cancelled(self) -> bool:
        """Check if operation can be cancelled."""
        return self.is_active() and self.status != UploadStatus.VALIDATING

    def __str__(self) -> str:
        """String representation of upload operation."""
        return (f"UploadOperation(id='{self.id[:8]}...', status={self.status.value}, "
                f"progress={self.files_processed}/{self.files_total})")

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"UploadOperation(id='{self.id}', box_id='{self.box_id}', "
                f"status={self.status.value}, source_type={self.source.type.value})")


# Import timedelta for time calculations
from datetime import timedelta
