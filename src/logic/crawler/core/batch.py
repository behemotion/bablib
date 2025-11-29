"""Batch crawler service for processing multiple projects."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from src.models.project_status import ProjectStatus
from src.logic.projects.core.project_manager import ProjectManager

from ..analytics.reporter import ErrorReporter
from ..models.batch import BatchOperation
from ..utils.progress import CrawlPhase, ProgressReporter
from .crawler import DocumentationCrawler

logger = logging.getLogger(__name__)


class BatchCrawler:
    """Service for batch crawling multiple projects."""

    def __init__(
        self,
        project_manager: ProjectManager | None = None,
        progress_reporter: ProgressReporter | None = None
    ):
        """Initialize batch crawler.

        Args:
            project_manager: Project manager instance
            progress_reporter: Progress reporter instance
        """
        self.project_manager = project_manager or ProjectManager()
        self.progress_reporter = progress_reporter
        self.operation: BatchOperation | None = None
        self._cancelled = False

    async def crawl_all(
        self,
        projects: list[ProjectStatus] | None = None,
        max_pages: int | None = None,
        rate_limit: float = 1.0,
        continue_on_error: bool = True,
        progress_callback: Callable | None = None
    ) -> dict[str, Any]:
        """Crawl all projects in batch.

        Args:
            projects: List of projects to crawl (None for all)
            max_pages: Maximum pages per project
            rate_limit: Requests per second
            continue_on_error: Continue if project fails
            progress_callback: Optional progress callback

        Returns:
            Summary of batch operation
        """
        # Get projects if not provided
        if projects is None:
            projects = await self.project_manager.list_projects()

        if not projects:
            logger.info("No projects to crawl")
            return {"total": 0, "succeeded": 0, "failed": 0}

        # Initialize batch operation
        project_names = [p.project_name for p in projects]
        self.operation = BatchOperation(
            projects=project_names,
            continue_on_error=continue_on_error
        )

        logger.info(f"Starting batch crawl for {len(projects)} projects")

        # Process each project sequentially
        for project in projects:
            if self._cancelled:
                logger.info("Batch crawl cancelled")
                break

            try:
                # Update progress
                if progress_callback:
                    progress_callback(self.operation.get_summary())

                # Crawl project
                result = await self.crawl_project(
                    project,
                    max_pages=max_pages,
                    rate_limit=rate_limit
                )

                # Mark as completed
                self.operation.mark_completed(
                    project.project_name,
                    pages=result.get('pages', 0),
                    embeddings=result.get('embeddings', 0)
                )

                logger.info(f"Successfully crawled {project.project_name}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to crawl {project.project_name}: {error_msg}")

                # Mark as failed
                self.operation.mark_failed(project.project_name, error_msg)

                # Stop if not continuing on error
                if not continue_on_error:
                    logger.info("Stopping batch due to error")
                    break

        # Complete operation
        self.operation.complete()

        # Generate summary
        summary = self.generate_summary()
        logger.info(f"Batch crawl completed: {summary}")

        return summary

    async def crawl_project(
        self,
        project: ProjectStatus,
        max_pages: int | None = None,
        rate_limit: float = 1.0
    ) -> dict[str, Any]:
        """Crawl a single project.

        Args:
            project: Project to crawl
            max_pages: Maximum pages to crawl
            rate_limit: Requests per second

        Returns:
            Crawl result dictionary
        """
        logger.info(f"Crawling project: {project.project_name}")

        # Mark project as crawling
        project.mark_crawling()
        await self.project_manager.update_project(project)

        # Create crawler and error reporter
        from src.core.config import BablibConfig
        from src.services.database import DatabaseManager

        config = BablibConfig()
        db_manager = DatabaseManager(config)
        await db_manager.initialize()

        crawler = DocumentationCrawler(db_manager, config)
        await crawler.initialize()

        error_reporter = ErrorReporter(project.project_name)

        try:
            # Start progress if available
            if self.progress_reporter and self.progress_reporter.is_active():
                self.progress_reporter.start_phase(
                    CrawlPhase.CRAWLING_CONTENT,
                    total=max_pages or 100,
                    description=f"Crawling {project.project_name}"
                )

            # Get or create box in DB
            # TODO: BatchCrawler needs full migration to Box-centric architecture
            # For now, we create/use boxes for crawl operations
            db_box = await db_manager.get_box_by_name(project.project_name)
            if not db_box:
                # Create box if it doesn't exist
                db_box = await db_manager.create_box(
                    name=project.project_name,
                    box_type="drag",  # Crawling = drag type
                    url=project.url or "",
                    crawl_depth=3
                )

            # Perform crawl
            session = await crawler.start_crawl(
                box_id=db_box.id,
                max_pages=max_pages,
                rate_limit=rate_limit
            )

            # Wait for completion
            while not session.is_completed():
                await asyncio.sleep(1)
                session = await db_manager.get_crawl_session(session.id)

            result = {
                'total_pages': session.pages_crawled,
                'embeddings_count': session.pages_crawled * 10  # Estimate
            }

            # Update project statistics
            project.increment_crawl()
            project.update_statistics(
                documents=result.get('total_pages', 0),
                embeddings=result.get('embeddings_count', 0)
            )
            project.mark_ready()

            await self.project_manager.update_project(project)

            # Save error report if errors occurred
            if error_reporter.has_errors():
                error_reporter.save_report()

            return {
                'status': 'success',
                'pages': result.get('total_pages', 0),
                'embeddings': result.get('embeddings_count', 0),
                'errors': error_reporter.get_error_count()
            }

        except Exception as e:
            # Mark project as errored
            project.mark_error(str(e))
            await self.project_manager.update_project(project)

            # Save error report
            error_reporter.add_error(
                url=project.url or "unknown",
                error_type="CRAWL_FAILED",
                error_message=str(e)
            )
            error_reporter.save_report()

            raise

        finally:
            # Complete progress phase
            if self.progress_reporter and self.progress_reporter.is_active():
                self.progress_reporter.complete_phase(CrawlPhase.CRAWLING_CONTENT)

            # Cleanup
            await crawler.cleanup()
            await db_manager.cleanup()

    def cancel(self) -> None:
        """Cancel the batch operation."""
        self._cancelled = True
        if self.operation:
            logger.info(f"Cancelling batch operation {self.operation.operation_id}")

    def get_progress(self) -> dict[str, Any]:
        """Get current progress.

        Returns:
            Progress dictionary
        """
        if not self.operation:
            return {"status": "not_started"}

        return {
            "current": self.operation.current_index,
            "total": len(self.operation.projects),
            "completed": self.operation.completed,
            "failed": self.operation.get_failed_projects(),
            "progress_percent": self.operation.get_progress(),
            "current_project": self.operation.get_current_project()
        }

    def get_summary(self) -> dict[str, Any]:
        """Get operation summary.

        Returns:
            Summary dictionary
        """
        if not self.operation:
            return {"status": "no_operation"}

        return self.operation.get_summary()

    def generate_summary(self) -> dict[str, Any]:
        """Generate detailed summary of batch operation.

        Returns:
            Detailed summary
        """
        if not self.operation:
            return {"status": "no_operation"}

        summary = {
            "total": len(self.operation.projects),
            "succeeded": len(self.operation.completed),
            "failed": len(self.operation.failed),
            "duration": self.operation.get_duration_seconds(),
            "success_rate": self.operation.get_success_rate(),
            "total_pages": self.operation.total_pages_crawled,
            "total_embeddings": self.operation.total_embeddings_created
        }

        # Add failure details
        if self.operation.failed:
            summary["failures"] = self.operation.get_failed_projects()

        return summary

    def format_summary(self, summary: dict[str, Any]) -> str:
        """Format summary for display.

        Args:
            summary: Summary dictionary

        Returns:
            Formatted string
        """
        lines = [
            "Batch Crawl Summary",
            "=" * 40,
            f"Total Projects: {summary.get('total', 0)}",
            f"Succeeded: {summary.get('succeeded', 0)}",
            f"Failed: {summary.get('failed', 0)}",
            f"Success Rate: {summary.get('success_rate', 0):.1f}%",
            f"Duration: {summary.get('duration', 0):.1f} seconds",
            f"Total Pages: {summary.get('total_pages', 0)}",
            f"Total Embeddings: {summary.get('total_embeddings', 0)}"
        ]

        if summary.get('failures'):
            lines.append("\nFailed Projects:")
            for failure in summary['failures']:
                lines.append(f"  - {failure['project']}: {failure['error']}")

        return "\n".join(lines)

    def get_results(self) -> dict[str, Any]:
        """Get results for all projects.

        Returns:
            Results dictionary keyed by project name
        """
        if not self.operation:
            return {}

        results = {}

        for project in self.operation.completed:
            results[project] = {"status": "success"}

        for project, error in self.operation.failed:
            results[project] = {"status": "failed", "error": error}

        return results

    def get_current_progress(self) -> str:
        """Get current progress as text.

        Returns:
            Progress text
        """
        if not self.operation:
            return "Not started"

        current = self.operation.get_current_project()
        if current:
            return f"Processing {current} ({self.operation.get_progress_text()})"
        elif self.operation.is_complete():
            return "Complete"
        else:
            return "Processing..."

    def get_estimated_completion(self) -> datetime | None:
        """Get estimated completion time.

        Returns:
            Estimated completion datetime or None
        """
        if self.operation:
            return self.operation.estimated_completion
        return None

    def get_all_errors(self) -> list[dict[str, Any]]:
        """Get all errors from batch operation.

        Returns:
            List of error dictionaries
        """
        if not self.operation:
            return []

        errors = []
        for project, error_msg in self.operation.failed:
            errors.append({
                "project": project,
                "error": error_msg,
                "type": "CRAWL_FAILED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return errors

    async def initialize_batch(self, operation: BatchOperation) -> None:
        """Initialize with an existing batch operation.

        Args:
            operation: Batch operation to use
        """
        self.operation = operation
        self._cancelled = False
