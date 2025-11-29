"""Service type enum model."""

from enum import Enum


class ServiceType(Enum):
    """Types of external services that Bablib integrates with."""

    DOCKER = "DOCKER"
    QDRANT = "QDRANT"
    OLLAMA = "OLLAMA"
    GIT = "GIT"

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        names = {
            ServiceType.DOCKER: "Docker Service",
            ServiceType.QDRANT: "Qdrant Database",
            ServiceType.OLLAMA: "Ollama Service",
            ServiceType.GIT: "Git"
        }
        return names[self]

    @property
    def default_url(self) -> str:
        """Get default service URL if applicable."""
        urls = {
            ServiceType.DOCKER: "unix:///var/run/docker.sock",
            ServiceType.QDRANT: "http://localhost:6333",
            ServiceType.OLLAMA: "http://localhost:11434",
            ServiceType.GIT: ""  # No URL for Git
        }
        return urls[self]

    @property
    def is_required(self) -> bool:
        """Check if service is required for basic Bablib operation."""
        required = {
            ServiceType.DOCKER: False,
            ServiceType.QDRANT: False,
            ServiceType.OLLAMA: False,
            ServiceType.GIT: True
        }
        return required[self]
