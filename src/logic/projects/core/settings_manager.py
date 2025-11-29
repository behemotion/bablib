"""Settings management with hierarchical inheritance for project configurations."""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from src.core.config import BablibConfig

from ..models.config import ProjectConfig
from ..models.project import ProjectType
from ..models.validation import ValidationResult

logger = logging.getLogger(__name__)


class SettingsManager:
    """
    Manages hierarchical settings with global defaults and project-specific overrides.

    Implements a layered configuration system where project settings override
    global defaults, with validation to ensure settings are appropriate for
    each project type.
    """

    def __init__(self, config: BablibConfig | None = None):
        """Initialize settings manager with global configuration."""
        self.global_config = config or BablibConfig()
        self.project_settings_cache: dict[str, ProjectConfig] = {}

    async def get_global_settings(self) -> dict[str, Any]:
        """
        Get global default settings from configuration.

        Returns:
            Dictionary of global default settings
        """
        return {
            'max_file_size': self.global_config.project_max_file_size,
            'allowed_formats': {
                'images': list(self.global_config.project_allowed_formats_images),
                'audio': list(self.global_config.project_allowed_formats_audio),
                'video': list(self.global_config.project_allowed_formats_video),
                'archives': list(self.global_config.project_allowed_formats_archives),
                'documents': list(self.global_config.project_allowed_formats_documents),
                'code': list(self.global_config.project_allowed_formats_code)
            },
            'embedding_model': self.global_config.embedding_model,
            'chunk_size': self.global_config.chunk_size,
            'chunk_overlap': self.global_config.chunk_overlap,
            'crawl_depth': self.global_config.crawl_depth,
            'rate_limit': self.global_config.rate_limit,
            'cli_shortcuts': {
                'global_unique': self.global_config.cli_global_unique_shortcuts,
                'two_char_fallback': self.global_config.cli_two_char_fallback
            }
        }

    async def get_project_settings(self, project_name: str) -> ProjectConfig:
        """
        Get effective settings for project (global + project overrides).

        Args:
            project_name: Name of the project

        Returns:
            ProjectConfig with effective settings

        Raises:
            ValueError: If project doesn't exist
        """
        # Check cache first
        if project_name in self.project_settings_cache:
            return self.project_settings_cache[project_name]

        # Load project-specific settings file
        project_settings = await self._load_project_settings_file(project_name)

        # Get global defaults
        global_settings = await self.get_global_settings()

        # Merge settings (project overrides global)
        effective_settings = self._merge_settings(global_settings, project_settings)

        # Create ProjectConfig
        config = ProjectConfig.from_dict(effective_settings)

        # Cache the result
        self.project_settings_cache[project_name] = config

        return config

    async def update_project_settings(
        self,
        project_name: str,
        settings: dict[str, Any]
    ) -> ProjectConfig:
        """
        Update project-specific settings.

        Args:
            project_name: Name of the project
            settings: New settings to apply

        Returns:
            Updated ProjectConfig

        Raises:
            ValueError: If validation fails
        """
        # Get current effective settings
        current_config = await self.get_project_settings(project_name)

        # Merge new settings with current
        updated_settings = self._merge_settings(current_config.to_dict(), settings)

        # Create and validate new config
        new_config = ProjectConfig.from_dict(updated_settings)

        # Save to project settings file
        await self._save_project_settings_file(project_name, settings)

        # Update cache
        self.project_settings_cache[project_name] = new_config

        logger.info(f"Updated settings for project {project_name}")
        return new_config

    async def validate_settings_hierarchy(
        self,
        global_settings: dict[str, Any],
        project_settings: dict[str, Any],
        project_type: ProjectType
    ) -> ValidationResult:
        """
        Validate settings combination for a project type.

        Args:
            global_settings: Global default settings
            project_settings: Project-specific overrides
            project_type: Type of project

        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []

        # Merge settings
        effective_settings = self._merge_settings(global_settings, project_settings)

        # Type-specific validation
        if project_type == ProjectType.CRAWLING:
            errors.extend(self._validate_crawling_settings(effective_settings))
        elif project_type == ProjectType.DATA:
            errors.extend(self._validate_data_settings(effective_settings))
        elif project_type == ProjectType.STORAGE:
            errors.extend(self._validate_storage_settings(effective_settings))

        # Common validation
        if 'max_file_size' in effective_settings:
            max_size = effective_settings['max_file_size']
            if max_size < 1024:  # Less than 1KB
                errors.append("max_file_size must be at least 1KB")
            elif max_size > 1073741824:  # More than 1GB
                warnings.append("max_file_size exceeds 1GB - this may cause performance issues")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _merge_settings(
        self,
        base_settings: dict[str, Any],
        overrides: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Recursively merge settings dictionaries.

        Args:
            base_settings: Base settings dictionary
            overrides: Override settings dictionary

        Returns:
            Merged settings dictionary
        """
        result = base_settings.copy()

        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._merge_settings(result[key], value)
            else:
                # Override value
                result[key] = value

        return result

    def _validate_crawling_settings(self, settings: dict[str, Any]) -> list[str]:
        """Validate settings for crawling projects."""
        errors = []

        if 'crawl_depth' in settings:
            depth = settings['crawl_depth']
            if not isinstance(depth, (int, float)) or depth < 1 or depth > 10:
                errors.append("crawl_depth must be between 1 and 10")

        if 'rate_limit' in settings:
            rate = settings['rate_limit']
            if not isinstance(rate, (int, float)) or rate <= 0 or rate > 10:
                errors.append("rate_limit must be between 0.1 and 10")

        # Crawling projects should focus on web formats
        if 'allowed_formats' in settings:
            formats = settings.get('allowed_formats', {})
            if isinstance(formats, dict):
                doc_formats = formats.get('documents', [])
                if 'html' not in doc_formats and 'htm' not in doc_formats:
                    errors.append("Crawling projects should support HTML formats")

        return errors

    def _validate_data_settings(self, settings: dict[str, Any]) -> list[str]:
        """Validate settings for data projects."""
        errors = []

        if 'chunk_size' in settings:
            chunk_size = settings['chunk_size']
            if not isinstance(chunk_size, int) or chunk_size < 100 or chunk_size > 2000:
                errors.append("chunk_size must be between 100 and 2000")

        if 'chunk_overlap' in settings:
            overlap = settings['chunk_overlap']
            chunk_size = settings.get('chunk_size', 500)
            if not isinstance(overlap, int) or overlap < 0 or overlap >= chunk_size:
                errors.append("chunk_overlap must be less than chunk_size")

        if 'embedding_model' in settings:
            model = settings['embedding_model']
            if not isinstance(model, str) or not model.strip():
                errors.append("embedding_model must be a non-empty string")

        # Data projects should support document formats
        if 'allowed_formats' in settings:
            formats = settings.get('allowed_formats', {})
            if isinstance(formats, dict):
                doc_formats = formats.get('documents', [])
                if not doc_formats:
                    errors.append("Data projects must support at least one document format")

        return errors

    def _validate_storage_settings(self, settings: dict[str, Any]) -> list[str]:
        """Validate settings for storage projects."""
        errors = []

        if 'enable_compression' in settings:
            if not isinstance(settings['enable_compression'], bool):
                errors.append("enable_compression must be a boolean")

        if 'auto_tagging' in settings:
            if not isinstance(settings['auto_tagging'], bool):
                errors.append("auto_tagging must be a boolean")

        if 'full_text_indexing' in settings:
            if not isinstance(settings['full_text_indexing'], bool):
                errors.append("full_text_indexing must be a boolean")

        # Storage projects typically allow all formats
        if 'max_file_size' in settings:
            max_size = settings['max_file_size']
            if max_size < 1048576:  # Less than 1MB
                errors.append("Storage projects should allow at least 1MB files")

        return errors

    async def _load_project_settings_file(self, project_name: str) -> dict[str, Any]:
        """
        Load project-specific settings from file.

        Args:
            project_name: Name of the project

        Returns:
            Project-specific settings dictionary
        """
        settings_path = self._get_project_settings_path(project_name)

        if not settings_path.exists():
            return {}

        try:
            with open(settings_path) as f:
                if settings_path.suffix == '.yaml':
                    return yaml.safe_load(f) or {}
                else:  # .json
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load project settings for {project_name}: {e}")
            return {}

    async def _save_project_settings_file(
        self,
        project_name: str,
        settings: dict[str, Any]
    ) -> None:
        """
        Save project-specific settings to file.

        Args:
            project_name: Name of the project
            settings: Settings to save
        """
        settings_path = self._get_project_settings_path(project_name)

        # Ensure directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(settings_path, 'w') as f:
                if settings_path.suffix == '.yaml':
                    yaml.safe_dump(settings, f, default_flow_style=False)
                else:  # .json
                    json.dump(settings, f, indent=2)

            logger.debug(f"Saved project settings for {project_name} to {settings_path}")
        except Exception as e:
            logger.error(f"Failed to save project settings for {project_name}: {e}")
            raise RuntimeError(f"Could not save project settings: {e}")

    def _get_project_settings_path(self, project_name: str) -> Path:
        """Get path to project settings file."""
        import os
        data_dir = os.environ.get(
            'BABLIB_DATA_DIR',
            str(Path.home() / '.local' / 'share' / 'bablib')
        )
        return Path(data_dir) / 'projects' / project_name / 'settings.yaml'

    async def export_settings(
        self,
        project_name: str,
        export_format: str = 'yaml'
    ) -> str:
        """
        Export project settings in specified format.

        Args:
            project_name: Name of the project
            export_format: Format for export ('yaml', 'json')

        Returns:
            Settings as string in requested format
        """
        config = await self.get_project_settings(project_name)
        settings = config.to_dict(exclude_none=True)

        if export_format == 'yaml':
            return yaml.safe_dump(settings, default_flow_style=False)
        elif export_format == 'json':
            return json.dumps(settings, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

    async def import_settings(
        self,
        project_name: str,
        settings_str: str,
        format_type: str = 'yaml'
    ) -> ProjectConfig:
        """
        Import settings from string.

        Args:
            project_name: Name of the project
            settings_str: Settings as string
            format_type: Format of the string ('yaml', 'json')

        Returns:
            Updated ProjectConfig

        Raises:
            ValueError: If parsing or validation fails
        """
        try:
            if format_type == 'yaml':
                settings = yaml.safe_load(settings_str)
            elif format_type == 'json':
                settings = json.loads(settings_str)
            else:
                raise ValueError(f"Unsupported format type: {format_type}")

            return await self.update_project_settings(project_name, settings)

        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to parse settings: {e}")

    def invalidate_cache(self, project_name: str | None = None) -> None:
        """
        Invalidate settings cache.

        Args:
            project_name: Specific project to invalidate, or None for all
        """
        if project_name:
            self.project_settings_cache.pop(project_name, None)
        else:
            self.project_settings_cache.clear()
