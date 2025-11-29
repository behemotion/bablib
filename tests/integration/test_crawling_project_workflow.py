"""
Integration test for crawling project workflow

Tests end-to-end crawling project operations including:
- Project creation with crawling type
- Web crawling configuration
- Integration with existing crawler logic
- Progress tracking and error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.logic.projects.core.project_manager import ProjectManager
from src.logic.projects.models.project import Project, ProjectType, ProjectStatus
from src.logic.projects.models.config import ProjectConfig
from src.logic.crawler.core.crawler import DocumentationCrawler
from src.logic.crawler.models.session import CrawlSession


@pytest.fixture
async def project_manager():
    """Create project manager for testing"""
    manager = ProjectManager()
    await manager.initialize()
    return manager


@pytest.fixture
def mock_crawler():
    """Create mock documentation crawler"""
    crawler = Mock(spec=DocumentationCrawler)
    crawler.crawl = AsyncMock()
    crawler.get_session_status = AsyncMock()
    return crawler


@pytest.mark.asyncio
async def test_crawling_project_creation(project_manager):
    """Test creating a crawling project with appropriate settings"""
    project_name = "test-crawling-project"
    project_type = ProjectType.CRAWLING

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=project_type
    )

    assert project is not None
    assert project.name == project_name
    assert project.type == ProjectType.CRAWLING
    assert project.status == ProjectStatus.ACTIVE

    # Verify crawling-specific settings
    config = await project_manager.get_project_config(project_name)
    assert config is not None
    assert "crawl_depth" in config.type_specific_settings
    assert "rate_limit" in config.type_specific_settings
    assert "user_agent" in config.type_specific_settings


@pytest.mark.asyncio
async def test_crawling_project_integration(project_manager, mock_crawler):
    """Test integration between project system and crawler logic"""
    project_name = "test-crawl-integration"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    # Get project handler
    project_handler = await project_manager.get_project_handler(project)

    # Mock successful crawl session
    mock_session = Mock(spec=CrawlSession)
    mock_session.session_id = "test-session-123"
    mock_session.status = "completed"
    mock_session.pages_crawled = 10
    mock_session.errors = []

    mock_crawler.crawl.return_value = mock_session

    # Start crawl operation
    with patch('src.logic.projects.types.crawling_project.DocumentationCrawler', return_value=mock_crawler):
        result = await project_handler.start_crawl(
            project=project,
            url="https://example.com/docs",
            depth=3
        )

    assert result.success is True
    assert result.operation_id == "test-session-123"
    mock_crawler.crawl.assert_called_once()


@pytest.mark.asyncio
async def test_crawling_project_settings_override(project_manager):
    """Test that crawling project settings properly override global defaults"""
    project_name = "test-crawl-settings"

    # Create crawling project with custom settings
    custom_settings = ProjectConfig(
        max_file_size=20971520,  # 20MB override
        allowed_formats=["html", "pdf", "txt", "md"],
        type_specific_settings={
            "crawl_depth": 5,
            "rate_limit": 0.5,
            "user_agent": "Bablib-Test/1.0",
            "follow_redirects": True,
            "max_pages": 100
        }
    )

    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING,
        config=custom_settings
    )

    # Verify settings were applied
    config = await project_manager.get_project_config(project_name)
    assert config.type_specific_settings["crawl_depth"] == 5
    assert config.type_specific_settings["rate_limit"] == 0.5
    assert config.type_specific_settings["user_agent"] == "Bablib-Test/1.0"


@pytest.mark.asyncio
async def test_crawling_progress_tracking(project_manager, mock_crawler):
    """Test progress tracking during crawling operations"""
    project_name = "test-crawl-progress"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    project_handler = await project_manager.get_project_handler(project)

    # Mock progressive crawl session updates
    progress_updates = []

    def mock_progress_callback(update):
        progress_updates.append(update)

    mock_session = Mock(spec=CrawlSession)
    mock_session.session_id = "progress-session-123"
    mock_session.status = "running"
    mock_session.pages_crawled = 0

    mock_crawler.crawl.return_value = mock_session

    # Mock session status updates
    status_responses = [
        {"pages_crawled": 5, "status": "running"},
        {"pages_crawled": 10, "status": "running"},
        {"pages_crawled": 15, "status": "completed"}
    ]
    mock_crawler.get_session_status.side_effect = status_responses

    # Start crawl with progress tracking
    with patch('src.logic.projects.types.crawling_project.DocumentationCrawler', return_value=mock_crawler):
        result = await project_handler.start_crawl(
            project=project,
            url="https://example.com/docs",
            depth=3,
            progress_callback=mock_progress_callback
        )

    assert result.success is True
    assert len(progress_updates) > 0


@pytest.mark.asyncio
async def test_crawling_error_handling(project_manager, mock_crawler):
    """Test error handling during crawling operations"""
    project_name = "test-crawl-errors"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    project_handler = await project_manager.get_project_handler(project)

    # Mock failed crawl session
    mock_session = Mock(spec=CrawlSession)
    mock_session.session_id = "error-session-123"
    mock_session.status = "failed"
    mock_session.pages_crawled = 2
    mock_session.errors = ["Connection timeout", "Invalid SSL certificate"]

    mock_crawler.crawl.return_value = mock_session

    # Start crawl operation that will fail
    with patch('src.logic.projects.types.crawling_project.DocumentationCrawler', return_value=mock_crawler):
        result = await project_handler.start_crawl(
            project=project,
            url="https://invalid-site.example",
            depth=3
        )

    assert result.success is False
    assert len(result.errors) > 0
    assert "Connection timeout" in result.errors


@pytest.mark.asyncio
async def test_crawling_project_cleanup(project_manager):
    """Test that crawling project cleanup removes crawl data"""
    project_name = "test-crawl-cleanup"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    # Verify project exists
    retrieved = await project_manager.get_project(project_name)
    assert retrieved is not None

    # Remove project
    success = await project_manager.remove_project(project_name)
    assert success is True

    # Verify project removed
    removed = await project_manager.get_project(project_name)
    assert removed is None

    # Verify crawl data cleanup occurred
    project_handler = await project_manager.get_project_handler(project)
    cleanup_success = await project_handler.verify_cleanup(project)
    assert cleanup_success is True


@pytest.mark.asyncio
async def test_crawling_rate_limiting(project_manager, mock_crawler):
    """Test that crawling respects rate limiting settings"""
    project_name = "test-rate-limiting"

    # Create crawling project with strict rate limiting
    custom_settings = ProjectConfig(
        type_specific_settings={
            "rate_limit": 2.0,  # 2 second delay between requests
            "crawl_depth": 2
        }
    )

    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING,
        config=custom_settings
    )

    project_handler = await project_manager.get_project_handler(project)

    # Mock crawler with timing tracking
    call_times = []

    async def mock_crawl_with_timing(*args, **kwargs):
        import time
        call_times.append(time.time())
        mock_session = Mock(spec=CrawlSession)
        mock_session.session_id = "rate-limit-session"
        mock_session.status = "completed"
        return mock_session

    mock_crawler.crawl.side_effect = mock_crawl_with_timing

    # Start crawl operation
    with patch('src.logic.projects.types.crawling_project.DocumentationCrawler', return_value=mock_crawler):
        await project_handler.start_crawl(
            project=project,
            url="https://example.com/docs",
            depth=2
        )

    # Verify rate limiting was applied (mock should be called with rate_limit setting)
    call_args = mock_crawler.crawl.call_args
    assert call_args is not None
    kwargs = call_args[1] if len(call_args) > 1 else {}
    assert kwargs.get("rate_limit") == 2.0


@pytest.mark.asyncio
async def test_crawling_project_stats(project_manager, mock_crawler):
    """Test retrieval of crawling project statistics"""
    project_name = "test-crawl-stats"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    project_handler = await project_manager.get_project_handler(project)

    # Mock completed crawl session
    mock_session = Mock(spec=CrawlSession)
    mock_session.session_id = "stats-session-123"
    mock_session.status = "completed"
    mock_session.pages_crawled = 25
    mock_session.total_size = 1048576  # 1MB
    mock_session.errors = []

    mock_crawler.crawl.return_value = mock_session

    # Start and complete crawl
    with patch('src.logic.projects.types.crawling_project.DocumentationCrawler', return_value=mock_crawler):
        await project_handler.start_crawl(
            project=project,
            url="https://example.com/docs",
            depth=3
        )

    # Get project statistics
    stats = await project_manager.get_project_stats(project_name)

    assert "pages_crawled" in stats
    assert "last_crawl_date" in stats
    assert "crawl_sessions" in stats
    assert stats["pages_crawled"] >= 0


@pytest.mark.asyncio
async def test_multiple_crawl_sessions(project_manager, mock_crawler):
    """Test handling multiple crawl sessions for same project"""
    project_name = "test-multiple-crawls"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    project_handler = await project_manager.get_project_handler(project)

    # Mock multiple crawl sessions
    session_ids = ["session-1", "session-2", "session-3"]

    for i, session_id in enumerate(session_ids):
        mock_session = Mock(spec=CrawlSession)
        mock_session.session_id = session_id
        mock_session.status = "completed"
        mock_session.pages_crawled = (i + 1) * 10

        mock_crawler.crawl.return_value = mock_session

        with patch('src.logic.projects.types.crawling_project.DocumentationCrawler', return_value=mock_crawler):
            result = await project_handler.start_crawl(
                project=project,
                url=f"https://example.com/docs/{i}",
                depth=2
            )

        assert result.success is True
        assert result.operation_id == session_id

    # Verify crawl history
    crawl_status = await project_handler.get_crawl_status(project)
    assert "session_history" in crawl_status
    assert len(crawl_status["session_history"]) == 3


@pytest.mark.asyncio
async def test_crawling_url_validation(project_manager):
    """Test URL validation for crawling projects"""
    project_name = "test-url-validation"

    # Create crawling project
    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.CRAWLING
    )

    project_handler = await project_manager.get_project_handler(project)

    # Test invalid URLs
    invalid_urls = [
        "not-a-url",
        "ftp://example.com",  # Wrong protocol
        "https://",  # Incomplete URL
        "http://localhost:99999",  # Invalid port
    ]

    for invalid_url in invalid_urls:
        with pytest.raises(ValueError, match="Invalid URL"):
            await project_handler.start_crawl(
                project=project,
                url=invalid_url,
                depth=1
            )

    # Test valid URL (should not raise)
    valid_url = "https://example.com/docs"
    # This would normally start a crawl, but we're just testing validation
    try:
        with patch('src.logic.projects.types.crawling_project.DocumentationCrawler') as mock_crawler_class:
            mock_crawler = Mock()
            mock_session = Mock(spec=CrawlSession)
            mock_session.session_id = "valid-session"
            mock_session.status = "completed"
            mock_crawler.crawl.return_value = mock_session
            mock_crawler_class.return_value = mock_crawler

            result = await project_handler.start_crawl(
                project=project,
                url=valid_url,
                depth=1
            )
            # If we get here, URL validation passed
            assert True
    except ValueError:
        pytest.fail("Valid URL should not raise ValueError")