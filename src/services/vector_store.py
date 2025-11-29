"""Vector store service using Qdrant for embeddings."""

import asyncio
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from src.core.config import BablibConfig
from src.core.lib_logger import get_component_logger


class VectorStoreError(Exception):
    """Vector store operation error."""
    pass


class VectorStoreService:
    """Manages vector storage operations using Qdrant."""

    def __init__(self, config: BablibConfig | None = None):
        """Initialize vector store service."""
        self.config = config or BablibConfig()
        self.logger = get_component_logger("vector_store")

        # Qdrant client
        self._client: QdrantClient | None = None
        self._initialized = False

        # Default collection settings
        self.default_vector_size = 1024  # mxbai-embed-large dimension
        self.default_distance = qdrant_models.Distance.COSINE

    async def initialize(self) -> None:
        """Initialize Qdrant client and connection."""
        if self._initialized:
            return

        try:
            # Create client based on deployment strategy
            from src.core.config import ServiceDeployment
            if self.config.qdrant_deployment == ServiceDeployment.DOCKER:
                self._client = QdrantClient(url=self.config.qdrant_url)
            else:
                # Local deployment
                qdrant_path = self.config.data_dir / "qdrant"
                self._client = QdrantClient(path=str(qdrant_path))

            # Test connection
            await self._test_connection()

            self._initialized = True
            self.logger.info("Vector store initialized", extra={
                "deployment": self.config.qdrant_deployment.value,
                "url": self.config.qdrant_url if self.config.qdrant_deployment == ServiceDeployment.DOCKER else str(qdrant_path)
            })

        except Exception as e:
            self.logger.error("Failed to initialize vector store", extra={
                "error": str(e),
                "deployment": self.config.qdrant_deployment.value
            })
            raise VectorStoreError(f"Failed to initialize vector store: {e}")

    async def cleanup(self) -> None:
        """Clean up vector store connections."""
        if self._client:
            # Qdrant client doesn't need explicit cleanup in sync mode
            self._client = None
        self._initialized = False
        self.logger.info("Vector store connections closed")

    def _ensure_initialized(self) -> None:
        """Ensure vector store is initialized."""
        if not self._initialized:
            raise VectorStoreError("Vector store not initialized. Call initialize() first.")

    async def _test_connection(self) -> None:
        """Test Qdrant connection."""
        try:
            # Use asyncio to run sync method in thread pool
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self._client.get_collections
            )
            self.logger.debug("Connection test successful", extra={
                "collections_count": len(collections.collections)
            })
        except Exception as e:
            raise VectorStoreError(f"Qdrant connection test failed: {e}")

    # Collection management

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int | None = None,
        distance: qdrant_models.Distance | None = None,
        overwrite: bool = False
    ) -> bool:
        """Create a new collection."""
        self._ensure_initialized()

        vector_size = vector_size or self.default_vector_size
        distance = distance or self.default_distance

        try:
            # Check if collection exists
            if not overwrite:
                exists = await self.collection_exists(collection_name)
                if exists:
                    self.logger.warning("Collection already exists", extra={
                        "collection_name": collection_name
                    })
                    return False

            # Create collection
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.create_collection,
                collection_name,
                qdrant_models.VectorParams(
                    size=vector_size,
                    distance=distance
                )
            )

            self.logger.info("Collection created", extra={
                "collection_name": collection_name,
                "vector_size": vector_size,
                "distance": distance.value
            })

            return True

        except Exception as e:
            self.logger.error("Failed to create collection", extra={
                "collection_name": collection_name,
                "error": str(e)
            })
            raise VectorStoreError(f"Failed to create collection {collection_name}: {e}")

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        self._ensure_initialized()

        try:
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self._client.get_collections
            )

            return any(c.name == collection_name for c in collections.collections)

        except Exception as e:
            self.logger.error("Failed to check collection existence", extra={
                "collection_name": collection_name,
                "error": str(e)
            })
            return False

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        self._ensure_initialized()

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.delete_collection,
                collection_name
            )

            self.logger.info("Collection deleted", extra={
                "collection_name": collection_name
            })

            return True

        except Exception as e:
            self.logger.error("Failed to delete collection", extra={
                "collection_name": collection_name,
                "error": str(e)
            })
            return False

    async def list_collections(self) -> list[str]:
        """List all collections."""
        self._ensure_initialized()

        try:
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self._client.get_collections
            )

            collection_names = [c.name for c in collections.collections]

            self.logger.debug("Listed collections", extra={
                "collections": collection_names
            })

            return collection_names

        except Exception as e:
            self.logger.error("Failed to list collections", extra={
                "error": str(e)
            })
            raise VectorStoreError(f"Failed to list collections: {e}")

    # Document operations

    async def upsert_document(
        self,
        collection_name: str,
        document_id: str,
        embedding: list[float],
        metadata: dict[str, Any]
    ) -> bool:
        """Upsert a document with its embedding."""
        self._ensure_initialized()

        try:
            # Prepare point
            point = qdrant_models.PointStruct(
                id=document_id,
                vector=embedding,
                payload=metadata
            )

            # Upsert point
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.upsert,
                collection_name,
                points=[point]
            )

            self.logger.debug("Document upserted", extra={
                "collection_name": collection_name,
                "document_id": document_id,
                "embedding_size": len(embedding)
            })

            return True

        except Exception as e:
            self.logger.error("Failed to upsert document", extra={
                "collection_name": collection_name,
                "document_id": document_id,
                "error": str(e)
            })
            raise VectorStoreError(f"Failed to upsert document {document_id}: {e}")

    async def upsert_documents(
        self,
        collection_name: str,
        documents: list[dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """Upsert multiple documents with batching to avoid timeouts."""
        self._ensure_initialized()

        total_documents = len(documents)
        upserted_count = 0

        try:
            # Process in batches to avoid timeouts
            for i in range(0, total_documents, batch_size):
                batch = documents[i:i + batch_size]

                # Prepare points for this batch
                points = []
                for doc in batch:
                    point = qdrant_models.PointStruct(
                        id=doc["id"],
                        vector=doc["embedding"],
                        payload=doc.get("metadata", {})
                    )
                    points.append(point)

                # Upsert batch with timeout handling
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            self._client.upsert,
                            collection_name,
                            points
                        ),
                        timeout=30.0  # 30 second timeout per batch
                    )
                    upserted_count += len(batch)

                    # Log progress for large uploads
                    if total_documents > 500 and (i + batch_size) % 500 == 0:
                        self.logger.info(f"Upserted {upserted_count}/{total_documents} documents to {collection_name}")

                except TimeoutError:
                    self.logger.error(f"Timeout while upserting batch {i//batch_size + 1}, retrying with smaller batch")
                    # Retry with smaller batch
                    if batch_size > 20:
                        for j in range(0, len(batch), 20):
                            small_batch = batch[j:j + 20]
                            small_points = []
                            for doc in small_batch:
                                point = qdrant_models.PointStruct(
                                    id=doc["id"],
                                    vector=doc["embedding"],
                                    payload=doc.get("metadata", {})
                                )
                                small_points.append(point)

                            await asyncio.wait_for(
                                asyncio.get_event_loop().run_in_executor(
                                    None,
                                    self._client.upsert,
                                    collection_name,
                                    small_points
                                ),
                                timeout=15.0
                            )
                            upserted_count += len(small_batch)
                    else:
                        raise

            self.logger.info("Documents upserted", extra={
                "collection_name": collection_name,
                "documents_count": upserted_count
            })

            return upserted_count

        except Exception as e:
            self.logger.error("Failed to upsert documents", extra={
                "collection_name": collection_name,
                "documents_count": total_documents,
                "upserted_count": upserted_count,
                "error": str(e)
            })
            raise VectorStoreError(f"Failed to upsert documents (uploaded {upserted_count}/{total_documents}): {e}")

    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filter_conditions: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Search for similar documents."""
        self._ensure_initialized()

        try:
            # Prepare filter
            query_filter = None
            if filter_conditions:
                query_filter = qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key=key,
                            match=qdrant_models.MatchValue(value=value)
                        )
                        for key, value in filter_conditions.items()
                    ]
                )

            # Perform search
            search_kwargs = {
                "collection_name": collection_name,
                "query_vector": query_embedding,
                "limit": limit
            }

            if query_filter:
                search_kwargs["query_filter"] = query_filter
            if score_threshold is not None:
                search_kwargs["score_threshold"] = score_threshold

            search_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.search(**search_kwargs)
            )

            # Format results
            results = []
            for point in search_result:
                result = {
                    "id": point.id,
                    "score": point.score,
                    "metadata": point.payload or {}
                }
                results.append(result)

            self.logger.debug("Search completed", extra={
                "collection_name": collection_name,
                "results_count": len(results),
                "limit": limit
            })

            return results

        except Exception as e:
            self.logger.error("Failed to search", extra={
                "collection_name": collection_name,
                "limit": limit,
                "error": str(e)
            })
            raise VectorStoreError(f"Failed to search in {collection_name}: {e}")

    async def get_document(
        self,
        collection_name: str,
        document_id: str
    ) -> dict[str, Any] | None:
        """Get a specific document by ID."""
        self._ensure_initialized()

        try:
            # Retrieve point
            points = await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.retrieve,
                collection_name,
                [document_id]
            )

            if not points:
                return None

            point = points[0]
            return {
                "id": point.id,
                "embedding": point.vector,
                "metadata": point.payload or {}
            }

        except Exception as e:
            self.logger.error("Failed to get document", extra={
                "collection_name": collection_name,
                "document_id": document_id,
                "error": str(e)
            })
            return None

    async def delete_document(
        self,
        collection_name: str,
        document_id: str
    ) -> bool:
        """Delete a document from the collection."""
        self._ensure_initialized()

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.delete,
                collection_name,
                points_selector=qdrant_models.PointIdsList(
                    points=[document_id]
                )
            )

            self.logger.debug("Document deleted", extra={
                "collection_name": collection_name,
                "document_id": document_id
            })

            return True

        except Exception as e:
            self.logger.error("Failed to delete document", extra={
                "collection_name": collection_name,
                "document_id": document_id,
                "error": str(e)
            })
            return False

    async def delete_documents(
        self,
        collection_name: str,
        document_ids: list[str]
    ) -> int:
        """Delete multiple documents from the collection."""
        self._ensure_initialized()

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.delete,
                collection_name,
                points_selector=qdrant_models.PointIdsList(
                    points=document_ids
                )
            )

            self.logger.info("Documents deleted", extra={
                "collection_name": collection_name,
                "documents_count": len(document_ids)
            })

            return len(document_ids)

        except Exception as e:
            self.logger.error("Failed to delete documents", extra={
                "collection_name": collection_name,
                "documents_count": len(document_ids),
                "error": str(e)
            })
            return 0

    # Collection statistics and information

    async def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """Get collection information and statistics."""
        self._ensure_initialized()

        try:
            collection_info = await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.get_collection,
                collection_name
            )

            return {
                "name": collection_name,
                "status": collection_info.status.value,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "config": {
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance.value
                }
            }

        except Exception as e:
            self.logger.error("Failed to get collection info", extra={
                "collection_name": collection_name,
                "error": str(e)
            })
            raise VectorStoreError(f"Failed to get collection info for {collection_name}: {e}")

    async def count_documents(self, collection_name: str) -> int:
        """Count documents in collection."""
        self._ensure_initialized()

        try:
            info = await self.get_collection_info(collection_name)
            return info["points_count"]

        except Exception as e:
            self.logger.error("Failed to count documents", extra={
                "collection_name": collection_name,
                "error": str(e)
            })
            return 0

    # Utility methods

    async def health_check(self) -> tuple[bool, str]:
        """Check vector store health."""
        if not self._initialized:
            return False, "Vector store not initialized"

        try:
            # Test basic operation
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self._client.get_collections
            )

            return True, f"Healthy - {len(collections.collections)} collections"

        except Exception as e:
            return False, f"Health check failed: {e}"

    async def create_index(
        self,
        collection_name: str,
        field_name: str,
        field_type: str = "keyword"
    ) -> bool:
        """Create an index on a payload field."""
        self._ensure_initialized()

        try:
            # Create payload index
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.create_payload_index,
                collection_name,
                field_name,
                field_type
            )

            self.logger.info("Payload index created", extra={
                "collection_name": collection_name,
                "field_name": field_name,
                "field_type": field_type
            })

            return True

        except Exception as e:
            self.logger.error("Failed to create index", extra={
                "collection_name": collection_name,
                "field_name": field_name,
                "error": str(e)
            })
            return False

    def get_client(self) -> QdrantClient:
        """Get the underlying Qdrant client."""
        self._ensure_initialized()
        return self._client

    async def add_embeddings(
        self,
        collection_name: str,
        embeddings: list[list[float]],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None
    ) -> int:
        """Add embeddings to collection (compatibility method).

        This method provides compatibility with code expecting an add_embeddings interface.
        It internally uses upsert_documents for the actual implementation.
        """
        documents = []
        for i, (embedding, doc_id) in enumerate(zip(embeddings, ids, strict=False)):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            documents.append({
                "id": doc_id,
                "embedding": embedding,
                "metadata": metadata
            })

        return await self.upsert_documents(collection_name, documents)
