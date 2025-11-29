"""Storage and data document models for file tracking and metadata."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .upload import UploadSource
from .validation import ValidationResult, FileValidationResult


class StorageFile(BaseModel):
    """
    Represents uploaded files in storage projects with metadata and inventory tracking.

    Storage files maintain comprehensive metadata for search, organization, and integrity verification.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique file identifier")
    box_id: str = Field(..., description="Parent box identifier")
    filename: str = Field(..., min_length=1, description="Original filename")
    file_path: str = Field(..., description="Local storage path")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="Detected MIME type")
    upload_source: UploadSource = Field(..., description="Source of the upload")
    upload_date: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")
    checksum: str = Field(..., description="SHA256 checksum for integrity verification")
    tags: list[str] = Field(default_factory=list, description="User-assigned tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="File-specific metadata")

    # Computed fields
    file_extension: str | None = Field(default=None, description="File extension")
    is_compressed: bool = Field(default=False, description="Whether file is compressed")
    compression_ratio: float | None = Field(default=None, description="Compression ratio if compressed")

    # Access tracking
    last_accessed: datetime | None = Field(default=None, description="Last access timestamp")
    access_count: int = Field(default=0, description="Number of times accessed")

    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Validate filename format."""
        if not v.strip():
            raise ValueError("Filename cannot be empty or whitespace")

        # Check for problematic characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"Filename cannot contain '{char}'")

        # Check for reserved names (Windows compatibility)
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
        name_without_ext = v.split('.')[0].upper()
        if name_without_ext in reserved_names:
            raise ValueError(f"Filename '{v}' uses reserved name")

        return v.strip()

    @field_validator('checksum')
    @classmethod
    def validate_checksum(cls, v):
        """Validate SHA256 checksum format."""
        if not v:
            raise ValueError("Checksum cannot be empty")

        if len(v) != 64:
            raise ValueError("Checksum must be 64 characters (SHA256)")

        try:
            int(v, 16)  # Verify it's a valid hex string
        except ValueError:
            raise ValueError("Checksum must be a valid hexadecimal string")

        return v.lower()

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate and normalize tags."""
        if not v:
            return []

        normalized_tags = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("All tags must be strings")

            # Normalize tag
            normalized = tag.strip().lower()
            if not normalized:
                continue

            # Validate tag format
            if len(normalized) > 50:
                raise ValueError("Tags cannot exceed 50 characters")

            if any(char in normalized for char in [',', ';', ':', '|']):
                raise ValueError("Tags cannot contain separators (, ; : |)")

            if normalized not in normalized_tags:
                normalized_tags.append(normalized)

        return normalized_tags

    @model_validator(mode='after')
    def set_file_extension(self) -> 'StorageFile':
        """Extract and set file extension."""
        if self.filename and '.' in self.filename and not self.file_extension:
            self.file_extension = self.filename.split('.')[-1].lower()
        return self

    @classmethod
    def from_upload(
        cls,
        box_id: str,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        upload_source: UploadSource,
        checksum: str | None = None
    ) -> 'StorageFile':
        """Create StorageFile from upload information."""
        # Generate checksum if not provided
        if checksum is None:
            checksum = cls.calculate_file_checksum(file_path)

        return cls(
            box_id=box_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            upload_source=upload_source,
            checksum=checksum
        )

    @staticmethod
    def calculate_file_checksum(file_path: str) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except OSError as e:
            raise ValueError(f"Failed to calculate checksum: {e}")

    def verify_integrity(self) -> bool:
        """Verify file integrity using checksum."""
        try:
            current_checksum = self.calculate_file_checksum(self.file_path)
            return current_checksum == self.checksum
        except ValueError:
            return False

    def add_tags(self, new_tags: list[str]) -> None:
        """Add tags to file."""
        current_tags = set(self.tags)
        for tag in new_tags:
            normalized = tag.strip().lower()
            if normalized and normalized not in current_tags:
                self.tags.append(normalized)

    def remove_tags(self, tags_to_remove: list[str]) -> None:
        """Remove tags from file."""
        normalized_remove = {tag.strip().lower() for tag in tags_to_remove}
        self.tags = [tag for tag in self.tags if tag not in normalized_remove]

    def record_access(self) -> None:
        """Record file access."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

    def get_display_size(self) -> str:
        """Get human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"

    def to_search_index(self) -> dict[str, Any]:
        """Convert to search index format."""
        return {
            'file_id': self.id,
            'filename': self.filename,
            'tags': ' '.join(self.tags),
            'mime_type': self.mime_type,
            'file_extension': self.file_extension or '',
            'upload_date': self.upload_date.isoformat(),
            'metadata': str(self.metadata)
        }


class DataDocument(BaseModel):
    """
    Represents documents processed for vector storage in data projects.

    Data documents are processed into chunks for vector search and retrieval.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique document identifier")
    box_id: str = Field(..., description="Parent box identifier")
    title: str = Field(..., min_length=1, description="Document title or filename")
    content: str = Field(..., description="Processed text content")
    source_path: str = Field(..., description="Original file path")
    upload_source: UploadSource = Field(..., description="Source of the upload")
    processed_date: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    chunk_count: int = Field(default=0, ge=0, description="Number of vector chunks created")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document-specific metadata")

    # Content analysis
    word_count: int = Field(default=0, ge=0, description="Number of words in content")
    character_count: int = Field(default=0, ge=0, description="Number of characters in content")
    language: str | None = Field(default=None, description="Detected language")

    # Processing details
    embedding_model: str | None = Field(default=None, description="Embedding model used")
    chunk_size: int | None = Field(default=None, description="Chunk size used for processing")
    chunk_overlap: int | None = Field(default=None, description="Chunk overlap used")

    # Quality metrics
    processing_success: bool = Field(default=True, description="Whether processing was successful")
    processing_errors: list[str] = Field(default_factory=list, description="Processing errors if any")
    quality_score: float | None = Field(default=None, description="Content quality score (0-1)")

    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        """Validate document title."""
        if not v.strip():
            raise ValueError("Document title cannot be empty or whitespace")
        return v.strip()

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate document content."""
        if not v.strip():
            raise ValueError("Document content cannot be empty or whitespace")
        return v

    @model_validator(mode='after')
    def set_content_metrics(self) -> 'DataDocument':
        """Calculate and set content metrics."""
        if self.content:
            # Set word count
            if not self.word_count:
                self.word_count = len(self.content.split())
            # Set character count
            if not self.character_count:
                self.character_count = len(self.content)
        return self

    @field_validator('quality_score')
    @classmethod
    def validate_quality_score(cls, v):
        """Validate quality score range."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Quality score must be between 0.0 and 1.0")
        return v

    @classmethod
    def from_file(
        cls,
        box_id: str,
        title: str,
        content: str,
        source_path: str,
        upload_source: UploadSource,
        processing_config: dict[str, Any] | None = None
    ) -> 'DataDocument':
        """Create DataDocument from file processing."""
        doc = cls(
            box_id=box_id,
            title=title,
            content=content,
            source_path=source_path,
            upload_source=upload_source
        )

        # Set processing configuration if provided
        if processing_config:
            doc.embedding_model = processing_config.get('embedding_model')
            doc.chunk_size = processing_config.get('chunk_size')
            doc.chunk_overlap = processing_config.get('chunk_overlap')

        return doc

    def create_chunks(self, chunk_size: int, overlap: int = 0) -> list[dict[str, Any]]:
        """Create text chunks for vector processing."""
        if not self.content:
            return []

        chunks = []
        text = self.content
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            # Try to break at word boundaries
            if end < len(text) and chunk_text[-1] != ' ':
                last_space = chunk_text.rfind(' ')
                if last_space > start + chunk_size // 2:  # Only if we don't lose too much
                    end = start + last_space
                    chunk_text = text[start:end]

            chunk = {
                'document_id': self.id,
                'chunk_index': len(chunks),
                'text': chunk_text.strip(),
                'start_char': start,
                'end_char': end,
                'metadata': {
                    'document_title': self.title,
                    'source_path': self.source_path,
                    'chunk_size': len(chunk_text),
                    'document_metadata': self.metadata
                }
            }
            chunks.append(chunk)

            # Move start position with overlap
            start = max(start + chunk_size - overlap, start + 1)
            if start >= len(text):
                break

        self.chunk_count = len(chunks)
        return chunks

    def update_processing_status(self, success: bool, errors: list[str] = None) -> None:
        """Update processing status."""
        self.processing_success = success
        if errors:
            self.processing_errors.extend(errors)

    def calculate_quality_score(self) -> float:
        """Calculate content quality score based on various metrics."""
        score = 1.0

        # Penalize for very short content
        if self.character_count < 100:
            score *= 0.5
        elif self.character_count < 500:
            score *= 0.8

        # Penalize for processing errors
        if self.processing_errors:
            score *= max(0.1, 1.0 - len(self.processing_errors) * 0.1)

        # Penalize for very few chunks
        if self.chunk_count < 2:
            score *= 0.7

        # Bonus for good chunk count
        if 5 <= self.chunk_count <= 50:
            score *= 1.1

        self.quality_score = min(1.0, score)
        return self.quality_score

    def get_summary(self) -> dict[str, Any]:
        """Get document summary."""
        return {
            'id': self.id,
            'title': self.title,
            'source_path': self.source_path,
            'processed_date': self.processed_date.isoformat(),
            'stats': {
                'word_count': self.word_count,
                'character_count': self.character_count,
                'chunk_count': self.chunk_count,
                'quality_score': self.quality_score
            },
            'processing': {
                'success': self.processing_success,
                'errors': len(self.processing_errors),
                'embedding_model': self.embedding_model
            }
        }

    def to_search_result(self, relevance_score: float | None = None) -> dict[str, Any]:
        """Convert to search result format."""
        result = {
            'document_id': self.id,
            'title': self.title,
            'source_path': self.source_path,
            'processed_date': self.processed_date.isoformat(),
            'word_count': self.word_count,
            'chunk_count': self.chunk_count,
            'metadata': self.metadata
        }

        if relevance_score is not None:
            result['relevance_score'] = relevance_score

        return result

    def __str__(self) -> str:
        """String representation of document."""
        return f"DataDocument(title='{self.title}', chunks={self.chunk_count}, words={self.word_count})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"DataDocument(id='{self.id}', title='{self.title}', "
                f"box_id='{self.box_id}', chunk_count={self.chunk_count})")


class FileInventory(BaseModel):
    """
    Searchable index for storage project files with full-text search capabilities.

    Provides efficient search across file metadata, tags, and content.
    """

    file_id: str = Field(..., description="Reference to StorageFile")
    content_text: str | None = Field(default=None, description="Extracted text content for search")
    tags_concat: str = Field(default="", description="Concatenated tags for search")
    search_metadata: str = Field(default="", description="Searchable metadata fields")
    index_date: datetime = Field(default_factory=datetime.utcnow, description="Index creation date")

    # Search optimization
    content_hash: str | None = Field(default=None, description="Hash of content for change detection")
    index_version: int = Field(default=1, description="Index format version")

    model_config = ConfigDict(
        validate_assignment=True
    )

    @classmethod
    def from_storage_file(cls, storage_file: StorageFile, content_text: str | None = None) -> 'FileInventory':
        """Create FileInventory from StorageFile."""
        # Prepare searchable metadata
        metadata_parts = [
            storage_file.filename,
            storage_file.mime_type,
            storage_file.file_extension or '',
            str(storage_file.file_size),
            storage_file.upload_date.strftime('%Y-%m-%d')
        ]

        # Add metadata values
        for key, value in storage_file.metadata.items():
            metadata_parts.append(f"{key}:{value}")

        search_metadata = ' '.join(metadata_parts)

        # Calculate content hash if content provided
        content_hash = None
        if content_text:
            content_hash = hashlib.sha256(content_text.encode()).hexdigest()

        return cls(
            file_id=storage_file.id,
            content_text=content_text or '',
            tags_concat=' '.join(storage_file.tags),
            search_metadata=search_metadata,
            content_hash=content_hash
        )

    def needs_reindex(self, storage_file: StorageFile, current_content: str | None = None) -> bool:
        """Check if file needs reindexing."""
        # Check if tags changed
        current_tags = ' '.join(storage_file.tags)
        if current_tags != self.tags_concat:
            return True

        # Check if content changed
        if current_content and self.content_hash:
            current_hash = hashlib.sha256(current_content.encode()).hexdigest()
            if current_hash != self.content_hash:
                return True

        return False

    def update_from_storage_file(self, storage_file: StorageFile, content_text: str | None = None) -> None:
        """Update inventory from current storage file state."""
        # Update tags
        self.tags_concat = ' '.join(storage_file.tags)

        # Update searchable metadata
        metadata_parts = [
            storage_file.filename,
            storage_file.mime_type,
            storage_file.file_extension or '',
            str(storage_file.file_size),
            storage_file.upload_date.strftime('%Y-%m-%d')
        ]

        for key, value in storage_file.metadata.items():
            metadata_parts.append(f"{key}:{value}")

        self.search_metadata = ' '.join(metadata_parts)

        # Update content if provided
        if content_text is not None:
            self.content_text = content_text
            self.content_hash = hashlib.sha256(content_text.encode()).hexdigest()

        self.index_date = datetime.now(timezone.utc)

    def get_searchable_text(self) -> str:
        """Get all searchable text combined."""
        parts = [
            self.tags_concat,
            self.search_metadata,
            self.content_text or ''
        ]
        return ' '.join(filter(None, parts))

    def __str__(self) -> str:
        """String representation of inventory entry."""
        content_size = len(self.content_text or '')
        return f"FileInventory(file_id='{self.file_id[:8]}...', content_size={content_size})"
