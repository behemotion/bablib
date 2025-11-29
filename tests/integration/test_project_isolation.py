"""Integration tests for project isolation with SQLite-vec."""

import pytest
import asyncio
from pathlib import Path
from typing import List

from src.services.sqlite_vec_service import SQLiteVecService
from src.core.config import BablibConfig
from src.models.vector_store_types import VectorStoreProvider


class TestProjectIsolation:
    """Test that SQLite-vec maintains project isolation with separate databases."""

    @pytest.fixture
    async def sqlite_service(self, tmp_path):
        """Create and initialize SQLiteVecService."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )
        service = SQLiteVecService(config)
        await service.initialize()
        return service

    @pytest.mark.asyncio
    async def test_separate_database_files_per_project(self, sqlite_service, tmp_path):
        """Test that each project gets its own database file."""
        # Create multiple projects
        project_names = ["python-docs", "fastapi-docs", "pytorch-docs"]

        for project in project_names:
            await sqlite_service.create_collection(project)

            # Check database file exists
            db_path = tmp_path / "data" / "projects" / project / "vectors.db"
            assert db_path.exists(), f"Database file for {project} not created"

        # Verify separate files
        db_files = list((tmp_path / "data" / "projects").glob("*/vectors.db"))
        assert len(db_files) == len(project_names)

    @pytest.mark.asyncio
    async def test_no_cross_project_data_leakage(self, sqlite_service):
        """Test that data from one project doesn't appear in another."""
        # Create two projects
        await sqlite_service.create_collection("project_a")
        await sqlite_service.create_collection("project_b")

        # Add documents to project_a
        embedding_a = [0.1] * 1024
        await sqlite_service.upsert_document(
            collection="project_a",
            doc_id="doc_a_1",
            embedding=embedding_a,
            metadata={"project": "a", "content": "Project A document"},
        )

        # Add documents to project_b
        embedding_b = [0.2] * 1024
        await sqlite_service.upsert_document(
            collection="project_b",
            doc_id="doc_b_1",
            embedding=embedding_b,
            metadata={"project": "b", "content": "Project B document"},
        )

        # Search in project_a should only find project_a documents
        results_a = await sqlite_service.search(
            collection="project_a", query_embedding=embedding_a, limit=10
        )

        assert len(results_a) == 1
        assert results_a[0]["doc_id"] == "doc_a_1"
        assert results_a[0]["metadata"]["project"] == "a"

        # Search in project_b should only find project_b documents
        results_b = await sqlite_service.search(
            collection="project_b", query_embedding=embedding_b, limit=10
        )

        assert len(results_b) == 1
        assert results_b[0]["doc_id"] == "doc_b_1"
        assert results_b[0]["metadata"]["project"] == "b"

    @pytest.mark.asyncio
    async def test_concurrent_project_access(self, sqlite_service):
        """Test that multiple projects can be accessed concurrently."""
        projects = ["project_1", "project_2", "project_3"]

        # Create projects
        for project in projects:
            await sqlite_service.create_collection(project)

        # Define concurrent operations
        async def add_and_search(project: str, index: int):
            """Add a document and search for it."""
            embedding = [float(index) / 10] * 1024
            doc_id = f"{project}_doc_{index}"

            await sqlite_service.upsert_document(
                collection=project,
                doc_id=doc_id,
                embedding=embedding,
                metadata={"index": index},
            )

            results = await sqlite_service.search(
                collection=project, query_embedding=embedding, limit=1
            )

            return project, results

        # Run concurrent operations
        tasks = []
        for i, project in enumerate(projects):
            for j in range(3):  # 3 documents per project
                tasks.append(add_and_search(project, i * 10 + j))

        results = await asyncio.gather(*tasks)

        # Verify each operation succeeded and returned correct data
        for project, search_results in results:
            assert len(search_results) > 0
            assert project in search_results[0]["doc_id"]

    @pytest.mark.asyncio
    async def test_project_deletion_isolation(self, sqlite_service):
        """Test that deleting one project doesn't affect others."""
        # Create and populate multiple projects
        projects = ["keep_1", "delete_me", "keep_2"]

        for project in projects:
            await sqlite_service.create_collection(project)
            embedding = [0.5] * 1024
            await sqlite_service.upsert_document(
                collection=project,
                doc_id=f"{project}_doc",
                embedding=embedding,
                metadata={"project": project},
            )

        # Delete middle project
        await sqlite_service.delete_collection("delete_me")

        # Verify other projects still exist and have data
        for project in ["keep_1", "keep_2"]:
            stats = await sqlite_service.get_collection_stats(project)
            assert stats["vector_count"] == 1
            assert stats["name"] == project

            # Verify data still accessible
            results = await sqlite_service.search(
                collection=project, query_embedding=[0.5] * 1024, limit=1
            )
            assert len(results) == 1
            assert results[0]["metadata"]["project"] == project

    @pytest.mark.asyncio
    async def test_project_stats_isolation(self, sqlite_service):
        """Test that stats are correctly isolated per project."""
        # Create projects with different amounts of data
        test_data = [
            ("small_project", 5),
            ("medium_project", 50),
            ("large_project", 100),
        ]

        for project_name, doc_count in test_data:
            await sqlite_service.create_collection(project_name)

            # Add documents
            for i in range(doc_count):
                embedding = [float(i) / 1000] * 1024
                await sqlite_service.upsert_document(
                    collection=project_name,
                    doc_id=f"{project_name}_doc_{i}",
                    embedding=embedding,
                    metadata={"index": i},
                )

        # Verify stats for each project
        for project_name, expected_count in test_data:
            stats = await sqlite_service.get_collection_stats(project_name)
            assert stats["vector_count"] == expected_count
            assert stats["vector_dimensions"] == 1024
            assert stats["name"] == project_name

    @pytest.mark.asyncio
    async def test_project_name_sanitization(self, sqlite_service):
        """Test that project names are properly sanitized for file system."""
        # Test various problematic project names
        test_names = [
            ("project-with-dashes", "project_with_dashes"),
            ("Project.With.Dots", "project_with_dots"),
            ("project/with/slashes", "project_with_slashes"),
            ("project with spaces", "project_with_spaces"),
            ("UPPERCASE", "uppercase"),
        ]

        for input_name, expected_safe_name in test_names:
            await sqlite_service.create_collection(input_name)

            # Verify collection is accessible with original name
            stats = await sqlite_service.get_collection_stats(input_name)
            assert stats is not None

            # Add and retrieve data
            embedding = [0.3] * 1024
            await sqlite_service.upsert_document(
                collection=input_name,
                doc_id="test_doc",
                embedding=embedding,
                metadata={"name": input_name},
            )

            results = await sqlite_service.search(
                collection=input_name, query_embedding=embedding, limit=1
            )
            assert len(results) == 1
            assert results[0]["metadata"]["name"] == input_name