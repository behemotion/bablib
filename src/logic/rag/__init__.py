"""RAG logic module for Bablib.

This module contains the core RAG implementation including:
- Core services: search, chunking, reranking
- Strategies: semantic chunking, query transformation, fusion retrieval
- Analytics: metrics and quality tracking
- Utilities: cache management, contextual headers
- Models: data structures for RAG operations
"""

from src.logic.rag.models.chunk import Chunk
from src.logic.rag.models.search_result import SearchResult, RerankSignals
from src.logic.rag.models.strategy_config import (
    SearchStrategy,
    ChunkStrategy,
    RerankWeights,
    SemanticChunkingConfig,
    QueryTransformConfig,
    FusionConfig,
)

__all__ = [
    "Chunk",
    "SearchResult",
    "RerankSignals",
    "SearchStrategy",
    "ChunkStrategy",
    "RerankWeights",
    "SemanticChunkingConfig",
    "QueryTransformConfig",
    "FusionConfig",
]