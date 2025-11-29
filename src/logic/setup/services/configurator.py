"""Setup configuration service."""

from pathlib import Path
from typing import Any

import yaml

from src.core.lib_logger import get_logger

logger = get_logger(__name__)


class SetupConfigurator:
    """Service for managing setup configuration."""

    def __init__(self, home_dir: Path | None = None):
        """Initialize the configurator.

        Args:
            home_dir: Optional home directory for testing
        """
        self.home_dir = home_dir or Path.home()
        self.config_dir = self.home_dir / ".config" / "bablib"
        self.config_file = self.config_dir / "settings.yaml"

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

        with open(self.config_file) as f:
            config = yaml.safe_load(f) or {}

        logger.debug(f"Loaded configuration from {self.config_file}")
        return config

    def save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save
        """
        # Ensure directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Save with nice formatting
        with open(self.config_file, "w") as f:
            yaml.dump(
                config,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                indent=2
            )

        logger.info(f"Saved configuration to {self.config_file}")

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update existing configuration with new values.

        Args:
            updates: Dictionary of updates to apply

        Returns:
            Updated configuration
        """
        try:
            config = self.load_config()
        except FileNotFoundError:
            config = {}

        config.update(updates)
        self.save_config(config)
        return config

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            config = self.load_config()
            return config.get(key, default)
        except FileNotFoundError:
            return default

    def set_config_value(self, key: str, value: Any) -> None:
        """Set a specific configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        try:
            config = self.load_config()
        except FileNotFoundError:
            config = {}

        config[key] = value
        self.save_config(config)

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate configuration values.

        Args:
            config: Configuration to validate

        Returns:
            Validation results
        """
        errors = []
        warnings = []

        # Check required fields
        required_fields = ["vector_store_provider", "ollama_url", "embedding_model"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate vector store provider
        if "vector_store_provider" in config:
            valid_providers = ["sqlite_vec", "qdrant"]
            if config["vector_store_provider"] not in valid_providers:
                errors.append(
                    f"Invalid vector_store_provider: {config['vector_store_provider']}. "
                    f"Must be one of: {', '.join(valid_providers)}"
                )

        # Validate URLs
        if "ollama_url" in config:
            url = config["ollama_url"]
            if not url.startswith(("http://", "https://")):
                errors.append(f"Invalid ollama_url format: {url}")

        # Validate embedding model
        if "embedding_model" in config:
            valid_models = ["mxbai-embed-large", "nomic-embed-text", "all-minilm"]
            if config["embedding_model"] not in valid_models:
                warnings.append(
                    f"Unknown embedding model: {config['embedding_model']}. "
                    f"Known models: {', '.join(valid_models)}"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def reset_to_defaults(self) -> dict[str, Any]:
        """Reset configuration to defaults.

        Returns:
            Default configuration
        """
        from src.logic.setup.services.initializer import SetupInitializer
        initializer = SetupInitializer(home_dir=self.home_dir)

        default_config = initializer.create_default_config()
        self.save_config(default_config)

        logger.info("Reset configuration to defaults")
        return default_config
