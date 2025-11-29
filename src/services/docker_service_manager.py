"""DockerServiceManager for container lifecycle and standardized naming."""
from typing import Any

from docker.models.containers import Container

import docker
from src.core.lib_logger import get_logger
from src.models.service_configuration import ServiceStatus

logger = get_logger(__name__)


class DockerServiceManager:
    """Service for managing Docker containers with standardized naming."""

    def __init__(self):
        """Initialize Docker service manager."""
        self.client = None
        self.standard_naming = {
            "qdrant": "bablib-memory-qdrant",
            "redis": "bablib-cache-redis",
            "bablib": "bablib-main"
        }
        self.network_name = "bablib-network"

    def _get_client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self.client is None:
            try:
                self.client = docker.from_env()
                # Test connection
                self.client.ping()
                logger.info("Connected to Docker daemon")
            except Exception as e:
                logger.error(f"Failed to connect to Docker: {e}")
                raise

        return self.client

    async def validate_docker_availability(self) -> bool:
        """Validate Docker daemon is available."""
        try:
            client = self._get_client()
            client.ping()
            logger.info("Docker validation successful")
            return True
        except Exception as e:
            logger.error(f"Docker validation failed: {e}")
            return False

    async def create_container(
        self,
        image: str,
        service_type: str,
        port_mappings: dict[str, str] | None = None,
        environment: dict[str, str] | None = None,
        volumes: dict[str, str] | None = None,
        force_recreate: bool = False
    ) -> tuple[bool, str]:
        """Create container with standardized naming."""
        try:
            client = self._get_client()

            # Get standardized container name
            container_name = self.standard_naming.get(service_type, f"bablib-{service_type}")

            # Check if container already exists
            existing_container = self._get_container_by_name(container_name)
            if existing_container:
                if force_recreate:
                    logger.info(f"Removing existing container: {container_name}")
                    await self.remove_container(container_name, force=True)
                else:
                    logger.info(f"Container already exists: {container_name}")
                    return True, container_name

            # Ensure network exists
            await self._ensure_network_exists()

            # Prepare container configuration
            container_config = {
                "image": image,
                "name": container_name,
                "network": self.network_name,
                "detach": True,
                "restart_policy": {"Name": "unless-stopped"}
            }

            if port_mappings:
                container_config["ports"] = port_mappings

            if environment:
                container_config["environment"] = environment

            if volumes:
                container_config["volumes"] = volumes

            # Create container
            logger.info(f"Creating container: {container_name} from image: {image}")
            container = client.containers.run(**container_config)

            logger.info(f"Container created successfully: {container_name}")
            return True, container_name

        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            return False, str(e)

    async def start_container(self, container_name: str) -> bool:
        """Start container by name."""
        try:
            client = self._get_client()
            container = client.containers.get(container_name)

            if container.status != "running":
                container.start()
                logger.info(f"Container started: {container_name}")
            else:
                logger.info(f"Container already running: {container_name}")

            return True

        except docker.errors.NotFound:
            logger.error(f"Container not found: {container_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to start container {container_name}: {e}")
            return False

    async def stop_container(self, container_name: str, timeout: int = 10) -> bool:
        """Stop container by name."""
        try:
            client = self._get_client()
            container = client.containers.get(container_name)

            if container.status == "running":
                container.stop(timeout=timeout)
                logger.info(f"Container stopped: {container_name}")
            else:
                logger.info(f"Container not running: {container_name}")

            return True

        except docker.errors.NotFound:
            logger.error(f"Container not found: {container_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to stop container {container_name}: {e}")
            return False

    async def remove_container(self, container_name: str, force: bool = False) -> bool:
        """Remove container by name."""
        try:
            client = self._get_client()
            container = client.containers.get(container_name)

            # Stop if running
            if container.status == "running" and not force:
                await self.stop_container(container_name)

            container.remove(force=force)
            logger.info(f"Container removed: {container_name}")
            return True

        except docker.errors.NotFound:
            logger.info(f"Container not found (already removed): {container_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container {container_name}: {e}")
            return False

    async def get_container_status(self, container_name: str) -> ServiceStatus:
        """Get container status."""
        try:
            client = self._get_client()
            container = client.containers.get(container_name)

            status_mapping = {
                "running": ServiceStatus.RUNNING,
                "exited": ServiceStatus.STOPPED,
                "created": ServiceStatus.STOPPED,
                "restarting": ServiceStatus.STARTING,
                "paused": ServiceStatus.STOPPED,
                "dead": ServiceStatus.ERROR
            }

            return status_mapping.get(container.status, ServiceStatus.UNKNOWN)

        except docker.errors.NotFound:
            return ServiceStatus.NOT_INSTALLED
        except Exception as e:
            logger.error(f"Failed to get container status {container_name}: {e}")
            return ServiceStatus.ERROR

    async def list_bablib_containers(self) -> list[dict[str, Any]]:
        """List all Bablib-related containers."""
        try:
            client = self._get_client()
            containers = client.containers.list(all=True)

            bablib_containers = []
            for container in containers:
                if any(keyword in container.name.lower() for keyword in ["bablib", "qdrant", "redis"]):
                    bablib_containers.append({
                        "name": container.name,
                        "id": container.id[:12],
                        "status": container.status,
                        "image": container.image.tags[0] if container.image.tags else "unknown",
                        "ports": self._format_ports(container.ports),
                        "created": container.attrs["Created"]
                    })

            return bablib_containers

        except Exception as e:
            logger.error(f"Failed to list Bablib containers: {e}")
            return []

    def _format_ports(self, ports_dict: dict) -> str:
        """Format port mappings for display."""
        if not ports_dict:
            return "No ports"

        port_strings = []
        for internal_port, external_bindings in ports_dict.items():
            if external_bindings:
                external_port = external_bindings[0]["HostPort"]
                port_strings.append(f"{external_port}:{internal_port}")
            else:
                port_strings.append(internal_port)

        return ", ".join(port_strings)

    def _get_container_by_name(self, name: str) -> Container | None:
        """Get container by name."""
        try:
            client = self._get_client()
            return client.containers.get(name)
        except docker.errors.NotFound:
            return None
        except Exception:
            return None

    async def _ensure_network_exists(self) -> None:
        """Ensure Bablib network exists."""
        try:
            client = self._get_client()

            # Check if network exists
            try:
                client.networks.get(self.network_name)
                logger.debug(f"Network exists: {self.network_name}")
            except docker.errors.NotFound:
                # Create network
                client.networks.create(
                    self.network_name,
                    driver="bridge",
                    check_duplicate=True
                )
                logger.info(f"Network created: {self.network_name}")

        except Exception as e:
            logger.error(f"Failed to ensure network exists: {e}")
            raise

    async def rename_container(
        self,
        current_name: str,
        new_name: str | None = None,
        service_type: str | None = None
    ) -> bool:
        """Rename container to follow Bablib naming standards."""
        try:
            client = self._get_client()

            # Get new name from service type if not provided
            if not new_name and service_type:
                new_name = self.standard_naming.get(service_type, f"bablib-{service_type}")

            if not new_name:
                logger.error("No new name provided for container rename")
                return False

            # Get container
            container = client.containers.get(current_name)

            # Check if target name already exists
            if self._get_container_by_name(new_name):
                logger.warning(f"Target name already exists: {new_name}")
                return False

            # Rename container
            container.rename(new_name)
            logger.info(f"Container renamed: {current_name} -> {new_name}")
            return True

        except docker.errors.NotFound:
            logger.error(f"Container not found: {current_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to rename container {current_name}: {e}")
            return False

    async def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        """Get container logs."""
        try:
            client = self._get_client()
            container = client.containers.get(container_name)

            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8')

        except docker.errors.NotFound:
            return f"Container not found: {container_name}"
        except Exception as e:
            logger.error(f"Failed to get logs for {container_name}: {e}")
            return f"Error getting logs: {e}"

    async def cleanup_bablib_resources(self, include_volumes: bool = False) -> dict[str, int]:
        """Clean up all Bablib-related Docker resources."""
        results = {"containers": 0, "volumes": 0, "networks": 0}

        try:
            client = self._get_client()

            # Remove containers
            containers = await self.list_bablib_containers()
            for container_info in containers:
                if await self.remove_container(container_info["name"], force=True):
                    results["containers"] += 1

            # Remove volumes if requested
            if include_volumes:
                volumes = client.volumes.list()
                for volume in volumes:
                    if "bablib" in volume.name.lower():
                        try:
                            volume.remove()
                            results["volumes"] += 1
                            logger.info(f"Volume removed: {volume.name}")
                        except Exception as e:
                            logger.warning(f"Failed to remove volume {volume.name}: {e}")

            # Remove network
            try:
                network = client.networks.get(self.network_name)
                network.remove()
                results["networks"] += 1
                logger.info(f"Network removed: {self.network_name}")
            except docker.errors.NotFound:
                pass
            except Exception as e:
                logger.warning(f"Failed to remove network {self.network_name}: {e}")

            logger.info(f"Cleanup completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return results
