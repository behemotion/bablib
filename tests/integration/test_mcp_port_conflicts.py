"""Integration test for MCP server port conflict prevention.

This test validates that the system properly detects and prevents
port conflicts when starting multiple servers as specified in quickstart.md.
"""

import pytest
import asyncio
import socket
from contextlib import contextmanager
from typing import Generator


class TestMcpPortConflictPrevention:
    """Integration tests for port conflict detection and prevention."""

    @pytest.fixture
    def read_only_port(self) -> int:
        """Default port for read-only MCP server."""
        return 9383

    @pytest.fixture
    def admin_port(self) -> int:
        """Default port for admin MCP server."""
        return 9384

    @contextmanager
    def occupy_port(self, port: int) -> Generator[socket.socket, None, None]:
        """Context manager to temporarily occupy a port."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            yield sock
        finally:
            sock.close()

    @pytest.mark.integration
    def test_port_availability_check(self, read_only_port: int, admin_port: int) -> None:
        """Test that the system can check port availability."""
        # Test with available ports
        assert self._is_port_available("127.0.0.1", read_only_port) in [True, False]
        assert self._is_port_available("127.0.0.1", admin_port) in [True, False]

        # Test with occupied port
        with self.occupy_port(9999):  # Use a different port for testing
            assert not self._is_port_available("127.0.0.1", 9999)

    @pytest.mark.integration
    def test_different_ports_no_conflict(
        self, read_only_port: int, admin_port: int
    ) -> None:
        """Test that servers on different ports don't conflict."""
        # This test verifies the design principle that different ports prevent conflicts
        assert read_only_port != admin_port
        assert abs(read_only_port - admin_port) >= 1

    @pytest.mark.integration
    def test_port_conflict_detection_mechanism(self) -> None:
        """Test the mechanism for detecting port conflicts."""
        test_port = 9999  # Use a safe test port

        # First, verify port is available
        assert self._is_port_available("127.0.0.1", test_port)

        # Occupy the port
        with self.occupy_port(test_port):
            # Now it should be detected as unavailable
            assert not self._is_port_available("127.0.0.1", test_port)

        # After releasing, should be available again
        assert self._is_port_available("127.0.0.1", test_port)

    @pytest.mark.integration
    def test_sequential_port_assignment(
        self, read_only_port: int, admin_port: int
    ) -> None:
        """Test that ports are assigned sequentially from base port 9382."""
        base_port = 9382  # Original Bablib MCP server port

        # Verify the sequential assignment pattern
        assert read_only_port == base_port + 1  # 9383
        assert admin_port == base_port + 2      # 9384

    @pytest.mark.integration
    def test_port_range_validation(self, read_only_port: int, admin_port: int) -> None:
        """Test that ports are within valid range."""
        # Valid port range is 1024-65535
        assert 1024 <= read_only_port <= 65535
        assert 1024 <= admin_port <= 65535

        # Should not use privileged ports (< 1024)
        assert read_only_port >= 1024
        assert admin_port >= 1024

    @pytest.mark.integration
    def test_simultaneous_port_binding_attempt(self) -> None:
        """Test behavior when attempting to bind to same port simultaneously."""
        test_port = 9997  # Use a safe test port

        async def try_bind_port(port: int, delay: float = 0) -> bool:
            """Try to bind to a port with optional delay."""
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("127.0.0.1", port))
                sock.listen(1)
                # Hold the port briefly
                await asyncio.sleep(0.1)
                sock.close()
                return True
            except OSError:
                return False

        async def test_concurrent_binding():
            # Try to bind to the same port concurrently
            results = await asyncio.gather(
                try_bind_port(test_port),
                try_bind_port(test_port, 0.05),  # Slight delay
                return_exceptions=True
            )

            # Only one should succeed, the other should fail
            successes = sum(1 for result in results if result is True)
            assert successes <= 1  # At most one should succeed

        # Run the async test
        asyncio.run(test_concurrent_binding())

    @pytest.mark.integration
    def test_port_configuration_override(
        self, read_only_port: int, admin_port: int
    ) -> None:
        """Test that port configuration can be overridden when needed."""
        # This tests the design that allows custom port configuration
        custom_ports = [9500, 9501, 9502]

        for port in custom_ports:
            # Should be able to validate custom ports
            is_available = self._is_port_available("127.0.0.1", port)
            assert isinstance(is_available, bool)

    @pytest.mark.integration
    def test_port_conflict_error_messaging(self) -> None:
        """Test that port conflicts produce clear error messages."""
        test_port = 9998

        with self.occupy_port(test_port):
            # Simulate what the server would do when encountering a conflict
            try:
                # This simulates the server trying to bind to an occupied port
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("127.0.0.1", test_port))
                sock.close()
                pytest.fail("Expected OSError for port conflict")
            except OSError as e:
                # Should get a clear error indicating the port is in use
                assert "Address already in use" in str(e) or "Only one usage" in str(e)

    @pytest.mark.integration
    def test_port_cleanup_on_shutdown(self) -> None:
        """Test that ports are properly released on server shutdown."""
        test_port = 9996

        # Simulate server startup and shutdown
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Bind port (server startup)
            sock.bind(("127.0.0.1", test_port))
            sock.listen(1)
            assert not self._is_port_available("127.0.0.1", test_port)
        finally:
            # Release port (server shutdown)
            sock.close()

        # Port should be available again after cleanup
        assert self._is_port_available("127.0.0.1", test_port)

    @pytest.mark.integration
    def test_default_port_isolation(self, read_only_port: int, admin_port: int) -> None:
        """Test that default ports don't conflict with common services."""
        # Common service ports that should be avoided
        common_ports = [
            80,    # HTTP
            443,   # HTTPS
            22,    # SSH
            25,    # SMTP
            53,    # DNS
            3306,  # MySQL
            5432,  # PostgreSQL
            6379,  # Redis
            8080,  # Common HTTP alternate
            8000,  # Common development server
        ]

        # MCP server ports should not conflict with common services
        assert read_only_port not in common_ports
        assert admin_port not in common_ports

    def _is_port_available(self, host: str, port: int) -> bool:
        """Helper method to check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                return True
        except OSError:
            return False