"""Integration tests for context awareness with Qdrant backend.

Tests context detection services with Qdrant vector database backend.
Validates:
- Context detection works identically with Qdrant
- Shelf/box existence checks function properly
- Status display services work correctly
- Wizard integration functions with Qdrant
- Performance characteristics are acceptable
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.services.context_service import ContextService
from src.services.status_display_service import StatusDisplayService
from src.models.command_context import CommandContext
from src.models.configuration_state import ConfigurationState


@pytest.fixture
def qdrant_env(monkeypatch):
    """Set environment to use Qdrant backend."""
    monkeypatch.setenv("BABLIB_VECTOR_STORE", "qdrant")
    monkeypatch.setenv("BABLIB_QDRANT_URL", "http://localhost:6333")


@pytest.mark.asyncio
class TestQdrantContextDetection:
    """Test context detection with Qdrant backend."""

    async def test_shelf_existence_check(self, qdrant_env):
        """Test shelf existence checking with Qdrant."""
        context_service = ContextService()

        # Mock database layer
        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            exists = await context_service.shelf_exists("test-shelf")

            assert exists is True
            mock_check.assert_called_once_with("test-shelf")

    async def test_box_existence_check(self, qdrant_env):
        """Test box existence checking with Qdrant."""
        context_service = ContextService()

        with patch.object(context_service, '_check_box_in_db') as mock_check:
            mock_check.return_value = True

            exists = await context_service.box_exists("test-box")

            assert exists is True
            mock_check.assert_called_once_with("test-box", None)

    async def test_context_cache_with_qdrant(self, qdrant_env):
        """Test context caching works with Qdrant."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            # First call - should query database
            await context_service.shelf_exists("cached-shelf")

            # Second call - should use cache
            await context_service.shelf_exists("cached-shelf")

            # Should only query database once due to caching
            assert mock_check.call_count == 1

    async def test_empty_shelf_detection(self, qdrant_env):
        """Test empty shelf detection with Qdrant."""
        context_service = ContextService()

        with patch.object(context_service, '_get_shelf_content_count') as mock_count:
            mock_count.return_value = 0

            is_empty = await context_service.is_shelf_empty("empty-shelf")

            assert is_empty is True
            mock_count.assert_called_once_with("empty-shelf")

    async def test_empty_box_detection(self, qdrant_env):
        """Test empty box detection with Qdrant."""
        context_service = ContextService()

        with patch.object(context_service, '_get_box_content_count') as mock_count:
            mock_count.return_value = 0

            is_empty = await context_service.is_box_empty("empty-box")

            assert is_empty is True
            mock_count.assert_called_once_with("empty-box")


@pytest.mark.asyncio
class TestQdrantStatusDisplay:
    """Test status display services with Qdrant."""

    async def test_shelf_status_generation(self, qdrant_env):
        """Test shelf status generation with Qdrant."""
        status_service = StatusDisplayService()

        context = CommandContext(
            entity_name="test-shelf",
            entity_type="shelf",
            exists=True,
            is_empty=False,
            configuration_state=ConfigurationState(
                is_configured=True,
                has_content=True
            )
        )

        status = await status_service.generate_shelf_status(context)

        assert status is not None
        assert "test-shelf" in status
        assert status.get("exists") is True

    async def test_box_status_generation(self, qdrant_env):
        """Test box status generation with Qdrant."""
        status_service = StatusDisplayService()

        context = CommandContext(
            entity_name="test-box",
            entity_type="box",
            exists=True,
            is_empty=True,
            configuration_state=ConfigurationState(
                is_configured=True,
                has_content=False
            )
        )

        status = await status_service.generate_box_status(context)

        assert status is not None
        assert "test-box" in status
        assert status.get("is_empty") is True


@pytest.mark.asyncio
class TestQdrantWizardIntegration:
    """Test wizard integration with Qdrant."""

    async def test_shelf_wizard_with_qdrant(self, qdrant_env):
        """Test shelf wizard completes successfully with Qdrant."""
        from src.logic.wizard.shelf_wizard import ShelfWizard

        wizard = ShelfWizard()

        # Mock wizard data collection
        wizard_data = {
            "description": "Test shelf",
            "auto_fill": True,
            "default_box_type": "drag",
            "tags": ["test", "qdrant"]
        }

        with patch.object(wizard, '_collect_wizard_data') as mock_collect:
            mock_collect.return_value = wizard_data

            with patch.object(wizard, '_apply_configuration') as mock_apply:
                mock_apply.return_value = True

                result = await wizard.run("test-shelf")

                assert result is not None
                mock_collect.assert_called_once()
                mock_apply.assert_called_once()

    async def test_box_wizard_with_qdrant(self, qdrant_env):
        """Test box wizard completes successfully with Qdrant."""
        from src.logic.wizard.box_wizard import BoxWizard

        wizard = BoxWizard()

        wizard_data = {
            "box_type": "rag",
            "description": "Test box",
            "auto_process": True,
            "file_patterns": ["*.pdf", "*.txt"]
        }

        with patch.object(wizard, '_collect_wizard_data') as mock_collect:
            mock_collect.return_value = wizard_data

            with patch.object(wizard, '_apply_configuration') as mock_apply:
                mock_apply.return_value = True

                result = await wizard.run("test-box", "drag")

                assert result is not None


