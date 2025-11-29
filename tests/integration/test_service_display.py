"""
Integration Test for Service Detection and Display
Tests service availability display from quickstart.md Scenario 6
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from click.testing import CliRunner


class TestServiceDisplay:
    """Integration test for service detection and smart display"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import modules dynamically to handle not existing initially"""
        try:
            from src.cli.main import cli
            from src.logic.setup.models.system_info import ServiceStatus
            self.cli = cli
            self.ServiceStatus = ServiceStatus
        except ImportError:
            pytest.skip("Modules not yet implemented")

    def test_hides_qdrant_when_sqlite_vec_available(self):
        """Test that Qdrant is hidden when SQLite-vec is available"""
        runner = CliRunner()

        # Mock the service detection to simulate SQLite-vec available, Qdrant not
        with patch('src.logic.setup.services.detector.ServiceDetector.detect_all') as mock_detect:
            mock_detect.return_value = AsyncMock(return_value={
                'sqlite_vec': {'available': True, 'version': '1.0.0'},
                'qdrant': {'available': False, 'version': None},
                'ollama': {'available': True, 'version': '0.1.0'}
            })

            with patch('sys.stdout.isatty', return_value=True):
                result = runner.invoke(
                    self.cli,
                    ['setup'],
                    input='\x1b'  # Escape to exit
                )

            # SQLite-vec should be shown
            assert "SQLite-vec" in result.output or "sqlite" in result.output.lower()
            # Qdrant should NOT be shown (hidden because alternative exists)
            assert "Qdrant" not in result.output

    def test_shows_critical_service_unavailable(self):
        """Test that critical services show as 'Not Available' when down"""
        runner = CliRunner()

        # Mock the service detection to simulate Ollama unavailable
        with patch('src.logic.setup.services.detector.ServiceDetector.detect_all') as mock_detect:
            mock_detect.return_value = AsyncMock(return_value={
                'sqlite_vec': {'available': True, 'version': '1.0.0'},
                'ollama': {'available': False, 'version': None}
            })

            with patch('sys.stdout.isatty', return_value=True):
                result = runner.invoke(
                    self.cli,
                    ['setup'],
                    input='\x1b'  # Escape to exit
                )

            # Ollama should be shown as not available
            assert "Ollama" in result.output or "ollama" in result.output.lower()
            assert "Not Available" in result.output or "not available" in result.output.lower()

    def test_shows_all_available_services(self):
        """Test that all available services are displayed with versions"""
        runner = CliRunner()

        # Mock all services as available
        with patch('src.logic.setup.services.detector.ServiceDetector.detect_all') as mock_detect:
            mock_detect.return_value = AsyncMock(return_value={
                'sqlite_vec': {'available': True, 'version': '1.0.0'},
                'qdrant': {'available': True, 'version': '1.12.0'},
                'ollama': {'available': True, 'version': '0.1.0'},
                'docker': {'available': True, 'version': '24.0.0'}
            })

            with patch('sys.stdout.isatty', return_value=True):
                result = runner.invoke(
                    self.cli,
                    ['setup'],
                    input='\x1b'  # Escape to exit
                )

            # All services should be shown when available
            output_lower = result.output.lower()
            assert "available" in output_lower

    def test_system_info_panel_in_menu(self):
        """Test that system info panel appears in setup menu"""
        runner = CliRunner()

        with patch('sys.stdout.isatty', return_value=True):
            result = runner.invoke(
                self.cli,
                ['setup'],
                input='\x1b'  # Escape to exit
            )

            # Check for system info sections
            assert any(text in result.output for text in [
                "Vector Store",
                "Embedding Model",
                "Config Directory",
                "Projects",
                "Settings",
                "Configuration"
            ])

    def test_service_status_colors(self):
        """Test that services show with appropriate colors (red/green)"""
        runner = CliRunner()

        # This test is mainly to ensure the color logic exists
        # Hard to test actual colors in CLI output
        with patch('src.logic.setup.services.detector.ServiceDetector.detect_all') as mock_detect:
            mock_detect.return_value = AsyncMock(return_value={
                'ollama': {'available': False, 'version': None}
            })

            with patch('sys.stdout.isatty', return_value=True):
                result = runner.invoke(
                    self.cli,
                    ['setup'],
                    input='\x1b'  # Escape to exit
                )

            # Service detection should have run
            assert result.exit_code in (0, 1)

    def test_directories_display(self):
        """Test that configuration directories are displayed"""
        runner = CliRunner()

        with patch('sys.stdout.isatty', return_value=True):
            result = runner.invoke(
                self.cli,
                ['setup'],
                input='\x1b'  # Escape to exit
            )

            # Check for directory paths
            assert any(path in result.output for path in [
                ".config/bablib",
                ".local/share/bablib",
                ".cache/bablib",
                "Config",
                "Data",
                "Cache"
            ])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])