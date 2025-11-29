"""Unit tests for CommandExecutor service."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import NamedTuple

from src.logic.mcp.services.command_executor import CommandExecutor, ExecutionResult
from src.logic.mcp.models.command_execution import (
    CommandExecutionRequest, AllowedCommand, CommandState
)


class MockProcess:
    """Mock subprocess process."""

    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        """Mock communicate method."""
        return self._stdout, self._stderr

    async def wait(self):
        """Mock wait method."""
        return self.returncode

    def kill(self):
        """Mock kill method."""
        pass


class TestCommandExecutor:
    """Test cases for CommandExecutor service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = CommandExecutor()

    @pytest.mark.asyncio
    async def test_execute_successful_command(self):
        """Test successful command execution."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[],
            options={}
        )

        mock_process = MockProcess(
            returncode=0,
            stdout=b"System healthy",
            stderr=b""
        )

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result = await self.executor.execute(request)

            # Verify execution
            assert result.exit_code == 0
            assert result.stdout == "System healthy"
            assert result.stderr == ""
            assert result.execution_time_ms > 0

            # Verify final state
            assert request.state == CommandState.COMPLETED

            # Verify correct command was called
            mock_exec.assert_called_once()
            args, kwargs = mock_exec.call_args
            assert args[0] == "uv"
            assert args[1] == "run"
            assert args[2] == "bablib"
            assert args[3] == "health"

    @pytest.mark.asyncio
    async def test_execute_failed_command(self):
        """Test command execution that fails."""
        request = CommandExecutionRequest(
            command=AllowedCommand.PROJECT,
            arguments=["--list"],
            options={}
        )

        mock_process = MockProcess(
            returncode=1,
            stdout=b"",
            stderr=b"Error: No projects found"
        )

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await self.executor.execute(request)

            # Verify execution
            assert result.exit_code == 1
            assert result.stdout == ""
            assert result.stderr == "Error: No projects found"
            assert result.execution_time_ms > 0

            # Verify final state
            assert request.state == CommandState.FAILED

    @pytest.mark.asyncio
    async def test_execute_command_with_arguments_and_options(self):
        """Test command execution with arguments and options."""
        request = CommandExecutionRequest(
            command=AllowedCommand.PROJECT,
            arguments=["test-project"],
            options={"description": "Test project", "type": "data"}
        )

        mock_process = MockProcess(
            returncode=0,
            stdout=b"Project created successfully",
            stderr=b""
        )

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result = await self.executor.execute(request)

            # Verify execution
            assert result.exit_code == 0
            assert result.stdout == "Project created successfully"

            # Verify command construction
            args, kwargs = mock_exec.call_args
            called_args = args
            assert "uv" in called_args
            assert "run" in called_args
            assert "bablib" in called_args
            assert "project" in called_args
            assert "test-project" in called_args

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self):
        """Test command execution timeout handling."""
        request = CommandExecutionRequest(
            command=AllowedCommand.CRAWL,
            arguments=["test-project"],
            timeout=1  # Very short timeout
        )

        # Mock a process that never completes
        mock_process = MockProcess()

        async def slow_communicate():
            await asyncio.sleep(2)  # Longer than timeout
            return b"", b""

        mock_process.communicate = slow_communicate

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await self.executor.execute(request)

            # Should handle timeout gracefully
            assert result.exit_code == -1
            assert "timed out" in result.stderr.lower()
            assert request.state == CommandState.FAILED

    @pytest.mark.asyncio
    async def test_execute_command_exception(self):
        """Test command execution exception handling."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[]
        )

        with patch('asyncio.create_subprocess_exec', side_effect=Exception("Process creation failed")):
            result = await self.executor.execute(request)

            # Should handle exception gracefully
            assert result.exit_code == -1
            assert result.stdout == ""
            assert "Process creation failed" in result.stderr
            assert request.state == CommandState.FAILED

    @pytest.mark.asyncio
    async def test_validate_command_success(self):
        """Test successful command validation."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[]
        )

        # Mock is_safe_to_execute at the class level
        with patch.object(CommandExecutionRequest, 'is_safe_to_execute', return_value=True):
            is_valid = await self.executor.validate_command(request)

            assert is_valid is True
            assert request.state == CommandState.VALIDATED

    @pytest.mark.asyncio
    async def test_validate_command_unsafe(self):
        """Test validation failure for unsafe command."""
        request = CommandExecutionRequest(
            command=AllowedCommand.PROJECT,
            arguments=["--create", "test"]
        )

        # Mock is_safe_to_execute to return False
        with patch.object(CommandExecutionRequest, 'is_safe_to_execute', return_value=False):
            is_valid = await self.executor.validate_command(request)

            assert is_valid is False
            # State should not be advanced for invalid commands

    @pytest.mark.asyncio
    async def test_validate_command_exception(self):
        """Test validation exception handling."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[]
        )

        # Mock is_safe_to_execute to raise exception
        with patch.object(CommandExecutionRequest, 'is_safe_to_execute', side_effect=Exception("Validation error")):
            is_valid = await self.executor.validate_command(request)

            assert is_valid is False
            assert request.state == CommandState.FAILED

    def test_is_command_allowed_valid_commands(self):
        """Test is_command_allowed for valid commands."""
        allowed_commands = ["project", "crawl", "setup", "health", "upload"]

        for command in allowed_commands:
            assert self.executor.is_command_allowed(command) is True

    def test_is_command_allowed_invalid_commands(self):
        """Test is_command_allowed for invalid commands."""
        disallowed_commands = ["serve", "rm", "delete", "sudo", "unknown"]

        for command in disallowed_commands:
            assert self.executor.is_command_allowed(command) is False

    @pytest.mark.asyncio
    async def test_get_command_help_success(self):
        """Test getting help for a valid command."""
        mock_process = MockProcess(
            returncode=0,
            stdout=b"Usage: bablib health [OPTIONS]\n\nHealth check commands...",
            stderr=b""
        )

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            help_text = await self.executor.get_command_help("health")

            assert "Usage: bablib health" in help_text
            assert "Health check commands" in help_text

            # Verify correct help command was called
            mock_exec.assert_called_once()
            args, kwargs = mock_exec.call_args
            assert args[0] == "uv"
            assert args[1] == "run"
            assert args[2] == "bablib"
            assert args[3] == "health"
            assert args[4] == "--help"

    @pytest.mark.asyncio
    async def test_get_command_help_disallowed_command(self):
        """Test getting help for a disallowed command."""
        help_text = await self.executor.get_command_help("serve")

        assert "Command 'serve' is not allowed" in help_text

    @pytest.mark.asyncio
    async def test_get_command_help_command_failure(self):
        """Test getting help when help command fails."""
        mock_process = MockProcess(
            returncode=1,
            stdout=b"",
            stderr=b"Command not found"
        )

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            help_text = await self.executor.get_command_help("health")

            assert "Help not available" in help_text
            assert "Command not found" in help_text

    @pytest.mark.asyncio
    async def test_get_command_help_exception(self):
        """Test getting help when an exception occurs."""
        with patch('asyncio.create_subprocess_exec', side_effect=Exception("Process error")):
            help_text = await self.executor.get_command_help("health")

            assert "Error getting help" in help_text
            assert "Process error" in help_text

    @pytest.mark.asyncio
    async def test_execution_result_namedtuple(self):
        """Test ExecutionResult NamedTuple properties."""
        result = ExecutionResult(
            exit_code=0,
            stdout="Output text",
            stderr="Error text",
            execution_time_ms=123.45
        )

        assert result.exit_code == 0
        assert result.stdout == "Output text"
        assert result.stderr == "Error text"
        assert result.execution_time_ms == 123.45

        # Test it's a proper NamedTuple
        assert hasattr(result, '_fields')
        assert result._fields == ('exit_code', 'stdout', 'stderr', 'execution_time_ms')

    @pytest.mark.asyncio
    async def test_state_progression_during_execution(self):
        """Test that command state progresses correctly during execution."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[]
        )

        # Initial state
        assert request.state == CommandState.CREATED

        mock_process = MockProcess(returncode=0, stdout=b"OK", stderr=b"")

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await self.executor.execute(request)

            # Verify final state after execution
            assert request.state == CommandState.COMPLETED

    @pytest.mark.asyncio
    async def test_command_string_construction(self):
        """Test that command strings are constructed correctly."""
        request = CommandExecutionRequest(
            command=AllowedCommand.PROJECT,
            arguments=["test-project", "--create"],
            options={"type": "data", "description": "Test description"}
        )

        mock_process = MockProcess(returncode=0)

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            await self.executor.execute(request)

            # Check that command was constructed correctly
            args, kwargs = mock_exec.call_args
            called_args = list(args)

            assert "uv" in called_args
            assert "run" in called_args
            assert "bablib" in called_args
            assert "project" in called_args
            assert "test-project" in called_args
            assert "--create" in called_args

    @pytest.mark.asyncio
    async def test_stdout_stderr_decoding(self):
        """Test proper decoding of stdout and stderr."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[]
        )

        # Test with UTF-8 encoded output
        mock_process = MockProcess(
            returncode=0,
            stdout="Output with émojis 🚀".encode('utf-8'),
            stderr="Error with spëcial chars".encode('utf-8')
        )

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await self.executor.execute(request)

            assert result.stdout == "Output with émojis 🚀"
            assert result.stderr == "Error with spëcial chars"

    @pytest.mark.asyncio
    async def test_working_directory_setting(self):
        """Test that commands are executed in the correct working directory."""
        request = CommandExecutionRequest(
            command=AllowedCommand.HEALTH,
            arguments=[]
        )

        mock_process = MockProcess(returncode=0)

        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            with patch('pathlib.Path.cwd', return_value="/test/path"):
                await self.executor.execute(request)

                # Verify cwd parameter was set correctly
                args, kwargs = mock_exec.call_args
                assert kwargs.get('cwd') == "/test/path"