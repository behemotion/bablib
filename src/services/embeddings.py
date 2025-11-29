"""Embedding service using local Ollama models."""

import asyncio
import hashlib
import json
from collections import OrderedDict
from typing import Any

import httpx

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger


class EmbeddingError(Exception):
    """Embedding operation error."""
    pass


class EmbeddingService:
    """Manages text embedding operations using Ollama."""

    def __init__(self, config: BablibConfig | None = None):
        """Initialize embedding service."""
        self.config = config or BablibConfig()
        self.logger = get_component_logger("embeddings")

        # HTTP client for Ollama API
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

        # LRU Embedding cache with 10K limit (~80MB)
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_max_size = 10000
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0

        # Model information
        self.model_info = {}

    async def initialize(self) -> None:
        """Initialize embedding service and verify models."""
        if self._initialized:
            return

        try:
            # Create HTTP client
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),  # 60 second timeout for embeddings
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )

            # Test connection and pull models if needed
            await self._ensure_models()

            self._initialized = True
            self.logger.info("Embedding service initialized", extra={
                "ollama_url": self.config.ollama_url,
                "embedding_model": self.config.embedding_model,
                "deployment": self.config.ollama_deployment.value
            })

        except Exception as e:
            self.logger.error("Failed to initialize embedding service", extra={
                "error": str(e),
                "ollama_url": self.config.ollama_url
            })
            raise EmbeddingError(f"Failed to initialize embedding service: {e}")

    async def cleanup(self) -> None:
        """Clean up embedding service."""
        if self._client:
            await self._client.aclose()
            self._client = None

        self._initialized = False
        self.logger.info("Embedding service cleaned up", extra={
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses
        })

    def _ensure_initialized(self) -> None:
        """Ensure embedding service is initialized."""
        if not self._initialized:
            raise EmbeddingError("Embedding service not initialized. Call initialize() first.")

    async def _ensure_models(self) -> None:
        """Ensure required models are available."""
        try:
            # Check if Ollama is available
            await self._health_check()

            # Get available models
            available_models = await self._list_models()

            # Check if embedding model is available
            if self.config.embedding_model not in available_models:
                self.logger.info("Pulling embedding model", extra={
                    "model": self.config.embedding_model
                })
                await self._pull_model(self.config.embedding_model)

            # Get model info
            self.model_info = await self._get_model_info(self.config.embedding_model)

        except Exception as e:
            raise EmbeddingError(f"Failed to ensure models are available: {e}")

    async def _health_check(self) -> None:
        """Check Ollama service health."""
        try:
            response = await self._client.get(f"{self.config.ollama_url}/api/version")
            if response.status_code != 200:
                raise EmbeddingError(f"Ollama health check failed: {response.status_code}")

        except httpx.RequestError as e:
            raise EmbeddingError(f"Cannot connect to Ollama: {e}")

    async def _list_models(self) -> list[str]:
        """List available models in Ollama."""
        try:
            response = await self._client.get(f"{self.config.ollama_url}/api/tags")
            if response.status_code != 200:
                raise EmbeddingError(f"Failed to list models: {response.status_code}")

            data = response.json()
            models = [model["name"] for model in data.get("models", [])]

            self.logger.debug("Available models", extra={"models": models})
            return models

        except Exception as e:
            raise EmbeddingError(f"Failed to list models: {e}")

    async def _pull_model(self, model_name: str) -> None:
        """Pull a model from Ollama."""
        try:
            payload = {"name": model_name}

            # Use streaming to handle long pull operations
            async with self._client.stream(
                "POST",
                f"{self.config.ollama_url}/api/pull",
                json=payload,
                timeout=httpx.Timeout(300.0)  # 5 minute timeout for pull
            ) as response:
                if response.status_code != 200:
                    raise EmbeddingError(f"Failed to pull model: {response.status_code}")

                # Stream and log progress
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "status" in data:
                                self.logger.debug("Model pull progress", extra={
                                    "model": model_name,
                                    "status": data["status"]
                                })
                        except json.JSONDecodeError:
                            continue

            self.logger.info("Model pulled successfully", extra={"model": model_name})

        except Exception as e:
            raise EmbeddingError(f"Failed to pull model {model_name}: {e}")

    async def _get_model_info(self, model_name: str) -> dict[str, Any]:
        """Get model information."""
        try:
            payload = {"name": model_name}
            response = await self._client.post(
                f"{self.config.ollama_url}/api/show",
                json=payload
            )

            if response.status_code != 200:
                self.logger.warning("Failed to get model info", extra={
                    "model": model_name,
                    "status": response.status_code
                })
                return {}

            return response.json()

        except Exception as e:
            self.logger.warning("Failed to get model info", extra={
                "model": model_name,
                "error": str(e)
            })
            return {}

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for text and model."""
        content = f"{model}:{text}".encode()
        return hashlib.sha256(content).hexdigest()

    async def create_embedding(
        self,
        text: str,
        model: str | None = None,
        use_cache: bool = True
    ) -> list[float]:
        """Create embedding for text."""
        self._ensure_initialized()

        if not text.strip():
            raise EmbeddingError("Empty text provided for embedding")

        model = model or self.config.embedding_model

        # Check cache first (LRU: move to end on access)
        if use_cache:
            cache_key = self._get_cache_key(text, model)
            if cache_key in self._cache:
                self._cache_hits += 1
                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)
                self.logger.debug("Cache hit for embedding", extra={
                    "text_length": len(text),
                    "model": model
                })
                return self._cache[cache_key]

        try:
            # Create embedding via Ollama API
            payload = {
                "model": model,
                "prompt": text
            }

            response = await self._client.post(
                f"{self.config.ollama_url}/api/embeddings",
                json=payload,
                timeout=httpx.Timeout(60.0)
            )

            if response.status_code != 200:
                raise EmbeddingError(f"Embedding request failed: {response.status_code} - {response.text}")

            data = response.json()
            embedding = data.get("embedding")

            if not embedding:
                raise EmbeddingError("No embedding returned from Ollama")

            # Cache the result with LRU eviction
            if use_cache:
                cache_key = self._get_cache_key(text, model)

                # Evict oldest entry if at capacity
                if len(self._cache) >= self._cache_max_size:
                    # Remove oldest (first) item
                    self._cache.popitem(last=False)
                    self._cache_evictions += 1
                    self.logger.debug("LRU cache eviction", extra={
                        "cache_size": len(self._cache),
                        "max_size": self._cache_max_size
                    })

                self._cache[cache_key] = embedding
                self._cache_misses += 1

            self.logger.debug("Embedding created", extra={
                "text_length": len(text),
                "model": model,
                "embedding_size": len(embedding)
            })

            return embedding

        except httpx.RequestError as e:
            raise EmbeddingError(f"Network error creating embedding: {e}")
        except Exception as e:
            raise EmbeddingError(f"Failed to create embedding: {e}")

    async def create_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
        batch_size: int = 10,
        use_cache: bool = True
    ) -> list[list[float]]:
        """Create embeddings for multiple texts."""
        self._ensure_initialized()

        if not texts:
            return []

        model = model or self.config.embedding_model
        embeddings = []

        # Process in batches to avoid overwhelming the service
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_tasks = []

            for text in batch:
                task = self.create_embedding(text, model, use_cache)
                batch_tasks.append(task)

            # Process batch concurrently
            try:
                batch_embeddings = await asyncio.gather(*batch_tasks)
                embeddings.extend(batch_embeddings)

                self.logger.debug("Batch embeddings created", extra={
                    "batch_size": len(batch),
                    "total_processed": len(embeddings),
                    "total_texts": len(texts)
                })

            except Exception as e:
                self.logger.error("Failed to create batch embeddings", extra={
                    "batch_start": i,
                    "batch_size": len(batch),
                    "error": str(e)
                })
                raise

        self.logger.info("All embeddings created", extra={
            "total_texts": len(texts),
            "total_embeddings": len(embeddings),
            "model": model
        })

        return embeddings

    async def get_embedding_dimension(self, model: str | None = None) -> int:
        """Get embedding dimension for a model."""
        self._ensure_initialized()

        model = model or self.config.embedding_model

        # Try to get from model info
        if model in self.model_info:
            # This would need to be extracted from model details
            # For now, return known dimensions
            pass

        # Known model dimensions
        model_dimensions = {
            "mxbai-embed-large": 1024,
            "nomic-embed-text": 768,
            "all-minilm": 384,
            "bge-large": 1024,
            "gte-large": 1024
        }

        for known_model, dimension in model_dimensions.items():
            if known_model in model:
                return dimension

        # Default: create a test embedding to determine dimension
        try:
            test_embedding = await self.create_embedding("test", model, use_cache=False)
            dimension = len(test_embedding)

            self.logger.info("Determined embedding dimension", extra={
                "model": model,
                "dimension": dimension
            })

            return dimension

        except Exception as e:
            self.logger.warning("Failed to determine embedding dimension", extra={
                "model": model,
                "error": str(e)
            })
            return 1024  # Default dimension

    async def similarity(
        self,
        embedding1: list[float],
        embedding2: list[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        if len(embedding1) != len(embedding2):
            raise EmbeddingError("Embeddings must have the same dimension")

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2, strict=False))
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(a * a for a in embedding2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        similarity = dot_product / (magnitude1 * magnitude2)
        return max(-1.0, min(1.0, similarity))  # Clamp to [-1, 1]

    async def health_check(self) -> tuple[bool, str]:
        """Check embedding service health."""
        if not self._initialized:
            return False, "Embedding service not initialized"

        try:
            # Test basic embedding creation
            test_embedding = await self.create_embedding(
                "Health check test",
                use_cache=False
            )

            if not test_embedding:
                return False, "Failed to create test embedding"

            return True, f"Healthy - Model: {self.config.embedding_model}, Dimension: {len(test_embedding)}"

        except Exception as e:
            return False, f"Health check failed: {e}"

    def get_cache_stats(self) -> dict[str, Any]:
        """Get embedding cache statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests) * 100 if total_requests > 0 else 0

        # Estimate memory usage: ~8KB per embedding (1024 dimensions × 8 bytes/float)
        memory_usage_mb = (len(self._cache) * 8) / 1024

        return {
            "cache_size": len(self._cache),
            "max_size": self._cache_max_size,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "evictions": self._cache_evictions,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "memory_usage_mb": round(memory_usage_mb, 2)
        }

    def clear_cache(self) -> int:
        """Clear embedding cache."""
        cache_size = len(self._cache)
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

        self.logger.info("Embedding cache cleared", extra={
            "cleared_entries": cache_size
        })

        return cache_size
