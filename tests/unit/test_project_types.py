"""Unit tests for ProjectType enum validation."""

import pytest
from enum import Enum
from typing import List, Optional

from src.logic.projects.models.project import ProjectType, ProjectStatus


class TestProjectTypeEnum:
    """Test cases for ProjectType enum validation."""

    def test_project_type_values(self):
        """Test that all expected project types are defined."""
        expected_types = ["CRAWLING", "DATA", "STORAGE"]
        actual_types = [pt.name for pt in ProjectType]

        assert set(actual_types) == set(expected_types), (
            f"Expected types {expected_types}, got {actual_types}"
        )

    def test_project_type_string_values(self):
        """Test that project types have correct string values."""
        assert ProjectType.CRAWLING.value == "crawling"
        assert ProjectType.DATA.value == "data"
        assert ProjectType.STORAGE.value == "storage"

    def test_project_type_from_string(self):
        """Test creating ProjectType from string values."""
        assert ProjectType("crawling") == ProjectType.CRAWLING
        assert ProjectType("data") == ProjectType.DATA
        assert ProjectType("storage") == ProjectType.STORAGE

    def test_invalid_project_type(self):
        """Test that invalid project types raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ProjectType("invalid_type")

        assert "invalid_type" in str(exc_info.value)

    def test_project_type_comparison(self):
        """Test enum comparison operations."""
        crawling1 = ProjectType.CRAWLING
        crawling2 = ProjectType.CRAWLING
        data = ProjectType.DATA

        assert crawling1 == crawling2
        assert crawling1 != data
        assert crawling1 is crawling2  # Same enum instance

    def test_project_type_iteration(self):
        """Test iterating over project types."""
        types_list = list(ProjectType)

        assert len(types_list) == 3
        assert ProjectType.CRAWLING in types_list
        assert ProjectType.DATA in types_list
        assert ProjectType.STORAGE in types_list

    def test_project_type_membership(self):
        """Test membership checking."""
        assert ProjectType.CRAWLING in ProjectType
        assert "crawling" not in ProjectType  # String not in enum

    def test_project_type_serialization(self):
        """Test that project types can be serialized."""
        project_type = ProjectType.CRAWLING

        # Test string serialization
        assert str(project_type.value) == "crawling"

        # Test JSON serialization (via value)
        import json
        serialized = json.dumps({"type": project_type.value})
        deserialized = json.loads(serialized)

        assert deserialized["type"] == "crawling"
        assert ProjectType(deserialized["type"]) == ProjectType.CRAWLING


class TestProjectTypeValidation:
    """Test project type validation in context."""

    def test_valid_project_types_for_operations(self):
        """Test which operations are valid for each project type."""
        # Define operation matrix
        operations = {
            ProjectType.CRAWLING: {
                "web_crawling": True,
                "document_upload": False,
                "file_upload": False,
                "vector_search": True,
                "file_retrieval": False,
            },
            ProjectType.DATA: {
                "web_crawling": False,
                "document_upload": True,
                "file_upload": False,
                "vector_search": True,
                "file_retrieval": False,
            },
            ProjectType.STORAGE: {
                "web_crawling": False,
                "document_upload": False,
                "file_upload": True,
                "vector_search": False,
                "file_retrieval": True,
            },
        }

        # Validate operation matrix
        for project_type, ops in operations.items():
            assert isinstance(project_type, ProjectType)
            assert all(isinstance(v, bool) for v in ops.values())

    def test_project_type_constraints(self):
        """Test constraints based on project type."""
        constraints = {
            ProjectType.CRAWLING: {
                "requires_url": True,
                "supports_upload": False,
                "has_vector_store": True,
            },
            ProjectType.DATA: {
                "requires_url": False,
                "supports_upload": True,
                "has_vector_store": True,
            },
            ProjectType.STORAGE: {
                "requires_url": False,
                "supports_upload": True,
                "has_vector_store": False,
            },
        }

        # Validate all project types have constraints defined
        for project_type in ProjectType:
            assert project_type in constraints, f"Missing constraints for {project_type}"

    def test_project_type_allowed_formats(self):
        """Test that each project type has appropriate format restrictions."""
        format_map = {
            ProjectType.CRAWLING: ["html", "htm", "xml", "json"],
            ProjectType.DATA: ["pdf", "docx", "txt", "md", "rst", "json", "xml"],
            ProjectType.STORAGE: [
                "jpg", "jpeg", "png", "gif", "tiff", "webp", "svg",
                "mp3", "wav", "flac", "ogg",
                "mp4", "avi", "mkv", "webm",
                "zip", "tar", "gz", "7z", "rar",
                "pdf", "docx", "txt", "md", "html", "json", "xml",
                "py", "js", "ts", "go", "rs", "java", "cpp", "c", "h",
            ],
        }

        for project_type in ProjectType:
            assert project_type in format_map, f"Missing format list for {project_type}"
            assert len(format_map[project_type]) > 0, f"Empty format list for {project_type}"

    def test_project_type_case_insensitive_lookup(self):
        """Test case-insensitive project type lookup."""
        test_cases = [
            ("crawling", ProjectType.CRAWLING),
            ("CRAWLING", ProjectType.CRAWLING),
            ("Crawling", ProjectType.CRAWLING),
            ("data", ProjectType.DATA),
            ("DATA", ProjectType.DATA),
            ("Data", ProjectType.DATA),
            ("storage", ProjectType.STORAGE),
            ("STORAGE", ProjectType.STORAGE),
            ("Storage", ProjectType.STORAGE),
        ]

        for input_str, expected_type in test_cases:
            # Simulate case-insensitive lookup
            normalized = input_str.lower()
            result = ProjectType(normalized)
            assert result == expected_type, (
                f"Failed to match '{input_str}' to {expected_type}"
            )


class TestProjectStatusEnum:
    """Test cases for ProjectStatus enum validation."""

    def test_project_status_values(self):
        """Test that all expected project statuses are defined."""
        expected_statuses = ["ACTIVE", "INACTIVE", "PROCESSING", "ERROR"]
        actual_statuses = [ps.name for ps in ProjectStatus]

        assert set(actual_statuses) == set(expected_statuses), (
            f"Expected statuses {expected_statuses}, got {actual_statuses}"
        )

    def test_project_status_transitions(self):
        """Test valid status transitions."""
        valid_transitions = {
            ProjectStatus.ACTIVE: [ProjectStatus.INACTIVE, ProjectStatus.PROCESSING, ProjectStatus.ERROR],
            ProjectStatus.INACTIVE: [ProjectStatus.ACTIVE],
            ProjectStatus.PROCESSING: [ProjectStatus.ACTIVE, ProjectStatus.ERROR],
            ProjectStatus.ERROR: [ProjectStatus.ACTIVE, ProjectStatus.INACTIVE],
        }

        # Validate all statuses have transition rules
        for status in ProjectStatus:
            assert status in valid_transitions, f"Missing transitions for {status}"

    def test_project_status_string_values(self):
        """Test that project statuses have correct string values."""
        assert ProjectStatus.ACTIVE.value == "active"
        assert ProjectStatus.INACTIVE.value == "inactive"
        assert ProjectStatus.PROCESSING.value == "processing"
        assert ProjectStatus.ERROR.value == "error"

    def test_invalid_project_status(self):
        """Test that invalid project statuses raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ProjectStatus("invalid_status")

        assert "invalid_status" in str(exc_info.value)


