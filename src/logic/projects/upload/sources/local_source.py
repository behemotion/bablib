"""
Local file system upload source handler

Handles uploading files from the local file system including:
- Single file uploads
- Directory uploads (recursive and non-recursive)
- Symbolic link handling
- File filtering and validation
- Progress tracking for large operations
"""

import logging
import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import aiofiles

from src.logic.projects.models.upload import UploadSource, UploadSourceType
from src.logic.projects.models.validation import ValidationResult
from src.logic.projects.upload.sources.base_source import BaseUploadSource

logger = logging.getLogger(__name__)


class LocalSource(BaseUploadSource):
    """Handler for local file system upload sources"""

    def __init__(self):
        super().__init__()
        self.source_type = UploadSourceType.LOCAL

    async def validate_source(self, source: UploadSource) -> ValidationResult:
        """Validate local source accessibility and permissions"""
        try:
            source_path = Path(source.location)

            # Check if path exists
            if not source_path.exists():
                return ValidationResult(
                    valid=False,
                    errors=[f"Path does not exist: {source.location}"],
                    warnings=[]
                )

            # Check read permissions
            if not os.access(source_path, os.R_OK):
                return ValidationResult(
                    valid=False,
                    errors=[f"No read permission for: {source.location}"],
                    warnings=[]
                )

            # Additional checks for directories
            if source_path.is_dir():
                # Check if directory is empty when not recursive
                if not source.recursive and not any(source_path.iterdir()):
                    return ValidationResult(
                        valid=True,
                        errors=[],
                        warnings=[f"Directory is empty: {source.location}"]
                    )

            return ValidationResult(valid=True, errors=[], warnings=[])

        except Exception as e:
            logger.error(f"Error validating local source {source.location}: {e}")
            return ValidationResult(
                valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=[]
            )

    async def list_files(
        self,
        source: UploadSource,
        recursive: bool = False
    ) -> AsyncGenerator[str]:
        """List files available from local source"""
        try:
            source_path = Path(source.location)

            if source_path.is_file():
                # Single file
                yield str(source_path)
                return

            if source_path.is_dir():
                # Directory listing
                if recursive:
                    # Recursive directory traversal
                    for root, dirs, files in os.walk(source_path):
                        root_path = Path(root)

                        # Apply exclusion patterns
                        if source.exclude_patterns:
                            files = self._filter_files(files, source.exclude_patterns)
                            dirs[:] = self._filter_directories(dirs, source.exclude_patterns)

                        for file in files:
                            file_path = root_path / file

                            # Handle symbolic links
                            if file_path.is_symlink():
                                if source.follow_symlinks:
                                    if file_path.exists():  # Valid symlink target
                                        yield str(file_path)
                                    else:
                                        logger.warning(f"Broken symlink: {file_path}")
                                # Skip symlinks if not following them
                                continue

                            if file_path.is_file():
                                yield str(file_path)
                else:
                    # Non-recursive directory listing
                    for item in source_path.iterdir():
                        if item.is_file():
                            # Apply exclusion patterns
                            if source.exclude_patterns:
                                if self._matches_exclusion_pattern(item.name, source.exclude_patterns):
                                    continue

                            # Handle symbolic links
                            if item.is_symlink():
                                if source.follow_symlinks and item.exists():
                                    yield str(item)
                                continue

                            yield str(item)

        except Exception as e:
            logger.error(f"Error listing files from {source.location}: {e}")
            raise

    async def download_file(
        self,
        source: UploadSource,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> bool:
        """Copy file from local source to destination (essentially a local copy)"""
        try:
            source_file = Path(remote_path)
            dest_file = Path(local_path)

            # Ensure destination directory exists
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Get file size for progress tracking
            file_size = source_file.stat().st_size
            bytes_copied = 0

            # Copy file with progress tracking
            async with aiofiles.open(source_file, 'rb') as src:
                async with aiofiles.open(dest_file, 'wb') as dst:
                    chunk_size = 64 * 1024  # 64KB chunks

                    while True:
                        chunk = await src.read(chunk_size)
                        if not chunk:
                            break

                        await dst.write(chunk)
                        bytes_copied += len(chunk)

                        # Report progress
                        if progress_callback:
                            progress_callback(bytes_copied, file_size)

            logger.debug(f"Successfully copied {remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Error copying file {remote_path} to {local_path}: {e}")
            return False

    async def get_file_info(
        self,
        source: UploadSource,
        remote_path: str
    ) -> dict[str, Any]:
        """Get file metadata from local file system"""
        try:
            file_path = Path(remote_path)

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {remote_path}")

            stat = file_path.stat()

            # Detect MIME type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"

            file_info = {
                "filename": file_path.name,
                "file_size": stat.st_size,
                "mime_type": mime_type,
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime,
                "is_symlink": file_path.is_symlink(),
                "is_directory": file_path.is_dir(),
                "permissions": oct(stat.st_mode)[-3:],
                "owner_uid": stat.st_uid,
                "group_gid": stat.st_gid
            }

            # Additional info for symlinks
            if file_path.is_symlink():
                try:
                    target = file_path.readlink()
                    file_info["symlink_target"] = str(target)
                    file_info["symlink_valid"] = file_path.exists()
                except Exception as e:
                    logger.warning(f"Could not read symlink target for {remote_path}: {e}")

            return file_info

        except Exception as e:
            logger.error(f"Error getting file info for {remote_path}: {e}")
            raise

    def _filter_files(self, files: list[str], exclude_patterns: list[str]) -> list[str]:
        """Filter files based on exclusion patterns"""
        filtered_files = []
        for file in files:
            if not self._matches_exclusion_pattern(file, exclude_patterns):
                filtered_files.append(file)
        return filtered_files

    def _filter_directories(self, dirs: list[str], exclude_patterns: list[str]) -> list[str]:
        """Filter directories based on exclusion patterns"""
        return [d for d in dirs if not self._matches_exclusion_pattern(d, exclude_patterns)]

    def _matches_exclusion_pattern(self, filename: str, patterns: list[str]) -> bool:
        """Check if filename matches any exclusion pattern"""
        import fnmatch

        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    async def test_connection(self, source: UploadSource) -> bool:
        """Test local source accessibility"""
        validation_result = await self.validate_source(source)
        return validation_result.valid

    async def get_total_size(self, source: UploadSource) -> int:
        """Calculate total size of files to be uploaded"""
        total_size = 0

        async for file_path in self.list_files(source, source.recursive):
            try:
                file_info = await self.get_file_info(source, file_path)
                total_size += file_info["file_size"]
            except Exception as e:
                logger.warning(f"Could not get size for {file_path}: {e}")
                continue

        return total_size

    async def count_files(self, source: UploadSource) -> int:
        """Count total number of files to be uploaded"""
        count = 0

        async for _ in self.list_files(source, source.recursive):
            count += 1

        return count

    def supports_resume(self) -> bool:
        """Local source doesn't need resume capability"""
        return False

    def requires_authentication(self) -> bool:
        """Local source doesn't require authentication"""
        return False
