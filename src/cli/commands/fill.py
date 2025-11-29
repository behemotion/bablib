"""CLI command for unified fill operation in the Shelf-Box Rhyme System."""

import asyncio
import logging
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.models.box import BoxNotFoundError
from src.services.fill_service import FillService
from src.services.box_service import BoxService
from src.services.shelf_service import ShelfService
from src.services.context_service import ContextService
from src.services.database import DatabaseError
from src.core.lib_logger import get_component_logger

logger = get_component_logger("fill_cli")
console = Console()


@click.command()
@click.argument('box', type=str)
@click.option('--source', '-S', type=str, required=True, help='Source URL or path')
@click.option('--shelf', type=str, help='Shelf context (uses current if not specified)')
# Drag-specific options (website crawling)
@click.option('--max-pages', '-m', type=int, help='Maximum pages to crawl (drag boxes)')
@click.option('--rate-limit', '-R', type=float, help='Requests per second (drag boxes)')
@click.option('--depth', '-e', type=int, help='Crawl depth (drag boxes)')
# Rag-specific options (document import)
@click.option('--chunk-size', '-z', type=int, help='Text chunk size (rag boxes)')
@click.option('--overlap', '-O', type=int, help='Chunk overlap (rag boxes)')
# Bag-specific options (file storage)
@click.option('--recursive', '-x', is_flag=True, help='Include subdirectories (bag boxes)')
@click.option('--pattern', '-P', type=str, help='File pattern filter (bag boxes)')
def fill(
    box: str,
    source: str,
    shelf: Optional[str] = None,
    max_pages: Optional[int] = None,
    rate_limit: Optional[float] = None,
    depth: Optional[int] = None,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
    recursive: bool = False,
    pattern: Optional[str] = None
):
    """Add content to a box (unified crawl/upload)."""

    async def _fill():
        fill_service = FillService()
        box_service = BoxService()
        shelf_service = ShelfService()
        context_service = ContextService()
        try:
            # Ensure current shelf context if not specified
            target_shelf = shelf
            if not target_shelf:
                current = await shelf_service.get_current_shelf()
                if not current:
                    console.print("[red]No current shelf set. Use 'bablib shelf current <name>' to set one.[/red]")
                    raise click.Abort()
                target_shelf = current.name

            # Use context service to check box existence and get context
            context = await context_service.check_box_exists(box, target_shelf)

            if not context.entity_exists:
                console.print(f"[red]Box '{box}' not found.[/red]")
                if click.confirm(f"Create box '{box}'?"):
                    box_type = click.prompt("Box type", type=click.Choice(['drag', 'rag', 'bag']))

                    # Create the box
                    box_obj = await box_service.create_box(
                        name=box,
                        box_type=box_type,
                        shelf_name=target_shelf
                    )
                    console.print(f"[green]Created {box_type} box '{box}'[/green]")

                    # Update context after creation
                    context = await context_service.check_box_exists(box, target_shelf)
                else:
                    raise click.Abort()

            # Get box object for type information
            box_obj = await box_service.get_box_by_name(box)

            # Validate source matches box type
            _validate_source_for_box_type(source, box_obj.type.value)

            # Prepare type-specific options
            options = {}

            if max_pages is not None:
                options['max_pages'] = max_pages
            if rate_limit is not None:
                options['rate_limit'] = rate_limit
            if depth is not None:
                options['depth'] = depth
            if chunk_size is not None:
                options['chunk_size'] = chunk_size
            if overlap is not None:
                options['overlap'] = overlap
            if recursive:
                options['recursive'] = recursive
            if pattern is not None:
                options['pattern'] = pattern

            # Show what we're about to do
            operation_messages = {
                'drag': f"[blue]Crawling {source} into drag box '{box}'...[/blue]",
                'rag': f"[blue]Importing {source} into rag box '{box}'...[/blue]",
                'bag': f"[blue]Storing {source} into bag box '{box}'...[/blue]"
            }

            console.print(operation_messages.get(box_obj.type.value, f"[blue]Filling {box_obj.type.value} box '{box}'...[/blue]"))

            # Show relevant options
            if options:
                console.print("[dim]Options:[/dim]")
                for key, value in options.items():
                    console.print(f"  [dim]{key}: {value}[/dim]")

            # Execute fill operation with progress indication
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Processing...", total=None)

                result = await fill_service.fill(
                    box_name=box,
                    source=source,
                    shelf_name=target_shelf,
                    **options
                )

                progress.stop()

            # Show results
            if result['success']:
                console.print(f"[green]Successfully filled box '{box}'[/green]")

                # Show operation-specific details
                if result.get('operation'):
                    console.print(f"  Operation: {result['operation']}")

                # Show some stats if available
                stats_shown = False
                for stat_key in ['max_pages', 'chunk_size', 'pattern']:
                    if stat_key in result:
                        if not stats_shown:
                            console.print("  Settings applied:")
                            stats_shown = True
                        console.print(f"    {stat_key}: {result[stat_key]}")

            else:
                error_msg = result.get('error', 'Unknown error')
                console.print(f"[red]Failed to fill: {error_msg}[/red]")
                raise click.Abort()

        except BoxNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise click.Abort()
        except DatabaseError as e:
            console.print(f"[red]Failed to fill: {e}[/red]")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Failed to fill box: {e}[/red]")
            raise click.Abort()
        finally:
            # Ensure database connections are closed
            await box_service.db.cleanup()
            await shelf_service.db.cleanup()

    asyncio.run(_fill())


def _validate_source_for_box_type(source: str, box_type: str):
    """Validate that source parameter matches box type requirements."""
    import re
    import os

    if box_type == 'drag':
        # Must be valid URL for drag boxes
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(source):
            console.print(f"[red]Error: Drag boxes require a valid URL, got: {source}[/red]")
            console.print("[dim]Example: https://docs.example.com[/dim]")
            raise click.Abort()

    elif box_type == 'rag':
        # Must be valid file path for rag boxes
        if not os.path.exists(source) and not source.startswith(('http://', 'https://')):
            console.print(f"[red]Error: Rag boxes require a valid file path or URL, got: {source}[/red]")
            console.print("[dim]Example: /path/to/documents or https://docs.example.com/file.pdf[/dim]")
            raise click.Abort()

    elif box_type == 'bag':
        # Must be valid content path or data for bag boxes
        if not source:
            console.print("[red]Error: Bag boxes require content source[/red]")
            console.print("[dim]Example: /path/to/files or 'data content'[/dim]")
            raise click.Abort()

    # Validation passed
    console.print(f"[green]✓[/green] Source validated for {box_type} box")


def _get_box_type_help(box_type: str) -> str:
    """Get help text for box type requirements."""
    help_messages = {
        'drag': "Drag boxes crawl websites. Provide a URL like: https://docs.example.com",
        'rag': "Rag boxes import documents. Provide a file path like: /path/to/docs",
        'bag': "Bag boxes store files. Provide a content path like: /path/to/files"
    }
    return help_messages.get(box_type, "Unknown box type")