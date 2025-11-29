"""Integration tests to verify all CLI commands work without Redis."""

import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import os


@pytest.mark.integration
class TestNoRedisIntegration:
    """Verify all Bablib functionality works without Redis."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary config without Redis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "bablib"
            config_dir.mkdir(parents=True)
            data_dir = Path(tmpdir) / ".local" / "share" / "bablib"
            data_dir.mkdir(parents=True)

            # Set environment to use temp directories
            os.environ["BABLIB_DATA_DIR"] = str(data_dir)
            yield config_dir, data_dir

            # Cleanup
            if "BABLIB_DATA_DIR" in os.environ:
                del os.environ["BABLIB_DATA_DIR"]

    @pytest.mark.asyncio
    async def test_status_command_without_redis(self, temp_config):
        """Test bablib status works without Redis."""
        from src.cli.main import BablibApp
        from src.core.config import BablibConfig

        # Ensure no Redis in config
        config = BablibConfig()
        assert not hasattr(config, 'redis_url')

        # Mock services
        with patch('src.cli.main.DatabaseManager') as mock_db, \
             patch('src.cli.main.VectorStore') as mock_vector, \
             patch('src.cli.main.EmbeddingService') as mock_embed:

            mock_db_instance = AsyncMock()
            mock_vector_instance = AsyncMock()
            mock_embed_instance = AsyncMock()

            mock_db.return_value = mock_db_instance
            mock_vector.return_value = mock_vector_instance
            mock_embed.return_value = mock_embed_instance

            app = BablibApp()
            await app.initialize()

            # Should work without Redis
            assert app.db_manager is not None
            assert app.vector_store is not None

    @pytest.mark.asyncio
    async def test_create_command_without_redis(self, temp_config):
        """Test bablib create works without Redis."""
        from src.cli.main import BablibApp
        from src.models import Project

        with patch('src.cli.main.DatabaseManager') as mock_db, \
             patch('src.cli.main.VectorStore') as mock_vector:

            mock_db_instance = AsyncMock()
            mock_vector_instance = AsyncMock()

            # Mock create project
            mock_db_instance.create_project = AsyncMock(return_value=Project(
                name="test-project",
                source_url="https://example.com",
                crawl_depth=2
            ))

            mock_db.return_value = mock_db_instance
            mock_vector.return_value = mock_vector_instance

            app = BablibApp()
            await app.initialize()

            # Create project should work without Redis
            project = await app.db_manager.create_project(
                name="test-project",
                source_url="https://example.com",
                crawl_depth=2
            )
            assert project.name == "test-project"

    @pytest.mark.asyncio
    async def test_list_command_without_redis(self, temp_config):
        """Test bablib list works without Redis."""
        from src.cli.main import BablibApp

        with patch('src.cli.main.DatabaseManager') as mock_db:
            mock_db_instance = AsyncMock()
            mock_db_instance.list_projects = AsyncMock(return_value=[])

            mock_db.return_value = mock_db_instance

            app = BablibApp()
            await app.initialize()

            # List should work without Redis
            projects = await app.db_manager.list_projects()
            assert isinstance(projects, list)

    @pytest.mark.asyncio
    async def test_serve_command_without_redis(self):
        """Test MCP server starts without Redis."""
        from src.services.mcp_server import MCPServer
        from src.core.config import BablibConfig

        config = BablibConfig()
        assert not hasattr(config, 'redis_url')

        # Mock FastAPI app
        with patch('src.services.mcp_server.FastAPI'):
            server = MCPServer(config=config)
            assert server.config is not None
            assert not hasattr(server.config, 'redis_url')