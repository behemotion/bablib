"""CLI commands for shelf management in the Shelf-Box Rhyme System."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.core.lib_logger import get_component_logger
from src.lib.paths import get_bablib_data_dir
from src.logic.wizard.orchestrator import WizardOrchestrator
from src.models.shelf import ShelfExistsError, ShelfNotFoundError, ShelfValidationError
from src.services.context_service import ContextService
from src.services.database import DatabaseError
from src.services.shelf_service import ShelfService

logger = get_component_logger("shelf_cli")
console = Console()


@click.group()
def shelf():
    """Manage documentation shelves (collections)."""
    pass


@shelf.command()
@click.argument('name', required=False)
@click.option('--init', '-i', is_flag=True, help='Launch setup wizard')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--create', '-c', is_flag=True, help='Force creation mode')
def inspect(name: str | None = None, init: bool = False, verbose: bool = False, create: bool = False):
    """Display shelf information or prompt creation if not found."""

    async def _inspect():
        context_service = ContextService()
        shelf_service = None
        try:
            if not name:
                # List all shelves
                shelf_service = ShelfService()
                shelves = await shelf_service.list_shelves()

                if not shelves:
                    console.print("[yellow]No shelves found. Create your first shelf![/yellow]")
                    if click.confirm("Create a shelf now?"):
                        name_input = click.prompt("Shelf name")
                        await _create_shelf_with_wizard(name_input, init)
                    return

                # Display shelf table
                table = Table()
                table.add_column("Name", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Boxes", style="blue")
                table.add_column("Last Modified", style="dim")

                for shelf in shelves:
                    status = "configured" if shelf.is_default else "active"
                    table.add_row(shelf.name, status, "?", "recently")

                console.print(table)
                return

            # Check specific shelf context
            context = await context_service.check_shelf_exists(name)

            if context.entity_exists:
                # Shelf exists - display information
                console.print(f"[cyan]Shelf '{name}'[/cyan]")

                if verbose:
                    console.print(f"  Status: {'Empty' if context.is_empty else 'Has content'}")
                    console.print(f"  Configuration: {'Configured' if context.configuration_state.is_configured else 'Needs setup'}")
                    if context.content_summary:
                        console.print(f"  Content: {context.content_summary}")
                    console.print(f"  Last modified: {context.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")

                if context.is_empty:
                    console.print(f"[yellow]Shelf '{name}' is empty.[/yellow]")
                    if click.confirm("Fill boxes now?"):
                        console.print("Launching box creation workflow...")
                        # This would integrate with box creation

                if not context.configuration_state.is_configured and init:
                    console.print("Launching setup wizard...")
                    await _run_shelf_wizard(name)

            else:
                # Shelf doesn't exist - offer to create
                console.print(f"[red]Shelf '{name}' not found.[/red]")

                if create or click.confirm(f"Create shelf '{name}'?"):
                    await _create_shelf_with_wizard(name, init)
                else:
                    console.print("Available actions:")
                    console.print("  - List existing shelves: [cyan]bablib shelf[/cyan]")
                    console.print("  - Create shelf: [cyan]bablib shelf create <name>[/cyan]")

        except Exception as e:
            logger.error(f"Error inspecting shelf: {e}")
            console.print(f"[red]Error: {e}[/red]")
        finally:
            # Ensure database connections are closed
            if shelf_service:
                await shelf_service.db.cleanup()

    asyncio.run(_inspect())


async def _create_shelf_with_wizard(name: str, run_wizard: bool = False):
    """Create shelf with optional wizard."""
    try:
        shelf_service = ShelfService()

        shelf = await shelf_service.create_shelf(name=name)
        console.print(f"[green]Created shelf '{name}'[/green]")

        if run_wizard or click.confirm("Launch setup wizard?"):
            await _run_shelf_wizard(name)

    except ShelfExistsError:
        console.print(f"[red]Shelf '{name}' already exists[/red]")
    except Exception as e:
        logger.error(f"Error creating shelf: {e}")
        console.print(f"[red]Error creating shelf: {e}[/red]")


async def _run_shelf_wizard(name: str):
    """Run shelf setup wizard."""
    try:
        wizard = WizardOrchestrator()
        wizard_state = await wizard.start_wizard("shelf", name)

        console.print(f"[blue]Starting shelf setup wizard for '{name}'[/blue]")
        console.print("Follow the prompts to configure your shelf...")

        # This would integrate with the full wizard flow
        console.print(f"[green]Wizard completed for shelf '{name}'[/green]")

    except Exception as e:
        logger.error(f"Error running shelf wizard: {e}")
        console.print(f"[red]Wizard error: {e}[/red]")


@shelf.command()
@click.argument('name', type=str)
@click.option('--shelf-description', '-d', type=str, help='Shelf description')
@click.option('--set-current', '-s', is_flag=True, help='Set as current shelf')
@click.option('--init', '-i', is_flag=True, help='Launch setup wizard after creation')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output', default=False)
@click.option('--force', '-F', is_flag=True, help='Force operation without prompts', default=False)
def create(name: str, shelf_description: str | None = None, set_current: bool = False, init: bool = False, verbose: bool = False, force: bool = False):
    """Create a new shelf with optional wizard."""

    async def _create():
        shelf_service = ShelfService()
        try:
            shelf = await shelf_service.create_shelf(
                name=name,
                description=shelf_description,
                set_current=set_current
            )

            console.print(f"[green]Created shelf '{name}'[/green]")

            if set_current:
                console.print("[blue]Set as current shelf[/blue]")

            # Show created shelf info
            console.print(f"  Auto-created: {name}_box (rag)")

            if init:
                console.print("Launching setup wizard...")
                await _run_shelf_wizard(name)
            console.print("  Boxes: 1")

        except ShelfExistsError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except ShelfValidationError as e:
            console.print(f"[red]Invalid name: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to create shelf: {e}[/red]")
            raise click.Abort()
        finally:
            # Ensure database connections are closed
            await shelf_service.db.cleanup()

    asyncio.run(_create())


@shelf.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--current-only', is_flag=True, help='Show only current shelf')
@click.option('--limit', '-l', type=int, default=10, help='Maximum shelves to display')
def list(verbose: bool = False, current_only: bool = False, limit: int = 10):
    """List all shelves."""

    async def _list():
        shelf_service = ShelfService()
        try:
            if current_only:
                current_shelf = await shelf_service.get_current_shelf()
                if current_shelf:
                    shelves = [current_shelf]
                else:
                    console.print("[yellow]No current shelf set[/yellow]")
                    return
            else:
                shelves = await shelf_service.list_shelves()

            if not shelves:
                console.print("[yellow]No shelves found[/yellow]")
                return

            # Apply limit
            if len(shelves) > limit:
                shelves = shelves[:limit]
                console.print(f"[dim]Showing first {limit} shelves[/dim]")

            # Create table
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Name", style="cyan")
            table.add_column("Boxes", justify="center")
            table.add_column("Current", justify="center")
            table.add_column("Created", style="dim")

            if verbose:
                table.add_column("ID", style="dim")
                table.add_column("Default", justify="center")

            # Get current shelf for marking
            current_shelf = await shelf_service.get_current_shelf()
            current_shelf_id = current_shelf.id if current_shelf else None

            for shelf in shelves:
                # Format current marker
                is_current = shelf.id == current_shelf_id
                current_marker = "→" if is_current else ""

                # Format created date
                created_date = shelf.created_at.strftime("%Y-%m-%d")

                row = [
                    shelf.name,
                    str(shelf.box_count),
                    current_marker,
                    created_date
                ]

                if verbose:
                    row.extend([
                        shelf.id[:12] + "...",
                        "✓" if shelf.is_default else ""
                    ])

                table.add_row(*row)

            console.print(table)

        except Exception as e:
            console.print(f"[red]Failed to list shelves: {e}[/red]")
            raise click.Abort()
        finally:
            # Ensure database connections are closed
            await shelf_service.db.cleanup()

    asyncio.run(_list())


@shelf.command()
@click.argument('name', type=str, required=False)
def current(name: str | None = None):
    """Get or set current shelf."""

    async def _current():
        shelf_service = ShelfService()
        try:
            if name:
                # Set current shelf
                shelf = await shelf_service.set_current_shelf(name)
                console.print(f"[green]Set current shelf to '{name}'[/green]")
            else:
                # Get current shelf
                current_shelf = await shelf_service.get_current_shelf()
                if current_shelf:
                    console.print(f"Current shelf: [cyan]{current_shelf.name}[/cyan]")
                else:
                    console.print("[yellow]No current shelf set[/yellow]")

        except ShelfNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to get/set current shelf: {e}[/red]")
            raise click.Abort()
        finally:
            # Ensure database connections are closed
            await shelf_service.db.cleanup()

    asyncio.run(_current())


@shelf.command()
@click.argument('old_name', type=str)
@click.argument('new_name', type=str)
def rename(old_name: str, new_name: str):
    """Rename a shelf."""

    async def _rename():
        shelf_service = ShelfService()
        try:
            shelf = await shelf_service.rename_shelf(old_name, new_name)
            console.print(f"[green]Renamed shelf '{old_name}' to '{new_name}'[/green]")

        except ShelfNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except ShelfExistsError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except ShelfValidationError as e:
            console.print(f"[red]Invalid name: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to rename shelf: {e}[/red]")
            raise click.Abort()
        finally:
            # Ensure database connections are closed
            await shelf_service.db.cleanup()

    asyncio.run(_rename())


async def _create_shelf_backup(shelf_service: ShelfService, shelf) -> Path:
    """
    Create a JSON backup of shelf data before deletion.

    Args:
        shelf_service: ShelfService instance
        shelf: Shelf model to backup

    Returns:
        Path to the created backup file
    """
    # Create backup directory
    backup_dir = get_bablib_data_dir() / "backups" / "shelves"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"shelf_{shelf.name}_{timestamp}.json"

    # Get associated boxes using shelf_service's database connection
    boxes = await shelf_service.db.list_boxes(shelf_id=shelf.id)

    # Build backup data
    backup_data = {
        "backup_version": "1.0",
        "backup_timestamp": datetime.now().isoformat(),
        "shelf": {
            "id": shelf.id,
            "name": shelf.name,
            "description": getattr(shelf, 'description', None),
            "is_default": shelf.is_default,
            "is_deletable": shelf.is_deletable,
            "created_at": shelf.created_at.isoformat() if shelf.created_at else None,
            "updated_at": shelf.updated_at.isoformat() if shelf.updated_at else None,
            "box_count": shelf.box_count,
        },
        "boxes": [
            {
                "id": box.get('id'),
                "name": box.get('name'),
                "type": box.get('type'),
                "description": box.get('description'),
                "url": box.get('url'),
                "created_at": box.get('created_at'),
            }
            for box in boxes
        ]
    }

    # Write backup file
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Created shelf backup: {backup_file}")
    return backup_file


@shelf.command()
@click.argument('name', type=str)
@click.option('--force', '-F', is_flag=True, help='Skip confirmation')
@click.option('--no-backup', is_flag=True, help="Don't create backup")
def delete(name: str, force: bool = False, no_backup: bool = False):
    """Delete a shelf."""

    async def _delete():
        shelf_service = ShelfService()
        try:
            # Get shelf info first
            shelf = await shelf_service.get_shelf_by_name(name)
            if not shelf:
                console.print(f"[red]Shelf '{name}' not found[/red]")
                raise click.Abort()

            # Check protection
            if shelf.is_default:
                console.print("[red]Cannot delete: Default shelf is protected[/red]")
                raise click.Abort()

            # Confirmation
            if not force:
                box_warning = f" (contains {shelf.box_count} boxes)" if shelf.box_count > 0 else ""
                confirm = click.confirm(
                    f"Delete shelf '{name}'{box_warning}?",
                    default=False
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            # Create backup if requested
            if not no_backup:
                try:
                    backup_path = await _create_shelf_backup(shelf_service, shelf)
                    console.print(f"[dim]Backup created: {backup_path}[/dim]")
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
                    console.print(f"[yellow]Warning: Could not create backup: {e}[/yellow]")

            # Delete shelf
            await shelf_service.delete_shelf(name)
            console.print(f"[green]Deleted shelf '{name}'[/green]")

        except DatabaseError as e:
            if "protected" in str(e) or "default" in str(e):
                console.print(f"[red]Cannot delete: {e}[/red]")
            else:
                console.print(f"[red]Failed to delete shelf: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to delete shelf: {e}[/red]")
            raise click.Abort()
        finally:
            # Ensure database connections are closed
            await shelf_service.db.cleanup()

    asyncio.run(_delete())
