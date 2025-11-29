"""Query result data model."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryResult(BaseModel):
    """Query result model representing a search result."""

    # Content identification
    id: str = Field(description="Unique result identifier (usually page ID)")
    url: str = Field(description="Source URL of the result")
    title: str = Field(description="Title of the source document")

    # Content
    content: str = Field(description="Relevant content snippet")
    full_content: str | None = Field(default=None, description="Full document content")

    # Relevance scoring
    score: float = Field(ge=0.0, le=1.0, description="Relevance score (0-1)")
    rerank_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Reranking score")

    # Context
    context_before: str | None = Field(default=None, description="Content before the match")
    context_after: str | None = Field(default=None, description="Content after the match")

    # Source metadata
    project: str = Field(description="Source project/shelf name")
    box_id: str = Field(description="Source box ID")
    page_id: str = Field(description="Source page ID")

    # Document metadata
    language: str | None = Field(default=None, description="Document language")
    mime_type: str = Field(default="text/html", description="Document MIME type")
    size_bytes: int = Field(default=0, ge=0, description="Document size in bytes")

    # Timing
    indexed_at: datetime | None = Field(default=None, description="When document was indexed")
    last_updated: datetime | None = Field(default=None, description="When document was last updated")

    # Search metadata
    query_terms: list[str] = Field(default_factory=list, description="Matched query terms")
    match_type: str = Field(default="semantic", description="Type of match (semantic, keyword, hybrid)")
    chunk_id: str | None = Field(default=None, description="Specific chunk ID if applicable")

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict()

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must be a valid HTTP/HTTPS URL")
        return v

    @field_validator('score')
    @classmethod
    def validate_score(cls, v):
        """Validate score is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Score must be between 0.0 and 1.0")
        return v

    @field_validator('rerank_score')
    @classmethod
    def validate_rerank_score(cls, v):
        """Validate rerank score is between 0 and 1."""
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError("Rerank score must be between 0.0 and 1.0")
        return v

    def get_snippet(self, max_length: int = 300) -> str:
        """Get content snippet with optional length limit."""
        content = self.content or ""
        if len(content) <= max_length:
            return content

        # Try to break at word boundary
        truncated = content[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:  # If word boundary is not too far back
            truncated = truncated[:last_space]

        return truncated + "..."

    def get_highlighted_snippet(
        self,
        query_terms: list[str] | None = None,
        highlight_start: str = "<mark>",
        highlight_end: str = "</mark>",
        max_length: int = 300
    ) -> str:
        """Get content snippet with highlighted query terms."""
        content = self.get_snippet(max_length)

        if not query_terms:
            query_terms = self.query_terms

        if not query_terms:
            return content

        # Sort terms by length (longest first) to avoid partial replacements
        sorted_terms = sorted(query_terms, key=len, reverse=True)

        for term in sorted_terms:
            if term.lower() in content.lower():
                # Case-insensitive replacement while preserving original case
                import re
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                content = pattern.sub(f"{highlight_start}{term}{highlight_end}", content)

        return content

    def get_context_window(self, window_size: int = 100) -> str:
        """Get content with surrounding context."""
        parts = []

        if self.context_before:
            before = self.context_before[-window_size:] if len(self.context_before) > window_size else self.context_before
            parts.append(f"...{before}")

        parts.append(self.content)

        if self.context_after:
            after = self.context_after[:window_size] if len(self.context_after) > window_size else self.context_after
            parts.append(f"{after}...")

        return " ".join(parts)

    def get_final_score(self) -> float:
        """Get the final relevance score (rerank score if available, otherwise base score)."""
        return self.rerank_score if self.rerank_score is not None else self.score

    def is_high_quality(self, min_score: float = 0.7, min_content_length: int = 50) -> bool:
        """Check if result meets high quality criteria."""
        return (
            self.get_final_score() >= min_score and
            len(self.content) >= min_content_length and
            bool(self.title.strip())
        )

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the result."""
        self.metadata[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "full_content": self.full_content,
            "score": self.score,
            "rerank_score": self.rerank_score,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "project": self.project,
            "box_id": self.box_id,
            "page_id": self.page_id,
            "language": self.language,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "query_terms": self.query_terms,
            "match_type": self.match_type,
            "chunk_id": self.chunk_id,
            "metadata": self.metadata,
            "final_score": self.get_final_score(),
            "snippet": self.get_snippet(),
            "high_quality": self.is_high_quality()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'QueryResult':
        """Create QueryResult from dictionary."""
        # Handle datetime fields
        for field in ['indexed_at', 'last_updated']:
            if field in data and data[field] and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))

        # Remove computed fields
        computed_fields = ['final_score', 'snippet', 'high_quality']
        for field in computed_fields:
            data.pop(field, None)

        return cls(**data)


class QueryResponse(BaseModel):
    """Response model for search queries."""

    query: str = Field(description="Original search query")
    results: list[QueryResult] = Field(description="Search results")
    total: int = Field(description="Total number of results found")
    limit: int = Field(description="Maximum results returned")
    offset: int = Field(default=0, description="Result offset")

    # Query metadata
    took_ms: int | None = Field(default=None, description="Query execution time in milliseconds")
    strategy: str = Field(default="semantic", description="Search strategy used")
    filters: dict[str, Any] = Field(default_factory=dict, description="Applied filters")

    # Query processing
    processed_query: str | None = Field(default=None, description="Processed/cleaned query")
    decomposed_queries: list[str] = Field(default_factory=list, description="Decomposed sub-queries")

    # Response metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = Field(default=False, description="Whether result was cached")

    model_config = ConfigDict()

    def get_high_quality_results(self, min_score: float = 0.7) -> list[QueryResult]:
        """Get only high quality results."""
        return [r for r in self.results if r.is_high_quality(min_score=min_score)]

    def get_results_by_project(self) -> dict[str, list[QueryResult]]:
        """Group results by project."""
        projects = {}
        for result in self.results:
            if result.project not in projects:
                projects[result.project] = []
            projects[result.project].append(result)
        return projects

    def get_top_results(self, count: int = 5) -> list[QueryResult]:
        """Get top N results by final score."""
        return sorted(self.results, key=lambda r: r.get_final_score(), reverse=True)[:count]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "took_ms": self.took_ms,
            "strategy": self.strategy,
            "filters": self.filters,
            "processed_query": self.processed_query,
            "decomposed_queries": self.decomposed_queries,
            "timestamp": self.timestamp.isoformat(),
            "cache_hit": self.cache_hit,
            "has_results": len(self.results) > 0,
            "projects": list(self.get_results_by_project().keys())
        }
