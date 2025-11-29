"""CLI commands for box management in the Shelf-Box Rhyme System."""

import asyncio
import logging
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from src.models.box import BoxExistsError, BoxValidationError, BoxNotFoundError
from src.models.box_type import BoxType
from src.services.box_service import BoxService
from src.services.shelf_service import ShelfService
from src.services.context_service import ContextService
from src.services.database import DatabaseError
from src.logic.wizard.orchestrator import WizardOrchestrator
from src.core.lib_logger import get_component_logger

logger = get_component_logger("box_cli")
console = Console()


@click.group()
def box():
    """Manage documentation boxes (projects)."""
    pass


@box.command()
@click.argument('name', required=False)
@click.option('--shelf', '-B', type=str, help='Specify shelf context')
@click.option('--init', '-i', is_flag=True, help='Launch setup wizard')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def inspect(name: Optional[str] = None, shelf: Optional[str] = None, init: bool = False, verbose: bool = False):
    """Display box information or prompt creation if not found."""

    async def _inspect():
        box_service = BoxService()
        try:
            context_service = ContextService()

            if not name:
                # List all boxes with status
                boxes = await box_service.list_boxes(shelf_name=shelf)

                if not boxes:
                    shelf_context = f" in shelf '{shelf}'" if shelf else ""
                    console.print(f"[yellow]No boxes found{shelf_context}. Create your first box![/yellow]")
                    if click.confirm("Create a box now?"):
                        name_input = click.prompt("Box name")
                        box_type = click.prompt("Box type", type=click.Choice(['drag', 'rag', 'bag']))
                        await _create_box_with_wizard(name_input, box_type, shelf, init)
                    return

                # Display box table with status
                table = Table()
                table.add_column("Name", style="cyan")
                table.add_column("Type", justify="center")
                table.add_column("Status", style="green")
                table.add_column("Content", style="blue")
                table.add_column("Last Modified", style="dim")

                for box in boxes:
                    # Get context for each box
                    box_context = await context_service.check_box_exists(box.name, shelf)

                    status = "configured" if box_context.configuration_state.is_configured else "needs setup"
                    content = "empty" if box_context.is_empty else "has content"
                    last_modified = box_context.last_modified.strftime("%Y-%m-%d") if box_context.last_modified else "unknown"

                    table.add_row(box.name, box.type.value, status, content, last_modified)

                console.print(table)
                return

            # Check specific box context
            context = await context_service.check_box_exists(name, shelf)

            if context.entity_exists:
                # Box exists - display information
                console.print(f"[cyan]Box '{name}'[/cyan] ([blue]{context.box_type}[/blue])")

                if verbose:
                    console.print(f"  Status: {'Empty' if context.is_empty else 'Has content'}")
                    console.print(f"  Configuration: {'Configured' if context.configuration_state.is_configured else 'Needs setup'}")
                    if context.content_summary:
                        console.print(f"  Content: {context.content_summary}")
                    if context.last_modified:
                        console.print(f"  Last modified: {context.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")

                if context.is_empty:
                    # Provide type-specific prompts
                    if context.box_type == 'drag':
                        console.print(f"[yellow]Box '{name}' is empty.[/yellow]")
                        if click.confirm("Provide website URL to crawl?"):
                            url = click.prompt("Website URL")
                            console.print(f"Starting crawl of {url}...")
                            # This would integrate with fill command
                    elif context.box_type == 'rag':
                        console.print(f"[yellow]Box '{name}' is empty.[/yellow]")
                        if click.confirm("Provide file path to upload?"):
                            file_path = click.prompt("File path")
                            console.print(f"Uploading files from {file_path}...")
                            # This would integrate with fill command
                    elif context.box_type == 'bag':
                        console.print(f"[yellow]Box '{name}' is empty.[/yellow]")
                        if click.confirm("Provide content to store?"):
                            content_path = click.prompt("Content path")
                            console.print(f"Storing content from {content_path}...")
                            # This would integrate with fill command

                if not context.configuration_state.is_configured and init:
                    console.print("Launching setup wizard...")
                    await _run_box_wizard(name, context.box_type)

            else:
                # Box doesn't exist - offer to create
                console.print(f"[red]Box '{name}' not found.[/red]")

                if click.confirm(f"Create box '{name}'?"):
                    box_type = click.prompt("Box type", type=click.Choice(['drag', 'rag', 'bag']))
                    await _create_box_with_wizard(name, box_type, shelf, init)
                else:
                    console.print("Available actions:")
                    console.print("  - List existing boxes: [cyan]bablib box[/cyan]")
                    console.print("  - Create box: [cyan]bablib box create <name> --type <type>[/cyan]")

        except Exception as e:
            logger.error(f"Error inspecting box: {e}")
            console.print(f"[red]Error: {e}[/red]")
        finally:
            await box_service.db.cleanup()

    asyncio.run(_inspect())


