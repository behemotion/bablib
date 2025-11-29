"""Health orchestrator core service integrating all validators."""

import asyncio
import time

from ..models.category import HealthCategory
from ..models.health_check import HealthCheck
from ..models.health_report import HealthReport
from ..models.status import HealthStatus
from ..services.config_validator import ConfigurationValidator
from ..services.health_reporter import HealthReporter
from ..services.system_validator import SystemValidator


class HealthOrchestrator:
    """Main health coordinator integrating all validators and service detection."""

    def __init__(self, timeout: float = 15.0, max_parallel: int = 4):
        """Initialize health orchestrator.

        Args:
            timeout: Maximum execution timeout in seconds
            max_parallel: Maximum parallel health checks
        """
        self.timeout = timeout
        self.max_parallel = max_parallel
        self.semaphore = asyncio.Semaphore(max_parallel)

        # Initialize services
        self.system_validator = SystemValidator()
        self.config_validator = ConfigurationValidator()
        self.health_reporter = HealthReporter()

    async def run_comprehensive_health_check(self,
                                           categories: set[HealthCategory] | None = None) -> HealthReport:
        """Run comprehensive health check across all or specified categories.

        Args:
            categories: Set of categories to check, None for all categories

        Returns:
            Complete health report
        """
        start_time = time.time()
        timeout_occurred = False

        try:
            # Determine which categories to check
            check_categories = categories or {
                HealthCategory.SYSTEM,
                HealthCategory.SERVICES,
                HealthCategory.CONFIGURATION
            }

            # Execute health checks with timeout
            all_checks = await asyncio.wait_for(
                self._execute_health_checks(check_categories),
                timeout=self.timeout
            )

            execution_time = time.time() - start_time

        except TimeoutError:
            execution_time = self.timeout
            timeout_occurred = True

            # Get partial results that completed before timeout
            all_checks = await self._get_partial_results(check_categories)

        # Generate and return health report
        return self.health_reporter.generate_report(
            checks=all_checks,
            execution_time=execution_time,
            timeout_occurred=timeout_occurred
        )

    async def run_system_health_check(self) -> HealthReport:
        """Run system-only health check."""
        return await self.run_comprehensive_health_check(
            categories={HealthCategory.SYSTEM}
        )

    async def run_services_health_check(self) -> HealthReport:
        """Run services-only health check."""
        return await self.run_comprehensive_health_check(
            categories={HealthCategory.SERVICES}
        )

    async def run_configuration_health_check(self) -> HealthReport:
        """Run configuration-only health check."""
        return await self.run_comprehensive_health_check(
            categories={HealthCategory.CONFIGURATION}
        )

    async def run_projects_health_check(self) -> HealthReport:
        """Run projects-only health check."""
        return await self.run_comprehensive_health_check(
            categories={HealthCategory.PROJECTS}
        )

    async def _execute_health_checks(self, categories: set[HealthCategory]) -> list[HealthCheck]:
        """Execute health checks for specified categories."""
        all_checks = []

        # Collect all check tasks
        check_tasks = []

        if HealthCategory.SYSTEM in categories:
            check_tasks.extend(await self._get_system_check_tasks())

        if HealthCategory.SERVICES in categories:
            check_tasks.extend(await self._get_services_check_tasks())

        if HealthCategory.CONFIGURATION in categories:
            check_tasks.extend(await self._get_configuration_check_tasks())

        if HealthCategory.PROJECTS in categories:
            check_tasks.extend(await self._get_projects_check_tasks())

        # Execute all checks with semaphore control
        if check_tasks:
            results = await asyncio.gather(*check_tasks, return_exceptions=True)

            # Process results and handle exceptions
            for result in results:
                if isinstance(result, HealthCheck):
                    all_checks.append(result)
                elif isinstance(result, Exception):
                    # Create error health check for failed tasks
                    error_check = HealthCheck(
                        id="orchestrator.execution_error",
                        category=HealthCategory.SYSTEM,
                        name="Health Check Execution Error",
                        status=HealthStatus.ERROR,
                        message="Health check task failed",
                        details=str(result),
                        resolution="Check system resources and try again",
                        execution_time=0.0
                    )
                    all_checks.append(error_check)

        return all_checks

    async def _get_system_check_tasks(self) -> list[asyncio.Task]:
        """Get system validation tasks."""
        return [
            asyncio.create_task(self._run_with_semaphore(self.system_validator.validate_python_version())),
            asyncio.create_task(self._run_with_semaphore(self.system_validator.validate_memory_requirements())),
            asyncio.create_task(self._run_with_semaphore(self.system_validator.validate_disk_space())),
            asyncio.create_task(self._run_with_semaphore(self.system_validator.validate_uv_installation())),
        ]

    async def _get_services_check_tasks(self) -> list[asyncio.Task]:
        """Get service validation tasks using existing ServiceDetector."""
        return [
            asyncio.create_task(self._run_with_semaphore(self._check_service_docker())),
            asyncio.create_task(self._run_with_semaphore(self._check_service_qdrant())),
            asyncio.create_task(self._run_with_semaphore(self._check_service_ollama())),
            asyncio.create_task(self._run_with_semaphore(self._check_service_git())),
            asyncio.create_task(self._run_with_semaphore(self._check_mcp_read_only_server())),
            asyncio.create_task(self._run_with_semaphore(self._check_mcp_admin_server())),
        ]

    async def _get_configuration_check_tasks(self) -> list[asyncio.Task]:
        """Get configuration validation tasks."""
        return [
            asyncio.create_task(self._run_with_semaphore(self.config_validator.validate_global_settings())),
            asyncio.create_task(self._run_with_semaphore(self.config_validator.validate_project_configurations())),
            asyncio.create_task(self._run_with_semaphore(self.config_validator.validate_vector_store_config())),
        ]

    async def _get_projects_check_tasks(self) -> list[asyncio.Task]:
        """Get project-specific validation tasks."""
        # Projects health checks would be implemented based on actual project structure
        # For now, return a placeholder check
        return [
            asyncio.create_task(self._run_with_semaphore(self._check_projects_placeholder()))
        ]

    async def _run_with_semaphore(self, coro):
        """Run coroutine with semaphore control."""
        async with self.semaphore:
            return await coro

    async def _check_service_docker(self) -> HealthCheck:
        """Check Docker service using existing ServiceDetector."""
        execution_start = time.time()

        try:
            # Import and use existing ServiceDetector
            from src.logic.setup.services.detector import ServiceDetector
            detector = ServiceDetector()

            docker_info = await detector.check_docker()

            if docker_info.get("status") == "available":
                status = HealthStatus.HEALTHY
                message = f"Docker {docker_info.get('version', 'unknown')} running"
                details = "Docker service available"
                resolution = None
            else:
                status = HealthStatus.WARNING  # Docker is optional
                message = "Docker not available"
                details = docker_info.get("error", "Docker service not running")
                resolution = "Install Docker for Qdrant support: https://docs.docker.com/get-docker/"

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="services.docker",
                category=HealthCategory.SERVICES,
                name="Docker Service",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="services.docker",
                category=HealthCategory.SERVICES,
                name="Docker Service",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check Docker service",
                details=str(e),
                resolution="Check Docker installation and service status",
                execution_time=execution_time
            )

    async def _check_service_qdrant(self) -> HealthCheck:
        """Check Qdrant service using existing ServiceDetector."""
        execution_start = time.time()

        try:
            from src.logic.setup.services.detector import ServiceDetector
            detector = ServiceDetector()

            qdrant_info = await detector.check_qdrant()

            if qdrant_info.get("status") == "available":
                status = HealthStatus.HEALTHY
                message = f"Qdrant {qdrant_info.get('version', 'unknown')} running"
                details = f"Qdrant available at {qdrant_info.get('url', 'http://localhost:6333')}"
                resolution = None
            else:
                status = HealthStatus.WARNING  # Qdrant is optional
                message = "Qdrant not available"
                details = qdrant_info.get("error", "Qdrant service not running")
                resolution = "Start Qdrant: docker run -d -p 6333:6333 qdrant/qdrant"

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="services.qdrant",
                category=HealthCategory.SERVICES,
                name="Qdrant Database",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="services.qdrant",
                category=HealthCategory.SERVICES,
                name="Qdrant Database",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check Qdrant service",
                details=str(e),
                resolution="Check Qdrant installation and connection",
                execution_time=execution_time
            )

    async def _check_service_ollama(self) -> HealthCheck:
        """Check Ollama service using existing ServiceDetector."""
        execution_start = time.time()

        try:
            from src.logic.setup.services.detector import ServiceDetector
            detector = ServiceDetector()

            ollama_info = await detector.check_ollama()

            if ollama_info.get("status") == "available":
                status = HealthStatus.HEALTHY
                message = f"Ollama {ollama_info.get('version', 'unknown')} running"
                details = f"Ollama available at {ollama_info.get('url', 'http://localhost:11434')}"
                resolution = None
            else:
                status = HealthStatus.WARNING  # Ollama is optional
                message = "Ollama not available"
                details = ollama_info.get("error", "Ollama service not running")
                resolution = "Install Ollama: https://ollama.ai/download"

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="services.ollama",
                category=HealthCategory.SERVICES,
                name="Ollama Service",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="services.ollama",
                category=HealthCategory.SERVICES,
                name="Ollama Service",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check Ollama service",
                details=str(e),
                resolution="Check Ollama installation and service status",
                execution_time=execution_time
            )

    async def _check_service_git(self) -> HealthCheck:
        """Check Git using existing ServiceDetector."""
        execution_start = time.time()

        try:
            from src.logic.setup.services.detector import ServiceDetector
            detector = ServiceDetector()

            git_info = await detector.check_git()

            if git_info.get("status") == "available":
                status = HealthStatus.HEALTHY
                message = f"Git {git_info.get('version', 'unknown')} available"
                details = f"Git version: {git_info.get('version', 'unknown')}"
                resolution = None
            else:
                status = HealthStatus.ERROR  # Git is required
                message = "Git not available"
                details = git_info.get("error", "Git not found in PATH")
                resolution = "Install Git: https://git-scm.com/downloads"

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="services.git",
                category=HealthCategory.SERVICES,
                name="Git",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="services.git",
                category=HealthCategory.SERVICES,
                name="Git",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check Git",
                details=str(e),
                resolution="Check Git installation",
                execution_time=execution_time
            )

    async def _check_projects_placeholder(self) -> HealthCheck:
        """Placeholder for project-specific health checks."""
        execution_start = time.time()

        try:
            # Check if projects directory exists and count projects
            import os
            from pathlib import Path

            data_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'bablib'
            projects_dir = data_dir / 'projects'

            if projects_dir.exists():
                project_count = len([d for d in projects_dir.iterdir() if d.is_dir()])
                status = HealthStatus.HEALTHY
                message = f"Found {project_count} projects"
                details = f"Projects directory: {projects_dir}"
                resolution = None
            else:
                status = HealthStatus.HEALTHY  # No projects is OK
                message = "No projects found"
                details = "Projects directory does not exist (normal for new installation)"
                resolution = None

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="projects.overview",
                category=HealthCategory.PROJECTS,
                name="Project Overview",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="projects.overview",
                category=HealthCategory.PROJECTS,
                name="Project Overview",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check projects",
                details=str(e),
                resolution="Check data directory permissions",
                execution_time=execution_time
            )

    async def _check_mcp_read_only_server(self) -> HealthCheck:
        """Check MCP read-only server status."""
        execution_start = time.time()

        try:
            import socket
            import httpx
            from src.logic.mcp.models.server_type import McpServerType

            server_type = McpServerType.READ_ONLY
            host = server_type.default_host
            port = server_type.default_port

            # Check if port is open
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                connection_result = sock.connect_ex((host, port))

            if connection_result == 0:
                # Server is running, try to get health info
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        response = await client.get(f"http://{host}:{port}/mcp/v1/health")
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success'):
                                server_data = data.get('data', {})
                                status = HealthStatus.HEALTHY
                                message = f"Read-only MCP server running on {host}:{port}"
                                details = f"Server status: {server_data.get('status', 'healthy')}"
                                resolution = None
                            else:
                                status = HealthStatus.WARNING
                                message = f"Read-only MCP server responding but unhealthy"
                                details = f"Health endpoint returned: {data}"
                                resolution = "Check server logs or restart server"
                        else:
                            status = HealthStatus.WARNING
                            message = f"Read-only MCP server running but health check failed"
                            details = f"HTTP {response.status_code} from health endpoint"
                            resolution = "Check server configuration or restart server"
                except Exception as e:
                    status = HealthStatus.WARNING
                    message = f"Read-only MCP server running but unreachable"
                    details = f"Port {port} open but health check failed: {e}"
                    resolution = "Check if server is properly configured"
            else:
                status = HealthStatus.UNAVAILABLE
                message = f"Read-only MCP server not running"
                details = f"No service listening on {host}:{port}"
                resolution = "Start server with: bablib serve"

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="services.mcp_read_only",
                category=HealthCategory.SERVICES,
                name="MCP Read-Only Server",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="services.mcp_read_only",
                category=HealthCategory.SERVICES,
                name="MCP Read-Only Server",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check read-only MCP server",
                details=str(e),
                resolution="Check system connectivity and try again",
                execution_time=execution_time
            )

    async def _check_mcp_admin_server(self) -> HealthCheck:
        """Check MCP admin server status."""
        execution_start = time.time()

        try:
            import socket
            import httpx
            from src.logic.mcp.models.server_type import McpServerType

            server_type = McpServerType.ADMIN
            host = server_type.default_host  # Should be 127.0.0.1
            port = server_type.default_port

            # Check if port is open
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                connection_result = sock.connect_ex((host, port))

            if connection_result == 0:
                # Server is running, try to get health info
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        response = await client.get(f"http://{host}:{port}/mcp/v1/health")
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success'):
                                server_data = data.get('data', {})
                                security_data = server_data.get('security_status', {})
                                localhost_only = security_data.get('localhost_only', True)

                                status = HealthStatus.HEALTHY
                                message = f"Admin MCP server running on {host}:{port}"
                                details = f"Server status: {server_data.get('status', 'healthy')}, Localhost only: {localhost_only}"
                                resolution = None
                            else:
                                status = HealthStatus.WARNING
                                message = f"Admin MCP server responding but unhealthy"
                                details = f"Health endpoint returned: {data}"
                                resolution = "Check server logs or restart admin server"
                        else:
                            status = HealthStatus.WARNING
                            message = f"Admin MCP server running but health check failed"
                            details = f"HTTP {response.status_code} from health endpoint"
                            resolution = "Check server configuration or restart admin server"
                except Exception as e:
                    status = HealthStatus.WARNING
                    message = f"Admin MCP server running but unreachable"
                    details = f"Port {port} open but health check failed: {e}"
                    resolution = "Check if admin server is properly configured"
            else:
                status = HealthStatus.UNAVAILABLE
                message = f"Admin MCP server not running"
                details = f"No service listening on {host}:{port}"
                resolution = "Start admin server with: bablib serve --admin"

            execution_time = time.time() - execution_start

            return HealthCheck(
                id="services.mcp_admin",
                category=HealthCategory.SERVICES,
                name="MCP Admin Server",
                status=status,
                message=message,
                details=details,
                resolution=resolution,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - execution_start
            return HealthCheck(
                id="services.mcp_admin",
                category=HealthCategory.SERVICES,
                name="MCP Admin Server",
                status=HealthStatus.UNAVAILABLE,
                message="Failed to check admin MCP server",
                details=str(e),
                resolution="Check system connectivity and try again",
                execution_time=execution_time
            )

    async def _get_partial_results(self, categories: set[HealthCategory]) -> list[HealthCheck]:
        """Get partial results when timeout occurs."""
        # In case of timeout, return minimal health checks indicating timeout
        timeout_checks = []

        for category in categories:
            timeout_checks.append(HealthCheck(
                id=f"{category.value.lower()}.timeout",
                category=category,
                name=f"{category.display_name} (Timeout)",
                status=HealthStatus.UNAVAILABLE,
                message=f"{category.display_name} checks timed out",
                details=f"Health checks for {category.display_name} exceeded {self.timeout}s timeout",
                resolution="Try running with longer timeout: --timeout 30",
                execution_time=self.timeout
            ))

        return timeout_checks
