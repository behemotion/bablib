"""
System Information Models for Bablib Setup
Provides models for displaying system configuration and service status
"""

import asyncio
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table


class ServiceStatus(BaseModel):
    """Represents availability of an external service"""

    name: str = Field(..., description="Service name (e.g., 'Ollama', 'Qdrant')")
    available: bool = Field(..., description="Whether service is accessible")
    version: str | None = Field(None, description="Detected version if available")
    has_alternative: bool = Field(False, description="Whether functional alternative exists")

    @property
    def status_color(self) -> str:
        """Get display color based on availability."""
        if self.available:
            return "green"
        elif self.has_alternative:
            return "yellow"
        else:
            return "red"

    @property
    def status_text(self) -> str:
        """Get display text for status."""
        if self.available:
            return f"Available ({self.version})" if self.version else "Available"
        else:
            return "Not Available"


class DirectoryInfo(BaseModel):
    """Information about Bablib directories"""

    config_dir: Path = Field(..., description="Configuration directory path")
    data_dir: Path = Field(..., description="Data storage directory path")
    cache_dir: Path = Field(..., description="Cache directory path")


class SystemInfoPanel:
    """Aggregates and formats system configuration information"""

    def __init__(self):
        """Initialize system info panel."""
        self.global_settings: dict[str, Any] = {}
        self.projects_count: int = 0
        self.available_services: list[ServiceStatus] = []
        self.vector_stores: list[str] = []
        self.sql_databases: list[str] = []
        self.directories: DirectoryInfo | None = None
        self._cache_time: float | None = None
        self._cached_data: dict[str, Any] | None = None
        self.console = Console()

    def collect_async(self) -> None:
        """
        Synchronous wrapper for async collection.
        For compatibility with sync code.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, schedule the coroutine
                task = asyncio.create_task(self._collect_async_internal())
                # For sync interface, we can't wait properly, so just return
                return
            else:
                # Run in new event loop
                asyncio.run(self._collect_async_internal())
        except RuntimeError:
            # No event loop, create one
            asyncio.run(self._collect_async_internal())

    async def _collect_async_internal(self) -> None:
        """Internal async collection method."""
        # Check cache
        if self._cache_time and (time.time() - self._cache_time) < 5:
            return

        # Import here to avoid circular dependencies
        try:
            from src.logic.setup.services.detector import ServiceDetector
            from src.models.project import ProjectDatabase
            from src.services.settings_service import SettingsService
        except ImportError:
            # Modules may not exist yet during testing
            self._set_default_values()
            return

        try:
            # Collect settings
            settings_service = SettingsService()
            settings = settings_service.get_settings()
            self.global_settings = {
                "Vector Store Provider": getattr(settings, 'vector_store_provider', 'sqlite_vec'),
                "Embedding Model": getattr(settings, 'embedding_model', 'mxbai-embed-large'),
                "Chunk Size": getattr(settings, 'chunk_size', 500),
                "Chunk Overlap": getattr(settings, 'chunk_overlap', 50),
                "Default Crawl Depth": getattr(settings, 'crawl_depth', 2),
                "Default Rate Limit": getattr(settings, 'rate_limit', 2.0),
            }

            # Collect project count
            try:
                db = ProjectDatabase()
                projects = await db.list_all_async()
                self.projects_count = len(projects)
            except Exception:
                self.projects_count = 0

            # Detect services
            detector = ServiceDetector()
            service_info = await detector.detect_all()

            # Convert to ServiceStatus objects
            self.available_services = []
            for name, info in service_info.items():
                # Determine if service has alternative
                has_alternative = False
                if name == 'qdrant' and service_info.get('sqlite_vec', {}).get('available'):
                    has_alternative = True

                status = ServiceStatus(
                    name=name.replace('_', '-').title(),
                    available=info.get('available', False),
                    version=info.get('version'),
                    has_alternative=has_alternative
                )
                self.available_services.append(status)

            # Collect directories
            config_dir = Path.home() / ".config" / "bablib"
            data_dir = Path.home() / ".local" / "share" / "bablib"
            cache_dir = Path.home() / ".cache" / "bablib"

            self.directories = DirectoryInfo(
                config_dir=config_dir,
                data_dir=data_dir,
                cache_dir=cache_dir
            )

            # Detect available stores
            self.vector_stores = []
            if any(s.name.lower() == 'sqlite-vec' and s.available for s in self.available_services):
                self.vector_stores.append("SQLite-vec")
            if any(s.name.lower() == 'qdrant' and s.available for s in self.available_services):
                self.vector_stores.append("Qdrant")

            # Update cache
            self._cache_time = time.time()

        except Exception:
            # If collection fails, use defaults
            self._set_default_values()

    def format_table(self) -> Table:
        """
        Generate Rich table for display.

        Returns:
            Table: Formatted table with system information
        """
        # Create table
        table = Table(title="System Information", show_header=True, header_style="bold cyan")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Details", style="white")

        # Add global settings
        if self.global_settings:
            settings_text = "\n".join(f"• {k}: {v}" for k, v in self.global_settings.items())
            table.add_row("Settings", settings_text)

        # Add directories
        if self.directories:
            dir_text = (
                f"• Config: {self.directories.config_dir}\n"
                f"• Data: {self.directories.data_dir}\n"
                f"• Cache: {self.directories.cache_dir}"
            )
            table.add_row("Directories", dir_text)

        # Add projects
        table.add_row("Projects", f"Total: {self.projects_count}")

        # Add services (filtered)
        filtered_services = self.filter_services()
        if filtered_services:
            service_text = "\n".join(
                f"• {s.name}: [{s.status_color}]{s.status_text}[/{s.status_color}]"
                for s in filtered_services
            )
            table.add_row("Services", service_text)

        # Add available stores
        if self.vector_stores:
            stores_text = ", ".join(self.vector_stores)
            table.add_row("Vector Stores", stores_text)

        return table

    def filter_services(self) -> list[ServiceStatus]:
        """
        Hide services with alternatives when unavailable.

        Returns:
            List[ServiceStatus]: Filtered list of services to display
        """
        filtered = []
        for service in self.available_services:
            # Show service if available OR if it's critical (no alternative)
            if service.available or not service.has_alternative:
                filtered.append(service)
        return filtered

    def _set_default_values(self):
        """Set default values when actual collection fails."""
        self.global_settings = {
            "Vector Store Provider": "sqlite_vec",
            "Embedding Model": "mxbai-embed-large",
            "Chunk Size": 500,
            "Chunk Overlap": 50,
        }
        self.projects_count = 0
        self.available_services = []
        self.directories = DirectoryInfo(
            config_dir=Path.home() / ".config" / "bablib",
            data_dir=Path.home() / ".local" / "share" / "bablib",
            cache_dir=Path.home() / ".cache" / "bablib"
        )
        self.vector_stores = ["SQLite-vec"]
