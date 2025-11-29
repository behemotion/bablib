"""Universal arrow key navigation utility for CLI interfaces."""

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table

logger = logging.getLogger(__name__)

# Platform-specific imports for keyboard navigation
try:
    import termios
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False


@dataclass
class NavigationChoice:
    """Represents a choice in navigation menu.

    Args:
        value: The value returned when this choice is selected
        label: The main display text for the option
        description: Optional longer description (displayed separately if needed)
        status: Optional status indicator (e.g., "[active]", "[v2.0]", "[installed]")
        style: Optional Rich style for custom formatting
    """
    value: str
    label: str
    description: str | None = None
    status: str | None = None
    style: str | None = None


@dataclass
class NavigationTheme:
    """Consistent theme settings for all navigation interfaces.

    Provides unified styling across all Bablib navigation menus.
    """
    highlight_style: str = "blue on white"  # Selected item style
    arrow_indicator: str = "→"  # Selection indicator
    box_style: str = "rounded"  # Box drawing style for panels
    number_hints: bool = True  # Show number shortcuts
    vim_mode: bool = True  # Enable w/s navigation


class ArrowNavigator:
    """Universal arrow key navigation utility."""

    def __init__(self, console: Console | None = None, theme: NavigationTheme | None = None):
        """Initialize the navigator.

        Args:
            console: Optional Rich console for output
            theme: Optional NavigationTheme for consistent styling
        """
        self.console = console or Console()
        self.theme = theme or NavigationTheme()
        self.use_keyboard_navigation = sys.stdin.isatty() and HAS_TERMIOS

    def get_char(self) -> str:
        """Get a single character from stdin without Enter.

        Returns:
            Character pressed or special key name
        """
        if not self.use_keyboard_navigation:
            # Fallback for non-TTY environments or platforms without termios
            return input().strip()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)

            # Handle escape sequences (arrow keys)
            if ch == '\x1b':  # ESC
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        return 'up'
                    elif ch3 == 'B':
                        return 'down'
                    elif ch3 == 'C':
                        return 'right'
                    elif ch3 == 'D':
                        return 'left'
                return 'escape'
            elif ch == '\r' or ch == '\n':
                return 'enter'
            elif ch == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
            elif ch == 'q':
                return 'quit'
            elif ch == '?':
                return 'help'
            elif ch.isdigit():
                return ch
            elif ch in 'sS':  # W/S navigation (down)
                return 'down'
            elif ch in 'wW':  # W/S navigation (up)
                return 'up'
            else:
                return ch

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def handle_navigation_key(
        self,
        key: str,
        current_index: int,
        choices_count: int
    ) -> tuple[int, str | None]:
        """Handle navigation key input.

        Args:
            key: Key pressed
            current_index: Current selection index
            choices_count: Total number of choices

        Returns:
            Tuple of (new_index, action) where action can be:
            - None: continue navigation
            - 'select': select current option
            - 'quit': quit navigation
            - 'help': show help
        """
        if key in ['up', 'w', 'W']:
            return (current_index - 1) % choices_count, None
        elif key in ['down', 's', 'S']:
            return (current_index + 1) % choices_count, None
        elif key == 'enter':
            return current_index, 'select'
        elif key in ['quit', 'escape', 'q']:
            return current_index, 'quit'
        elif key == 'help' or key == '?':
            return current_index, 'help'
        elif key.isdigit():
            # Direct number selection
            idx = int(key) - 1
            if 0 <= idx < choices_count:
                return idx, 'select'

        return current_index, None

    def display_choices_table(
        self,
        choices: list[NavigationChoice],
        current_index: int,
        title: str | None = None,
        show_numbers: bool = None,
        highlight_style: str | None = None
    ) -> None:
        """Display choices in a table format.

        Args:
            choices: List of navigation choices
            current_index: Currently selected index
            title: Optional title to display
            show_numbers: Whether to show numbered options (uses theme default if None)
            highlight_style: Rich style for highlighted option (uses theme default if None)
        """
        if show_numbers is None:
            show_numbers = self.theme.number_hints
        if highlight_style is None:
            highlight_style = self.theme.highlight_style
        if title:
            self.console.print(f"\n[cyan]{title}[/cyan]")

        table = Table(show_header=False, show_edge=False)
        if show_numbers:
            table.add_column("Key", style="yellow")
        table.add_column("Option")

        for i, choice in enumerate(choices):
            # Number display for AddressNavigator pattern
            if show_numbers:
                key_display = f"{self.theme.arrow_indicator} {i+1}" if i == current_index else f"  {i+1}"
            else:
                key_display = self.theme.arrow_indicator if i == current_index else " "

            # Build the option display with label and status
            if choice.status:
                label_with_status = f"{choice.label} [dim cyan]{choice.status}[/dim cyan]"
            else:
                label_with_status = choice.label

            if i == current_index:
                # For highlighted items, include status within the highlight
                if choice.status:
                    option_display = f"[{highlight_style}] {choice.label} {choice.status} [/{highlight_style}]"
                else:
                    option_display = f"[{highlight_style}] {choice.label} [/{highlight_style}]"
            else:
                option_display = label_with_status
                if choice.style:
                    option_display = f"[{choice.style}]{option_display}[/{choice.style}]"

            if show_numbers:
                table.add_row(key_display, option_display)
            else:
                table.add_row(key_display, option_display)

        self.console.print(table)

    def show_help(self, vim_keys: bool = True) -> None:
        """Display navigation help.

        Args:
            vim_keys: Whether to show vim-style key bindings
        """
        help_lines = [
            "[bold yellow]Navigation Help[/bold yellow]",
            "",
            "• [cyan]↑/↓[/cyan] Arrow keys - Navigate options",
            "• [cyan]1-9[/cyan] Numbers - Direct selection",
            "• [cyan]Enter[/cyan] - Select highlighted option",
            "• [cyan]Escape[/cyan] or [cyan]q[/cyan] - Quit/Go back",
            "• [cyan]?[/cyan] - Show this help",
        ]

        if vim_keys:
            help_lines.insert(3, "• [cyan]w/s[/cyan] W/S keys - Navigate options")

        help_lines.append("")
        help_lines.append("[dim]Press any key to continue...[/dim]")

        help_text = "\n".join(help_lines)
        self.console.print(Panel(help_text, title="Help", border_style="cyan"))

        if self.use_keyboard_navigation:
            self.get_char()
        else:
            input()

    def navigate_choices(
        self,
        prompt: str,
        choices: list[NavigationChoice] | list[tuple[str, str]],
        default: str | None = None,
        help_callback: Callable | None = None,
        show_instructions: bool = True,
        vim_keys: bool = True
    ) -> str | None:
        """Interactive navigation through choices.

        Args:
            prompt: Prompt message to display
            choices: List of NavigationChoice objects or (value, label) tuples
            default: Default choice value
            help_callback: Optional custom help function
            show_instructions: Whether to show navigation instructions
            vim_keys: Whether to enable vim-style navigation keys

        Returns:
            Selected choice value or None if cancelled
        """
        # Convert tuples to NavigationChoice objects if needed
        if choices and isinstance(choices[0], tuple):
            choices = [NavigationChoice(value=v, label=l) for v, l in choices]

        if not choices:
            return None

        choice_values = [choice.value for choice in choices]

        # Find default index
        current_index = 0
        if default and default in choice_values:
            current_index = choice_values.index(default)

        if not self.use_keyboard_navigation:
            # Fallback to numbered input for non-TTY environments
            self.display_choices_table(choices, current_index, title=prompt)

            try:
                choice_num = IntPrompt.ask(
                    "Select option",
                    choices=[str(i) for i in range(1, len(choices) + 1)],
                    default=str(current_index + 1),
                    console=self.console
                )
                return choice_values[choice_num - 1]
            except (KeyboardInterrupt, EOFError):
                return default or choice_values[0] if choice_values else None

        # Interactive arrow key navigation
        while True:
            self.console.clear()
            self.display_choices_table(choices, current_index, title=prompt)

            if show_instructions:
                instruction_parts = ["Use ↑/↓ arrows"]
                if vim_keys:
                    instruction_parts.append("or w/s")
                instruction_parts.extend(["or numbers to navigate", "Enter to select", "? for help", "q to quit"])
                instruction = ", ".join(instruction_parts)
                self.console.print(f"\n[dim]{instruction}[/dim]")

            try:
                key = self.get_char()
                new_index, action = self.handle_navigation_key(key, current_index, len(choices))

                current_index = new_index

                if action == 'select':
                    return choice_values[current_index]
                elif action == 'quit':
                    return default or choice_values[0] if choice_values else None
                elif action == 'help':
                    if help_callback:
                        help_callback()
                    else:
                        self.show_help(vim_keys=vim_keys)

            except KeyboardInterrupt:
                return default or choice_values[0] if choice_values else None

    def confirm_yes_no(
        self,
        prompt: str,
        default: bool = False
    ) -> bool:
        """Display a yes/no confirmation prompt.

        IMPORTANT: This method NEVER uses numbered options per constitutional requirements.
        Only accepts y/n/yes/no keys (case-insensitive).

        Args:
            prompt: The confirmation question to display
            default: Default value if Enter is pressed (True for yes, False for no)

        Returns:
            True if user confirms (yes), False otherwise (no)
        """
        default_hint = "[Y/n]" if default else "[y/N]"
        self.console.print(f"\n[yellow]{prompt}[/yellow] {default_hint}: ", end="")

        if not self.use_keyboard_navigation:
            # Non-interactive fallback
            response = input().strip().lower()
        else:
            response = self.get_char().lower()

        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        elif response == 'enter':
            return default
        else:
            # Invalid input, ask again
            self.console.print("[red]Please answer 'y' for yes or 'n' for no.[/red]")
            return self.confirm_yes_no(prompt, default)

    def navigate_menu(
        self,
        title: str,
        menu_items: list[NavigationChoice],
        default_index: int = 0,
        show_instructions: bool = True,
        vim_keys: bool = True
    ) -> str | None:
        """Navigate a menu with title and return selected value.

        Args:
            title: Menu title
            menu_items: List of menu items
            default_index: Default selected index
            show_instructions: Whether to show navigation instructions
            vim_keys: Whether to enable vim-style navigation keys

        Returns:
            Selected menu item value or None if cancelled
        """
        current_index = default_index

        if not self.use_keyboard_navigation:
            # Fallback for non-TTY environments
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]\n")
            self.display_choices_table(menu_items, current_index)

            try:
                choice_num = IntPrompt.ask(
                    "Select option",
                    choices=[str(i) for i in range(1, len(menu_items) + 1)],
                    default=str(current_index + 1),
                    console=self.console
                )
                return menu_items[choice_num - 1].value
            except (KeyboardInterrupt, EOFError):
                return None

        # Interactive navigation
        while True:
            self.console.clear()
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]\n")
            self.display_choices_table(menu_items, current_index)

            if show_instructions:
                instruction_parts = ["Use ↑/↓ arrows"]
                if vim_keys:
                    instruction_parts.append("or w/s")
                instruction_parts.extend(["or numbers to navigate", "Enter to select", "? for help", "q to quit"])
                instruction = ", ".join(instruction_parts)
                self.console.print(f"\n[dim]{instruction}[/dim]")

            try:
                key = self.get_char()
                new_index, action = self.handle_navigation_key(key, current_index, len(menu_items))

                current_index = new_index

                if action == 'select':
                    return menu_items[current_index].value
                elif action == 'quit':
                    return None
                elif action == 'help':
                    self.show_help(vim_keys=vim_keys)

            except KeyboardInterrupt:
                return None


