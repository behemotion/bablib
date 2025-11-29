"""Health reporter service for generating health reports."""

import json

import yaml
from rich.console import Console
from rich.table import Table

from ..models.health_check import HealthCheck
from ..models.health_report import HealthReport
from ..models.status import HealthStatus


class HealthReporter:
    """Service for generating and formatting health reports."""

    def __init__(self):
        """Initialize health reporter."""
        self.console = Console()

    def generate_report(self, checks: list[HealthCheck], execution_time: float,
                       timeout_occurred: bool = False) -> HealthReport:
        """Generate a complete health report from health checks."""
        if not checks:
            raise ValueError("Cannot generate health report without health checks")

        return HealthReport.create_from_checks(
            checks=checks,
            execution_time=execution_time,
            timeout_occurred=timeout_occurred
        )

    def format_table_output(self, report: HealthReport, title: str | None = None) -> str:
        """Format health report as a Rich table."""
        console = Console(file=None, force_terminal=False)

        # Create table
        table_title = title or "Bablib Health Status"
        table = Table(title=table_title, show_header=True, header_style="bold cyan")
        table.add_column("Component", style="cyan", no_wrap=True, width=25)
        table.add_column("Status", style="green", width=15)
        table.add_column("Details", style="dim")

        # Add rows for each health check
        for check in report.checks:
            # Format status with symbol and text
            status_symbol = check.status.symbol
            status_text = check.status.value
            status_display = f"{status_symbol} {status_text}"

            # Use appropriate color based on status
            if check.status == HealthStatus.HEALTHY:
                status_style = "green"
            elif check.status == HealthStatus.WARNING:
                status_style = "yellow"
            elif check.status == HealthStatus.ERROR:
                status_style = "red"
            else:  # UNAVAILABLE
                status_style = "dim"

            # Combine message and details
            details = check.message
            if check.details and check.details != check.message:
                details = f"{check.message} - {check.details}"

            table.add_row(
                check.name,
                f"[{status_style}]{status_display}[/{status_style}]",
                details
            )

        # Create output string
        with console.capture() as capture:
            console.print(table)
            console.print()  # Empty line

            # Overall status
            overall_symbol = report.overall_status.symbol
            overall_text = report.overall_status.value

            if report.overall_status == HealthStatus.HEALTHY:
                console.print(f"{overall_symbol} [bold green]Overall Status: {overall_text}[/bold green]")
            elif report.overall_status == HealthStatus.WARNING:
                console.print(f"{overall_symbol} [bold yellow]Overall Status: {overall_text}[/bold yellow]")
            elif report.overall_status == HealthStatus.ERROR:
                console.print(f"{overall_symbol} [bold red]Overall Status: {overall_text}[/bold red]")
            else:
                console.print(f"{overall_symbol} [bold dim]Overall Status: {overall_text}[/bold dim]")

            # Summary statistics
            summary = report.summary
            console.print(f"({summary.healthy_count}/{summary.total_checks} checks passed)")

            # Execution time (show appropriate precision)
            exec_time = report.total_execution_time
            if exec_time < 0.01:
                console.print(f"Execution Time: {exec_time * 1000:.1f} ms")
            elif exec_time < 1.0:
                console.print(f"Execution Time: {exec_time:.2f} seconds")
            else:
                console.print(f"Execution Time: {exec_time:.1f} seconds")

            # Timeout warning if applicable
            if report.timeout_occurred:
                console.print("[yellow]⚠️ Some checks timed out[/yellow]")

        return capture.get()

    def format_json_output(self, report: HealthReport) -> str:
        """Format health report as JSON."""
        return json.dumps(report.to_dict(), indent=2)

    def format_yaml_output(self, report: HealthReport) -> str:
        """Format health report as YAML."""
        return yaml.dump(report.to_dict(), default_flow_style=False, indent=2)

    def format_detailed_output(self, report: HealthReport) -> str:
        """Format health report with detailed information including resolution guidance."""
        console = Console(file=None, force_terminal=False)

        with console.capture() as capture:
            # Header
            console.print("[bold cyan]Bablib Health Report[/bold cyan]")
            console.print(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print()

            # Group checks by category
            checks_by_category = {}
            for check in report.checks:
                category = check.category
                if category not in checks_by_category:
                    checks_by_category[category] = []
                checks_by_category[category].append(check)

            # Display each category
            for category, category_checks in checks_by_category.items():
                console.print(f"[bold]{category.display_name}[/bold]")
                console.print(f"[dim]{category.description}[/dim]")
                console.print()

                for check in category_checks:
                    # Status with symbol
                    status_symbol = check.status.symbol
                    status_text = check.status.value

                    console.print(f"  {status_symbol} [bold]{check.name}[/bold]: {check.message}")

                    if check.details:
                        console.print(f"     [dim]Details: {check.details}[/dim]")

                    if check.resolution:
                        console.print(f"     [yellow]Resolution: {check.resolution}[/yellow]")

                    # Individual check execution time (show appropriate precision)
                    check_time = check.execution_time
                    if check_time < 0.01:
                        console.print(f"     [dim]Execution time: {check_time * 1000:.1f}ms[/dim]")
                    else:
                        console.print(f"     [dim]Execution time: {check_time:.2f}s[/dim]")
                    console.print()

            # Overall summary
            console.print("[bold]Summary[/bold]")
            console.print(f"Overall Status: {report.overall_status.symbol} {report.overall_status.value}")
            console.print(f"Total Checks: {report.summary.total_checks}")
            console.print(f"Healthy: {report.summary.healthy_count}")
            console.print(f"Warnings: {report.summary.warning_count}")
            console.print(f"Errors: {report.summary.error_count}")
            console.print(f"Unavailable: {report.summary.unavailable_count}")
            console.print(f"Success Rate: {report.summary.success_rate:.1f}%")

            # Total execution time (show appropriate precision)
            exec_time = report.total_execution_time
            if exec_time < 0.01:
                console.print(f"Total Execution Time: {exec_time * 1000:.1f}ms")
            elif exec_time < 1.0:
                console.print(f"Total Execution Time: {exec_time:.2f}s")
            else:
                console.print(f"Total Execution Time: {exec_time:.1f}s")

            if report.timeout_occurred:
                console.print("[yellow]⚠️ Some checks timed out during execution[/yellow]")

        return capture.get()

    def format_output(self, report: HealthReport, format_type: str = "table",
                     detailed: bool = False, title: str | None = None) -> str:
        """Format health report based on specified format type."""
        if format_type.lower() == "json":
            return self.format_json_output(report)
        elif format_type.lower() == "yaml":
            return self.format_yaml_output(report)
        elif format_type.lower() == "table":
            if detailed:
                return self.format_detailed_output(report)
            else:
                return self.format_table_output(report, title)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def get_exit_code(self, report: HealthReport) -> int:
        """Get appropriate CLI exit code for the health report."""
        return report.exit_code

    def get_resolution_suggestions(self, report: HealthReport) -> list[str]:
        """Get all resolution suggestions from health checks with issues."""
        suggestions = []

        for check in report.checks:
            if check.has_issues and check.resolution:
                suggestions.append(f"{check.name}: {check.resolution}")

        return suggestions

    def has_critical_issues(self, report: HealthReport) -> bool:
        """Check if the report contains critical issues that prevent operation."""
        critical_checks = [
            "system.python_version",
            "config.global_settings"
        ]

        for check in report.checks:
            if (check.id in critical_checks and
                check.status in [HealthStatus.ERROR, HealthStatus.UNAVAILABLE]):
                return True

        return False

    def display_command_guide(self) -> str:
        """Display quick start guide with common Bablib commands.

        Returns:
            Formatted table string with command guide
        """
        from rich.console import Console
        from rich.table import Table

        console = Console(file=None, force_terminal=False)

        table = Table(title="[bold cyan]Quick Start Guide[/bold cyan]", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="yellow", width=35)
        table.add_column("Description", style="green", width=45)
        table.add_column("Example", style="dim", width=25)

        # Core commands
        table.add_row("bablib shelf create <name>", "Create a documentation shelf", "bablib shelf create 'my docs'")
        table.add_row("bablib box create <name> --type <type>", "Create a documentation box", "bablib box create 'python-docs' --type drag")
        table.add_row("bablib fill <box> --source <url>", "Fill box with content", "bablib fill 'python-docs' --source 'https://docs.python.org'")
        table.add_row("bablib shelf list", "List all shelves", "bablib shelf list --verbose")
        table.add_row("bablib box list", "List all boxes", "bablib box list --type drag")
        table.add_row("bablib serve", "Start MCP server", "bablib serve --port 9382")

        # Setup commands
        table.add_row("bablib setup --init", "Initialize Bablib", "bablib setup --init --auto")
        table.add_row("bablib setup --reset", "Reset installation", "bablib setup --reset")
        table.add_row("bablib health", "Check system health", "bablib health")

        # Advanced usage
        table.add_row("bablib box delete <name>", "Remove a box", "bablib box delete 'python-docs'")
        table.add_row("bablib shelf delete <name>", "Remove a shelf", "bablib shelf delete 'my docs'")

        with console.capture() as capture:
            console.print(table)

        return capture.get()
