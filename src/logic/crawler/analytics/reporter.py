"""Error reporting service for crawl operations."""

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.lib.paths import get_bablib_data_dir

logger = logging.getLogger(__name__)


class ErrorReporter:
    """Service for collecting and reporting crawl errors."""

    def __init__(self, project_name: str):
        """Initialize error reporter for a project.

        Args:
            project_name: Name of the project being crawled
        """
        self.project_name = project_name
        self.errors: list[dict[str, Any]] = []
        self.start_time = datetime.now(timezone.utc)
        self.report_id = str(uuid4())
        self._stats = {
            'total_pages': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'embeddings_count': 0
        }

    def add_error(
        self,
        url: str,
        error_type: str,
        error_message: str,
        error_code: int | None = None,
        retry_count: int = 0,
        include_traceback: bool = False
    ) -> None:
        """Add an error to the report.

        Args:
            url: URL that caused the error
            error_type: Type of error (NETWORK, PARSE, TIMEOUT, etc.)
            error_message: Human-readable error message
            error_code: Optional HTTP error code
            retry_count: Number of retry attempts
            include_traceback: Whether to include stack trace
        """
        error_entry = {
            'error_id': str(uuid4()),
            'url': url,
            'error_type': error_type,
            'error_message': error_message[:500],  # Limit message length
            'error_code': error_code,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'retry_count': retry_count
        }

        if include_traceback:
            error_entry['stacktrace'] = traceback.format_exc()

        self.errors.append(error_entry)
        logger.debug(f"Error recorded for {url}: {error_type} - {error_message}")

    def update_stats(
        self,
        total_pages: int | None = None,
        successful_pages: int | None = None,
        failed_pages: int | None = None,
        embeddings_count: int | None = None
    ) -> None:
        """Update crawl statistics.

        Args:
            total_pages: Total pages to crawl
            successful_pages: Successfully crawled pages
            failed_pages: Failed pages
            embeddings_count: Number of embeddings created
        """
        if total_pages is not None:
            self._stats['total_pages'] = total_pages
        if successful_pages is not None:
            self._stats['successful_pages'] = successful_pages
        if failed_pages is not None:
            self._stats['failed_pages'] = failed_pages
        if embeddings_count is not None:
            self._stats['embeddings_count'] = embeddings_count

    def increment_success(self) -> None:
        """Increment successful page count."""
        self._stats['successful_pages'] += 1

    def increment_failure(self) -> None:
        """Increment failed page count."""
        self._stats['failed_pages'] += 1

    def get_report_dir(self) -> Path:
        """Get the directory for storing reports.

        Returns:
            Path to report directory
        """
        data_dir = get_bablib_data_dir()
        report_dir = data_dir / "projects" / self.project_name / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir

    def generate_report(self) -> dict[str, Any]:
        """Generate a complete crawl report.

        Returns:
            Dictionary containing the full report
        """
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()

        # Determine status
        if self._stats['failed_pages'] == 0:
            status = 'SUCCESS'
        elif self._stats['successful_pages'] > 0:
            status = 'PARTIAL'
        else:
            status = 'FAILED'

        report = {
            'report_id': self.report_id,
            'project_name': self.project_name,
            'timestamp': end_time.isoformat(),
            'status': status,
            'total_pages': self._stats['total_pages'],
            'successful_pages': self._stats['successful_pages'],
            'failed_pages': self._stats['failed_pages'],
            'embeddings_count': self._stats['embeddings_count'],
            'duration_seconds': duration,
            'errors': self.errors,
            'error_summary': self._generate_error_summary()
        }

        return report

    def _generate_error_summary(self) -> dict[str, Any]:
        """Generate summary statistics for errors.

        Returns:
            Error summary dictionary
        """
        if not self.errors:
            return {'total_errors': 0}

        error_types = {}
        for error in self.errors:
            error_type = error['error_type']
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            'total_errors': len(self.errors),
            'by_type': error_types,
            'unique_urls': len(set(e['url'] for e in self.errors))
        }

    def save_report(self) -> tuple[Path, Path]:
        """Save report to both JSON and human-readable formats.

        Returns:
            Tuple of (json_path, text_path)
        """
        report = self.generate_report()
        report_dir = self.get_report_dir()

        # Create timestamp for filenames
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

        # Save JSON report
        json_path = report_dir / f"report_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        # Save human-readable report
        text_path = report_dir / f"report_{timestamp}.txt"
        with open(text_path, 'w') as f:
            f.write(self._format_human_report(report))

        # Also save as latest for easy access
        latest_json = report_dir / "report_latest.json"
        latest_text = report_dir / "report_latest.txt"

        with open(latest_json, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        with open(latest_text, 'w') as f:
            f.write(self._format_human_report(report))

        logger.info(f"Reports saved to {report_dir}")
        return json_path, text_path

    def _format_human_report(self, report: dict[str, Any]) -> str:
        """Format report for human readability.

        Args:
            report: Report dictionary

        Returns:
            Formatted text report
        """
        lines = [
            "=" * 80,
            f"CRAWL REPORT - {self.project_name}",
            "=" * 80,
            f"Report ID: {report['report_id']}",
            f"Timestamp: {report['timestamp']}",
            f"Status: {report['status']}",
            f"Duration: {report['duration_seconds']:.2f} seconds",
            "",
            "STATISTICS:",
            "-" * 40,
            f"Total Pages: {report['total_pages']}",
            f"Successful: {report['successful_pages']}",
            f"Failed: {report['failed_pages']}",
            f"Embeddings Created: {report['embeddings_count']}",
            ""
        ]

        if report['errors']:
            lines.extend([
                "ERROR SUMMARY:",
                "-" * 40,
                f"Total Errors: {report['error_summary']['total_errors']}",
                f"Unique URLs: {report['error_summary']['unique_urls']}",
                "",
                "Errors by Type:"
            ])

            for error_type, count in report['error_summary']['by_type'].items():
                lines.append(f"  {error_type}: {count}")

            lines.extend([
                "",
                "DETAILED ERRORS:",
                "-" * 40
            ])

            for i, error in enumerate(report['errors'], 1):
                lines.extend([
                    f"\n[{i}] URL: {error['url']}",
                    f"    Type: {error['error_type']}",
                    f"    Message: {error['error_message']}",
                ])
                if error.get('error_code'):
                    lines.append(f"    Code: {error['error_code']}")
                lines.append(f"    Time: {error['timestamp']}")
                if error.get('retry_count', 0) > 0:
                    lines.append(f"    Retries: {error['retry_count']}")

        lines.extend([
            "",
            "=" * 80,
            "END OF REPORT"
        ])

        return "\n".join(lines)

    def has_errors(self) -> bool:
        """Check if any errors were recorded.

        Returns:
            True if errors exist
        """
        return len(self.errors) > 0

    def get_error_count(self) -> int:
        """Get total number of errors.

        Returns:
            Error count
        """
        return len(self.errors)

    def clear_errors(self) -> None:
        """Clear all recorded errors."""
        self.errors.clear()
        logger.debug("Error list cleared")
