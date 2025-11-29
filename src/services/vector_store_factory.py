"""Vector store factory for creating appropriate vector store services."""

import logging

from src.core.config import BablibConfig
from src.models.vector_store_types import VectorStoreProvider
from src.services.settings_service import SettingsService
from src.services.sqlite_vec_service import SQLiteVecService, detect_sqlite_vec
from src.services.vector_store import VectorStoreError, VectorStoreService

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for creating vector store services based on configuration."""

    @staticmethod
    def create_vector_store(config: BablibConfig = None, provider: VectorStoreProvider = None) -> VectorStoreService | SQLiteVecService:
        """Create appropriate vector store service based on provider."""

        # If provider not specified, get from settings
        if provider is None:
            settings_service = SettingsService()
            if settings_service.settings_path.exists():
                settings = settings_service.get_settings()
                provider = settings.vector_store_provider
            else:
                # Default to SQLite-vec if no settings
                provider = VectorStoreProvider.SQLITE_VEC

        # Create appropriate service
        if provider == VectorStoreProvider.SQLITE_VEC:
            # Check if SQLite-vec is available before creating
            available, message = detect_sqlite_vec()
            if not available:
                logger.warning(f"SQLite-vec not available: {message}")
                raise VectorStoreError(f"SQLite-vec extension not available: {message}")
            return SQLiteVecService(config or BablibConfig())
        elif provider == VectorStoreProvider.QDRANT:
            return VectorStoreService(config or BablibConfig())
        else:
            raise ValueError(f"Unsupported vector store provider: {provider}")

    @staticmethod
    def get_current_provider() -> VectorStoreProvider:
        """Get the currently configured vector store provider."""
        settings_service = SettingsService()
        if settings_service.settings_path.exists():
            settings = settings_service.get_settings()
            return settings.vector_store_provider
        else:
            return VectorStoreProvider.SQLITE_VEC

    @staticmethod
    def check_provider_availability(provider: VectorStoreProvider) -> tuple[bool, str]:
        """Check if a vector store provider is available and ready."""
        if provider == VectorStoreProvider.SQLITE_VEC:
            return detect_sqlite_vec()
        elif provider == VectorStoreProvider.QDRANT:
            # For Qdrant, we'll need to test connection during initialization
            return True, "Qdrant connection test required during initialization"
        else:
            return False, f"Unknown provider: {provider}"

    @staticmethod
    def get_fallback_suggestion(provider: VectorStoreProvider) -> str:
        """Get fallback suggestion when a provider is not available."""
        if provider == VectorStoreProvider.SQLITE_VEC:
            return (
                "SQLite-vec is not available. Suggestions:\n"
                "  1. Install sqlite-vec: uv pip install --system sqlite-vec\n"
                "  2. Use Qdrant instead: bablib setup --init --vector-store qdrant --force\n"
                "  3. Check Python installation (macOS may need Homebrew Python)"
            )
        elif provider == VectorStoreProvider.QDRANT:
            return (
                "Qdrant is not available. Suggestions:\n"
                "  1. Start Qdrant: docker run -p 6333:6333 qdrant/qdrant\n"
                "  2. Use SQLite-vec instead: bablib setup --init --vector-store sqlite_vec --force\n"
                "  3. Check Qdrant service status: bablib services list"
            )
        else:
            return f"Unknown provider: {provider}"
