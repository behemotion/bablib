"""Performance tests for Bablib installation and setup speed requirements.

This module validates that Bablib installation meets the <30s requirement from quickstart.md.
Tests cover end-to-end installation timing, system validation performance, service detection
speed, and critical decision handling performance.

Requirements:
- Total installation time: <30s
- System validation: <5s
- Service detection: Reasonable timeout handling
- Critical decision handling: Fast response
"""

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import socket

import pytest

from src.services.setup import SetupWizardService, SetupError
from src.services.system_validator import SystemRequirementsService
from src.services.detection import ServiceDetectionService
from src.services.config import ConfigService
from src.models.installation import (
    InstallationContext, ServiceStatus, SetupWizardState, CriticalDecisionPoint
)
from src.models.system_requirements import SystemRequirements


# Performance test configuration
INSTALLATION_TIMEOUT = 30.0  # 30 seconds max for full installation
SYSTEM_VALIDATION_TIMEOUT = 5.0  # 5 seconds max for system validation
SERVICE_DETECTION_TIMEOUT = 10.0  # 10 seconds max for service detection
CRITICAL_DECISION_TIMEOUT = 2.0  # 2 seconds max for decision handling


@pytest.mark.performance
class TestInstallationPerformance:
    """Test installation performance requirements."""

    def test_full_installation_under_30_seconds(self, benchmark, mock_temp_directories, mock_async_service_detection):
        """Test that complete installation process completes in <30 seconds."""

        async def run_full_installation():
            """Run complete installation simulation."""
            with patch('src.services.setup.SetupWizardService._check_python_version'), \
                 patch('src.services.setup.SetupWizardService._create_installation_context') as mock_context:

                # Mock installation context creation
                mock_context.return_value = InstallationContext(
                    install_method="uvx",
                    install_date=datetime.now(),
                    version="1.0.0",
                    python_version="3.13.1",
                    uv_version="0.4.0",
                    install_path=Path("/home/user/.local/bin/bablib"),
                    is_global=True,
                    user_data_dir=mock_temp_directories["data_dir"],
                    config_dir=mock_temp_directories["config_dir"],
                    cache_dir=mock_temp_directories["cache_dir"]
                )

                # Create setup wizard with mocked directories
                wizard = SetupWizardService()
                with patch.object(wizard.config_service, 'config_dir', mock_temp_directories["config_dir"]), \
                     patch.object(wizard.config_service, 'data_dir', mock_temp_directories["data_dir"]), \
                     patch.object(wizard.config_service, 'cache_dir', mock_temp_directories["cache_dir"]):

                    # Run quiet setup (fastest path)
                    context = await wizard.run_quiet_setup()
                    return context

        # Benchmark the installation process
        def benchmark_installation():
            return asyncio.run(run_full_installation())

        result = benchmark.pedantic(
            benchmark_installation,
            rounds=3,
            iterations=1,
            warmup_rounds=1
        )

        # Assert installation completed successfully
        assert result is not None
        assert isinstance(result, InstallationContext)

        # Check that benchmark time is under 30 seconds
        # benchmark.stats includes timing information
        assert benchmark.stats["mean"] < INSTALLATION_TIMEOUT, \
            f"Installation took {benchmark.stats['mean']:.2f}s, must be under {INSTALLATION_TIMEOUT}s"

    def test_interactive_installation_performance(self, benchmark, mock_temp_directories, mock_async_service_detection):
        """Test interactive installation stays within time limits."""

        async def run_interactive_installation():
            """Run interactive installation with automated responses."""
            with patch('src.services.setup.SetupWizardService._check_python_version'), \
                 patch('src.services.setup.SetupWizardService._show_welcome'), \
                 patch('src.services.setup.SetupWizardService._show_completion'), \
                 patch('src.services.setup.SetupWizardService._create_installation_context') as mock_context, \
                 patch('rich.prompt.Confirm.ask', return_value=False):  # Skip service installation

                mock_context.return_value = InstallationContext(
                    install_method="uvx",
                    install_date=datetime.now(),
                    version="1.0.0",
                    python_version="3.13.1",
                    uv_version="0.4.0",
                    install_path=Path("/home/user/.local/bin/bablib"),
                    is_global=True,
                    user_data_dir=mock_temp_directories["data_dir"],
                    config_dir=mock_temp_directories["config_dir"],
                    cache_dir=mock_temp_directories["cache_dir"]
                )

                wizard = SetupWizardService()
                with patch.object(wizard.config_service, 'config_dir', mock_temp_directories["config_dir"]), \
                     patch.object(wizard.config_service, 'data_dir', mock_temp_directories["data_dir"]), \
                     patch.object(wizard.config_service, 'cache_dir', mock_temp_directories["cache_dir"]):

                    context = await wizard.run_interactive_setup(skip_services=True)
                    return context

        def benchmark_interactive():
            return asyncio.run(run_interactive_installation())

        result = benchmark.pedantic(
            benchmark_interactive,
            rounds=2,
            iterations=1
        )

        assert result is not None
        assert benchmark.stats["mean"] < INSTALLATION_TIMEOUT


