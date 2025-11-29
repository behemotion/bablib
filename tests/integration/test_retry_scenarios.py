"""Integration test retry logic with exponential backoff."""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.retry_service import RetryService
from src.services.installation_wizard_service import InstallationWizardService
from src.models.retry_policy import RetryPolicy


class TestRetryScenarios:
    """Test retry logic with exponential backoff (2s, 4s, 8s) in various scenarios."""

    @pytest.fixture
    def retry_service(self):
        """Create retry service for testing."""
        return RetryService()

    @pytest.fixture
    def retry_policy(self):
        """Create retry policy for testing."""
        return RetryPolicy()

    @pytest.fixture
    def wizard_service(self):
        """Create installation wizard service for testing."""
        return InstallationWizardService()

    @pytest.mark.asyncio
    async def test_exact_exponential_backoff_timing(self, retry_service):
        """Test that retry delays follow exact exponential backoff sequence: 2s, 4s, 8s."""
        delay_times = []

        async def failing_operation():
            raise Exception("Operation failed")

        async def time_measuring_operation():
            start_time = time.time()
            try:
                await retry_service.retry_with_backoff(failing_operation, max_attempts=3)
            except Exception:
                pass  # Expected to fail
            return time.time() - start_time

        with patch('asyncio.sleep') as mock_sleep:
            # Capture the delay times passed to sleep
            mock_sleep.side_effect = lambda delay: delay_times.append(delay) or asyncio.sleep(0)

            try:
                await retry_service.retry_with_backoff(failing_operation, max_attempts=3)
            except Exception:
                pass  # Expected to fail after retries

            # Verify exact delay sequence
            expected_delays = [2.0, 4.0]  # Two retries, so two delays
            assert len(delay_times) == 2
            assert delay_times[0] == 2.0, f"First delay should be 2s, got {delay_times[0]}s"
            assert delay_times[1] == 4.0, f"Second delay should be 4s, got {delay_times[1]}s"

    @pytest.mark.asyncio
    async def test_retry_policy_delay_calculation(self, retry_policy):
        """Test retry policy calculates exact delays for each attempt."""
        # Test delay calculation for each attempt
        assert retry_policy.get_delay_seconds(1) == 2.0
        assert retry_policy.get_delay_seconds(2) == 4.0
        assert retry_policy.get_delay_seconds(3) == 8.0

        # Test beyond max attempts uses max delay
        assert retry_policy.get_delay_seconds(4) == 8.0

    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self, retry_service):
        """Test that successful operations don't trigger retries."""
        call_count = 0

        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        with patch('asyncio.sleep') as mock_sleep:
            result = await retry_service.retry_with_backoff(successful_operation, max_attempts=3)

            # Verify no retries occurred
            assert call_count == 1
            assert result == "success"
            mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_operation_succeeds_on_second_attempt(self, retry_service):
        """Test operation succeeds on second attempt after one retry."""
        call_count = 0
        delay_times = []

        async def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt fails")
            return "success"

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: delay_times.append(delay) or asyncio.sleep(0)

            result = await retry_service.retry_with_backoff(eventually_successful_operation, max_attempts=3)

            # Verify operation succeeded on second attempt
            assert call_count == 2
            assert result == "success"

            # Verify only one delay (2s) occurred
            assert len(delay_times) == 1
            assert delay_times[0] == 2.0

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self, retry_service):
        """Test behavior when all retry attempts fail."""
        call_count = 0
        delay_times = []

        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count} failed")

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: delay_times.append(delay) or asyncio.sleep(0)

            with pytest.raises(ValueError, match="Attempt 3 failed"):
                await retry_service.retry_with_backoff(always_failing_operation, max_attempts=3)

            # Verify all attempts were made
            assert call_count == 3

            # Verify correct delay sequence (2s, 4s)
            assert len(delay_times) == 2
            assert delay_times == [2.0, 4.0]

    @pytest.mark.asyncio
    async def test_docker_operation_retry_integration(self, retry_service):
        """Test retry integration with Docker operations."""
        call_count = 0

        async def simulated_docker_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Docker daemon not responding")
            return {"success": True, "container_id": "abc123"}

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: asyncio.sleep(0)  # Speed up test

            result = await retry_service.retry_docker_operation(simulated_docker_operation)

            assert result["success"] is True
            assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_network_operation_retry_integration(self, retry_service):
        """Test retry integration with network operations."""
        call_count = 0

        async def simulated_network_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionRefusedError("Connection refused")
            return {"status": "connected", "response_time": 0.05}

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: asyncio.sleep(0)

            result = await retry_service.retry_network_operation(simulated_network_operation)

            assert result["status"] == "connected"
            assert call_count == 2  # Failed once, succeeded on second

    @pytest.mark.asyncio
    async def test_installation_wizard_retry_integration(self, wizard_service):
        """Test retry logic integration with installation wizard steps."""
        docker_check_attempts = 0

        async def mock_docker_check():
            nonlocal docker_check_attempts
            docker_check_attempts += 1
            if docker_check_attempts < 2:
                raise ConnectionError("Docker daemon not available")
            return True

        qdrant_install_attempts = 0

        async def mock_qdrant_install():
            nonlocal qdrant_install_attempts
            qdrant_install_attempts += 1
            if qdrant_install_attempts < 3:
                raise Exception("Container creation failed")
            return {"success": True, "container_name": "bablib-memory-qdrant"}

        with patch.object(wizard_service.retry_service, 'retry_docker_operation') as mock_docker_retry, \
             patch.object(wizard_service.retry_service, 'retry_docker_operation') as mock_qdrant_retry, \
             patch('asyncio.sleep') as mock_sleep:

            mock_sleep.side_effect = lambda delay: asyncio.sleep(0)
            mock_docker_retry.side_effect = lambda op: mock_docker_check()
            mock_qdrant_retry.side_effect = lambda op: mock_qdrant_install()

            # Test Docker check retry
            result = await wizard_service._execute_docker_check()
            assert result is True
            assert docker_check_attempts == 2

            # Test Qdrant installation retry
            with patch.object(wizard_service.qdrant_service, 'install_qdrant', side_effect=mock_qdrant_install):
                result = await wizard_service._execute_qdrant_installation(False, None, None)
                assert result is True
                assert qdrant_install_attempts == 3

    @pytest.mark.asyncio
    async def test_retry_state_tracking(self, retry_service):
        """Test that retry state is properly tracked during operations."""
        retry_states = []

        async def operation_with_state_capture():
            # Capture the current retry state
            state = retry_service.create_retry_state()
            retry_states.append({
                'attempt': state.attempt_number,
                'delay': state.next_delay_seconds,
                'started_at': state.started_at
            })
            raise Exception("State capture operation")

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: asyncio.sleep(0)

            try:
                await retry_service.retry_with_backoff(operation_with_state_capture, max_attempts=3)
            except Exception:
                pass

            # Verify state tracking shows progression
            assert len(retry_states) >= 1
            first_state = retry_states[0]
            assert first_state['attempt'] == 0
            assert first_state['delay'] == 2.0
            assert first_state['started_at'] > 0

    @pytest.mark.asyncio
    async def test_retry_with_different_exception_types(self, retry_service):
        """Test retry behavior with different exception types."""
        attempt_count = 0
        exceptions_raised = []

        async def operation_with_varied_exceptions():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count == 1:
                exc = ConnectionError("Network error")
            elif attempt_count == 2:
                exc = TimeoutError("Operation timeout")
            else:
                exc = ValueError("Invalid configuration")

            exceptions_raised.append(type(exc).__name__)
            raise exc

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: asyncio.sleep(0)

            with pytest.raises(ValueError):
                await retry_service.retry_with_backoff(operation_with_varied_exceptions, max_attempts=3)

            # Verify all exception types were encountered
            assert len(exceptions_raised) == 3
            assert "ConnectionError" in exceptions_raised
            assert "TimeoutError" in exceptions_raised
            assert "ValueError" in exceptions_raised

    @pytest.mark.asyncio
    async def test_retry_timing_precision(self, retry_service):
        """Test that retry timing is precise and follows exact exponential backoff."""
        actual_delays = []

        async def failing_operation():
            raise Exception("Precision test failure")

        original_sleep = asyncio.sleep

        async def precise_sleep(delay):
            actual_delays.append(delay)
            # Use minimal actual sleep for test speed
            await original_sleep(0.001)

        with patch('asyncio.sleep', side_effect=precise_sleep):
            try:
                await retry_service.retry_with_backoff(failing_operation, max_attempts=3)
            except Exception:
                pass

            # Verify precise timing
            assert len(actual_delays) == 2
            assert actual_delays[0] == 2.0  # Exactly 2 seconds
            assert actual_delays[1] == 4.0  # Exactly 4 seconds

    @pytest.mark.asyncio
    async def test_retry_policy_should_retry_logic(self, retry_policy):
        """Test retry policy's should_retry decision logic."""
        # Test that retries continue within max attempts
        assert retry_policy.should_retry(Exception("test"), 1) is True
        assert retry_policy.should_retry(Exception("test"), 2) is True
        assert retry_policy.should_retry(Exception("test"), 3) is True

        # Test that retries stop after max attempts
        assert retry_policy.should_retry(Exception("test"), 4) is False

    @pytest.mark.asyncio
    async def test_service_connection_retry_pattern(self, retry_service):
        """Test service connection retry with realistic failure patterns."""
        connection_attempts = []

        async def service_connection():
            connection_attempts.append(time.time())
            if len(connection_attempts) <= 2:
                raise ConnectionRefusedError("Service not ready")
            return {"connected": True, "service": "qdrant"}

        with patch('asyncio.sleep') as mock_sleep:
            # Track actual sleep delays
            sleep_delays = []
            mock_sleep.side_effect = lambda delay: sleep_delays.append(delay) or asyncio.sleep(0)

            result = await retry_service.retry_service_connection(service_connection)

            assert result["connected"] is True
            assert len(connection_attempts) == 3

            # Verify exponential backoff was used
            assert len(sleep_delays) == 2
            assert sleep_delays[0] == 2.0
            assert sleep_delays[1] == 4.0

    @pytest.mark.asyncio
    async def test_concurrent_retry_operations(self, retry_service):
        """Test multiple concurrent retry operations don't interfere."""
        async def operation_a():
            await asyncio.sleep(0.01)
            raise Exception("Operation A failed")

        async def operation_b():
            await asyncio.sleep(0.01)
            return "Operation B succeeded"

        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.side_effect = lambda delay: asyncio.sleep(0.001)

            # Run operations concurrently
            results = await asyncio.gather(
                retry_service.retry_with_backoff(operation_a, max_attempts=2),
                retry_service.retry_with_backoff(operation_b, max_attempts=2),
                return_exceptions=True
            )

            # Verify independent operation results
            assert isinstance(results[0], Exception)  # Operation A failed
            assert results[1] == "Operation B succeeded"  # Operation B succeeded

    @pytest.mark.asyncio
    async def test_maximum_delay_enforcement(self, retry_policy):
        """Test that maximum delay is enforced for high attempt numbers."""
        # Test delays beyond the predefined sequence
        assert retry_policy.get_delay_seconds(5) == retry_policy.max_delay_seconds
        assert retry_policy.get_delay_seconds(10) == retry_policy.max_delay_seconds

        # Verify max delay value
        assert retry_policy.max_delay_seconds == 8.0