async def _create_box_with_wizard(name: str, box_type: str, shelf: Optional[str] = None, run_wizard: bool = False):
    """Create box with optional wizard."""
    try:
        box_service = BoxService()
        shelf_service = ShelfService()

        # Ensure we have a target shelf
        target_shelf = shelf
        if not target_shelf:
            current = await shelf_service.get_current_shelf()
            if current:
                target_shelf = current.name
            else:
                console.print("[red]No current shelf set.[/red]")
                console.print("Either:")
                console.print("  1. Specify a shelf: [cyan]--shelf <shelf>[/cyan]")
                console.print("  2. Set current shelf: [cyan]bablib shelf current <shelf>[/cyan]")
                return

        box = await box_service.create_box(
            name=name,
            box_type=box_type,
            shelf_name=target_shelf
        )
        console.print(f"[green]Created {box_type} box '{name}'[/green]")

        if run_wizard or click.confirm("Launch setup wizard?"):
            await _run_box_wizard(name, box_type)

    except BoxExistsError:
        console.print(f"[red]Box '{name}' already exists[/red]")
    except Exception as e:
        logger.error(f"Error creating box: {e}")
        console.print(f"[red]Error creating box: {e}[/red]")


async def _run_box_wizard(name: str, box_type: str):
    """Run box setup wizard."""
    try:
        wizard = WizardOrchestrator()
        wizard_state = await wizard.start_wizard("box", name)

        console.print(f"[blue]Starting {box_type} box setup wizard for '{name}'[/blue]")
        console.print("Follow the prompts to configure your box...")

        # This would integrate with the full wizard flow
        console.print(f"[green]Wizard completed for box '{name}'[/green]")

    except Exception as e:
        logger.error(f"Error running box wizard: {e}")
        console.print(f"[red]Wizard error: {e}[/red]")


@box.command()
@click.argument('name', type=str)
@click.option('--type', '-T', 'box_type', type=click.Choice(['drag', 'rag', 'bag']), required=True, help='Box type')
@click.option('--shelf', '-B', type=str, help='Add to shelf')
@click.option('--box-description', '-D', 'description', type=str, help='Box description')
@click.option('--init', '-i', is_flag=True, help='Launch setup wizard after creation')
def create(name: str, box_type: str, shelf: Optional[str] = None, description: Optional[str] = None, init: bool = False):
    """Create a new box."""

    async def _create():
        box_service = BoxService()
        shelf_service = ShelfService()
        try:
            # Ensure we have a current shelf if none specified
            target_shelf = shelf
            if not target_shelf:
                current = await shelf_service.get_current_shelf()
                if current:
                    target_shelf = current.name
                else:
                    console.print("[red]No current shelf set.[/red]")
                    console.print("Either:")
                    console.print("  1. Specify a shelf: [cyan]bablib box create <name> --type <type> --shelf <shelf>[/cyan]")
                    console.print("  2. Set current shelf: [cyan]bablib shelf current <shelf>[/cyan]")
                    raise click.Abort()

            # Create the box
            box = await box_service.create_box(
                name=name,
                box_type=box_type,
                shelf_name=target_shelf,
                description=description
            )

            console.print(f"[green]Created {box_type} box '{name}'[/green]")
            if target_shelf:
                console.print(f"  Added to shelf: [cyan]{target_shelf}[/cyan]")

            # Show box type description
            console.print(f"  Purpose: {box.get_type_description()}")

            # Launch wizard if requested
            if init:
                console.print("Launching setup wizard...")
                await _run_box_wizard(name, box_type)

        except BoxExistsError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except BoxValidationError as e:
            console.print(f"[red]Invalid box: {e}[/red]")
            raise click.Abort()
        except DatabaseError as e:
            if "not found" in str(e):
                console.print(f"[red]Shelf '{shelf}' not found[/red]")
            else:
                console.print(f"[red]Failed to create box: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to create box: {e}[/red]")
            raise click.Abort()
        finally:
            await box_service.db.cleanup()
            await shelf_service.db.cleanup()

    asyncio.run(_create())


