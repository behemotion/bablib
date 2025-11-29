"""Health category enum model."""

from enum import Enum


class HealthCategory(Enum):
    """Categories of health checks for organization and filtering."""

    SYSTEM = "SYSTEM"
    SERVICES = "SERVICES"
    CONFIGURATION = "CONFIGURATION"
    PROJECTS = "PROJECTS"

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        names = {
            HealthCategory.SYSTEM: "System Requirements",
            HealthCategory.SERVICES: "External Services",
            HealthCategory.CONFIGURATION: "Configuration Files",
            HealthCategory.PROJECTS: "Project Health"
        }
        return names[self]

    @property
    def description(self) -> str:
        """Get category description."""
        descriptions = {
            HealthCategory.SYSTEM: "System requirements and environment validation",
            HealthCategory.SERVICES: "External service availability and configuration",
            HealthCategory.CONFIGURATION: "Bablib configuration file validation",
            HealthCategory.PROJECTS: "Project-specific health validation"
        }
        return descriptions[self]
