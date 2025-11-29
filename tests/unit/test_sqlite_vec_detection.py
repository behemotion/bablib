"""Unit tests for SQLite-vec extension detection."""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.services.sqlite_vec_service import detect_sqlite_vec, SQLiteVecService
from src.core.config import BablibConfig
from src.models.vector_store_types import VectorStoreProvider


class TestSQLiteVecDetection:
    """Test SQLite-vec extension detection functionality."""

    def test_detect_sqlite_vec_success(self):
        """Test successful detection of SQLite-vec extension."""
        with patch("sqlite3.connect") as mock_connect:
            # Mock successful extension loading
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = ("0.1.3",)
            mock_conn.execute.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            with patch("src.services.sqlite_vec_service.sqlite_vec") as mock_sqlite_vec:
                mock_sqlite_vec.load = MagicMock()

                available, message = detect_sqlite_vec()

                assert available is True
                assert "0.1.3" in message
                mock_conn.enable_load_extension.assert_called()
                mock_sqlite_vec.load.assert_called_once_with(mock_conn)

    def test_detect_sqlite_vec_import_error(self):
        """Test detection when sqlite-vec is not installed."""
        with patch("src.services.sqlite_vec_service.sqlite_vec", None):
            available, message = detect_sqlite_vec()

            assert available is False
            assert "not installed" in message.lower()

    def test_detect_sqlite_vec_load_error(self):
        """Test detection when extension fails to load."""
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            with patch("src.services.sqlite_vec_service.sqlite_vec") as mock_sqlite_vec:
                # Simulate load failure
                mock_sqlite_vec.load.side_effect = Exception("Failed to load extension")

                available, message = detect_sqlite_vec()

                assert available is False
                assert "failed to load" in message.lower()

    def test_sqlite_version_check(self):
        """Test checking SQLite version compatibility."""
        service = SQLiteVecService(
            BablibConfig(
                database_path="/tmp/test.db",
                vector_store_provider=VectorStoreProvider.SQLITE_VEC,
            )
        )

        # Mock SQLite version
        with patch("sqlite3.sqlite_version_info", (3, 41, 0)):
            version_ok, message = service.check_sqlite_version()
            assert version_ok is True
            assert "3.41" in message

        with patch("sqlite3.sqlite_version_info", (3, 35, 0)):
            version_ok, message = service.check_sqlite_version()
            assert version_ok is False
            assert "requires" in message.lower()

    def test_extension_availability_check(self):
        """Test checking if extension is available at runtime."""
        service = SQLiteVecService(
            BablibConfig(
                database_path="/tmp/test.db",
                vector_store_provider=VectorStoreProvider.SQLITE_VEC,
            )
        )

        with patch.object(service, "detect_extension") as mock_detect:
            mock_detect.return_value = (True, "Extension available")

            available = service.is_extension_available()
            assert available is True

            mock_detect.return_value = (False, "Not available")
            available = service.is_extension_available()
            assert available is False

    @pytest.mark.asyncio
    async def test_initialize_with_missing_extension(self):
        """Test initialization fails gracefully when extension is missing."""
        service = SQLiteVecService(
            BablibConfig(
                database_path="/tmp/test.db",
                vector_store_provider=VectorStoreProvider.SQLITE_VEC,
            )
        )

        with patch.object(service, "detect_extension") as mock_detect:
            mock_detect.return_value = (False, "Extension not available")

            with pytest.raises(RuntimeError) as exc_info:
                await service.initialize()

            assert "sqlite-vec extension not available" in str(exc_info.value).lower()

    def test_suggest_installation_command(self):
        """Test generating installation suggestion for missing extension."""
        service = SQLiteVecService(
            BablibConfig(
                database_path="/tmp/test.db",
                vector_store_provider=VectorStoreProvider.SQLITE_VEC,
            )
        )

        suggestion = service.get_installation_suggestion()

        assert "pip install sqlite-vec" in suggestion
        assert "bablib services setup --service sqlite-vec" in suggestion

    @pytest.mark.asyncio
    async def test_auto_detect_in_setup(self):
        """Test automatic detection during service setup."""
        from src.services.service_configuration import ServiceConfigurationService

        service_config = ServiceConfigurationService(
            config=BablibConfig(
                database_path="/tmp/test.db",
                vector_store_provider=VectorStoreProvider.SQLITE_VEC,
            )
        )

        with patch("src.services.sqlite_vec_service.detect_sqlite_vec") as mock_detect:
            mock_detect.return_value = (True, "Extension available")

            status = await service_config.detect_sqlite_vec_status()

            assert status["available"] is True
            assert status["provider"] == "sqlite_vec"
            mock_detect.assert_called_once()

    def test_version_compatibility_matrix(self):
        """Test SQLite version compatibility checks."""
        test_cases = [
            ((3, 45, 0), True, "fully compatible"),
            ((3, 41, 0), True, "compatible"),
            ((3, 40, 0), False, "limited features"),
            ((3, 35, 0), False, "too old"),
        ]

        service = SQLiteVecService(
            BablibConfig(
                database_path="/tmp/test.db",
                vector_store_provider=VectorStoreProvider.SQLITE_VEC,
            )
        )

        for version, expected_ok, expected_msg_part in test_cases:
            with patch("sqlite3.sqlite_version_info", version):
                version_ok, message = service.check_sqlite_version()
                assert version_ok == expected_ok
                assert expected_msg_part in message.lower()