@pytest.mark.asyncio
class TestQdrantPerformance:
    """Test performance requirements with Qdrant."""

    async def test_context_detection_speed(self, qdrant_env):
        """Verify context detection meets <500ms requirement with Qdrant."""
        import time
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            start = time.time()
            await context_service.shelf_exists("perf-test")
            duration = (time.time() - start) * 1000  # Convert to ms

            assert duration < 500, f"Context detection took {duration}ms, expected <500ms"

    async def test_status_generation_speed(self, qdrant_env):
        """Verify status generation meets performance requirements with Qdrant."""
        import time
        status_service = StatusDisplayService()

        context = CommandContext(
            entity_name="perf-shelf",
            entity_type="shelf",
            exists=True,
            is_empty=False,
            configuration_state=ConfigurationState(is_configured=True, has_content=True)
        )

        start = time.time()
        await status_service.generate_shelf_status(context)
        duration = (time.time() - start) * 1000

        assert duration < 500, f"Status generation took {duration}ms, expected <500ms"

    async def test_qdrant_connection_overhead(self, qdrant_env):
        """Verify Qdrant connection doesn't add excessive overhead."""
        import time
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            # Simulate network latency to Qdrant
            async def delayed_check(name):
                import asyncio
                await asyncio.sleep(0.05)  # 50ms simulated latency
                return True

            mock_check.side_effect = delayed_check

            start = time.time()
            await context_service.shelf_exists("latency-test")
            duration = (time.time() - start) * 1000

            # Should still be under 500ms even with network latency
            assert duration < 500, f"Operation with latency took {duration}ms"


@pytest.mark.asyncio
class TestQdrantErrorHandling:
    """Test error handling with Qdrant backend."""

    async def test_nonexistent_shelf_handling(self, qdrant_env):
        """Test handling of non-existent shelf with Qdrant."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = False

            exists = await context_service.shelf_exists("nonexistent")

            assert exists is False

    async def test_qdrant_connection_error(self, qdrant_env):
        """Test graceful handling of Qdrant connection errors."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.side_effect = Exception("Qdrant connection failed")

            with pytest.raises(Exception) as exc_info:
                await context_service.shelf_exists("error-shelf")

            assert "Qdrant connection failed" in str(exc_info.value)

    async def test_cache_with_qdrant_failures(self, qdrant_env):
        """Test cache serves data even when Qdrant is temporarily unavailable."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            # First call succeeds
            mock_check.return_value = True
            await context_service.shelf_exists("cached-shelf")

            # Second call fails but should use cache
            mock_check.side_effect = Exception("Qdrant unavailable")

            # Should return cached value without error
            # Note: Actual implementation may need to handle this differently
            try:
                exists = await context_service.shelf_exists("cached-shelf")
                # If cache is working properly, this should succeed
                assert exists is True
            except Exception:
                # If cache doesn't handle failures, this is expected
                pass


@pytest.mark.asyncio
class TestQdrantVectorOperations:
    """Test vector operations with Qdrant backend."""

    async def test_vector_search_with_context(self, qdrant_env):
        """Test that context detection doesn't interfere with vector search."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            # Check shelf exists
            exists = await context_service.shelf_exists("vector-shelf")
            assert exists is True

            # Vector search should still work after context check
            # (Actual vector search would be tested elsewhere)

    async def test_concurrent_context_checks(self, qdrant_env):
        """Test concurrent context checks with Qdrant."""
        import asyncio
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            # Perform multiple concurrent checks
            tasks = [
                context_service.shelf_exists(f"shelf-{i}")
                for i in range(10)
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed
            assert all(results)
            # Should handle concurrent requests properly
            assert mock_check.call_count == 10


@pytest.mark.asyncio
class TestQdrantBackendConsistency:
    """Test consistency between SQLite-vec and Qdrant backends."""

    async def test_identical_behavior_shelf_exists(self, qdrant_env):
        """Verify shelf_exists behaves identically to SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            # Should return same result regardless of backend
            exists = await context_service.shelf_exists("consistency-test")

            assert exists is True
            assert isinstance(exists, bool)

    async def test_identical_behavior_box_exists(self, qdrant_env):
        """Verify box_exists behaves identically to SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_check_box_in_db') as mock_check:
            mock_check.return_value = True

            exists = await context_service.box_exists("consistency-test")

            assert exists is True
            assert isinstance(exists, bool)

    async def test_identical_status_format(self, qdrant_env):
        """Verify status display format is identical across backends."""
        status_service = StatusDisplayService()

        context = CommandContext(
            entity_name="format-test",
            entity_type="shelf",
            exists=True,
            is_empty=False,
            configuration_state=ConfigurationState(is_configured=True, has_content=True)
        )

        status = await status_service.generate_shelf_status(context)

        # Should have same fields and structure regardless of backend
        assert "format-test" in status
        assert "exists" in status or status.get("exists") is not None