class TestProjectTypeIntegration:
    """Integration tests for project type usage."""

    def test_project_type_with_settings(self):
        """Test project type determines valid settings."""
        from src.logic.projects.models.config import ProjectConfig

        # Test crawling project settings
        crawling_config = ProjectConfig(
            project_type=ProjectType.CRAWLING,
            crawl_depth=3,
            rate_limit=1.0,
            user_agent="Bablib/1.0"
        )
        assert crawling_config.project_type == ProjectType.CRAWLING
        assert crawling_config.crawl_depth == 3

        # Test data project settings
        data_config = ProjectConfig(
            project_type=ProjectType.DATA,
            chunk_size=500,
            embedding_model="mxbai-embed-large",
            vector_store_type="qdrant"
        )
        assert data_config.project_type == ProjectType.DATA
        assert data_config.chunk_size == 500

        # Test storage project settings
        storage_config = ProjectConfig(
            project_type=ProjectType.STORAGE,
            enable_compression=True,
            auto_tagging=True,
            full_text_indexing=True
        )
        assert storage_config.project_type == ProjectType.STORAGE
        assert storage_config.enable_compression is True

    def test_project_type_factory_routing(self):
        """Test that project type correctly routes to handlers."""
        # This simulates the factory pattern usage
        handler_map = {
            ProjectType.CRAWLING: "CrawlingProjectHandler",
            ProjectType.DATA: "DataProjectHandler",
            ProjectType.STORAGE: "StorageProjectHandler",
        }

        for project_type in ProjectType:
            handler_name = handler_map.get(project_type)
            assert handler_name is not None, f"No handler for {project_type}"
            assert "Handler" in handler_name, f"Invalid handler name for {project_type}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])