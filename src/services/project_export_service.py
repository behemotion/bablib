"""Project export service for settings backup and recreation support."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..models.unified_project import UnifiedProject
from ..logic.projects.models.project import ProjectType


logger = logging.getLogger(__name__)


class ProjectExport(BaseModel):
    """Project export data for backup and recreation."""

    project_name: str = Field(..., description="Original project name")
    project_type: ProjectType = Field(..., description="Project type")
    schema_version: int = Field(..., description="Schema version at export")
    exported_at: datetime = Field(default_factory=datetime.utcnow, description="Export timestamp")
    settings: dict[str, Any] = Field(default_factory=dict, description="Project settings")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Project metadata")
    source_url: Optional[str] = Field(default=None, description="Source URL if applicable")
    statistics: dict[str, Any] = Field(default_factory=dict, description="Project statistics")

    # Export metadata
    export_version: str = Field(default="1.0", description="Export format version")
    bablib_version: Optional[str] = Field(default=None, description="Bablib version that created export")
    export_type: str = Field(default="full", description="Type of export (full, settings-only)")

    def to_json(self, pretty: bool = True) -> str:
        """Convert export to JSON string."""
        data = self.model_dump(mode='json')
        # Convert datetime to ISO format
        data['exported_at'] = self.exported_at.isoformat()

        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'ProjectExport':
        """Create ProjectExport from JSON string."""
        data = json.loads(json_str)

        # Convert datetime field
        if 'exported_at' in data:
            data['exported_at'] = datetime.fromisoformat(data['exported_at'])

        return cls(**data)

    def get_filename(self, include_timestamp: bool = True) -> str:
        """Get suggested filename for export."""
        clean_name = "".join(c for c in self.project_name if c.isalnum() or c in '-_')

        if include_timestamp:
            timestamp = self.exported_at.strftime("%Y%m%d_%H%M%S")
            return f"{clean_name}_{timestamp}_export.json"
        else:
            return f"{clean_name}_export.json"


class ProjectExportService:
    """Service for exporting project settings and metadata."""

    def __init__(self):
        """Initialize export service."""
        self.logger = logging.getLogger(__name__)

    async def export_project(
        self,
        project: UnifiedProject,
        export_type: str = "full",
        include_statistics: bool = True
    ) -> ProjectExport:
        """
        Export project to backup format.

        Args:
            project: Project to export
            export_type: Type of export (full, settings-only)
            include_statistics: Whether to include statistics

        Returns:
            ProjectExport object with all relevant data
        """
        try:
            # Get Bablib version if available
            bablib_version = await self._get_bablib_version()

            # Prepare statistics
            statistics = {}
            if include_statistics and export_type == "full":
                statistics = project.statistics.copy()

            # Create export
            export = ProjectExport(
                project_name=project.name,
                project_type=project.type,
                schema_version=project.schema_version,
                settings=project.settings.copy(),
                metadata=project.metadata.copy(),
                source_url=project.source_url,
                statistics=statistics,
                export_type=export_type,
                bablib_version=bablib_version
            )

            self.logger.info(f"Exported project '{project.name}' (type: {export_type})")
            return export

        except Exception as e:
            self.logger.error(f"Failed to export project '{project.name}': {e}")
            raise

    async def export_to_file(
        self,
        project: UnifiedProject,
        output_path: Optional[Path] = None,
        export_type: str = "full",
        include_statistics: bool = True,
        pretty_json: bool = True
    ) -> Path:
        """
        Export project to JSON file.

        Args:
            project: Project to export
            output_path: Optional output file path
            export_type: Type of export
            include_statistics: Whether to include statistics
            pretty_json: Whether to format JSON nicely

        Returns:
            Path to created export file
        """
        # Create export
        export = await self.export_project(project, export_type, include_statistics)

        # Determine output path
        if output_path is None:
            output_path = Path.cwd() / export.get_filename()
        elif output_path.is_dir():
            output_path = output_path / export.get_filename()

        # Write to file
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(export.to_json(pretty=pretty_json))

            self.logger.info(f"Exported project '{project.name}' to {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to write export file to {output_path}: {e}")
            raise

    async def export_multiple_projects(
        self,
        projects: list[UnifiedProject],
        output_dir: Optional[Path] = None,
        export_type: str = "full",
        include_statistics: bool = True
    ) -> list[Path]:
        """
        Export multiple projects to files.

        Args:
            projects: List of projects to export
            output_dir: Output directory for exports
            export_type: Type of export
            include_statistics: Whether to include statistics

        Returns:
            List of paths to created export files
        """
        if output_dir is None:
            output_dir = Path.cwd() / "project_exports"

        output_dir.mkdir(parents=True, exist_ok=True)

        export_paths = []

        for project in projects:
            try:
                export_path = await self.export_to_file(
                    project=project,
                    output_path=output_dir,
                    export_type=export_type,
                    include_statistics=include_statistics
                )
                export_paths.append(export_path)

            except Exception as e:
                self.logger.error(f"Failed to export project '{project.name}': {e}")
                # Continue with other projects

        self.logger.info(f"Exported {len(export_paths)} projects to {output_dir}")
        return export_paths

    async def load_export_from_file(self, file_path: Path) -> ProjectExport:
        """
        Load project export from JSON file.

        Args:
            file_path: Path to export file

        Returns:
            ProjectExport object
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            export = ProjectExport.from_json(content)
            self.logger.info(f"Loaded export for project '{export.project_name}' from {file_path}")
            return export

        except Exception as e:
            self.logger.error(f"Failed to load export from {file_path}: {e}")
            raise

    async def validate_export(self, export: ProjectExport) -> dict[str, Any]:
        """
        Validate project export for recreation.

        Args:
            export: ProjectExport to validate

        Returns:
            Validation result with issues and recommendations
        """
        issues = []
        warnings = []
        recommendations = []

        # Check export format version
        if export.export_version != "1.0":
            warnings.append(f"Export format version {export.export_version} may not be fully supported")

        # Check project type
        if not export.project_type:
            issues.append("Project type is missing or invalid")

        # Check required settings for project type
        required_settings = self._get_required_settings(export.project_type)
        missing_settings = [s for s in required_settings if s not in export.settings]
        if missing_settings:
            issues.append(f"Missing required settings: {', '.join(missing_settings)}")

        # Check for deprecated settings
        deprecated_settings = self._get_deprecated_settings()
        deprecated_found = [s for s in export.settings.keys() if s in deprecated_settings]
        if deprecated_found:
            warnings.append(f"Deprecated settings found: {', '.join(deprecated_found)}")

        # Check schema version compatibility
        current_version = 3  # Current unified schema version
        if export.schema_version != current_version:
            recommendations.append(
                f"Export is from schema version {export.schema_version}, "
                f"recreation will use current version {current_version}"
            )

        # Check export age
        age_days = (datetime.now(timezone.utc) - export.exported_at).days
        if age_days > 30:
            warnings.append(f"Export is {age_days} days old - settings may be outdated")

        is_valid = len(issues) == 0

        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "export_age_days": age_days,
            "schema_version_change": export.schema_version != current_version
        }

    async def get_recreation_preview(self, export: ProjectExport) -> dict[str, Any]:
        """
        Get preview of what will be created during recreation.

        Args:
            export: ProjectExport to preview

        Returns:
            Preview of recreation results
        """
        # Validate export first
        validation = await self.validate_export(export)

        # Prepare settings for current schema
        updated_settings = export.settings.copy()

        # Apply any necessary setting migrations
        updated_settings = await self._migrate_settings(updated_settings, export.project_type)

        # Get default settings for missing values
        default_settings = self._get_default_settings(export.project_type)
        for key, value in default_settings.items():
            if key not in updated_settings:
                updated_settings[key] = value

        preview = {
            "project_name": export.project_name,
            "project_type": export.project_type.value,
            "new_schema_version": 3,
            "preserved_settings": updated_settings,
            "preserved_metadata": export.metadata,
            "source_url": export.source_url,
            "validation": validation,
            "changes": {
                "schema_version": f"v{export.schema_version} → v3",
                "settings_updated": len(updated_settings) != len(export.settings),
                "new_defaults_added": len(default_settings) > 0
            }
        }

        return preview

    def _get_required_settings(self, project_type: ProjectType) -> list[str]:
        """Get required settings for project type."""
        requirements = {
            ProjectType.CRAWLING: ['crawl_depth'],
            ProjectType.DATA: ['chunk_size', 'embedding_model'],
            ProjectType.STORAGE: ['enable_compression']
        }
        return requirements.get(project_type, [])

    def _get_deprecated_settings(self) -> list[str]:
        """Get list of deprecated setting names."""
        return [
            'use_legacy_parser',
            'old_vector_format',
            'deprecated_embedding_model',
            'legacy_chunk_strategy'
        ]

    def _get_default_settings(self, project_type: ProjectType) -> dict[str, Any]:
        """Get default settings for project type."""
        defaults = {
            ProjectType.CRAWLING: {
                'rate_limit': 1.0,
                'user_agent': 'Bablib/1.0',
                'max_file_size': 10485760,
                'allowed_formats': ['html', 'pdf', 'txt', 'md']
            },
            ProjectType.DATA: {
                'chunk_overlap': 50,
                'vector_store_type': 'sqlite_vec',
                'max_file_size': 52428800,
                'allowed_formats': ['pdf', 'docx', 'txt', 'md', 'html', 'json']
            },
            ProjectType.STORAGE: {
                'auto_tagging': True,
                'full_text_indexing': True,
                'max_file_size': 104857600,
                'allowed_formats': ['*']
            }
        }
        return defaults.get(project_type, {})

    async def _migrate_settings(self, settings: dict[str, Any], project_type: ProjectType) -> dict[str, Any]:
        """Migrate settings to current schema format."""
        migrated = settings.copy()

        # Remove deprecated settings
        deprecated = self._get_deprecated_settings()
        for key in deprecated:
            if key in migrated:
                del migrated[key]
                self.logger.info(f"Removed deprecated setting: {key}")

        # Apply specific migrations based on project type
        if project_type == ProjectType.CRAWLING:
            # Ensure crawl_depth is within valid range
            if 'crawl_depth' in migrated:
                depth = migrated['crawl_depth']
                if not isinstance(depth, int) or depth < 1 or depth > 10:
                    migrated['crawl_depth'] = 3
                    self.logger.info("Reset crawl_depth to default value (3)")

        elif project_type == ProjectType.DATA:
            # Update embedding model if using old name
            if 'embedding_model' in migrated:
                old_models = {
                    'sentence-transformers/all-MiniLM-L6-v2': 'mxbai-embed-large',
                    'text-embedding-ada-002': 'mxbai-embed-large'
                }
                if migrated['embedding_model'] in old_models:
                    migrated['embedding_model'] = old_models[migrated['embedding_model']]
                    self.logger.info(f"Updated embedding model to {migrated['embedding_model']}")

        return migrated

    async def _get_bablib_version(self) -> Optional[str]:
        """Get current Bablib version."""
        try:
            # Try to get version from package
            import importlib.metadata
            return importlib.metadata.version('bablib')
        except Exception:
            # Fallback to reading from pyproject.toml or version file
            try:
                import toml
                with open('pyproject.toml', 'r') as f:
                    pyproject = toml.load(f)
                return pyproject.get('project', {}).get('version')
            except Exception:
                return None

    async def create_batch_export(
        self,
        projects: list[UnifiedProject],
        output_path: Optional[Path] = None,
        include_statistics: bool = False
    ) -> Path:
        """
        Create a single file containing exports for multiple projects.

        Args:
            projects: List of projects to export
            output_path: Optional output file path
            include_statistics: Whether to include statistics

        Returns:
            Path to created batch export file
        """
        exports = []

        for project in projects:
            export = await self.export_project(
                project=project,
                export_type="full",
                include_statistics=include_statistics
            )
            exports.append(export.model_dump(mode='json'))

        batch_data = {
            "batch_export_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_projects": len(projects),
            "bablib_version": await self._get_bablib_version(),
            "projects": exports
        }

        # Determine output path
        if output_path is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = Path.cwd() / f"bablib_projects_batch_{timestamp}.json"

        # Write batch export
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Created batch export with {len(projects)} projects: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to create batch export: {e}")
            raise