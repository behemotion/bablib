"""Integration tests for interactive menu navigation."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from rich.console import Console
import tempfile
from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.setup]


class TestInteractiveMenuNavigation:
    """Test interactive menu system navigation."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich console for testing."""
        return Mock(spec=Console)

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)

    def test_menu_main_screen_display(self, mock_console):
        """Test main menu screen displays correctly."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.display_main_menu()

        # Verify main menu options displayed
        calls = mock_console.print.call_args_list
        output = ' '.join(str(call) for call in calls)

        assert "Initialize Bablib" in output
        assert "Modify Configuration" in output
        assert "Uninstall Bablib" in output
        assert "Reset Installation" in output
        assert "Exit" in output

    def test_menu_navigation_with_arrow_keys(self, mock_console):
        """Test navigating menu with arrow keys."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.options = ["Option 1", "Option 2", "Option 3"]
        menu.current_index = 0

        # Test down arrow
        menu.handle_key("down")
        assert menu.current_index == 1

        menu.handle_key("down")
        assert menu.current_index == 2

        # Test wrap around
        menu.handle_key("down")
        assert menu.current_index == 0

        # Test up arrow
        menu.handle_key("up")
        assert menu.current_index == 2

    def test_menu_selection_with_enter(self, mock_console):
        """Test selecting menu option with Enter key."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.options = ["Initialize", "Configure", "Exit"]
        menu.current_index = 1

        selected = menu.handle_key("enter")

        assert selected == "Configure"

    def test_menu_back_navigation(self, mock_console):
        """Test navigating back through menu hierarchy."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.menu_stack = ["main"]
        menu.current_menu = "main"

        # Navigate to submenu
        menu.enter_submenu("configuration")
        assert menu.current_menu == "configuration"
        assert menu.menu_stack == ["main", "configuration"]

        # Go back
        menu.handle_key("escape")
        assert menu.current_menu == "main"
        assert menu.menu_stack == ["main"]

    def test_menu_help_display(self, mock_console):
        """Test help information display."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.help_visible = False

        # Toggle help on
        menu.handle_key("?")
        assert menu.help_visible is True

        # Verify help content displayed
        menu.display_help()
        calls = mock_console.print.call_args_list
        output = ' '.join(str(call) for call in calls)

        assert "arrow keys" in output.lower()
        assert "enter" in output.lower()
        assert "escape" in output.lower()


class TestMenuConfigurationFlow:
    """Test configuration modification through menu."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich console."""
        return Mock(spec=Console)

    @pytest.fixture
    def mock_config(self):
        """Mock configuration service."""
        with patch("src.logic.setup.services.configurator.SetupConfigurator") as mock:
            mock.return_value.load_config.return_value = {
                "vector_store_provider": "sqlite_vec",
                "ollama_url": "http://localhost:11434",
                "embedding_model": "mxbai-embed-large"
            }
            yield mock

    def test_configuration_menu_displays_current_values(self, mock_console, mock_config):
        """Test config menu shows current settings."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.display_configuration_menu()

        # Verify current values displayed
        calls = mock_console.print.call_args_list
        output = ' '.join(str(call) for call in calls)

        assert "sqlite_vec" in output
        assert "localhost:11434" in output
        assert "mxbai-embed-large" in output

    def test_modify_vector_store_selection(self, mock_console, mock_config):
        """Test changing vector store through menu."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)

        # Simulate selecting vector store option
        menu.current_menu = "configuration"
        menu.options = ["Vector Store", "Ollama URL", "Back"]
        menu.current_index = 0

        menu.handle_key("enter")

        # Should show vector store options
        assert menu.current_menu == "vector_store_selection"

    def test_configuration_changes_require_confirmation(self, mock_console, mock_config):
        """Test that config changes require confirmation."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.pending_changes = {
            "vector_store_provider": "qdrant"
        }

        # Attempt to save changes
        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = True
            menu.save_configuration()

            confirm.assert_called_once()
            mock_config.return_value.save_config.assert_called_once()

    def test_configuration_validation(self, mock_console):
        """Test configuration value validation."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)

        # Valid vector store
        assert menu.validate_config_value("vector_store_provider", "sqlite_vec") is True
        assert menu.validate_config_value("vector_store_provider", "qdrant") is True

        # Invalid vector store
        assert menu.validate_config_value("vector_store_provider", "invalid") is False

        # Valid URL
        assert menu.validate_config_value("ollama_url", "http://localhost:11434") is True

        # Invalid URL
        assert menu.validate_config_value("ollama_url", "not-a-url") is False


class TestMenuUninstallFlow:
    """Test uninstall process through menu."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich console."""
        return Mock(spec=Console)

    @pytest.fixture
    def mock_uninstaller(self):
        """Mock uninstaller service."""
        with patch("src.logic.setup.services.uninstaller.SetupUninstaller") as mock:
            mock.return_value.generate_manifest.return_value = {
                "directories": [
                    "~/.config/bablib",
                    "~/.local/share/bablib",
                    "~/.cache/bablib"
                ],
                "total_size_mb": 150
            }
            yield mock

    def test_uninstall_shows_manifest(self, mock_console, mock_uninstaller):
        """Test uninstall displays manifest before proceeding."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)
        menu.start_uninstall()

        # Verify manifest displayed
        mock_uninstaller.return_value.generate_manifest.assert_called_once()

        calls = mock_console.print.call_args_list
        output = ' '.join(str(call) for call in calls)

        assert ".config/bablib" in output
        assert "150" in output  # Size

    def test_uninstall_requires_confirmation(self, mock_console, mock_uninstaller):
        """Test uninstall requires user confirmation."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            confirm.return_value = False  # User cancels

            result = menu.start_uninstall()

            confirm.assert_called_once()
            mock_uninstaller.return_value.execute.assert_not_called()
            assert result is None  # Cancelled

    def test_uninstall_with_backup_option(self, mock_console, mock_uninstaller):
        """Test uninstall with backup creation."""
        from src.logic.setup.core.menu import InteractiveMenu

        menu = InteractiveMenu(console=mock_console)

        with patch("src.logic.setup.utils.prompts.confirm_action") as confirm:
            with patch("src.logic.setup.utils.prompts.prompt_choice") as prompt:
                confirm.return_value = True
                prompt.return_value = "yes"  # Create backup

                menu.start_uninstall()

                mock_uninstaller.return_value.execute.assert_called_with(
                    backup=True
                )