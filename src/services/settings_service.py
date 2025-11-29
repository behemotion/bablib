"""
Settings service for managing Bablib configuration.
"""

import shutil
from datetime import datetime
from pathlib import Path

import yaml

from src.core.config import BablibConfig
from src.lib.paths import ensure_directory, get_global_settings_path
from src.models.settings import GlobalSettings


class SettingsService:
    """Service for managing Bablib settings."""

    def __init__(self):
        """Initialize settings service."""
        self.settings_path = get_global_settings_path()
        self.settings_version = "2.0.0"  # Bumped version for new structure

    def get_settings(self) -> BablibConfig:
        """Load settings from file or create defaults."""
        if self.settings_path.exists():
            try:
                with open(self.settings_path) as f:
                    data = yaml.safe_load(f)
                    if data and 'settings' in data:
                        settings_data = data['settings']

                        # Convert string back to enums if needed
                        if 'vector_store_provider' in settings_data and isinstance(settings_data['vector_store_provider'], str):
                            from src.models.vector_store_types import (
                                VectorStoreProvider,
                            )
                            settings_data['vector_store_provider'] = VectorStoreProvider.from_string(settings_data['vector_store_provider'])

                        if 'qdrant_deployment' in settings_data and isinstance(settings_data['qdrant_deployment'], str):
                            from src.core.config import ServiceDeployment
                            settings_data['qdrant_deployment'] = ServiceDeployment(settings_data['qdrant_deployment'])

                        if 'ollama_deployment' in settings_data and isinstance(settings_data['ollama_deployment'], str):
                            from src.core.config import ServiceDeployment
                            settings_data['ollama_deployment'] = ServiceDeployment(settings_data['ollama_deployment'])

                        return BablibConfig(**settings_data)
            except Exception as e:
                print(f"Warning: Failed to load settings: {e}")

        # Return defaults if file doesn't exist or is invalid
        return BablibConfig()

    def save_settings(self, settings: BablibConfig) -> None:
        """Save settings to file."""
        ensure_directory(self.settings_path.parent)

        # Convert settings to dict with proper enum serialization
        settings_dict = settings.model_dump()

        # Convert all enums to string values for YAML serialization
        if 'vector_store_provider' in settings_dict:
            settings_dict['vector_store_provider'] = settings_dict['vector_store_provider'].value
        if 'qdrant_deployment' in settings_dict:
            settings_dict['qdrant_deployment'] = settings_dict['qdrant_deployment'].value
        if 'ollama_deployment' in settings_dict:
            settings_dict['ollama_deployment'] = settings_dict['ollama_deployment'].value

        # Remove fields that shouldn't be persisted
        exclude_fields = ['data_dir', 'database_url', 'log_file']
        for field in exclude_fields:
            settings_dict.pop(field, None)

        data = {
            'version': self.settings_version,
            'settings': settings_dict,
            'metadata': {
                'updated_at': datetime.now().isoformat()
            }
        }

        with open(self.settings_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def update_setting(self, key: str, value: any) -> bool:
        """Update a single setting."""
        try:
            settings = self.get_settings()
            if hasattr(settings, key):
                setattr(settings, key, value)
                self.save_settings(settings)
                return True
            return False
        except Exception:
            return False

    def reset_to_defaults(self, backup: bool = True) -> Path | None:
        """Reset settings to factory defaults."""
        if backup and self.settings_path.exists():
            # Create backup
            backup_path = self.settings_path.with_suffix(
                f'.yaml.backup.{datetime.now().strftime("%Y%m%d-%H%M%S")}'
            )
            shutil.copy2(self.settings_path, backup_path)
        else:
            backup_path = None

        # Save factory defaults
        default_settings = BablibConfig()
        self.save_settings(default_settings)

        return backup_path

    def migrate_from_v1(self) -> bool:
        """Migrate settings from v1.0.0 format if needed."""
        if not self.settings_path.exists():
            return True

        try:
            with open(self.settings_path) as f:
                data = yaml.safe_load(f)

            # Check if this is v1 format
            if data and data.get('version') == '1.0.0':
                # Backup old settings
                backup_path = self.settings_path.with_suffix('.yaml.v1_backup')
                shutil.copy2(self.settings_path, backup_path)

                # Migrate to new format
                old_settings = data.get('settings', {})
                new_config = BablibConfig(**old_settings)
                self.save_settings(new_config)

                print(f"Migrated settings from v1 to v2 format. Backup saved to {backup_path}")
                return True

        except Exception as e:
            print(f"Warning: Failed to migrate settings: {e}")
            return False

        return True

    # Compatibility methods for test suite
    def get_global_settings(self) -> GlobalSettings:
        """Get global settings as GlobalSettings model for backward compatibility."""
        # For backward compatibility, return GlobalSettings with its own defaults
        # rather than converting from BablibConfig which has different defaults
        return GlobalSettings()

    def save_global_settings(self, settings: GlobalSettings) -> None:
        """Save global settings from GlobalSettings model for backward compatibility."""
        # Convert back to BablibConfig
        config = BablibConfig(**settings.model_dump())
        self.save_settings(config)

    def validate_settings(self, settings_dict: dict) -> tuple[bool, list[str]]:
        """Validate settings dictionary for backward compatibility."""
        try:
            # Try to create GlobalSettings from the dict
            GlobalSettings(**settings_dict)
            return True, []
        except Exception as e:
            return False, [str(e)]

