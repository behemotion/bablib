"""Main CLI entry point for Bablib - Simplified version with commands in separate modules."""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console

# Optional uvloop for better performance
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger, setup_logging
from src.logic.crawler.core.crawler import DocumentationCrawler
from src.services.database import DatabaseManager
from src.services.embeddings import EmbeddingService
from src.logic.rag.core.search_service import RAGSearchService
from src.services.vector_store import VectorStoreService
from src.version import __version__


class BablibApp:
    """Main Bablib application."""

    def __init__(self, config: BablibConfig | None = None):
        """Initialize Bablib application."""
        self.config = config or BablibConfig()
        self.console = Console()
        self.logger = None

        # Services
        self.db_manager: DatabaseManager | None = None
        self.vector_store: VectorStoreService | None = None
        self.embedding_service: EmbeddingService | None = None
        self.rag_service: RAGSearchService | None = None
        self.crawler: DocumentationCrawler | None = None

        self._initialized = False

    async def initialize(self, debug: bool = False) -> None:
        """Initialize all services."""
        if self._initialized:
            return

        try:
            # Setup logging with debug override
            if debug:
                self.config.debug = True
                self.config.log_level = "DEBUG"
            setup_logging(self.config)
            self.logger = get_component_logger("cli")

            # Initialize services
            self.db_manager = DatabaseManager(self.config)
            await self.db_manager.initialize()

            # Use factory to create appropriate vector store based on settings
            from src.services.vector_store_factory import VectorStoreFactory
            try:
                self.vector_store = VectorStoreFactory.create_vector_store(self.config)
                await self.vector_store.initialize()
            except Exception as e:
                # Get current provider and provide helpful suggestion
                current_provider = VectorStoreFactory.get_current_provider()
                suggestion = VectorStoreFactory.get_fallback_suggestion(current_provider)

                error_msg = f"Failed to initialize {current_provider.value} vector store: {e}\n\n{suggestion}"
                self.logger.error("Vector store initialization failed", extra={
                    "provider": current_provider.value,
                    "error": str(e)
                })
                raise RuntimeError(error_msg)

            self.embedding_service = EmbeddingService(self.config)
            await self.embedding_service.initialize()

            self.rag_service = RAGSearchService(
                self.vector_store,
                self.embedding_service,
                self.config
            )

            self.crawler = DocumentationCrawler(self.db_manager, self.config)
            await self.crawler.initialize()

            self._initialized = True
            self.logger.info("Bablib application initialized")

        except Exception as e:
            self.console.print(f"[red]Failed to initialize Bablib: {e}[/red]")
            if self.logger:
                self.logger.error("Initialization failed", extra={"error": str(e)})
            raise

    async def cleanup(self) -> None:
        """Clean up all services."""
        if self.crawler:
            await self.crawler.cleanup()
        if self.embedding_service:
            await self.embedding_service.cleanup()
        if self.vector_store:
            await self.vector_store.cleanup()
        if self.db_manager:
            await self.db_manager.cleanup()

        self._initialized = False
        if self.logger:
            self.logger.info("Bablib application cleaned up")


# Global app instance for CLI
app: BablibApp | None = None


def get_app() -> BablibApp:
    """Get or create global app instance."""
    global app
    if app is None:
        app = BablibApp()
    return app


def run_async(coro):
    """Run async coroutine in sync context."""
    if UVLOOP_AVAILABLE:
        try:
            uvloop.install()
        except Exception:
            pass

    return asyncio.run(coro)


def _is_first_time_installation() -> bool:
    """Check if this is a first-time installation."""
    try:
        from src.services.config import ConfigService
        config_service = ConfigService()

        # Check for existing installation context
        context = config_service.load_installation_context()
        if context:
            return False

        # Check for any existing configuration
        config_dir = config_service.config_dir
        if config_dir.exists():
            # Look for any configuration files
            config_files = list(config_dir.glob("*.json"))
            if config_files:
                return False

        return True
    except Exception:
        # If we can't determine, assume first time for safety
        return True


def _detect_uv_installation() -> bool:
    """Detect if this is running from a UV tool installation."""
    import os

    # Check for UV environment variables
    if "UV_TOOL_DIR" in os.environ or "UVX_ROOT" in os.environ:
        return True

    # Check if running from UV virtual environment
    current_executable = Path(sys.executable)
    if "uv" in str(current_executable).lower():
        return True

    # Check if bablib is in a UV-managed location
    try:
        import shutil
        bablib_path = shutil.which("bablib")
        if bablib_path:
            path_str = str(Path(bablib_path))
            if ".local" in path_str and "uv" in path_str.lower():
                return True
    except Exception:
        pass

    return False


def _should_run_auto_setup() -> bool:
    """Determine if auto-setup should run."""
    import os
    # Check if explicitly disabled
    if os.environ.get("BABLIB_SKIP_AUTO_SETUP", "").lower() in ["1", "true"]:
        return False

    return _is_first_time_installation() and _detect_uv_installation()