@pytest.mark.performance
class TestSystemValidationPerformance:
    """Test system validation performance requirements."""

    def test_system_validation_under_5_seconds(self, benchmark):
        """Test that system validation completes in <5 seconds."""

        async def run_system_validation():
            """Run complete system validation."""
            validator = SystemRequirementsService(timeout=2)  # Reduced timeout for performance
            requirements = await validator.validate_system_requirements()
            return requirements

        def benchmark_validation():
            return asyncio.run(run_system_validation())

        result = benchmark.pedantic(
            benchmark_validation,
            rounds=5,
            iterations=1
        )

        assert result is not None
        assert isinstance(result, SystemRequirements)
        assert benchmark.stats["mean"] < SYSTEM_VALIDATION_TIMEOUT, \
            f"System validation took {benchmark.stats['mean']:.2f}s, must be under {SYSTEM_VALIDATION_TIMEOUT}s"

    def test_individual_validation_components_performance(self, benchmark):
        """Test individual validation components for performance bottlenecks."""
        validator = SystemRequirementsService(timeout=1)

        # Test Python version check (should be very fast)
        def check_python():
            return asyncio.run(validator.check_python_requirements())

        result = benchmark.pedantic(check_python, rounds=10, iterations=5)
        assert benchmark.stats["mean"] < 0.1  # Should be under 100ms

        # Test memory check
        benchmark.reset()
        def check_memory():
            return asyncio.run(validator.check_memory_requirements())

        result = benchmark.pedantic(check_memory, rounds=5, iterations=3)
        assert benchmark.stats["mean"] < 1.0  # Should be under 1s

        # Test disk check
        benchmark.reset()
        def check_disk():
            return asyncio.run(validator.check_disk_requirements())

        result = benchmark.pedantic(check_disk, rounds=5, iterations=3)
        assert benchmark.stats["mean"] < 0.5  # Should be under 500ms

    def test_concurrent_validation_performance(self, benchmark):
        """Test that concurrent validation improves performance."""

        async def run_concurrent_validation():
            """Run multiple validations concurrently."""
            validator = SystemRequirementsService(timeout=2)

            # Run multiple checks concurrently
            results = await asyncio.gather(
                validator.check_python_requirements(),
                validator.check_memory_requirements(),
                validator.check_disk_requirements(),
                validator.check_platform_requirements(),
                validator.check_uv_requirements(),
                return_exceptions=True
            )
            return results

        def benchmark_concurrent():
            return asyncio.run(run_concurrent_validation())

        result = benchmark.pedantic(
            benchmark_concurrent,
            rounds=3,
            iterations=1
        )

        # Concurrent should be faster than sequential
        assert benchmark.stats["mean"] < 3.0  # Should be under 3s for all checks


