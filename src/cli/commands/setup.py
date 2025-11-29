"""Unified setup command for all setup operations."""

import logging

import click
from rich.console import Console
from rich.table import Table

from src.core.config import get_config
from src.logic.health.services.health_reporter import HealthReporter
from src.logic.setup.core.orchestrator import SetupOrchestrator
from src.logic.setup.core.router import CommandRouter

logger = logging.getLogger(__name__)
console = Console()


def display_global_settings():
    """Display global settings in a table format."""
    config = get_config()

    table = Table(title="[bold cyan]Global Settings[/bold cyan]", show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="yellow", width=25)
    table.add_column("Value", style="green", width=40)
    table.add_column("Description", style="dim", width=30)

    # Core settings
    table.add_row("Vector Store", str(config.vector_store_provider.value), "Vector database provider")
    table.add_row("Embedding Model", config.embedding_model, "AI model for embeddings")
    table.add_row("Data Directory", str(config.data_dir), "Local data storage path")
    table.add_row("Log Level", config.log_level, "Logging verbosity level")

    # Crawling settings
    table.add_row("Default Crawl Depth", str(config.crawl_depth), "Maximum link depth")
    table.add_row("Rate Limit", f"{config.rate_limit} req/s", "Request throttling")
    table.add_row("Chunk Size", str(config.chunk_size), "Text processing chunk size")
    table.add_row("Chunk Overlap", str(config.chunk_overlap), "Text chunk overlap")

    # Service URLs
    table.add_row("Qdrant URL", config.qdrant_url, "Vector database endpoint")
    table.add_row("Ollama URL", config.ollama_url, "Embedding service endpoint")
    table.add_row("MCP Port", str(config.mcp_port), "MCP server port")

    console.print(table)




@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output', default=False)
@click.option('--quiet', '-q', is_flag=True, help='Suppress non-error output', default=False)
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'table']), help='Output format', default='table')
@click.option('--init', '-i', is_flag=True, help='Launch setup wizard', default=False)
@click.option('--force', '-F', is_flag=True, help='Force operation without prompts', default=False)
@click.option('--dry-run', '-n', is_flag=True, help='Show what would be done without executing', default=False)
@click.option('--timeout', '-t', type=int, help='Operation timeout in seconds')
@click.option('--auto', '-a', is_flag=True, help='Auto-configure with defaults', default=False)
@click.option('--vector-store', '-V', type=click.Choice(['sqlite_vec', 'qdrant']), help='Vector store provider')
@click.option('--uninstall', '-u', is_flag=True, help='Uninstall Bablib', default=False)
@click.option('--reset', '-r', is_flag=True, help='Reset configuration', default=False)
@click.option('--preserve-data', '-k', is_flag=True, help='Preserve user data during reset', default=False)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Disable interactive prompts"
)
@click.option(
    "--backup",
    is_flag=True,
    help="Create backup before uninstalling (with --uninstall)"
)
@click.pass_context
def setup(
    ctx: click.Context,
    verbose: bool,
    quiet: bool,
    format: str,
    init: bool,
    force: bool,
    dry_run: bool,
    timeout: int | None,
    auto: bool,
    vector_store: str | None,
    uninstall: bool,
    reset: bool,
    preserve_data: bool,
    non_interactive: bool,
    backup: bool
):
    """Unified setup command for Bablib configuration.

    The one-stop command for all Bablib setup operations. Choose between
    interactive menu (no flags) or specific operations with flags.

    \b
    OPERATIONS:
      --init         Initialize configuration and vector store
      --uninstall    Remove Bablib completely from your system
      --reset        Reset to fresh state (keeps or removes data)
      (no flags)     Interactive menu with guided setup

    \b
    QUICK SETUPS:
      bablib setup                           # Interactive menu with help
      bablib setup --init --auto             # Quick setup with defaults
      bablib setup --init --vector-store sqlite_vec  # Choose vector store

    \b
    VECTOR STORE OPTIONS:
      sqlite_vec     Local SQLite with vector extension (recommended)
      qdrant         Scalable vector database (requires Docker)

    \b
    UNINSTALL & RESET:
      bablib setup --uninstall --force       # Uninstall without confirmation
      bablib setup --uninstall --backup      # Create backup first
      bablib setup --reset --preserve-data   # Reset but keep projects
      bablib setup --uninstall --dry-run     # Preview what would be removed

    \b
    FLAGS:
      --force            Skip confirmation prompts
      --auto             Use default values (with --init)
      --non-interactive  Disable all interactive prompts
      --backup           Create backup before destructive operations
      --dry-run          Preview changes without applying them
      --preserve-data    Keep user projects during reset/uninstall
    """

    # Initialize router and orchestrator
    router = CommandRouter()
    orchestrator = SetupOrchestrator()

    try:
        # Route to appropriate operation
        operation = router.route_operation(
            init=init,
            uninstall=uninstall,
            reset=reset,
            force=force,
            auto=auto,
            non_interactive=non_interactive,
            vector_store=vector_store,
            backup=backup,
            dry_run=dry_run,
            preserve_data=preserve_data
        )

        # Execute the operation
        if operation.type == "init":
            console.print("[cyan]Initializing Bablib...[/cyan]")
            try:
                result = orchestrator.initialize(**operation.options)
            except RuntimeError as e:
                # Check if it's the "already initialized" error
                if "already initialized" in str(e).lower():
                    console.print("[yellow]ℹ Bablib is already initialized.[/yellow]")
                    console.print("[dim]Use 'bablib setup --init --force' to reinitialize.[/dim]")
                    ctx.exit(0)  # Exit gracefully
                else:
                    # Re-raise other runtime errors
                    raise

        elif operation.type == "uninstall":
            console.print("[yellow]Preparing to uninstall Bablib...[/yellow]")
            result = orchestrator.uninstall(**operation.options)

        elif operation.type == "reset":
            console.print("[yellow]Resetting Bablib installation...[/yellow]")
            result = orchestrator.reset(**operation.options)

        elif operation.type == "menu":
            # Launch interactive menu
            console.print("[cyan]Welcome to Bablib Setup[/cyan]")
            result = orchestrator.run_interactive_menu()

        else:
            raise ValueError(f"Unknown operation type: {operation.type}")

        # Display result
        if result.status == "completed":
            console.print(f"[green]✓ {operation.type.title()} completed successfully[/green]")

            # Display settings and help tables after successful init
            if operation.type == "init":
                console.print("\n")
                display_global_settings()
                console.print("\n")
                health_reporter = HealthReporter()
                help_output = health_reporter.display_command_guide()
                console.print(help_output)

        elif result.status == "cancelled":
            console.print("[yellow]Operation cancelled[/yellow]")
        elif result.status == "dry_run":
            console.print("[blue]Dry run completed - no changes made[/blue]")
        else:
            console.print(f"[red]Operation failed: {result.error_message}[/red]")
            ctx.exit(1)

    except ValueError as e:
        # Flag validation error
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[dim]Run 'bablib setup --help' for usage information[/dim]")
        ctx.exit(1)

    except click.exceptions.Exit:
        # Allow clean exits from nested code
        raise

    except Exception as e:
        logger.exception("Setup command failed")
        console.print(f"[red]Setup failed: {e}[/red]")
        ctx.exit(1)
