"""Interactive menu system for setup operations."""

from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.cli.utils.navigation import ArrowNavigator, NavigationChoice
from src.core.lib_logger import get_logger
from src.logic.setup.models.menu_state import MenuState

logger = get_logger(__name__)


class InteractiveMenu:
    """Interactive menu for setup operations."""

    def __init__(self, console: Console | None = None):
        """Initialize the interactive menu.

        Args:
            console: Optional Rich console for testing
        """
        self.console = console or Console()
        self.state = MenuState()
        self.navigator = ArrowNavigator(console=self.console)

    def run(self) -> str | None:
        """Run the interactive menu.

        Returns:
            Selected operation or None if cancelled
        """
        try:
            selection = self._show_main_menu()
            return selection
        except KeyboardInterrupt:
            return None
        except Exception as e:
            logger.error(f"Menu error: {e}")
            return None


    def render(self) -> None:
        """Render the current menu state."""
        self.clear_screen()

        if self.state.current_menu == "main":
            self.display_main_menu()
        elif self.state.current_menu == "configuration":
            self.display_configuration_menu()

        # Show navigation path
        if not self.state.is_at_root():
            path = self.state.get_navigation_path()
            self.console.print(f"\n[dim]{path}[/dim]")

        # Show help hint
        if not self.state.help_visible:
            self.console.print("\n[dim]Press ? for help[/dim]")

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        self.console.clear()

    def show_error(self, message: str) -> None:
        """Display an error message.

        Args:
            message: Error message to display
        """
        self.console.print(f"[red]Error: {message}[/red]")
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()

    def validate_url(self, url: str) -> bool:
        """Validate URL format.

        Args:
            url: URL to validate

        Returns:
            True if valid
        """
        return url.startswith(("http://", "https://"))

    def validate_config_value(self, key: str, value: Any) -> bool:
        """Validate a configuration value.

        Args:
            key: Configuration key
            value: Value to validate

        Returns:
            True if valid
        """
        if key == "vector_store_provider":
            return value in ["sqlite_vec", "qdrant"]
        elif key == "ollama_url":
            return self.validate_url(value)
        elif key == "embedding_model":
            valid_models = ["mxbai-embed-large", "nomic-embed-text", "all-minilm"]
            return value in valid_models
        elif key == "crawl_depth":
            return isinstance(value, int) and 1 <= value <= 10

        return True

    def enter_submenu(self, menu_id: str) -> None:
        """Navigate to a submenu.

        Args:
            menu_id: Menu identifier
        """
        self.state.push_menu(menu_id)
        self.current_index = 0

    def get_main_menu_options(self) -> list[str]:
        """Get main menu options.

        Returns:
            List of option labels
        """
        return [
            "Initialize Bablib",
            "Modify Configuration",
            "Uninstall Bablib",
            "Reset Installation",
            "Exit"
        ]

    def filter_options(self, search: str) -> list[str]:
        """Filter options by search term.

        Args:
            search: Search term

        Returns:
            Filtered options
        """
        if not search:
            return self.options

        search_lower = search.lower()
        return [opt for opt in self.options if search_lower in opt.lower()]

    def _show_current_menu(self) -> str | None:
        """Show the current menu and get selection.

        Returns:
            Selected option
        """
        if self.state.current_menu == "main":
            return self._show_main_menu()
        elif self.state.current_menu == "configuration":
            return self._show_configuration_menu()
        else:
            return None

    def _show_main_menu(self) -> str | None:
        """Show main menu and get selection.

        Returns:
            Selected option
        """
        # Display ASCII branding
        from src.cli.utils.branding import ASCIIBranding
        branding = ASCIIBranding()
        logo = branding.render()
        self.console.print(logo)
        self.console.print()  # Add space after logo

        # Display system information panel
        from src.logic.setup.models.system_info import SystemInfoPanel
        info_panel = SystemInfoPanel()
        info_panel.collect_async()

        # Show system info table
        info_table = info_panel.format_table()
        self.console.print(info_table)
        self.console.print()  # Add space after info

        choices = [
            NavigationChoice("initialize", "Initialize Bablib"),
            NavigationChoice("configuration", "Modify Configuration"),
            NavigationChoice("uninstall", "Uninstall Bablib"),
            NavigationChoice("reset", "Reset Installation"),
            NavigationChoice("exit", "Exit")
        ]

        return self.navigator.navigate_menu(
            title="Bablib Setup Menu",
            menu_items=choices,
            default_index=0
        )

    def _show_configuration_menu(self) -> str | None:
        """Show configuration menu and get selection.

        Returns:
            Selected option
        """
        # Load current configuration for display
        from src.logic.setup.services.configurator import SetupConfigurator
        configurator = SetupConfigurator()

        try:
            config = configurator.load_config()
        except FileNotFoundError:
            self.console.print("[red]No configuration found. Please initialize first.[/red]")
            self.console.print("\nPress Enter to go back...")
            input()
            return "back"

        # Display current settings
        self.console.print("\n[bold cyan]Configuration Settings[/bold cyan]\n")
        table = Table(show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Current Value", style="green")

        table.add_row("Vector Store", config.get("vector_store_provider", "Not set"))
        table.add_row("Ollama URL", config.get("ollama_url", "Not set"))
        table.add_row("Embedding Model", config.get("embedding_model", "Not set"))
        table.add_row("Default Crawl Depth", str(config.get("crawl_depth", "3")))

        self.console.print(table)

        choices = [
            NavigationChoice("vector_store", "Change Vector Store"),
            NavigationChoice("ollama_url", "Change Ollama URL"),
            NavigationChoice("embedding_model", "Change Embedding Model"),
            NavigationChoice("crawl_depth", "Change Default Crawl Depth"),
            NavigationChoice("back", "Back to Main Menu")
        ]

        while True:
            result = self.navigator.navigate_choices(
                prompt="Select an option:",
                choices=choices,
                default="back"
            )

            if result == "back" or result is None:
                return "back"
            elif result in ["vector_store", "ollama_url", "embedding_model", "crawl_depth"]:
                self._modify_config_value(result)
                # Stay in menu after modification, reload config display
                try:
                    config = configurator.load_config()
                    self.console.clear()
                    self.console.print("\n[bold cyan]Configuration Settings[/bold cyan]\n")
                    table = Table(show_header=True)
                    table.add_column("Setting", style="cyan")
                    table.add_column("Current Value", style="green")

                    table.add_row("Vector Store", config.get("vector_store_provider", "Not set"))
                    table.add_row("Ollama URL", config.get("ollama_url", "Not set"))
                    table.add_row("Embedding Model", config.get("embedding_model", "Not set"))
                    table.add_row("Default Crawl Depth", str(config.get("crawl_depth", "3")))

                    self.console.print(table)
                except Exception:
                    pass  # Continue even if config reload fails
                continue

    def _handle_configuration(self) -> None:
        """Handle configuration menu navigation."""
        self.state.push_menu("configuration")

    def _modify_config_value(self, key: str) -> None:
        """Modify a configuration value.

        Args:
            key: Configuration key to modify
        """
        from src.logic.setup.services.configurator import SetupConfigurator
        configurator = SetupConfigurator()

        # Get new value from user
        if key == "vector_store":
            new_value = Prompt.ask(
                "Select vector store",
                choices=["sqlite_vec", "qdrant"],
                default="sqlite_vec"
            )
        elif key == "ollama_url":
            new_value = Prompt.ask(
                "Enter Ollama URL",
                default="http://localhost:11434"
            )
        elif key == "embedding_model":
            new_value = Prompt.ask(
                "Select embedding model",
                choices=["mxbai-embed-large", "nomic-embed-text", "all-minilm"],
                default="mxbai-embed-large"
            )
        elif key == "crawl_depth":
            while True:
                depth_str = Prompt.ask(
                    "Enter default crawl depth (1-10)",
                    default="2"
                )
                try:
                    depth = int(depth_str)
                    if 1 <= depth <= 10:
                        new_value = depth
                        break
                    else:
                        self.console.print("[red]Depth must be between 1 and 10[/red]")
                except ValueError:
                    self.console.print("[red]Please enter a valid number[/red]")
        else:
            return

        # Validate and save
        if self.validate_config_value(key, new_value):
            try:
                config = configurator.load_config()
                config[key] = new_value
                configurator.save_config(config)
                self.console.print(f"[green]✓ {key} updated successfully[/green]")
            except Exception as e:
                self.show_error(f"Failed to update configuration: {e}")
        else:
            self.show_error(f"Invalid value for {key}")

    def confirm_action(self, action: str) -> bool:
        """Get confirmation for an action.

        Args:
            action: Action to confirm

        Returns:
            True if confirmed
        """
        return Confirm.ask(f"Are you sure you want to {action}?", default=False)

    def save_configuration(self) -> None:
        """Save pending configuration changes."""
        if self.state.has_pending_changes():
            if self.confirm_action("save configuration changes"):
                changes = self.state.save_changes()
                # Apply changes through configurator
                from src.logic.setup.services.configurator import SetupConfigurator
                configurator = SetupConfigurator()
                config = configurator.load_config()
                config.update(changes)
                configurator.save_config(config)
                self.console.print("[green]✓ Configuration saved[/green]")

    def start_uninstall(self) -> str | None:
        """Start uninstall process with confirmation.

        Returns:
            "uninstall" if confirmed, None otherwise
        """
        from src.logic.setup.services.uninstaller import SetupUninstaller
        uninstaller = SetupUninstaller()

        # Generate and show manifest
        manifest = uninstaller.generate_manifest()

        self.console.print("\n[bold red]Uninstall Manifest[/bold red]\n")
        for line in manifest.to_display_list():
            self.console.print(line)

        if self.confirm_action("proceed with uninstallation"):
            return "uninstall"

        return None