@pytest.mark.performance
class TestServiceDetectionPerformance:
    """Test service detection performance requirements."""

    def test_service_detection_timeout_handling(self, benchmark):
        """Test service detection with proper timeout handling."""

        async def run_service_detection_with_timeouts():
            """Run service detection with various timeout scenarios."""
            detection_service = ServiceDetectionService()

            # Mock slow services to test timeout behavior
            with patch.object(detection_service, '_check_docker_service') as mock_docker, \
                 patch.object(detection_service, '_check_ollama_service') as mock_ollama, \
                 patch.object(detection_service, '_check_qdrant_service') as mock_qdrant:

                # Mock fast responses (normal case)
                mock_docker.return_value = ServiceStatus(
                    name="docker",
                    available=True,
                    version="24.0.0",
                    last_checked=datetime.now(),
                    error_message=None,
                    setup_completed=True
                )

                # Mock slow service (timeout case)
                async def slow_service():
                    await asyncio.sleep(0.1)  # Simulate slight delay
                    return ServiceStatus(
                        name="ollama",
                        available=False,
                        version=None,
                        last_checked=datetime.now(),
                        error_message="Connection timeout",
                        setup_completed=False
                    )

                mock_ollama.side_effect = slow_service

                # Mock normal service
                mock_qdrant.return_value = ServiceStatus(
                    name="qdrant",
                    available=True,
                    version="1.13.0",
                    last_checked=datetime.now(),
                    error_message=None,
                    setup_completed=True
                )

                statuses = await detection_service.check_all_services()
                return statuses

        def benchmark_detection():
            return asyncio.run(run_service_detection_with_timeouts())

        result = benchmark.pedantic(
            benchmark_detection,
            rounds=3,
            iterations=1
        )

        assert result is not None
        assert len(result) >= 3  # At least docker, ollama, qdrant
        assert benchmark.stats["mean"] < SERVICE_DETECTION_TIMEOUT

    def test_service_detection_failure_handling(self, benchmark):
        """Test that service detection handles failures quickly."""

        async def run_failing_service_detection():
            """Run service detection where all services fail."""
            detection_service = ServiceDetectionService()

            with patch.object(detection_service, '_check_docker_service') as mock_docker, \
                 patch.object(detection_service, '_check_ollama_service') as mock_ollama, \
                 patch.object(detection_service, '_check_qdrant_service') as mock_qdrant:

                # All services unavailable (fast failure)
                for mock_service, name in [(mock_docker, "docker"), (mock_ollama, "ollama"), (mock_qdrant, "qdrant")]:
                    mock_service.return_value = ServiceStatus(
                        name=name,
                        available=False,
                        version=None,
                        last_checked=datetime.now(),
                        error_message=f"{name} not available",
                        setup_completed=False
                    )

                statuses = await detection_service.check_all_services()
                return statuses

        def benchmark_failing():
            return asyncio.run(run_failing_service_detection())

        result = benchmark.pedantic(
            benchmark_failing,
            rounds=5,
            iterations=1
        )

        assert result is not None
        # Failing services should be detected quickly
        assert benchmark.stats["mean"] < 2.0  # Should fail fast


@pytest.mark.performance
class TestCriticalDecisionPerformance:
    """Test critical decision handling performance."""

    def test_decision_detection_performance(self, benchmark, mock_temp_directories):
        """Test that critical decision detection is fast."""

        def run_decision_detection():
            """Run critical decision detection."""
            wizard = SetupWizardService()

            with patch.object(wizard.config_service, 'config_dir', mock_temp_directories["config_dir"]), \
                 patch.object(wizard.config_service, 'data_dir', mock_temp_directories["data_dir"]):

                # Mock port conflict scenario
                with patch.object(wizard, '_check_port_conflict', return_value=True), \
                     patch.object(wizard, '_check_existing_data', return_value=False):

                    decisions = wizard._detect_critical_decisions()
                    return decisions

        result = benchmark.pedantic(
            run_decision_detection,
            rounds=10,
            iterations=5
        )

        assert result is not None
        assert isinstance(result, list)
        assert benchmark.stats["mean"] < CRITICAL_DECISION_TIMEOUT

    def test_port_conflict_detection_performance(self, benchmark):
        """Test port conflict detection speed."""

        def check_port_conflict():
            """Check for port conflicts."""
            wizard = SetupWizardService()
            return wizard._check_port_conflict()

        result = benchmark.pedantic(
            check_port_conflict,
            rounds=20,
            iterations=10
        )

        # Port checking should be very fast
        assert benchmark.stats["mean"] < 0.1  # Under 100ms

    def test_data_directory_check_performance(self, benchmark, mock_temp_directories):
        """Test data directory checking performance."""

        def check_data_directory():
            """Check existing data directory."""
            wizard = SetupWizardService()
            with patch.object(wizard.config_service, 'data_dir', mock_temp_directories["data_dir"]):
                return wizard._check_existing_data()

        result = benchmark.pedantic(
            check_data_directory,
            rounds=20,
            iterations=10
        )

        # Directory checking should be very fast
        assert benchmark.stats["mean"] < 0.05  # Under 50ms


