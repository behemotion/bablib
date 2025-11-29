"""
HTTP/HTTPS upload source handler

Handles downloading files from HTTP/HTTPS sources including:
- GET requests with authentication
- Range requests for resume capability
- Redirect following
- Progress tracking for large downloads
- SSL certificate verification
"""

import logging
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiofiles
import httpx

from src.logic.projects.models.upload import UploadSource, UploadSourceType
from src.logic.projects.models.validation import ValidationResult
from src.logic.projects.upload.sources.base_source import BaseUploadSource

logger = logging.getLogger(__name__)


class HTTPSource(BaseUploadSource):
    """Handler for HTTP/HTTPS upload sources"""

    def __init__(self):
        super().__init__()
        self.source_type = UploadSourceType.HTTP
        self._client_pool = {}

    async def validate_source(self, source: UploadSource) -> ValidationResult:
        """Validate HTTP source accessibility"""
        try:
            # Parse HTTP URL
            parsed = urlparse(source.location)
            if parsed.scheme.lower() not in ['http', 'https']:
                return ValidationResult(
                    valid=False,
                    errors=[f"Invalid HTTP URL scheme: {parsed.scheme}"],
                    warnings=[]
                )

            # Validate URL format
            if not parsed.netloc:
                return ValidationResult(
                    valid=False,
                    errors=[f"Invalid HTTP URL format: {source.location}"],
                    warnings=[]
                )

            # Test connection with HEAD request
            connection_test = await self._test_http_connection(source)
            if not connection_test["success"]:
                return ValidationResult(
                    valid=False,
                    errors=[connection_test["error"]],
                    warnings=connection_test.get("warnings", [])
                )

            return ValidationResult(
                valid=True,
                errors=[],
                warnings=connection_test.get("warnings", [])
            )

        except Exception as e:
            logger.error(f"Error validating HTTP source {source.location}: {e}")
            return ValidationResult(
                valid=False,
                errors=[f"HTTP validation error: {str(e)}"],
                warnings=[]
            )

    async def list_files(
        self,
        source: UploadSource,
        recursive: bool = False
    ) -> AsyncGenerator[str]:
        """List files available from HTTP source (single URL only)"""
        # HTTP sources typically represent single files
        # Directory listing is not standard for HTTP
        yield source.location

    async def download_file(
        self,
        source: UploadSource,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> bool:
        """Download file from HTTP source"""
        try:
            client = await self._get_http_client(source)

            # Prepare request headers
            headers = {}
            if source.credentials:
                # Add authorization if provided
                auth_header = self._prepare_auth_header(source.credentials)
                if auth_header:
                    headers.update(auth_header)

            # Check if we should resume download
            resume_offset = 0
            if Path(local_path).exists():
                resume_offset = Path(local_path).stat().st_size
                if resume_offset > 0:
                    headers['Range'] = f'bytes={resume_offset}-'

            # Make request
            async with client.stream('GET', remote_path, headers=headers) as response:

                # Handle HTTP errors
                if response.status_code == 404:
                    logger.error(f"File not found: {remote_path}")
                    return False
                elif response.status_code == 416:  # Range Not Satisfiable
                    logger.info(f"File already completely downloaded: {remote_path}")
                    return True
                elif response.status_code not in [200, 206]:  # 206 = Partial Content
                    logger.error(f"HTTP error {response.status_code} for {remote_path}")
                    return False

                # Get content length for progress tracking
                content_length = response.headers.get('content-length')
                total_size = int(content_length) if content_length else 0

                # If resuming, add offset to total size
                if response.status_code == 206:
                    total_size += resume_offset

                # Ensure destination directory exists
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)

                # Download with progress tracking
                mode = 'ab' if resume_offset > 0 else 'wb'
                bytes_downloaded = resume_offset

                async with aiofiles.open(local_path, mode) as local_file:
                    async for chunk in response.aiter_bytes(chunk_size=64*1024):
                        await local_file.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Report progress
                        if progress_callback and total_size > 0:
                            progress_callback(bytes_downloaded, total_size)

            logger.debug(f"Successfully downloaded {remote_path} to {local_path}")
            return True

        except httpx.TimeoutException as e:
            logger.error(f"HTTP timeout downloading {remote_path}: {e}")
            return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading {remote_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error downloading HTTP file {remote_path}: {e}")
            return False

    async def get_file_info(
        self,
        source: UploadSource,
        remote_path: str
    ) -> dict[str, Any]:
        """Get file metadata from HTTP source using HEAD request"""
        try:
            client = await self._get_http_client(source)

            # Prepare request headers
            headers = {}
            if source.credentials:
                auth_header = self._prepare_auth_header(source.credentials)
                if auth_header:
                    headers.update(auth_header)

            # Make HEAD request to get metadata
            response = await client.head(remote_path, headers=headers)
            response.raise_for_status()

            # Extract file information from headers
            file_info = {
                "filename": self._extract_filename_from_url(remote_path, response.headers),
                "file_path": remote_path,
                "file_size": int(response.headers.get('content-length', 0)),
                "mime_type": response.headers.get('content-type', 'application/octet-stream'),
                "last_modified": response.headers.get('last-modified'),
                "etag": response.headers.get('etag'),
                "server": response.headers.get('server'),
                "accepts_ranges": response.headers.get('accept-ranges', 'none') == 'bytes',
                "is_directory": False
            }

            # Clean up MIME type (remove charset etc.)
            if ';' in file_info["mime_type"]:
                file_info["mime_type"] = file_info["mime_type"].split(';')[0].strip()

            return file_info

        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting file info for {remote_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting HTTP file info for {remote_path}: {e}")
            raise

    async def test_connection(self, source: UploadSource) -> bool:
        """Test HTTP connection"""
        result = await self._test_http_connection(source)
        return result["success"]

    def supports_resume(self) -> bool:
        """HTTP supports resuming via Range requests"""
        return True

    def requires_authentication(self) -> bool:
        """HTTP may require authentication"""
        return False  # Optional

    async def _get_http_client(self, source: UploadSource) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        client_key = f"{source.location}:{id(source.credentials) if source.credentials else 'none'}"

        if client_key not in self._client_pool:
            # Client configuration
            client_config = {
                "timeout": httpx.Timeout(30.0, connect=10.0),
                "follow_redirects": True,
                "limits": httpx.Limits(max_connections=10, max_keepalive_connections=5)
            }

            # SSL verification
            if source.location.startswith('https://'):
                verify_ssl = source.connection_params.get('verify_ssl', True) if source.connection_params else True
                client_config["verify"] = verify_ssl

            # Create client
            client = httpx.AsyncClient(**client_config)
            self._client_pool[client_key] = client

        return self._client_pool[client_key]

    async def _test_http_connection(self, source: UploadSource) -> dict[str, Any]:
        """Test HTTP connection and return result"""
        try:
            client = await self._get_http_client(source)

            # Prepare request headers
            headers = {}
            if source.credentials:
                auth_header = self._prepare_auth_header(source.credentials)
                if auth_header:
                    headers.update(auth_header)

            # Make HEAD request
            response = await client.head(source.location, headers=headers)

            warnings = []

            # Check for potential issues
            if response.status_code == 200:
                # Check if server supports range requests
                if response.headers.get('accept-ranges') != 'bytes':
                    warnings.append("Server does not support range requests (resume not available)")

                # Check SSL certificate for HTTPS
                if source.location.startswith('https://'):
                    # httpx handles SSL verification automatically
                    pass

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "content_length": response.headers.get('content-length'),
                    "content_type": response.headers.get('content-type'),
                    "warnings": warnings,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.reason_phrase}"
                }

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except httpx.ConnectError as e:
            error_msg = f"Connection failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except httpx.TimeoutException as e:
            error_msg = f"Connection timeout: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"HTTP connection failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _prepare_auth_header(self, credentials: dict[str, str]) -> dict[str, str] | None:
        """Prepare authentication header from credentials"""
        auth_type = credentials.get("auth_type", "basic").lower()

        if auth_type == "basic":
            username = credentials.get("username")
            password = credentials.get("password")

            if username and password:
                import base64
                auth_string = f"{username}:{password}"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                return {"Authorization": f"Basic {encoded_auth}"}

        elif auth_type == "bearer":
            token = credentials.get("token")
            if token:
                return {"Authorization": f"Bearer {token}"}

        elif auth_type == "custom":
            # Custom headers
            header_name = credentials.get("header_name")
            header_value = credentials.get("header_value")
            if header_name and header_value:
                return {header_name: header_value}

        return None

    def _extract_filename_from_url(self, url: str, headers: httpx.Headers) -> str:
        """Extract filename from URL or Content-Disposition header"""
        # First try Content-Disposition header
        content_disposition = headers.get('content-disposition')
        if content_disposition and 'filename=' in content_disposition:
            try:
                # Parse filename from header
                import re
                filename_match = re.search(r'filename[*]?=["\']?([^"\';\r\n]+)', content_disposition)
                if filename_match:
                    return filename_match.group(1).strip()
            except Exception:
                pass

        # Fall back to URL path
        parsed = urlparse(url)
        filename = Path(parsed.path).name

        # If no filename in path, generate one
        if not filename or filename == '/':
            # Use domain and generate filename
            domain = parsed.netloc.replace(':', '_').replace('.', '_')
            filename = f"download_{domain}"

        return filename

    async def validate_url(self, url: str) -> ValidationResult:
        """Validate HTTP URL format and accessibility"""
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme.lower() not in ['http', 'https']:
                return ValidationResult.failure([f"Unsupported URL scheme: {parsed.scheme}"])

            # Check netloc
            if not parsed.netloc:
                return ValidationResult.failure(["Invalid URL: missing hostname"])

            # Basic connectivity test
            temp_source = UploadSource(type=UploadSourceType.HTTP, location=url)
            test_result = await self._test_http_connection(temp_source)

            if test_result["success"]:
                return ValidationResult.success(test_result.get("warnings", []))
            else:
                return ValidationResult.failure([test_result["error"]])

        except Exception as e:
            return ValidationResult.failure([f"URL validation error: {str(e)}"])

    async def get_content_info(self, url: str) -> dict[str, Any]:
        """Get content type and size from HTTP headers"""
        temp_source = UploadSource(type=UploadSourceType.HTTP, location=url)
        return await self.get_file_info(temp_source, url)

    async def cleanup(self, source: UploadSource) -> None:
        """Cleanup HTTP clients"""
        # Close all clients in pool
        for client in self._client_pool.values():
            try:
                await client.aclose()
            except (httpx.HTTPError, OSError, RuntimeError):
                pass
        self._client_pool.clear()

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
            client = await self._get_http_client(source)

            # Prepare headers with range request
            headers = {'Range': f'bytes={resume_offset}-'}
            if source.credentials:
                auth_header = self._prepare_auth_header(source.credentials)
                if auth_header:
                    headers.update(auth_header)

            # Make range request
            async with client.stream('GET', remote_path, headers=headers) as response:

                if response.status_code == 416:  # Range Not Satisfiable
                    logger.info(f"File already completely downloaded: {remote_path}")
                    return True
                elif response.status_code != 206:  # Partial Content expected
                    logger.error(f"Server does not support range requests: HTTP {response.status_code}")
                    return False

                # Get content range info
                content_range = response.headers.get('content-range', '')
                total_size = resume_offset  # Default fallback

                if content_range:
                    # Parse "bytes start-end/total" format
                    try:
                        total_size = int(content_range.split('/')[-1])
                    except (ValueError, IndexError):
                        pass

                # Resume download
                bytes_downloaded = resume_offset

                async with aiofiles.open(local_path, 'ab') as local_file:
                    async for chunk in response.aiter_bytes(chunk_size=64*1024):
                        await local_file.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Report progress
                        if progress_callback and total_size > 0:
                            progress_callback(bytes_downloaded, total_size)

            logger.debug(f"Successfully resumed download of {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Error resuming HTTP download {remote_path}: {e}")
            return False
