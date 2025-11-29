"""
SMB upload source handler

Handles uploading files from SMB/CIFS shares including:
- NTLM and Kerberos authentication
- Domain and workgroup support
- Directory listing and traversal
- File downloads with progress tracking
"""

import logging
import uuid
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.logic.projects.models.upload import UploadSource, UploadSourceType
from src.logic.projects.models.validation import ValidationResult
from src.logic.projects.upload.sources.base_source import BaseUploadSource

logger = logging.getLogger(__name__)

try:
    import smbprotocol.exceptions
    from smbprotocol.connection import Connection
    from smbprotocol.file_info import FileInformationClass
    from smbprotocol.open import (
        CreateDisposition,
        ImpersonationLevel,
        Open,
        ShareAccess,
    )
    from smbprotocol.session import Session
    from smbprotocol.tree import TreeConnect
    SMB_AVAILABLE = True
except ImportError:
    logger.warning("SMB support not available. Install smbprotocol package for SMB functionality.")
    SMB_AVAILABLE = False


class SMBSource(BaseUploadSource):
    """Handler for SMB/CIFS upload sources"""

    def __init__(self):
        super().__init__()
        self.source_type = UploadSourceType.SMB
        self._connection_pool = {}

        if not SMB_AVAILABLE:
            logger.warning("SMB functionality disabled - smbprotocol package not installed")

    async def validate_source(self, source: UploadSource) -> ValidationResult:
        """Validate SMB source accessibility and credentials"""
        if not SMB_AVAILABLE:
            return ValidationResult(
                valid=False,
                errors=["SMB support not available - install smbprotocol package"],
                warnings=[]
            )

        try:
            # Parse SMB URL
            parsed = urlparse(source.location)
            if parsed.scheme.lower() not in ['smb', 'cifs']:
                return ValidationResult(
                    valid=False,
                    errors=[f"Invalid SMB URL scheme: {parsed.scheme}"],
                    warnings=[]
                )

            # Validate required credentials
            if not source.credentials:
                return ValidationResult(
                    valid=False,
                    errors=["SMB requires authentication credentials"],
                    warnings=[]
                )

            username = source.credentials.get("username")
            password = source.credentials.get("password")

            if not username or not password:
                return ValidationResult(
                    valid=False,
                    errors=["SMB username and password are required"],
                    warnings=[]
                )

            # Test connection
            connection_test = await self._test_smb_connection(source)
            if not connection_test["success"]:
                return ValidationResult(
                    valid=False,
                    errors=[connection_test["error"]],
                    warnings=[]
                )

            return ValidationResult(valid=True, errors=[], warnings=[])

        except Exception as e:
            logger.error(f"Error validating SMB source {source.location}: {e}")
            return ValidationResult(
                valid=False,
                errors=[f"SMB validation error: {str(e)}"],
                warnings=[]
            )

    async def list_files(
        self,
        source: UploadSource,
        recursive: bool = False
    ) -> AsyncGenerator[str]:
        """List files available from SMB source"""
        if not SMB_AVAILABLE:
            raise ImportError("SMB support not available")

        try:
            tree = await self._get_smb_tree(source)
            parsed = urlparse(source.location)
            base_path = parsed.path or "\\"

            if recursive:
                async for file_path in self._list_files_recursive(tree, base_path, source):
                    yield file_path
            else:
                async for file_path in self._list_files_non_recursive(tree, base_path, source):
                    yield file_path

        except Exception as e:
            logger.error(f"Error listing SMB files from {source.location}: {e}")
            raise
        finally:
            await self._release_smb_connection(source)

    async def download_file(
        self,
        source: UploadSource,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> bool:
        """Download file from SMB source"""
        if not SMB_AVAILABLE:
            raise ImportError("SMB support not available")

        try:
            tree = await self._get_smb_tree(source)

            # Open remote file
            file_open = Open(tree, remote_path)
            file_open.create(
                ImpersonationLevel.Impersonation,
                ShareAccess.FILE_SHARE_READ,
                CreateDisposition.FILE_OPEN
            )

            # Get file size
            file_info = file_open.query_info(FileInformationClass.FileStandardInformation)
            file_size = file_info['end_of_file']

            # Ensure destination directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            # Download with progress tracking
            bytes_downloaded = 0
            chunk_size = 64 * 1024  # 64KB chunks

            with open(local_path, 'wb') as local_file:
                while bytes_downloaded < file_size:
                    remaining = file_size - bytes_downloaded
                    current_chunk_size = min(chunk_size, remaining)

                    # Read chunk from SMB file
                    chunk = file_open.read(bytes_downloaded, current_chunk_size)
                    local_file.write(chunk)
                    bytes_downloaded += len(chunk)

                    # Report progress
                    if progress_callback:
                        progress_callback(bytes_downloaded, file_size)

            file_open.close()

            logger.debug(f"Successfully downloaded {remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Error downloading SMB file {remote_path}: {e}")
            return False
        finally:
            await self._release_smb_connection(source)

    async def get_file_info(
        self,
        source: UploadSource,
        remote_path: str
    ) -> dict[str, Any]:
        """Get file metadata from SMB source"""
        if not SMB_AVAILABLE:
            raise ImportError("SMB support not available")

        try:
            tree = await self._get_smb_tree(source)

            # Open file to get information
            file_open = Open(tree, remote_path)
            file_open.create(
                ImpersonationLevel.Impersonation,
                ShareAccess.FILE_SHARE_READ,
                CreateDisposition.FILE_OPEN
            )

            # Get file information
            basic_info = file_open.query_info(FileInformationClass.FileBasicInformation)
            standard_info = file_open.query_info(FileInformationClass.FileStandardInformation)

            file_info = {
                "filename": Path(remote_path).name,
                "file_path": remote_path,
                "file_size": standard_info['end_of_file'],
                "is_directory": bool(basic_info['file_attributes'] & 0x10),  # FILE_ATTRIBUTE_DIRECTORY
                "created_at": basic_info['creation_time'],
                "modified_at": basic_info['last_write_time'],
                "accessed_at": basic_info['last_access_time'],
                "attributes": basic_info['file_attributes'],
                "mime_type": "application/octet-stream"
            }

            # Guess MIME type from extension
            import mimetypes
            mime_type, _ = mimetypes.guess_type(remote_path)
            if mime_type:
                file_info["mime_type"] = mime_type

            file_open.close()
            return file_info

        except Exception as e:
            logger.error(f"Error getting SMB file info for {remote_path}: {e}")
            raise
        finally:
            await self._release_smb_connection(source)

    async def test_connection(self, source: UploadSource) -> bool:
        """Test SMB connection"""
        if not SMB_AVAILABLE:
            return False

        result = await self._test_smb_connection(source)
        return result["success"]

    def requires_authentication(self) -> bool:
        """SMB always requires authentication"""
        return True

    async def _get_smb_tree(self, source: UploadSource) -> 'TreeConnect':
        """Get or create SMB tree connection"""
        connection_key = source.location

        if connection_key in self._connection_pool:
            tree = self._connection_pool[connection_key]
            try:
                # Test if connection is still alive
                tree.session.connection.send(b'\x00' * 4)  # Simple ping
                return tree
            except (smbprotocol.exceptions.SMBException, OSError, ConnectionError):
                # Connection dead, remove from pool
                del self._connection_pool[connection_key]

        # Create new connection
        parsed = urlparse(source.location)
        server = parsed.hostname
        port = parsed.port or 445
        share = parsed.path.split('/')[1] if parsed.path else None

        if not share:
            raise ValueError(f"No share specified in SMB URL: {source.location}")

        # Create connection
        connection = Connection(uuid.uuid4(), server, port)
        connection.connect()

        # Create session
        session = Session(connection, source.credentials["username"])

        # Authenticate
        domain = source.credentials.get("domain", "")
        password = source.credentials["password"]

        session.setup_session(password, domain)

        # Connect to tree/share
        tree = TreeConnect(session, f"\\\\{server}\\{share}")
        tree.tree_connect()

        self._connection_pool[connection_key] = tree
        return tree

    async def _release_smb_connection(self, source: UploadSource) -> None:
        """Release SMB connection (keep in pool for reuse)"""
        # Keep connection in pool for reuse
        pass

    async def _test_smb_connection(self, source: UploadSource) -> dict[str, Any]:
        """Test SMB connection and return result"""
        try:
            tree = await self._get_smb_tree(source)

            # Test by listing root directory
            files = tree.query_directory("\\", "*")

            return {
                "success": True,
                "files_found": len(files),
                "error": None
            }

        except smbprotocol.exceptions.SMBException as e:
            error_msg = f"SMB protocol error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"SMB connection failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _list_files_recursive(
        self,
        tree: 'TreeConnect',
        base_path: str,
        source: UploadSource
    ) -> AsyncGenerator[str]:
        """Recursively list files from SMB directory"""
        try:
            # Normalize path separators for SMB
            smb_path = base_path.replace('/', '\\')
            if not smb_path.endswith('\\'):
                smb_path += '\\'

            # Query directory contents
            items = tree.query_directory(smb_path, "*")

            for item in items:
                filename = item['file_name']

                # Skip . and ..
                if filename in ['.', '..']:
                    continue

                item_path = f"{smb_path}{filename}"

                # Apply exclusion patterns
                if source.exclude_patterns:
                    if self._matches_exclusion_pattern(filename, source.exclude_patterns):
                        continue

                # Check if it's a directory
                is_directory = bool(item['file_attributes'] & 0x10)  # FILE_ATTRIBUTE_DIRECTORY

                if is_directory:
                    # Recursively list subdirectory
                    async for file_path in self._list_files_recursive(tree, item_path, source):
                        yield file_path
                else:
                    # Regular file
                    yield item_path.replace('\\', '/')  # Convert back to Unix-style path

        except Exception as e:
            logger.error(f"Error listing SMB directory {base_path}: {e}")

    async def _list_files_non_recursive(
        self,
        tree: 'TreeConnect',
        base_path: str,
        source: UploadSource
    ) -> AsyncGenerator[str]:
        """List files from SMB directory (non-recursive)"""
        try:
            # Normalize path separators for SMB
            smb_path = base_path.replace('/', '\\')
            if not smb_path.endswith('\\'):
                smb_path += '\\'

            # Query directory contents
            items = tree.query_directory(smb_path, "*")

            for item in items:
                filename = item['file_name']

                # Skip . and ..
                if filename in ['.', '..']:
                    continue

                # Check if it's a directory
                is_directory = bool(item['file_attributes'] & 0x10)  # FILE_ATTRIBUTE_DIRECTORY

                # Skip directories in non-recursive mode
                if is_directory:
                    continue

                # Apply exclusion patterns
                if source.exclude_patterns:
                    if self._matches_exclusion_pattern(filename, source.exclude_patterns):
                        continue

                item_path = f"{smb_path}{filename}"
                yield item_path.replace('\\', '/')  # Convert back to Unix-style path

        except Exception as e:
            logger.error(f"Error listing SMB directory {base_path}: {e}")

    def _matches_exclusion_pattern(self, filename: str, patterns: list) -> bool:
        """Check if filename matches any exclusion pattern"""
        import fnmatch
        return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)

    async def cleanup(self, source: UploadSource) -> None:
        """Cleanup SMB connections"""
        connection_key = source.location
        if connection_key in self._connection_pool:
            try:
                tree = self._connection_pool[connection_key]
                tree.tree_disconnect()
                tree.session.logoff()
                tree.session.connection.disconnect()
            except (smbprotocol.exceptions.SMBException, OSError, ConnectionError):
                pass
            finally:
                del self._connection_pool[connection_key]
