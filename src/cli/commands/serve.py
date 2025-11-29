"""Serve command for Bablib CLI."""

import os

import click

# Optional uvloop for better performance
try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False


def get_app():
    """Get or create global app instance."""
    from src.cli.main import get_app as main_get_app
    return main_get_app()


@click.command(name="serve")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output', default=False)
@click.option('--quiet', '-q', is_flag=True, help='Suppress non-error output', default=False)
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'table']), help='Output format', default='table')
@click.option('--init', '-i', is_flag=True, help='Launch setup wizard', default=False)
@click.option('--force', '-F', is_flag=True, help='Force operation without prompts', default=False)
@click.option('--dry-run', '-n', is_flag=True, help='Show what would be done without executing', default=False)
@click.option('--timeout', '-t', type=int, help='Operation timeout in seconds')
@click.option('--host', '-H', type=str, help='Server host address')
@click.option('--port', '-o', type=int, help='Server port number')
@click.option('--admin', '-A', is_flag=True, help='Enable admin server', default=False)
@click.option('--foreground', '-g', is_flag=True, help='Run in foreground', default=False)
@click.option('--status', '-w', is_flag=True, help='Check server status', default=False)
@click.pass_context
def serve(ctx: click.Context, verbose: bool, quiet: bool, format: str, init: bool, force: bool, dry_run: bool, timeout: int, host: str, port: int, admin: bool, foreground: bool, status: bool):
    """Start the MCP server for AI assistant integration.

    The MCP (Model Context Protocol) server exposes your documentation
    to AI assistants like Claude, enabling context-aware responses.

    \b
    SERVER TYPES:
      bablib serve                   # Read-only server (port 9383, all interfaces)
      bablib serve --admin           # Admin server (port 9384, localhost only)

    \b
    SERVER MODES:
      bablib serve                   # Start in background (recommended)
      bablib serve --foreground      # Run in foreground (for debugging)
      bablib serve --status          # Check if server is running

    \b
    CONFIGURATION:
      --admin          Start admin server instead of read-only
      --host HOST      Server bind address (auto-detected by server type)
      --port PORT      Server port (auto-detected by server type)
      -f, --foreground Run in foreground instead of background
      -i, --init       Launch MCP setup wizard

    \b
    MCP INTEGRATION:
      READ-ONLY SERVER (default):
      - Project listing and search across documentation
      - Safe read-only access for AI assistants
      - Runs on port 9383, accessible from any interface

      ADMIN SERVER (--admin flag):
      - Full Bablib command execution capabilities
      - Project creation, removal, crawling operations
      - Runs on port 9384, localhost only for security

    \b
    EXAMPLES:
      bablib serve                   # Start read-only server (background)
      bablib serve --admin           # Start admin server (background)
      bablib serve -f                # Read-only server in foreground
      bablib serve --admin -f        # Admin server in foreground
      bablib serve --init            # Launch MCP setup wizard
      bablib serve --status          # Check server status
      bablib serve --port 8080       # Custom port (overrides default)

    \b
    CLIENT SETUP:
      Read-only server: http://localhost:9383
      Admin server: http://127.0.0.1:9384 (localhost only)
      Protocol: MCP (Model Context Protocol)

    \b
    SECURITY NOTES:
      - Admin server restricted to localhost (127.0.0.1) for security
      - Read-only server prevents any write operations
      - Use admin server only for trusted local AI assistants

    \b
    TROUBLESHOOTING:
      - Use --foreground to see real-time server logs
      - Check --status to verify server is responding
      - Ensure no other service is using the port
      - Run 'bablib health' to verify system components
    """
    import socket
    import asyncio

    from src.logic.mcp.models.server_type import McpServerType
    from src.logic.mcp.models.config import McpServerConfig
    from src.logic.mcp.core.orchestrator import ServerOrchestrator
    from src.logic.mcp.utils.port_manager import PortManager
    from src.logic.wizard.orchestrator import WizardOrchestrator

    app = get_app()

    # Launch MCP setup wizard if requested
    if init:
        try:
            app.console.print("[blue]Starting MCP setup wizard...[/blue]")

            # Run the MCP wizard to configure server settings
            wizard = WizardOrchestrator()

            async def run_mcp_wizard():
                """Run MCP setup wizard."""
                wizard_state = await wizard.start_wizard("mcp", "server")
                app.console.print("[blue]Configuring MCP server settings...[/blue]")

                # Simulate wizard steps for MCP configuration
                app.console.print("Step 1: Enable read-only server? [Y/n]: ", end="")
                enable_readonly = click.confirm("", default=True)

                if enable_readonly:
                    app.console.print("Step 2: Read-only server port [9383]: ", end="")
                    readonly_port = click.prompt("", default=9383, type=int)
                else:
                    readonly_port = None

                app.console.print("Step 3: Enable admin server? [y/N]: ", end="")
                enable_admin = click.confirm("", default=False)

                if enable_admin:
                    app.console.print("Step 4: Admin server port [9384]: ", end="")
                    admin_port = click.prompt("", default=9384, type=int)
                else:
                    admin_port = None

                app.console.print("Step 5: Auto-start with system? [y/N]: ", end="")
                auto_start = click.confirm("", default=False)

                # Show configuration summary
                app.console.print("\n[green]Configuration Summary:[/green]")
                if enable_readonly:
                    app.console.print(f"  Read-only server: Port {readonly_port}")
                if enable_admin:
                    app.console.print(f"  Admin server: Port {admin_port}")
                app.console.print(f"  Auto-start: {'Yes' if auto_start else 'No'}")

                if click.confirm("\nApply this configuration?", default=True):
                    app.console.print("[green]✓ MCP server configuration saved[/green]")

                    # Start the appropriate server based on wizard choices
                    if enable_admin and admin:
                        return McpServerType.ADMIN, admin_port or 9384
                    elif enable_readonly:
                        return McpServerType.READ_ONLY, readonly_port or 9383
                    else:
                        app.console.print("[yellow]No servers enabled. Use --admin or default read-only mode.[/yellow]")
                        return None, None
                else:
                    app.console.print("[yellow]Configuration cancelled. Using defaults.[/yellow]")
                    return None, None

            # Run wizard and get configuration
            server_type_result, port_result = asyncio.run(run_mcp_wizard())

            if server_type_result and port_result:
                # Update server type and port based on wizard results
                if server_type_result == McpServerType.ADMIN:
                    admin = True
                port = port_result

                app.console.print(f"[green]Starting {server_type_result.value} server on port {port}...[/green]")

        except Exception as e:
            app.console.print(f"[red]Wizard error: {e}[/red]")
            app.console.print("[dim]Continuing with default configuration...[/dim]")

    # Determine server type and configuration
    server_type = McpServerType.ADMIN if admin else McpServerType.READ_ONLY

    # Set host and port based on server type if not provided
    if host is None:
        host = server_type.default_host
    if port is None:
        port = server_type.default_port

    # Create server configuration
    try:
        server_config = McpServerConfig(
            server_type=server_type,
            host=host,
            port=port,
            enabled=True
        )
    except Exception as e:
        app.console.print(f"[red]✗[/red] Invalid configuration: {e}")
        raise click.ClickException(str(e))

    # Check server status if requested
    if status:
        try:
            # Try to connect to the server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                if result == 0:
                    app.console.print(f"[green]✓[/green] {server_type.value.title()} MCP server is running on {host}:{port}")

                    # Try to get server info via health endpoint
                    try:
                        import httpx
                        response = httpx.get(f"http://{host}:{port}/mcp/v1/health", timeout=2)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success'):
                                server_data = data.get('data', {})
                                app.console.print(f"  Server Type: {server_data.get('server_type', 'Unknown')}")
                                app.console.print(f"  Status: {server_data.get('status', 'Unknown')}")
                    except Exception:
                        pass
                else:
                    app.console.print(f"[yellow]⚠[/yellow] {server_type.value.title()} MCP server is not running on {host}:{port}")
                    cmd_hint = "bablib serve --admin" if admin else "bablib serve"
                    app.console.print(f"[dim]Start it with: {cmd_hint}[/dim]")
        except Exception as e:
            app.console.print(f"[red]✗[/red] Error checking server status: {e}")
        return

    # Initialize port manager and orchestrator
    port_manager = PortManager()
    orchestrator = ServerOrchestrator(port_manager)

    if foreground:
        # Run in foreground
        app.console.print(f"[green]Starting {server_type.value} MCP server on {host}:{port}...[/green]")
        app.console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        app.console.print("[cyan]Server endpoints:[/cyan]")
        app.console.print(f"  MCP API:  {server_config.url}/mcp/v1/")
        app.console.print(f"  Health:   {server_config.url}/mcp/v1/health")
        if server_type == McpServerType.ADMIN:
            app.console.print("[yellow]  ⚠ Admin server - localhost only for security[/yellow]")
        app.console.print("")

        async def run_server():
            """Run server asynchronously."""
            try:
                success = await orchestrator.start_single_server(server_config)
                if not success:
                    raise RuntimeError("Failed to start server")

                # Keep running until interrupted
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                app.console.print("\n[yellow]Server stopped[/yellow]")
            except Exception as e:
                app.console.print(f"[red]✗ Server error: {e}[/red]")
                raise
            finally:
                await orchestrator.stop_all_servers()

        try:
            if UVLOOP_AVAILABLE:
                uvloop.install()
            asyncio.run(run_server())
        except KeyboardInterrupt:
            pass
        except Exception as e:
            raise click.ClickException(str(e))
    else:
        # Check if server is already running
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                result = sock.connect_ex((host, port))
                if result == 0:
                    app.console.print(f"[yellow]⚠[/yellow] {server_type.value.title()} server already running on {host}:{port}")
                    cmd_hint = "bablib serve --admin --status" if admin else "bablib serve --status"
                    app.console.print(f"[dim]Use '{cmd_hint}' to check status[/dim]")
                    return
        except Exception:
            pass

        # Run in background
        app.console.print(f"[green]✅ Starting {server_type.value} MCP server on {host}:{port}[/green]")

        # Fork the process to run in background
        pid = os.fork()
        if pid == 0:
            # Child process - redirect stdout/stderr to suppress INFO messages
            with open(os.devnull, 'w') as devnull:
                os.dup2(devnull.fileno(), 1)  # stdout
                os.dup2(devnull.fileno(), 2)  # stderr

            async def run_background_server():
                """Run server in background."""
                try:
                    success = await orchestrator.start_single_server(server_config)
                    if success:
                        # Keep running until the process is killed
                        while True:
                            await asyncio.sleep(1)
                except Exception:
                    pass

            try:
                if UVLOOP_AVAILABLE:
                    uvloop.install()
                asyncio.run(run_background_server())
            except Exception:
                pass
        else:
            # Parent process - show status and helpful info
            app.console.print(f"[dim]Process ID: {pid}[/dim]")
            app.console.print("")
            app.console.print("[cyan]Server management:[/cyan]")
            app.console.print(f"  Stop server:   kill {pid}")
            status_cmd = "bablib serve --admin --status" if admin else "bablib serve --status"
            app.console.print(f"  Check status:  {status_cmd}")
            app.console.print("  View logs:     tail -f ~/.local/share/bablib/mcp_server.log")
            app.console.print("")
            app.console.print("[cyan]Connect from AI Assistant:[/cyan]")
            app.console.print(f"  Server URL: {server_config.url}")
            if server_type == McpServerType.ADMIN:
                app.console.print("  [yellow]⚠ Admin server - use only with trusted local assistants[/yellow]")
            app.console.print("  Add to your AI assistant's MCP settings for documentation access")
