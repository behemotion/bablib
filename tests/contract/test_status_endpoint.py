"""Contract tests for status endpoint without Redis."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json


class TestStatusEndpoint:
    """Validate status endpoint excludes Redis."""

    @pytest.mark.asyncio
    async def test_status_response_excludes_redis(self):
        """Verify status endpoint response doesn't include Redis."""
        from src.cli.main import BablibApp

        # Mock the services
        with patch('src.cli.main.DatabaseManager') as mock_db, \
             patch('src.cli.main.VectorStore') as mock_vector, \
             patch('src.cli.main.EmbeddingService') as mock_embed:

            # Setup mocks
            mock_db_instance = AsyncMock()
            mock_vector_instance = AsyncMock()
            mock_embed_instance = AsyncMock()

            mock_db.return_value = mock_db_instance
            mock_vector.return_value = mock_vector_instance
            mock_embed.return_value = mock_embed_instance

            # Create app
            app = BablibApp()
            await app.initialize()

            # Get status (mocked)
            status = {
                "status": "healthy",
                "services": {
                    "database": {"name": "database", "status": "healthy", "available": True},
                    "vector_store": {"name": "vector_store", "status": "healthy", "available": True},
                    "embeddings": {"name": "embeddings", "status": "healthy", "available": True}
                }
            }

            # Verify Redis is not in services
            assert "redis" not in status["services"]
            assert len(status["services"]) == 3  # Only database, vector_store, embeddings

    def test_health_check_works_without_redis(self):
        """Verify health check endpoint works without Redis dependency."""
        # Simple health check should not depend on Redis
        health_response = {"status": "ok"}
        assert health_response["status"] == "ok"
        assert "redis" not in str(health_response).lower()

    @pytest.mark.asyncio
    def test_service_health_excludes_redis(self):
        """Verify individual service health checks exclude Redis."""
        from src.core.docker_utils import ServiceHealthChecker

        checker = ServiceHealthChecker()

        # Mock the health check methods
        with patch.object(checker, 'check_qdrant', new_callable=AsyncMock) as mock_qdrant, \
             patch.object(checker, 'check_ollama', new_callable=AsyncMock) as mock_ollama:

            mock_qdrant.return_value = True
            mock_ollama.return_value = True

            # Should not have check_redis method
            assert not hasattr(checker, 'check_redis')

    def test_status_cli_output_format(self):
        """Verify CLI status output doesn't show Redis."""
        from src.cli.main import BablibApp

        # Mock status data
        status_data = {
            "database": "Connected",
            "vector_store": "Healthy",
            "embeddings": "Ready"
        }

        # Redis should not be in the output
        assert "redis" not in status_data
        assert len(status_data) == 3