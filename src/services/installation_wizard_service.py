"""InstallationWizardService orchestrating the setup flow."""
import asyncio
from datetime import datetime
from typing import Any

from src.core.lib_logger import get_logger
from src.models.installation_profile import InstallationProfile, InstallationState
from src.models.service_configuration import ServiceStatus
from src.services.docker_service_manager import DockerServiceManager
from src.services.mcp_configuration_service import MCPConfigurationService
from src.services.progress_tracking_service import ProgressTrackingService
from src.services.qdrant_container_service import QdrantContainerService
from src.services.retry_service import RetryService
from src.services.system_requirements_service import SystemRequirementsService

logger = get_logger(__name__)


class InstallationWizardService:
    """Service orchestrating the complete setup flow."""

    def __init__(self):
        """Initialize installation wizard service."""
        self.system_service = SystemRequirementsService()
        self.docker_manager = DockerServiceManager()
        self.qdrant_service = QdrantContainerService(self.docker_manager)
        self.progress_service = ProgressTrackingService()
        self.retry_service = RetryService()
        self.mcp_service = MCPConfigurationService()

        # Installation steps definition
        self.installation_steps = [
            {"id": "system_check", "name": "Python 3.13+ detected"},
            {"id": "docker_check", "name": "Docker available"},
            {"id": "requirements_validation", "name": "System requirements validation"},
            {"id": "docker_network_setup", "name": "Docker network configuration"},
            {"id": "qdrant_installation", "name": "Qdrant installing"},
            {"id": "qdrant_validation", "name": "Qdrant service validation"},
            {"id": "mcp_config_generation", "name": "MCP configuration generation"},
            {"id": "final_validation", "name": "Installation validation"}
        ]

    async def start_installation(
        self,
        force_reinstall: bool = False,
        custom_qdrant_port: int | None = None,
        custom_data_dir: str | None = None
    ) -> dict[str, Any]:
        """Start the complete installation process."""
        try:
            logger.info("Starting Bablib installation wizard")

            # Create installation profile
            profile = InstallationProfile.create_new()
            profile.state = InstallationState.INSTALLING

            # Initialize progress tracking
            self.progress_service.initialize_steps(self.installation_steps)
            await self.progress_service.start_live_display()

            # Define step functions
            step_functions = {
                "system_check": lambda: self._execute_system_check(),
                "docker_check": lambda: self._execute_docker_check(),
                "requirements_validation": lambda: self._execute_requirements_validation(),
                "docker_network_setup": lambda: self._execute_docker_network_setup(),
                "qdrant_installation": lambda: self._execute_qdrant_installation(
                    force_reinstall, custom_qdrant_port, custom_data_dir
                ),
                "qdrant_validation": lambda: self._execute_qdrant_validation(),
                "mcp_config_generation": lambda: self._execute_mcp_config_generation(),
                "final_validation": lambda: self._execute_final_validation()
            }

            # Execute installation sequence
            results = await self.progress_service.run_installation_sequence(
                step_functions,
                stop_on_failure=True
            )

            # Update profile based on results
            if results["success"]:
                profile.state = InstallationState.COMPLETED
                profile.installation_completed_at = datetime.now()
                profile.services = await self._get_service_configurations()
            else:
                profile.state = InstallationState.FAILED

            # Display final summary
            self.progress_service.display_final_summary()

            # Generate installation report
            installation_report = {
                "profile": profile.to_dict(),
                "results": results,
                "services": profile.services if hasattr(profile, 'services') else [],
                "mcp_config_path": self.mcp_service.get_default_config_path()
            }

            logger.info(f"Installation {'completed' if results['success'] else 'failed'}")
            return installation_report

        except Exception as e:
            logger.error(f"Installation wizard failed: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_system_check(self) -> bool:
        """Execute system requirements check."""
        try:
            python_valid = self.system_service._validate_python_version()
            if python_valid:
                logger.info("Python version check passed")
                return True
            else:
                logger.error("Python version check failed")
                return False

        except Exception as e:
            logger.error(f"System check failed: {e}")
            return False

    async def _execute_docker_check(self) -> bool:
        """Execute Docker availability check."""
        try:
            return await self.retry_service.retry_docker_operation(
                lambda: self.docker_manager.validate_docker_availability()
            )

        except Exception as e:
            logger.error(f"Docker check failed: {e}")
            return False

    async def _execute_requirements_validation(self) -> bool:
        """Execute comprehensive requirements validation."""
        try:
            requirements = await self.system_service.validate_all_requirements()
            critical_requirements = ["python_version", "memory", "docker"]

            for req in critical_requirements:
                if not requirements.get(req, False):
                    logger.error(f"Critical requirement failed: {req}")
                    return False

            logger.info("All critical requirements validated")
            return True

        except Exception as e:
            logger.error(f"Requirements validation failed: {e}")
            return False

    async def _execute_docker_network_setup(self) -> bool:
        """Execute Docker network setup."""
        try:
            # This is handled internally by DockerServiceManager
            # Just validate Docker is ready for container operations
            return await self.docker_manager.validate_docker_availability()

        except Exception as e:
            logger.error(f"Docker network setup failed: {e}")
            return False

    async def _execute_qdrant_installation(
        self,
        force_reinstall: bool,
        custom_port: int | None,
        custom_data_dir: str | None
    ) -> bool:
        """Execute Qdrant installation with retry logic."""
        try:
            installation_result = await self.retry_service.retry_docker_operation(
                lambda: self.qdrant_service.install_qdrant(
                    force_rename=True,
                    custom_port=custom_port,
                    data_dir=custom_data_dir
                )
            )

            if installation_result and installation_result.get("success", False):
                logger.info(f"Qdrant installed successfully: {installation_result['container_name']}")
                return True
            else:
                logger.error(f"Qdrant installation failed: {installation_result}")
                return False

        except Exception as e:
            logger.error(f"Qdrant installation failed: {e}")
            return False

    async def _execute_qdrant_validation(self) -> bool:
        """Execute Qdrant service validation."""
        try:
            # Wait for Qdrant to be fully ready
            await asyncio.sleep(2)

            service_config = await self.qdrant_service.get_qdrant_status()
            if service_config.status == ServiceStatus.RUNNING:
                logger.info("Qdrant validation successful")
                return True
            else:
                logger.error(f"Qdrant validation failed - status: {service_config.status}")
                return False

        except Exception as e:
            logger.error(f"Qdrant validation failed: {e}")
            return False

    async def _execute_mcp_config_generation(self) -> bool:
        """Execute MCP configuration generation."""
        try:
            # Generate universal MCP configuration
            config = self.mcp_service.generate_universal_config(
                server_url="http://localhost:8765",
                capabilities=["search", "crawl", "embed", "status"]
            )

            # Validate configuration
            if not self.mcp_service.validate_config(config):
                logger.error("MCP configuration validation failed")
                return False

            # Save configuration
            config_path = self.mcp_service.get_default_config_path()
            if self.mcp_service.save_config(config, config_path):
                logger.info(f"MCP configuration generated: {config_path}")
                return True
            else:
                logger.error("Failed to save MCP configuration")
                return False

        except Exception as e:
            logger.error(f"MCP configuration generation failed: {e}")
            return False

    async def _execute_final_validation(self) -> bool:
        """Execute final installation validation."""
        try:
            # Validate all services are running
            services = await self._get_service_configurations()

            for service in services:
                if service["status"] not in ["RUNNING", "READY"]:
                    logger.error(f"Service not ready: {service['service_name']} - {service['status']}")
                    return False

            # Validate MCP configuration exists
            config_path = self.mcp_service.get_default_config_path()
            if not config_path.exists():
                logger.error("MCP configuration not found")
                return False

            logger.info("Final validation successful - all services ready")
            return True

        except Exception as e:
            logger.error(f"Final validation failed: {e}")
            return False

    async def _get_service_configurations(self) -> list[dict[str, Any]]:
        """Get current service configurations."""
        try:
            services = []

            # Qdrant service
            qdrant_config = await self.qdrant_service.get_qdrant_status()
            services.append({
                "service_name": qdrant_config.service_name,
                "container_name": qdrant_config.container_name,
                "image": qdrant_config.image,
                "port": qdrant_config.port,
                "status": qdrant_config.status.value,
                "health_check_url": qdrant_config.health_check_url
            })

            return services

        except Exception as e:
            logger.error(f"Failed to get service configurations: {e}")
            return []

    async def check_installation_status(self) -> dict[str, Any]:
        """Check current installation status."""
        try:
            # Check if services are running
            services = await self._get_service_configurations()

            # Check if MCP config exists
            config_path = self.mcp_service.get_default_config_path()
            mcp_config_exists = config_path.exists()

            # Determine overall status
            all_services_running = all(
                service["status"] in ["RUNNING", "READY"] for service in services
            )

            if all_services_running and mcp_config_exists:
                status = "COMPLETED"
            elif len(services) > 0:
                status = "PARTIAL"
            else:
                status = "NOT_INSTALLED"

            return {
                "status": status,
                "services": services,
                "mcp_config_exists": mcp_config_exists,
                "mcp_config_path": str(config_path) if mcp_config_exists else None,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to check installation status: {e}")
            return {"status": "ERROR", "error": str(e)}

    async def uninstall_bablib(self, remove_data: bool = False) -> dict[str, Any]:
        """Uninstall Bablib components."""
        try:
            logger.info("Starting Bablib uninstall")

            results = {"success": True, "removed_components": [], "errors": []}

            # Remove Qdrant
            qdrant_result = await self.qdrant_service.remove_qdrant(remove_data=remove_data)
            if qdrant_result["container_removed"]:
                results["removed_components"].append("qdrant_container")
            if qdrant_result["volume_removed"]:
                results["removed_components"].append("qdrant_data")
            results["errors"].extend(qdrant_result["errors"])

            # Clean up Docker resources
            cleanup_result = await self.docker_manager.cleanup_bablib_resources(
                include_volumes=remove_data
            )
            results["removed_components"].extend([
                f"{cleanup_result['containers']} containers",
                f"{cleanup_result['volumes']} volumes",
                f"{cleanup_result['networks']} networks"
            ])

            # Remove MCP configuration
            config_path = self.mcp_service.get_default_config_path()
            if config_path.exists():
                try:
                    config_path.unlink()
                    results["removed_components"].append("mcp_config")
                except Exception as e:
                    results["errors"].append(f"Failed to remove MCP config: {e}")

            if results["errors"]:
                results["success"] = False

            logger.info(f"Uninstall {'completed' if results['success'] else 'completed with errors'}")
            return results

        except Exception as e:
            logger.error(f"Uninstall failed: {e}")
            return {"success": False, "error": str(e)}

    def get_installation_recommendations(self) -> list[str]:
        """Get installation recommendations based on system state."""
        recommendations = [
            "Ensure Docker Desktop is installed and running",
            "Verify Python 3.13+ is available in PATH",
            "Check that ports 6333 and 8765 are available",
            "Ensure at least 4GB RAM and 2GB disk space are available"
        ]

        return recommendations
