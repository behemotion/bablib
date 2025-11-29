"""Crawl session data model."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CrawlStatus(str, Enum):
    """Valid crawl session status values."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlSession(BaseModel):
    """Crawl session model representing a single crawling operation."""

    id: str = Field(description="Unique session identifier")
    box_id: str = Field(description="Associated box ID")
    status: CrawlStatus = Field(default=CrawlStatus.CREATED, description="Current session status")

    # Session configuration
    crawl_depth: int = Field(description="Maximum depth for this session")
    current_depth: int = Field(default=0, ge=0, description="Current crawling depth")
    current_url: str | None = Field(default=None, description="Currently processing URL")
    user_agent: str = Field(default="Bablib/1.0", description="User agent for requests")
    rate_limit: float = Field(default=1.0, ge=0.1, le=10.0, description="Requests per second")
    timeout: int = Field(default=30, ge=5, le=300, description="Request timeout in seconds")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Progress tracking
    pages_discovered: int = Field(default=0, ge=0)
    pages_crawled: int = Field(default=0, ge=0)
    pages_failed: int = Field(default=0, ge=0)
    pages_skipped: int = Field(default=0, ge=0)
    total_size_bytes: int = Field(default=0, ge=0)
    queue_size: int = Field(default=0, ge=0, description="Current crawl queue size")

    # Error tracking
    error_message: str | None = Field(default=None)
    error_count: int = Field(default=0, ge=0)
    max_errors: int = Field(default=50, ge=1, description="Maximum errors before stopping")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    archived: bool = Field(default=False, description="Whether session is archived")

    model_config = ConfigDict(
        use_enum_values=True
    )

    @field_validator('rate_limit')
    @classmethod
    def validate_rate_limit(cls, v):
        """Validate rate limit is reasonable."""
        if v <= 0:
            raise ValueError("Rate limit must be positive")
        return v

    def start_session(self) -> None:
        """Mark session as started."""
        if self.status != CrawlStatus.CREATED:
            raise ValueError(f"Cannot start session in status: {self.status}")

        self.status = CrawlStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def pause_session(self) -> None:
        """Pause the crawl session."""
        if self.status != CrawlStatus.RUNNING:
            raise ValueError(f"Cannot pause session in status: {self.status}")

        self.status = CrawlStatus.PAUSED
        self.updated_at = datetime.now(timezone.utc)

    def resume_session(self) -> None:
        """Resume the crawl session."""
        if self.status != CrawlStatus.PAUSED:
            raise ValueError(f"Cannot resume session in status: {self.status}")

        self.status = CrawlStatus.RUNNING
        self.updated_at = datetime.now(timezone.utc)

    def complete_session(self) -> None:
        """Mark session as completed."""
        if self.status not in [CrawlStatus.RUNNING, CrawlStatus.PAUSED]:
            raise ValueError(f"Cannot complete session in status: {self.status}")

        self.status = CrawlStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def fail_session(self, error_message: str) -> None:
        """Mark session as failed."""
        self.status = CrawlStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def cancel_session(self) -> None:
        """Cancel the session."""
        if self.status in [CrawlStatus.COMPLETED, CrawlStatus.FAILED]:
            raise ValueError(f"Cannot cancel session in status: {self.status}")

        self.status = CrawlStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_progress(
        self,
        pages_discovered: int | None = None,
        pages_crawled: int | None = None,
        pages_failed: int | None = None,
        pages_skipped: int | None = None,
        total_size_bytes: int | None = None,
        current_depth: int | None = None,
        current_url: str | None = None,
        queue_size: int | None = None
    ) -> None:
        """Update session progress."""
        if pages_discovered is not None:
            self.pages_discovered = pages_discovered
        if pages_crawled is not None:
            self.pages_crawled = pages_crawled
        if pages_failed is not None:
            self.pages_failed = pages_failed
        if pages_skipped is not None:
            self.pages_skipped = pages_skipped
        if total_size_bytes is not None:
            self.total_size_bytes = total_size_bytes
        if current_depth is not None:
            self.current_depth = current_depth
        if current_url is not None:
            self.current_url = current_url
        if queue_size is not None:
            self.queue_size = queue_size

        self.updated_at = datetime.now(timezone.utc)

    def increment_error_count(self) -> bool:
        """Increment error count. Returns True if max errors reached."""
        self.error_count += 1
        self.updated_at = datetime.now(timezone.utc)
        return self.error_count >= self.max_errors

    def get_duration(self) -> float | None:
        """Get session duration in seconds."""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    def get_pages_per_second(self) -> float | None:
        """Calculate pages crawled per second."""
        duration = self.get_duration()
        if not duration or duration <= 0:
            return None

        return self.pages_crawled / duration

    def get_success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total_attempted = self.pages_crawled + self.pages_failed
        if total_attempted == 0:
            return 100.0

        return (self.pages_crawled / total_attempted) * 100

    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status in [CrawlStatus.RUNNING, CrawlStatus.PAUSED]

    def is_completed(self) -> bool:
        """Check if session is completed (successfully or not)."""
        return self.status in [CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.CANCELLED]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "box_id": self.box_id,
            "status": self.status.value,
            "crawl_depth": self.crawl_depth,
            "current_depth": self.current_depth,
            "current_url": self.current_url,
            "user_agent": self.user_agent,
            "rate_limit": self.rate_limit,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat(),
            "pages_discovered": self.pages_discovered,
            "pages_crawled": self.pages_crawled,
            "pages_failed": self.pages_failed,
            "pages_skipped": self.pages_skipped,
            "total_size_bytes": self.total_size_bytes,
            "queue_size": self.queue_size,
            "error_message": self.error_message,
            "error_count": self.error_count,
            "max_errors": self.max_errors,
            "metadata": self.metadata,
            "archived": self.archived,
            "duration_seconds": self.get_duration(),
            "pages_per_second": self.get_pages_per_second(),
            "success_rate": self.get_success_rate()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CrawlSession':
        """Create CrawlSession from dictionary."""
        # Handle datetime fields
        for field in ['created_at', 'started_at', 'completed_at', 'updated_at']:
            if field in data and data[field] and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))

        # Remove computed fields
        for field in ['duration_seconds', 'pages_per_second', 'success_rate']:
            data.pop(field, None)

        return cls(**data)
