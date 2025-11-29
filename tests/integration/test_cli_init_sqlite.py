"""Integration tests for bablib setup --init with SQLite-vec option."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from src.cli.main import cli
from src.models.vector_store_types import VectorStoreProvider


class TestSetupInitWithSQLiteVec:
    """Test bablib setup --init command with SQLite-vec vector store option."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_home(self, tmp_path):
        """Create temporary home directory for testing."""
        home = tmp_path / "home"
        home.mkdir()
        return home

    def test_setup_init_with_sqlite_vec_flag(self, runner, temp_home):
        """Test non-interactive init with --vector-store sqlite_vec flag."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3 available")

                result = runner.invoke(
                    cli,
                    ["setup", "--init", "--vector-store", "sqlite_vec"],
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "SQLite-vec selected" in result.output
                assert "Configuration saved" in result.output

    def test_setup_init_interactive_sqlite_vec_selection(self, runner, temp_home):
        """Test interactive init with SQLite-vec selection."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec 0.1.3 available")

                # Simulate user selecting option 2 (SQLite-vec)
                result = runner.invoke(
                    cli,
                    ["setup", "--init"],
                    input="2\n",  # Select SQLite-vec
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "Vector Database Selection" in result.output
                assert "SQLite-vec (local, no external dependencies)" in result.output
                assert "SQLite-vec selected" in result.output

    def test_setup_init_sqlite_vec_not_installed(self, runner, temp_home):
        """Test init when SQLite-vec is not installed."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (False, "sqlite-vec not installed")

                result = runner.invoke(
                    cli,
                    ["setup", "--init", "--vector-store", "sqlite_vec"],
                    catch_exceptions=False
                )

                # Should show warning but continue
                assert "sqlite-vec not installed" in result.output.lower()
                assert "pip install sqlite-vec" in result.output

    def test_setup_init_creates_config_with_sqlite_vec(self, runner, temp_home):
        """Test that init creates configuration with SQLite-vec provider."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            config_dir = Path.cwd() / ".config" / "bablib"

            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                result = runner.invoke(
                    cli,
                    ["setup", "--init", "--vector-store", "sqlite_vec"],
                    catch_exceptions=False
                )

                assert result.exit_code == 0

                # Check config file was created
                config_file = config_dir / "config.yaml"
                assert config_file.exists()

                # Verify configuration contains SQLite-vec
                import yaml
                with open(config_file) as f:
                    config = yaml.safe_load(f)
                    assert config["vector_store"]["provider"] == "sqlite_vec"

    def test_setup_init_with_custom_sqlite_path(self, runner, temp_home):
        """Test init with custom SQLite-vec database path."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            custom_path = Path.cwd() / "custom_data"

            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                result = runner.invoke(
                    cli,
                    [
                        "setup", "--init",
                        "--vector-store", "sqlite_vec",
                        "--sqlite-vec-path", str(custom_path)
                    ],
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "SQLite-vec selected" in result.output

    def test_setup_init_validates_sqlite_version(self, runner, temp_home):
        """Test that init validates SQLite version compatibility."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                with patch("sqlite3.sqlite_version_info", (3, 35, 0)):
                    result = runner.invoke(
                        cli,
                        ["setup", "--init", "--vector-store", "sqlite_vec"],
                        catch_exceptions=False
                    )

                    assert "SQLite version" in result.output
                    assert "requires" in result.output.lower()

    def test_setup_init_with_existing_qdrant_config(self, runner, temp_home):
        """Test init with SQLite-vec when Qdrant is already configured."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            config_dir = Path.cwd() / ".config" / "bablib"
            config_dir.mkdir(parents=True)

            # Create existing config with Qdrant
            config_file = config_dir / "config.yaml"
            import yaml
            with open(config_file, "w") as f:
                yaml.dump({
                    "vector_store": {
                        "provider": "qdrant",
                        "qdrant_config": {"url": "http://localhost:6333"}
                    }
                }, f)

            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                result = runner.invoke(
                    cli,
                    ["setup", "--init", "--vector-store", "sqlite_vec", "--force"],
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "SQLite-vec selected" in result.output

                # Verify config was updated
                with open(config_file) as f:
                    config = yaml.safe_load(f)
                    assert config["vector_store"]["provider"] == "sqlite_vec"

    @pytest.mark.parametrize("provider_input,expected_provider", [
        ("sqlite_vec", VectorStoreProvider.SQLITE_VEC),
        ("sqlite-vec", VectorStoreProvider.SQLITE_VEC),
        ("SQLITE_VEC", VectorStoreProvider.SQLITE_VEC),
        ("qdrant", VectorStoreProvider.QDRANT),
    ])
    def test_setup_init_provider_name_normalization(self, runner, temp_home, provider_input, expected_provider):
        """Test that various provider name formats are normalized correctly."""
        with runner.isolated_filesystem(temp_dir=str(temp_home)):
            with patch("src.logic.setup.services.detector.ServiceDetector.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "available")

                result = runner.invoke(
                    cli,
                    ["setup", "--init", "--vector-store", provider_input],
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                if expected_provider == VectorStoreProvider.SQLITE_VEC:
                    assert "SQLite-vec selected" in result.output
                else:
                    assert "Qdrant" in result.output