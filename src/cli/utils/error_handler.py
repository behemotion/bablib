"""Centralized CLI error handling with consistent messaging and suggestions.

Provides standardized error messages, actionable suggestions, and consistent
error formatting across all CLI commands.
"""

import logging
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)


# Standard CLI error message templates
CLI_ERROR_MESSAGES = {
    # Project errors
    "project_exists": "Project '{name}' already exists. Use --force to overwrite.",
    "project_not_found": "Project '{name}' not found.",
    "invalid_project_type": "Invalid project type '{type}'. Must be one of: {valid_types}",
    "project_in_use": "Project '{name}' is currently in use by another operation.",
    "project_corrupted": "Project '{name}' appears to be corrupted. Consider removing and recreating it.",

    # Upload/source errors
    "invalid_source_type": "Invalid source type '{type}'. Must be one of: {valid_types}",
    "source_not_found": "Source '{source}' not found or inaccessible.",
    "authentication_failed": "Authentication failed for {source}. Please check credentials.",
    "network_timeout": "Network timeout while connecting to {source}. Retrying ({attempt}/3)...",
    "connection_refused": "Connection refused to {source}. Check if the service is running.",

    # File errors
    "file_too_large": "File '{filename}' ({size}) exceeds maximum size limit ({limit}).",
    "invalid_format": "File '{filename}' has unsupported format '{format}' for {project_type} projects.",
    "file_corrupted": "File '{filename}' appears to be corrupted or incomplete.",
    "permission_denied": "Permission denied accessing '{path}'. Check file permissions.",
    "path_not_found": "Path '{path}' does not exist.",

    # System errors
    "disk_space_low": "Insufficient disk space. Need {required}, have {available}.",
    "memory_limit": "Operation requires {required} memory, but only {available} is available.",
    "service_unavailable": "Required service '{service}' is not available. {suggestion}",

    # Configuration errors
    "invalid_config": "Invalid configuration: {details}",
    "missing_setting": "Required setting '{setting}' is not configured.",
    "config_conflict": "Configuration conflict: {details}",

    # Operation errors
    "operation_failed": "Operation '{operation}' failed: {reason}",
    "operation_cancelled": "Operation cancelled by user.",
    "operation_timeout": "Operation timed out after {duration} seconds.",
    "concurrent_operation": "Another {operation} operation is already in progress.",

    # Validation errors
    "validation_failed": "Validation failed: {details}",
    "invalid_input": "Invalid input '{input}': {reason}",
    "missing_required": "Required parameter '{parameter}' is missing.",

    # Database errors
    "database_error": "Database error: {details}",
    "database_locked": "Database is locked by another process. Try again later.",
    "migration_failed": "Database migration failed: {reason}"
}


# Suggested actions for common errors
ERROR_SUGGESTIONS = {
    "project_not_found": [
        "Run 'bablib shelf list' to see available shelves",
        "Run 'bablib box list' to see available boxes",
        "Check the name spelling",
        "Create a shelf and box first: 'bablib shelf create <name>' then 'bablib box create <name> --type <type>'"
    ],
    "authentication_failed": [
        "Verify your username and password",
        "Check if the service requires special authentication methods",
        "For SSH/SFTP, ensure your SSH key is properly configured"
    ],
    "network_timeout": [
        "Check your internet connection",
        "Verify the host is accessible",
        "Try increasing the timeout value",
        "Check firewall settings"
    ],
    "disk_space_low": [
        "Free up disk space by removing unnecessary files",
        "Use 'df -h' to check available space",
        "Consider moving the project to a different location"
    ],
    "permission_denied": [
        "Check file/directory permissions with 'ls -la'",
        "Run with appropriate user permissions",
        "Use 'chmod' to fix permissions if you own the files"
    ],
    "service_unavailable": [
        "Check if the service is installed",
        "Start the service if it's not running",
        "Verify service configuration"
    ],
    "invalid_format": [
        "Check the list of supported formats for this project type",
        "Convert the file to a supported format",
        "Use a different project type that supports this format"
    ]
}


