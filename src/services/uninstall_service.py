"""Uninstall service orchestrator for managing the uninstall process."""

from pathlib import Path
from typing import Any

import click

import docker
from src.core.lib_logger import get_logger
from src.models.component_status import ComponentStatus
from src.models.removal_operation import OperationType, RemovalOperation
from src.models.uninstall_config import UninstallConfig
from src.models.uninstall_inventory import ComponentType, UninstallComponent
from src.models.uninstall_progress import UninstallProgress
from src.services.backup_service import BackupService
from src.services.component_detection import ComponentDetectionService
from src.services.removal_executor import RemovalExecutor


class UninstallWarning:
    """Uninstall warning data structure for contract compliance"""
    def __init__(self, message: str, data_types: list[str], is_irreversible: bool, estimated_data_loss: str):
        self.message = message
        self.data_types = data_types
        self.is_irreversible = is_irreversible
        self.estimated_data_loss = estimated_data_loss

logger = get_logger(__name__)


class UninstallService:
    """Main orchestration service for uninstall operations."""

    def __init__(self):
        """Initialize the uninstall service."""
        self.detection_service = ComponentDetectionService()
        self.removal_executor = RemovalExecutor()
        self.backup_service = BackupService()
        self.progress = UninstallProgress()

    async def validate_installation(self) -> list[ComponentStatus]:
        """Detect what needs removal."""
        components = await self.detection_service.detect_all_components()

        # Flatten components into a list of ComponentStatus
        all_components = []

        for container in components.get('containers', []):
            all_components.append(container)

        for volume in components.get('volumes', []):
            all_components.append(volume)

        for directory in components.get('directories', []):
            all_components.append(directory)

        for config in components.get('configs', []):
            all_components.append(config)

        if components.get('package'):
            all_components.append(components['package'])

        return all_components

    async def create_backup(self, config: UninstallConfig, components: dict[str, Any]) -> dict | None:
        """Create backup if requested."""
        if not config.backup:
            return None

        try:
            logger.info("Creating backup before uninstall")
            backup_info = await self.backup_service.create_backup(
                components=components,
                path=config.backup_path
            )
            self.progress.set_backup_info(backup_info['path'])
            return backup_info
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            if not config.force:
                # Ask user if they want to continue without backup
                if not self.handle_failure(None, f"Backup failed: {e}"):
                    raise
            return None

    async def execute(
        self,
        config: UninstallConfig,
        components: dict[str, Any] | None = None,
        preserve_external: bool = True
    ) -> dict[str, Any]:
        """Perform uninstall operation."""
        # Detect components if not provided
        if components is None:
            components = await self.detection_service.detect_all_components()

        # If force flag is used, remove all projects first
        if config.force:
            await self._remove_all_projects()

        # Count total components
        total = 0
        for key in ['containers', 'volumes', 'directories', 'configs']:
            total += len(components.get(key, []))
        if components.get('package'):
            total += 1

        self.progress.total_components = total

        # Create operations queue
        operations = self._create_operations_queue(components, preserve_external)

        # Execute operations
        for operation in operations:
            if config.dry_run:
                logger.info(f"[DRY RUN] Would execute: {operation.get_display_name()}")
                self.progress.increment_skipped()
                # Call UI callback if available
                if hasattr(self, '_ui_callback') and self._ui_callback:
                    self._ui_callback('skipped')
            else:
                success = await self._execute_operation(operation, config)
                if success:
                    self.progress.increment_removed()
                    # Call UI callback if available
                    if hasattr(self, '_ui_callback') and self._ui_callback:
                        self._ui_callback('removed')
                else:
                    self.progress.increment_failed()
                    # Call UI callback if available
                    if hasattr(self, '_ui_callback') and self._ui_callback:
                        self._ui_callback('failed')

                    # Handle failure
                    if not config.force:
                        if not self.handle_failure(
                            None,
                            f"Failed to {operation.get_display_name()}"
                        ):
                            break  # User chose to stop

        self.progress.mark_complete()

        return {
            'success': self.progress.failed_components == 0,
            'removed': self.progress.removed_components,
            'failed': self.progress.failed_components,
            'skipped': self.progress.skipped_components,
            'summary': self.progress.get_summary()
        }

    def handle_failure(self, component: ComponentStatus | None, error_message: str) -> bool:
        """Prompt user on failure (without --force)."""
        logger.error(error_message)

        # In non-interactive mode, continue
        if not click.get_current_context().obj.get('interactive', True):
            return True

        return click.confirm(
            f"\n{error_message}\nContinue with remaining removals?",
            default=False
        )

    def _create_operations_queue(
        self,
        components: dict[str, Any],
        preserve_external: bool
    ) -> list[RemovalOperation]:
        """Create ordered queue of removal operations."""
        operations = []

        # 1. Stop containers first
        for container in components.get('containers', []):
            if hasattr(container, 'component_name'):
                name = container.component_name
            else:
                name = container.get('Names', ['/unknown'])[0].lstrip('/')

            container_id = container.get('Id', name) if isinstance(container, dict) else name
            op = RemovalOperation.create_stop_container(container_id, name)
            operations.append(op)

        # 2. Remove containers
        for container in components.get('containers', []):
            if hasattr(container, 'component_name'):
                name = container.component_name
            else:
                name = container.get('Names', ['/unknown'])[0].lstrip('/')

            container_id = container.get('Id', name) if isinstance(container, dict) else name
            # Find corresponding stop operation
            stop_op = next((op for op in operations if op.target == container_id), None)
            depends_on = stop_op.operation_id if stop_op else None

            op = RemovalOperation.create_remove_container(container_id, depends_on)
            operations.append(op)

        # 3. Remove volumes (skip external if preserve_external is True)
        for volume in components.get('volumes', []):
            if hasattr(volume, '__dict__'):
                # ComponentStatus object
                if preserve_external and volume.is_external:
                    logger.info(f"Preserving external volume: {volume.component_name}")
                    continue
                name = volume.component_name
            else:
                # Dictionary
                name = volume.get('Name', 'unknown')

            op = RemovalOperation.create_remove_volume(name)
            operations.append(op)

        # 4. Delete config files
        for config in components.get('configs', []):
            if hasattr(config, 'component_path'):
                path = str(config.component_path)
            elif isinstance(config, Path):
                path = str(config)
            else:
                continue

            op = RemovalOperation.create_delete_config(path)
            operations.append(op)

        # 5. Delete directories
        for directory in components.get('directories', []):
            if hasattr(directory, 'component_path'):
                path = str(directory.component_path)
            elif isinstance(directory, Path):
                path = str(directory)
            else:
                continue

            op = RemovalOperation.create_delete_directory(path)
            operations.append(op)

        # 6. Uninstall package last
        if components.get('package'):
            op = RemovalOperation.create_uninstall_package('bablib')
            operations.append(op)

        # Sort by priority
        operations.sort(key=lambda x: x.priority)

        return operations

    async def _execute_operation(
        self,
        operation: RemovalOperation,
        config: UninstallConfig
    ) -> bool:
        """Execute a single removal operation."""
        logger.info(f"Executing: {operation.get_display_name()}")

        try:
            if operation.operation_type == OperationType.STOP_CONTAINER:
                return await self.removal_executor.stop_container(operation.target)

            elif operation.operation_type == OperationType.REMOVE_CONTAINER:
                return await self.removal_executor.remove_container(
                    operation.target,
                    force=config.force
                )

            elif operation.operation_type == OperationType.REMOVE_VOLUME:
                return await self.removal_executor.remove_volume(
                    operation.target,
                    force=config.force
                )

            elif operation.operation_type == OperationType.DELETE_DIRECTORY:
                return await self.removal_executor.delete_directory(Path(operation.target))

            elif operation.operation_type == OperationType.DELETE_CONFIG:
                return await self.removal_executor.delete_file(Path(operation.target))

            elif operation.operation_type == OperationType.UNINSTALL_PACKAGE:
                return await self.removal_executor.uninstall_package()

            else:
                logger.warning(f"Unknown operation type: {operation.operation_type}")
                return False

        except Exception as e:
            logger.error(f"Operation failed: {e}")
            operation.mark_failed(str(e))

            # Retry if possible
            if operation.can_retry:
                operation.increment_retry()
                logger.info(f"Retrying operation (attempt {operation.retry_count}/{operation.max_retries})")
                return await self._execute_operation(operation, config)

            return False

    async def scan_installed_components(self) -> list[UninstallComponent]:
        """Scan and return all installed Bablib components."""
        components = await self.detection_service.detect_all_components()
        uninstall_components = []

        # Convert containers
        for container in components.get('containers', []):
            name = container.get('Names', ['/unknown'])[0].lstrip('/') if isinstance(container, dict) else str(container)
            uninstall_components.append(UninstallComponent(
                component_type=ComponentType.CONTAINER,
                name=name,
                path=None,
                size_mb=0,  # Could be calculated from container size
                is_external=False
            ))

        # Convert volumes
        for volume in components.get('volumes', []):
            name = volume.get('Name', 'unknown') if isinstance(volume, dict) else str(volume)
            uninstall_components.append(UninstallComponent(
                component_type=ComponentType.VOLUME,
                name=name,
                path=None,
                size_mb=0,  # Could be calculated from volume size
                is_external=getattr(volume, 'is_external', False) if hasattr(volume, 'is_external') else False
            ))

        # Convert directories
        for directory in components.get('directories', []):
            path = str(directory.component_path) if hasattr(directory, 'component_path') else str(directory)
            uninstall_components.append(UninstallComponent(
                component_type=ComponentType.DIRECTORY,
                name=Path(path).name,
                path=path,
                size_mb=0,  # Could be calculated from directory size
                is_external=False
            ))

        # Convert configs
        for config in components.get('configs', []):
            path = str(config.component_path) if hasattr(config, 'component_path') else str(config)
            uninstall_components.append(UninstallComponent(
                component_type=ComponentType.CONFIG_FILE,
                name=Path(path).name,
                path=path,
                size_mb=0,  # Config files are typically small
                is_external=False
            ))

        # Add package component
        if components.get('package'):
            uninstall_components.append(UninstallComponent(
                component_type=ComponentType.PACKAGE,
                name="bablib",
                path=None,
                size_mb=0,
                is_external=False
            ))

        return uninstall_components

    async def check_running_services(self) -> list[str]:
        """Check for running Bablib services that need shutdown."""
        running_services = []

        try:
            client = docker.from_env()
            containers = client.containers.list()

            for container in containers:
                # Check if it's a Bablib-related container
                container_name = container.name
                if any(keyword in container_name.lower() for keyword in ['bablib', 'qdrant']):
                    if container.status == 'running':
                        running_services.append(container_name)

        except Exception as e:
            logger.warning(f"Failed to check running services: {e}")

        return running_services

    def generate_uninstall_warning(self, components: list[UninstallComponent]) -> UninstallWarning:
        """Generate warning about data loss and irreversible actions."""
        data_types = []
        total_size = sum(comp.size_mb for comp in components)

        # Identify data types that will be lost
        for component in components:
            if component.component_type == ComponentType.VOLUME:
                data_types.append("Vector database data")
            elif component.component_type == ComponentType.DIRECTORY:
                if "data" in component.name.lower() or "cache" in component.name.lower():
                    data_types.append("Application data")
            elif component.component_type == ComponentType.CONFIG_FILE:
                data_types.append("Configuration files")

        if not data_types:
            data_types = ["Application components"]

        message = (
            f"This will permanently remove Bablib and all associated data.\n"
            f"Components to be removed: {len(components)}\n"
            f"Data types affected: {', '.join(set(data_types))}"
        )

        return UninstallWarning(
            message=message,
            data_types=list(set(data_types)),
            is_irreversible=True,
            estimated_data_loss=f"{total_size:.1f}MB" if total_size > 0 else "Unknown size"
        )

    async def stop_all_services(self, service_names: list[str]) -> dict[str, bool]:
        """Stop all running Bablib services before uninstall."""
        results = {}

        try:
            client = docker.from_env()

            for service_name in service_names:
                try:
                    container = client.containers.get(service_name)
                    if container.status == 'running':
                        logger.info(f"Stopping service: {service_name}")
                        container.stop(timeout=10)
                        results[service_name] = True
                    else:
                        results[service_name] = True  # Already stopped
                except docker.errors.NotFound:
                    results[service_name] = True  # Container doesn't exist
                except Exception as e:
                    logger.error(f"Failed to stop {service_name}: {e}")
                    results[service_name] = False

        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            for service_name in service_names:
                results[service_name] = False

        return results

    async def _remove_all_projects(self) -> None:
        """Remove all projects and their data."""
        try:
            logger.info("Removing all projects as part of uninstall")
            # Import database manager to get projects
            from src.core.config import BablibConfig
            from src.services.database import DatabaseManager

            config = BablibConfig()
            db_manager = DatabaseManager(config)
            await db_manager.initialize()

            # Get all projects
            projects = await db_manager.list_projects()

            if projects:
                logger.info(f"Found {len(projects)} project(s) to remove")
                for project in projects:
                    try:
                        logger.info(f"Removing project: {project.name}")
                        cleanup_result = await db_manager.cleanup_project(project.id)
                        if cleanup_result["success"]:
                            logger.info(f"Successfully removed project '{project.name}'")
                        else:
                            logger.warning(f"Failed to remove project '{project.name}': {cleanup_result.get('error')}")
                    except Exception as e:
                        logger.warning(f"Error removing project '{project.name}': {e}")
                        # Continue with other projects even if one fails
            else:
                logger.info("No projects found to remove")

            await db_manager.cleanup()

        except Exception as e:
            logger.warning(f"Error during project removal: {e}")
            # Don't fail the entire uninstall if project removal fails

    async def execute_uninstall(
        self,
        components: list[UninstallComponent],
        force: bool = False,
        preserve_external: bool = True
    ) -> dict[str, Any]:
        """Execute the uninstall process."""
        # Convert UninstallComponent list to the format expected by existing execute method
        components_dict = {
            'containers': [],
            'volumes': [],
            'directories': [],
            'configs': [],
            'package': None
        }

        for component in components:
            if component.component_type == ComponentType.CONTAINER:
                components_dict['containers'].append({'Names': [f'/{component.name}'], 'Id': component.name})
            elif component.component_type == ComponentType.VOLUME:
                vol_obj = type('Volume', (), {'Name': component.name, 'is_external': component.is_external})()
                components_dict['volumes'].append(vol_obj)
            elif component.component_type == ComponentType.DIRECTORY:
                dir_obj = type('Directory', (), {'component_path': Path(component.path)})()
                components_dict['directories'].append(dir_obj)
            elif component.component_type == ComponentType.CONFIG_FILE:
                config_obj = type('Config', (), {'component_path': Path(component.path)})()
                components_dict['configs'].append(config_obj)
            elif component.component_type == ComponentType.PACKAGE:
                components_dict['package'] = component.name

        # Create config for execution
        config = UninstallConfig(
            force=force,
            dry_run=False,
            backup=False
        )

        return await self.execute(config, components_dict, preserve_external)

    async def rollback_uninstall(self, backup_path: str) -> bool:
        """Rollback uninstall using backup (if available)."""
        if not backup_path:
            logger.error("No backup path provided for rollback")
            return False

        try:
            logger.info(f"Attempting rollback from backup: {backup_path}")
            # This would typically restore from backup
            # Implementation depends on backup format and restoration logic
            result = await self.backup_service.restore_backup(backup_path)
            logger.info("Rollback completed successfully")
            return result
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
