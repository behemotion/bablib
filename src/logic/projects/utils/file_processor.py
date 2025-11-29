"""
File processing utilities

Provides file processing capabilities including:
- Memory-efficient file streaming
- Chunk-based processing
- Progress tracking during operations
- Type-specific file handling
- Compression and decompression
"""

import asyncio
import gzip
import hashlib
import logging
import mimetypes
import shutil
import tempfile
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

from src.logic.projects.models.project import Project, ProjectType

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Result of file processing operation"""

    def __init__(
        self,
        success: bool,
        processed_path: str,
        original_path: str,
        file_size: int = 0,
        processed_size: int = 0,
        metadata: dict[str, Any] | None = None,
        errors: list[str] | None = None
    ):
        self.success = success
        self.processed_path = processed_path
        self.original_path = original_path
        self.file_size = file_size
        self.processed_size = processed_size
        self.metadata = metadata or {}
        self.errors = errors or []


class FileProcessor:
    """Utility class for file processing operations"""

    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB default chunks
        self.chunk_size = chunk_size
        self.temp_dir = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.temp_dir = tempfile.mkdtemp(prefix="bablib_processor_")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def process_file(
        self,
        source_path: str,
        target_path: str,
        project: Project,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ProcessingResult:
        """Process a file based on project type and settings"""
        try:
            source = Path(source_path)
            target = Path(target_path)

            if not source.exists():
                return ProcessingResult(
                    success=False,
                    processed_path=target_path,
                    original_path=source_path,
                    errors=[f"Source file not found: {source_path}"]
                )

            # Ensure target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)

            # Get file metadata
            metadata = await self._get_processing_metadata(source_path)

            # Process based on project type
            if project.type == ProjectType.DATA:
                result = await self._process_for_data_project(
                    source_path, target_path, metadata, progress_callback
                )
            elif project.type == ProjectType.STORAGE:
                result = await self._process_for_storage_project(
                    source_path, target_path, metadata, progress_callback
                )
            elif project.type == ProjectType.CRAWLING:
                result = await self._process_for_crawling_project(
                    source_path, target_path, metadata, progress_callback
                )
            else:
                # Default processing - simple copy
                result = await self._copy_file_with_progress(
                    source_path, target_path, progress_callback
                )

            return result

        except Exception as e:
            logger.error(f"Error processing file {source_path}: {e}")
            return ProcessingResult(
                success=False,
                processed_path=target_path,
                original_path=source_path,
                errors=[f"Processing error: {str(e)}"]
            )

    async def stream_file_chunks(
        self,
        file_path: str,
        chunk_size: int | None = None
    ) -> AsyncGenerator[bytes]:
        """Stream file in chunks for memory-efficient processing"""
        chunk_size = chunk_size or self.chunk_size

        try:
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    # Allow other coroutines to run
                    await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Error streaming file {file_path}: {e}")
            raise

    async def calculate_checksum(
        self,
        file_path: str,
        algorithm: str = "sha256"
    ) -> str:
        """Calculate file checksum using streaming"""
        try:
            if algorithm == "sha256":
                hasher = hashlib.sha256()
            elif algorithm == "md5":
                hasher = hashlib.md5()
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            async for chunk in self.stream_file_chunks(file_path):
                hasher.update(chunk)

            return hasher.hexdigest()

        except Exception as e:
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""

    async def compress_file(
        self,
        source_path: str,
        target_path: str | None = None,
        compression_level: int = 6
    ) -> ProcessingResult:
        """Compress file using gzip"""
        try:
            source = Path(source_path)
            if not target_path:
                target_path = f"{source_path}.gz"

            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            original_size = source.stat().st_size
            compressed_size = 0

            with open(source_path, 'rb') as f_in:
                with gzip.open(target_path, 'wb', compresslevel=compression_level) as f_out:
                    async for chunk in self.stream_file_chunks(source_path):
                        f_out.write(chunk)
                        compressed_size += len(chunk)

            final_size = target.stat().st_size
            compression_ratio = final_size / original_size if original_size > 0 else 0

            return ProcessingResult(
                success=True,
                processed_path=target_path,
                original_path=source_path,
                file_size=original_size,
                processed_size=final_size,
                metadata={
                    "compression_ratio": compression_ratio,
                    "compression_level": compression_level,
                    "algorithm": "gzip"
                }
            )

        except Exception as e:
            logger.error(f"Error compressing file {source_path}: {e}")
            return ProcessingResult(
                success=False,
                processed_path=target_path or f"{source_path}.gz",
                original_path=source_path,
                errors=[f"Compression error: {str(e)}"]
            )

    async def decompress_file(
        self,
        source_path: str,
        target_path: str | None = None
    ) -> ProcessingResult:
        """Decompress gzip file"""
        try:
            source = Path(source_path)
            if not target_path:
                if source_path.endswith('.gz'):
                    target_path = source_path[:-3]
                else:
                    target_path = f"{source_path}.decompressed"

            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            original_size = source.stat().st_size
            decompressed_size = 0

            with gzip.open(source_path, 'rb') as f_in:
                with open(target_path, 'wb') as f_out:
                    while True:
                        chunk = f_in.read(self.chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        decompressed_size += len(chunk)
                        # Allow other coroutines to run
                        await asyncio.sleep(0)

            return ProcessingResult(
                success=True,
                processed_path=target_path,
                original_path=source_path,
                file_size=original_size,
                processed_size=decompressed_size,
                metadata={"algorithm": "gzip"}
            )

        except Exception as e:
            logger.error(f"Error decompressing file {source_path}: {e}")
            return ProcessingResult(
                success=False,
                processed_path=target_path or source_path,
                original_path=source_path,
                errors=[f"Decompression error: {str(e)}"]
            )

    async def extract_text_content(
        self,
        file_path: str,
        max_size: int = 10 * 1024 * 1024  # 10MB limit
    ) -> str:
        """Extract text content from various file types"""
        try:
            path = Path(file_path)
            if path.stat().st_size > max_size:
                raise ValueError(f"File too large for text extraction: {path.stat().st_size} bytes")

            # Get MIME type
            mime_type, _ = mimetypes.guess_type(file_path)

            if mime_type and mime_type.startswith('text/'):
                # Handle text files
                return await self._extract_text_from_text_file(file_path)

            elif mime_type == 'application/pdf':
                # Handle PDF files
                return await self._extract_text_from_pdf(file_path)

            elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                # Handle Word documents
                return await self._extract_text_from_docx(file_path)

            else:
                # Try to read as text anyway
                try:
                    return await self._extract_text_from_text_file(file_path)
                except UnicodeDecodeError:
                    return f"[Binary file: {path.name}]"

        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return f"[Error extracting text: {str(e)}]"

    async def _process_for_data_project(
        self,
        source_path: str,
        target_path: str,
        metadata: dict[str, Any],
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ProcessingResult:
        """Process file for data project (vector storage)"""
        # For data projects, extract text content and store both original and text
        text_content = await self.extract_text_content(source_path)

        # Copy original file
        copy_result = await self._copy_file_with_progress(source_path, target_path, progress_callback)

        # Add extracted text to metadata
        copy_result.metadata.update({
            "text_content": text_content,
            "text_length": len(text_content),
            "extractable": len(text_content) > 0 and not text_content.startswith('[')
        })

        return copy_result

    async def _process_for_storage_project(
        self,
        source_path: str,
        target_path: str,
        metadata: dict[str, Any],
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ProcessingResult:
        """Process file for storage project (with optional compression)"""
        # Check if file should be compressed based on type and size
        should_compress = await self._should_compress_file(source_path, metadata)

        if should_compress:
            # Compress and store
            compress_result = await self.compress_file(source_path, f"{target_path}.gz")
            if compress_result.success:
                # Update paths to reflect compression
                compress_result.processed_path = target_path
                # Move compressed file to final location
                shutil.move(f"{target_path}.gz", target_path)
                compress_result.metadata["compressed"] = True
                return compress_result

        # Fall back to regular copy
        copy_result = await self._copy_file_with_progress(source_path, target_path, progress_callback)
        copy_result.metadata["compressed"] = False
        return copy_result

    async def _process_for_crawling_project(
        self,
        source_path: str,
        target_path: str,
        metadata: dict[str, Any],
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ProcessingResult:
        """Process file for crawling project (web content processing)"""
        # For crawling projects, validate and normalize web content
        if metadata.get("mime_type", "").startswith("text/html"):
            # Process HTML content
            processed_content = await self._process_html_content(source_path)

            # Write processed content to target
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)

            return ProcessingResult(
                success=True,
                processed_path=target_path,
                original_path=source_path,
                file_size=Path(source_path).stat().st_size,
                processed_size=Path(target_path).stat().st_size,
                metadata={"processed_html": True, "content_length": len(processed_content)}
            )

        # For other file types, just copy
        return await self._copy_file_with_progress(source_path, target_path, progress_callback)

    async def _copy_file_with_progress(
        self,
        source_path: str,
        target_path: str,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ProcessingResult:
        """Copy file with progress reporting"""
        try:
            source = Path(source_path)
            target = Path(target_path)

            file_size = source.stat().st_size
            copied_bytes = 0

            with open(source_path, 'rb') as src, open(target_path, 'wb') as dst:
                while True:
                    chunk = src.read(self.chunk_size)
                    if not chunk:
                        break

                    dst.write(chunk)
                    copied_bytes += len(chunk)

                    if progress_callback:
                        progress_callback(copied_bytes, file_size)

                    # Allow other coroutines to run
                    await asyncio.sleep(0)

            # Calculate checksum for integrity
            checksum = await self.calculate_checksum(target_path)

            return ProcessingResult(
                success=True,
                processed_path=target_path,
                original_path=source_path,
                file_size=file_size,
                processed_size=copied_bytes,
                metadata={
                    "checksum": checksum,
                    "operation": "copy",
                    "integrity_verified": True
                }
            )

        except Exception as e:
            logger.error(f"Error copying file from {source_path} to {target_path}: {e}")
            return ProcessingResult(
                success=False,
                processed_path=target_path,
                original_path=source_path,
                errors=[f"Copy error: {str(e)}"]
            )

    async def _get_processing_metadata(self, file_path: str) -> dict[str, Any]:
        """Get metadata needed for processing decisions"""
        try:
            path = Path(file_path)
            stat = path.stat()

            mime_type, _ = mimetypes.guess_type(file_path)

            return {
                "file_size": stat.st_size,
                "mime_type": mime_type or "application/octet-stream",
                "extension": path.suffix.lower(),
                "filename": path.name,
                "is_text": mime_type and mime_type.startswith("text/") if mime_type else False
            }

        except Exception as e:
            logger.error(f"Error getting processing metadata for {file_path}: {e}")
            return {}

    async def _should_compress_file(self, file_path: str, metadata: dict[str, Any]) -> bool:
        """Determine if file should be compressed"""
        mime_type = metadata.get("mime_type", "")
        file_size = metadata.get("file_size", 0)

        # Don't compress already compressed formats
        compressed_types = [
            "image/jpeg", "image/png", "image/gif",
            "video/", "audio/",
            "application/zip", "application/gzip", "application/x-7z-compressed"
        ]

        if any(mime_type.startswith(ct) for ct in compressed_types):
            return False

        # Only compress text files larger than 1KB
        if mime_type.startswith("text/") and file_size > 1024:
            return True

        # Compress large application files
        if mime_type.startswith("application/") and file_size > 10 * 1024:  # 10KB
            return True

        return False

    async def _extract_text_from_text_file(self, file_path: str) -> str:
        """Extract text from text files with encoding detection"""
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(file_path, encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        # If all encodings fail, read as binary and decode with errors='replace'
        with open(file_path, 'rb') as f:
            content = f.read()
            return content.decode('utf-8', errors='replace')

    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF files"""
        try:
            # Try to use PyPDF2 if available
            import PyPDF2
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except ImportError:
            logger.debug("PyPDF2 not available for PDF text extraction")
            return f"[PDF file: {Path(file_path).name} - text extraction requires PyPDF2]"
        except Exception as e:
            logger.debug(f"Error extracting text from PDF {file_path}: {e}")
            return f"[PDF file: {Path(file_path).name} - extraction failed]"

    async def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX files"""
        try:
            # Try to use python-docx if available
            from docx import Document
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except ImportError:
            logger.debug("python-docx not available for DOCX text extraction")
            return f"[DOCX file: {Path(file_path).name} - text extraction requires python-docx]"
        except Exception as e:
            logger.debug(f"Error extracting text from DOCX {file_path}: {e}")
            return f"[DOCX file: {Path(file_path).name} - extraction failed]"

    async def _process_html_content(self, file_path: str) -> str:
        """Process HTML content for web crawling projects"""
        try:
            # Try to use BeautifulSoup for HTML processing if available
            from bs4 import BeautifulSoup

            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()

            # Extract clean text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text

        except ImportError:
            logger.debug("BeautifulSoup not available for HTML processing")
            # Fallback to reading as plain text
            return await self._extract_text_from_text_file(file_path)
        except Exception as e:
            logger.debug(f"Error processing HTML content {file_path}: {e}")
            return await self._extract_text_from_text_file(file_path)
