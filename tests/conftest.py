"""Test configuration and fixtures for Bablib tests."""

import asyncio
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import AsyncMock, Mock

import pytest
from click.testing import CliRunner

from src.core.config import BablibConfig
from src.services.database import DatabaseManager
from src.services.database_migrator import DatabaseMigrator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config(temp_dir: Path) -> BablibConfig:
    """Create test configuration with temporary directories."""
    config = BablibConfig(data_dir=temp_dir / "data")

    # Ensure directories exist
    config.data_dir.mkdir(exist_ok=True)

    return config


@pytest.fixture
def db_manager(test_config: BablibConfig) -> DatabaseManager:
    """Create database manager with test database."""
    manager = DatabaseManager(test_config)

    # Run migrations to ensure tables exist
    migrator = DatabaseMigrator(test_config)
    migrator.run_migrations()

    return manager


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI runner for testing Click commands."""
    return CliRunner(mix_stderr=False)


# Wizard testing fixtures
@pytest.fixture
def mock_wizard_session() -> Dict[str, Any]:
    """Create mock wizard session data."""
    return {
        "wizard_id": str(uuid.uuid4()),
        "wizard_type": "shelf",
        "target_entity": "test-shelf",
        "current_step": 1,
        "total_steps": 5,
        "collected_data": {},
        "start_time": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "is_complete": False
    }


@pytest.fixture
def mock_wizard_steps() -> List[Dict[str, Any]]:
    """Create mock wizard steps definition."""
    return [
        {
            "step_number": 1,
            "wizard_type": "shelf",
            "step_title": "Description",
            "prompt_text": "Enter shelf description (optional):",
            "input_type": "text",
            "choices": None,
            "validation_rules": ["max_length:500"],
            "is_optional": True,
            "depends_on": None
        },
        {
            "step_number": 2,
            "wizard_type": "shelf",
            "step_title": "Auto-fill Setting",
            "prompt_text": "Auto-fill empty boxes when accessed?",
            "input_type": "boolean",
            "choices": ["yes", "no"],
            "validation_rules": [],
            "is_optional": False,
            "depends_on": None
        },
        {
            "step_number": 3,
            "wizard_type": "shelf",
            "step_title": "Default Box Type",
            "prompt_text": "Default box type for new boxes:",
            "input_type": "choice",
            "choices": ["drag", "rag", "bag"],
            "validation_rules": [],
            "is_optional": False,
            "depends_on": None
        },
        {
            "step_number": 4,
            "wizard_type": "shelf",
            "step_title": "Tags",
            "prompt_text": "Add tags (comma-separated, optional):",
            "input_type": "text",
            "choices": None,
            "validation_rules": ["csv_format"],
            "is_optional": True,
            "depends_on": None
        },
        {
            "step_number": 5,
            "wizard_type": "shelf",
            "step_title": "Confirmation",
            "prompt_text": "Apply this configuration?",
            "input_type": "boolean",
            "choices": ["yes", "no"],
            "validation_rules": [],
            "is_optional": False,
            "depends_on": None
        }
    ]


@pytest.fixture
def mock_command_context() -> Dict[str, Any]:
    """Create mock command context data."""
    return {
        "entity_name": "test-shelf",
        "entity_type": "shelf",
        "entity_exists": False,
        "is_empty": None,
        "configuration_state": {
            "is_configured": False,
            "has_content": False,
            "configuration_version": "1.0",
            "setup_completed_at": None,
            "needs_migration": False
        },
        "last_modified": datetime.utcnow().isoformat(),
        "content_summary": None
    }


@pytest.fixture
def mock_configuration_state() -> Dict[str, Any]:
    """Create mock configuration state."""
    return {
        "is_configured": True,
        "has_content": True,
        "configuration_version": "1.0",
        "setup_completed_at": datetime.utcnow().isoformat(),
        "needs_migration": False
    }


@pytest.fixture
def mock_flag_definitions() -> List[Dict[str, Any]]:
    """Create mock flag definitions for testing."""
    return [
        {
            "long_form": "--init",
            "short_form": "-i",
            "flag_type": "boolean",
            "description": "Launch setup wizard",
            "choices": None,
            "default_value": "false",
            "is_global": True
        },
        {
            "long_form": "--verbose",
            "short_form": "-v",
            "flag_type": "boolean",
            "description": "Enable verbose output",
            "choices": None,
            "default_value": "false",
            "is_global": True
        },
        {
            "long_form": "--type",
            "short_form": "-t",
            "flag_type": "choice",
            "description": "Box type",
            "choices": '["drag", "rag", "bag"]',
            "default_value": None,
            "is_global": False
        }
    ]


# Context service mocks
@pytest.fixture
def mock_context_service():
    """Create mock context service."""
    service = Mock()

    async def check_shelf_exists(name: str):
        if name == "existing-shelf":
            return Mock(exists=True, is_empty=False, name=name)
        elif name == "empty-shelf":
            return Mock(exists=True, is_empty=True, name=name)
        else:
            return Mock(exists=False, is_empty=None, name=name)

    async def check_box_exists(name: str, shelf: Optional[str] = None):
        if name == "existing-box":
            return Mock(exists=True, is_empty=False, name=name, type="drag")
        elif name == "empty-box":
            return Mock(exists=True, is_empty=True, name=name, type="rag")
        else:
            return Mock(exists=False, is_empty=None, name=name, type=None)

    service.check_shelf_exists = AsyncMock(side_effect=check_shelf_exists)
    service.check_box_exists = AsyncMock(side_effect=check_box_exists)

    return service


@pytest.fixture
def mock_wizard_orchestrator():
    """Create mock wizard orchestrator."""
    orchestrator = Mock()

    async def start_wizard(wizard_type: str, target_entity: str):
        wizard_id = str(uuid.uuid4())
        return Mock(
            wizard_id=wizard_id,
            wizard_type=wizard_type,
            target_entity=target_entity,
            current_step=1,
            total_steps=5
        )

    async def process_step(wizard_id: str, response: Any):
        return Mock(
            accepted=True,
            validation_errors=[],
            next_step=Mock(number=2, title="Next Step"),
            is_complete=False
        )

    async def complete_wizard(wizard_id: str):
        return Mock(
            configuration_applied=True,
            entity_created=True,
            next_actions=[]
        )

    orchestrator.start_wizard = AsyncMock(side_effect=start_wizard)
    orchestrator.process_step = AsyncMock(side_effect=process_step)
    orchestrator.complete_wizard = AsyncMock(side_effect=complete_wizard)

    return orchestrator


@pytest.fixture
def mock_navigation_choices():
    """Create mock navigation choices for testing ArrowNavigator."""
    return [
        ("option1", "First Option", "Description for first option"),
        ("option2", "Second Option", "Description for second option"),
        ("option3", "Third Option", "Description for third option"),
    ]


# Database fixtures for testing
@pytest.fixture
def wizard_state_record():
    """Create a wizard state record for database testing."""
    return {
        "wizard_id": str(uuid.uuid4()),
        "wizard_type": "shelf",
        "target_entity": "test-shelf",
        "current_step": 1,
        "total_steps": 5,
        "collected_data": '{"description": "Test shelf"}',
        "start_time": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "is_complete": False
    }


@pytest.fixture
def command_context_record():
    """Create a command context record for database testing."""
    return {
        "entity_name": "test-context",
        "entity_type": "shelf",
        "entity_exists": True,
        "is_empty": False,
        "configuration_state": '{"is_configured": true, "has_content": true}',
        "last_modified": datetime.utcnow().isoformat(),
        "content_summary": "Test content summary",
        "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    }


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Create performance timer for testing response times."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        @property
        def duration(self) -> float:
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0.0

        def assert_under(self, max_seconds: float):
            assert self.duration < max_seconds, f"Operation took {self.duration}s, expected <{max_seconds}s"

    return Timer()


# Memory testing fixtures
@pytest.fixture
def memory_monitor():
    """Create memory monitor for testing memory usage."""
    import psutil
    import os

    class MemoryMonitor:
        def __init__(self):
            self.process = psutil.Process(os.getpid())
            self.baseline = None
            self.peak = None

        def start(self):
            self.baseline = self.process.memory_info().rss

        def update(self):
            current = self.process.memory_info().rss
            if self.peak is None or current > self.peak:
                self.peak = current

        @property
        def memory_used_mb(self) -> float:
            if self.baseline and self.peak:
                return (self.peak - self.baseline) / (1024 * 1024)
            return 0.0

        def assert_under(self, max_mb: float):
            assert self.memory_used_mb < max_mb, f"Memory usage {self.memory_used_mb}MB, expected <{max_mb}MB"

    return MemoryMonitor()


# Event loop fixture for async tests
@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Clean up fixture
@pytest.fixture(autouse=True)
def cleanup_wizard_sessions(db_manager: DatabaseManager):
    """Auto-cleanup wizard sessions after each test."""
    yield
    # Clean up any wizard sessions created during tests
    try:
        with sqlite3.connect(db_manager.config.database_path) as conn:
            conn.execute("DELETE FROM wizard_states WHERE start_time < datetime('now', '-1 hour')")
            conn.execute("DELETE FROM command_contexts WHERE expires_at < datetime('now')")
            conn.commit()
    except Exception:
        # Ignore cleanup errors in tests
        pass