class CLIErrorHandler:
    """Centralized error handler for CLI commands."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.error_count = 0
        self.warning_count = 0

    def error(
        self,
        error_key: str,
        context: dict[str, Any] | None = None,
        show_suggestions: bool = True,
        exit_after: bool = False
    ) -> None:
        """Display a formatted error message.

        Args:
            error_key: Key from CLI_ERROR_MESSAGES
            context: Dict with values to format into the message
            show_suggestions: Whether to show suggested actions
            exit_after: Whether to exit the program after showing the error
        """
        try:
            # Get error message template
            if error_key in CLI_ERROR_MESSAGES:
                message = CLI_ERROR_MESSAGES[error_key]
                if context:
                    message = message.format(**context)
            else:
                message = error_key  # Use as literal message if not a template

            # Create error text
            error_text = Text()
            error_text.append("✗ Error: ", style="bold red")
            error_text.append(message, style="red")

            # Display error
            self.console.print(error_text)
            self.error_count += 1

            # Show suggestions if available
            if show_suggestions and error_key in ERROR_SUGGESTIONS:
                self._show_suggestions(ERROR_SUGGESTIONS[error_key])

            # Log the error
            logger.error(f"CLI Error [{error_key}]: {message}")

            # Exit if requested
            if exit_after:
                import sys
                sys.exit(1)

        except Exception as e:
            # Fallback error display
            self.console.print(f"[red]Error: {error_key}[/red]")
            logger.error(f"Error handler failed: {e}")

    def warning(
        self,
        message: str,
        details: str | None = None
    ) -> None:
        """Display a formatted warning message."""
        warning_text = Text()
        warning_text.append("⚠ Warning: ", style="bold yellow")
        warning_text.append(message, style="yellow")

        self.console.print(warning_text)

        if details:
            self.console.print(f"  {details}", style="dim yellow")

        self.warning_count += 1
        logger.warning(f"CLI Warning: {message}")

    def success(
        self,
        message: str,
        details: str | None = None
    ) -> None:
        """Display a success message."""
        success_text = Text()
        success_text.append("✓ ", style="bold green")
        success_text.append(message, style="green")

        self.console.print(success_text)

        if details:
            self.console.print(f"  {details}", style="dim green")

    def info(
        self,
        message: str,
        details: str | None = None
    ) -> None:
        """Display an informational message."""
        self.console.print(f"[cyan]ℹ {message}[/cyan]")

        if details:
            self.console.print(f"  {details}", style="dim cyan")

    def _show_suggestions(self, suggestions: list[str]) -> None:
        """Display suggested actions for error recovery."""
        if not suggestions:
            return

        self.console.print("\n[yellow]Suggested actions:[/yellow]")
        for suggestion in suggestions:
            self.console.print(f"  • {suggestion}")

    def handle_exception(
        self,
        exception: Exception,
        operation: str | None = None,
        show_traceback: bool = False
    ) -> None:
        """Handle unexpected exceptions with appropriate messaging."""
        try:
            # Map common exceptions to user-friendly messages
            error_mapping = {
                FileNotFoundError: "file_not_found",
                PermissionError: "permission_denied",
                ConnectionRefusedError: "connection_refused",
                TimeoutError: "operation_timeout",
                MemoryError: "memory_limit",
                KeyboardInterrupt: "operation_cancelled"
            }

            # Check if we can map this exception
            for exc_type, error_key in error_mapping.items():
                if isinstance(exception, exc_type):
                    context = {"path": str(exception)} if hasattr(exception, 'filename') else {}
                    self.error(error_key, context)
                    return

            # Generic exception handling
            if operation:
                self.error(
                    "operation_failed",
                    {"operation": operation, "reason": str(exception)}
                )
            else:
                self.console.print(f"[red]Unexpected error: {str(exception)}[/red]")

            # Show traceback if requested or in debug mode
            if show_traceback:
                import traceback
                self.console.print(
                    Panel(
                        traceback.format_exc(),
                        title="Traceback",
                        border_style="red",
                        expand=False
                    )
                )

            logger.exception(f"Unhandled exception in {operation or 'CLI'}")

        except Exception:
            # Last resort error display
            self.console.print(f"[red]Fatal error: {str(exception)}[/red]")
            logger.exception("Error handler crashed")

    def show_validation_errors(
        self,
        errors: list[str],
        title: str = "Validation Failed"
    ) -> None:
        """Display a list of validation errors."""
        if not errors:
            return

        error_panel = Panel.fit(
            "\n".join([f"• {error}" for error in errors]),
            title=f"[red]{title}[/red]",
            border_style="red"
        )
        self.console.print(error_panel)

        self.error_count += len(errors)

    def get_error_summary(self) -> str:
        """Get a summary of errors and warnings."""
        parts = []
        if self.error_count > 0:
            parts.append(f"{self.error_count} error{'s' if self.error_count != 1 else ''}")
        if self.warning_count > 0:
            parts.append(f"{self.warning_count} warning{'s' if self.warning_count != 1 else ''}")

        return ", ".join(parts) if parts else "No errors"

    def reset_counters(self) -> None:
        """Reset error and warning counters."""
        self.error_count = 0
        self.warning_count = 0


# Convenience functions for quick error handling

def show_error(
    message: str,
    console: Console | None = None,
    exit_after: bool = False
) -> None:
    """Quick function to show an error message."""
    handler = CLIErrorHandler(console)
    handler.error(message, exit_after=exit_after)


def show_warning(
    message: str,
    console: Console | None = None
) -> None:
    """Quick function to show a warning message."""
    handler = CLIErrorHandler(console)
    handler.warning(message)


def show_success(
    message: str,
    console: Console | None = None
) -> None:
    """Quick function to show a success message."""
    handler = CLIErrorHandler(console)
    handler.success(message)


def format_error_message(
    error_key: str,
    context: dict[str, Any] | None = None
) -> str:
    """Format an error message without displaying it."""
    if error_key in CLI_ERROR_MESSAGES:
        message = CLI_ERROR_MESSAGES[error_key]
        if context:
            return message.format(**context)
        return message
    return error_key
