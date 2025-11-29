"""Unit tests for ErrorReporter."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock
from src.logic.crawler.analytics.reporter import ErrorReporter


class TestErrorReporter:
    """Test ErrorReporter functionality."""

    def test_initialization(self):
        """Test ErrorReporter initialization."""
        reporter = ErrorReporter("test-project")

        assert reporter.project_name == "test-project"
        assert len(reporter.errors) == 0
        assert reporter.report_id is not None
        assert reporter._stats['total_pages'] == 0

    def test_add_error(self):
        """Test adding errors to reporter."""
        reporter = ErrorReporter("test-project")

        reporter.add_error(
            url="http://example.com",
            error_type="NETWORK",
            error_message="Connection timeout"
        )

        assert len(reporter.errors) == 1
        error = reporter.errors[0]
        assert error['url'] == "http://example.com"
        assert error['error_type'] == "NETWORK"
        assert error['error_message'] == "Connection timeout"
        assert 'error_id' in error
        assert 'timestamp' in error

    def test_add_error_with_details(self):
        """Test adding error with all details."""
        reporter = ErrorReporter("test-project")

        reporter.add_error(
            url="http://example.com/page",
            error_type="TIMEOUT",
            error_message="Request timeout",
            error_code=504,
            retry_count=3,
            include_traceback=True
        )

        error = reporter.errors[0]
        assert error['error_code'] == 504
        assert error['retry_count'] == 3
        assert 'stacktrace' in error

    def test_error_message_truncation(self):
        """Test that long error messages are truncated."""
        reporter = ErrorReporter("test-project")
        long_message = "x" * 600

        reporter.add_error(
            url="http://example.com",
            error_type="PARSE",
            error_message=long_message
        )

        assert len(reporter.errors[0]['error_message']) == 500

    def test_update_stats(self):
        """Test updating statistics."""
        reporter = ErrorReporter("test-project")

        reporter.update_stats(
            total_pages=100,
            successful_pages=85,
            failed_pages=15,
            embeddings_count=850
        )

        assert reporter._stats['total_pages'] == 100
        assert reporter._stats['successful_pages'] == 85
        assert reporter._stats['failed_pages'] == 15
        assert reporter._stats['embeddings_count'] == 850

    def test_increment_counts(self):
        """Test incrementing success and failure counts."""
        reporter = ErrorReporter("test-project")

        reporter.increment_success()
        reporter.increment_success()
        reporter.increment_failure()

        assert reporter._stats['successful_pages'] == 2
        assert reporter._stats['failed_pages'] == 1

    def test_get_report_dir(self):
        """Test report directory path generation."""
        reporter = ErrorReporter("test-project")
        report_dir = reporter.get_report_dir()

        assert "test-project" in str(report_dir)
        assert "reports" in str(report_dir)
        assert "bablib" in str(report_dir)

    def test_generate_report(self):
        """Test report generation."""
        reporter = ErrorReporter("test-project")

        # Add test data
        reporter.update_stats(total_pages=50, successful_pages=45, failed_pages=5)
        reporter.add_error("http://example.com/1", "NETWORK", "Error 1")
        reporter.add_error("http://example.com/2", "TIMEOUT", "Error 2")

        report = reporter.generate_report()

        assert report['report_id'] == reporter.report_id
        assert report['project_name'] == "test-project"
        assert report['status'] == 'PARTIAL'  # Has both successes and failures
        assert report['total_pages'] == 50
        assert report['successful_pages'] == 45
        assert report['failed_pages'] == 5
        assert len(report['errors']) == 2
        assert 'error_summary' in report
        assert report['error_summary']['total_errors'] == 2

    def test_status_determination(self):
        """Test correct status determination in reports."""
        # All success
        reporter1 = ErrorReporter("test1")
        reporter1.update_stats(total_pages=10, successful_pages=10, failed_pages=0)
        report1 = reporter1.generate_report()
        assert report1['status'] == 'SUCCESS'

        # All failed
        reporter2 = ErrorReporter("test2")
        reporter2.update_stats(total_pages=10, successful_pages=0, failed_pages=10)
        report2 = reporter2.generate_report()
        assert report2['status'] == 'FAILED'

        # Partial
        reporter3 = ErrorReporter("test3")
        reporter3.update_stats(total_pages=10, successful_pages=7, failed_pages=3)
        report3 = reporter3.generate_report()
        assert report3['status'] == 'PARTIAL'

    def test_error_summary_generation(self):
        """Test error summary statistics."""
        reporter = ErrorReporter("test-project")

        reporter.add_error("http://example.com/1", "NETWORK", "Error 1")
        reporter.add_error("http://example.com/2", "NETWORK", "Error 2")
        reporter.add_error("http://example.com/3", "TIMEOUT", "Error 3")
        reporter.add_error("http://example.com/1", "NETWORK", "Error 4")  # Duplicate URL

        summary = reporter._generate_error_summary()

        assert summary['total_errors'] == 4
        assert summary['by_type']['NETWORK'] == 3
        assert summary['by_type']['TIMEOUT'] == 1
        assert summary['unique_urls'] == 3  # Only 3 unique URLs

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_save_report(self, mock_mkdir, mock_file):
        """Test saving report to files."""
        reporter = ErrorReporter("test-project")
        reporter.add_error("http://example.com", "NETWORK", "Test error")

        json_path, text_path = reporter.save_report()

        # Should create directory
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)

        # Should write files
        assert mock_file.called
        # Check that both JSON and text files are written
        assert mock_file.call_count >= 2

    def test_human_report_format(self):
        """Test human-readable report formatting."""
        reporter = ErrorReporter("test-project")
        reporter.update_stats(total_pages=100, successful_pages=90, failed_pages=10)
        reporter.add_error("http://example.com", "NETWORK", "Connection failed", error_code=500)

        report = reporter.generate_report()
        formatted = reporter._format_human_report(report)

        assert "CRAWL REPORT" in formatted
        assert "test-project" in formatted
        assert "Total Pages: 100" in formatted
        assert "Successful: 90" in formatted
        assert "Failed: 10" in formatted
        assert "NETWORK" in formatted
        assert "Connection failed" in formatted
        assert "500" in formatted

    def test_has_errors(self):
        """Test error checking."""
        reporter = ErrorReporter("test-project")

        assert not reporter.has_errors()

        reporter.add_error("http://example.com", "NETWORK", "Error")
        assert reporter.has_errors()

    def test_get_error_count(self):
        """Test error counting."""
        reporter = ErrorReporter("test-project")

        assert reporter.get_error_count() == 0

        reporter.add_error("http://example.com/1", "NETWORK", "Error 1")
        reporter.add_error("http://example.com/2", "TIMEOUT", "Error 2")

        assert reporter.get_error_count() == 2

    def test_clear_errors(self):
        """Test clearing errors."""
        reporter = ErrorReporter("test-project")

        reporter.add_error("http://example.com", "NETWORK", "Error")
        assert len(reporter.errors) == 1

        reporter.clear_errors()
        assert len(reporter.errors) == 0