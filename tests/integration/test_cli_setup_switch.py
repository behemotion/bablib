"""Integration tests for switching vector store with bablib setup."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from src.cli.main import cli
from src.models.vector_store_types import VectorStoreProvider


class TestSetupVectorStoreSwitch:
    """Test switching vector store provider with bablib setup."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def initialized_config(self, tmp_path):
        """Create initialized configuration with Qdrant."""
        config_dir = tmp_path / ".config" / "bablib"
        config_dir.mkdir(parents=True)

        config_file = config_dir / "config.yaml"
        import yaml
        with open(config_file, "w") as f:
            yaml.dump({
                "vector_store": {
                    "provider": "qdrant",
                    "qdrant_config": {"url": "http://localhost:6333"}
                }
            }, f)

        return tmp_path, config_file

    def test_setup_switch_from_qdrant_to_sqlite_vec(self, runner, initialized_config):
        """Test switching from Qdrant to SQLite-vec."""
        work_dir, config_file = initialized_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.setup.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                # Non-interactive switch
                result = runner.invoke(
                    cli,
                    ["setup", "--vector-store", "sqlite_vec", "--force"],
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "Changing vector store requires re-crawling" in result.output
                assert "Configuration updated" in result.output

                # Verify config was updated
                import yaml
                with open(config_file) as f:
                    config = yaml.safe_load(f)
                    assert config["vector_store"]["provider"] == "sqlite_vec"

    def test_setup_interactive_vector_store_change(self, runner, initialized_config):
        """Test interactive vector store change."""
        work_dir, config_file = initialized_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.setup.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                # Simulate interactive flow
                result = runner.invoke(
                    cli,
                    ["setup"],
                    input="y\n2\ny\n",  # Yes to change, select SQLite-vec, confirm
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "Current Configuration" in result.output
                assert "Vector Store: qdrant" in result.output
                assert "Would you like to change the vector store?" in result.output
                assert "SQLite-vec" in result.output
                assert "Warning: Changing vector store requires re-crawling" in result.output

    def test_setup_switch_with_existing_projects_warning(self, runner, initialized_config):
        """Test that switching with existing projects shows warning."""
        work_dir, config_file = initialized_config

        # Create mock projects
        projects_dir = work_dir / ".local" / "share" / "bablib" / "projects"
        projects_dir.mkdir(parents=True)
        (projects_dir / "python-docs").mkdir()
        (projects_dir / "fastapi-docs").mkdir()

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.setup.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                result = runner.invoke(
                    cli,
                    ["setup", "--vector-store", "sqlite_vec"],
                    input="y\n",  # Confirm switch
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "existing projects" in result.output.lower()
                assert "python-docs" in result.output
                assert "fastapi-docs" in result.output
                assert "re-crawling" in result.output.lower()

    def test_setup_abort_switch_on_confirmation(self, runner, initialized_config):
        """Test aborting vector store switch on confirmation."""
        work_dir, config_file = initialized_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            result = runner.invoke(
                cli,
                ["setup", "--vector-store", "sqlite_vec"],
                input="n\n",  # Abort switch
                catch_exceptions=False
            )

            assert result.exit_code == 0
            assert "Aborted" in result.output or "Cancelled" in result.output

            # Verify config was NOT updated
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)
                assert config["vector_store"]["provider"] == "qdrant"

    def test_setup_sqlite_vec_missing_extension(self, runner, initialized_config):
        """Test setup when SQLite-vec extension is missing."""
        work_dir, config_file = initialized_config

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.setup.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (False, "Extension not installed")

                result = runner.invoke(
                    cli,
                    ["setup", "--vector-store", "sqlite_vec"],
                    catch_exceptions=False
                )

                assert "sqlite-vec extension not found" in result.output.lower()
                assert "pip install sqlite-vec" in result.output

    def test_setup_switch_from_sqlite_vec_to_qdrant(self, runner, tmp_path):
        """Test switching from SQLite-vec to Qdrant."""
        config_dir = tmp_path / ".config" / "bablib"
        config_dir.mkdir(parents=True)

        config_file = config_dir / "config.yaml"
        import yaml
        with open(config_file, "w") as f:
            yaml.dump({
                "vector_store": {
                    "provider": "sqlite_vec",
                    "sqlite_vec_config": {"enabled": True}
                }
            }, f)

        with runner.isolated_filesystem(temp_dir=str(tmp_path)):
            with patch("src.cli.commands.setup.check_qdrant_connection") as mock_qdrant:
                mock_qdrant.return_value = True

                result = runner.invoke(
                    cli,
                    ["setup", "--vector-store", "qdrant", "--force"],
                    input="http://localhost:6333\n\n",  # Qdrant URL, no API key
                    catch_exceptions=False
                )

                assert result.exit_code == 0
                assert "Configuring Qdrant" in result.output

                # Verify config was updated
                with open(config_file) as f:
                    config = yaml.safe_load(f)
                    assert config["vector_store"]["provider"] == "qdrant"

    def test_setup_preserves_other_settings(self, runner, initialized_config):
        """Test that changing vector store preserves other settings."""
        work_dir, config_file = initialized_config

        # Add other settings to config
        import yaml
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        config["embedding_model"] = "mxbai-embed-large"
        config["ollama_url"] = "http://localhost:11434"

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        with runner.isolated_filesystem(temp_dir=str(work_dir)):
            with patch("src.cli.commands.setup.detect_sqlite_vec") as mock_detect:
                mock_detect.return_value = (True, "sqlite-vec available")

                result = runner.invoke(
                    cli,
                    ["setup", "--vector-store", "sqlite_vec", "--force"],
                    catch_exceptions=False
                )

                assert result.exit_code == 0

                # Verify other settings preserved
                with open(config_file) as f:
                    updated_config = yaml.safe_load(f)
                    assert updated_config["vector_store"]["provider"] == "sqlite_vec"
                    assert updated_config["embedding_model"] == "mxbai-embed-large"
                    assert updated_config["ollama_url"] == "http://localhost:11434"