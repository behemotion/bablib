"""Performance tests for setup operations."""

import pytest
import time
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch

pytestmark = [pytest.mark.performance, pytest.mark.setup]


class TestSetupPerformance:
    """Test that setup operations meet performance requirements."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_services(self):
        """Mock external services for predictable timing."""
        with patch("src.logic.setup.services.detector.ServiceDetector") as detector:
            # Simulate fast service detection
            detector.return_value.detect_all.return_value = {
                "docker": {"status": "available"},
                "qdrant": {"status": "unavailable"},
                "ollama": {"status": "available"},
                "sqlite_vec": {"status": "available"}
            }
            detector.return_value.detect_all.side_effect = lambda: (
                time.sleep(0.5),  # Simulate detection time
                detector.return_value.detect_all.return_value
            )[1]
            yield detector

    def test_complete_setup_under_30_seconds(self, temp_home, mock_services):
        """Test that complete setup finishes in <30 seconds."""
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        orchestrator = SetupOrchestrator(home_dir=temp_home)

        start_time = time.time()
        result = orchestrator.initialize(
            auto=True,
            vector_store="sqlite_vec"
        )
        end_time = time.time()

        elapsed = end_time - start_time

        assert result.status == "completed"
        assert elapsed < 30, f"Setup took {elapsed:.2f} seconds, exceeding 30s limit"

    def test_service_detection_under_2_seconds(self, temp_home):
        """Test that service detection completes in <2 seconds."""
        from src.logic.setup.services.detector import ServiceDetector

        detector = ServiceDetector()

        start_time = time.time()
        services = detector.detect_all()
        end_time = time.time()

        elapsed = end_time - start_time

        assert elapsed < 2, f"Service detection took {elapsed:.2f} seconds"

    def test_directory_creation_under_1_second(self, temp_home):
        """Test that directory structure creation is <1 second."""
        from src.logic.setup.services.initializer import SetupInitializer

        initializer = SetupInitializer(home_dir=temp_home)

        start_time = time.time()
        initializer.create_directories()
        end_time = time.time()

        elapsed = end_time - start_time

        assert elapsed < 1, f"Directory creation took {elapsed:.2f} seconds"
        assert (temp_home / ".config" / "bablib").exists()
        assert (temp_home / ".local" / "share" / "bablib").exists()
        assert (temp_home / ".cache" / "bablib").exists()

    def test_config_generation_under_1_second(self, temp_home):
        """Test that config file generation is <1 second."""
        from src.logic.setup.services.configurator import SetupConfigurator

        configurator = SetupConfigurator(home_dir=temp_home)

        # Ensure directories exist
        (temp_home / ".config" / "bablib").mkdir(parents=True)

        config_data = {
            "vector_store_provider": "sqlite_vec",
            "ollama_url": "http://localhost:11434",
            "embedding_model": "mxbai-embed-large"
        }

        start_time = time.time()
        configurator.save_config(config_data)
        end_time = time.time()

        elapsed = end_time - start_time

        assert elapsed < 1, f"Config generation took {elapsed:.2f} seconds"

    def test_sqlite_vec_initialization_under_2_seconds(self, temp_home):
        """Test that SQLite-vec initialization is <2 seconds."""
        from src.logic.setup.services.initializer import SetupInitializer

        initializer = SetupInitializer(home_dir=temp_home)

        # Ensure directories exist
        (temp_home / ".local" / "share" / "bablib").mkdir(parents=True)

        start_time = time.time()
        initializer.initialize_sqlite_vec()
        end_time = time.time()

        elapsed = end_time - start_time

        assert elapsed < 2, f"SQLite-vec init took {elapsed:.2f} seconds"

    def test_import_overhead_under_2_seconds(self):
        """Test that import/startup time is <2 seconds."""
        import subprocess
        import sys

        code = """
import time
start = time.time()
from src.logic.setup.core.orchestrator import SetupOrchestrator
end = time.time()
print(end - start)
"""

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(Path.cwd())
        )

        elapsed = float(result.stdout.strip())

        assert elapsed < 2, f"Import overhead took {elapsed:.2f} seconds"

    def test_parallel_service_detection(self):
        """Test that services are detected in parallel."""
        from src.logic.setup.services.detector import ServiceDetector
        import asyncio

        detector = ServiceDetector()

        # Mock individual service checks with delays
        async def slow_check():
            await asyncio.sleep(0.5)
            return {"status": "available"}

        with patch.object(detector, "check_docker", slow_check):
            with patch.object(detector, "check_qdrant", slow_check):
                with patch.object(detector, "check_ollama", slow_check):
                    with patch.object(detector, "check_sqlite_vec", slow_check):
                        start_time = time.time()
                        asyncio.run(detector.detect_all_async())
                        end_time = time.time()

                        elapsed = end_time - start_time

                        # If parallel, should be ~0.5s, not 2s
                        assert elapsed < 1, f"Parallel detection took {elapsed:.2f} seconds"


class TestSetupMemoryUsage:
    """Test memory usage during setup operations."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_setup_memory_usage_reasonable(self, temp_home):
        """Test that setup doesn't use excessive memory."""
        import psutil
        import os
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        orchestrator = SetupOrchestrator(home_dir=temp_home)
        orchestrator.initialize(auto=True, vector_store="sqlite_vec")

        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before

        # Should not increase memory by more than 100MB
        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f} MB"

    def test_no_memory_leaks_in_repeated_setup(self, temp_home):
        """Test that repeated setup operations don't leak memory."""
        import psutil
        import os
        from src.logic.setup.core.orchestrator import SetupOrchestrator

        process = psutil.Process(os.getpid())
        orchestrator = SetupOrchestrator(home_dir=temp_home)

        # Run setup multiple times
        memory_readings = []
        for i in range(5):
            orchestrator.initialize(auto=True, vector_store="sqlite_vec", force=True)
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_readings.append(memory_mb)

        # Memory should not continuously increase
        memory_growth = memory_readings[-1] - memory_readings[0]
        assert memory_growth < 50, f"Memory grew by {memory_growth:.2f} MB over 5 runs"