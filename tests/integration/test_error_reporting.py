"""Integration tests for error reporting functionality."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
from src.cli.main import main
from src.logic.crawler.analytics.reporter import ErrorReporter


class TestErrorReportingIntegration:
    """Integration tests for error reporting during crawl operations."""

    def test_error_report_generation(self):
        """Test that error reports are generated when crawl has errors."""
        runner = CliRunner()

        with patch('src.services.crawler.CrawlerService') as mock_crawler:
            with patch('logic.crawler.analytics.reporter.ErrorReporter') as mock_reporter:
                reporter_instance = MagicMock()
                mock_reporter.return_value = reporter_instance

                # Simulate errors
                reporter_instance.has_errors.return_value = True
                reporter_instance.get_error_count.return_value = 5
                reporter_instance.save_report.return_value = (
                    Path("/tmp/report.json"),
                    Path("/tmp/report.txt")
                )

                with patch('src.services.project_manager.ProjectManager') as mock_pm:
                    mock_pm.return_value.get_project.return_value = MagicMock()

                    result = runner.invoke(main, ["crawl", "test-project"])

                    # Report should be saved
                    assert reporter_instance.save_report.called

    def test_error_report_prompt(self):
        """Test that user is prompted to view error report."""
        runner = CliRunner()

        with patch('logic.crawler.analytics.reporter.ErrorReporter') as mock_reporter:
            reporter_instance = MagicMock()
            mock_reporter.return_value = reporter_instance

            reporter_instance.has_errors.return_value = True
            report_path = Path("/tmp/test-project/reports/report_20240126.txt")
            reporter_instance.save_report.return_value = (None, report_path)

            with patch('src.services.crawler.CrawlerService'):
                with patch('src.services.project_manager.ProjectManager') as mock_pm:
                    mock_pm.return_value.get_project.return_value = MagicMock()

                    result = runner.invoke(main, ["crawl", "test-project"])

                    # Should prompt to review errors
                    assert "error" in result.output.lower()
                    assert str(report_path) in result.output or "report" in result.output.lower()

    def test_error_collection_during_crawl(self):
        """Test that errors are collected during crawl operation."""
        runner = CliRunner()

        with patch('logic.crawler.analytics.reporter.ErrorReporter') as mock_reporter:
            reporter_instance = MagicMock()
            mock_reporter.return_value = reporter_instance

            errors_collected = []

            def collect_error(url, error_type, message, **kwargs):
                errors_collected.append({
                    'url': url,
                    'type': error_type,
                    'message': message
                })

            reporter_instance.add_error.side_effect = collect_error

            with patch('src.services.crawler.CrawlerService') as mock_crawler:
                # Simulate various errors
                async def crawl_with_errors(*args, **kwargs):
                    reporter_instance.add_error("http://example.com/1", "NETWORK", "Timeout")
                    reporter_instance.add_error("http://example.com/2", "PARSE", "Invalid HTML")
                    reporter_instance.add_error("http://example.com/3", "RATE_LIMIT", "Too many requests")

                mock_crawler.return_value.crawl = crawl_with_errors

                with patch('src.services.project_manager.ProjectManager') as mock_pm:
                    mock_pm.return_value.get_project.return_value = MagicMock()

                    result = runner.invoke(main, ["crawl", "test-project"])

                    # Errors should be collected
                    assert len(errors_collected) >= 3

    def test_error_report_formats(self):
        """Test that reports are saved in both JSON and text formats."""
        from src.logic.crawler.analytics.reporter import ErrorReporter

        reporter = ErrorReporter("test-project")

        # Add test errors
        reporter.add_error("http://example.com/1", "NETWORK", "Connection refused")
        reporter.add_error("http://example.com/2", "TIMEOUT", "Request timeout after 30s")

        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.mkdir'):
                json_path, text_path = reporter.save_report()

                # Should write both formats
                assert mock_file.call_count >= 2  # At least JSON and text

                # Check write calls
                write_calls = mock_file.return_value.write.call_args_list
                written_content = ''.join(str(call) for call in write_calls)

    def test_error_report_location(self):
        """Test that error reports are saved in correct location."""
        from src.logic.crawler.analytics.reporter import ErrorReporter
        from platformdirs import user_data_dir

        reporter = ErrorReporter("test-project")
        report_dir = reporter.get_report_dir()

        # Should be in project-specific directory
        assert "test-project" in str(report_dir)
        assert "reports" in str(report_dir)
        assert str(user_data_dir("bablib")) in str(report_dir)

    def test_error_summary_in_output(self):
        """Test that error summary is shown in CLI output."""
        runner = CliRunner()

        with patch('logic.crawler.analytics.reporter.ErrorReporter') as mock_reporter:
            reporter_instance = MagicMock()
            mock_reporter.return_value = reporter_instance

            reporter_instance.has_errors.return_value = True
            reporter_instance.get_error_count.return_value = 10
            reporter_instance.generate_report.return_value = {
                'error_summary': {
                    'total_errors': 10,
                    'by_type': {
                        'NETWORK': 5,
                        'TIMEOUT': 3,
                        'PARSE': 2
                    }
                }
            }

            with patch('src.services.crawler.CrawlerService'):
                with patch('src.services.project_manager.ProjectManager') as mock_pm:
                    mock_pm.return_value.get_project.return_value = MagicMock()

                    result = runner.invoke(main, ["crawl", "test-project"])

                    # Summary should be in output
                    assert "10" in result.output or "errors" in result.output.lower()

    def test_no_report_when_no_errors(self):
        """Test that no report is generated when crawl has no errors."""
        runner = CliRunner()

        with patch('logic.crawler.analytics.reporter.ErrorReporter') as mock_reporter:
            reporter_instance = MagicMock()
            mock_reporter.return_value = reporter_instance

            reporter_instance.has_errors.return_value = False
            reporter_instance.get_error_count.return_value = 0

            with patch('src.services.crawler.CrawlerService'):
                with patch('src.services.project_manager.ProjectManager') as mock_pm:
                    mock_pm.return_value.get_project.return_value = MagicMock()

                    result = runner.invoke(main, ["crawl", "test-project"])

                    # Should not save report
                    assert not reporter_instance.save_report.called

    def test_report_overwrite_on_recrawl(self):
        """Test that reports are overwritten on project recrawl."""
        from src.logic.crawler.analytics.reporter import ErrorReporter

        # First crawl
        reporter1 = ErrorReporter("test-project")
        reporter1.add_error("http://example.com/old", "NETWORK", "Old error")

        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.mkdir'):
                reporter1.save_report()

        # Second crawl (recrawl)
        reporter2 = ErrorReporter("test-project")
        reporter2.add_error("http://example.com/new", "TIMEOUT", "New error")

        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.mkdir'):
                json_path, text_path = reporter2.save_report()

                # Should save to latest files
                assert "latest" in str(json_path) or "latest" in str(text_path)

    def test_error_details_in_report(self):
        """Test that error reports contain all necessary details."""
        from src.logic.crawler.analytics.reporter import ErrorReporter

        reporter = ErrorReporter("test-project")

        # Add detailed error
        reporter.add_error(
            url="http://example.com/page",
            error_type="NETWORK",
            error_message="Connection timeout after 30 seconds",
            error_code=504,
            retry_count=3,
            include_traceback=True
        )

        report = reporter.generate_report()

        # Check report structure
        assert 'errors' in report
        assert len(report['errors']) == 1

        error = report['errors'][0]
        assert error['url'] == "http://example.com/page"
        assert error['error_type'] == "NETWORK"
        assert error['error_code'] == 504
        assert error['retry_count'] == 3
        assert 'timestamp' in error

    def test_error_report_with_stats(self):
        """Test that error report includes crawl statistics."""
        from src.logic.crawler.analytics.reporter import ErrorReporter

        reporter = ErrorReporter("test-project")
        reporter.update_stats(
            total_pages=100,
            successful_pages=85,
            failed_pages=15,
            embeddings_count=850
        )

        report = reporter.generate_report()

        # Check statistics
        assert report['total_pages'] == 100
        assert report['successful_pages'] == 85
        assert report['failed_pages'] == 15
        assert report['embeddings_count'] == 850
        assert 'duration_seconds' in report