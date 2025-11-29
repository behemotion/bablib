"""Contract tests for interactive menu navigation and selection."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rich.console import Console

pytestmark = [pytest.mark.contract, pytest.mark.setup]


class TestMenuNavigationContract:
    """Test interactive menu navigation behaviors."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich console."""
        return Mock(spec=Console)

    @pytest.fixture
    def mock_menu(self):
        """Mock interactive menu."""
        with patch("src.logic.setup.core.menu.InteractiveMenu") as mock:
            yield mock

    def test_menu_display_main_options(self, mock_menu, mock_console):
        """Test that main menu displays all setup options."""
        menu = mock_menu.return_value
        menu.get_main_menu_options.return_value = [
            "Initialize Bablib",
            "Modify Configuration",
            "Uninstall Bablib",
            "Reset Installation",
            "Exit"
        ]

        options = menu.get_main_menu_options()

        assert len(options) == 5
        assert "Initialize Bablib" in options
        assert "Exit" in options

    def test_menu_arrow_key_navigation(self, mock_menu):
        """Test arrow key navigation in menu."""
        menu = mock_menu.return_value
        menu.current_index = 0

        # Simulate down arrow
        menu.handle_key_press("down")
        assert menu.current_index == 1

        # Simulate up arrow
        menu.handle_key_press("up")
        assert menu.current_index == 0

    def test_menu_enter_key_selection(self, mock_menu):
        """Test Enter key selects current option."""
        menu = mock_menu.return_value
        menu.current_index = 2
        menu.options = ["Option 1", "Option 2", "Option 3"]

        selected = menu.handle_key_press("enter")

        assert selected == "Option 3"

    def test_menu_escape_key_back(self, mock_menu):
        """Test Escape key goes back to previous menu."""
        menu = mock_menu.return_value
        menu.menu_stack = ["main", "config"]

        menu.handle_key_press("escape")

        assert menu.menu_stack == ["main"]

    def test_menu_help_toggle(self, mock_menu):
        """Test '?' key toggles help display."""
        menu = mock_menu.return_value
        menu.help_visible = False

        menu.handle_key_press("?")
        assert menu.help_visible is True

        menu.handle_key_press("?")
        assert menu.help_visible is False


class TestMenuSelectionContract:
    """Test menu selection and action execution."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock setup orchestrator."""
        with patch("src.logic.setup.core.orchestrator.SetupOrchestrator") as mock:
            yield mock

    def test_initialize_selection_triggers_init(self, mock_orchestrator):
        """Test selecting Initialize triggers initialization."""
        menu = Mock()
        menu.run.return_value = "initialize"

        orchestrator = mock_orchestrator.return_value
        orchestrator.process_menu_selection("initialize")

        orchestrator.initialize.assert_called_once()

    def test_uninstall_selection_shows_confirmation(self, mock_orchestrator):
        """Test uninstall selection requires confirmation."""
        menu = Mock()
        menu.run.return_value = "uninstall"
        menu.confirm_action.return_value = True

        orchestrator = mock_orchestrator.return_value
        orchestrator.process_menu_selection("uninstall")

        menu.confirm_action.assert_called_with("uninstall")
        orchestrator.uninstall.assert_called_once()

    def test_reset_selection_shows_double_confirmation(self, mock_orchestrator):
        """Test reset requires double confirmation."""
        menu = Mock()
        menu.run.return_value = "reset"
        menu.confirm_action.side_effect = [True, True]  # Double confirmation

        orchestrator = mock_orchestrator.return_value
        orchestrator.process_menu_selection("reset")

        assert menu.confirm_action.call_count == 2
        orchestrator.reset.assert_called_once()

    def test_exit_selection_closes_menu(self, mock_orchestrator):
        """Test exit selection terminates menu."""
        menu = Mock()
        menu.run.return_value = "exit"

        orchestrator = mock_orchestrator.return_value
        result = orchestrator.process_menu_selection("exit")

        assert result is None
        orchestrator.initialize.assert_not_called()
        orchestrator.uninstall.assert_not_called()


class TestMenuStateManagement:
    """Test menu state persistence and navigation history."""

    @pytest.fixture
    def menu_state(self):
        """Create a menu state instance."""
        from src.logic.setup.models.menu_state import MenuState
        return MenuState(
            current_menu="main",
            selected_index=0,
            menu_stack=[],
            pending_changes={},
            help_visible=False
        )

    def test_menu_state_navigation_tracking(self, menu_state):
        """Test menu navigation history is tracked."""
        menu_state.push_menu("config")
        menu_state.push_menu("vector_store")

        assert menu_state.menu_stack == ["main", "config", "vector_store"]
        assert menu_state.current_menu == "vector_store"

    def test_menu_state_back_navigation(self, menu_state):
        """Test going back through menu history."""
        menu_state.menu_stack = ["main", "config", "vector_store"]
        menu_state.current_menu = "vector_store"

        menu_state.go_back()

        assert menu_state.current_menu == "config"
        assert menu_state.menu_stack == ["main", "config"]

    def test_menu_state_pending_changes(self, menu_state):
        """Test tracking unsaved changes in menu."""
        menu_state.add_pending_change("vector_store", "qdrant")
        menu_state.add_pending_change("ollama_url", "http://localhost:11434")

        assert menu_state.pending_changes == {
            "vector_store": "qdrant",
            "ollama_url": "http://localhost:11434"
        }

    def test_menu_state_clear_on_save(self, menu_state):
        """Test pending changes cleared after save."""
        menu_state.pending_changes = {"key": "value"}

        menu_state.save_changes()

        assert menu_state.pending_changes == {}


class TestMenuValidation:
    """Test menu input validation and error handling."""

    @pytest.fixture
    def mock_menu(self):
        """Mock interactive menu."""
        with patch("src.logic.setup.core.menu.InteractiveMenu") as mock:
            yield mock

    def test_menu_validates_vector_store_selection(self, mock_menu):
        """Test vector store selection is validated."""
        menu = mock_menu.return_value

        # Valid selection
        assert menu.validate_selection("vector_store", "sqlite_vec") is True
        assert menu.validate_selection("vector_store", "qdrant") is True

        # Invalid selection
        assert menu.validate_selection("vector_store", "invalid") is False

    def test_menu_validates_url_format(self, mock_menu):
        """Test URL inputs are validated."""
        menu = mock_menu.return_value

        # Valid URLs
        assert menu.validate_url("http://localhost:11434") is True
        assert menu.validate_url("https://example.com:8080") is True

        # Invalid URLs
        assert menu.validate_url("not-a-url") is False
        assert menu.validate_url("") is False

    def test_menu_shows_validation_errors(self, mock_menu, mock_console):
        """Test validation errors are displayed to user."""
        menu = mock_menu.return_value
        menu.console = mock_console

        menu.show_error("Invalid vector store selection")

        mock_console.print.assert_called_with(
            "[red]Error: Invalid vector store selection[/red]"
        )