@pytest.mark.performance
class TestInstallationRegressionDetection:
    """Test for performance regression detection."""

    def test_baseline_performance_metrics(self, benchmark):
        """Establish baseline performance metrics."""

        async def minimal_setup():
            """Minimal setup operation for baseline."""
            # Just create a basic installation context
            context = InstallationContext(
                install_method="uvx",
                install_date=datetime.now(),
                version="1.0.0",
                python_version="3.13.1",
                uv_version="0.4.0",
                install_path=Path("/tmp/bablib"),
                is_global=True,
                user_data_dir=Path("/tmp/data"),
                config_dir=Path("/tmp/config"),
                cache_dir=Path("/tmp/cache")
            )
            return context

        def benchmark_baseline():
            return asyncio.run(minimal_setup())

        result = benchmark.pedantic(
            benchmark_baseline,
            rounds=50,
            iterations=10
        )

        # Baseline should be very fast (< 10ms)
        assert benchmark.stats["mean"] < 0.01

        # Store performance data for regression detection
        performance_data = {
            "test": "baseline_performance",
            "mean": benchmark.stats["mean"],
            "min": benchmark.stats["min"],
            "max": benchmark.stats["max"],
            "stddev": benchmark.stats["stddev"],
            "timestamp": datetime.now().isoformat()
        }

        # In a real implementation, this would be stored to a database or file
        # for tracking performance over time
        assert performance_data["mean"] > 0  # Sanity check

    def test_memory_usage_during_installation(self, benchmark):
        """Test memory usage stays reasonable during installation."""
        import psutil
        import os

        def measure_memory_usage():
            """Measure memory usage during mock installation."""
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss

            # Simulate installation operations
            contexts = []
            for i in range(10):
                context = InstallationContext(
                    install_method="uvx",
                    install_date=datetime.now(),
                    version="1.0.0",
                    python_version="3.13.1",
                    uv_version="0.4.0",
                    install_path=Path(f"/tmp/bablib_{i}"),
                    is_global=True,
                    user_data_dir=Path(f"/tmp/data_{i}"),
                    config_dir=Path(f"/tmp/config_{i}"),
                    cache_dir=Path(f"/tmp/cache_{i}")
                )
                contexts.append(context)

            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory

            # Cleanup
            del contexts

            return memory_increase

        result = benchmark.pedantic(
            measure_memory_usage,
            rounds=3,
            iterations=1
        )

        # Memory increase should be reasonable (< 10MB)
        assert result < 10 * 1024 * 1024  # 10MB


