"""Contract tests for Redis removal validation."""

import os
import subprocess
from pathlib import Path
import pytest


class TestRedisRemoval:
    """Validate Redis has been completely removed from the codebase."""

    def test_no_redis_imports_in_source(self):
        """Verify no Redis imports exist in source code."""
        src_dir = Path(__file__).parent.parent.parent / "src"

        # Check for direct Redis imports
        result = subprocess.run(
            ["grep", "-r", "import redis", str(src_dir)],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0, f"Found Redis imports: {result.stdout}"

        # Check for from redis imports
        result = subprocess.run(
            ["grep", "-r", "from redis", str(src_dir)],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0, f"Found Redis imports: {result.stdout}"

    def test_no_redis_in_dependencies(self):
        """Verify Redis is not in project dependencies."""
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            assert "redis" not in content.lower(), "Redis found in pyproject.toml dependencies"

    def test_redis_config_rejected(self):
        """Verify Redis configuration is rejected."""
        from src.core.config import BablibConfig

        # Test that Redis environment variables are rejected
        os.environ["BABLIB_REDIS_URL"] = "redis://localhost:6379"

        with pytest.raises(ValueError, match="Redis configuration detected"):
            config = BablibConfig()

        # Clean up
        del os.environ["BABLIB_REDIS_URL"]

    def test_no_redis_in_docker_compose(self):
        """Verify Redis is not in Docker Compose configuration."""
        docker_compose_path = Path(__file__).parent.parent.parent / "docker" / "docker-compose.yml"
        if docker_compose_path.exists():
            content = docker_compose_path.read_text()
            assert "redis" not in content.lower(), "Redis service found in docker-compose.yml"

    def test_services_work_without_redis(self):
        """Verify core services initialize without Redis."""
        from src.services.database import DatabaseManager
        from src.services.vector_store import VectorStoreService
        from src.core.config import BablibConfig

        # These should initialize without any Redis dependency
        config = BablibConfig()
        assert hasattr(config, 'qdrant_url'), "Qdrant config should exist"
        assert not hasattr(config, 'redis_url'), "Redis config should not exist"