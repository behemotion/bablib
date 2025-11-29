"""Docker utilities and health checks for Bablib services."""

import asyncio
import logging
import subprocess
import time
from pathlib import Path

import httpx

# Optional Docker imports - only needed when Docker features are used
try:
    from docker.errors import DockerException
    from docker.models.containers import Container

    import docker
    DOCKER_AVAILABLE = True
    ContainerType = Container
except ImportError:
    docker = None
    DockerException = Exception
    Container = None
    DOCKER_AVAILABLE = False
    # Use typing.Any for type hints when Docker is not available
    from typing import Any
    ContainerType = Any

# Optional Qdrant imports - only needed when Qdrant features are used
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import ResponseHandlingException
    QDRANT_AVAILABLE = True
except ImportError:
    QdrantClient = None
    ResponseHandlingException = Exception
    QDRANT_AVAILABLE = False

from .config import BablibConfig, ServiceDeployment

logger = logging.getLogger(__name__)


class DockerServiceManager:
    """Manage Docker services for Bablib."""

    def __init__(self, config: BablibConfig):
        """Initialize with configuration."""
        self.config = config
        self.docker_compose_file = Path("docker/docker-compose.yml")

    def is_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        if not DOCKER_AVAILABLE:
            return False

        try:
            # Try with auto version negotiation
            client = docker.from_env(version='auto')
            client.ping()
            return True
        except DockerException as e:
            # If it's an API version issue, try with compatibility
            if "api version" in str(e).lower() or "500" in str(e):
                try:
                    import os
                    # Try with older API version that's widely compatible
                    os.environ['DOCKER_API_VERSION'] = '1.41'
                    client = docker.from_env()
                    client.ping()
                    os.environ.pop('DOCKER_API_VERSION', None)
                    logger.info("Docker available with API v1.41 compatibility mode")
                    return True
                except DockerException:
                    logger.warning(f"Docker not available even with compatibility mode: {e}")
                    return False
            return False

    def get_service_containers(self) -> dict[str, ContainerType | None]:
        """Get containers for Bablib services."""
        if not self.is_docker_available():
            return {"qdrant": None}

        try:
            client = docker.from_env()
            containers = {"qdrant": None}

            # Look for containers by name patterns
            for container in client.containers.list():
                name = container.name.lower()
                if "qdrant" in name:
                    containers["qdrant"] = container

            return containers
        except DockerException as e:
            logger.error(f"Failed to get Docker containers: {e}")
            return {"qdrant": None}

    def start_services(self, services: list[str] | None = None) -> bool:
        """Start Docker services using docker-compose."""
        if not self.docker_compose_file.exists():
            logger.error(f"Docker compose file not found: {self.docker_compose_file}")
            return False

        cmd = ["docker-compose", "-f", str(self.docker_compose_file), "up", "-d"]
        if services:
            cmd.extend(services)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Started Docker services: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Docker services: {e.stderr}")
            return False

    def stop_services(self, services: list[str] | None = None) -> bool:
        """Stop Docker services using docker-compose."""
        if not self.docker_compose_file.exists():
            logger.error(f"Docker compose file not found: {self.docker_compose_file}")
            return False

        cmd = ["docker-compose", "-f", str(self.docker_compose_file), "down"]
        if services:
            cmd.extend(services)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Stopped Docker services: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop Docker services: {e.stderr}")
            return False

    def get_service_logs(self, service: str, lines: int = 100) -> str:
        """Get logs from a specific service."""
        if not self.docker_compose_file.exists():
            return f"Docker compose file not found: {self.docker_compose_file}"

        cmd = [
            "docker-compose", "-f", str(self.docker_compose_file),
            "logs", "--tail", str(lines), service
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Failed to get logs for {service}: {e.stderr}"

    async def wait_for_services(self, timeout: int = 60) -> dict[str, bool]:
        """Wait for services to become healthy."""
        start_time = time.time()
        health_checker = ServiceHealthChecker(self.config)

        while (time.time() - start_time) < timeout:
            health_status = await health_checker.check_all_services()

            # Check if required services are healthy
            required_services = []
            strategy = self.config.get_effective_deployment_strategy()

            if strategy["qdrant"] == ServiceDeployment.DOCKER:
                required_services.append("qdrant")

            if all(health_status.get(service, False) for service in required_services):
                logger.info("All required Docker services are healthy")
                return health_status

            await asyncio.sleep(2)

        logger.warning(f"Services not ready after {timeout}s timeout")
        return await health_checker.check_all_services()


class ServiceHealthChecker:
    """Check health of Bablib services."""

    def __init__(self, config: BablibConfig):
        """Initialize with configuration."""
        self.config = config

    async def check_qdrant(self) -> tuple[bool, str]:
        """Check Qdrant service health."""
        try:
            client = QdrantClient(url=self.config.qdrant_url)
            client.get_collections()
            return True, "Healthy"
        except ResponseHandlingException as e:
            return False, f"Connection failed: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"


    async def check_ollama(self) -> tuple[bool, str]:
        """Check Ollama service health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.config.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = len(data.get("models", []))
                    return True, f"Healthy ({models} models available)"
                else:
                    return False, f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            return False, "Timeout"
        except Exception as e:
            return False, f"Connection failed: {e}"

    async def check_database(self) -> tuple[bool, str]:
        """Check database connection."""
        try:
            from sqlalchemy import create_engine, text

            # Convert async URL to sync for health check
            db_url = self.config.database_url.replace("+aiosqlite", "")
            engine = create_engine(db_url)

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            engine.dispose()
            return True, "Healthy"
        except Exception as e:
            return False, f"Database error: {e}"

    async def check_all_services(self) -> dict[str, bool]:
        """Check health of all services."""
        tasks = {
            "qdrant": self.check_qdrant(),
            "ollama": self.check_ollama(),
            "database": self.check_database(),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        health_status = {}
        for service, result in zip(tasks.keys(), results, strict=False):
            if isinstance(result, Exception):
                health_status[service] = False
                logger.error(f"Health check failed for {service}: {result}")
            else:
                is_healthy, message = result
                health_status[service] = is_healthy
                if is_healthy:
                    logger.debug(f"{service}: {message}")
                else:
                    logger.warning(f"{service}: {message}")

        return health_status

    async def wait_for_service(self, service: str, timeout: int = 30) -> bool:
        """Wait for a specific service to become healthy."""
        start_time = time.time()

        check_method = getattr(self, f"check_{service}", None)
        if not check_method:
            logger.error(f"Unknown service: {service}")
            return False

        while (time.time() - start_time) < timeout:
            is_healthy, message = await check_method()
            if is_healthy:
                logger.info(f"{service} is healthy: {message}")
                return True

            logger.debug(f"Waiting for {service}: {message}")
            await asyncio.sleep(2)

        logger.error(f"{service} not healthy after {timeout}s timeout")
        return False


class ServiceConnectionManager:
    """Manage connections to Bablib services with automatic retry and failover."""

    def __init__(self, config: BablibConfig):
        """Initialize with configuration."""
        self.config = config
        self.health_checker = ServiceHealthChecker(config)
        self._connections = {}

    async def get_qdrant_client(self) -> QdrantClient:
        """Get Qdrant client with connection validation."""
        if "qdrant" not in self._connections:
            client = QdrantClient(url=self.config.qdrant_url)

            # Validate connection
            try:
                client.get_collections()
                self._connections["qdrant"] = client
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                raise ConnectionError(f"Qdrant connection failed: {e}")

        return self._connections["qdrant"]


    async def get_ollama_client(self) -> httpx.AsyncClient:
        """Get Ollama HTTP client with connection validation."""
        if "ollama" not in self._connections:
            client = httpx.AsyncClient(
                base_url=self.config.ollama_url,
                timeout=self.config.ollama_timeout
            )

            # Validate connection
            try:
                response = await client.get("/api/tags")
                if response.status_code != 200:
                    raise ConnectionError(f"Ollama HTTP {response.status_code}")
                self._connections["ollama"] = client
            except Exception as e:
                logger.error(f"Failed to connect to Ollama: {e}")
                raise ConnectionError(f"Ollama connection failed: {e}")

        return self._connections["ollama"]

    async def close_all_connections(self):
        """Close all active connections."""
        for service, connection in self._connections.items():
            try:
                if service == "ollama" and hasattr(connection, "aclose"):
                    await connection.aclose()
                elif hasattr(connection, "close"):
                    connection.close()
            except Exception as e:
                logger.warning(f"Error closing {service} connection: {e}")

        self._connections.clear()

    async def test_all_connections(self) -> dict[str, bool]:
        """Test all service connections."""
        return await self.health_checker.check_all_services()
