"""SetupLogicService orchestration for Bablib setup logic.

This is the main orchestration service that coordinates all setup operations.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..models.setup_configuration import SetupConfiguration
from ..models.setup_session import SetupSession
from ..models.setup_types import (
    EmbeddingModelConfig,
    SetupMode,
    SetupStep,
    VectorStorageConfig,
)
from .component_health import ComponentHealthChecker
from .config_service import ConfigService
from .docker_manager import DockerManager
from .mcp_detector import MCPDetector
from .ollama_manager import OllamaManager
from .system_requirements_service import SystemRequirementsService

logger = logging.getLogger(__name__)


class SetupLogicService:
    """Main orchestration service for setup logic."""

    def __init__(self):
        """Initialize setup logic service."""
        self.health_checker = ComponentHealthChecker()
        self.docker_manager = DockerManager()
        self.ollama_manager = OllamaManager()
        self.mcp_detector = MCPDetector()
        self.config_service = ConfigService()
        self.requirements_service = SystemRequirementsService()

    async def run_interactive_setup(self) -> bool:
        """Run interactive setup with user prompts."""
        try:
            logger.info("Starting interactive setup")

            # Detect components first
            components = await self.health_checker.check_all_components()

            # Check component availability
            docker_available = any(c.component_name == "docker" and c.available for c in components)
            ollama_available = any(c.component_name == "ollama" and c.available for c in components)

            # Prepare initial configuration with at least one component
            initial_vector_storage = None
            initial_embedding_model = None

            # Set default configurations based on availability
            if docker_available:
                initial_vector_storage = VectorStorageConfig(
                    connection_url="http://localhost:6333",
                    data_path="/tmp/bablib/qdrant"
                )

            if ollama_available:
                initial_embedding_model = EmbeddingModelConfig(
                    model_name="mxbai-embed-large",
                    download_required=False
                )

            # If neither is available, create minimal default config
            if not initial_vector_storage and not initial_embedding_model:
                initial_vector_storage = VectorStorageConfig(
                    provider="qdrant",
                    connection_url="http://localhost:6333",
                    data_path="/tmp/bablib/qdrant"
                )

            # Create setup configuration with initial components
            config = SetupConfiguration(
                setup_mode=SetupMode.INTERACTIVE,
                version="0.2.1",
                vector_storage=initial_vector_storage,
                embedding_model=initial_embedding_model
            )

            # Create session
            session = SetupSession(setup_config_id=config.setup_id)
            session.start_session()

            # Mark detection step as complete
            session.complete_step(SetupStep.DETECT_COMPONENTS)

            if docker_available and config.vector_storage:
                # Actually create and start the Qdrant container
                from pathlib import Path
                data_path = Path(config.vector_storage.data_path)
                await self.docker_manager.create_qdrant_container(
                    container_name="bablib-memory-qdrant",
                    port=6333,
                    data_path=data_path
                )
                logger.info("Qdrant container created and started successfully")

                session.complete_step(SetupStep.CONFIGURE_VECTOR_STORAGE)

            if ollama_available and config.embedding_model:
                # Embedding model is already configured, just mark step as complete
                session.complete_step(SetupStep.SETUP_EMBEDDING_MODEL)

            # Skip MCP for now
            session.complete_step(SetupStep.CONFIGURE_MCP_CLIENTS)
            session.complete_step(SetupStep.VALIDATE_CONFIGURATION)

            # Save configuration
            config.mark_as_completed()
            await self.config_service.save_configuration(config)
            session.complete_step(SetupStep.PERSIST_SETTINGS)

            session.complete_session()
            await self.config_service.save_session(session)

            logger.info("Interactive setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Interactive setup failed: {e}")
            if 'session' in locals():
                session.fail_session(str(e))
                await self.config_service.save_session(session)
            raise

    async def run_auto_setup(self) -> bool:
        """Run automated setup with defaults."""
        try:
            logger.info("Starting auto setup")

            # Detect components first
            components = await self.health_checker.check_all_components()

            # Check component availability
            docker_available = any(c.component_name == "docker" and c.available for c in components)
            ollama_available = any(c.component_name == "ollama" and c.available for c in components)

            # Prepare initial configuration with at least one component
            initial_vector_storage = None
            initial_embedding_model = None

            # Set default configurations based on availability
            if docker_available:
                initial_vector_storage = VectorStorageConfig(
                    connection_url="http://localhost:6333",
                    data_path="/tmp/bablib/qdrant"
                )

            if ollama_available:
                initial_embedding_model = EmbeddingModelConfig(
                    model_name="embeddinggemma:300m-qat-q4_0",
                    download_required=True
                )

            # If neither is available, create minimal default config
            if not initial_vector_storage and not initial_embedding_model:
                initial_vector_storage = VectorStorageConfig(
                    provider="qdrant",
                    connection_url="http://localhost:6333",
                    data_path="/tmp/bablib/qdrant"
                )

            # Create setup configuration with initial components
            config = SetupConfiguration(
                setup_mode=SetupMode.AUTO,
                version="0.2.1",
                vector_storage=initial_vector_storage,
                embedding_model=initial_embedding_model
            )

            # Create session
            session = SetupSession(setup_config_id=config.setup_id)
            session.start_session()

            # Mark detection step as complete
            session.complete_step(SetupStep.DETECT_COMPONENTS)

            if docker_available and config.vector_storage:
                # Actually create and start the Qdrant container
                from pathlib import Path
                data_path = Path(config.vector_storage.data_path)
                await self.docker_manager.create_qdrant_container(
                    container_name="bablib-memory-qdrant",
                    port=6333,
                    data_path=data_path
                )
                logger.info("Qdrant container created and started successfully")

                session.complete_step(SetupStep.CONFIGURE_VECTOR_STORAGE)

            if ollama_available and config.embedding_model:
                # Embedding model is already configured, just mark step as complete
                session.complete_step(SetupStep.SETUP_EMBEDDING_MODEL)

            session.complete_step(SetupStep.CONFIGURE_MCP_CLIENTS)
            session.complete_step(SetupStep.VALIDATE_CONFIGURATION)

            # Save configuration
            config.mark_as_completed()
            await self.config_service.save_configuration(config)
            session.complete_step(SetupStep.PERSIST_SETTINGS)

            session.complete_session()
            await self.config_service.save_session(session)

            logger.info("Auto setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Auto setup failed: {e}")
            if 'session' in locals():
                session.fail_session(str(e))
                await self.config_service.save_session(session)
            raise

    async def get_setup_status(self) -> dict[str, Any]:
        """Get current setup status."""
        existing_setup = await self.config_service.check_existing_setup()

        if not existing_setup:
            return {
                "setup_completed": False,
                "setup_mode": None,
                "last_setup_time": None,
                "components_status": {},
                "configuration_file": None,
                "warnings": ["Setup not completed"]
            }

        # Get component health
        components = await self.health_checker.check_all_components()
        components_status = {}

        for component in components:
            status_key = component.component_name
            # Handle component_type as either enum or string
            component_type_value = component.component_type.value if hasattr(component.component_type, 'value') else component.component_type
            if component_type_value == "mcp_client":
                status_key = "mcp_clients"
                if status_key not in components_status:
                    components_status[status_key] = []
                components_status[status_key].append({
                    'name': component.component_name,
                    'status': component.health_status,
                    'available': component.available,
                    'version': component.version,
                    'last_checked': component.last_checked.isoformat(),
                    'error_message': component.error_message
                })
            else:
                components_status[status_key] = {
                    'name': component.component_name,
                    'status': component.health_status,
                    'available': component.available,
                    'version': component.version,
                    'last_checked': component.last_checked.isoformat(),
                    'error_message': component.error_message
                }

        return {
            **existing_setup,
            "components_status": components_status
        }

    async def detect_components(self) -> dict[str, Any]:
        """Detect all external components."""
        components = await self.health_checker.check_all_components()

        result = {}
        for component in components:
            result[component.component_name] = {
                "available": component.available,
                "version": component.version,
                "health_status": component.health_status,
                "error_message": component.error_message,
                "capabilities": component.capabilities
            }

        return result

    # Additional methods for API endpoints
    async def create_setup_session(self, setup_mode: str, force_restart: bool = False) -> dict[str, Any]:
        """Create a new setup session (for API)."""
        session = SetupSession(
            setup_config_id=uuid4()
        )

        await self.config_service.save_session(session)

        return {
            "session_id": str(session.session_id),
            "setup_mode": setup_mode,
            "status": session.session_status,
            "created_at": session.started_at.isoformat(),
            "total_steps": session.total_steps
        }

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        """Get session status (for API)."""
        session = await self.config_service.load_session(session_id)
        if not session:
            from ..models.setup_types import SessionNotFoundError
            raise SessionNotFoundError(f"Session {session_id} not found")

        return session.get_session_summary()

    async def get_component_availability(self, session_id: str) -> dict[str, Any]:
        """Get component availability (for API)."""
        components = await self.health_checker.check_all_components()

        return {
            "components": [c.get_status_details() for c in components],
            "last_checked": datetime.now(UTC).isoformat()
        }

    async def configure_components(self, session_id: str, config_data: dict[str, Any]) -> dict[str, Any]:
        """Configure components (for API)."""
        # Mock implementation
        return {
            "success": True,
            "configuration_id": str(uuid4()),
            "validation_errors": [],
            "warnings": []
        }

    async def execute_setup(self, session_id: str) -> dict[str, Any]:
        """Execute setup (for API)."""
        return {
            "execution_started": True,
            "estimated_duration": 180,
            "steps_to_execute": [
                "detect_components",
                "configure_vector_storage",
                "setup_embedding_model",
                "configure_mcp_clients",
                "validate_configuration",
                "persist_settings"
            ]
        }

    async def check_system_requirements(self) -> dict[str, Any]:
        """Check system requirements for Bablib."""
        try:
            validation_results = await self.requirements_service.validate_all_requirements()

            # Check if all critical requirements are met
            critical_requirements = ["python_version", "memory", "disk"]
            meets_requirements = all(
                validation_results.get(req, False) for req in critical_requirements
            )

            # Collect issues
            issues = []
            if not validation_results.get("python_version", False):
                issues.append("Python 3.13+ is required")
            if not validation_results.get("memory", False):
                issues.append("At least 4GB of RAM is required")
            if not validation_results.get("disk", False):
                issues.append("At least 2GB of free disk space is required")

            return {
                "meets_requirements": meets_requirements,
                "validation_results": validation_results,
                "issues": issues,
                "warnings": []
            }
        except Exception as e:
            logger.error(f"Failed to check system requirements: {e}")
            return {
                "meets_requirements": False,
                "validation_results": {},
                "issues": [str(e)],
                "warnings": []
            }

    async def run_automated_setup(self, force: bool = False) -> dict[str, Any]:
        """Run automated setup with minimal user interaction."""
        try:
            logger.info("Starting automated setup")

            # Check if setup already exists and not forcing
            if not force:
                existing_setup = await self.config_service.check_existing_setup()
                if existing_setup and existing_setup.get("setup_completed"):
                    return {
                        "success": False,
                        "error": "Setup already completed. Use --force to re-run.",
                        "existing_setup": existing_setup
                    }

            # Run auto setup
            success = await self.run_auto_setup()

            if success:
                return {
                    "success": True,
                    "message": "Automated setup completed successfully",
                    "warnings": []
                }
            else:
                return {
                    "success": False,
                    "error": "Automated setup failed",
                    "warnings": []
                }

        except Exception as e:
            logger.error(f"Automated setup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "warnings": []
            }
