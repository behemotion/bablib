"""Admin MCP service for command execution."""

import logging
from typing import Dict, Any

from src.logic.mcp.models.response import McpResponse
from src.logic.mcp.models.command_execution import CommandExecutionRequest
from src.logic.mcp.services.command_executor import CommandExecutor

logger = logging.getLogger(__name__)


class AdminMcpService:
    """Service providing admin MCP operations for command execution."""

    def __init__(self, command_executor: CommandExecutor):
        """Initialize with command executor."""
        self.command_executor = command_executor

    async def execute_command(self, request: CommandExecutionRequest) -> McpResponse:
        """Execute a Bablib CLI command."""
        try:
            # Validate the command is safe to execute
            if not request.is_safe_to_execute():
                # Provide specific error messages for blocked operations
                command_str = request.to_command_string().lower()
                if "uninstall" in command_str or "reset" in command_str:
                    return McpResponse.error_response(
                        error="Uninstall and reset operations are not allowed via MCP admin server for security reasons"
                    )
                elif request.command == "project" and "--remove" in request.arguments and "--all" in request.arguments:
                    return McpResponse.error_response(
                        error="Removing all projects is not allowed via MCP admin server for security reasons"
                    )
                else:
                    return McpResponse.error_response(
                        error="Command rejected for security reasons"
                    )

            # Execute command through executor
            result = await self.command_executor.execute(request)

            return McpResponse.success_response(
                data={
                    "command": request.to_command_string(),
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time_ms": result.execution_time_ms
                }
            )

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return McpResponse.error_response(
                error=f"Command execution failed: {str(e)}"
            )

    async def project_create(
        self,
        name: str,
        project_type: str,
        description: str = None,
        settings: Dict[str, Any] = None
    ) -> McpResponse:
        """Create a new project via command execution."""
        try:
            # Build command execution request
            arguments = ["--create", name, "--type", project_type]
            if description:
                arguments.extend(["--description", description])

            options = {}
            if settings:
                # Convert settings dict to CLI options
                for key, value in settings.items():
                    options[key] = value

            request = CommandExecutionRequest(
                command="project",
                arguments=arguments,
                options=options
            )

            # Execute through command executor
            result = await self.command_executor.execute(request)

            if result.exit_code == 0:
                return McpResponse.success_response(
                    data={
                        "operation": "create",
                        "project_name": name,
                        "result": result.stdout
                    }
                )
            else:
                return McpResponse.error_response(
                    error=f"Project creation failed: {result.stderr}"
                )

        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return McpResponse.error_response(
                error=f"Project creation failed: {str(e)}"
            )

    async def project_remove(
        self,
        name: str,
        confirm: bool = False,
        backup: bool = False
    ) -> McpResponse:
        """Remove a project via command execution."""
        try:
            arguments = ["--remove", name]
            options = {}

            if confirm:
                options["confirm"] = True
            if backup:
                options["backup"] = True

            request = CommandExecutionRequest(
                command="project",
                arguments=arguments,
                options=options
            )

            result = await self.command_executor.execute(request)

            if result.exit_code == 0:
                return McpResponse.success_response(
                    data={
                        "operation": "remove",
                        "project_name": name,
                        "result": result.stdout
                    }
                )
            else:
                return McpResponse.error_response(
                    error=f"Project removal failed: {result.stderr}"
                )

        except Exception as e:
            logger.error(f"Error removing project: {e}")
            return McpResponse.error_response(
                error=f"Project removal failed: {str(e)}"
            )

    async def crawl_project(
        self,
        project_name: str,
        url: str = None,
        max_pages: int = None,
        depth: int = None,
        rate_limit: float = None
    ) -> McpResponse:
        """Start project crawling via command execution."""
        try:
            arguments = [project_name]
            options = {}

            if url:
                options["url"] = url
            if max_pages:
                options["max-pages"] = max_pages
            if depth:
                options["depth"] = depth
            if rate_limit:
                options["rate-limit"] = rate_limit

            request = CommandExecutionRequest(
                command="crawl",
                arguments=arguments,
                options=options,
                timeout=300  # Longer timeout for crawling
            )

            result = await self.command_executor.execute(request)

            # Parse crawl result to extract metrics
            pages_crawled = 0
            errors_encountered = 0
            duration_seconds = result.execution_time_ms / 1000.0

            # Simple parsing of stdout for metrics (would be more sophisticated in real implementation)
            if "pages crawled" in result.stdout:
                # Extract metrics from output
                pass

            status = "completed" if result.exit_code == 0 else "failed"

            return McpResponse.success_response(
                data={
                    "project_name": project_name,
                    "pages_crawled": pages_crawled,
                    "errors_encountered": errors_encountered,
                    "duration_seconds": duration_seconds,
                    "status": status
                }
            )

        except Exception as e:
            logger.error(f"Error crawling project: {e}")
            return McpResponse.error_response(
                error=f"Project crawling failed: {str(e)}"
            )