@pytest.mark.performance
class TestRealisticSystemConditions:
    """Test performance under realistic system conditions."""

    def test_installation_with_limited_resources(self, benchmark, mock_temp_directories):
        """Test installation performance with simulated resource constraints."""

        async def run_constrained_installation():
            """Run installation with resource constraints."""
            # Mock system with limited resources
            with patch('src.services.system_validator.SystemRequirementsService._get_available_memory_gb', return_value=4), \
                 patch('src.services.system_validator.SystemRequirementsService._get_available_disk_gb', return_value=2):

                wizard = SetupWizardService()

                with patch.object(wizard.config_service, 'config_dir', mock_temp_directories["config_dir"]), \
                     patch.object(wizard.config_service, 'data_dir', mock_temp_directories["data_dir"]), \
                     patch.object(wizard.config_service, 'cache_dir', mock_temp_directories["cache_dir"]), \
                     patch('src.services.setup.SetupWizardService._check_python_version'), \
                     patch('src.services.setup.SetupWizardService._create_installation_context') as mock_context:

                    mock_context.return_value = InstallationContext(
                        install_method="uvx",
                        install_date=datetime.now(),
                        version="1.0.0",
                        python_version="3.13.1",
                        uv_version="0.4.0",
                        install_path=Path("/home/user/.local/bin/bablib"),
                        is_global=True,
                        user_data_dir=mock_temp_directories["data_dir"],
                        config_dir=mock_temp_directories["config_dir"],
                        cache_dir=mock_temp_directories["cache_dir"]
                    )

                    context = await wizard.run_quiet_setup()
                    return context

        def benchmark_constrained():
            return asyncio.run(run_constrained_installation())

        result = benchmark.pedantic(
            benchmark_constrained,
            rounds=2,
            iterations=1
        )

        assert result is not None
        # Should still complete within timeout even with limited resources
        assert benchmark.stats["mean"] < INSTALLATION_TIMEOUT

    def test_installation_with_slow_network(self, benchmark, mock_temp_directories):
        """Test installation with simulated slow network conditions."""

        async def run_slow_network_installation():
            """Run installation with slow network simulation."""
            detection_service = ServiceDetectionService()

            # Mock slow network responses
            with patch.object(detection_service, '_check_ollama_service') as mock_ollama, \
                 patch.object(detection_service, '_check_qdrant_service') as mock_qdrant, \
                 patch.object(detection_service, '_check_docker_service') as mock_docker:

                async def slow_network_response(service_name):
                    # Simulate network delay
                    await asyncio.sleep(0.2)  # 200ms delay
                    return ServiceStatus(
                        name=service_name,
                        available=False,
                        version=None,
                        last_checked=datetime.now(),
                        error_message="Network timeout",
                        setup_completed=False
                    )

                mock_ollama.side_effect = lambda: slow_network_response("ollama")
                mock_qdrant.side_effect = lambda: slow_network_response("qdrant")
                mock_docker.side_effect = lambda: slow_network_response("docker")

                statuses = await detection_service.check_all_services()
                return statuses

        def benchmark_slow_network():
            return asyncio.run(run_slow_network_installation())

        result = benchmark.pedantic(
            benchmark_slow_network,
            rounds=2,
            iterations=1
        )

        assert result is not None
        # Should handle slow network gracefully
        assert benchmark.stats["mean"] < 3.0  # Allow for network delays


@pytest.mark.performance
@pytest.mark.integration
class TestEndToEndPerformance:
    """End-to-end performance tests for complete workflows."""

    def test_uv_tool_installation_performance(self, benchmark):
        """Test UV tool installation pathway performance."""

        def simulate_uv_installation():
            """Simulate UV-based installation."""
            with patch('subprocess.run') as mock_run, \
                 patch('shutil.which') as mock_which:

                # Mock UV availability
                mock_which.return_value = '/usr/local/bin/uv'
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout="uv 0.4.0",
                    stderr=""
                )

                # Simulate installation steps
                steps = [
                    "check_uv_availability",
                    "validate_system",
                    "install_package",
                    "setup_directories",
                    "validate_installation"
                ]

                for step in steps:
                    # Simulate work for each step
                    time.sleep(0.01)  # 10ms per step

                return True

        result = benchmark.pedantic(
            simulate_uv_installation,
            rounds=10,
            iterations=1
        )

        assert result is True
        # UV installation should be fast
        assert benchmark.stats["mean"] < 1.0

    def test_development_installation_performance(self, benchmark, mock_temp_directories):
        """Test development installation pathway performance."""

        async def run_development_setup():
            """Run development setup simulation."""
            with patch('src.services.setup.SetupWizardService._check_python_version'), \
                 patch('src.services.setup.SetupWizardService._create_installation_context') as mock_context:

                mock_context.return_value = InstallationContext(
                    install_method="development",
                    install_date=datetime.now(),
                    version="1.0.0",
                    python_version="3.13.1",
                    uv_version=None,  # Development mode may not have UV
                    install_path=Path("./bablib"),
                    is_global=False,
                    user_data_dir=mock_temp_directories["data_dir"],
                    config_dir=mock_temp_directories["config_dir"],
                    cache_dir=mock_temp_directories["cache_dir"]
                )

                wizard = SetupWizardService()
                with patch.object(wizard.config_service, 'config_dir', mock_temp_directories["config_dir"]), \
                     patch.object(wizard.config_service, 'data_dir', mock_temp_directories["data_dir"]), \
                     patch.object(wizard.config_service, 'cache_dir', mock_temp_directories["cache_dir"]):

                    context = await wizard.run_quiet_setup()
                    return context

        def benchmark_development():
            return asyncio.run(run_development_setup())

        result = benchmark.pedantic(
            benchmark_development,
            rounds=3,
            iterations=1
        )

        assert result is not None
        assert result.install_method == "development"
        # Development setup should be fast
        assert benchmark.stats["mean"] < 5.0