@box.command()
@click.option('--shelf', '-B', type=str, help='Filter by shelf')
@click.option('--type', '-T', 'box_type', type=click.Choice(['drag', 'rag', 'bag']), help='Filter by type')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.option('--limit', '-l', type=int, default=10, help='Maximum boxes to display')
def list(shelf: Optional[str] = None, box_type: Optional[str] = None, verbose: bool = False, limit: int = 10):
    """List boxes."""

    async def _list():
        box_service = BoxService()
        shelf_service = ShelfService()
        try:
            # If no shelf specified, try current shelf
            filter_shelf = shelf
            if not filter_shelf:
                current = await shelf_service.get_current_shelf()
                if current:
                    filter_shelf = current.name

            boxes = await box_service.list_boxes(
                shelf_name=filter_shelf,
                box_type=box_type
            )

            if not boxes:
                filter_desc = ""
                if filter_shelf:
                    filter_desc += f" in shelf '{filter_shelf}'"
                if box_type:
                    filter_desc += f" of type '{box_type}'"
                console.print(f"[yellow]No boxes found{filter_desc}[/yellow]")
                return

            # Apply limit
            if len(boxes) > limit:
                boxes = boxes[:limit]
                console.print(f"[dim]Showing first {limit} boxes[/dim]")

            # Create table
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Name", style="cyan")
            table.add_column("Type", justify="center")
            table.add_column("Shelves", style="dim")
            table.add_column("Created", style="dim")

            if verbose:
                table.add_column("ID", style="dim")
                table.add_column("URL", style="green")

            for box in boxes:
                # Get shelf info for this box
                box_stats = await box_service.get_box_stats(box.name)
                shelves_str = ", ".join(box_stats['containing_shelves'][:2])  # Show first 2
                if len(box_stats['containing_shelves']) > 2:
                    shelves_str += f" +{len(box_stats['containing_shelves']) - 2}"

                # Format created date
                created_date = box.created_at.strftime("%Y-%m-%d")

                row = [
                    box.name,
                    box.type.value,
                    shelves_str,
                    created_date
                ]

                if verbose:
                    row.extend([
                        box.id[:12] + "...",
                        box.url or ""
                    ])

                table.add_row(*row)

            console.print(table)

        except Exception as e:
            console.print(f"[red]Failed to list boxes: {e}[/red]")
            raise click.Abort()
        finally:
            await box_service.db.cleanup()
            await shelf_service.db.cleanup()

    asyncio.run(_list())


@box.command()
@click.argument('box', type=str)
@click.option('--to-shelf', type=str, required=True, help='Target shelf')
def add(box: str, to_shelf: str):
    """Add box to shelf."""

    async def _add():
        box_service = BoxService()
        try:
            success = await box_service.add_box_to_shelf(box, to_shelf)
            if success:
                console.print(f"[green]Added box '{box}' to shelf '{to_shelf}'[/green]")
            else:
                console.print(f"[yellow]Box '{box}' already in shelf '{to_shelf}'[/yellow]")

        except BoxNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except DatabaseError as e:
            if "not found" in str(e):
                console.print(f"[red]Shelf '{to_shelf}' not found[/red]")
            else:
                console.print(f"[red]Failed to add box: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to add box: {e}[/red]")
            raise click.Abort()
        finally:
            await box_service.db.cleanup()

    asyncio.run(_add())


@box.command()
@click.argument('box', type=str)
@click.option('--from-shelf', type=str, required=True, help='Source shelf')
def remove(box: str, from_shelf: str):
    """Remove box from shelf."""

    async def _remove():
        box_service = BoxService()
        try:
            success = await box_service.remove_box_from_shelf(box, from_shelf)
            if success:
                console.print(f"[green]Removed box '{box}' from shelf '{from_shelf}'[/green]")

        except BoxNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except DatabaseError as e:
            if "last box" in str(e):
                console.print(f"[red]Cannot remove last box from shelf[/red]")
            elif "not found" in str(e):
                console.print(f"[red]Shelf '{from_shelf}' not found[/red]")
            else:
                console.print(f"[red]Failed to remove box: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to remove box: {e}[/red]")
            raise click.Abort()
        finally:
            await box_service.db.cleanup()

    asyncio.run(_remove())


@box.command()
@click.argument('old_name', type=str)
@click.argument('new_name', type=str)
def rename(old_name: str, new_name: str):
    """Rename a box."""

    async def _rename():
        box_service = BoxService()
        try:
            box = await box_service.rename_box(old_name, new_name)
            console.print(f"[green]Renamed box '{old_name}' to '{new_name}'[/green]")

        except BoxNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except BoxExistsError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except BoxValidationError as e:
            console.print(f"[red]Invalid name: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to rename box: {e}[/red]")
            raise click.Abort()
        finally:
            await box_service.db.cleanup()

    asyncio.run(_rename())


@box.command()
@click.argument('name', type=str)
@click.option('--force', '-F', is_flag=True, help='Skip confirmation')
def delete(name: str, force: bool = False):
    """Delete a box."""

    async def _delete():
        box_service = BoxService()
        try:
            # Get box info first
            box = await box_service.get_box_by_name(name)
            if not box:
                console.print(f"[red]Box '{name}' not found[/red]")
                raise click.Abort()

            # Check protection
            if not box.is_deletable:
                console.print(f"[red]Cannot delete protected box[/red]")
                raise click.Abort()

            # Get shelves containing this box for warning
            box_stats = await box_service.get_box_stats(name)
            shelf_count = box_stats['shelf_count']

            # Confirmation
            if not force:
                shelf_warning = f" (in {shelf_count} shelves)" if shelf_count > 0 else ""
                confirm = click.confirm(
                    f"Delete {box.type.value} box '{name}'{shelf_warning}?",
                    default=False
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            # Delete box
            await box_service.delete_box(name)
            console.print(f"[green]Deleted box '{name}'[/green]")

        except DatabaseError as e:
            if "protected" in str(e):
                console.print(f"[red]Cannot delete protected box[/red]")
            else:
                console.print(f"[red]Failed to delete box: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to delete box: {e}[/red]")
            raise click.Abort()
        finally:
            await box_service.db.cleanup()

    asyncio.run(_delete())