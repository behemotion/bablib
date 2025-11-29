"""Configuration validator service for health checks."""

from pathlib import Path
from typing import Any

import yaml

from ..models.category import HealthCategory
from ..models.health_check import HealthCheck
from ..models.status import HealthStatus


class ConfigurationValidator:
    """Service for validating Bablib configuration files."""

    def __init__(self):
        """Initialize configuration validator."""
        self.config_paths = self._get_config_paths()

    async def validate_global_settings(self) -> HealthCheck:
        """Validate global Bablib settings file."""
        execution_start = self._get_current_time()

        try:
            settings_path = self.config_paths.get('settings')

            if not settings_path or not settings_path.exists():
                status = HealthStatus.WARNING
                message = "Global settings file not found"
                details = f"Expected location: {settings_path}" if settings_path else "No settings path configured"
                resolution = "Run 'bablib setup' to create initial configuration"
            else:
                # Try to load and validate settings
                validation_result = await self._validate_yaml_file(settings_path)

                if validation_result['valid']:
                    status = HealthStatus.HEALTHY
                    message = "Global settings file is valid"
                    details = f"Configuration loaded from {settings_path}"
                    resolution = None
                else:
                    status = HealthStatus.ERROR
                    message = "Global settings file is invalid"
                    details = validation_result['error']
                    resolution = "Fix configuration errors or run 'bablib setup --reset'"

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="config.global_settings",
                category=HealthCategory.CONFIGURATION,
                name="Global Settings",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="config.global_settings",
                category=HealthCategory.CONFIGURATION,
                name="Global Settings",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to validate global settings",
                details=str(e),
                resolution="Check file permissions and configuration directory access",
                execution_time=execution_time
            )

    async def validate_project_configurations(self) -> HealthCheck:
        """Validate project-specific configurations."""
        execution_start = self._get_current_time()

        try:
            projects_dir = self.config_paths.get('projects')

            if not projects_dir or not projects_dir.exists():
                status = HealthStatus.HEALTHY  # OK to have no projects
                message = "No project configurations found"
                details = "Projects directory not found (normal for new installation)"
                resolution = None
            else:
                # Count and validate project configs
                project_configs = list(projects_dir.glob("*/config.yaml"))
                valid_count = 0
                invalid_configs = []

                for config_path in project_configs:
                    validation_result = await self._validate_yaml_file(config_path)
                    if validation_result['valid']:
                        valid_count += 1
                    else:
                        invalid_configs.append(config_path.parent.name)

                if not project_configs:
                    status = HealthStatus.HEALTHY
                    message = "No project configurations to validate"
                    details = "Projects directory exists but is empty"
                    resolution = None
                elif invalid_configs:
                    status = HealthStatus.ERROR
                    message = f"Invalid project configurations: {', '.join(invalid_configs)}"
                    details = f"Valid: {valid_count}, Invalid: {len(invalid_configs)}"
                    resolution = "Fix project configurations or remove invalid projects"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"All {valid_count} project configurations are valid"
                    details = f"Validated {valid_count} project configurations"
                    resolution = None

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="config.project_configs",
                category=HealthCategory.CONFIGURATION,
                name="Project Configurations",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="config.project_configs",
                category=HealthCategory.CONFIGURATION,
                name="Project Configurations",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to validate project configurations",
                details=str(e),
                resolution="Check projects directory permissions and access",
                execution_time=execution_time
            )

    async def validate_vector_store_config(self) -> HealthCheck:
        """Validate vector store configuration."""
        execution_start = self._get_current_time()

        try:
            settings_path = self.config_paths.get('settings')

            if not settings_path or not settings_path.exists():
                status = HealthStatus.WARNING
                message = "Vector store configuration not found"
                details = "Global settings file missing"
                resolution = "Run 'bablib setup' to configure vector store"
            else:
                # Load settings and check vector store configuration
                settings_data = await self._load_yaml_file(settings_path)

                if not settings_data:
                    status = HealthStatus.ERROR
                    message = "Cannot read vector store configuration"
                    details = "Global settings file is corrupted or empty"
                    resolution = "Run 'bablib setup --reset' to regenerate configuration"
                else:
                    vector_provider = settings_data.get('vector_store_provider')

                    if not vector_provider:
                        status = HealthStatus.WARNING
                        message = "Vector store provider not configured"
                        details = "No vector_store_provider specified in settings"
                        resolution = "Run 'bablib setup --vector-store <provider>' to configure"
                    elif vector_provider in ['sqlite_vec', 'qdrant']:
                        status = HealthStatus.HEALTHY
                        message = f"Vector store configured: {vector_provider}"
                        details = f"Using {vector_provider} as vector store provider"
                        resolution = None
                    else:
                        status = HealthStatus.ERROR
                        message = f"Invalid vector store provider: {vector_provider}"
                        details = f"Unknown provider: {vector_provider}"
                        resolution = "Set vector_store_provider to 'sqlite_vec' or 'qdrant'"

            execution_time = self._get_current_time() - execution_start

            return HealthCheck(
                id="config.vector_store",
                category=HealthCategory.CONFIGURATION,
                name="Vector Store Configuration",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = self._get_current_time() - execution_start
            return HealthCheck(
                id="config.vector_store",
                category=HealthCategory.CONFIGURATION,
                name="Vector Store Configuration",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to validate vector store configuration",
                details=str(e),
                resolution="Check configuration file permissions and format",
                execution_time=execution_time
            )

    async def validate_all_configurations(self) -> list[HealthCheck]:
        """Validate all configuration files."""
        import asyncio

        # Run all configuration checks in parallel
        checks = await asyncio.gather(
            self.validate_global_settings(),
            self.validate_project_configurations(),
            self.validate_vector_store_config(),
            return_exceptions=True
        )

        # Filter out any exceptions and convert to HealthCheck objects
        valid_checks = []
        for check in checks:
            if isinstance(check, HealthCheck):
                valid_checks.append(check)
            elif isinstance(check, Exception):
                # Create error health check for failed validation
                valid_checks.append(HealthCheck(
                    id="config.unknown_error",
                    category=HealthCategory.CONFIGURATION,
                    name="Configuration Validation Error",
                    status=HealthStatus.ERROR,
                    message="Configuration validation failed",
                    details=str(check),
                    resolution="Check configuration files and permissions",
                    execution_time=0.0
                ))

        return valid_checks

    def _get_config_paths(self) -> dict[str, Path | None]:
        """Get configuration file paths."""
        try:
            from src.services.config import ConfigService
            config_service = ConfigService()

            return {
                'settings': config_service.config_dir / 'settings.yaml',
                'projects': config_service.data_dir / 'projects'
            }
        except Exception:
            # Fallback to standard XDG paths
            import os
            from pathlib import Path

            config_dir = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'bablib'
            data_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'bablib'

            return {
                'settings': config_dir / 'settings.yaml',
                'projects': data_dir / 'projects'
            }

    async def _validate_yaml_file(self, file_path: Path) -> dict[str, Any]:
        """Validate a YAML file and return validation result."""
        try:
            if not file_path.exists():
                return {'valid': False, 'error': 'File does not exist'}

            with open(file_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if data is None:
                return {'valid': False, 'error': 'File is empty or contains only comments'}

            return {'valid': True, 'data': data}

        except yaml.YAMLError as e:
            return {'valid': False, 'error': f'YAML syntax error: {e}'}
        except PermissionError:
            return {'valid': False, 'error': 'Permission denied reading file'}
        except Exception as e:
            return {'valid': False, 'error': f'Unexpected error: {e}'}

    async def _load_yaml_file(self, file_path: Path) -> dict[str, Any] | None:
        """Load a YAML file and return its contents."""
        try:
            if not file_path.exists():
                return None

            with open(file_path, encoding='utf-8') as f:
                return yaml.safe_load(f)

        except Exception:
            return None

    def _get_current_time(self) -> float:
        """Get current time for execution timing."""
        import time
        return time.time()
