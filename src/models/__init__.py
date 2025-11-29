"""Data models for Bablib."""

# Page moved to src.logic.crawler.models.page
from src.logic.crawler.models.page import Page, PageStatus

# CrawlSession moved to src.logic.crawler.models.session
from src.logic.crawler.models.session import CrawlSession, CrawlStatus

from .installation import (
    CriticalDecisionPoint,
    InstallationContext,
    InstallationRequest,
    InstallationResponse,
    PackageMetadata,
    ServiceStatus,
    SetupWizardState,
)
from .installation import (
    SystemRequirements as InstallationSystemRequirements,
)
from .installation_profile import InstallationProfile
from .installation_state import InstallationState
from .project import Project, ProjectStatus
from .query_result import QueryResponse, QueryResult
from .service_config import (
    ServiceConfiguration,
    ServiceName,
    ServiceStatusType,
)
from .system_requirements import SystemRequirements
from .vector_store_types import VectorStoreProvider
# Shelf-Box Rhyme System models
from .box_type import BoxType
from .box import Box
from .shelf import Shelf
from .shelf_box import ShelfBox
from .schema_version import SchemaVersion

# Rebuild Pydantic models to resolve forward references
Box.model_rebuild()
Shelf.model_rebuild()
ShelfBox.model_rebuild()

__all__ = [
    "Project",
    "ProjectStatus",
    "CrawlSession",
    "CrawlStatus",
    "Page",
    "PageStatus",
    "QueryResult",
    "QueryResponse",
    "InstallationContext",
    "ServiceStatus",
    "SetupWizardState",
    "PackageMetadata",
    "InstallationRequest",
    "InstallationResponse",
    "InstallationSystemRequirements",
    "SystemRequirements",
    "CriticalDecisionPoint",
    "InstallationState",
    "InstallationProfile",
    "ServiceConfiguration",
    "ServiceName",
    "ServiceStatusType",
    "VectorStoreProvider",
    # Shelf-Box Rhyme System models
    "BoxType",
    "Box",
    "Shelf",
    "ShelfBox",
    "SchemaVersion",
]
