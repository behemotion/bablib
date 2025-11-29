"""Command router for flag-based operation routing."""

from dataclasses import dataclass
from typing import Any


@dataclass
class RouteOperation:
    """Represents a routed operation."""

    type: str
    options: dict[str, Any]


class CommandRouter:
    """Routes command flags to appropriate operations."""

    def __init__(self):
        """Initialize the command router."""
        self.operation_flags = {"init", "uninstall", "reset"}
        self.modifier_flags = {"force", "auto", "non-interactive"}
        self.option_flags = {"vector-store", "backup", "dry-run", "preserve-data"}

    def validate_flags(
        self,
        init: bool = False,
        uninstall: bool = False,
        reset: bool = False,
        force: bool = False,
        auto: bool = False,
        non_interactive: bool = False,
        vector_store: str | None = None,
        backup: bool = False,
        dry_run: bool = False,
        preserve_data: bool = False,
        **kwargs
    ) -> bool:
        """Validate flag combinations.

        Returns:
            True if valid, raises ValueError if invalid
        """
        # Check for conflicting operation flags
        operation_count = sum([init, uninstall, reset])
        if operation_count > 1:
            ops = []
            if init:
                ops.append("--init")
            if uninstall:
                ops.append("--uninstall")
            if reset:
                ops.append("--reset")
            raise ValueError(
                f"conflicting operation flags: {', '.join(ops)} cannot be used together. "
                "Only one operation flag can be specified at a time."
            )

        # Check flag dependencies
        if vector_store and not init:
            raise ValueError(
                "--vector-store requires --init flag. "
                "Try: bablib setup --init --vector-store sqlite_vec"
            )

        if auto and operation_count == 0:
            raise ValueError(
                "--auto requires an operation flag. "
                "Try: bablib setup --init --auto"
            )

        if non_interactive and operation_count == 0:
            raise ValueError(
                "--non-interactive requires an operation flag. "
                "Try: bablib setup --init --non-interactive"
            )

        if force and operation_count == 0:
            raise ValueError(
                "--force requires an operation flag. "
                "Try: bablib setup --uninstall --force"
            )

        # Check option flag dependencies
        if backup and not uninstall:
            raise ValueError(
                "--backup requires --uninstall flag. "
                "Try: bablib setup --uninstall --backup"
            )

        if dry_run and not uninstall:
            raise ValueError(
                "--dry-run requires --uninstall flag. "
                "Try: bablib setup --uninstall --dry-run"
            )

        if preserve_data and not (uninstall or reset):
            raise ValueError(
                "--preserve-data requires --uninstall or --reset flag"
            )

        return True

    def route_operation(
        self,
        init: bool = False,
        uninstall: bool = False,
        reset: bool = False,
        force: bool = False,
        auto: bool = False,
        non_interactive: bool = False,
        vector_store: str | None = None,
        backup: bool = False,
        dry_run: bool = False,
        preserve_data: bool = False,
        **kwargs
    ) -> RouteOperation:
        """Route flags to appropriate operation.

        Returns:
            RouteOperation with operation type and options
        """
        # Validate first
        self.validate_flags(
            init=init,
            uninstall=uninstall,
            reset=reset,
            force=force,
            auto=auto,
            non_interactive=non_interactive,
            vector_store=vector_store,
            backup=backup,
            dry_run=dry_run,
            preserve_data=preserve_data,
            **kwargs
        )

        # Determine operation type
        if init:
            return RouteOperation(
                type="init",
                options={
                    "auto": auto,
                    "force": force,
                    "vector_store": vector_store,
                    "non_interactive": non_interactive,
                    **kwargs
                }
            )
        elif uninstall:
            return RouteOperation(
                type="uninstall",
                options={
                    "force": force,
                    "backup": backup,
                    "dry_run": dry_run,
                    "preserve_data": preserve_data,
                    **kwargs
                }
            )
        elif reset:
            return RouteOperation(
                type="reset",
                options={
                    "force": force,
                    "preserve_data": preserve_data,
                    "vector_store": vector_store,
                    **kwargs
                }
            )
        else:
            # No operation flags - launch menu
            return RouteOperation(
                type="menu",
                options={}
            )

    def get_flag_help(self) -> str:
        """Get help text for valid flag combinations.

        Returns:
            Help text string
        """
        return """
Valid flag combinations for 'bablib setup':

Operation Flags (choose one):
  --init            Initialize Bablib configuration
  --uninstall       Remove Bablib installation
  --reset           Reset to fresh state (uninstall + reinit)
  (no flags)        Launch interactive menu

Modifier Flags:
  --force           Skip confirmation prompts
  --auto            Use automatic mode with defaults (requires operation)
  --non-interactive Disable all prompts (requires operation)

Option Flags:
  --vector-store    Select vector store: sqlite_vec or qdrant (with --init)
  --backup          Create backup before uninstalling (with --uninstall)
  --dry-run         Show what would be removed (with --uninstall)
  --preserve-data   Keep user project data (with --uninstall or --reset)

Examples:
  bablib setup                                  # Interactive menu
  bablib setup --init --auto                    # Quick setup with defaults
  bablib setup --init --vector-store sqlite_vec # Setup with specific store
  bablib setup --uninstall --force              # Uninstall without confirmation
  bablib setup --reset --preserve-data          # Reset but keep projects
"""

    def parse_conflict_error(self, flags: set[str]) -> tuple[str, str]:
        """Parse conflicting flags and generate error message with suggestion.

        Args:
            flags: Set of flag names

        Returns:
            Tuple of (error_message, suggestion)
        """
        operation_conflicts = flags & self.operation_flags

        if len(operation_conflicts) > 1:
            formatted_flags = [f"--{f}" for f in operation_conflicts]
            error = (
                f"Conflicting flags: {', '.join(formatted_flags)} "
                "cannot be used together."
            )
            suggestion = "Use only one operation flag at a time."
        else:
            error = f"Invalid flag combination: {', '.join(flags)}"
            suggestion = "Run 'bablib setup --help' for valid combinations."

        return error, suggestion

    def get_operation_description(self, operation_type: str) -> str:
        """Get description of an operation type.

        Args:
            operation_type: Type of operation

        Returns:
            Human-readable description
        """
        descriptions = {
            "init": "Initialize Bablib with configuration and directories",
            "uninstall": "Remove Bablib installation and all data",
            "reset": "Reset Bablib to a fresh installation state",
            "menu": "Interactive menu for setup operations"
        }
        return descriptions.get(operation_type, "Unknown operation")

    def is_destructive_operation(self, operation_type: str) -> bool:
        """Check if operation is destructive and needs confirmation.

        Args:
            operation_type: Type of operation

        Returns:
            True if operation is destructive
        """
        return operation_type in ["uninstall", "reset"]

    def get_required_confirmations(self, operation_type: str) -> int:
        """Get number of confirmations required for an operation.

        Args:
            operation_type: Type of operation

        Returns:
            Number of confirmations needed
        """
        confirmations = {
            "init": 0,
            "uninstall": 1,
            "reset": 2,  # Double confirmation
            "menu": 0
        }
        return confirmations.get(operation_type, 0)
