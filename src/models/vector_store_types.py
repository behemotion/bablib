"""Vector store type definitions for Bablib."""

from enum import Enum


class VectorStoreProvider(str, Enum):
    """Available vector storage backends."""

    QDRANT = "qdrant"
    SQLITE_VEC = "sqlite_vec"

    @classmethod
    def get_display_name(cls, provider: "VectorStoreProvider") -> str:
        """Get human-friendly display name for provider."""
        display_names = {
            cls.QDRANT: "Qdrant (recommended for large deployments)",
            cls.SQLITE_VEC: "SQLite-vec (local, no external dependencies)",
        }
        return display_names.get(provider, provider.value)

    @classmethod
    def from_string(cls, value: str) -> "VectorStoreProvider":
        """Create provider from string value."""
        value = value.lower().replace("-", "_")
        for provider in cls:
            if provider.value == value:
                return provider
        raise ValueError(f"Unknown vector store provider: {value}")
