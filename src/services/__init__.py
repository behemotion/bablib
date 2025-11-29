"""Services module for Bablib."""

from .database import DatabaseManager
from .embeddings import EmbeddingService
from .rag import RAGSearchService
from .vector_store import VectorStoreService

# DocumentationCrawler moved to src.logic.crawler.core.crawler
# Import directly from src.logic.crawler.core.crawler when needed

__all__ = [
    "DatabaseManager",
    "VectorStoreService",
    "EmbeddingService",
    "RAGSearchService",
    # "DocumentationCrawler",  # Moved to src.logic.crawler.core.crawler
]
