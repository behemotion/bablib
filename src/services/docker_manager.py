"""Docker container management service for Bablib setup logic.

This service handles Docker container lifecycle management for vector storage components,
specifically Qdrant containers used by Bablib.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

try:
    from docker.errors import APIError, DockerException, NotFound
    from docker.models.containers import Container

    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    # Handle case where docker package is not installed
    docker = None
    Container = None
    DockerException = Exception
    NotFound = Exception
    APIError = Exception
    DOCKER_AVAILABLE = False

from ..models.setup_types import ExternalDependencyError
from ..models.setup_types import TimeoutError as SetupTimeoutError
from .docker_compatibility import DockerAPICompatibility, DockerManagerCompatible

logger = logging.getLogger(__name__)


def check_docker_availability() -> tuple[bool, str]:
    """Check if Docker and Docker Compose are available on the system.

    Returns:
        tuple: (is_available, message)
    """
    import shutil
    import subprocess

    # Check if docker command exists
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        return False, "Docker command not found. Please install Docker from https://docs.docker.com/get-docker/"

    # Check if docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, "Docker daemon not running. Please start Docker service."
    except subprocess.TimeoutExpired:
        return False, "Docker command timed out. Please check Docker installation."
    except Exception as e:
        return False, f"Docker check failed: {e}"

    # Check for docker compose
    compose_available = False
    compose_cmd = None

    # Try docker compose (newer syntax)
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            compose_available = True
            compose_cmd = "docker compose"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # Try docker-compose (legacy syntax) if docker compose failed
    if not compose_available:
        try:
            result = subprocess.run(
                ["docker-compose", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                compose_available = True
                compose_cmd = "docker-compose"
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

    if not compose_available:
        return False, "Docker Compose not found. Please install Docker Compose."

    return True, f"Docker and Docker Compose ({compose_cmd}) are available"


async def run_qdrant_container(
    container_name: str = "bablib-qdrant",
    port: int = 6333,
    image: str = "qdrant/qdrant:latest"
) -> tuple[bool, str]:
    """Start Qdrant container using subprocess (no Docker Python package needed).

    Returns:
        tuple: (success, message)
    """
    import subprocess

    try:
        # Check if container already exists and is running
        check_cmd = ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"]
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and container_name in result.stdout:
            return True, f"Qdrant container '{container_name}' is already running"

        # Check if container exists but is stopped
        check_all_cmd = ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"]
        result = subprocess.run(check_all_cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and container_name in result.stdout:
            # Start existing container
            start_cmd = ["docker", "start", container_name]
            result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return True, f"Started existing Qdrant container '{container_name}'"
            else:
                return False, f"Failed to start container: {result.stderr}"

        # Create and run new container
        run_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:6333",
            image
        ]

        result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            container_id = result.stdout.strip()[:12]  # First 12 chars of container ID
            return True, f"Created and started Qdrant container '{container_name}' ({container_id})"
        else:
            return False, f"Failed to create container: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except Exception as e:
        return False, f"Error running Docker command: {e}"


async def stop_qdrant_container(container_name: str = "bablib-qdrant") -> tuple[bool, str]:
    """Stop Qdrant container using subprocess.

    Returns:
        tuple: (success, message)
    """
    import subprocess

    try:
        stop_cmd = ["docker", "stop", container_name]
        result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return True, f"Stopped Qdrant container '{container_name}'"
        else:
            # Container might not exist or already stopped
            if "No such container" in result.stderr:
                return True, f"Container '{container_name}' does not exist"
            else:
                return False, f"Failed to stop container: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Docker stop command timed out"
    except Exception as e:
        return False, f"Error stopping container: {e}"


class DockerManager:
    """Manages Docker container operations for Bablib setup."""

    def __init__(self):
        """Initialize Docker client."""
        self._client: Any | None = None
        self._connected = False
        self._compat_manager = DockerManagerCompatible()
        self._api_compat = DockerAPICompatibility()

    async def connect(self, timeout: float = 5.0) -> bool:
        """Connect to Docker daemon with timeout and version compatibility.

        Args:
            timeout: Connection timeout in seconds (default 5.0)
        """
        if not DOCKER_AVAILABLE:
            raise ExternalDependencyError("Docker Python package not available. Advanced Docker operations unavailable.")

        try:
            # First try the compatibility manager
            connected = await self._compat_manager.connect(timeout=timeout)
            if connected:
                self._client = self._compat_manager.client
                self._connected = True
                logger.info(f"Connected to Docker daemon with API version: {self._compat_manager.compat.negotiated_version}")
                return True

            # Fallback to traditional method if compatibility layer fails
            self._client = docker.from_env()
            # Test connection with timeout
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, self._client.ping),
                    timeout=timeout
                )
            except TimeoutError:
                logger.warning(f"Docker connection timed out after {timeout} seconds")
                raise ExternalDependencyError(f"Docker daemon not responding (timeout after {timeout}s)")

            self._connected = True
            logger.info("Connected to Docker daemon")
            return True
        except DockerException as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            # Check if it's an API version mismatch
            if "api version" in str(e).lower() or "500" in str(e):
                logger.info("Attempting version compatibility workaround...")
                # Try with compatibility layer again with explicit versions
                connected = await self._compat_manager.connect(timeout=timeout * 2)
                if connected:
                    self._client = self._compat_manager.client
                    self._connected = True
                    return True
            raise ExternalDependencyError(f"Docker daemon not available: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to Docker: {e}")
            raise ExternalDependencyError(f"Docker connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Docker daemon."""
        if self._client:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._client.close)
            except Exception as e:
                logger.warning(f"Error closing Docker client: {e}")
            finally:
                self._client = None
                self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to Docker daemon."""
        return self._connected and self._client is not None

    async def get_docker_version(self) -> dict[str, Any]:
        """Get Docker version information."""
        if not self.is_connected():
            await self.connect()

        try:
            version_info = await asyncio.get_event_loop().run_in_executor(
                None, self._client.version
            )
            return version_info
        except DockerException as e:
            logger.error(f"Failed to get Docker version: {e}")
            raise ExternalDependencyError(f"Cannot get Docker version: {e}")

    async def check_docker_health(self) -> dict[str, Any]:
        """Check Docker daemon health with timeout protection."""
        try:
            # Use timeout for the entire health check
            async def _do_health_check():
                if not self.is_connected():
                    await self.connect(timeout=5.0)

                version = await self.get_docker_version()

                return {
                    "available": True,
                    "version": version.get("Version", "unknown"),
                    "api_version": version.get("ApiVersion", "unknown"),
                    "platform": version.get("Os", "unknown"),
                    "architecture": version.get("Arch", "unknown"),
                    "health_status": "healthy"
                }

            # Apply timeout to entire health check operation
            try:
                return await asyncio.wait_for(_do_health_check(), timeout=10.0)
            except TimeoutError:
                logger.warning("Docker health check timed out")
                return {
                    "available": False,
                    "version": None,
                    "health_status": "timeout",
                    "error": "Docker health check timed out after 10 seconds"
                }

        except ExternalDependencyError as e:
            return {
                "available": False,
                "version": None,
                "health_status": "unhealthy",
                "error": str(e)
            }
        except Exception as e:
            return {
                "available": False,
                "version": None,
                "health_status": "unhealthy",
                "error": f"Docker health check failed: {e}"
            }

    async def find_container(self, name: str) -> Container | None:
        """Find container by name."""
        if not self.is_connected():
            await self.connect()

        try:
            containers = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._client.containers.list(all=True)
            )

            for container in containers:
                if container.name == name or name in container.name:
                    return container
            return None

        except DockerException as e:
            logger.error(f"Failed to list containers: {e}")
            raise ExternalDependencyError(f"Cannot list Docker containers: {e}")

    async def get_container_status(self, name: str) -> dict[str, Any]:
        """Get container status information."""
        container = await self.find_container(name)

        if not container:
            return {
                "exists": False,
                "status": None,
                "health": None,
                "container_id": None
            }

        try:
            # Refresh container info
            await asyncio.get_event_loop().run_in_executor(None, container.reload)

            return {
                "exists": True,
                "status": container.status,
                "health": container.attrs.get("State", {}).get("Health", {}).get("Status"),
                "container_id": container.id,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "created": container.attrs.get("Created"),
                "ports": container.ports
            }

        except DockerException as e:
            logger.error(f"Failed to get container status: {e}")
            return {
                "exists": True,
                "status": "error",
                "health": "unknown",
                "container_id": container.id if container else None,
                "error": str(e)
            }

    async def create_qdrant_container(
        self,
        container_name: str = "bablib-memory-qdrant",
        port: int = 6333,
        data_path: Path | None = None,
        image: str = "qdrant/qdrant:v1.15.4"
    ) -> dict[str, Any]:
        """Create and start Qdrant container."""
        if not self.is_connected():
            await self.connect()

        try:
            # Check if container already exists
            existing_container = await self.find_container(container_name)
            if existing_container:
                logger.warning(f"Container {container_name} already exists")
                return await self.get_container_status(container_name)

            # Prepare volume mounts
            volumes = {}
            if data_path:
                data_path.mkdir(parents=True, exist_ok=True)
                volumes[str(data_path)] = {"bind": "/qdrant/storage", "mode": "rw"}

            # Container configuration
            container_config = {
                "image": image,
                "name": container_name,
                "ports": {f"{port}/tcp": port},
                "volumes": volumes,
                "detach": True,
                "restart_policy": {"Name": "unless-stopped"},
                "environment": {
                    "QDRANT__SERVICE__HTTP_PORT": str(port),
                    "QDRANT__SERVICE__GRPC_PORT": str(port + 1)
                }
            }

            logger.info(f"Creating Qdrant container: {container_name}")

            # Pull image if needed
            logger.info(f"Pulling Qdrant image: {image}")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._client.images.pull(image)
            )

            # Create and start container
            container = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._client.containers.run(**container_config)
            )

            # Wait for container to be healthy
            await self._wait_for_container_health(container, timeout=60)

            logger.info(f"Qdrant container created successfully: {container.id}")

            return {
                "status": "success",
                "container_id": container.id,
                "container_name": container_name,
                "port": port,
                "image": image,
                "data_path": str(data_path) if data_path else None
            }

        except DockerException as e:
            logger.error(f"Failed to create Qdrant container: {e}")
            raise ExternalDependencyError(f"Cannot create Qdrant container: {e}")

    async def stop_container(self, name: str, timeout: int = 10) -> bool:
        """Stop container gracefully."""
        container = await self.find_container(name)
        if not container:
            logger.warning(f"Container {name} not found")
            return True

        try:
            logger.info(f"Stopping container: {name}")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: container.stop(timeout=timeout)
            )
            return True
        except DockerException as e:
            logger.error(f"Failed to stop container {name}: {e}")
            return False

    async def remove_container(self, name: str, force: bool = False) -> bool:
        """Remove container."""
        container = await self.find_container(name)
        if not container:
            logger.warning(f"Container {name} not found")
            return True

        try:
            # Stop first if running
            if container.status == "running":
                await self.stop_container(name)

            logger.info(f"Removing container: {name}")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: container.remove(force=force)
            )
            return True
        except DockerException as e:
            logger.error(f"Failed to remove container {name}: {e}")
            return False

    async def recreate_qdrant_container(
        self,
        container_name: str = "bablib-memory-qdrant",
        **kwargs
    ) -> dict[str, Any]:
        """Recreate Qdrant container (remove old, create new)."""
        logger.info(f"Recreating Qdrant container: {container_name}")

        # Remove existing container
        removed = await self.remove_container(container_name, force=True)
        if not removed:
            raise ExternalDependencyError(f"Failed to remove existing container: {container_name}")

        # Create new container
        return await self.create_qdrant_container(container_name=container_name, **kwargs)

    async def _wait_for_container_health(self, container: Container, timeout: int = 60) -> None:
        """Wait for container to become healthy."""
        start_time = asyncio.get_event_loop().time()

        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(None, container.reload)

                if container.status == "running":
                    # For containers without health checks, consider running as healthy
                    health_status = container.attrs.get("State", {}).get("Health", {}).get("Status")
                    if health_status in ["healthy", None]:  # None means no health check defined
                        logger.info(f"Container {container.name} is healthy")
                        return
                    elif health_status == "unhealthy":
                        raise ExternalDependencyError(f"Container {container.name} is unhealthy")

                elif container.status in ["exited", "dead"]:
                    logs = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: container.logs(tail=50).decode()
                    )
                    raise ExternalDependencyError(
                        f"Container {container.name} failed to start. Status: {container.status}\n"
                        f"Logs:\n{logs}"
                    )

                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise SetupTimeoutError(
                        f"Container {container.name} did not become healthy within {timeout} seconds"
                    )

                await asyncio.sleep(2)  # Check every 2 seconds

            except DockerException as e:
                raise ExternalDependencyError(f"Error checking container health: {e}")

    async def get_container_logs(self, name: str, tail: int = 50) -> str:
        """Get container logs."""
        container = await self.find_container(name)
        if not container:
            return f"Container {name} not found"

        try:
            logs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: container.logs(tail=tail).decode('utf-8', errors='replace')
            )
            return logs
        except DockerException as e:
            logger.error(f"Failed to get logs for container {name}: {e}")
            return f"Error getting logs: {e}"

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
