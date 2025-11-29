"""Page data model."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PageStatus(str, Enum):
    """Valid page status values."""
    DISCOVERED = "discovered"
    CRAWLING = "crawling"
    PROCESSED = "processed"
    INDEXED = "indexed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Page(BaseModel):
    """Page model representing a crawled documentation page."""

    id: str = Field(description="Unique page identifier")
    box_id: str = Field(description="Associated box ID")
    session_id: str = Field(description="Associated crawl session ID")
    url: str = Field(description="Page URL")
    status: PageStatus = Field(default=PageStatus.DISCOVERED, description="Current page status")

    # Content
    title: str | None = Field(default=None, description="Page title")
    content_html: str | None = Field(default=None, description="Raw HTML content")
    content_text: str | None = Field(default=None, description="Extracted text content")
    content_hash: str | None = Field(default=None, description="Content hash for deduplication")

    # Metadata
    mime_type: str = Field(default="text/html", description="Content MIME type")
    charset: str = Field(default="utf-8", description="Content character encoding")
    language: str | None = Field(default=None, description="Detected language code")
    size_bytes: int = Field(default=0, ge=0, description="Content size in bytes")

    # Crawl metadata
    crawl_depth: int = Field(ge=0, description="Depth at which page was discovered")
    parent_url: str | None = Field(default=None, description="URL that linked to this page")
    response_code: int | None = Field(default=None, description="HTTP response code")
    response_time_ms: int | None = Field(default=None, description="Response time in milliseconds")

    # Timestamps
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    crawled_at: datetime | None = Field(default=None)
    processed_at: datetime | None = Field(default=None)
    indexed_at: datetime | None = Field(default=None)

    # Error handling
    error_message: str | None = Field(default=None)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)

    # Links and structure
    outbound_links: list[str] = Field(default_factory=list, description="URLs found on this page")
    internal_links: list[str] = Field(default_factory=list, description="Internal links found")
    external_links: list[str] = Field(default_factory=list, description="External links found")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        use_enum_values=True
    )

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must be a valid HTTP/HTTPS URL")
        return v

    @field_validator('response_code')
    @classmethod
    def validate_response_code(cls, v):
        """Validate HTTP response code."""
        if v is not None and (v < 100 or v > 599):
            raise ValueError("Invalid HTTP response code")
        return v

    def generate_content_hash(self) -> str:
        """Generate content hash for deduplication."""
        if not self.content_text:
            return ""

        content = self.content_text.strip().encode('utf-8')
        return hashlib.sha256(content).hexdigest()

    def update_content(
        self,
        title: str | None = None,
        content_html: str | None = None,
        content_text: str | None = None,
        mime_type: str | None = None,
        charset: str | None = None
    ) -> None:
        """Update page content."""
        if title is not None:
            self.title = title
        if content_html is not None:
            self.content_html = content_html
            self.size_bytes = len(content_html.encode('utf-8'))
        if content_text is not None:
            self.content_text = content_text
            self.content_hash = self.generate_content_hash()
        if mime_type is not None:
            self.mime_type = mime_type
        if charset is not None:
            self.charset = charset

        self.status = PageStatus.PROCESSED
        self.processed_at = datetime.now(timezone.utc)

    def mark_crawling(self) -> None:
        """Mark page as currently being crawled."""
        self.status = PageStatus.CRAWLING

    def mark_crawled(
        self,
        response_code: int,
        response_time_ms: int,
        error_message: str | None = None
    ) -> None:
        """Mark page as crawled."""
        self.response_code = response_code
        self.response_time_ms = response_time_ms
        self.crawled_at = datetime.now(timezone.utc)

        if error_message:
            self.error_message = error_message
            self.status = PageStatus.FAILED
        else:
            # Don't change status here - let update_content() set it to PROCESSED
            # This method just records the crawl metadata
            pass

    def mark_indexed(self) -> None:
        """Mark page as indexed."""
        if self.status != PageStatus.PROCESSED:
            raise ValueError(f"Cannot index page in status: {self.status}")

        self.status = PageStatus.INDEXED
        self.indexed_at = datetime.now(timezone.utc)

    def mark_failed(self, error_message: str) -> None:
        """Mark page as failed."""
        self.status = PageStatus.FAILED
        self.error_message = error_message

    def mark_skipped(self, reason: str) -> None:
        """Mark page as skipped."""
        self.status = PageStatus.SKIPPED
        self.error_message = reason

    def can_retry(self) -> bool:
        """Check if page can be retried."""
        return (
            self.status == PageStatus.FAILED and
            self.retry_count < self.max_retries
        )

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1

    def get_domain(self) -> str:
        """Get domain from URL."""
        parsed = urlparse(self.url)
        return parsed.netloc

    def is_internal_link(self, link_url: str, base_domain: str) -> bool:
        """Check if a link is internal to the base domain."""
        try:
            link_domain = urlparse(link_url).netloc
            return link_domain == base_domain or link_domain == ""
        except (ValueError, AttributeError):
            return False

    def categorize_links(self, base_domain: str) -> None:
        """Categorize outbound links as internal or external."""
        self.internal_links = []
        self.external_links = []

        for link in self.outbound_links:
            if self.is_internal_link(link, base_domain):
                self.internal_links.append(link)
            else:
                self.external_links.append(link)

    def get_text_preview(self, max_length: int = 200) -> str:
        """Get preview of text content."""
        if not self.content_text:
            return ""

        text = self.content_text.strip()
        if len(text) <= max_length:
            return text

        return text[:max_length] + "..."

    def is_duplicate(self, other: 'Page') -> bool:
        """Check if this page is a duplicate of another."""
        if not self.content_hash or not other.content_hash:
            return False
        return self.content_hash == other.content_hash

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "box_id": self.box_id,
            "session_id": self.session_id,
            "url": self.url,
            "status": self.status.value,
            "title": self.title,
            "content_html": self.content_html,
            "content_text": self.content_text,
            "content_hash": self.content_hash,
            "mime_type": self.mime_type,
            "charset": self.charset,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "crawl_depth": self.crawl_depth,
            "parent_url": self.parent_url,
            "response_code": self.response_code,
            "response_time_ms": self.response_time_ms,
            "discovered_at": self.discovered_at.isoformat(),
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "outbound_links": self.outbound_links,
            "internal_links": self.internal_links,
            "external_links": self.external_links,
            "metadata": self.metadata,
            "domain": self.get_domain(),
            "text_preview": self.get_text_preview()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Page':
        """Create Page from dictionary."""
        # Handle datetime fields
        datetime_fields = ['discovered_at', 'crawled_at', 'processed_at', 'indexed_at']
        for field in datetime_fields:
            if field in data and data[field] and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))

        # Remove computed fields
        computed_fields = ['domain', 'text_preview']
        for field in computed_fields:
            data.pop(field, None)

        return cls(**data)
