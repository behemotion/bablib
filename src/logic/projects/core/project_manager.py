"""ProjectManager service implementation for project lifecycle management."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models.config import ProjectConfig
from ..models.project import Project, ProjectStatus, ProjectType
from .database_repository import ProjectDatabaseRepository

logger = logging.getLogger(__name__)


class ProjectManager:
    """
    Main project management service implementing project lifecycle operations.

    Handles project creation, deletion, updates, and coordination with type-specific handlers.
    Provides unified interface for all project operations.
    """

    def __init__(self, data_directory: str | None = None):
        """Initialize ProjectManager with data directory."""
        self.data_directory = data_directory or self._get_default_data_directory()
        self.projects_directory = Path(self.data_directory) / "projects"
        self.registry_path = Path(self.data_directory) / "project_registry.db"
        self._ensure_directories()

        # Initialize database repository
        self.db_repository = ProjectDatabaseRepository(self.data_directory)
        self._db_initialized = False

    def _get_default_data_directory(self) -> str:
        """Get default data directory using XDG specification."""
        return os.environ.get(
            'BABLIB_DATA_DIR',
            str(Path.home() / '.local' / 'share' / 'bablib')
        )

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.projects_directory.mkdir(parents=True, exist_ok=True)

    async def _ensure_db_initialized(self) -> None:
        """Ensure database repository is initialized."""
        if not self._db_initialized:
            await self.db_repository.initialize()
            self._db_initialized = True

    async def create_project(
        self,
        name: str,
        project_type: ProjectType,
        settings: ProjectConfig | None = None,
        force: bool = False
    ) -> Project:
        """
        Create a new project with type-specific initialization.

        Args:
            name: Project name (must be unique)
            project_type: Type of project to create
            settings: Optional project-specific settings
            force: Whether to overwrite existing project

        Returns:
            Created Project instance

        Raises:
            ValueError: If project name is invalid or already exists
            RuntimeError: If project creation fails
        """
        await self._ensure_db_initialized()
        logger.info(f"Creating {project_type.value} project: {name}")

        # Validate project name
        if await self._project_exists(name) and not force:
            raise ValueError(f"Project '{name}' already exists. Use force=True to overwrite.")

        # Create project instance with defaults
        project = Project(
            name=name,
            type=project_type,
            status=ProjectStatus.ACTIVE
        )

        # Apply settings if provided
        if settings:
            project.update_settings(settings.to_dict(exclude_none=True))
        else:
            # Use type defaults
            project.update_settings(project.get_default_settings())

        try:
            # Create project directory
            project_dir = Path(project.get_project_directory())
            project_dir.mkdir(parents=True, exist_ok=True)

            # Initialize type-specific components
            from .project_factory import ProjectFactory
            factory = ProjectFactory()
            handler = factory.create_project_handler(project_type)

            success = await handler.initialize_project(project)
            if not success:
                raise RuntimeError("Project type-specific initialization failed")

            # Save project to registry
            await self._save_project_to_registry(project)

            logger.info(f"Successfully created project: {name}")
            return project

        except Exception as e:
            logger.error(f"Failed to create project {name}: {e}")
            # Cleanup on failure
            await self._cleanup_failed_project(project)
            raise RuntimeError(f"Project creation failed: {e}")

    async def get_project(self, name: str) -> Project | None:
        """
        Retrieve project by name.

        Args:
            name: Project name

        Returns:
            Project instance if found, None otherwise
        """
        return await self._load_project_from_registry(name)

    async def list_projects(
        self,
        status: ProjectStatus | None = None,
        project_type: ProjectType | None = None,
        limit: int | None = None
    ) -> list[Project]:
        """
        List projects with optional filtering.

        Args:
            status: Filter by project status
            project_type: Filter by project type
            limit: Maximum number of projects to return

        Returns:
            List of Project instances matching criteria
        """
        await self._ensure_db_initialized()
        return await self.db_repository.list_projects(status, project_type, limit)

    async def update_project(self, project: Project) -> Project:
        """
        Update project metadata and settings.

        Args:
            project: Project instance with updated data

        Returns:
            Updated Project instance

        Raises:
            ValueError: If project doesn't exist
            RuntimeError: If update fails
        """
        logger.info(f"Updating project: {project.name}")

        # Verify project exists
        existing = await self.get_project(project.name)
        if not existing:
            raise ValueError(f"Project '{project.name}' not found")

        try:
            # Update timestamp
            project.updated_at = datetime.now(timezone.utc)

            # Validate settings for project type
            from .project_factory import ProjectFactory
            factory = ProjectFactory()
            handler = factory.create_project_handler(project.type)

            config = ProjectConfig.from_dict(project.settings)
            validation_result = await handler.validate_settings(config)
            if not validation_result.valid:
                raise ValueError(f"Invalid settings: {', '.join(validation_result.errors)}")

            # Save updated project
            await self._save_project_to_registry(project)

            logger.info(f"Successfully updated project: {project.name}")
            return project

        except Exception as e:
            logger.error(f"Failed to update project {project.name}: {e}")
            raise RuntimeError(f"Project update failed: {e}")

    async def remove_project(self, name: str, backup: bool = True, force: bool = False) -> bool:
        """
        Remove project with type-specific cleanup.

        Args:
            name: Project name to remove
            backup: Whether to create backup before removal
            force: Whether to force removal even if errors occur

        Returns:
            True if removal successful

        Raises:
            ValueError: If project doesn't exist
            RuntimeError: If removal fails and force=False
        """
        logger.info(f"Removing project: {name} (backup={backup}, force={force})")

        # Get project details
        project = await self.get_project(name)
        if not project:
            raise ValueError(f"Project '{name}' not found")

        try:
            # Create backup if requested
            if backup:
                await self._create_project_backup(project)

            # Type-specific cleanup
            from .project_factory import ProjectFactory
            factory = ProjectFactory()
            handler = factory.create_project_handler(project.type)

            cleanup_success = await handler.cleanup_project(project)
            if not cleanup_success and not force:
                raise RuntimeError("Type-specific cleanup failed")

            # Remove project directory
            project_dir = Path(project.get_project_directory())
            if project_dir.exists():
                await self._remove_directory_recursive(project_dir)

            # Remove from registry
            await self._remove_project_from_registry(name)

            logger.info(f"Successfully removed project: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove project {name}: {e}")
            if not force:
                raise RuntimeError(f"Project removal failed: {e}")
            return False

    async def get_project_stats(self, name: str) -> dict[str, Any]:
        """
        Get project statistics (file count, size, etc.).

        Args:
            name: Project name

        Returns:
            Dictionary containing project statistics

        Raises:
            ValueError: If project doesn't exist
        """
        project = await self.get_project(name)
        if not project:
            raise ValueError(f"Project '{name}' not found")

        project_dir = Path(project.get_project_directory())

        # Basic directory stats
        stats = {
            'name': project.name,
            'type': project.type.value,
            'status': project.status.value,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'directory_size': 0,
            'file_count': 0,
            'database_size': 0
        }

        try:
            # Calculate directory size and file count
            if project_dir.exists():
                for file_path in project_dir.rglob('*'):
                    if file_path.is_file():
                        stats['file_count'] += 1
                        stats['directory_size'] += file_path.stat().st_size

            # Database size
            db_path = Path(project.get_database_path())
            if db_path.exists():
                stats['database_size'] = db_path.stat().st_size

            # Type-specific stats
            from .project_factory import ProjectFactory
            factory = ProjectFactory()
            handler = factory.create_project_handler(project.type)

            # Get type-specific statistics if handler supports it
            if hasattr(handler, 'get_project_stats'):
                type_stats = await handler.get_project_stats(project)
                stats.update(type_stats)

        except Exception as e:
            logger.warning(f"Failed to get complete stats for project {name}: {e}")

        return stats

    async def validate_project_name(self, name: str) -> list[str]:
        """
        Validate project name and return list of issues.

        Args:
            name: Project name to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not name or not name.strip():
            errors.append("Project name cannot be empty")
            return errors

        name = name.strip()

        # Length validation
        if len(name) < 1:
            errors.append("Project name must be at least 1 character")
        if len(name) > 100:
            errors.append("Project name cannot exceed 100 characters")

        # Character validation
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in name:
                errors.append(f"Project name cannot contain '{char}'")

        # Reserved names
        reserved_names = ['con', 'prn', 'aux', 'nul'] + [f'com{i}' for i in range(1, 10)] + [f'lpt{i}' for i in range(1, 10)]
        if name.lower() in reserved_names:
            errors.append(f"'{name}' is a reserved name")

        # Check if already exists
        if await self._project_exists(name):
            errors.append(f"Project '{name}' already exists")

        return errors

    async def get_supported_project_types(self) -> list[ProjectType]:
        """
        Get list of supported project types.

        Returns:
            List of supported ProjectType values
        """
        from .project_factory import ProjectFactory
        factory = ProjectFactory()
        return factory.get_supported_types()

    # Private helper methods

    async def _project_exists(self, name: str) -> bool:
        """Check if project exists in registry."""
        await self._ensure_db_initialized()
        project = await self.db_repository.get_project(name)
        return project is not None

    async def _save_project_to_registry(self, project: Project) -> None:
        """Save project to registry database."""
        await self._ensure_db_initialized()
        await self.db_repository.save_project(project)

        # Also ensure project-specific database is created
        await self.db_repository._ensure_project_database(project)

    async def _load_project_from_registry(self, name: str) -> Project | None:
        """Load project from registry database."""
        await self._ensure_db_initialized()
        return await self.db_repository.get_project(name)

    async def _load_all_projects_from_registry(self) -> list[Project]:
        """Load all projects from registry."""
        await self._ensure_db_initialized()
        return await self.db_repository.list_projects()

    async def _remove_project_from_registry(self, name: str) -> None:
        """Remove project from registry database."""
        await self._ensure_db_initialized()
        await self.db_repository.delete_project(name)

    async def _create_project_backup(self, project: Project) -> None:
        """Create backup of project before removal."""
        import shutil

        backup_dir = Path(self.data_directory) / "backups" / f"{project.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Copy project directory
        project_dir = Path(project.get_project_directory())
        if project_dir.exists():
            shutil.copytree(project_dir, backup_dir / "data", dirs_exist_ok=True)

        # Copy project metadata from registry
        import json
        project_data = project.dict()
        with open(backup_dir / "project.json", 'w') as f:
            json.dump(project_data, f, indent=2, default=str)

        logger.info(f"Created backup for project {project.name} at {backup_dir}")

    async def _remove_directory_recursive(self, directory: Path) -> None:
        """Remove directory and all contents."""
        import shutil

        if directory.exists():
            # Use asyncio to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, str(directory))

    async def _cleanup_failed_project(self, project: Project) -> None:
        """Clean up resources from failed project creation."""
        try:
            # Remove project directory if it exists
            project_dir = Path(project.get_project_directory())
            if project_dir.exists():
                await self._remove_directory_recursive(project_dir)

            # Remove registry entry if it exists
            await self._remove_project_from_registry(project.name)

        except Exception as e:
            logger.warning(f"Failed to cleanup failed project {project.name}: {e}")

    def __str__(self) -> str:
        """String representation of ProjectManager."""
        return f"ProjectManager(data_directory='{self.data_directory}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"ProjectManager(data_directory='{self.data_directory}', "
                f"projects_directory='{self.projects_directory}')")
