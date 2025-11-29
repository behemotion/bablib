"""Contract tests for SQLiteVecConfiguration model."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from src.models.sqlite_vec_config import SQLiteVecConfiguration


class TestSQLiteVecConfiguration:
    """Test SQLiteVecConfiguration model validation and behavior."""

    def test_create_with_defaults(self, tmp_path):
        """Test creating configuration with default values."""
        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=tmp_path / "vectors.db"
        )

        assert config.enabled is True
        assert config.database_path == tmp_path / "vectors.db"
        assert config.vector_dimensions == 1024
        assert config.batch_size == 100
        assert config.max_connections == 5
        assert config.wal_mode is True
        assert config.busy_timeout == 5000

    def test_vector_dimensions_validation(self, tmp_path):
        """Test vector dimensions must be within valid range."""
        # Valid dimensions
        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=tmp_path / "vectors.db",
            vector_dimensions=2048
        )
        assert config.vector_dimensions == 2048

        # Invalid: too small
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path=tmp_path / "vectors.db",
                vector_dimensions=0
            )
        assert "greater than or equal to 1" in str(exc_info.value).lower()

        # Invalid: too large
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path=tmp_path / "vectors.db",
                vector_dimensions=4097
            )
        assert ("less than or equal to 4096" in str(exc_info.value).lower() or
                "input should be less than or equal to 4096" in str(exc_info.value).lower())

    def test_batch_size_validation(self, tmp_path):
        """Test batch size must be within valid range."""
        # Valid batch size
        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=tmp_path / "vectors.db",
            batch_size=500
        )
        assert config.batch_size == 500

        # Invalid: too small
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path=tmp_path / "vectors.db",
                batch_size=0
            )
        assert ("at least 1" in str(exc_info.value).lower() or
                "greater than or equal to 1" in str(exc_info.value).lower())

        # Invalid: too large
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path=tmp_path / "vectors.db",
                batch_size=1001
            )
        assert ("at most 1000" in str(exc_info.value).lower() or
                "less than or equal to 1000" in str(exc_info.value).lower())

    def test_max_connections_validation(self, tmp_path):
        """Test max connections must be within valid range."""
        # Valid connections
        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=tmp_path / "vectors.db",
            max_connections=8
        )
        assert config.max_connections == 8

        # Invalid: too small
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path=tmp_path / "vectors.db",
                max_connections=0
            )
        assert ("at least 1" in str(exc_info.value).lower() or
                "greater than or equal to 1" in str(exc_info.value).lower())

        # Invalid: too large
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path=tmp_path / "vectors.db",
                max_connections=11
            )
        assert ("at most 10" in str(exc_info.value).lower() or
                "less than or equal to 10" in str(exc_info.value).lower())

    def test_database_path_validation(self, tmp_path):
        """Test database path must be within data directory."""
        # Valid path within data directory
        data_dir = tmp_path / ".local" / "share" / "bablib"
        data_dir.mkdir(parents=True)

        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=data_dir / "project" / "vectors.db",
            data_directory=data_dir
        )
        assert config.database_path == data_dir / "project" / "vectors.db"

        # Invalid: path outside data directory
        with pytest.raises(ValidationError) as exc_info:
            SQLiteVecConfiguration(
                enabled=True,
                database_path="/etc/vectors.db",
                data_directory=data_dir
            )
        assert "must be within data directory" in str(exc_info.value).lower()

    def test_configuration_serialization(self, tmp_path):
        """Test configuration can be serialized and deserialized."""
        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=tmp_path / "vectors.db",
            vector_dimensions=768,
            batch_size=200,
            max_connections=3,
            wal_mode=False,
            busy_timeout=10000
        )

        # Serialize to dict
        config_dict = config.model_dump()
        assert config_dict["enabled"] is True
        assert str(config_dict["database_path"]).endswith("vectors.db")
        assert config_dict["vector_dimensions"] == 768
        assert config_dict["batch_size"] == 200
        assert config_dict["max_connections"] == 3
        assert config_dict["wal_mode"] is False
        assert config_dict["busy_timeout"] == 10000

        # Deserialize from dict
        config2 = SQLiteVecConfiguration(**config_dict)
        assert config2 == config

    def test_get_connection_string(self, tmp_path):
        """Test generating SQLite connection string with parameters."""
        config = SQLiteVecConfiguration(
            enabled=True,
            database_path=tmp_path / "vectors.db",
            wal_mode=True,
            busy_timeout=5000
        )

        conn_str = config.get_connection_string()
        assert str(tmp_path / "vectors.db") in conn_str
        assert "mode=wal" in conn_str.lower() or "journal_mode=wal" in conn_str.lower()
        assert "busy_timeout=5000" in conn_str.lower() or "timeout=5" in conn_str.lower()