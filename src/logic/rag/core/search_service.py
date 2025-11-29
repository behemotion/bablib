"""Enhanced RAG search service with Phase 1 improvements."""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger
from src.logic.rag.analytics.rag_metrics import RAGMetrics
from src.logic.rag.analytics.quality_metrics import RAGQualityMetrics
from src.logic.rag.core.chunking_service import ChunkingService
from src.logic.rag.core.reranking_service import RerankingService
from src.logic.rag.models.chunk import Chunk
from src.logic.rag.models.document import Document
from src.logic.rag.models.search_result import SearchResult
from src.logic.rag.models.strategy_config import ChunkStrategy, SearchStrategy
from src.logic.rag.strategies.fusion_retrieval import FusionRetrieval
from src.logic.rag.strategies.query_transformer import QueryTransformer
from src.services.embeddings import EmbeddingError, EmbeddingService
from src.services.vector_store import VectorStoreError, VectorStoreService


class RAGError(Exception):
    """RAG service operation error."""

    pass


class RAGSearchService:
    """Enhanced RAG search service with parallel queries and fast reranking."""

    def __init__(
        self,
        vector_store: VectorStoreService,
        embedding_service: EmbeddingService,
        config: BablibConfig | None = None,
        enable_metrics: bool = True,
    ):
        """Initialize enhanced RAG search service.

        Args:
            vector_store: Vector store service
            embedding_service: Embedding service
            config: Bablib configuration
            enable_metrics: Enable performance and quality metrics tracking
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.config = config or BablibConfig()
        self.logger = get_component_logger("rag")

        # Initialize new services
        self.chunking_service = ChunkingService(embedding_service)
        self.reranking_service = RerankingService()
        self.query_transformer = QueryTransformer()
        self.fusion_retrieval = FusionRetrieval()

        # Initialize metrics (Phase 3)
        self.metrics = RAGMetrics() if enable_metrics else None
        self.quality_metrics = RAGQualityMetrics() if enable_metrics else None

        # Search configuration
        self.default_limit = 10
        self.default_score_threshold = 0.7

        # Query cache (5-minute TTL)
        self._query_cache: dict[str, tuple[list[SearchResult], datetime]] = {}
        self._cache_ttl = 300

    async def search(
        self,
        query: str,
        collection_name: str,
        limit: int = 10,
        strategy: SearchStrategy = SearchStrategy.SEMANTIC,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
        transform_query: bool = False,
        rerank: bool = False,
    ) -> list[SearchResult]:
        """Execute search with specified strategy.

        Args:
            query: Search query string
            collection_name: Collection to search
            limit: Maximum results to return
            strategy: Search strategy enum
            score_threshold: Minimum similarity score
            filters: Metadata filters
            transform_query: Enable query transformation (Phase 2)
            rerank: Enable fast reranking

        Returns:
            List of SearchResult objects
        """
        if not query.strip():
            self.logger.warning("Empty query provided")
            return []

        start_time = datetime.now()

        try:
            # Check cache
            cache_key = self._get_cache_key(query, collection_name, limit, strategy)
            if cache_key in self._query_cache:
                cached_results, cached_time = self._query_cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                    self.logger.debug(
                        "Cache hit for query", extra={"query": query[:50]}
                    )
                    return cached_results

            # PHASE 2: Query transformation
            if transform_query:
                results = await self._search_with_query_transformation(
                    query, collection_name, limit, strategy, score_threshold, filters, rerank
                )
            else:
                # Execute search based on strategy (normal path)
                results = await self._execute_search_strategy(
                    query, collection_name, limit, strategy, score_threshold, filters
                )

                # PHASE 1: Fast reranking
                if rerank and len(results) > 1:
                    results = await self.reranking_service.rerank(query, results)

            # Cache results
            self._query_cache[cache_key] = (results, datetime.now())

            took_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.info(
                "Search completed",
                extra={
                    "query": query[:50],
                    "strategy": strategy.value,
                    "results_count": len(results),
                    "took_ms": took_ms,
                },
            )

            # PHASE 3: Record metrics
            if self.metrics:
                cache_hit = cache_key in self._query_cache and (datetime.now() - self._query_cache[cache_key][1]).total_seconds() < self._cache_ttl
                self.metrics.record_search(
                    strategy=strategy.value,
                    latency_ms=took_ms,
                    result_count=len(results),
                    query=query,
                    cache_hit=cache_hit
                )

            return results

        except Exception as e:
            self.logger.error(
                "Search failed",
                extra={"query": query[:50], "strategy": strategy.value, "error": str(e)},
            )
            raise RAGError(f"Search failed: {e}")

    async def _execute_search_strategy(
        self,
        query: str,
        collection_name: str,
        limit: int,
        strategy: SearchStrategy,
        score_threshold: float | None,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Execute search with specified strategy (internal).

        Args:
            query: Search query
            collection_name: Collection to search
            limit: Max results
            strategy: Search strategy
            score_threshold: Min score
            filters: Metadata filters

        Returns:
            List of search results
        """
        # Execute search based on strategy
        if strategy == SearchStrategy.SEMANTIC:
            results = await self._semantic_search(
                query, collection_name, limit, score_threshold, filters
            )
        elif strategy == SearchStrategy.HYBRID:
            results = await self._hybrid_search(
                query, collection_name, limit, score_threshold, filters
            )
        elif strategy == SearchStrategy.ADVANCED:
            # PHASE 1: Parallel sub-query execution
            results = await self._advanced_search_parallel(
                query, collection_name, limit, score_threshold, filters
            )
        elif strategy == SearchStrategy.FUSION:
            # PHASE 2: Fusion retrieval
            results = await self.fusion_retrieval.fuse_results(
                query=query,
                collection_name=collection_name,
                search_executor=self,
                limit=limit,
            )
        else:
            raise RAGError(f"Unknown search strategy: {strategy}")

        return results

    async def _search_with_query_transformation(
        self,
        query: str,
        collection_name: str,
        limit: int,
        strategy: SearchStrategy,
        score_threshold: float | None,
        filters: dict[str, Any] | None,
        rerank: bool,
    ) -> list[SearchResult]:
        """Execute search with query transformation (Phase 2).

        Generates multiple query variations and executes them in parallel,
        then fuses results using reciprocal rank fusion.

        Args:
            query: Original query
            collection_name: Collection to search
            limit: Max results per query
            strategy: Search strategy
            score_threshold: Min score
            filters: Metadata filters
            rerank: Enable reranking

        Returns:
            Fused results from all query variations
        """
        # Generate query variations
        query_variations = await self.query_transformer.transform_query(query)

        self.logger.info(
            f"Generated {len(query_variations)} query variations",
            extra={"original": query[:50], "variations_count": len(query_variations)},
        )

        # Execute searches in parallel for all variations
        search_tasks = [
            self._execute_search_strategy(
                variation, collection_name, limit, strategy, score_threshold, filters
            )
            for variation in query_variations
        ]

        all_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Collect successful results
        all_results: list[SearchResult] = []
        for i, results in enumerate(all_results_lists):
            if isinstance(results, Exception):
                self.logger.warning(
                    f"Query variation {i} failed: {results}",
                    extra={"variation": query_variations[i][:50]},
                )
                continue
            all_results.extend(results)

        # Remove duplicates and fuse by document ID (simple RRF)
        fused_results = self._fuse_results_simple(all_results, limit)

        # Apply reranking if requested
        if rerank and len(fused_results) > 1:
            fused_results = await self.reranking_service.rerank(query, fused_results)

        return fused_results

    def _fuse_results_simple(
        self, results: list[SearchResult], limit: int
    ) -> list[SearchResult]:
        """Simple result fusion by averaging scores for duplicate documents.

        Args:
            results: All search results from variations
            limit: Max results to return

        Returns:
            Fused and deduplicated results
        """
        # Group by document ID
        doc_results: dict[str, list[SearchResult]] = {}
        for result in results:
            if result.id not in doc_results:
                doc_results[result.id] = []
            doc_results[result.id].append(result)

        # Fuse by averaging scores
        fused = []
        for doc_id, doc_result_list in doc_results.items():
            # Take first result and average scores
            avg_score = sum(r.score for r in doc_result_list) / len(doc_result_list)
            fused_result = doc_result_list[0]
            fused_result.score = avg_score
            fused.append(fused_result)

        # Sort by fused score and limit
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:limit]

    async def _semantic_search(
        self,
        query: str,
        collection_name: str,
        limit: int,
        score_threshold: float | None,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Perform semantic vector search."""
        try:
            # Create query embedding
            query_embedding = await self.embedding_service.create_embedding(query)

            # Perform vector search
            vector_results = await self.vector_store.search(
                collection_name=collection_name,
                query_embedding=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                filter_conditions=filters,
            )

            # Convert to SearchResult objects
            results = []
            for result in vector_results:
                metadata = result.get("metadata", {})

                search_result = SearchResult(
                    id=result["id"],
                    url=metadata.get("url", ""),
                    title=metadata.get("title", ""),
                    content=metadata.get("content", ""),
                    score=result["score"],
                    project=metadata.get("project", ""),
                    match_type="semantic",
                    query_terms=self._extract_query_terms(query),
                    context_header=metadata.get("context_header"),
                )
                results.append(search_result)

            return results

        except (VectorStoreError, EmbeddingError) as e:
            raise RAGError(f"Semantic search failed: {e}")

    async def _hybrid_search(
        self,
        query: str,
        collection_name: str,
        limit: int,
        score_threshold: float | None,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Perform hybrid semantic + keyword search."""
        try:
            # Run both searches in parallel
            semantic_task = self._semantic_search(
                query, collection_name, limit * 2, score_threshold, filters
            )
            keyword_task = self._keyword_search(
                query, collection_name, limit * 2, filters
            )

            semantic_results, keyword_results = await asyncio.gather(
                semantic_task, keyword_task
            )

            # Combine results
            combined = self._combine_hybrid_results(
                semantic_results, keyword_results, limit
            )

            return combined

        except Exception as e:
            raise RAGError(f"Hybrid search failed: {e}")

    async def _advanced_search_parallel(
        self,
        query: str,
        collection_name: str,
        limit: int,
        score_threshold: float | None,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """PHASE 1: Advanced search with PARALLEL sub-query execution.

        This is the key Phase 1 improvement: replacing sequential sub-query
        processing with parallel execution using asyncio.gather.
        """
        try:
            # Decompose complex queries
            sub_queries = self._decompose_query(query)

            if len(sub_queries) <= 1:
                # Fall back to semantic search for simple queries
                return await self._semantic_search(
                    query, collection_name, limit, score_threshold, filters
                )

            # PHASE 1 IMPROVEMENT: Parallel execution of sub-queries
            search_tasks = [
                self._semantic_search(
                    sub_query, collection_name, limit, score_threshold, filters
                )
                for sub_query in sub_queries
            ]

            # Execute all sub-queries in parallel
            all_results_lists = await asyncio.gather(*search_tasks)

            # Flatten results
            all_results = []
            for results_list in all_results_lists:
                all_results.extend(results_list)

            # Aggregate and rank
            aggregated = self._aggregate_sub_results(query, all_results, limit)

            return aggregated

        except Exception as e:
            raise RAGError(f"Advanced search failed: {e}")

    async def _keyword_search(
        self,
        query: str,
        collection_name: str,
        limit: int,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Simplified keyword search."""
        try:
            query_terms = self._extract_query_terms(query)

            # Use semantic search with lower threshold
            results = await self._semantic_search(
                query, collection_name, limit, 0.3, filters
            )

            # Filter for keyword matches
            keyword_filtered = []
            for result in results:
                content_lower = result.content.lower()
                if any(term.lower() in content_lower for term in query_terms):
                    result.match_type = "keyword"
                    keyword_filtered.append(result)

            return keyword_filtered[:limit]

        except Exception:
            return []

    def _combine_hybrid_results(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        limit: int,
    ) -> list[SearchResult]:
        """Combine semantic and keyword results."""
        result_map: dict[str, SearchResult] = {}

        # Add semantic results (0.7 weight)
        for result in semantic_results:
            if result.id not in result_map:
                hybrid_score = result.score * 0.7
                result.match_type = "hybrid_semantic"
                # Store hybrid_score temporarily in rerank_score field
                result.rerank_score = hybrid_score
                result_map[result.id] = result

        # Add keyword results (0.3 weight, boost if exists)
        for result in keyword_results:
            if result.id in result_map:
                existing = result_map[result.id]
                existing.rerank_score = (existing.rerank_score or 0) + (
                    result.score * 0.3
                )
                existing.match_type = "hybrid_both"
            else:
                result.rerank_score = result.score * 0.3
                result.match_type = "hybrid_keyword"
                result_map[result.id] = result

        # Sort by hybrid score
        combined = list(result_map.values())
        combined.sort(key=lambda x: x.rerank_score or 0, reverse=True)

        return combined[:limit]

    def _decompose_query(self, query: str) -> list[str]:
        """Decompose complex queries into sub-queries."""
        query = query.strip()

        # Split on conjunctions
        patterns = [r"\s+and\s+", r"\s+or\s+", r"\s*,\s*", r"\s*;\s*"]

        sub_queries = [query]
        for pattern in patterns:
            new_sub = []
            for sq in sub_queries:
                parts = re.split(pattern, sq, flags=re.IGNORECASE)
                if len(parts) > 1:
                    new_sub.extend([p.strip() for p in parts if p.strip()])
                else:
                    new_sub.append(sq)
            sub_queries = new_sub

        # Filter short queries
        sub_queries = [q for q in sub_queries if len(q.split()) >= 2]

        return sub_queries if sub_queries else [query]

    def _aggregate_sub_results(
        self, original_query: str, all_results: list[SearchResult], limit: int
    ) -> list[SearchResult]:
        """Aggregate results from multiple sub-queries."""
        result_map: dict[str, SearchResult] = {}

        for result in all_results:
            if result.id not in result_map:
                result_map[result.id] = result
                # Track sub-query matches in rerank_score field temporarily
                result.rerank_score = result.score
            else:
                existing = result_map[result.id]
                # Boost for multiple matches
                existing.rerank_score = max(
                    existing.rerank_score or 0, result.score
                ) * 1.1

        # Sort by aggregated score
        aggregated = list(result_map.values())
        aggregated.sort(key=lambda x: x.rerank_score or 0, reverse=True)

        return aggregated[:limit]

    def _extract_query_terms(self, query: str) -> list[str]:
        """Extract meaningful terms from query."""
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
        }

        words = re.findall(r"\b\w+\b", query.lower())
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        return terms

    def _get_cache_key(
        self,
        query: str,
        collection_name: str,
        limit: int,
        strategy: SearchStrategy,
    ) -> str:
        """Generate cache key for query."""
        content = f"{query}:{collection_name}:{limit}:{strategy.value}".encode()
        return hashlib.sha256(content).hexdigest()

    async def index_documents(
        self,
        collection_name: str,
        documents: list[Document],
        chunk_strategy: ChunkStrategy = ChunkStrategy.CHARACTER,
        chunk_size: int = 1000,
        overlap: int = 100,
        batch_size: int = 50,
    ) -> int:
        """Index documents with chunking and contextual headers.

        Args:
            collection_name: Target collection
            documents: Documents to index
            chunk_strategy: Chunking strategy
            chunk_size: Max chunk size
            overlap: Overlap between chunks
            batch_size: Embedding batch size

        Returns:
            Total chunks indexed
        """
        if not documents:
            return 0

        try:
            # Ensure collection exists
            if not await self.vector_store.collection_exists(collection_name):
                await self.vector_store.create_collection(collection_name)

            # Chunk all documents with contextual headers
            all_chunks: list[Chunk] = []
            for doc in documents:
                chunks = await self.chunking_service.chunk_document(
                    document=doc,
                    strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    add_context_headers=True,  # PHASE 1: Always add headers
                )
                all_chunks.extend(chunks)

            # PHASE 3: Create embeddings with adaptive batching
            processed_docs = []
            current_batch_size = batch_size
            success_streak = 0
            failure_streak = 0
            min_batch = 10
            max_batch = 200

            i = 0
            while i < len(all_chunks):
                batch = all_chunks[i : i + current_batch_size]
                batch_start = datetime.now()

                try:
                    # Process batch
                    for chunk in batch:
                        embedding = await self.embedding_service.create_embedding(
                            chunk.content
                        )
                        processed_doc = {
                            "id": chunk.id,
                            "embedding": embedding,
                            "metadata": {
                                "title": chunk.title,
                                "content": chunk.content,
                                "url": chunk.url,
                                "project": chunk.project,
                                "chunk_index": chunk.chunk_index,
                                "parent_id": chunk.parent_id,
                                "context_header": chunk.context_header,
                            },
                        }
                        processed_docs.append(processed_doc)

                    # Batch success
                    batch_time = (datetime.now() - batch_start).total_seconds()
                    self.logger.debug(
                        f"Batch processed: size={len(batch)}, time={batch_time:.2f}s"
                    )

                    success_streak += 1
                    failure_streak = 0

                    # Increase batch size after 3 consecutive successes
                    if success_streak >= 3 and current_batch_size < max_batch:
                        old_size = current_batch_size
                        current_batch_size = min(
                            int(current_batch_size * 1.5), max_batch
                        )
                        self.logger.debug(
                            f"Increasing batch size: {old_size} -> {current_batch_size}"
                        )
                        success_streak = 0

                    i += len(batch)

                except Exception as e:
                    # Batch failure - reduce batch size
                    self.logger.warning(
                        f"Batch processing failed (size={current_batch_size}): {e}"
                    )
                    failure_streak += 1
                    success_streak = 0

                    # Decrease batch size after 2 consecutive failures
                    if failure_streak >= 2 and current_batch_size > min_batch:
                        old_size = current_batch_size
                        current_batch_size = max(
                            int(current_batch_size * 0.5), min_batch
                        )
                        self.logger.debug(
                            f"Decreasing batch size: {old_size} -> {current_batch_size}"
                        )
                        failure_streak = 0

                    # Retry with smaller batch or skip
                    if current_batch_size >= min_batch:
                        continue  # Retry same batch with new size
                    else:
                        # Skip this batch and move on
                        i += len(batch)

            # Batch insert all processed documents
            indexed_count = await self.vector_store.upsert_documents(
                collection_name, processed_docs
            )

            self.logger.info(
                "Documents indexed",
                extra={
                    "collection_name": collection_name,
                    "original_documents": len(documents),
                    "chunks_indexed": indexed_count,
                },
            )

            return indexed_count

        except Exception as e:
            self.logger.error(
                "Failed to index documents",
                extra={
                    "collection_name": collection_name,
                    "documents_count": len(documents),
                    "error": str(e),
                },
            )
            raise RAGError(f"Failed to index documents: {e}")

    def clear_cache(self) -> int:
        """Clear query cache."""
        cache_size = len(self._query_cache)
        self._query_cache.clear()
        return cache_size

    def get_metrics_summary(self):
        """Get performance metrics summary.

        Returns:
            MetricsSummary if metrics enabled, None otherwise
        """
        if self.metrics:
            return self.metrics.get_summary()
        return None

    def record_user_feedback(
        self,
        query: str,
        result_ids: list[str],
        clicked_ids: list[str],
        user_rating: int | None = None,
    ) -> None:
        """Record user feedback for quality metrics.

        Args:
            query: Search query
            result_ids: Result IDs returned (in order)
            clicked_ids: Result IDs clicked by user
            user_rating: Optional 1-5 rating
        """
        if self.quality_metrics:
            self.quality_metrics.record_user_feedback(
                query=query,
                result_ids=result_ids,
                clicked_ids=clicked_ids,
                user_rating=user_rating,
            )