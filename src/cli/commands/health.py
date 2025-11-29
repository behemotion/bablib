"""Health check command for Bablib CLI - Unified Implementation."""

import asyncio
import sys

import click
from rich.console import Console

# Optional uvloop for better performance
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False


def run_async(coro):
    """Run async coroutine in sync context."""
    if UVLOOP_AVAILABLE:
        try:
            uvloop.install()
        except Exception:
            pass

    return asyncio.run(coro)


@click.command(name="health")
@click.option("--system", "-s", is_flag=True, help="Check only system requirements")
@click.option("--services", "-e", is_flag=True, help="Check only external services")
@click.option("--config", "-c", is_flag=True, help="Check only configuration validity")
@click.option("--projects", "-p", is_flag=True, help="Check project-specific health")
@click.option("--format", "-f", "format_type", default="table",
              type=click.Choice(["table", "json", "yaml"], case_sensitive=False),
              help="Output format")
@click.option("--json", "-j", is_flag=True, help="Output in JSON format (shortcut for --format json)")
@click.option("--verbose", "-v", is_flag=True, help="Include detailed diagnostic information")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress indicators, show only results")
@click.option("--timeout", "-t", default=15, type=click.IntRange(1, 60),
              help="Maximum execution timeout in seconds")
@click.option("--parallel", "-P", default=4, type=click.IntRange(1, 8),
              help="Maximum parallel health checks")
@click.pass_context
def health(ctx: click.Context, system: bool, services: bool, config: bool, projects: bool,
           format_type: str, json: bool, verbose: bool, quiet: bool, timeout: int, parallel: int):
    """Check health status of Bablib components with comprehensive validation.

    Verify that your Bablib installation is working correctly by checking
    system requirements, external services, configuration, and projects.

    \b
    WHAT IS CHECKED:
      System       Python version, memory, disk space, permissions
      Services     Docker, Qdrant, Ollama, Git availability
      Config       Settings files, vector store configuration
      Projects     Individual project health and integrity

    \b
    CATEGORY OPTIONS:
      --system     System requirements only (Python, memory, disk)
      --services   External services only (Docker, Qdrant, Ollama, Git)
      --config     Configuration files only (settings, vector store)
      --projects   Project health only (requires existing projects)
      (default)    System + Services + Config (recommended)

    \b
    OUTPUT FORMATS:
      table        Human-readable table with status indicators (default)
      json         Machine-readable JSON for automation/scripts
      yaml         YAML format for configuration management tools

    \b
    PERFORMANCE OPTIONS:
      -v, --verbose       Include detailed diagnostic information
      -q, --quiet         Suppress progress indicators
      -t, --timeout N     Maximum check timeout (1-60 seconds, default: 15)
      -P, --parallel N    Parallel checks (1-8 workers, default: 4)

    \b
    EXAMPLES:
      bablib health                    # Complete health check (recommended)
      bablib health --system           # System requirements only
      bablib health --services         # External services only
      bablib health --format json     # JSON output for scripts
      bablib health --verbose          # Detailed diagnostic information
      bablib health --timeout 30      # Extended timeout for slow systems

    \b
    TROUBLESHOOTING:
      Run this command after installation or when experiencing issues.
      Use --verbose for detailed error information and suggested fixes.
    """
    async def _unified_health_check():
        try:
            # Import health orchestration components
            from src.logic.health.core.orchestrator import HealthOrchestrator
            from src.logic.health.core.router import HealthCommandRouter

            # Initialize components
            router = HealthCommandRouter()

            # Handle --json shortcut flag
            effective_format = "json" if json else format_type

            # Parse and validate flags
            try:
                categories, options = router.parse_flags(
                    system=system,
                    services=services,
                    config=config,
                    projects=projects,
                    format_type=effective_format,
                    verbose=verbose,
                    quiet=quiet,
                    timeout=timeout,
                    parallel=parallel
                )
            except ValueError as e:
                console = Console()
                console.print(f"[red]Error: {e}[/red]")
                console.print("Use [cyan]bablib health --help[/cyan] for usage information")
                sys.exit(4)  # Invalid arguments exit code

            # Initialize orchestrator with validated options
            orchestrator = HealthOrchestrator(
                timeout=options['timeout'],
                max_parallel=options['parallel']
            )

            # Show progress if not in quiet mode
            console = Console()
            if not options['suppress_progress']:
                category_names = [cat.display_name for cat in categories]
                console.print(f"🔍 Running health checks for: {', '.join(category_names)}")

            # Execute health checks
            try:
                report = await orchestrator.run_comprehensive_health_check(categories)
            except KeyboardInterrupt:
                console.print("[yellow]Health check interrupted by user[/yellow]")
                sys.exit(5)  # Interrupted exit code

            # Generate output title
            title = router.get_title_for_categories(categories)

            # Format and display results
            output = orchestrator.health_reporter.format_output(
                report=report,
                format_type=options['format'].value,
                detailed=options['show_detailed'],
                title=title
            )

            # Print output
            print(output.rstrip())  # Remove trailing newlines

            # Show resolution guidance if needed
            if router.should_show_resolution_guidance(options, report.has_issues):
                suggestions = orchestrator.health_reporter.get_resolution_suggestions(report)
                if suggestions and not options['quiet']:
                    console.print("\n[cyan]Resolution Guidance:[/cyan]")
                    for suggestion in suggestions[:3]:  # Limit to top 3 suggestions
                        console.print(f"  • {suggestion}")

            # Exit with appropriate code
            sys.exit(report.exit_code)

        except Exception as e:
            console = Console()
            if not quiet:
                console.print(f"[red]Health check failed: {e}[/red]")
                if verbose:
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")

            # Check for import errors (likely missing dependencies)
            if "No module named" in str(e):
                console.print("[yellow]Tip: Try running 'bablib setup' to fix installation issues[/yellow]")

            sys.exit(3)  # Unavailable exit code

    run_async(_unified_health_check())
