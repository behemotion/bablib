"""Contract tests for configuration validation without Redis."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestConfigValidation:
    """Validate configuration properly rejects Redis settings."""

    def test_clean_config_passes_validation(self):
        """Verify clean configuration without Redis passes validation."""
        from src.core.config import BablibConfig

        # Clean environment
        for key in list(os.environ.keys()):
            if 'REDIS' in key:
                del os.environ[key]

        # This should work without Redis
        config = BablibConfig()
        assert config.qdrant_url == "http://localhost:6333"
        assert config.ollama_url == "http://localhost:11434"
        assert not hasattr(config, 'redis_url')

    def test_redis_url_causes_validation_error(self):
        """Verify Redis URL in config causes validation error."""
        from src.core.config import BablibConfig

        os.environ["BABLIB_REDIS_URL"] = "redis://localhost:6379"

        with pytest.raises(ValueError) as exc_info:
            config = BablibConfig()

        assert "Redis configuration detected" in str(exc_info.value)
        del os.environ["BABLIB_REDIS_URL"]

    def test_redis_password_causes_validation_error(self):
        """Verify Redis password in config causes validation error."""
        from src.core.config import BablibConfig

        os.environ["BABLIB_REDIS_PASSWORD"] = "secret"

        with pytest.raises(ValueError) as exc_info:
            config = BablibConfig()

        assert "Redis configuration detected" in str(exc_info.value)
        del os.environ["BABLIB_REDIS_PASSWORD"]

    def test_detect_service_availability_excludes_redis(self):
        """Verify service detection excludes Redis."""
        from src.core.config import BablibConfig

        config = BablibConfig()
        availability = config.detect_service_availability()

        # Should check these services but not Redis
        assert "qdrant" in availability
        assert "ollama" in availability
        assert "docker" in availability
        assert "redis" not in availability

    def test_deployment_strategy_excludes_redis(self):
        """Verify deployment strategy excludes Redis."""
        from src.core.config import BablibConfig

        config = BablibConfig()
        strategy = config.get_effective_deployment_strategy()

        # Should have strategies for these but not Redis
        assert "qdrant" in strategy
        assert "ollama" in strategy
        assert "redis" not in strategy