"""Performance tests for SQLite-vec setup time."""

import pytest
import time
import asyncio
from pathlib import Path

from src.services.sqlite_vec_service import SQLiteVecService
from src.core.config import BablibConfig
from src.models.vector_store_types import VectorStoreProvider


class TestSQLiteVecSetupPerformance:
    """Test that SQLite-vec setup completes within performance requirements."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_setup_under_30_seconds(self, tmp_path):
        """Test that complete SQLite-vec setup takes less than 30 seconds."""
        start_time = time.time()

        # Initialize configuration
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        # Create service
        service = SQLiteVecService(config)

        # Initialize service
        await service.initialize()

        # Create multiple collections to simulate real setup
        collections = ["project1", "project2", "project3"]
        for collection in collections:
            await service.create_collection(collection)

        # Add some initial data to each collection
        test_embedding = [0.1] * 1024
        for collection in collections:
            for i in range(10):  # Add 10 documents per collection
                await service.upsert_document(
                    collection=collection,
                    doc_id=f"doc_{i}",
                    embedding=test_embedding,
                    metadata={"index": i}
                )

        elapsed_time = time.time() - start_time

        # Assert setup completed in under 30 seconds
        assert elapsed_time < 30.0, f"Setup took {elapsed_time:.2f}s, exceeds 30s limit"

        # Preferably under 10 seconds for local SQLite
        if elapsed_time < 10.0:
            print(f"✓ Excellent: Setup completed in {elapsed_time:.2f}s")
        elif elapsed_time < 20.0:
            print(f"✓ Good: Setup completed in {elapsed_time:.2f}s")
        else:
            print(f"⚠️  Slow: Setup took {elapsed_time:.2f}s")

    @pytest.mark.asyncio
    async def test_collection_creation_performance(self, tmp_path):
        """Test performance of creating multiple collections."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        service = SQLiteVecService(config)
        await service.initialize()

        # Measure time to create 10 collections
        start_time = time.time()

        tasks = []
        for i in range(10):
            tasks.append(service.create_collection(f"collection_{i}"))

        await asyncio.gather(*tasks)

        elapsed_time = time.time() - start_time

        # Should create 10 collections in under 5 seconds
        assert elapsed_time < 5.0, f"Creating 10 collections took {elapsed_time:.2f}s"

        # Calculate average per collection
        avg_time = elapsed_time / 10
        print(f"Average collection creation time: {avg_time*1000:.2f}ms")

    @pytest.mark.asyncio
    async def test_initialization_with_existing_data(self, tmp_path):
        """Test initialization performance with existing database."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        # First, create some data
        service = SQLiteVecService(config)
        await service.initialize()
        await service.create_collection("existing_data")

        # Add substantial data
        test_embedding = [0.1] * 1024
        for i in range(100):
            await service.upsert_document(
                collection="existing_data",
                doc_id=f"doc_{i}",
                embedding=test_embedding,
                metadata={"index": i}
            )

        await service.close()

        # Now measure re-initialization time
        start_time = time.time()

        service2 = SQLiteVecService(config)
        await service2.initialize()

        # Verify data is accessible
        stats = await service2.get_collection_stats("existing_data")
        assert stats["vector_count"] == 100

        elapsed_time = time.time() - start_time

        # Re-initialization should be very fast (<1 second)
        assert elapsed_time < 1.0, f"Re-initialization took {elapsed_time:.2f}s"
        print(f"Re-initialization time: {elapsed_time*1000:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_setup_operations(self, tmp_path):
        """Test performance of concurrent setup operations."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        service = SQLiteVecService(config)
        await service.initialize()

        start_time = time.time()

        # Simulate concurrent setup operations
        async def setup_project(name: str):
            await service.create_collection(name)
            test_embedding = [0.1] * 1024
            for i in range(5):
                await service.upsert_document(
                    collection=name,
                    doc_id=f"{name}_doc_{i}",
                    embedding=test_embedding,
                    metadata={"project": name}
                )
            return name

        # Setup 5 projects concurrently
        projects = [f"project_{i}" for i in range(5)]
        results = await asyncio.gather(*[setup_project(p) for p in projects])

        elapsed_time = time.time() - start_time

        assert len(results) == 5
        assert elapsed_time < 10.0, f"Concurrent setup took {elapsed_time:.2f}s"

        print(f"Concurrent setup of 5 projects: {elapsed_time:.2f}s")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("num_docs", [10, 50, 100, 500])
    async def test_batch_insert_performance(self, tmp_path, num_docs):
        """Test performance of batch document insertion."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        service = SQLiteVecService(config)
        await service.initialize()
        await service.create_collection("batch_test")

        test_embedding = [0.1] * 1024

        start_time = time.time()

        # Insert documents in batches
        batch_size = 100
        for i in range(0, num_docs, batch_size):
            batch_end = min(i + batch_size, num_docs)
            tasks = []
            for j in range(i, batch_end):
                tasks.append(
                    service.upsert_document(
                        collection="batch_test",
                        doc_id=f"doc_{j}",
                        embedding=test_embedding,
                        metadata={"index": j}
                    )
                )
            await asyncio.gather(*tasks)

        elapsed_time = time.time() - start_time

        # Performance expectations
        expected_times = {
            10: 1.0,
            50: 3.0,
            100: 5.0,
            500: 20.0
        }

        assert elapsed_time < expected_times[num_docs], \
            f"Inserting {num_docs} documents took {elapsed_time:.2f}s"

        throughput = num_docs / elapsed_time
        print(f"Insert {num_docs} docs: {elapsed_time:.2f}s ({throughput:.0f} docs/s)")