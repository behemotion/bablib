"""
SFTP upload source handler

Handles uploading files from SFTP servers including:
- SSH key and password authentication
- Directory listing and traversal
- File downloads with progress tracking
- Connection management and security
"""

import io
import logging
import stat
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import paramiko

from src.logic.projects.models.upload import UploadSource, UploadSourceType
from src.logic.projects.models.validation import ValidationResult
from src.logic.projects.upload.sources.base_source import BaseUploadSource

logger = logging.getLogger(__name__)


class SFTPSource(BaseUploadSource):
    """Handler for SFTP upload sources"""

    def __init__(self):
        super().__init__()
        self.source_type = UploadSourceType.SFTP
        self._connection_pool = {}

    async def validate_source(self, source: UploadSource) -> ValidationResult:
        """Validate SFTP source accessibility and credentials"""
        try:
            # Parse SFTP URL
            parsed = urlparse(source.location)
            if parsed.scheme.lower() != 'sftp':
                return ValidationResult(
                    valid=False,
                    errors=[f"Invalid SFTP URL scheme: {parsed.scheme}"],
                    warnings=[]
                )

            # Validate required credentials
            if not source.credentials:
                return ValidationResult(
                    valid=False,
                    errors=["SFTP requires authentication credentials"],
                    warnings=[]
                )

            username = source.credentials.get("username")
            if not username:
                return ValidationResult(
                    valid=False,
                    errors=["SFTP username is required"],
                    warnings=[]
                )

            # Test connection
            connection_test = await self._test_sftp_connection(source)
            if not connection_test["success"]:
                return ValidationResult(
                    valid=False,
                    errors=[connection_test["error"]],
                    warnings=[]
                )

            return ValidationResult(valid=True, errors=[], warnings=[])

        except Exception as e:
            logger.error(f"Error validating SFTP source {source.location}: {e}")
            return ValidationResult(
                valid=False,
                errors=[f"SFTP validation error: {str(e)}"],
                warnings=[]
            )

    async def list_files(
        self,
        source: UploadSource,
        recursive: bool = False
    ) -> AsyncGenerator[str]:
        """List files available from SFTP source"""
        try:
            sftp = await self._get_sftp_connection(source)
            parsed = urlparse(source.location)
            base_path = parsed.path or "."

            if recursive:
                async for file_path in self._list_files_recursive(sftp, base_path, source):
                    yield file_path
            else:
                async for file_path in self._list_files_non_recursive(sftp, base_path, source):
                    yield file_path

        except Exception as e:
            logger.error(f"Error listing SFTP files from {source.location}: {e}")
            raise
        finally:
            await self._release_sftp_connection(source)

    async def download_file(
        self,
        source: UploadSource,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> bool:
        """Download file from SFTP source"""
        try:
            sftp = await self._get_sftp_connection(source)

            # Get file size for progress tracking
            stat_result = sftp.stat(remote_path)
            file_size = stat_result.st_size

            # Ensure destination directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            # Download with progress tracking
            if progress_callback and file_size > 0:
                await self._download_with_progress(
                    sftp, remote_path, local_path, file_size, progress_callback
                )
            else:
                # Simple download without progress
                sftp.get(remote_path, local_path)

            logger.debug(f"Successfully downloaded {remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Error downloading SFTP file {remote_path}: {e}")
            return False
        finally:
            await self._release_sftp_connection(source)

    async def get_file_info(
        self,
        source: UploadSource,
        remote_path: str
    ) -> dict[str, Any]:
        """Get file metadata from SFTP source"""
        try:
            sftp = await self._get_sftp_connection(source)

            # Get file statistics
            stat_result = sftp.stat(remote_path)

            file_info = {
                "filename": Path(remote_path).name,
                "file_path": remote_path,
                "file_size": stat_result.st_size,
                "is_directory": stat.S_ISDIR(stat_result.st_mode),
                "is_symlink": stat.S_ISLNK(stat_result.st_mode),
                "permissions": oct(stat_result.st_mode)[-3:],
                "owner_uid": stat_result.st_uid,
                "group_gid": stat_result.st_gid,
                "created_at": stat_result.st_ctime,
                "modified_at": stat_result.st_mtime,
                "accessed_at": stat_result.st_atime,
                "mime_type": "application/octet-stream"
            }

            # Guess MIME type from extension
            import mimetypes
            mime_type, _ = mimetypes.guess_type(remote_path)
            if mime_type:
                file_info["mime_type"] = mime_type

            return file_info

        except Exception as e:
            logger.error(f"Error getting SFTP file info for {remote_path}: {e}")
            raise
        finally:
            await self._release_sftp_connection(source)

    async def test_connection(self, source: UploadSource) -> bool:
        """Test SFTP connection"""
        result = await self._test_sftp_connection(source)
        return result["success"]

    def requires_authentication(self) -> bool:
        """SFTP always requires authentication"""
        return True

    def supports_resume(self) -> bool:
        """SFTP supports resuming downloads"""
        return True

    async def _get_sftp_connection(self, source: UploadSource) -> paramiko.SFTPClient:
        """Get or create SFTP connection"""
        connection_key = source.location

        if connection_key in self._connection_pool:
            sftp = self._connection_pool[connection_key]
            try:
                # Test if connection is still alive
                sftp.listdir('.')
                return sftp
            except (paramiko.SSHException, OSError, IOError):
                # Connection dead, remove from pool
                del self._connection_pool[connection_key]

        # Create new connection
        parsed = urlparse(source.location)
        host = parsed.hostname
        port = parsed.port or 22

        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddHostPolicy())

        # Prepare authentication
        username = source.credentials["username"]
        password = source.credentials.get("password")
        private_key_str = source.credentials.get("private_key")
        private_key_path = source.credentials.get("private_key_path")

        # Connect with timeout
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 30
        }

        # Add authentication method
        if private_key_str:
            # Use private key from string
            key_file = io.StringIO(private_key_str)
            private_key = paramiko.RSAKey.from_private_key(key_file)
            connect_kwargs["pkey"] = private_key
        elif private_key_path:
            # Use private key from file
            private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
            connect_kwargs["pkey"] = private_key
        elif password:
            # Use password authentication
            connect_kwargs["password"] = password
        else:
            raise ValueError("No valid authentication method provided for SFTP")

        # Connect
        ssh.connect(**connect_kwargs)

        # Create SFTP client
        sftp = ssh.open_sftp()

        # Change to specified directory if provided
        if parsed.path and parsed.path != "/":
            try:
                sftp.chdir(parsed.path)
            except Exception as e:
                logger.warning(f"Could not change to directory {parsed.path}: {e}")

        self._connection_pool[connection_key] = sftp
        return sftp

    async def _release_sftp_connection(self, source: UploadSource) -> None:
        """Release SFTP connection (keep in pool for reuse)"""
        # Keep connection in pool for reuse
        pass

    async def _test_sftp_connection(self, source: UploadSource) -> dict[str, Any]:
        """Test SFTP connection and return result"""
        try:
            sftp = await self._get_sftp_connection(source)

            # Test by listing current directory
            sftp.listdir('.')

            return {
                "success": True,
                "error": None
            }

        except paramiko.AuthenticationException as e:
            error_msg = f"SFTP authentication failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except paramiko.SSHException as e:
            error_msg = f"SFTP SSH error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"SFTP connection failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _list_files_recursive(
        self,
        sftp: paramiko.SFTPClient,
        base_path: str,
        source: UploadSource
    ) -> AsyncGenerator[str]:
        """Recursively list files from SFTP directory"""
        try:
            # Get directory listing with attributes
            items = sftp.listdir_attr(base_path)

            for item in items:
                item_path = f"{base_path.rstrip('/')}/{item.filename}"

                # Apply exclusion patterns
                if source.exclude_patterns:
                    if self._matches_exclusion_pattern(item.filename, source.exclude_patterns):
                        continue

                if stat.S_ISDIR(item.st_mode):
                    # Recursively list subdirectory
                    async for file_path in self._list_files_recursive(sftp, item_path, source):
                        yield file_path
                elif stat.S_ISREG(item.st_mode):
                    # Regular file
                    yield item_path

        except Exception as e:
            logger.error(f"Error listing SFTP directory {base_path}: {e}")

    async def _list_files_non_recursive(
        self,
        sftp: paramiko.SFTPClient,
        base_path: str,
        source: UploadSource
    ) -> AsyncGenerator[str]:
        """List files from SFTP directory (non-recursive)"""
        try:
            # Get directory listing with attributes
            items = sftp.listdir_attr(base_path)

            for item in items:
                # Skip directories
                if stat.S_ISDIR(item.st_mode):
                    continue

                # Apply exclusion patterns
                if source.exclude_patterns:
                    if self._matches_exclusion_pattern(item.filename, source.exclude_patterns):
                        continue

                if stat.S_ISREG(item.st_mode):
                    item_path = f"{base_path.rstrip('/')}/{item.filename}"
                    yield item_path

        except Exception as e:
            logger.error(f"Error listing SFTP directory {base_path}: {e}")

    async def _download_with_progress(
        self,
        sftp: paramiko.SFTPClient,
        remote_path: str,
        local_path: str,
        file_size: int,
        progress_callback: Callable[[int, int], None]
    ) -> None:
        """Download file with progress tracking"""
        bytes_downloaded = 0
        chunk_size = 64 * 1024  # 64KB chunks

        with open(local_path, 'wb') as local_file:
            with sftp.open(remote_path, 'rb') as remote_file:
                while True:
                    chunk = remote_file.read(chunk_size)
                    if not chunk:
                        break

                    local_file.write(chunk)
                    bytes_downloaded += len(chunk)

                    # Report progress
                    progress_callback(bytes_downloaded, file_size)

    def _matches_exclusion_pattern(self, filename: str, patterns: list) -> bool:
        """Check if filename matches any exclusion pattern"""
        import fnmatch
        return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)

    async def cleanup(self, source: UploadSource) -> None:
        """Cleanup SFTP connections"""
        connection_key = source.location
        if connection_key in self._connection_pool:
            try:
                sftp = self._connection_pool[connection_key]
                sftp.close()
                # Also close the underlying SSH connection
                if hasattr(sftp, 'sock') and hasattr(sftp.sock, 'close'):
                    sftp.sock.close()
            except (paramiko.SSHException, OSError, IOError):
                pass
            finally:
                del self._connection_pool[connection_key]

    async def resume_download(
        self,
        source: UploadSource,
        remote_path: str,
        local_path: str,
        resume_offset: int,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> bool:
        """Resume interrupted download from specified offset"""
        try:
            sftp = await self._get_sftp_connection(source)

            # Get total file size
            stat_result = sftp.stat(remote_path)
            total_size = stat_result.st_size

            if resume_offset >= total_size:
                logger.warning(f"Resume offset {resume_offset} >= file size {total_size}")
                return True  # File already completely downloaded

            # Open files for resuming
            with open(local_path, 'ab') as local_file:  # Append mode
                with sftp.open(remote_path, 'rb') as remote_file:
                    # Seek to resume position
                    remote_file.seek(resume_offset)

                    bytes_downloaded = resume_offset
                    chunk_size = 64 * 1024  # 64KB chunks

                    while bytes_downloaded < total_size:
                        remaining = total_size - bytes_downloaded
                        current_chunk_size = min(chunk_size, remaining)

                        chunk = remote_file.read(current_chunk_size)
                        if not chunk:
                            break

                        local_file.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Report progress
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_size)

            logger.debug(f"Successfully resumed download of {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Error resuming SFTP download {remote_path}: {e}")
            return False
        finally:
            await self._release_sftp_connection(source)
