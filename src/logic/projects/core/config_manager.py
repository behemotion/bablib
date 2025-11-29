"""ConfigManager for hierarchical project configuration management."""

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from ..models.config import ProjectConfig
from ..models.project import ProjectType
from .env_config import EnvironmentConfigHandler

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Hierarchical configuration manager for projects.

    Manages configuration inheritance from global defaults to project-specific overrides,
    providing a unified interface for configuration access and validation.
    """

    def __init__(self, data_directory: str | None = None, config_directory: str | None = None):
        """Initialize ConfigManager with directory paths."""
        self.data_directory = data_directory or self._get_default_data_directory()
        self.config_directory = config_directory or self._get_default_config_directory()

        # Configuration file paths
        self.global_config_path = Path(self.config_directory) / "settings.yaml"
        self.projects_config_dir = Path(self.data_directory) / "projects"

        self._ensure_directories()
        self._global_config_cache: dict[str, Any] | None = None

    def _get_default_data_directory(self) -> str:
        """Get default data directory using XDG specification."""
        return os.environ.get(
            'BABLIB_DATA_DIR',
            str(Path.home() / '.local' / 'share' / 'bablib')
        )

    def _get_default_config_directory(self) -> str:
        """Get default config directory using XDG specification."""
        return os.environ.get(
            'BABLIB_CONFIG_DIR',
            str(Path.home() / '.config' / 'bablib')
        )

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        Path(self.config_directory).mkdir(parents=True, exist_ok=True)
        self.projects_config_dir.mkdir(parents=True, exist_ok=True)

    async def get_global_settings(self) -> dict[str, Any]:
        """
        Get global default settings.

        Returns:
            Dictionary containing global configuration settings
        """
        if self._global_config_cache is None:
            await self._load_global_config()

        return self._global_config_cache.copy()

    async def get_project_settings(self, project_name: str) -> ProjectConfig:
        """
        Get effective settings for project (global + project overrides + env vars).

        Args:
            project_name: Name of the project

        Returns:
            ProjectConfig with effective settings

        Raises:
            ValueError: If project doesn't exist
        """
        # Load global settings
        global_settings = await self.get_global_settings()

        # Apply global environment variable overrides
        global_env_overrides = EnvironmentConfigHandler.get_global_env_overrides()
        if global_env_overrides:
            global_settings.update(global_env_overrides)

        # Load project-specific settings
        project_settings = await self._load_project_config(project_name)

        # Get project type for defaults
        project_type = await self._get_project_type(project_name)
        if project_type is None:
            raise ValueError(f"Project '{project_name}' not found")

        # Create config with type defaults
        config = ProjectConfig()

        # Apply hierarchy: type defaults -> global -> project-specific -> env vars
        effective_settings = config.get_effective_config(project_type, global_settings)
        effective_settings.update(project_settings)

        # Apply project-specific environment variable overrides
        env_overrides = EnvironmentConfigHandler.get_env_overrides(project_name)
        if env_overrides:
            effective_settings.update(env_overrides)
            logger.debug(f"Applied {len(env_overrides)} environment variable overrides for project {project_name}")

        return ProjectConfig.from_dict(effective_settings)

    async def update_project_settings(
        self,
        project_name: str,
        settings: dict[str, Any]
    ) -> ProjectConfig:
        """
        Update project-specific settings.

        Args:
            project_name: Name of the project
            settings: Settings to update

        Returns:
            Updated ProjectConfig

        Raises:
            ValueError: If project doesn't exist or settings are invalid
        """
        # Verify project exists
        project_type = await self._get_project_type(project_name)
        if project_type is None:
            raise ValueError(f"Project '{project_name}' not found")

        # Load current project settings
        current_settings = await self._load_project_config(project_name)

        # Merge with new settings
        merged_settings = {**current_settings, **settings}

        # Validate merged settings
        config = ProjectConfig.from_dict(merged_settings)
        validation_errors = config.validate_for_type(project_type)
        if validation_errors:
            raise ValueError(f"Invalid settings: {', '.join(validation_errors)}")

        # Save updated settings
        await self._save_project_config(project_name, merged_settings)

        # Return effective config
        return await self.get_project_settings(project_name)

    async def validate_settings_hierarchy(
        self,
        global_settings: dict[str, Any],
        project_settings: dict[str, Any],
        project_type: ProjectType
    ) -> list[str]:
        """
        Validate settings combination for consistency.

        Args:
            global_settings: Global configuration
            project_settings: Project-specific configuration
            project_type: Type of project

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        try:
            # Create merged configuration
            type_defaults = ProjectConfig.get_type_defaults(project_type)
            merged = {**type_defaults, **global_settings, **project_settings}

            # Validate using ProjectConfig
            config = ProjectConfig.from_dict(merged)
            validation_errors = config.validate_for_type(project_type)
            errors.extend(validation_errors)

            # Check for incompatible settings
            incompatible = config.get_incompatible_settings(project_type)
            for setting in incompatible:
                errors.append(f"Setting '{setting}' is not compatible with {project_type.value} projects")

        except Exception as e:
            errors.append(f"Configuration validation failed: {e}")

        return errors

    async def reset_project_settings(self, project_name: str) -> ProjectConfig:
        """
        Reset project to use only global and type defaults.

        Args:
            project_name: Name of the project

        Returns:
            ProjectConfig with default settings

        Raises:
            ValueError: If project doesn't exist
        """
        # Verify project exists
        project_type = await self._get_project_type(project_name)
        if project_type is None:
            raise ValueError(f"Project '{project_name}' not found")

        # Remove project-specific config file
        config_file = self._get_project_config_path(project_name)
        if config_file.exists():
            config_file.unlink()

        logger.info(f"Reset settings for project: {project_name}")

        # Return effective config (now just global + type defaults)
        return await self.get_project_settings(project_name)

    async def export_project_config(self, project_name: str, format: str = 'yaml') -> str:
        """
        Export project configuration to string.

        Args:
            project_name: Name of the project
            format: Export format ('yaml' or 'json')

        Returns:
            Configuration as formatted string

        Raises:
            ValueError: If project doesn't exist or format is unsupported
        """
        config = await self.get_project_settings(project_name)
        config_dict = config.to_dict(exclude_none=True)

        if format.lower() == 'yaml':
            return yaml.dump(config_dict, default_flow_style=False, sort_keys=True)
        elif format.lower() == 'json':
            return json.dumps(config_dict, indent=2, sort_keys=True)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'json'")

    async def import_project_config(
        self,
        project_name: str,
        config_data: str,
        format: str = 'yaml',
        merge: bool = True
    ) -> ProjectConfig:
        """
        Import project configuration from string.

        Args:
            project_name: Name of the project
            config_data: Configuration data as string
            format: Data format ('yaml' or 'json')
            merge: Whether to merge with existing settings

        Returns:
            Updated ProjectConfig

        Raises:
            ValueError: If import fails or settings are invalid
        """
        # Parse configuration data
        try:
            if format.lower() == 'yaml':
                imported_settings = yaml.safe_load(config_data)
            elif format.lower() == 'json':
                imported_settings = json.loads(config_data)
            else:
                raise ValueError(f"Unsupported format: {format}")
        except Exception as e:
            raise ValueError(f"Failed to parse {format} data: {e}")

        if not isinstance(imported_settings, dict):
            raise ValueError("Configuration data must be a dictionary")

        # Update project settings
        if merge:
            return await self.update_project_settings(project_name, imported_settings)
        else:
            # Replace all project settings
            await self._save_project_config(project_name, imported_settings)
            return await self.get_project_settings(project_name)

    async def get_config_summary(self, project_name: str) -> dict[str, Any]:
        """
        Get configuration summary showing sources of each setting.

        Args:
            project_name: Name of the project

        Returns:
            Dictionary showing setting sources and values
        """
        project_type = await self._get_project_type(project_name)
        if project_type is None:
            raise ValueError(f"Project '{project_name}' not found")

        # Get all configuration layers
        type_defaults = ProjectConfig.get_type_defaults(project_type)
        global_settings = await self.get_global_settings()
        project_settings = await self._load_project_config(project_name)
        env_overrides = EnvironmentConfigHandler.get_env_overrides(project_name)

        # Build summary
        summary = {
            'project_name': project_name,
            'project_type': project_type.value,
            'effective_config': {},
            'setting_sources': {},
            'overrides': {
                'global_overrides_defaults': [],
                'project_overrides_global': [],
                'project_overrides_defaults': [],
                'env_overrides': list(env_overrides.keys()) if env_overrides else []
            },
            'environment_variables': env_overrides if env_overrides else {}
        }

        # Calculate effective values and sources
        all_keys = set(type_defaults.keys()) | set(global_settings.keys()) | set(project_settings.keys())
        if env_overrides:
            all_keys |= set(env_overrides.keys())

        for key in all_keys:
            # Determine final value and source (env vars have highest priority)
            if env_overrides and key in env_overrides:
                summary['effective_config'][key] = env_overrides[key]
                summary['setting_sources'][key] = 'environment'

            elif key in project_settings:
                summary['effective_config'][key] = project_settings[key]
                summary['setting_sources'][key] = 'project'

                # Track overrides
                if key in global_settings:
                    summary['overrides']['project_overrides_global'].append(key)
                if key in type_defaults:
                    summary['overrides']['project_overrides_defaults'].append(key)

            elif key in global_settings:
                summary['effective_config'][key] = global_settings[key]
                summary['setting_sources'][key] = 'global'

                if key in type_defaults:
                    summary['overrides']['global_overrides_defaults'].append(key)

            elif key in type_defaults:
                summary['effective_config'][key] = type_defaults[key]
                summary['setting_sources'][key] = 'type_default'

        return summary

    # Private helper methods

    async def _load_global_config(self) -> None:
        """Load global configuration from file."""
        try:
            if self.global_config_path.exists():
                with open(self.global_config_path) as f:
                    self._global_config_cache = yaml.safe_load(f) or {}
            else:
                # Create default global config
                self._global_config_cache = self._get_default_global_config()
                await self._save_global_config()

        except Exception as e:
            logger.warning(f"Failed to load global config: {e}")
            self._global_config_cache = self._get_default_global_config()

    def _get_default_global_config(self) -> dict[str, Any]:
        """Get default global configuration."""
        return {
            'project_defaults': {
                'max_file_size': 10485760,  # 10MB
                'concurrent_uploads': 3,
                'retry_attempts': 3,
                'timeout_seconds': 30
            },
            'allowed_formats': {
                'images': ['jpg', 'jpeg', 'png', 'gif', 'tiff', 'webp', 'svg'],
                'audio': ['mp3', 'wav', 'flac', 'ogg'],
                'video': ['mp4', 'avi', 'mkv', 'webm'],
                'archives': ['zip', 'tar', 'gz', '7z', 'rar'],
                'documents': ['pdf', 'docx', 'txt', 'md', 'html', 'json', 'xml'],
                'code': ['py', 'js', 'ts', 'go', 'rs', 'java', 'cpp', 'c', 'h']
            },
            'cli_shortcuts': {
                'global_unique': True,
                'two_char_fallback': True
            }
        }

    async def _save_global_config(self) -> None:
        """Save global configuration to file."""
        try:
            with open(self.global_config_path, 'w') as f:
                yaml.dump(self._global_config_cache, f, default_flow_style=False, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to save global config: {e}")

    async def _load_project_config(self, project_name: str) -> dict[str, Any]:
        """Load project-specific configuration."""
        config_file = self._get_project_config_path(project_name)

        if not config_file.exists():
            return {}

        try:
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config for project {project_name}: {e}")
            return {}

    async def _save_project_config(self, project_name: str, settings: dict[str, Any]) -> None:
        """Save project-specific configuration."""
        config_file = self._get_project_config_path(project_name)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(config_file, 'w') as f:
                yaml.dump(settings, f, default_flow_style=False, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to save config for project {project_name}: {e}")
            raise

    def _get_project_config_path(self, project_name: str) -> Path:
        """Get path to project configuration file."""
        return self.projects_config_dir / project_name / "settings.yaml"

    async def _get_project_type(self, project_name: str) -> ProjectType | None:
        """Get project type from project registry."""
        # Load project data to get type
        from .project_manager import ProjectManager
        manager = ProjectManager(self.data_directory)
        project = await manager.get_project(project_name)
        return project.type if project else None

    def clear_cache(self) -> None:
        """Clear global configuration cache."""
        self._global_config_cache = None

    def __str__(self) -> str:
        """String representation of ConfigManager."""
        return f"ConfigManager(config_dir='{self.config_directory}')"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"ConfigManager(config_directory='{self.config_directory}', "
                f"data_directory='{self.data_directory}')")
