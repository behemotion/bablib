"""CrawlingProject handler for web documentation crawling projects."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, List

from ...contracts.service_interfaces import CrawlingProjectContract
from ..models.config import ProjectConfig
from ..models.files import ValidationResult
from ..models.project import Project

logger = logging.getLogger(__name__)


class CrawlingProject(CrawlingProjectContract):
    """
    Handler for crawling projects that specialize in web documentation crawling.

    Integrates with the existing Bablib crawler functionality to provide
    project-specific crawling capabilities.
    """

    def __init__(self):
        """Initialize CrawlingProject handler."""
        pass

    async def initialize_project(self, project: Project) -> bool:
        """
        Initialize crawling project with required directories and configuration.

        Args:
            project: Project instance to initialize

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info(f"Initializing crawling project: {project.name}")

            project_dir = Path(project.get_project_directory())

            # Create project-specific directories
            directories = [
                project_dir / "crawl_data",
                project_dir / "pages",
                project_dir / "assets",
                project_dir / "logs"
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            # Create crawling configuration file
            crawl_config = {
                'project_name': project.name,
                'project_type': 'crawling',
                'settings': project.settings,
                'created_at': project.created_at.isoformat(),
                'status': 'initialized'
            }

            config_file = project_dir / "crawl_config.json"
            import json
            with open(config_file, 'w') as f:
                json.dump(crawl_config, f, indent=2)

            # Initialize database for crawl sessions
            await self._initialize_crawl_database(project)

            logger.info(f"Successfully initialized crawling project: {project.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize crawling project {project.name}: {e}")
            return False

    async def cleanup_project(self, project: Project) -> bool:
        """
        Clean up crawling project resources.

        Args:
            project: Project instance to clean up

        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            logger.info(f"Cleaning up crawling project: {project.name}")

            # Stop any active crawl operations
            await self._stop_active_crawls(project)

            # Archive crawl data if requested
            backup_enabled = project.settings.get('backup_on_cleanup', True)
            if backup_enabled:
                await self._archive_crawl_data(project)

            # Clean up temporary files
            project_dir = Path(project.get_project_directory())
            temp_dir = project_dir / "temp"
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info(f"Successfully cleaned up crawling project: {project.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup crawling project {project.name}: {e}")
            return False

    async def validate_settings(self, settings: ProjectConfig) -> ValidationResult:
        """
        Validate settings for crawling projects.

        Args:
            settings: ProjectConfig to validate

        Returns:
            ValidationResult indicating validation status
        """
        errors = []
        warnings = []

        # Required settings for crawling projects
        if settings.crawl_depth is None:
            errors.append("crawl_depth is required for crawling projects")
        elif not (1 <= settings.crawl_depth <= 10):
            errors.append("crawl_depth must be between 1 and 10")

        if settings.rate_limit is None:
            errors.append("rate_limit is required for crawling projects")
        elif settings.rate_limit <= 0:
            errors.append("rate_limit must be positive")

        # Validate allowed formats include HTML
        if settings.allowed_formats and 'html' not in settings.allowed_formats:
            warnings.append("HTML format should be included for effective web crawling")

        # Check for incompatible settings
        incompatible_settings = [
            'chunk_size', 'embedding_model', 'enable_compression', 'auto_tagging'
        ]
        for setting in incompatible_settings:
            if hasattr(settings, setting) and getattr(settings, setting) is not None:
                warnings.append(f"Setting '{setting}' is not used by crawling projects")

        # Validate user agent format
        if settings.user_agent and len(settings.user_agent) > 200:
            errors.append("user_agent cannot exceed 200 characters")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    async def get_default_settings(self) -> ProjectConfig:
        """
        Get default settings for crawling projects.

        Returns:
            ProjectConfig with crawling-specific defaults
        """
        return ProjectConfig(
            max_file_size=10485760,  # 10MB
            allowed_formats=['html', 'pdf', 'txt', 'md', 'rst'],
            crawl_depth=3,
            rate_limit=1.0,
            user_agent='Bablib/1.0',
            follow_redirects=True,
            respect_robots_txt=True,
            concurrent_uploads=3,
            retry_attempts=3,
            timeout_seconds=30
        )

    async def start_crawl(
        self,
        project: Project,
        url: str,
        depth: int,
        progress_callback: Callable[[dict[str, Any]], None] | None = None
    ) -> dict[str, Any]:
        """
        Start web crawling operation for the project.

        Args:
            project: Project instance
            url: Starting URL for crawling
            depth: Maximum crawl depth
            progress_callback: Optional progress callback

        Returns:
            Dictionary with crawl operation details

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If crawl operation fails to start
        """
        logger.info(f"Starting crawl for project {project.name}: {url}")

        # Validate parameters
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError("Invalid URL provided")

        if not (1 <= depth <= 10):
            raise ValueError("Crawl depth must be between 1 and 10")

        try:
            # Import crawler from existing logic
            from ...crawler.core.crawler import DocumentationCrawler

            # Create crawler instance with project-specific settings
            crawler_config = {
                'max_depth': depth,
                'rate_limit': project.settings.get('rate_limit', 1.0),
                'user_agent': project.settings.get('user_agent', 'Bablib/1.0'),
                'respect_robots_txt': project.settings.get('respect_robots_txt', True),
                'follow_redirects': project.settings.get('follow_redirects', True),
                'output_directory': str(Path(project.get_project_directory()) / "crawl_data")
            }

            crawler = DocumentationCrawler(**crawler_config)

            # Start crawl operation
            crawl_session_id = await crawler.start_crawl(
                url=url,
                project_name=project.name,
                progress_callback=progress_callback
            )

            # Record crawl session in project
            await self._record_crawl_session(project, {
                'session_id': crawl_session_id,
                'start_url': url,
                'max_depth': depth,
                'started_at': project.updated_at.isoformat(),
                'status': 'active',
                'config': crawler_config
            })

            return {
                'success': True,
                'session_id': crawl_session_id,
                'start_url': url,
                'max_depth': depth,
                'estimated_pages': self._estimate_pages_to_crawl(depth),
                'status': 'started'
            }

        except Exception as e:
            logger.error(f"Failed to start crawl for project {project.name}: {e}")
            raise RuntimeError(f"Crawl operation failed to start: {e}")

    async def get_crawl_status(self, project: Project) -> dict[str, Any]:
        """
        Get crawling operation status for the project.

        Args:
            project: Project instance

        Returns:
            Dictionary containing crawl status information
        """
        try:
            # Load active crawl sessions
            sessions = await self._load_crawl_sessions(project)
            active_sessions = [s for s in sessions if s.get('status') == 'active']

            # Get overall project crawl statistics
            project_dir = Path(project.get_project_directory())
            crawl_data_dir = project_dir / "crawl_data"

            stats = {
                'project_name': project.name,
                'active_sessions': len(active_sessions),
                'total_sessions': len(sessions),
                'pages_crawled': 0,
                'total_size': 0,
                'last_crawl': None,
                'status': 'idle'
            }

            # Count crawled pages and calculate size
            if crawl_data_dir.exists():
                for file_path in crawl_data_dir.rglob('*.html'):
                    stats['pages_crawled'] += 1
                    stats['total_size'] += file_path.stat().st_size

            # Get last crawl session info
            if sessions:
                last_session = max(sessions, key=lambda s: s.get('started_at', ''))
                stats['last_crawl'] = last_session.get('started_at')
                if active_sessions:
                    stats['status'] = 'crawling'

            # Add active session details
            if active_sessions:
                stats['active_sessions_details'] = active_sessions

            return stats

        except Exception as e:
            logger.error(f"Failed to get crawl status for project {project.name}: {e}")
            return {
                'project_name': project.name,
                'error': str(e),
                'status': 'error'
            }

    async def get_project_stats(self, project: Project) -> dict[str, Any]:
        """
        Get project-specific statistics for crawling projects.

        Args:
            project: Project instance

        Returns:
            Dictionary containing project statistics
        """
        try:
            project_dir = Path(project.get_project_directory())

            stats = {
                'type_specific_stats': {
                    'pages_crawled': 0,
                    'unique_domains': 0,
                    'total_links': 0,
                    'crawl_sessions': 0,
                    'avg_page_size': 0,
                    'largest_page': 0
                }
            }

            # Count pages and analyze content
            crawl_data_dir = project_dir / "crawl_data"
            if crawl_data_dir.exists():
                page_sizes = []
                domains = set()

                for file_path in crawl_data_dir.rglob('*.html'):
                    stats['type_specific_stats']['pages_crawled'] += 1
                    file_size = file_path.stat().st_size
                    page_sizes.append(file_size)

                    # Extract domain from filename or metadata
                    # This is a simplified approach
                    filename = file_path.name
                    if '_' in filename:
                        domain_part = filename.split('_')[0]
                        domains.add(domain_part)

                if page_sizes:
                    stats['type_specific_stats']['avg_page_size'] = sum(page_sizes) // len(page_sizes)
                    stats['type_specific_stats']['largest_page'] = max(page_sizes)

                stats['type_specific_stats']['unique_domains'] = len(domains)

            # Get crawl session count
            sessions = await self._load_crawl_sessions(project)
            stats['type_specific_stats']['crawl_sessions'] = len(sessions)

            return stats

        except Exception as e:
            logger.error(f"Failed to get project stats for {project.name}: {e}")
            return {'type_specific_stats': {}}

    # Private helper methods

    async def _initialize_crawl_database(self, project: Project) -> None:
        """Initialize database for crawl session tracking."""
        # In a real implementation, this would create database tables
        # For now, create a simple JSON file for session storage
        sessions_file = Path(project.get_project_directory()) / "crawl_sessions.json"
        if not sessions_file.exists():
            import json
            with open(sessions_file, 'w') as f:
                json.dump([], f)

    async def _stop_active_crawls(self, project: Project) -> None:
        """Stop any active crawl operations for the project."""
        try:
            # In a real implementation, this would coordinate with the crawler
            # to stop active operations
            sessions = await self._load_crawl_sessions(project)
            active_sessions = [s for s in sessions if s.get('status') == 'active']

            for session in active_sessions:
                session['status'] = 'stopped'
                session['stopped_at'] = project.updated_at.isoformat()

            await self._save_crawl_sessions(project, sessions)

        except Exception as e:
            logger.warning(f"Failed to stop active crawls for project {project.name}: {e}")

    async def _archive_crawl_data(self, project: Project) -> None:
        """Archive crawl data before cleanup."""
        try:
            import shutil
            from datetime import datetime

            project_dir = Path(project.get_project_directory())
            crawl_data_dir = project_dir / "crawl_data"

            if crawl_data_dir.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_name = f"{project.name}_crawl_data_{timestamp}"
                archive_path = project_dir / f"{archive_name}.tar.gz"

                # Create archive
                shutil.make_archive(
                    str(project_dir / archive_name),
                    'gztar',
                    str(crawl_data_dir)
                )

                logger.info(f"Archived crawl data to: {archive_path}")

        except Exception as e:
            logger.warning(f"Failed to archive crawl data for project {project.name}: {e}")

    async def _record_crawl_session(self, project: Project, session_data: dict[str, Any]) -> None:
        """Record a crawl session in project data."""
        try:
            sessions = await self._load_crawl_sessions(project)
            sessions.append(session_data)
            await self._save_crawl_sessions(project, sessions)

        except Exception as e:
            logger.error(f"Failed to record crawl session for project {project.name}: {e}")

    async def _load_crawl_sessions(self, project: Project) -> List[dict[str, Any]]:
        """Load crawl sessions from project data."""
        try:
            sessions_file = Path(project.get_project_directory()) / "crawl_sessions.json"
            if sessions_file.exists():
                import json
                with open(sessions_file) as f:
                    return json.load(f)
            return []

        except Exception as e:
            logger.error(f"Failed to load crawl sessions for project {project.name}: {e}")
            return []

    async def _save_crawl_sessions(self, project: Project, sessions: List[dict[str, Any]]) -> None:
        """Save crawl sessions to project data."""
        try:
            sessions_file = Path(project.get_project_directory()) / "crawl_sessions.json"
            import json
            with open(sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save crawl sessions for project {project.name}: {e}")

    def _estimate_pages_to_crawl(self, depth: int) -> int:
        """Estimate number of pages to crawl based on depth."""
        # Simple estimation: assume average of 10 links per page
        return min(10 ** depth, 1000)  # Cap at 1000 pages

    def __str__(self) -> str:
        """String representation of CrawlingProject handler."""
        return "CrawlingProject(web documentation crawling)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return "CrawlingProject(type=crawling, capabilities=[web_crawling, link_extraction, content_processing])"


# Import List type for type hints
