"""
FTP upload source handler

Handles uploading files from FTP servers including:
- Anonymous and authenticated connections
- Directory listing and traversal
- File downloads with progress tracking
- Connection pooling and retry logic
"""

import ftplib
import logging
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.logic.projects.models.upload import UploadSource, UploadSourceType
from src.logic.projects.models.validation import ValidationResult
from src.logic.projects.upload.sources.base_source import BaseUploadSource

logger = logging.getLogger(__name__)


class FTPSource(BaseUploadSource):
    """Handler for FTP upload sources"""

    def __init__(self):
        super().__init__()
        self.source_type = UploadSourceType.FTP
        self._connection_pool = {}

    async def validate_source(self, source: UploadSource) -> ValidationResult:
        """Validate FTP source accessibility and credentials"""
        try:
            # Parse FTP URL
            parsed = urlparse(source.location)
            if parsed.scheme.lower() != 'ftp':
                return ValidationResult(
                    valid=False,
                    errors=[f"Invalid FTP URL scheme: {parsed.scheme}"],
                    warnings=[]
                )

            # Test connection
            connection_test = await self._test_ftp_connection(source)
            if not connection_test["success"]:
                return ValidationResult(
                    valid=False,
                    errors=[connection_test["error"]],
                    warnings=[]
                )

            return ValidationResult(valid=True, errors=[], warnings=[])

        except Exception as e:
            logger.error(f"Error validating FTP source {source.location}: {e}")
            return ValidationResult(
                valid=False,
                errors=[f"FTP validation error: {str(e)}"],
                warnings=[]
            )

    async def list_files(
        self,
        source: UploadSource,
        recursive: bool = False
    ) -> AsyncGenerator[str]:
        """List files available from FTP source"""
        try:
            ftp = await self._get_ftp_connection(source)
            parsed = urlparse(source.location)
            base_path = parsed.path or "/"

            if recursive:
                async for file_path in self._list_files_recursive(ftp, base_path, source):
                    yield file_path
            else:
                async for file_path in self._list_files_non_recursive(ftp, base_path, source):
                    yield file_path

        except Exception as e:
            logger.error(f"Error listing FTP files from {source.location}: {e}")
            raise
        finally:
            await self._release_ftp_connection(source)

    async def download_file(
        self,
        source: UploadSource,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> bool:
        """Download file from FTP source"""
        try:
            ftp = await self._get_ftp_connection(source)

            # Get file size for progress tracking
            try:
                file_size = ftp.size(remote_path)
            except ftplib.error_perm:
                # SIZE command not supported, try to get size from listing
                file_size = await self._get_file_size_from_listing(ftp, remote_path)

            # Ensure destination directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            # Download with progress tracking
            bytes_downloaded = 0

            def progress_wrapper(chunk):
                nonlocal bytes_downloaded
                bytes_downloaded += len(chunk)
                if progress_callback:
                    progress_callback(bytes_downloaded, file_size or 0)

            # Download file
            with open(local_path, 'wb') as local_file:
                def write_chunk(chunk):
                    local_file.write(chunk)
                    progress_wrapper(chunk)

                ftp.retrbinary(f'RETR {remote_path}', write_chunk)

            logger.debug(f"Successfully downloaded {remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Error downloading FTP file {remote_path}: {e}")
            return False
        finally:
            await self._release_ftp_connection(source)

    async def get_file_info(
        self,
        source: UploadSource,
        remote_path: str
    ) -> dict[str, Any]:
        """Get file metadata from FTP source"""
        try:
            ftp = await self._get_ftp_connection(source)

            # Get file info from MLST command if supported
            try:
                mlst_response = ftp.mlst(remote_path)
                return self._parse_mlst_response(mlst_response, remote_path)
            except (ftplib.error_perm, AttributeError):
                # MLST not supported, fall back to LIST
                pass

            # Try to get basic info
            file_info = {
                "filename": Path(remote_path).name,
                "file_path": remote_path,
                "is_directory": False,
                "mime_type": "application/octet-stream"
            }

            # Try to get file size
            try:
                file_size = ftp.size(remote_path)
                file_info["file_size"] = file_size
            except ftplib.error_perm:
                file_info["file_size"] = 0

            # Try to get modification time
            try:
                mod_time = ftp.voidcmd(f'MDTM {remote_path}')
                file_info["modified_at"] = self._parse_mdtm_response(mod_time)
            except ftplib.error_perm:
                file_info["modified_at"] = None

            # Guess MIME type from extension
            import mimetypes
            mime_type, _ = mimetypes.guess_type(remote_path)
            if mime_type:
                file_info["mime_type"] = mime_type

            return file_info

        except Exception as e:
            logger.error(f"Error getting FTP file info for {remote_path}: {e}")
            raise
        finally:
            await self._release_ftp_connection(source)

    async def test_connection(self, source: UploadSource) -> bool:
        """Test FTP connection"""
        result = await self._test_ftp_connection(source)
        return result["success"]

    def requires_authentication(self) -> bool:
        """FTP may require authentication"""
        return True

    async def _get_ftp_connection(self, source: UploadSource) -> ftplib.FTP:
        """Get or create FTP connection"""
        connection_key = source.location

        if connection_key in self._connection_pool:
            ftp = self._connection_pool[connection_key]
            try:
                # Test if connection is still alive
                ftp.voidcmd("NOOP")
                return ftp
            except (ftplib.error_temp, ftplib.error_perm, OSError, EOFError):
                # Connection dead, remove from pool
                del self._connection_pool[connection_key]

        # Create new connection
        parsed = urlparse(source.location)
        host = parsed.hostname
        port = parsed.port or 21

        ftp = ftplib.FTP()

        # Set timeout
        ftp.connect(host, port, timeout=30)

        # Login
        username = source.credentials.get("username", "anonymous") if source.credentials else "anonymous"
        password = source.credentials.get("password", "anonymous@") if source.credentials else "anonymous@"

        ftp.login(username, password)

        # Set passive mode
        ftp.set_pasv(True)

        # Change to specified directory if provided
        if parsed.path and parsed.path != "/":
            try:
                ftp.cwd(parsed.path)
            except ftplib.error_perm as e:
                logger.warning(f"Could not change to directory {parsed.path}: {e}")

        self._connection_pool[connection_key] = ftp
        return ftp

    async def _release_ftp_connection(self, source: UploadSource) -> None:
        """Release FTP connection (keep in pool for reuse)"""
        # Keep connection in pool for reuse
        pass

    async def _test_ftp_connection(self, source: UploadSource) -> dict[str, Any]:
        """Test FTP connection and return result"""
        try:
            ftp = await self._get_ftp_connection(source)
            welcome_msg = ftp.getwelcome()

            return {
                "success": True,
                "welcome_message": welcome_msg,
                "error": None
            }

        except ftplib.error_perm as e:
            error_msg = f"FTP authentication failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"FTP connection failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _list_files_recursive(
        self,
        ftp: ftplib.FTP,
        base_path: str,
        source: UploadSource
    ) -> AsyncGenerator[str]:
        """Recursively list files from FTP directory"""
        try:
            # Get directory listing
            items = []
            ftp.retrlines('LIST', items.append)

            for line in items:
                parsed_item = self._parse_ftp_list_line(line)
                if not parsed_item:
                    continue

                item_path = f"{base_path.rstrip('/')}/{parsed_item['name']}"

                # Apply exclusion patterns
                if source.exclude_patterns:
                    if self._matches_exclusion_pattern(parsed_item['name'], source.exclude_patterns):
                        continue

                if parsed_item['is_directory']:
                    # Recursively list subdirectory
                    original_dir = ftp.pwd()
                    try:
                        ftp.cwd(item_path)
                        async for file_path in self._list_files_recursive(ftp, item_path, source):
                            yield file_path
                    finally:
                        ftp.cwd(original_dir)
                else:
                    # Yield file
                    yield item_path

        except Exception as e:
            logger.error(f"Error listing FTP directory {base_path}: {e}")

    async def _list_files_non_recursive(
        self,
        ftp: ftplib.FTP,
        base_path: str,
        source: UploadSource
    ) -> AsyncGenerator[str]:
        """List files from FTP directory (non-recursive)"""
        try:
            # Get directory listing
            items = []
            ftp.retrlines('LIST', items.append)

            for line in items:
                parsed_item = self._parse_ftp_list_line(line)
                if not parsed_item or parsed_item['is_directory']:
                    continue

                # Apply exclusion patterns
                if source.exclude_patterns:
                    if self._matches_exclusion_pattern(parsed_item['name'], source.exclude_patterns):
                        continue

                item_path = f"{base_path.rstrip('/')}/{parsed_item['name']}"
                yield item_path

        except Exception as e:
            logger.error(f"Error listing FTP directory {base_path}: {e}")

    def _parse_ftp_list_line(self, line: str) -> dict[str, Any] | None:
        """Parse FTP LIST command output line"""
        try:
            # Unix-style listing: -rw-r--r-- 1 user group 1234 Nov 15 10:30 filename
            parts = line.split()
            if len(parts) < 9:
                return None

            permissions = parts[0]
            is_directory = permissions.startswith('d')
            filename = ' '.join(parts[8:])  # Handle filenames with spaces

            return {
                'name': filename,
                'is_directory': is_directory,
                'permissions': permissions,
                'size': int(parts[4]) if not is_directory else 0
            }

        except Exception as e:
            logger.debug(f"Could not parse FTP list line: {line} - {e}")
            return None

    def _parse_mlst_response(self, mlst_response: str, file_path: str) -> dict[str, Any]:
        """Parse MLST command response"""
        # MLST response format: "modify=20210315103045;size=1234;type=file; filename"
        facts = {}
        response_line = mlst_response.split('\n')[1] if '\n' in mlst_response else mlst_response

        if ';' in response_line:
            facts_part, filename = response_line.rsplit(';', 1)
            filename = filename.strip()

            for fact in facts_part.split(';'):
                if '=' in fact:
                    key, value = fact.split('=', 1)
                    facts[key] = value

        file_info = {
            "filename": Path(file_path).name,
            "file_path": file_path,
            "file_size": int(facts.get("size", 0)),
            "is_directory": facts.get("type") == "dir",
            "modified_at": facts.get("modify"),
            "mime_type": "application/octet-stream"
        }

        # Guess MIME type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            file_info["mime_type"] = mime_type

        return file_info

    def _parse_mdtm_response(self, mdtm_response: str) -> str | None:
        """Parse MDTM command response"""
        try:
            # MDTM response: "213 20210315103045"
            timestamp = mdtm_response.split()[1]
            # Convert YYYYMMDDHHMMSS to ISO format
            from datetime import datetime
            dt = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
            return dt.isoformat()
        except Exception:
            return None

    async def _get_file_size_from_listing(self, ftp: ftplib.FTP, file_path: str) -> int | None:
        """Get file size from directory listing when SIZE command fails"""
        try:
            parent_dir = str(Path(file_path).parent)
            filename = Path(file_path).name

            original_dir = ftp.pwd()
            try:
                if parent_dir != ".":
                    ftp.cwd(parent_dir)

                items = []
                ftp.retrlines('LIST', items.append)

                for line in items:
                    parsed_item = self._parse_ftp_list_line(line)
                    if parsed_item and parsed_item['name'] == filename:
                        return parsed_item['size']

            finally:
                ftp.cwd(original_dir)

        except Exception as e:
            logger.debug(f"Could not get file size from listing for {file_path}: {e}")

        return None

    def _matches_exclusion_pattern(self, filename: str, patterns: list) -> bool:
        """Check if filename matches any exclusion pattern"""
        import fnmatch
        return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)

    async def cleanup(self, source: UploadSource) -> None:
        """Cleanup FTP connections"""
        connection_key = source.location
        if connection_key in self._connection_pool:
            try:
                ftp = self._connection_pool[connection_key]
                ftp.quit()
            except (ftplib.error_temp, ftplib.error_perm, OSError, EOFError):
                pass
            finally:
                del self._connection_pool[connection_key]
