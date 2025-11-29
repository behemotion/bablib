"""
ASCII Branding Module for Bablib
Provides ASCII art logo generation with 256-color gradient support
"""

import os
import sys

from rich.console import Console


class ASCIIBranding:
    """Encapsulates ASCII art logo generation and rendering"""

    def __init__(
        self,
        text: str = "BABLIB",
        subtitle: str = "BY BEHEMOTION",
        height: int = 7
    ):
        """
        Initialize ASCII branding.

        Args:
            text: The main text to render (default: "BABLIB")
            subtitle: Text below logo (default: "BY BEHEMOTION")
            height: Number of rows for ASCII art (fixed: 7)
        """
        self.text = text.upper()
        self.subtitle = subtitle
        self.height = height
        self.fallback_mode = False
        self.gradient_colors = self._generate_default_gradient()
        self.console = Console()

    def render(self) -> str:
        """
        Generate ASCII art with gradient.

        Returns:
            str: ASCII art with color codes or plain text fallback
        """
        terminal_width = self.detect_terminal_width()

        # Use fallback for narrow terminals
        if terminal_width < 60:
            return self.get_plain_text()

        # Check if terminal supports colors
        if not sys.stdout.isatty():
            return self.get_plain_text()

        # Generate ASCII art
        ascii_art = self._generate_ascii_art()

        # Apply gradient if supported
        if self._supports_256_colors():
            ascii_art = self._apply_gradient(ascii_art)

        # Add subtitle
        full_art = ascii_art + "\n" + self._center_text(self.subtitle, terminal_width)

        return full_art

    def get_plain_text(self) -> str:
        """
        Return fallback plain text.

        Returns:
            str: Plain text version without ASCII art
        """
        return f"{self.text}\n{self.subtitle}"

    def detect_terminal_width(self) -> int:
        """
        Check terminal width capabilities.

        Returns:
            int: Terminal width in characters
        """
        try:
            # Try to get terminal size
            size = os.get_terminal_size()
            return size.columns
        except (OSError, AttributeError):
            # Default to 80 if can't detect
            return 80

    def generate_gradient(self, start_color: int, end_color: int, steps: int) -> list[int]:
        """
        Create color gradient for 256-color terminals.

        Args:
            start_color: Starting color code (0-255)
            end_color: Ending color code (0-255)
            steps: Number of gradient steps

        Returns:
            List[int]: Color codes for gradient
        """
        if steps <= 1:
            return [start_color]

        gradient = []
        for i in range(steps):
            # Linear interpolation
            ratio = i / (steps - 1)
            color = int(start_color + (end_color - start_color) * ratio)
            gradient.append(color)

        return gradient

    def _generate_default_gradient(self) -> list[int]:
        """Generate default green gradient colors."""
        # Green gradient from bright to dark (256-color codes)
        # 46 = bright green, 22 = darker green
        return self.generate_gradient(46, 22, self.height)

    def _generate_ascii_art(self) -> str:
        """Generate the actual ASCII art for BABLIB."""
        # 7-row ASCII art for BABLIB
        art_lines = [
            "██████╗  █████╗ ██████╗ ██╗     ██╗██████╗ ",
            "██╔══██╗██╔══██╗██╔══██╗██║     ██║██╔══██╗",
            "██████╔╝███████║██████╔╝██║     ██║██████╔╝",
            "██╔══██╗██╔══██║██╔══██╗██║     ██║██╔══██╗",
            "██████╔╝██║  ██║██████╔╝███████╗██║██████╔╝",
            "╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝╚═════╝ ",
            "                                           "
        ]

        # Ensure exactly 7 rows
        art_lines = art_lines[:self.height]
        while len(art_lines) < self.height:
            art_lines.append(" " * len(art_lines[0]))

        return "\n".join(art_lines)

    def _apply_gradient(self, text: str) -> str:
        """Apply 256-color gradient to ASCII art."""
        lines = text.split("\n")
        colored_lines = []

        for i, line in enumerate(lines):
            if i < len(self.gradient_colors):
                color_code = self.gradient_colors[i]
                # Use ANSI 256-color escape sequence
                colored_line = f"\033[38;5;{color_code}m{line}\033[0m"
                colored_lines.append(colored_line)
            else:
                colored_lines.append(line)

        return "\n".join(colored_lines)

    def _supports_256_colors(self) -> bool:
        """Check if terminal supports 256 colors."""
        # Check common environment variables
        term = os.environ.get('TERM', '')
        colorterm = os.environ.get('COLORTERM', '')

        # Check for 256 color support
        if '256color' in term or 'truecolor' in colorterm:
            return True

        # Check if TTY and assume modern terminal
        if sys.stdout.isatty():
            return True

        return False

    def _center_text(self, text: str, width: int) -> str:
        """Center text within given width."""
        padding = (width - len(text)) // 2
        return " " * padding + text
