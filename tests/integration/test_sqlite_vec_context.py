"""Integration tests for context awareness with SQLite-vec backend.

Tests context detection services with SQLite-vec vector database backend.
Validates:
- Context detection works identically with SQLite-vec
- Shelf/box existence checks function properly
- Status display services work correctly
- Wizard integration functions with SQLite-vec
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.services.context_service import ContextService
from src.services.status_display_service import StatusDisplayService
from src.models.command_context import CommandContext
from src.models.configuration_state import ConfigurationState


@pytest.fixture
def sqlite_vec_env(monkeypatch):
    """Set environment to use SQLite-vec backend."""
    monkeypatch.setenv("BABLIB_VECTOR_STORE", "sqlite_vec")


@pytest.mark.asyncio
class TestSQLiteVecContextDetection:
    """Test context detection with SQLite-vec backend."""

    async def test_shelf_existence_check(self, sqlite_vec_env):
        """Test shelf existence checking with SQLite-vec."""
        context_service = ContextService()

        # Mock database layer
        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            exists = await context_service.shelf_exists("test-shelf")

            assert exists is True
            mock_check.assert_called_once_with("test-shelf")

    async def test_box_existence_check(self, sqlite_vec_env):
        """Test box existence checking with SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_check_box_in_db') as mock_check:
            mock_check.return_value = True

            exists = await context_service.box_exists("test-box")

            assert exists is True
            mock_check.assert_called_once_with("test-box", None)

    async def test_context_cache_with_sqlite_vec(self, sqlite_vec_env):
        """Test context caching works with SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            # First call - should query database
            await context_service.shelf_exists("cached-shelf")

            # Second call - should use cache
            await context_service.shelf_exists("cached-shelf")

            # Should only query database once due to caching
            assert mock_check.call_count == 1

    async def test_empty_shelf_detection(self, sqlite_vec_env):
        """Test empty shelf detection with SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_get_shelf_content_count') as mock_count:
            mock_count.return_value = 0

            is_empty = await context_service.is_shelf_empty("empty-shelf")

            assert is_empty is True
            mock_count.assert_called_once_with("empty-shelf")

    async def test_empty_box_detection(self, sqlite_vec_env):
        """Test empty box detection with SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_get_box_content_count') as mock_count:
            mock_count.return_value = 0

            is_empty = await context_service.is_box_empty("empty-box")

            assert is_empty is True
            mock_count.assert_called_once_with("empty-box")


@pytest.mark.asyncio
class TestSQLiteVecStatusDisplay:
    """Test status display services with SQLite-vec."""

    async def test_shelf_status_generation(self, sqlite_vec_env):
        """Test shelf status generation with SQLite-vec."""
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

    async def test_box_status_generation(self, sqlite_vec_env):
        """Test box status generation with SQLite-vec."""
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
class TestSQLiteVecWizardIntegration:
    """Test wizard integration with SQLite-vec."""

    async def test_shelf_wizard_with_sqlite_vec(self, sqlite_vec_env):
        """Test shelf wizard completes successfully with SQLite-vec."""
        from src.logic.wizard.shelf_wizard import ShelfWizard

        wizard = ShelfWizard()

        # Mock wizard data collection
        wizard_data = {
            "description": "Test shelf",
            "auto_fill": True,
            "default_box_type": "drag",
            "tags": ["test", "sqlite"]
        }

        with patch.object(wizard, '_collect_wizard_data') as mock_collect:
            mock_collect.return_value = wizard_data

            with patch.object(wizard, '_apply_configuration') as mock_apply:
                mock_apply.return_value = True

                result = await wizard.run("test-shelf")

                assert result is not None
                mock_collect.assert_called_once()
                mock_apply.assert_called_once()

    async def test_box_wizard_with_sqlite_vec(self, sqlite_vec_env):
        """Test box wizard completes successfully with SQLite-vec."""
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
class TestSQLiteVecPerformance:
    """Test performance requirements with SQLite-vec."""

    async def test_context_detection_speed(self, sqlite_vec_env):
        """Verify context detection meets <500ms requirement."""
        import time
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            start = time.time()
            await context_service.shelf_exists("perf-test")
            duration = (time.time() - start) * 1000  # Convert to ms

            assert duration < 500, f"Context detection took {duration}ms, expected <500ms"

    async def test_status_generation_speed(self, sqlite_vec_env):
        """Verify status generation meets performance requirements."""
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


@pytest.mark.asyncio
class TestSQLiteVecErrorHandling:
    """Test error handling with SQLite-vec backend."""

    async def test_nonexistent_shelf_handling(self, sqlite_vec_env):
        """Test handling of non-existent shelf with SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = False

            exists = await context_service.shelf_exists("nonexistent")

            assert exists is False

    async def test_database_error_handling(self, sqlite_vec_env):
        """Test graceful handling of database errors with SQLite-vec."""
        context_service = ContextService()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception) as exc_info:
                await context_service.shelf_exists("error-shelf")

            assert "Database connection failed" in str(exc_info.value)

    async def test_cache_corruption_recovery(self, sqlite_vec_env):
        """Test recovery from cache corruption with SQLite-vec."""
        context_service = ContextService()

        # Simulate cache corruption by clearing internal cache
        if hasattr(context_service, '_cache'):
            context_service._cache.clear()

        with patch.object(context_service, '_check_shelf_in_db') as mock_check:
            mock_check.return_value = True

            # Should recover by querying database
            exists = await context_service.shelf_exists("recovery-test")

            assert exists is True