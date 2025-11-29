"""UploadManager orchestration service for coordinating file uploads."""

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models.box import Box
from src.models.box_type import BoxType
from ..models.upload import (
    ConflictResolution,
    UploadOperation,
    UploadSource,
    UploadSourceType,
    UploadStatus,
)

logger = logging.getLogger(__name__)


class UploadManager:
    """
    Main upload orchestration service for coordinating file uploads from various sources.

    Manages upload operations, progress tracking, validation, and coordination
    between source handlers and project-specific processing.
    """

    def __init__(self):
        """Initialize UploadManager."""
        self._active_operations: dict[str, UploadOperation] = {}
        self._operation_tasks: dict[str, asyncio.Task] = {}
        self._source_handlers: dict[UploadSourceType, Any] = {}
        self._register_source_handlers()

    def _register_source_handlers(self) -> None:
        """Register upload source handlers."""
        try:
            # Import handlers dynamically to avoid circular imports
            from .sources.ftp_source import FTPSource
            from .sources.http_source import HTTPSource
            from .sources.local_source import LocalSource
            from .sources.sftp_source import SFTPSource
            from .sources.smb_source import SMBSource

            self._source_handlers[UploadSourceType.LOCAL] = LocalSource
            self._source_handlers[UploadSourceType.FTP] = FTPSource
            self._source_handlers[UploadSourceType.SFTP] = SFTPSource
            self._source_handlers[UploadSourceType.SMB] = SMBSource
            self._source_handlers[UploadSourceType.HTTP] = HTTPSource
            self._source_handlers[UploadSourceType.HTTPS] = HTTPSource  # Same handler for HTTP/HTTPS

            logger.debug("Registered upload source handlers")

        except ImportError as e:
            logger.error(f"Failed to import upload source handlers: {e}")

    async def upload_files(
        self,
        box: Box,
        source: UploadSource,
        recursive: bool = False,
        exclude_patterns: list[str] | None = None,
        conflict_resolution: ConflictResolution = ConflictResolution.ASK,
        dry_run: bool = False,
        progress_callback: Callable[[dict[str, Any]], None] | None = None
    ) -> UploadOperation:
        """
        Upload files from source to box.

        Args:
            box: Target box for uploads
            source: Upload source configuration
            recursive: Whether to recursively process directories
            exclude_patterns: File patterns to exclude
            conflict_resolution: How to handle filename conflicts
            dry_run: Whether to perform dry run without actual uploads
            progress_callback: Optional callback for progress updates

        Returns:
            UploadOperation tracking the upload process

        Raises:
            ValueError: If source type is not supported or validation fails
            RuntimeError: If upload initialization fails
        """
        logger.info(f"Starting upload to box {box.name} from {source.type.value} source")

        # Create upload operation
        operation = UploadOperation(
            box_id=box.id,
            source=source,
            recursive=recursive,
            exclude_patterns=exclude_patterns or [],
            conflict_resolution=conflict_resolution,
            dry_run=dry_run
        )

        # Validate upload before starting
        validation_result = await self.validate_upload(box, source)
        if not validation_result.valid:
            operation.status = UploadStatus.REJECTED
            for error in validation_result.errors:
                operation.record_file_failure("validation", error)
            return operation

        # Register operation
        self._active_operations[operation.id] = operation

        # Start upload task
        upload_task = asyncio.create_task(
            self._execute_upload(operation, box, progress_callback)
        )
        self._operation_tasks[operation.id] = upload_task

        return operation

    async def validate_upload(self, box: Box, source: UploadSource) -> 'ValidationResult':
        """
        Validate upload operation before execution.

        Args:
            box: Target box
            source: Upload source

        Returns:
            ValidationResult indicating if upload is valid
        """
        from ..models.files import ValidationResult

        errors = []
        warnings = []

        # Check if source type is supported
        if source.type not in self._source_handlers:
            errors.append(f"Unsupported source type: {source.type.value}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Validate source accessibility
        try:
            handler_class = self._source_handlers[source.type]
            handler = handler_class()
            source_validation = await handler.validate_source(source)

            if not source_validation.valid:
                errors.extend(source_validation.errors)
                warnings.extend(source_validation.warnings)

        except Exception as e:
            errors.append(f"Source validation failed: {e}")

        # Check box type compatibility - RAG boxes support uploads
        if box.type not in [BoxType.RAG, BoxType.BAG]:
            errors.append(f"Box type {box.type.value} does not support uploads (use RAG or BAG)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    async def get_upload_status(self, operation_id: str) -> UploadOperation | None:
        """
        Get status of ongoing upload operation.

        Args:
            operation_id: Upload operation identifier

        Returns:
            UploadOperation if found, None otherwise
        """
        return self._active_operations.get(operation_id)

    async def cancel_upload(self, operation_id: str) -> bool:
        """
        Cancel ongoing upload operation.

        Args:
            operation_id: Upload operation identifier

        Returns:
            True if cancellation successful, False otherwise
        """
        if operation_id not in self._active_operations:
            return False

        operation = self._active_operations[operation_id]

        if not operation.can_be_cancelled():
            logger.warning(f"Upload operation {operation_id} cannot be cancelled in current state")
            return False

        # Cancel the task
        if operation_id in self._operation_tasks:
            task = self._operation_tasks[operation_id]
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        # Update operation status
        operation.status = UploadStatus.CANCELLED
        operation.complete_operation(UploadStatus.CANCELLED)

        logger.info(f"Cancelled upload operation: {operation_id}")
        return True

    async def list_active_uploads(self, box_id: str | None = None) -> list[UploadOperation]:
        """
        List active upload operations.

        Args:
            box_id: Optional filter by box ID

        Returns:
            List of active UploadOperation instances
        """
        operations = [op for op in self._active_operations.values() if op.is_active()]

        if box_id:
            operations = [op for op in operations if op.box_id == box_id]

        return operations

    async def get_upload_history(
        self,
        box_id: str | None = None,
        limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get upload operation history.

        Args:
            box_id: Optional filter by box ID
            limit: Maximum number of records to return

        Returns:
            List of upload operation summaries
        """
        # In a real implementation, this would query a database
        # For now, return summaries of completed operations
        history = []

        for operation in self._active_operations.values():
            if not operation.is_active():
                if box_id is None or operation.box_id == box_id:
                    history.append(operation.get_summary())

        # Sort by completion time (newest first)
        history.sort(key=lambda x: x['timing']['completed_at'] or '', reverse=True)

        if limit:
            history = history[:limit]

        return history

    async def cleanup_completed_operations(self, max_age_hours: int = 24) -> int:
        """
        Clean up completed operations older than specified age.

        Args:
            max_age_hours: Maximum age in hours for completed operations

        Returns:
            Number of operations cleaned up
        """
        cleanup_count = 0
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)

        operations_to_remove = []

        for operation_id, operation in self._active_operations.items():
            if not operation.is_active() and operation.completed_at:
                if operation.completed_at.timestamp() < cutoff_time:
                    operations_to_remove.append(operation_id)

        for operation_id in operations_to_remove:
            del self._active_operations[operation_id]
            if operation_id in self._operation_tasks:
                del self._operation_tasks[operation_id]
            cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} completed upload operations")

        return cleanup_count

    # Private execution methods

    async def _execute_upload(
        self,
        operation: UploadOperation,
        box: Box,
        progress_callback: Callable[[dict[str, Any]], None] | None
    ) -> None:
        """Execute the upload operation."""
        try:
            # Update status to validating
            operation.status = UploadStatus.VALIDATING
            operation.update_progress(stage="validating")
            await self._notify_progress(operation, progress_callback)

            # Get source handler
            handler_class = self._source_handlers[operation.source.type]
            handler = handler_class()

            # List files from source
            operation.status = UploadStatus.DOWNLOADING
            operation.update_progress(stage="listing_files")
            await self._notify_progress(operation, progress_callback)

            files_to_upload = []
            async for file_path in handler.list_files(operation.source, operation.recursive):
                # Apply exclusion patterns
                if self._should_exclude_file(file_path, operation.exclude_patterns):
                    continue
                files_to_upload.append(file_path)

            operation.files_total = len(files_to_upload)

            # Calculate total size if possible
            total_size = 0
            for file_path in files_to_upload:
                try:
                    file_info = await handler.get_file_info(operation.source, file_path)
                    total_size += file_info.get('size', 0)
                except Exception:
                    pass  # Skip size calculation if not available

            operation.bytes_total = total_size

            # Process each file
            operation.status = UploadStatus.PROCESSING
            operation.update_progress(stage="processing_files")

            for file_path in files_to_upload:
                if operation.status == UploadStatus.CANCELLED:
                    break

                await self._process_single_file(
                    operation, box, handler, file_path, progress_callback
                )

            # Complete operation
            if operation.status != UploadStatus.CANCELLED:
                if operation.files_failed == 0:
                    operation.complete_operation(UploadStatus.COMPLETE)
                else:
                    operation.complete_operation(UploadStatus.FAILED)

            await self._notify_progress(operation, progress_callback)

        except asyncio.CancelledError:
            operation.complete_operation(UploadStatus.CANCELLED)
            raise
        except Exception as e:
            logger.error(f"Upload operation {operation.id} failed: {e}")
            operation.record_file_failure("general", str(e))
            operation.complete_operation(UploadStatus.FAILED)
            await self._notify_progress(operation, progress_callback)

    async def _process_single_file(
        self,
        operation: UploadOperation,
        box: Box,
        handler: Any,
        file_path: str,
        progress_callback: Callable[[dict[str, Any]], None] | None
    ) -> None:
        """Process a single file upload."""
        try:
            operation.current_file = file_path
            await self._notify_progress(operation, progress_callback)

            # Get file info
            file_info = await handler.get_file_info(operation.source, file_path)
            file_size = file_info.get('size', 0)

            # Validate file
            from .validators.format_validator import FormatValidator
            validator = FormatValidator()

            # Check file size - use box settings or default 10MB
            max_size = getattr(box, 'max_file_size', None) or 10485760
            if file_size > max_size:
                operation.record_file_failure(
                    file_path,
                    f"File size {file_size} exceeds limit {max_size}",
                    "SIZE_LIMIT_EXCEEDED"
                )
                return

            # Dry run mode - just record what would be uploaded
            if operation.dry_run:
                operation.record_file_success(file_path, file_size, file_info)
                return

            # Download file to temporary location - use box data directory
            from src.lib.paths import get_box_data_path
            temp_dir = get_box_data_path(box.name) / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            temp_file = temp_dir / f"upload_{uuid.uuid4().hex}"

            success = await handler.download_file(
                operation.source,
                file_path,
                str(temp_file),
                progress_callback=lambda current, total: self._update_bytes_progress(
                    operation, current, progress_callback
                )
            )

            if not success:
                operation.record_file_failure(file_path, "Download failed")
                return

            # Validate downloaded file format - use box settings or allow all
            allowed_formats = getattr(box, 'allowed_formats', None) or []
            if allowed_formats and '*' not in allowed_formats:
                validation_result = await validator.validate_file_format(str(temp_file), allowed_formats)
                if not validation_result.valid:
                    operation.record_file_failure(file_path, f"Invalid format: {validation_result.errors[0]}")
                    temp_file.unlink(missing_ok=True)
                    return

            # Process file based on box type
            await self._process_file_for_box_type(
                operation, box, temp_file, file_path, file_size, file_info
            )

            # Clean up temp file
            temp_file.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            operation.record_file_failure(file_path, str(e))

    async def _process_file_for_box_type(
        self,
        operation: UploadOperation,
        box: Box,
        temp_file: Path,
        original_path: str,
        file_size: int,
        file_info: dict[str, Any]
    ) -> None:
        """Process file according to box type."""
        # Handle based on box type
        if box.type == BoxType.BAG:
            # BAG boxes store files directly
            await self._store_file_in_bag_box(
                operation, box, temp_file, original_path, file_size, file_info
            )
        elif box.type == BoxType.RAG:
            # RAG boxes process for vector storage
            await self._process_file_for_rag_box(
                operation, box, temp_file, original_path, file_size, file_info
            )
        else:
            # Other box types not supported for uploads
            operation.record_file_failure(
                original_path,
                f"Box type {box.type.value} does not support file uploads"
            )

    async def _store_file_in_bag_box(
        self,
        operation: UploadOperation,
        box: Box,
        temp_file: Path,
        original_path: str,
        file_size: int,
        file_info: dict[str, Any]
    ) -> None:
        """Store file in BAG box."""
        # Move file to box storage directory
        from src.lib.paths import get_box_data_path
        storage_dir = get_box_data_path(box.name) / "files"
        storage_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(original_path).name
        final_path = storage_dir / filename

        # Handle conflicts
        if final_path.exists():
            if operation.conflict_resolution == ConflictResolution.SKIP:
                operation.record_file_skip(original_path, "File already exists")
                return
            elif operation.conflict_resolution == ConflictResolution.RENAME:
                counter = 1
                while final_path.exists():
                    name_parts = filename.rsplit('.', 1)
                    if len(name_parts) == 2:
                        new_filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        new_filename = f"{filename}_{counter}"
                    final_path = storage_dir / new_filename
                    counter += 1

        # Move file
        import shutil
        shutil.move(str(temp_file), str(final_path))

        # Record success
        operation.record_file_success(original_path, file_size, {
            'storage_path': str(final_path),
            'original_info': file_info
        })

    async def _process_file_for_rag_box(
        self,
        operation: UploadOperation,
        box: Box,
        temp_file: Path,
        original_path: str,
        file_size: int,
        file_info: dict[str, Any]
    ) -> None:
        """Process file for RAG box (document processing for vector storage)."""
        # Extract text content based on file type
        content = await self._extract_text_content(temp_file)

        if not content:
            operation.record_file_failure(original_path, "No text content could be extracted")
            return

        # Create document record
        from ..models.files import DataDocument

        document = DataDocument.from_file(
            box_id=box.id,
            title=Path(original_path).name,
            content=content,
            source_path=original_path,
            upload_source=operation.source,
            processing_config={}  # Use default processing config
        )

        # Calculate quality score
        document.calculate_quality_score()

        # Store document (in real implementation, this would save to database)
        # For now, just record success
        operation.record_file_success(original_path, file_size, {
            'document_id': document.id,
            'word_count': document.word_count,
            'quality_score': document.quality_score
        })

    async def _extract_text_content(self, file_path: Path) -> str:
        """Extract text content from file based on type."""
        # Simple text extraction - in real implementation would use
        # appropriate libraries for different file types
        try:
            if file_path.suffix.lower() in ['.txt', '.md', '.py', '.js', '.html']:
                with open(file_path, encoding='utf-8') as f:
                    return f.read()
            else:
                # For other file types, return filename as placeholder
                return f"Content of {file_path.name}"
        except Exception as e:
            logger.warning(f"Failed to extract content from {file_path}: {e}")
            return ""

    def _should_exclude_file(self, file_path: str, exclude_patterns: list[str]) -> bool:
        """Check if file should be excluded based on patterns."""
        import fnmatch

        for pattern in exclude_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    async def _notify_progress(
        self,
        operation: UploadOperation,
        callback: Callable[[dict[str, Any]], None] | None
    ) -> None:
        """Notify progress callback if provided."""
        if callback:
            try:
                progress_data = {
                    'operation_id': operation.id,
                    'status': operation.status.value,
                    'files_processed': operation.files_processed,
                    'files_total': operation.files_total,
                    'bytes_processed': operation.bytes_processed,
                    'bytes_total': operation.bytes_total,
                    'current_file': operation.current_file,
                    'stage': operation.current_stage,
                    'percentage': operation.get_progress_percentage()
                }
                callback(progress_data)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def _update_bytes_progress(
        self,
        operation: UploadOperation,
        bytes_processed: int,
        callback: Callable[[dict[str, Any]], None] | None
    ) -> None:
        """Update bytes progress during file download."""
        operation.bytes_processed += bytes_processed
        # Only notify every 1MB to avoid excessive callbacks
        if bytes_processed % 1048576 == 0:
            asyncio.create_task(self._notify_progress(operation, callback))

    def __str__(self) -> str:
        """String representation of UploadManager."""
        active_count = len([op for op in self._active_operations.values() if op.is_active()])
        return f"UploadManager({active_count} active operations)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"UploadManager(active_operations={len(self._active_operations)}, "
                f"source_handlers={list(self._source_handlers.keys())})")


# Import required for ValidationResult
from ..models.files import ValidationResult