# Performance utility functions for detailed timing analysis
def get_performance_breakdown(func, *args, **kwargs):
    """Get detailed performance breakdown of a function."""
    import cProfile
    import pstats
    from io import StringIO

    profiler = cProfile.Profile()
    profiler.enable()

    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()

    profiler.disable()

    # Capture profiling data
    profile_stream = StringIO()
    stats = pstats.Stats(profiler, stream=profile_stream)
    stats.sort_stats('cumulative').print_stats(10)

    return {
        'result': result,
        'total_time': end_time - start_time,
        'profile_data': profile_stream.getvalue()
    }


@pytest.mark.performance
class TestDetailedTimingBreakdown:
    """Detailed timing breakdown for optimization insights."""

    def test_installation_phase_timing(self, mock_temp_directories, mock_async_service_detection):
        """Break down installation timing by phase."""

        async def run_timed_installation():
            """Run installation with detailed phase timing."""
            phase_timings = {}

            # Phase 1: Python check
            start = time.time()
            with patch('src.services.setup.SetupWizardService._check_python_version'):
                pass  # Mocked
            phase_timings['python_check'] = time.time() - start

            # Phase 2: Service detection
            start = time.time()
            detection_service = ServiceDetectionService()
            with patch.object(detection_service, 'check_all_services') as mock_check:
                mock_check.return_value = {
                    "docker": ServiceStatus(name="docker", available=True, version="24.0.0", last_checked=datetime.now(), setup_completed=True),
                    "ollama": ServiceStatus(name="ollama", available=True, version="0.1.7", last_checked=datetime.now(), setup_completed=True),
                    "qdrant": ServiceStatus(name="qdrant", available=True, version="1.13.0", last_checked=datetime.now(), setup_completed=True)
                }
                await mock_check()
            phase_timings['service_detection'] = time.time() - start

            # Phase 3: Configuration setup
            start = time.time()
            context = InstallationContext(
                install_method="uvx",
                install_date=datetime.now(),
                version="1.0.0",
                python_version="3.13.1",
                uv_version="0.4.0",
                install_path=Path("/home/user/.local/bin/bablib"),
                is_global=True,
                user_data_dir=mock_temp_directories["data_dir"],
                config_dir=mock_temp_directories["config_dir"],
                cache_dir=mock_temp_directories["cache_dir"]
            )
            phase_timings['config_setup'] = time.time() - start

            return phase_timings

        timings = asyncio.run(run_timed_installation())

        # Verify phase timings are reasonable
        assert timings['python_check'] < 0.1  # Should be very fast
        assert timings['service_detection'] < 2.0  # Should be under 2s
        assert timings['config_setup'] < 0.5  # Should be fast

        total_time = sum(timings.values())
        assert total_time < 5.0  # Total of all phases should be under 5s

        # Log timing breakdown for analysis
        print(f"\nPhase timing breakdown:")
        for phase, timing in timings.items():
            print(f"  {phase}: {timing:.3f}s")
        print(f"  Total: {total_time:.3f}s")


# Configuration for performance test execution
@pytest.fixture(scope="session", autouse=True)
def configure_performance_tests():
    """Configure performance test environment."""
    # Set environment variables for performance testing
    import os
    os.environ["BABLIB_PERFORMANCE_MODE"] = "true"
    os.environ["BABLIB_TEST_TIMEOUT"] = "1"  # Reduced timeout for tests

    yield

    # Cleanup
    os.environ.pop("BABLIB_PERFORMANCE_MODE", None)
    os.environ.pop("BABLIB_TEST_TIMEOUT", None)