# Convenience functions
def create_navigation_choice(
    value: str,
    label: str,
    description: str | None = None,
    status: str | None = None
) -> NavigationChoice:
    """Create a navigation choice object.

    Args:
        value: Choice value to return when selected
        label: Display label for the choice (required - short description)
        description: Optional longer description
        status: Optional status indicator (e.g., "[enabled]", "[v1.0]")

    Returns:
        NavigationChoice object
    """
    return NavigationChoice(value=value, label=label, description=description, status=status)


def prompt_with_arrows(
    prompt: str,
    choices: list[NavigationChoice] | list[tuple[str, str]],
    default: str | None = None,
    console: Console | None = None
) -> str | None:
    """Quick prompt with arrow navigation.

    Supports both ArrowNavigator (arrows) and AddressNavigator (numbers).

    Args:
        prompt: Prompt message
        choices: List of choices
        default: Default choice value
        console: Optional Rich console

    Returns:
        Selected choice value
    """
    navigator = ArrowNavigator(console=console)
    return navigator.navigate_choices(prompt, choices, default=default)


def confirm_action(
    prompt: str,
    default: bool = False,
    console: Console | None = None
) -> bool:
    """Display a yes/no confirmation prompt.

    IMPORTANT: Never uses numbered options - only y/n keys per constitutional requirements.

    Args:
        prompt: Confirmation question
        default: Default value if Enter pressed
        console: Optional Rich console

    Returns:
        True if confirmed (yes), False otherwise
    """
    navigator = ArrowNavigator(console=console)
    return navigator.confirm_yes_no(prompt, default)
