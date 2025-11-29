"""Performance tests for SQLite-vec search operations."""

import pytest
import time
import asyncio
import random
from typing import List

from src.services.sqlite_vec_service import SQLiteVecService
from src.core.config import BablibConfig
from src.models.vector_store_types import VectorStoreProvider


class TestSQLiteVecSearchPerformance:
    """Test that SQLite-vec search operations meet performance requirements."""

    @pytest.fixture
    async def populated_service(self, tmp_path):
        """Create service with populated test data."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        service = SQLiteVecService(config)
        await service.initialize()
        await service.create_collection("test_collection")

        # Populate with test data
        for i in range(1000):  # 1000 documents
            # Create somewhat random embeddings
            embedding = [random.random() for _ in range(1024)]
            await service.upsert_document(
                collection="test_collection",
                doc_id=f"doc_{i}",
                embedding=embedding,
                metadata={
                    "index": i,
                    "category": f"category_{i % 10}",
                    "content": f"Test document {i}"
                }
            )

        return service

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_search_under_100ms(self, populated_service):
        """Test that vector search completes in under 100ms."""
        service = populated_service

        # Generate query embedding
        query_embedding = [random.random() for _ in range(1024)]

        # Warm up (first query might be slower)
        await service.search("test_collection", query_embedding, limit=10)

        # Measure search time
        search_times = []
        for _ in range(10):  # Run 10 searches
            start_time = time.time()
            results = await service.search(
                collection="test_collection",
                query_embedding=query_embedding,
                limit=10
            )
            elapsed_time = time.time() - start_time
            search_times.append(elapsed_time * 1000)  # Convert to ms

            assert len(results) == 10
            assert all("doc_id" in r for r in results)
            assert all("score" in r for r in results)

        avg_time = sum(search_times) / len(search_times)
        max_time = max(search_times)
        min_time = min(search_times)

        print(f"\nSearch performance (1000 docs):")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")

        # Assert average search time is under 100ms
        assert avg_time < 100.0, f"Average search time {avg_time:.2f}ms exceeds 100ms limit"

        # Preferably under 50ms for 1000 documents
        if avg_time < 20.0:
            print("  ✓ Excellent performance")
        elif avg_time < 50.0:
            print("  ✓ Good performance")
        else:
            print("  ⚠️  Acceptable but could be optimized")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("num_results", [1, 5, 10, 20, 50])
    async def test_search_varying_limit(self, populated_service, num_results):
        """Test search performance with different result limits."""
        service = populated_service
        query_embedding = [random.random() for _ in range(1024)]

        # Measure search time
        times = []
        for _ in range(5):
            start_time = time.time()
            results = await service.search(
                collection="test_collection",
                query_embedding=query_embedding,
                limit=num_results
            )
            elapsed_ms = (time.time() - start_time) * 1000
            times.append(elapsed_ms)

            assert len(results) == num_results

        avg_time = sum(times) / len(times)

        # Performance should scale reasonably with limit
        expected_max = 100.0 + (num_results * 2)  # Base + overhead per result
        assert avg_time < expected_max, \
            f"Search for {num_results} results took {avg_time:.2f}ms"

        print(f"Search limit={num_results}: {avg_time:.2f}ms")

    @pytest.mark.asyncio
    async def test_search_scaling_with_collection_size(self, tmp_path):
        """Test how search performance scales with collection size."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        service = SQLiteVecService(config)
        await service.initialize()

        collection_sizes = [100, 500, 1000, 5000]
        search_times = {}

        for size in collection_sizes:
            collection_name = f"collection_{size}"
            await service.create_collection(collection_name)

            # Populate collection
            for i in range(size):
                embedding = [random.random() for _ in range(1024)]
                await service.upsert_document(
                    collection=collection_name,
                    doc_id=f"doc_{i}",
                    embedding=embedding,
                    metadata={"index": i}
                )

            # Measure search time
            query_embedding = [random.random() for _ in range(1024)]

            # Warm up
            await service.search(collection_name, query_embedding, limit=10)

            # Measure
            times = []
            for _ in range(5):
                start_time = time.time()
                await service.search(
                    collection=collection_name,
                    query_embedding=query_embedding,
                    limit=10
                )
                times.append((time.time() - start_time) * 1000)

            avg_time = sum(times) / len(times)
            search_times[size] = avg_time

            print(f"Collection size {size}: {avg_time:.2f}ms")

            # Even with 5000 documents, should be under 200ms
            if size <= 1000:
                assert avg_time < 100.0, f"Search in {size} docs took {avg_time:.2f}ms"
            else:
                assert avg_time < 200.0, f"Search in {size} docs took {avg_time:.2f}ms"

        # Check scaling is reasonable (not exponential)
        if len(search_times) >= 2:
            sizes = sorted(search_times.keys())
            for i in range(1, len(sizes)):
                prev_size = sizes[i-1]
                curr_size = sizes[i]
                size_ratio = curr_size / prev_size
                time_ratio = search_times[curr_size] / search_times[prev_size]

                # Time should not scale worse than O(n log n)
                assert time_ratio < size_ratio * 2, \
                    f"Poor scaling: {size_ratio}x size increase caused {time_ratio}x time increase"

    @pytest.mark.asyncio
    async def test_concurrent_search_performance(self, populated_service):
        """Test performance of concurrent search operations."""
        service = populated_service

        # Generate different query embeddings
        queries = [
            [random.random() for _ in range(1024)]
            for _ in range(10)
        ]

        start_time = time.time()

        # Run 10 searches concurrently
        tasks = [
            service.search("test_collection", query, limit=10)
            for query in queries
        ]
        results = await asyncio.gather(*tasks)

        elapsed_time = time.time() - start_time
        avg_time_per_search = (elapsed_time * 1000) / 10

        assert all(len(r) == 10 for r in results)

        print(f"\nConcurrent search performance:")
        print(f"  10 searches total: {elapsed_time*1000:.2f}ms")
        print(f"  Average per search: {avg_time_per_search:.2f}ms")

        # Concurrent searches should complete efficiently
        # Allow some overhead for concurrency
        assert avg_time_per_search < 150.0, \
            f"Concurrent searches too slow: {avg_time_per_search:.2f}ms average"

    @pytest.mark.asyncio
    async def test_first_search_performance(self, tmp_path):
        """Test performance of first search (cold cache)."""
        config = BablibConfig(
            database_path=str(tmp_path / "bablib.db"),
            data_dir=str(tmp_path / "data"),
            vector_store_provider=VectorStoreProvider.SQLITE_VEC,
        )

        service = SQLiteVecService(config)
        await service.initialize()
        await service.create_collection("cold_test")

        # Add test data
        for i in range(100):
            embedding = [random.random() for _ in range(1024)]
            await service.upsert_document(
                collection="cold_test",
                doc_id=f"doc_{i}",
                embedding=embedding,
                metadata={"index": i}
            )

        # Close and reopen to ensure cold cache
        await service.close()
        service = SQLiteVecService(config)
        await service.initialize()

        # Measure first search (cold)
        query_embedding = [random.random() for _ in range(1024)]

        start_time = time.time()
        results = await service.search(
            collection="cold_test",
            query_embedding=query_embedding,
            limit=10
        )
        cold_time = (time.time() - start_time) * 1000

        # Measure second search (warm)
        start_time = time.time()
        results = await service.search(
            collection="cold_test",
            query_embedding=query_embedding,
            limit=10
        )
        warm_time = (time.time() - start_time) * 1000

        print(f"\nCache performance:")
        print(f"  Cold search: {cold_time:.2f}ms")
        print(f"  Warm search: {warm_time:.2f}ms")
        print(f"  Speedup: {cold_time/warm_time:.1f}x")

        # Even cold search should be under 200ms for 100 documents
        assert cold_time < 200.0, f"Cold search took {cold_time:.2f}ms"
        assert warm_time < 100.0, f"Warm search took {warm_time:.2f}ms"