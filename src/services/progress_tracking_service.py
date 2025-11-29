"""ProgressTrackingService with Rich Live display integration."""
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.core.lib_logger import get_logger
from src.models.progress_tracker import ProgressStep, StepStatus

logger = get_logger(__name__)


class ProgressTrackingService:
    """Service for tracking and displaying progress with Rich UI."""

    def __init__(self):
        """Initialize progress tracking service."""
        self.console = Console()
        self.steps: list[ProgressStep] = []
        self.live_display: Live | None = None
        self.current_step_id: str | None = None
        self.callbacks: dict[str, Callable[[ProgressStep], Awaitable[None]]] = {}

    def initialize_steps(self, step_definitions: list[dict[str, Any]]) -> None:
        """Initialize progress steps."""
        self.steps = []
        for step_def in step_definitions:
            step = ProgressStep(
                id=step_def["id"],
                name=step_def["name"],
                status=StepStatus.PENDING,
                start_time=None,
                end_time=None,
                duration_seconds=None
            )
            self.steps.append(step)

        logger.info(f"Initialized {len(self.steps)} progress steps")

    def start_step(self, step_id: str) -> bool:
        """Start a progress step."""
        try:
            step = self._get_step_by_id(step_id)
            if not step:
                logger.error(f"Step not found: {step_id}")
                return False

            step.status = StepStatus.RUNNING
            step.start_time = datetime.now()
            self.current_step_id = step_id

            logger.info(f"Step started: {step_id} - {step.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start step {step_id}: {e}")
            return False

    def complete_step(self, step_id: str, success: bool = True) -> bool:
        """Complete a progress step."""
        try:
            step = self._get_step_by_id(step_id)
            if not step:
                logger.error(f"Step not found: {step_id}")
                return False

            step.status = StepStatus.COMPLETED if success else StepStatus.ERROR
            step.end_time = datetime.now()

            if step.start_time:
                duration = (step.end_time - step.start_time).total_seconds()
                step.duration_seconds = duration

            self.current_step_id = None

            status_text = "completed" if success else "failed"
            logger.info(f"Step {status_text}: {step_id} - {step.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to complete step {step_id}: {e}")
            return False

    def fail_step(self, step_id: str, error_message: str | None = None) -> bool:
        """Mark a step as failed."""
        try:
            step = self._get_step_by_id(step_id)
            if not step:
                logger.error(f"Step not found: {step_id}")
                return False

            step.status = StepStatus.ERROR
            step.end_time = datetime.now()

            if step.start_time:
                duration = (step.end_time - step.start_time).total_seconds()
                step.duration_seconds = duration

            if error_message:
                step.error_message = error_message

            logger.error(f"Step failed: {step_id} - {step.name}: {error_message or 'Unknown error'}")
            return True

        except Exception as e:
            logger.error(f"Failed to fail step {step_id}: {e}")
            return False

    def _get_step_by_id(self, step_id: str) -> ProgressStep | None:
        """Get step by ID."""
        return next((step for step in self.steps if step.id == step_id), None)

    def get_progress_summary(self) -> dict[str, Any]:
        """Get progress summary."""
        total_steps = len(self.steps)
        completed_steps = len([s for s in self.steps if s.status == StepStatus.COMPLETED])
        failed_steps = len([s for s in self.steps if s.status == StepStatus.ERROR])
        running_steps = len([s for s in self.steps if s.status == StepStatus.RUNNING])

        return {
            "total_steps": total_steps,
            "completed": completed_steps,
            "failed": failed_steps,
            "running": running_steps,
            "pending": total_steps - completed_steps - failed_steps - running_steps,
            "progress_percentage": (completed_steps / total_steps * 100) if total_steps > 0 else 0,
            "current_step": self.current_step_id,
            "overall_status": self._get_overall_status()
        }

    def _get_overall_status(self) -> str:
        """Get overall progress status."""
        if any(step.status == StepStatus.ERROR for step in self.steps):
            return "error"
        elif any(step.status == StepStatus.RUNNING for step in self.steps):
            return "running"
        elif all(step.status == StepStatus.COMPLETED for step in self.steps):
            return "completed"
        else:
            return "pending"

    def create_progress_table(self) -> Table:
        """Create Rich table for progress display."""
        table = Table(title="Installation Progress", show_header=True, header_style="bold magenta")

        table.add_column("Step", style="dim", width=20)
        table.add_column("Status", width=12)
        table.add_column("Duration", justify="right", width=10)
        table.add_column("Description", width=40)

        for step in self.steps:
            # Status with emoji
            if step.status == StepStatus.COMPLETED:
                status = "[green]✓ Completed[/green]"
            elif step.status == StepStatus.RUNNING:
                status = "[yellow]⏳ Running[/yellow]"
            elif step.status == StepStatus.ERROR:
                status = "[red]✗ Failed[/red]"
            else:
                status = "[dim]○ Pending[/dim]"

            # Duration
            duration = ""
            if step.duration_seconds:
                duration = f"{step.duration_seconds:.1f}s"
            elif step.status == StepStatus.RUNNING and step.start_time:
                current_duration = (datetime.now() - step.start_time).total_seconds()
                duration = f"{current_duration:.1f}s"

            # Description
            description = step.name
            if step.status == StepStatus.ERROR and hasattr(step, 'error_message'):
                description += f" - {step.error_message}"

            table.add_row(step.id, status, duration, description)

        return table

    def create_progress_panel(self) -> Panel:
        """Create Rich panel with progress information."""
        summary = self.get_progress_summary()

        # Create summary text
        summary_text = Text()
        summary_text.append(f"Progress: {summary['completed']}/{summary['total_steps']} steps completed", style="bold")
        summary_text.append(f" ({summary['progress_percentage']:.1f}%)\n")

        if summary['running'] > 0:
            summary_text.append(f"Currently running: {summary['current_step']}", style="yellow")
        elif summary['failed'] > 0:
            summary_text.append(f"Failed steps: {summary['failed']}", style="red")
        elif summary['overall_status'] == "completed":
            summary_text.append("All steps completed successfully!", style="green bold")

        # Create table
        table = self.create_progress_table()

        return Panel.fit(
            table,
            title="Bablib Installation Progress",
            subtitle=summary_text,
            border_style="blue"
        )

    async def start_live_display(self) -> None:
        """Start live progress display."""
        try:
            self.live_display = Live(
                self.create_progress_panel(),
                refresh_per_second=2,
                console=self.console
            )
            self.live_display.start()
            logger.info("Live progress display started")

        except Exception as e:
            logger.error(f"Failed to start live display: {e}")

    def stop_live_display(self) -> None:
        """Stop live progress display."""
        try:
            if self.live_display:
                self.live_display.stop()
                self.live_display = None
                logger.info("Live progress display stopped")

        except Exception as e:
            logger.error(f"Failed to stop live display: {e}")

    def update_live_display(self) -> None:
        """Update live progress display."""
        try:
            if self.live_display:
                self.live_display.update(self.create_progress_panel())

        except Exception as e:
            logger.error(f"Failed to update live display: {e}")

    async def execute_step_with_progress(
        self,
        step_id: str,
        step_function: Callable[[], Awaitable[bool]],
        auto_update_display: bool = True
    ) -> bool:
        """Execute a step function with automatic progress tracking."""
        try:
            # Start step
            if not self.start_step(step_id):
                return False

            if auto_update_display:
                self.update_live_display()

            # Execute callback if registered
            step = self._get_step_by_id(step_id)
            if step and step_id in self.callbacks:
                await self.callbacks[step_id](step)

            # Execute step function
            success = await step_function()

            # Complete step
            self.complete_step(step_id, success)

            if auto_update_display:
                self.update_live_display()

            return success

        except Exception as e:
            self.fail_step(step_id, str(e))
            if auto_update_display:
                self.update_live_display()
            return False

    def register_step_callback(self, step_id: str, callback: Callable[[ProgressStep], Awaitable[None]]) -> None:
        """Register callback for step events."""
        self.callbacks[step_id] = callback

    async def run_installation_sequence(
        self,
        step_functions: dict[str, Callable[[], Awaitable[bool]]],
        stop_on_failure: bool = True
    ) -> dict[str, Any]:
        """Run complete installation sequence with progress tracking."""
        try:
            await self.start_live_display()

            results = {"success": True, "completed_steps": [], "failed_steps": []}

            for step_id, step_function in step_functions.items():
                success = await self.execute_step_with_progress(step_id, step_function)

                if success:
                    results["completed_steps"].append(step_id)
                else:
                    results["failed_steps"].append(step_id)
                    results["success"] = False

                    if stop_on_failure:
                        logger.error(f"Installation stopped due to failed step: {step_id}")
                        break

            self.stop_live_display()

            # Final summary
            summary = self.get_progress_summary()
            results["summary"] = summary

            return results

        except Exception as e:
            logger.error(f"Installation sequence failed: {e}")
            self.stop_live_display()
            return {"success": False, "error": str(e)}

    def display_final_summary(self) -> None:
        """Display final installation summary."""
        try:
            summary = self.get_progress_summary()

            # Create final summary panel
            if summary["overall_status"] == "completed":
                title = "[green]Installation Completed Successfully![/green]"
                style = "green"
            elif summary["overall_status"] == "error":
                title = "[red]Installation Failed[/red]"
                style = "red"
            else:
                title = "[yellow]Installation Incomplete[/yellow]"
                style = "yellow"

            summary_text = f"""
Steps Completed: {summary['completed']}/{summary['total_steps']}
Failed Steps: {summary['failed']}
Total Duration: {self._calculate_total_duration():.1f}s
"""

            panel = Panel(
                summary_text.strip(),
                title=title,
                border_style=style,
                padding=(1, 2)
            )

            self.console.print(panel)

        except Exception as e:
            logger.error(f"Failed to display final summary: {e}")

    def _calculate_total_duration(self) -> float:
        """Calculate total duration of all completed steps."""
        total = 0.0
        for step in self.steps:
            if step.duration_seconds:
                total += step.duration_seconds
        return total
