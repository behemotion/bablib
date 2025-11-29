"""Integration tests for complete setup flow."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

pytestmark = [pytest.mark.integration, pytest.mark.setup]


class TestFullSetupFlow:
    """Test complete setup initialization flow."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_services(self):
        """Mock external service dependencies."""
        with patch("src.logic.setup.services.detector.ServiceDetector") as detector:
            detector.return_value.detect_all.return_value = {
                "docker": {"status": "available", "version": "20.10.0"},
                "qdrant": {"status": "unavailable"},
                "ollama": {"status": "available", "version": "0.1.0"},
                "sqlite_vec": {"status": "available"}
            }
            yield detector

    def test_setup_creates_directory_structure(self, temp_home, mock_services):
        """Test that setup creates all required directories."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)
        result = orchestrator.initialize(auto=True, vector_store="sqlite_vec")

        # Verify directories created
        assert (temp_home / ".config" / "bablib").exists()
        assert (temp_home / ".local" / "share" / "bablib").exists()
        assert (temp_home / ".cache" / "bablib").exists()

    def test_setup_writes_configuration(self, temp_home, mock_services):
        """Test that setup writes configuration files."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)
        result = orchestrator.initialize(
            auto=True,
            vector_store="sqlite_vec"
        )

        # Verify config file created
        config_file = temp_home / ".config" / "bablib" / "settings.yaml"
        assert config_file.exists()

        # Verify config content
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
            assert config["vector_store_provider"] == "sqlite_vec"

    def test_setup_detects_services(self, temp_home, mock_services):
        """Test that setup detects available services."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)
        result = orchestrator.initialize(auto=True)

        # Verify service detection was called
        mock_services.return_value.detect_all.assert_called_once()

        # Verify result includes service info
        assert result.services_detected["docker"]["status"] == "available"
        assert result.services_detected["ollama"]["status"] == "available"

    def test_setup_validates_system_requirements(self, temp_home):
        """Test that setup validates system requirements."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        with patch("src.logic.setup.services.validator.SetupValidator") as validator:
            validator.return_value.validate_system.return_value = {
                "python_version": "3.13.0",
                "memory_gb": 8.0,
                "disk_gb": 50.0,
                "valid": True
            }

            orchestrator = SetupOrchestrator(home_dir=temp_home)
            result = orchestrator.initialize(auto=True)

            validator.return_value.validate_system.assert_called_once()

    def test_setup_interactive_mode_prompts(self, temp_home, mock_services):
        """Test that interactive mode prompts for user input."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        with patch("src.logic.setup.utils.prompts.prompt_choice") as prompt:
            prompt.return_value = "sqlite_vec"

            orchestrator = SetupOrchestrator(home_dir=temp_home)
            result = orchestrator.initialize(auto=False)

            # Should prompt for vector store selection
            prompt.assert_called()
            assert "vector" in str(prompt.call_args).lower()

    def test_setup_handles_existing_installation(self, temp_home):
        """Test that setup handles existing installation correctly."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        # Create existing config
        config_dir = temp_home / ".config" / "bablib"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "settings.yaml"
        config_file.write_text("vector_store_provider: qdrant\n")

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        # Should fail without force flag
        with pytest.raises(RuntimeError, match="already initialized"):
            orchestrator.initialize(auto=True)

        # Should succeed with force flag
        result = orchestrator.initialize(auto=True, force=True)
        assert result.status == "completed"


class TestSetupErrorHandling:
    """Test error handling during setup."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_setup_handles_permission_errors(self, temp_home):
        """Test setup handles permission errors gracefully."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        # Make directory read-only
        config_dir = temp_home / ".config"
        config_dir.mkdir()
        config_dir.chmod(0o444)

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        with pytest.raises(PermissionError):
            orchestrator.initialize(auto=True)

    def test_setup_handles_disk_space_error(self, temp_home):
        """Test setup handles insufficient disk space."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        with patch("src.logic.setup.services.validator.SetupValidator") as validator:
            validator.return_value.validate_system.return_value = {
                "python_version": "3.13.0",
                "memory_gb": 8.0,
                "disk_gb": 0.5,  # Insufficient
                "valid": False,
                "error": "Insufficient disk space"
            }

            orchestrator = SetupOrchestrator(home_dir=temp_home)

            with pytest.raises(RuntimeError, match="disk space"):
                orchestrator.initialize(auto=True)

    def test_setup_handles_service_unavailable(self, temp_home):
        """Test setup continues when optional services unavailable."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        with patch("src.logic.setup.services.detector.ServiceDetector") as detector:
            detector.return_value.detect_all.return_value = {
                "docker": {"status": "unavailable"},
                "qdrant": {"status": "unavailable"},
                "ollama": {"status": "unavailable"},
                "sqlite_vec": {"status": "available"}
            }

            orchestrator = SetupOrchestrator(home_dir=temp_home)
            result = orchestrator.initialize(
                auto=True,
                vector_store="sqlite_vec"
            )

            # Should succeed with SQLite-vec
            assert result.status == "completed"
            # Should warn about unavailable services
            assert result.warnings