@click.group(invoke_without_command=True)
@click.version_option(__version__, "--version", "-v", help="Show version and exit")
@click.option("--config-file", type=click.Path(exists=True), help="Configuration file path")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.option("--json", is_flag=True, help="Output in JSON format")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.option("--no-progress", is_flag=True, help="Disable progress indicators")
@click.option("--skip-auto-setup", is_flag=True, help="Skip automatic setup for first-time installations")
@click.pass_context
def main(ctx: click.Context, config_file: str | None, debug: bool, quiet: bool,
         json: bool, no_color: bool, no_progress: bool, skip_auto_setup: bool):
    """Bablib - Local documentation crawler and search tool with RAG capabilities.

    Bablib crawls documentation websites, stores them locally, and provides
    semantic search through an MCP server for AI assistants like Claude.

    \b
    INSTALLATION:
      uv tool install git+https://github.com/behemotion/doc-bro

    \b
    QUICK START:
      bablib setup                                  # Interactive setup wizard
      bablib shelf create 'my docs'                 # Create shelf (collection)
      bablib box create 'python-docs' --type drag  # Create box (documentation unit)
      bablib fill 'python-docs' --source 'https://docs.python.org'  # Fill box with content
      bablib serve                                  # Start MCP server for AI assistants

    \b
    SHELF-BOX SYSTEM:
      bablib shelf create <name>                    # Create documentation shelf
      bablib shelf list                             # List all shelves
      bablib box create <name> --type <type>        # Create box (drag/rag/bag)
      bablib box list                               # List all boxes
      bablib fill <box> --source <url/path>        # Fill box with content
      bablib health                                 # Check system health

    \b
    VECTOR STORE OPTIONS:
      - SQLite-vec: Local, no dependencies, perfect for getting started
      - Qdrant: Scalable, production-ready, requires Docker

    \b
    AI ASSISTANT INTEGRATION:
      Once the MCP server is running (bablib serve), AI assistants like Claude
      can access your documentation for context-aware responses.
    """
    # Store context for commands
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["quiet"] = quiet
    ctx.obj["json"] = json
    ctx.obj["no_color"] = no_color
    ctx.obj["no_progress"] = no_progress

    # Initialize app with config
    global app
    config = BablibConfig()
    if config_file:
        # Load config from file if needed
        pass

    # Apply debug flag to config
    if debug:
        config.debug = True
        config.log_level = "DEBUG"

    app = BablibApp(config)

    # If no command specified, show help or run auto-setup
    if ctx.invoked_subcommand is None:
        console = Console()

        # Check for auto-setup on first installation
        if not skip_auto_setup and _should_run_auto_setup():
            console.print("🚀 [bold cyan]Welcome to Bablib![/bold cyan]")
            console.print("This appears to be your first time running Bablib.")
            console.print("Starting automatic setup...\n")

            async def run_auto_setup():
                from src.models.installation import InstallationRequest
                from src.services.installation_wizard import InstallationWizardService

                wizard_service = InstallationWizardService()
                request = InstallationRequest(
                    auto_mode=True,
                    force_reinstall=False
                )

                try:
                    result = await wizard_service.run_installation(request)
                    if result.success:
                        console.print("\n✅ [bold green]Setup completed successfully![/bold green]")
                        console.print("\n[cyan]Quick start with shelf-box system:[/cyan]")
                        console.print("  1. Create shelf:  [cyan]bablib shelf create 'my docs'[/cyan]")
                        console.print("  2. Create box:    [cyan]bablib box create 'python-docs' --type drag[/cyan]")
                        console.print("  3. Fill box:      [cyan]bablib fill 'python-docs' --source 'https://docs.python.org'[/cyan]")
                        console.print("  4. Start server:  [cyan]bablib serve[/cyan]")
                        console.print("\n[dim]For more options: bablib --help[/dim]")
                    else:
                        console.print(f"\n❌ Setup failed: {result.error}")
                        console.print("💡 Try running: [cyan]bablib setup[/cyan] for manual setup")
                except Exception as e:
                    console.print(f"\n❌ Setup error: {e}")
                    console.print("💡 Try running: [cyan]bablib setup[/cyan] for manual setup")

            run_async(run_auto_setup())
            ctx.exit(0)

        # Show concise help
        console.print(f"Bablib v{__version__} - Documentation Crawler & Search Tool\n")
        console.print("[cyan]Shelf-Box Commands:[/cyan]")
        console.print("  bablib shelf create <name>    Create documentation shelf")
        console.print("  bablib shelf list             List shelves")
        console.print("  bablib box create <name> --type <type>  Create box (drag/rag/bag)")
        console.print("  bablib fill <box> --source <url>        Fill box with content")
        console.print("\n[cyan]System Commands:[/cyan]")
        console.print("  bablib setup                  Interactive setup wizard")
        console.print("  bablib serve                  Start MCP server")
        console.print("  bablib health                 Check service health")
        console.print("  bablib --help                 Show all commands")
        ctx.exit(0)


# Import and register all commands
from src.cli.commands.health import health
from src.cli.commands.serve import serve
from src.cli.commands.setup import setup
from src.cli.commands.shelf import shelf
from src.cli.commands.box import box
from src.cli.commands.fill import fill

# Legacy commands removed - functionality moved to unified health command

# Initialize CLI interface components (for standardized progress displays)
try:
    from src.cli.interface.factories.progress_factory import ProgressFactory
    # Pre-warm the progress factory for better performance
    ProgressFactory()
except ImportError:
    # Interface components not available - CLI will still work without standardized progress
    pass

# Add commands to main group
main.add_command(shelf)
main.add_command(box)
main.add_command(fill)
main.add_command(serve)
main.add_command(health)
main.add_command(setup)

# CLI alias
cli = main

if __name__ == "__main__":
    main()
