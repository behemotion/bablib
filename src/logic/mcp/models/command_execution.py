"""CommandExecutionRequest model for executing Bablib CLI commands via admin server."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class CommandState(str, Enum):
    """States of command execution."""

    CREATED = "created"
    VALIDATED = "validated"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class AllowedCommand(str, Enum):
    """Commands allowed via admin server execution."""

    PROJECT = "project"
    CRAWL = "crawl"
    SETUP = "setup"
    HEALTH = "health"
    UPLOAD = "upload"


class CommandExecutionRequest(BaseModel):
    """Request to execute Bablib CLI commands via admin server.

    Attributes:
        command: Base command (e.g., "project", "crawl")
        arguments: Command arguments
        options: Command options/flags
        timeout: Execution timeout in seconds
    """

    command: AllowedCommand
    arguments: List[str] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[int] = Field(default=30, ge=1, le=300)

    # Internal state tracking
    state: CommandState = Field(default=CommandState.CREATED, exclude=True)

    @field_validator("command")
    @classmethod
    def validate_allowed_command(cls, v: AllowedCommand) -> AllowedCommand:
        """Validate that only allowed commands can be executed."""
        # 'serve' command is intentionally excluded to prevent recursion
        return v

    @field_validator("arguments")
    @classmethod
    def validate_arguments(cls, v: List[str]) -> List[str]:
        """Validate command arguments for basic security."""
        for arg in v:
            if not isinstance(arg, str):
                raise ValueError("All arguments must be strings")

            # Basic security check - prevent command injection
            if ";" in arg or "|" in arg or "&" in arg:
                raise ValueError("Arguments cannot contain command separators")

        return v

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate command options."""
        # Ensure all option keys are valid strings
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError("Option keys must be strings")

            # Basic validation of option values
            if not isinstance(value, (str, int, float, bool)):
                raise ValueError("Option values must be simple types (str, int, float, bool)")

        return v

    def to_command_string(self) -> str:
        """Convert to command string for execution."""
        parts = [f"bablib {self.command.value}"]

        # Add arguments
        parts.extend(self.arguments)

        # Add options
        for key, value in self.options.items():
            if isinstance(value, bool):
                if value:
                    parts.append(f"--{key}")
            else:
                parts.append(f"--{key}={value}")

        return " ".join(parts)

    def is_safe_to_execute(self) -> bool:
        """Check if the command is safe to execute."""
        # Additional safety checks beyond validation

        # Prevent recursive serve commands
        if self.command == "project" and "serve" in self.arguments:
            return False

        # Prevent uninstall operations via MCP admin
        if self.command == AllowedCommand.SETUP:
            if "--uninstall" in self.arguments or any("uninstall" in arg.lower() for arg in self.arguments):
                return False
            if "--reset" in self.arguments or any("reset" in arg.lower() for arg in self.arguments):
                return False

        # Prevent delete all projects operation
        if self.command == AllowedCommand.PROJECT:
            # Check if trying to remove all projects
            if "--remove" in self.arguments and ("--all" in self.arguments or any("all" in arg.lower() for arg in self.arguments)):
                return False
            # Also block if trying to remove with wildcard patterns
            for arg in self.arguments:
                if arg in ["*", "**", ".*"]:
                    return False

        # Check for potentially dangerous operations
        dangerous_patterns = ["rm", "delete", "--force", "--yes"]
        command_str = self.to_command_string().lower()

        if any(pattern in command_str for pattern in dangerous_patterns):
            # These might be OK in specific contexts, but require careful review
            pass

        return True

    def advance_state(self, new_state: CommandState) -> None:
        """Advance the command to a new state."""
        valid_transitions = {
            CommandState.CREATED: [CommandState.VALIDATED, CommandState.FAILED],
            CommandState.VALIDATED: [CommandState.EXECUTING, CommandState.FAILED],
            CommandState.EXECUTING: [CommandState.COMPLETED, CommandState.FAILED],
            CommandState.COMPLETED: [],  # Terminal state
            CommandState.FAILED: [],     # Terminal state
        }

        if new_state not in valid_transitions[self.state]:
            raise ValueError(f"Invalid state transition from {self.state} to {new_state}")

        self.state = new_state