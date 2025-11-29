"""Integration tests for bablib system-check with SQLite-vec."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from src.cli.main import cli


class TestSystemCheckWithSQLiteVec:
    """Test bablib system-check command with SQLite-vec configuration."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sqlite_vec_config(self, tmp_path):
        """Create configuration with SQLite-vec."""
        config_dir = tmp_path / ".config" / "bablib"
        config_dir.mkdir(parents=True)

        config_file = config_dir / "config.yaml"
        import yaml
        with open(config_file, "w") as f:
            yaml.dump({
                "vector_store": {
                    "provider": "sqlite_vec",
                    "sqlite_vec_config": {
                        "enabled": True,
                        "database_path": str(tmp_path / "data" / "vectors.db")
                    }
                }
            }, f)

        return tmp_path, config_file

    def test_system_check_sqlite_vec_available(self, runner, sqlite_vec_config):
        """Test system-check when SQLite-vec is available."""
        work_dir, config_file = sqlite_vec_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3")

                with patch("sqlite3.sqlite_version", "3.45.0"):
                    result = runner.invoke(
                        cli,
                        ["system-check"],
                        catch_exceptions=False
                    )

                    assert result.exit_code == 0
                    assert "Vector Store:" in result.output
                    assert "Provider: sqlite_vec" in result.output
                    assert "✓ SQLite version: 3.45.0" in result.output
                    assert "✓ sqlite-vec extension: 0.1.3" in result.output
                    assert "✓ Database path writable" in result.output
                    assert "Status: READY" in result.output

    def test_system_check_sqlite_vec_not_installed(self, runner, sqlite_vec_config):
        """Test system-check when SQLite-vec is not installed."""
        work_dir, config_file = sqlite_vec_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (False, "Extension not installed")

                result = runner.invoke(
                    cli,
                    ["system-check"],
                    catch_exceptions=False
                )

                assert result.exit_code != 0
                assert "✗ sqlite-vec extension: Not installed" in result.output
                assert "pip install sqlite-vec" in result.output
                assert "Status: ERROR" in result.output or "Status: NOT READY" in result.output

    def test_system_check_sqlite_version_warning(self, runner, sqlite_vec_config):
        """Test system-check with old SQLite version."""
        work_dir, config_file = sqlite_vec_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3")

                with patch("sqlite3.sqlite_version_info", (3, 35, 0)):
                    with patch("sqlite3.sqlite_version", "3.35.0"):
                        result = runner.invoke(
                            cli,
                            ["system-check"],
                            catch_exceptions=False
                        )

                        assert "⚠️" in result.output or "Warning" in result.output
                        assert "SQLite version: 3.35.0" in result.output
                        assert "recommended" in result.output.lower() or "upgrade" in result.output.lower()

    def test_system_check_database_path_permissions(self, runner, sqlite_vec_config):
        """Test system-check verifies database path permissions."""
        work_dir, config_file = sqlite_vec_config

        # Create data directory without write permissions
        data_dir = work_dir / "data"
        data_dir.mkdir(mode=0o555)  # Read-only

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3")

                result = runner.invoke(
                    cli,
                    ["system-check"],
                    catch_exceptions=False
                )

                assert "Database path" in result.output
                assert "writable" in result.output.lower() or "permission" in result.output.lower()

    def test_system_check_shows_project_stats(self, runner, sqlite_vec_config):
        """Test system-check shows SQLite-vec project statistics."""
        work_dir, config_file = sqlite_vec_config

        # Create mock project databases
        projects_dir = work_dir / ".local" / "share" / "bablib" / "projects"
        projects_dir.mkdir(parents=True)

        project1 = projects_dir / "python-docs"
        project1.mkdir()
        (project1 / "vectors.db").write_text("mock db")

        project2 = projects_dir / "fastapi-docs"
        project2.mkdir()
        (project2 / "vectors.db").write_text("mock db 2")

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3")

                with patch("src.services.sqlite_vec_service.SQLiteVecService.get_collection_stats") as mock_stats:
                    mock_stats.side_effect = [
                        {"name": "python-docs", "vector_count": 1234, "disk_usage_bytes": 15000000},
                        {"name": "fastapi-docs", "vector_count": 567, "disk_usage_bytes": 7000000}
                    ]

                    result = runner.invoke(
                        cli,
                        ["system-check"],
                        catch_exceptions=False
                    )

                    assert result.exit_code == 0
                    assert "2 projects" in result.output or "python-docs" in result.output
                    assert "MB" in result.output  # Should show size

    def test_system_check_compare_providers(self, runner, tmp_path):
        """Test system-check output differs between Qdrant and SQLite-vec."""
        config_dir = tmp_path / ".config" / "bablib"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.yaml"

        # Test with Qdrant
        import yaml
        with open(config_file, "w") as f:
            yaml.dump({
                "vector_store": {
                    "provider": "qdrant",
                    "qdrant_config": {"url": "http://localhost:6333"}
                }
            }, f)

        with runner.isolated_filesystem(temp_dir=str(tmp_path)):
            result_qdrant = runner.invoke(cli, ["system-check"])
            assert "Qdrant" in result_qdrant.output
            assert "sqlite-vec" not in result_qdrant.output.lower()

        # Test with SQLite-vec
        with open(config_file, "w") as f:
            yaml.dump({
                "vector_store": {
                    "provider": "sqlite_vec",
                    "sqlite_vec_config": {"enabled": True}
                }
            }, f)

        with runner.isolated_filesystem(temp_dir=str(tmp_path)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3")

                result_sqlite = runner.invoke(cli, ["system-check"])
                assert "sqlite_vec" in result_sqlite.output.lower() or "SQLite-vec" in result_sqlite.output
                assert "extension" in result_sqlite.output

    def test_system_check_verbose_mode(self, runner, sqlite_vec_config):
        """Test system-check verbose mode shows additional SQLite-vec details."""
        work_dir, config_file = sqlite_vec_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.system_check.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3")

                result = runner.invoke(
                    cli,
                    ["system-check", "--verbose"],
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "Vector Store Configuration" in result.output
                assert "batch_size" in result.output
                assert "max_connections" in result.output
                assert "wal_mode" in result.output