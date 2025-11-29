"""Environment variable support for project configuration."""

import logging
import os
from typing import Any

from ..models.project import ProjectType

logger = logging.getLogger(__name__)


class EnvironmentConfigHandler:
    """
    Handles environment variable configuration for projects.

    Provides a way to override project settings through environment variables,
    following the pattern BABLIB_PROJECT_<PROJECT_NAME>_<SETTING>.
    """

    # Mapping of environment variable suffixes to setting paths
    ENV_VAR_MAPPING = {
        'MAX_FILE_SIZE': 'max_file_size',
        'CHUNK_SIZE': 'chunk_size',
        'CHUNK_OVERLAP': 'chunk_overlap',
        'CRAWL_DEPTH': 'crawl_depth',
        'RATE_LIMIT': 'rate_limit',
        'EMBEDDING_MODEL': 'embedding_model',
        'VECTOR_STORE_TYPE': 'vector_store_type',
        'ENABLE_COMPRESSION': 'enable_compression',
        'AUTO_TAGGING': 'auto_tagging',
        'FULL_TEXT_INDEXING': 'full_text_indexing',
        'ALLOWED_FORMATS': 'allowed_formats',
    }

    @staticmethod
    def get_project_env_prefix(project_name: str) -> str:
        """
        Get environment variable prefix for a project.

        Args:
            project_name: Name of the project

        Returns:
            Environment variable prefix
        """
        # Replace non-alphanumeric characters with underscores
        clean_name = ''.join(c if c.isalnum() else '_' for c in project_name.upper())
        return f"BABLIB_PROJECT_{clean_name}"

    @classmethod
    def get_env_overrides(cls, project_name: str) -> dict[str, Any]:
        """
        Get environment variable overrides for a project.

        Args:
            project_name: Name of the project

        Returns:
            Dictionary of settings overridden by environment variables
        """
        prefix = cls.get_project_env_prefix(project_name)
        overrides = {}

        for env_suffix, setting_path in cls.ENV_VAR_MAPPING.items():
            env_var = f"{prefix}_{env_suffix}"
            value = os.environ.get(env_var)

            if value is not None:
                parsed_value = cls._parse_env_value(env_suffix, value)
                if parsed_value is not None:
                    cls._set_nested_dict(overrides, setting_path, parsed_value)
                    logger.debug(f"Applied env override {env_var}={value} to {setting_path}")

        return overrides

    @classmethod
    def _parse_env_value(cls, env_suffix: str, value: str) -> Any:
        """
        Parse environment variable value based on expected type.

        Args:
            env_suffix: Environment variable suffix
            value: String value from environment

        Returns:
            Parsed value in appropriate type
        """
        try:
            # Integer values
            if env_suffix in ['MAX_FILE_SIZE', 'CHUNK_SIZE', 'CHUNK_OVERLAP', 'CRAWL_DEPTH']:
                return int(value)

            # Float values
            elif env_suffix == 'RATE_LIMIT':
                return float(value)

            # Boolean values
            elif env_suffix in ['ENABLE_COMPRESSION', 'AUTO_TAGGING', 'FULL_TEXT_INDEXING']:
                return value.lower() in ('true', '1', 'yes', 'on')

            # List values (comma-separated)
            elif env_suffix == 'ALLOWED_FORMATS':
                return [fmt.strip() for fmt in value.split(',') if fmt.strip()]

            # String values
            else:
                return value

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse env var {env_suffix}={value}: {e}")
            return None

    @staticmethod
    def _set_nested_dict(dictionary: dict, path: str, value: Any) -> None:
        """
        Set value in nested dictionary using dot notation path.

        Args:
            dictionary: Target dictionary
            path: Dot-separated path (e.g., 'settings.max_file_size')
            value: Value to set
        """
        keys = path.split('.')
        current = dictionary

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    @classmethod
    def get_global_env_overrides(cls) -> dict[str, Any]:
        """
        Get global environment variable overrides (not project-specific).

        Returns:
            Dictionary of global settings from environment variables
        """
        overrides = {}

        # Global project defaults
        if value := os.environ.get('BABLIB_PROJECT_MAX_FILE_SIZE'):
            try:
                overrides['project_max_file_size'] = int(value)
            except ValueError:
                logger.warning(f"Invalid BABLIB_PROJECT_MAX_FILE_SIZE: {value}")

        # CLI settings
        if value := os.environ.get('BABLIB_CLI_GLOBAL_UNIQUE_SHORTCUTS'):
            overrides['cli_global_unique_shortcuts'] = value.lower() in ('true', '1', 'yes')

        if value := os.environ.get('BABLIB_CLI_TWO_CHAR_FALLBACK'):
            overrides['cli_two_char_fallback'] = value.lower() in ('true', '1', 'yes')

        # Project type defaults
        for project_type in ['CRAWLING', 'DATA', 'STORAGE']:
            prefix = f"BABLIB_DEFAULT_{project_type}"

            if chunk_size := os.environ.get(f"{prefix}_CHUNK_SIZE"):
                try:
                    cls._set_nested_dict(
                        overrides,
                        f"project_defaults.{project_type.lower()}.chunk_size",
                        int(chunk_size)
                    )
                except ValueError:
                    pass

            if embedding_model := os.environ.get(f"{prefix}_EMBEDDING_MODEL"):
                cls._set_nested_dict(
                    overrides,
                    f"project_defaults.{project_type.lower()}.embedding_model",
                    embedding_model
                )

        return overrides

    @staticmethod
    def export_project_env_template(
        project_name: str,
        project_type: ProjectType
    ) -> str:
        """
        Generate environment variable template for a project.

        Args:
            project_name: Name of the project
            project_type: Type of the project

        Returns:
            Environment variable template as string
        """
        prefix = EnvironmentConfigHandler.get_project_env_prefix(project_name)
        template_lines = [
            f"# Environment variables for project: {project_name}",
            f"# Project type: {project_type.value}",
            "",
            "# File handling",
            f"# {prefix}_MAX_FILE_SIZE=10485760  # Max file size in bytes",
            "",
        ]

        if project_type == ProjectType.CRAWLING:
            template_lines.extend([
                "# Crawling settings",
                f"# {prefix}_CRAWL_DEPTH=3  # Crawl depth (1-10)",
                f"# {prefix}_RATE_LIMIT=1.0  # Requests per second",
                "",
            ])

        elif project_type == ProjectType.DATA:
            template_lines.extend([
                "# Vector processing settings",
                f"# {prefix}_CHUNK_SIZE=500  # Chunk size for embeddings",
                f"# {prefix}_CHUNK_OVERLAP=50  # Overlap between chunks",
                f"# {prefix}_EMBEDDING_MODEL=mxbai-embed-large",
                f"# {prefix}_VECTOR_STORE_TYPE=sqlite_vec  # or 'qdrant'",
                "",
            ])

        elif project_type == ProjectType.STORAGE:
            template_lines.extend([
                "# Storage settings",
                f"# {prefix}_ENABLE_COMPRESSION=true",
                f"# {prefix}_AUTO_TAGGING=true",
                f"# {prefix}_FULL_TEXT_INDEXING=true",
                "",
            ])

        template_lines.extend([
            "# Allowed file formats (comma-separated)",
            f"# {prefix}_ALLOWED_FORMATS=pdf,docx,txt,md,html",
            "",
            "# Note: These variables override project-specific settings",
            "# Note: Boolean values accept: true/false, 1/0, yes/no, on/off",
        ])

        return '\n'.join(template_lines)

    @staticmethod
    def validate_env_config() -> list[str]:
        """
        Validate environment variable configuration.

        Returns:
            List of validation warnings
        """
        warnings = []

        # Check for conflicting settings
        env_vars = os.environ
        project_prefixes = set()

        for key in env_vars:
            if key.startswith('BABLIB_PROJECT_'):
                # Extract project name from variable
                parts = key.split('_')
                if len(parts) >= 4:  # BABLIB_PROJECT_<NAME>_<SETTING>
                    project_prefix = '_'.join(parts[:3])
                    project_prefixes.add(project_prefix)

        # Check each project for consistency
        for prefix in project_prefixes:
            # Check for mixed project type settings
            has_crawling = any(k.startswith(f"{prefix}_CRAWL") for k in env_vars)
            has_data = any(k.startswith(f"{prefix}_CHUNK") or
                          k.startswith(f"{prefix}_EMBEDDING") for k in env_vars)
            has_storage = any(k.startswith(f"{prefix}_ENABLE_COMPRESSION") or
                            k.startswith(f"{prefix}_AUTO_TAGGING") for k in env_vars)

            setting_types = sum([has_crawling, has_data, has_storage])
            if setting_types > 1:
                project_name = prefix.replace('BABLIB_PROJECT_', '')
                warnings.append(
                    f"Project {project_name} has mixed type settings in environment variables"
                )

        # Check for deprecated variables
        deprecated_vars = [
            'BABLIB_REDIS_URL',
            'BABLIB_REDIS_PASSWORD',
            'BABLIB_REDIS_DEPLOYMENT'
        ]
        for var in deprecated_vars:
            if var in env_vars:
                warnings.append(f"Deprecated environment variable found: {var}")

        return warnings

    @classmethod
    def get_all_project_configs(cls) -> dict[str, dict[str, Any]]:
        """
        Get all project configurations from environment variables.

        Returns:
            Dictionary mapping project names to their env configurations
        """
        configs = {}
        processed_prefixes = set()

        for key in os.environ:
            if key.startswith('BABLIB_PROJECT_'):
                parts = key.split('_')
                if len(parts) >= 4:
                    # Extract project name (may be multiple parts)
                    # Pattern: BABLIB_PROJECT_<NAME>_<SETTING>
                    # Find the last part that's a known setting
                    for i in range(len(parts) - 1, 2, -1):
                        if parts[i] in cls.ENV_VAR_MAPPING:
                            project_parts = parts[2:i]
                            project_name = '_'.join(project_parts).lower()

                            if project_name not in configs:
                                configs[project_name] = cls.get_env_overrides(project_name)
                            break

        return configs
