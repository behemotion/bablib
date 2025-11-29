"""Command executor service for CLI command delegation."""

import asyncio
import logging
import time
from typing import NamedTuple
from pathlib import Path

from src.logic.mcp.models.command_execution import CommandExecutionRequest, CommandState

logger = logging.getLogger(__name__)


class ExecutionResult(NamedTuple):
    """Result of command execution."""
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: float


class CommandExecutor:
    """Service for executing Bablib CLI commands safely."""

    def __init__(self):
        """Initialize command executor."""
        pass

    async def execute(self, request: CommandExecutionRequest) -> ExecutionResult:
        """Execute a command request and return the result."""
        try:
            # Validate command first if not already validated
            if request.state == CommandState.CREATED:
                is_valid = await self.validate_command(request)
                if not is_valid:
                    return ExecutionResult(
                        exit_code=-1,
                        stdout="",
                        stderr="Command validation failed",
                        execution_time_ms=0.0
                    )

            # Advance state to executing
            request.advance_state(CommandState.EXECUTING)

            start_time = time.time()

            # Build the full command
            cmd_args = ["uv", "run", "bablib"] + request.to_command_string().split()[1:]

            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd()
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=request.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError(f"Command timed out after {request.timeout} seconds")

            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000

            # Decode output
            stdout_text = stdout.decode('utf-8') if stdout else ""
            stderr_text = stderr.decode('utf-8') if stderr else ""

            # Create result
            result = ExecutionResult(
                exit_code=process.returncode,
                stdout=stdout_text,
                stderr=stderr_text,
                execution_time_ms=execution_time_ms
            )

            # Advance state based on result
            if process.returncode == 0:
                request.advance_state(CommandState.COMPLETED)
            else:
                request.advance_state(CommandState.FAILED)

            return result

        except Exception as e:
            request.advance_state(CommandState.FAILED)
            logger.error(f"Command execution failed: {e}")

            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=0.0
            )

    async def validate_command(self, request: CommandExecutionRequest) -> bool:
        """Validate that a command is safe to execute."""
        try:
            # Basic validation checks
            if not request.is_safe_to_execute():
                return False

            # Additional environment-specific checks could go here
            # e.g., check if required services are running

            request.advance_state(CommandState.VALIDATED)
            return True

        except Exception as e:
            logger.error(f"Command validation failed: {e}")
            request.advance_state(CommandState.FAILED)
            return False

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command is in the allowed list."""
        allowed_commands = {"project", "crawl", "setup", "health", "upload"}
        return command in allowed_commands

    async def get_command_help(self, command: str) -> str:
        """Get help text for a command."""
        try:
            if not self.is_command_allowed(command):
                return f"Command '{command}' is not allowed"

            # Execute help command
            process = await asyncio.create_subprocess_exec(
                "uv", "run", "bablib", command, "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return stdout.decode('utf-8')
            else:
                return f"Help not available: {stderr.decode('utf-8')}"

        except Exception as e:
            return f"Error getting help: {str(e)}"