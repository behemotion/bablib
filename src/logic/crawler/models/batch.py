"""BatchOperation model for batch crawl tracking."""

from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BatchOperation(BaseModel):
    """Batch crawl operation tracking."""

    operation_id: str = Field(default_factory=lambda: str(uuid4()))
    projects: list[str] = Field(default_factory=list)
    current_index: int = Field(default=0, ge=0)
    completed: list[str] = Field(default_factory=list)
    failed: list[tuple[str, str]] = Field(default_factory=list)  # (project, error)
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    estimated_completion: datetime | None = None
    continue_on_error: bool = Field(default=True)
    total_pages_crawled: int = Field(default=0, ge=0)
    total_embeddings_created: int = Field(default=0, ge=0)

    @field_validator('current_index')
    @classmethod
    def validate_current_index(cls, v: int, info) -> int:
        """Validate that current_index <= len(projects)."""
        if 'projects' in info.data and v > len(info.data['projects']):
            raise ValueError(f"Current index ({v}) cannot exceed number of projects ({len(info.data['projects'])})")
        return v

    @field_validator('projects')
    @classmethod
    def validate_unique_projects(cls, v: list[str]) -> list[str]:
        """Validate that projects list has no duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Project list contains duplicates")
        return v

    def get_current_project(self) -> str | None:
        """Get the current project being processed.

        Returns:
            Current project name or None if complete
        """
        if 0 <= self.current_index < len(self.projects):
            return self.projects[self.current_index]
        return None

    def mark_completed(self, project: str, pages: int = 0, embeddings: int = 0) -> None:
        """Mark a project as completed.

        Args:
            project: Project name
            pages: Number of pages crawled
            embeddings: Number of embeddings created
        """
        if project not in self.completed:
            self.completed.append(project)
            self.total_pages_crawled += pages
            self.total_embeddings_created += embeddings

        # Advance if this was the current project
        if self.get_current_project() == project:
            self.current_index += 1
            self._update_estimated_completion()

    def mark_failed(self, project: str, error: str) -> None:
        """Mark a project as failed.

        Args:
            project: Project name
            error: Error message
        """
        self.failed.append((project, error))

        # Advance if this was the current project and continue_on_error is True
        if self.get_current_project() == project and self.continue_on_error:
            self.current_index += 1
            self._update_estimated_completion()

    def _update_estimated_completion(self) -> None:
        """Update estimated completion time based on current progress."""
        if self.current_index == 0 or len(self.projects) == 0:
            return

        elapsed = datetime.now(timezone.utc) - self.start_time
        avg_time_per_project = elapsed / self.current_index
        remaining_projects = len(self.projects) - self.current_index

        if remaining_projects > 0:
            estimated_remaining = avg_time_per_project * remaining_projects
            self.estimated_completion = datetime.now(timezone.utc) + estimated_remaining

    def is_complete(self) -> bool:
        """Check if batch operation is complete.

        Returns:
            True if all projects processed
        """
        return self.current_index >= len(self.projects)

    def get_progress(self) -> float:
        """Get progress as percentage.

        Returns:
            Progress (0-100)
        """
        if len(self.projects) == 0:
            return 100.0
        return (self.current_index / len(self.projects)) * 100

    def get_progress_text(self) -> str:
        """Get progress as text.

        Returns:
            Progress text
        """
        return f"{self.current_index}/{len(self.projects)} projects"

    def get_success_count(self) -> int:
        """Get number of successful projects.

        Returns:
            Success count
        """
        return len(self.completed)

    def get_failure_count(self) -> int:
        """Get number of failed projects.

        Returns:
            Failure count
        """
        return len(self.failed)

    def get_duration(self) -> timedelta:
        """Get operation duration.

        Returns:
            Duration as timedelta
        """
        end = self.end_time or datetime.now(timezone.utc)
        return end - self.start_time

    def get_duration_seconds(self) -> float:
        """Get operation duration in seconds.

        Returns:
            Duration in seconds
        """
        return self.get_duration().total_seconds()

    def complete(self) -> None:
        """Mark the batch operation as complete."""
        self.end_time = datetime.now(timezone.utc)
        self.estimated_completion = None

    def get_summary(self) -> dict[str, Any]:
        """Get operation summary.

        Returns:
            Summary dictionary
        """
        return {
            "operation_id": self.operation_id,
            "total_projects": len(self.projects),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "progress": f"{self.get_progress():.1f}%",
            "duration_seconds": self.get_duration_seconds(),
            "total_pages": self.total_pages_crawled,
            "total_embeddings": self.total_embeddings_created,
            "is_complete": self.is_complete(),
            "success_rate": self.get_success_rate()
        }

    def get_success_rate(self) -> float:
        """Calculate success rate.

        Returns:
            Success rate (0-100)
        """
        total_processed = len(self.completed) + len(self.failed)
        if total_processed == 0:
            return 0.0
        return (len(self.completed) / total_processed) * 100

    def get_failed_projects(self) -> list[dict[str, str]]:
        """Get list of failed projects with errors.

        Returns:
            List of failure dictionaries
        """
        return [
            {"project": project, "error": error}
            for project, error in self.failed
        ]

    def get_remaining_projects(self) -> list[str]:
        """Get list of remaining projects.

        Returns:
            List of unprocessed project names
        """
        if self.current_index >= len(self.projects):
            return []
        return self.projects[self.current_index:]

    def should_continue(self) -> bool:
        """Check if batch should continue processing.

        Returns:
            True if should continue
        """
        return not self.is_complete() and (
            self.continue_on_error or len(self.failed) == 0
        )

    model_config = ConfigDict()
