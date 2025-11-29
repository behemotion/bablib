"""Setup initialization service."""

import sqlite3
from pathlib import Path
from typing import Any

from src.core.lib_logger import get_logger

logger = get_logger(__name__)


class SetupInitializer:
    """Service for initializing Bablib setup."""

    def __init__(self, home_dir: Path | None = None):
        """Initialize the setup initializer.

        Args:
            home_dir: Optional home directory for testing
        """
        self.home_dir = home_dir or Path.home()
        self.config_dir = self.home_dir / ".config" / "bablib"
        self.data_dir = self.home_dir / ".local" / "share" / "bablib"
        self.cache_dir = self.home_dir / ".cache" / "bablib"

    def create_directories(self) -> dict[str, Path]:
        """Create required directory structure.

        Returns:
            Dictionary of created directories
        """
        directories = {
            "config": self.config_dir,
            "data": self.data_dir,
            "cache": self.cache_dir,
            "projects": self.data_dir / "projects",
            "logs": self.data_dir / "logs" / "setup"
        }

        for name, path in directories.items():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {path}")

        return directories

    def initialize_sqlite_vec(self) -> Path:
        """Initialize SQLite-vec vector store.

        Returns:
            Path to initialized database
        """
        db_path = self.data_dir / "vectors.db"

        # Create database and tables
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Create vector store tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vector_collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    dimension INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (collection_id) REFERENCES vector_collections(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vectors_collection
                ON vectors(collection_id)
            """)

            conn.commit()
            logger.info(f"Initialized SQLite-vec at {db_path}")

        finally:
            conn.close()

        return db_path

    def initialize_qdrant(self) -> dict[str, Any]:
        """Initialize Qdrant vector store configuration.

        Returns:
            Qdrant configuration details
        """
        # Qdrant doesn't need local initialization
        # Just return configuration for connecting to it
        config = {
            "url": "http://localhost:6333",
            "timeout": 30,
            "prefer_grpc": False,
            "collections": []
        }

        logger.info("Configured Qdrant connection settings")
        return config

    def initialize_embedding_model(self, model: str = "mxbai-embed-large") -> dict[str, Any]:
        """Initialize embedding model configuration.

        Args:
            model: Embedding model to use

        Returns:
            Model configuration
        """
        config = {
            "model": model,
            "ollama_url": "http://localhost:11434",
            "dimension": 1024 if model == "mxbai-embed-large" else 768,
            "batch_size": 32
        }

        logger.info(f"Configured embedding model: {model}")
        return config

    def create_default_config(self) -> dict[str, Any]:
        """Create default configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "vector_store_provider": "sqlite_vec",
            "ollama_url": "http://localhost:11434",
            "embedding_model": "mxbai-embed-large",
            "chunk_size": 500,
            "chunk_overlap": 50,
            "crawl_depth": 2,
            "rate_limit": 2.0,
            "mcp_host": "localhost",
            "mcp_port": 9382,
            "log_level": "INFO"
        }

    def execute(
        self,
        vector_store: str = "sqlite_vec",
        auto: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """Execute full initialization.

        Args:
            vector_store: Vector store to initialize
            auto: Use automatic defaults
            **kwargs: Additional options

        Returns:
            Initialization results
        """
        results = {
            "directories": self.create_directories(),
            "config": self.create_default_config()
        }

        # Initialize vector store
        if vector_store == "sqlite_vec":
            results["vector_db"] = str(self.initialize_sqlite_vec())
        elif vector_store == "qdrant":
            results["vector_config"] = self.initialize_qdrant()

        # Initialize embedding model
        results["embedding"] = self.initialize_embedding_model()

        return results
