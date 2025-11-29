"""
Menu UI service for interactive settings configuration.
"""

from typing import Any

from rich.console import Console
from rich.live import Live
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.core.config import BablibConfig
from src.models.ui import MenuConfig, MenuState, SettingsMenuItem


class MenuUIService:
    """Service for interactive menu UI using Rich."""

    def __init__(self, console: Console | None = None):
        """Initialize menu UI service."""
        self.console = console or Console()
        self.state = MenuState()
        self.config = MenuConfig(title="Bablib Settings")

    def create_menu_items(self, settings: BablibConfig) -> list[SettingsMenuItem]:
        """Create menu items from settings."""
        items = []

        # Editable settings
        items.append(SettingsMenuItem(
            key="embedding_model",
            display_name="Embedding Model",
            value=settings.embedding_model,
            value_type="str",
            description="Default embedding model for vectors",
            is_editable=True,
            validation={
                "choices": ["mxbai-embed-large", "nomic-embed-text", "all-minilm", "bge-small-en"]
            }
        ))

        items.append(SettingsMenuItem(
            key="crawl_depth",
            display_name="Crawl Depth",
            value=settings.crawl_depth,
            value_type="int",
            description="Default crawling depth in levels",
            is_editable=True,
            validation={"min": 1, "max": 10}
        ))

        items.append(SettingsMenuItem(
            key="chunk_size",
            display_name="Chunk Size",
            value=settings.chunk_size,
            value_type="int",
            description="Text chunk size in characters",
            is_editable=True,
            validation={"min": 100, "max": 10000}
        ))

        items.append(SettingsMenuItem(
            key="rag_top_k",
            display_name="RAG Top K",
            value=settings.rag_top_k,
            value_type="int",
            description="Number of context chunks for RAG",
            is_editable=True,
            validation={"min": 1, "max": 20}
        ))

        items.append(SettingsMenuItem(
            key="rag_temperature",
            display_name="RAG Temperature",
            value=settings.rag_temperature,
            value_type="float",
            description="Generation temperature (0.0-1.0)",
            is_editable=True,
            validation={"min": 0.0, "max": 1.0}
        ))

        items.append(SettingsMenuItem(
            key="rate_limit",
            display_name="Rate Limit",
            value=settings.rate_limit,
            value_type="float",
            description="Requests per second for crawling",
            is_editable=True,
            validation={"min": 0.1, "max": 10.0}
        ))

        items.append(SettingsMenuItem(
            key="max_retries",
            display_name="Max Retries",
            value=settings.max_retries,
            value_type="int",
            description="Maximum retry attempts",
            is_editable=True,
            validation={"min": 0, "max": 10}
        ))

        items.append(SettingsMenuItem(
            key="timeout",
            display_name="Timeout",
            value=settings.timeout,
            value_type="int",
            description="Request timeout in seconds",
            is_editable=True,
            validation={"min": 5, "max": 300}
        ))

        # Non-editable settings (if showing)
        if self.config.show_fixed:
            items.append(SettingsMenuItem(
                key="vector_storage",
                display_name="Vector Storage",
                value=settings.vector_storage,
                value_type="str",
                description="Vector storage location",
                is_editable=False
            ))

            items.append(SettingsMenuItem(
                key="qdrant_url",
                display_name="Qdrant URL",
                value=settings.qdrant_url,
                value_type="str",
                description="Qdrant service endpoint",
                is_editable=False
            ))

            items.append(SettingsMenuItem(
                key="ollama_url",
                display_name="Ollama URL",
                value=settings.ollama_url,
                value_type="str",
                description="Ollama service endpoint",
                is_editable=False
            ))

        return items

    def render_menu(self) -> Table:
        """Render menu as a Rich table."""
        table = Table(
            title=self.config.title,
            show_header=True,
            header_style="bold cyan",
            title_style="bold white"
        )

        table.add_column("", width=2)  # Selection indicator
        table.add_column("Setting", style="cyan", min_width=20)
        table.add_column("Value", style="white", min_width=25)
        table.add_column("Type", style="dim", min_width=15)

        for i, item in enumerate(self.state.items):
            # Selection indicator
            indicator = ">" if i == self.state.current_index else " "

            # Style for current row
            if i == self.state.current_index:
                if self.state.editing:
                    row_style = "bold yellow"
                else:
                    row_style = "bold white"
            else:
                row_style = "dim" if not item.is_editable else None

            # Format value
            if self.state.editing and i == self.state.current_index:
                value_display = f"[{self.state.edit_buffer}]"
            else:
                value_display = item.format_value()

            table.add_row(
                indicator,
                item.display_name,
                value_display,
                item.get_type_hint(),
                style=row_style
            )

        return table

    def validate_input(self, item: SettingsMenuItem, value_str: str) -> tuple[bool, Any, str | None]:
        """Validate user input for a menu item."""
        try:
            # Type conversion
            if item.value_type == "int":
                value = int(value_str)
            elif item.value_type == "float":
                value = float(value_str)
            elif item.value_type == "bool":
                value = value_str.lower() in ["true", "yes", "1", "on"]
            else:
                value = value_str

            # Validation rules
            if item.validation:
                if "min" in item.validation and value < item.validation["min"]:
                    return False, None, f"Value must be >= {item.validation['min']}"
                if "max" in item.validation and value > item.validation["max"]:
                    return False, None, f"Value must be <= {item.validation['max']}"
                if "choices" in item.validation and value not in item.validation["choices"]:
                    choices_str = ", ".join(item.validation["choices"])
                    return False, None, f"Value must be one of: {choices_str}"

            return True, value, None

        except ValueError as e:
            return False, None, f"Invalid {item.value_type}: {str(e)}"

    def handle_keyboard_input(self, key: str) -> str:
        """Handle keyboard input and return action."""
        if not self.state.editing:
            # Navigation mode
            if key in ["up", "k"]:
                self.state.move_up()
                return "navigate"
            elif key in ["down", "j"]:
                self.state.move_down()
                return "navigate"
            elif key == "enter":
                if self.state.start_editing():
                    return "start_edit"
                else:
                    self.state.set_message("This setting cannot be edited", is_error=True)
                    return "error"
            elif key in ["q", "escape"]:
                return "exit"
        else:
            # Editing mode
            if key == "enter":
                # Validate and apply
                item = self.state.get_current_item()
                if item:
                    is_valid, value, error = self.validate_input(item, self.state.edit_buffer)
                    if is_valid:
                        self.state.apply_edit(value)
                        self.state.set_message(f"Updated {item.display_name}")
                        return "apply_edit"
                    else:
                        self.state.set_message(error, is_error=True)
                        return "error"
            elif key == "escape":
                self.state.cancel_editing()
                return "cancel_edit"
            else:
                # Update edit buffer
                if key == "backspace":
                    self.state.edit_buffer = self.state.edit_buffer[:-1]
                else:
                    self.state.edit_buffer += key
                return "editing"

        return "none"

    def run_interactive_menu(self, settings: GlobalSettings) -> dict[str, Any]:
        """Run the interactive menu and return updated settings."""
        # Initialize menu items
        self.state.items = self.create_menu_items(settings)

        # Display menu
        with Live(self.render_menu(), console=self.console, refresh_per_second=10) as live:
            while True:
                # Show hints
                if self.config.show_hints:
                    self.console.print(self.config.get_hints(), style="dim")

                # Show message if any
                if self.state.message:
                    self.console.print(self.state.message, style="yellow")
                    self.state.clear_message()

                # Get keyboard input (simplified for non-interactive context)
                key = Prompt.ask("Action", default="q")

                action = self.handle_keyboard_input(key)

                if action == "exit":
                    if self.state.changes_made and self.config.confirm_exit:
                        if Confirm.ask("Save changes?"):
                            break
                        else:
                            # Reset changes
                            self.state.items = self.create_menu_items(settings)
                            self.state.changes_made = False
                    else:
                        break

                # Update display
                live.update(self.render_menu())

        # Extract updated values
        updates = {}
        for item in self.state.items:
            if item.is_editable and hasattr(settings, item.key):
                current_value = getattr(settings, item.key)
                if item.value != current_value:
                    updates[item.key] = item.value

        return updates

    def display_settings_table(self, settings: GlobalSettings):
        """Display settings in a static table."""
        table = Table(title="Current Global Settings")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Type", style="dim")

        items = self.create_menu_items(settings)
        for item in items:
            table.add_row(
                item.display_name,
                item.format_value(),
                item.get_type_hint()
            )

        self.console.print(table)
