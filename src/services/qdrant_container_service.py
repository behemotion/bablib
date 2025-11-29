"""QdrantContainerService with "bablib-memory-qdrant" naming enforcement."""
import asyncio
from typing import Any

from src.core.lib_logger import get_logger
from src.models.service_configuration import ServiceConfiguration, ServiceStatus
from src.services.docker_service_manager import DockerServiceManager

logger = get_logger(__name__)


class QdrantContainerService:
    """Service for managing Qdrant containers with standardized naming."""

    def __init__(self, docker_manager: DockerServiceManager | None = None):
        """Initialize Qdrant container service."""
        self.docker_manager = docker_manager or DockerServiceManager()
        self.standard_name = "bablib-memory-qdrant"
        self.image = "qdrant/qdrant:v1.12.1"  # Stable version
        self.default_port = 6333
        self.grpc_port = 6334
        self.volume_name = "bablib-qdrant-data"

    async def install_qdrant(
        self,
        force_rename: bool = True,
        custom_port: int | None = None,
        data_dir: str | None = None
    ) -> dict[str, Any]:
        """Install Qdrant with Bablib standard naming."""
        try:
            logger.info("Starting Qdrant installation with Bablib standards")

            # Check for existing containers
            existing_containers = await self._find_existing_qdrant_containers()

            if existing_containers:
                if force_rename:
                    logger.info("Found existing Qdrant containers, applying rename strategy")
                    rename_result = await self._handle_existing_containers(existing_containers)
                    if not rename_result["success"]:
                        return {
                            "success": False,
                            "error": "Failed to handle existing containers",
                            "details": rename_result
                        }
                else:
                    return {
                        "success": False,
                        "error": "Existing Qdrant containers found. Use force_rename=True to resolve.",
                        "existing_containers": [c["name"] for c in existing_containers]
                    }

            # Set up port mapping
            port = custom_port or self.default_port
            port_mappings = {
                f"{self.default_port}/tcp": port,
                f"{self.grpc_port}/tcp": self.grpc_port
            }

            # Set up volume mapping
            volumes = {}
            if data_dir:
                volumes[data_dir] = {"bind": "/qdrant/storage", "mode": "rw"}
            else:
                # Use Docker volume
                volumes[self.volume_name] = {"bind": "/qdrant/storage", "mode": "rw"}

            # Environment variables for Qdrant configuration
            environment = {
                "QDRANT__SERVICE__HTTP_PORT": str(self.default_port),
                "QDRANT__SERVICE__GRPC_PORT": str(self.grpc_port)
            }

            # Create container
            success, result = await self.docker_manager.create_container(
                image=self.image,
                service_type="qdrant",
                port_mappings=port_mappings,
                environment=environment,
                volumes=volumes,
                force_recreate=True
            )

            if success:
                # Wait for container to be ready
                ready = await self._wait_for_qdrant_ready(timeout=60)

                return {
                    "success": True,
                    "container_name": self.standard_name,
                    "image": self.image,
                    "port": port,
                    "grpc_port": self.grpc_port,
                    "ready": ready,
                    "url": f"http://localhost:{port}",
                    "data_volume": self.volume_name if not data_dir else data_dir
                }
            else:
                return {
                    "success": False,
                    "error": f"Container creation failed: {result}"
                }

        except Exception as e:
            logger.error(f"Qdrant installation failed: {e}")
            return {
                "success": False,
                "error": f"Installation failed: {e}"
            }

    async def _find_existing_qdrant_containers(self) -> list[dict[str, Any]]:
        """Find existing Qdrant containers."""
        try:
            all_containers = await self.docker_manager.list_bablib_containers()
            qdrant_containers = []

            for container in all_containers:
                # Check if it's Qdrant by image or name
                if (
                    "qdrant" in container["image"].lower() or
                    "qdrant" in container["name"].lower() or
                    container["name"] == self.standard_name
                ):
                    qdrant_containers.append(container)

            return qdrant_containers

        except Exception as e:
            logger.error(f"Failed to find existing Qdrant containers: {e}")
            return []

    async def _handle_existing_containers(self, containers: list[dict[str, Any]]) -> dict[str, Any]:
        """Handle existing Qdrant containers by renaming or removing."""
        results = {"success": True, "renamed": [], "removed": [], "errors": []}

        try:
            for container in containers:
                container_name = container["name"]

                if container_name == self.standard_name:
                    # This is already using standard naming, check if it should be recreated
                    if container["status"] != "running":
                        # Remove stopped container to recreate
                        if await self.docker_manager.remove_container(container_name, force=True):
                            results["removed"].append(container_name)
                        else:
                            results["errors"].append(f"Failed to remove {container_name}")
                    else:
                        # Container is running with standard name - keep it
                        logger.info(f"Qdrant container already running with standard name: {container_name}")
                        continue
                else:
                    # Try to rename to backup name
                    backup_name = f"{container_name}-backup-{int(asyncio.get_event_loop().time())}"

                    if await self.docker_manager.rename_container(container_name, backup_name):
                        results["renamed"].append(f"{container_name} -> {backup_name}")
                        logger.info(f"Renamed existing container: {container_name} -> {backup_name}")
                    else:
                        # If rename fails, try to remove
                        if await self.docker_manager.remove_container(container_name, force=True):
                            results["removed"].append(container_name)
                            logger.info(f"Removed existing container: {container_name}")
                        else:
                            results["errors"].append(f"Failed to handle {container_name}")
                            results["success"] = False

            return results

        except Exception as e:
            logger.error(f"Failed to handle existing containers: {e}")
            return {"success": False, "error": str(e)}

    async def _wait_for_qdrant_ready(self, timeout: int = 60) -> bool:
        """Wait for Qdrant to be ready to accept connections."""
        import aiohttp

        url = f"http://localhost:{self.default_port}/health"
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            logger.info("Qdrant is ready")
                            return True
            except Exception:
                pass

            await asyncio.sleep(2)

        logger.warning(f"Qdrant not ready after {timeout} seconds")
        return False

    async def get_qdrant_status(self) -> ServiceConfiguration:
        """Get Qdrant service status."""
        try:
            container_status = await self.docker_manager.get_container_status(self.standard_name)

            # Check if service is responsive
            is_responsive = False
            if container_status == ServiceStatus.RUNNING:
                is_responsive = await self._check_qdrant_health()

            service_config = ServiceConfiguration(
                service_name="qdrant",
                container_name=self.standard_name,
                image=self.image,
                port=self.default_port,
                status=container_status,
                health_check_url=f"http://localhost:{self.default_port}/health",
                config_path="/qdrant/config/config.yaml"
            )

            return service_config

        except Exception as e:
            logger.error(f"Failed to get Qdrant status: {e}")
            return ServiceConfiguration(
                service_name="qdrant",
                container_name=self.standard_name,
                status=ServiceStatus.ERROR
            )

    async def _check_qdrant_health(self) -> bool:
        """Check Qdrant health endpoint."""
        import aiohttp

        try:
            url = f"http://localhost:{self.default_port}/health"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except Exception:
            return False

    async def start_qdrant(self) -> bool:
        """Start Qdrant container."""
        try:
            success = await self.docker_manager.start_container(self.standard_name)
            if success:
                # Wait for readiness
                ready = await self._wait_for_qdrant_ready(timeout=30)
                if ready:
                    logger.info("Qdrant started and ready")
                else:
                    logger.warning("Qdrant started but not ready")
                return success
            return False

        except Exception as e:
            logger.error(f"Failed to start Qdrant: {e}")
            return False

    async def stop_qdrant(self) -> bool:
        """Stop Qdrant container."""
        try:
            return await self.docker_manager.stop_container(self.standard_name)
        except Exception as e:
            logger.error(f"Failed to stop Qdrant: {e}")
            return False

    async def remove_qdrant(self, remove_data: bool = False) -> dict[str, Any]:
        """Remove Qdrant container and optionally data."""
        try:
            results = {"container_removed": False, "volume_removed": False, "errors": []}

            # Remove container
            if await self.docker_manager.remove_container(self.standard_name, force=True):
                results["container_removed"] = True
                logger.info(f"Qdrant container removed: {self.standard_name}")
            else:
                results["errors"].append("Failed to remove container")

            # Remove volume if requested
            if remove_data:
                try:
                    client = self.docker_manager._get_client()
                    volume = client.volumes.get(self.volume_name)
                    volume.remove()
                    results["volume_removed"] = True
                    logger.info(f"Qdrant data volume removed: {self.volume_name}")
                except Exception as e:
                    results["errors"].append(f"Failed to remove volume: {e}")

            return results

        except Exception as e:
            logger.error(f"Failed to remove Qdrant: {e}")
            return {"container_removed": False, "volume_removed": False, "errors": [str(e)]}

    async def get_qdrant_info(self) -> dict[str, Any]:
        """Get detailed Qdrant information."""
        try:
            service_config = await self.get_qdrant_status()

            info = {
                "service_name": "qdrant",
                "container_name": self.standard_name,
                "image": self.image,
                "status": service_config.status.value,
                "ports": {
                    "http": self.default_port,
                    "grpc": self.grpc_port
                },
                "urls": {
                    "http": f"http://localhost:{self.default_port}",
                    "grpc": f"http://localhost:{self.grpc_port}",
                    "dashboard": f"http://localhost:{self.default_port}/dashboard"
                },
                "data_volume": self.volume_name,
                "health_check": f"http://localhost:{self.default_port}/health"
            }

            # Add container logs if running
            if service_config.status == ServiceStatus.RUNNING:
                logs = await self.docker_manager.get_container_logs(self.standard_name, tail=20)
                info["recent_logs"] = logs.split('\n')[-20:] if logs else []

            return info

        except Exception as e:
            logger.error(f"Failed to get Qdrant info: {e}")
            return {"error": str(e)}

    def get_connection_config(self) -> dict[str, Any]:
        """Get Qdrant connection configuration for clients."""
        return {
            "host": "localhost",
            "port": self.default_port,
            "grpc_port": self.grpc_port,
            "url": f"http://localhost:{self.default_port}",
            "api_key": None,  # Default Qdrant doesn't use API key
            "timeout": 30,
            "prefer_grpc": False
        }
