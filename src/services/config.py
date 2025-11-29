"""Configuration management service for installation metadata."""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.lib.paths import get_bablib_cache_dir, get_bablib_config_dir, get_bablib_data_dir
from src.models.installation import InstallationContext, PackageMetadata, ServiceStatus

logger = logging.getLogger(__name__)


class InstallationError(Exception):
    """Base exception for installation-related errors."""
    pass


class ConfigurationError(InstallationError):
    """Configuration file issues."""
    pass


class MigrationError(InstallationError):
    """Problems during migration."""
    pass


class ConfigService:
    """Service for managing installation configuration and metadata."""

    def __init__(self):
        """Initialize configuration service."""
        self.app_name = "bablib"
        self._config_dir: Path | None = None
        self._data_dir: Path | None = None
        self._cache_dir: Path | None = None

    @property
    def config_dir(self) -> Path:
        """Get XDG-compliant configuration directory."""
        if self._config_dir is None:
            self._config_dir = get_bablib_config_dir()
        return self._config_dir

    @property
    def data_dir(self) -> Path:
        """Get XDG-compliant data directory."""
        if self._data_dir is None:
            self._data_dir = get_bablib_data_dir()
        return self._data_dir

    @property
    def cache_dir(self) -> Path:
        """Get XDG-compliant cache directory."""
        if self._cache_dir is None:
            self._cache_dir = get_bablib_cache_dir()
        return self._cache_dir

    @property
    def installation_config_path(self) -> Path:
        """Get path to installation configuration file."""
        return self.config_dir / "installation.json"

    @property
    def services_config_path(self) -> Path:
        """Get path to services configuration file."""
        return self.config_dir / "services.json"

    def ensure_directories(self) -> None:
        """Ensure all required directories exist with proper permissions."""
        for directory in [self.config_dir, self.data_dir, self.cache_dir]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                # Set appropriate permissions (user read/write only)
                directory.chmod(0o700)
            except PermissionError as e:
                raise ConfigurationError(f"Cannot create directory {directory}: {e}")
            except Exception as e:
                raise ConfigurationError(f"Error creating directory {directory}: {e}")

    def create_installation_context(
        self,
        install_method: str | None = None,
        version: str = "1.0.0",
        python_version: str = "3.13.1",
        uv_version: str | None = None,
        install_path: Path | None = None,
        is_global: bool = True
    ) -> InstallationContext:
        """Create and save installation context."""
        if install_path is None:
            # Try to detect install path
            install_path = shutil.which("bablib")
            if install_path:
                install_path = Path(install_path)
            else:
                install_path = Path("/usr/local/bin/bablib")

        # Auto-detect installation method if not provided
        if install_method is None:
            install_method = self._detect_install_method(install_path)

        # Auto-detect UV version if not provided
        if uv_version is None:
            uv_version = self._detect_uv_version()

        context = InstallationContext(
            install_method=install_method,
            install_date=datetime.now(),
            version=version,
            python_version=python_version,
            uv_version=uv_version,
            install_path=install_path,
            is_global=is_global,
            user_data_dir=self.data_dir,
            config_dir=self.config_dir,
            cache_dir=self.cache_dir
        )

        self.save_installation_context(context)
        return context

    def _detect_install_method(self, install_path: Path) -> str:
        """Detect installation method based on install path."""
        path_str = str(install_path)

        # Check for uv tool installation (typically in ~/.local/bin and not pipx)
        if ".local" in path_str and "pipx" not in path_str:
            return "uvx"
        # Check for development mode (current directory or contains src/)
        elif path_str.startswith(".") or "src" in path_str:
            return "development"
        # Everything else is considered manual
        else:
            return "manual"

    def _detect_uv_version(self) -> str | None:
        """Detect UV version if available."""
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Output format: "uv 0.4.0"
                version_line = result.stdout.strip()
                parts = version_line.split()
                if len(parts) >= 2:
                    return parts[-1]  # Return the version number
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return None

    def load_installation_context(self) -> InstallationContext | None:
        """Load installation context from configuration file."""
        if not self.installation_config_path.exists():
            return None

        try:
            with open(self.installation_config_path) as f:
                data = json.load(f)

            # Convert string paths back to Path objects
            for path_field in ['install_path', 'user_data_dir', 'config_dir', 'cache_dir']:
                if path_field in data:
                    data[path_field] = Path(data[path_field])

            # Convert ISO datetime string back to datetime
            if 'install_date' in data:
                data['install_date'] = datetime.fromisoformat(data['install_date'])

            return InstallationContext.model_validate(data)

        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Corrupted installation config: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading installation config: {e}")

    def save_installation_context(self, context: InstallationContext) -> None:
        """Save installation context to configuration file."""
        self.ensure_directories()

        try:
            # Create backup if file exists
            if self.installation_config_path.exists():
                backup_path = self.installation_config_path.with_suffix('.json.backup')
                shutil.copy2(self.installation_config_path, backup_path)

            # Write atomically using temporary file
            temp_path = self.installation_config_path.with_suffix('.json.tmp')

            with open(temp_path, 'w') as f:
                json.dump(
                    context.model_dump(mode='json'),
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            # Atomic move
            temp_path.replace(self.installation_config_path)

            # Set appropriate permissions
            self.installation_config_path.chmod(0o600)

        except Exception as e:
            # Clean up temporary file if it exists
            temp_path = self.installation_config_path.with_suffix('.json.tmp')
            if temp_path.exists():
                temp_path.unlink()
            raise ConfigurationError(f"Error saving installation config: {e}")

    def load_services_config(self) -> list[ServiceStatus]:
        """Load services configuration from file."""
        if not self.services_config_path.exists():
            return []

        try:
            with open(self.services_config_path) as f:
                data = json.load(f)

            services = []
            for service_data in data:
                # Convert ISO datetime string back to datetime
                if 'last_checked' in service_data:
                    service_data['last_checked'] = datetime.fromisoformat(service_data['last_checked'])
                services.append(ServiceStatus.model_validate(service_data))

            return services

        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Corrupted services config: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading services config: {e}")

    def save_services_config(self, services: list[ServiceStatus]) -> None:
        """Save services configuration to file."""
        self.ensure_directories()

        try:
            # Create backup if file exists
            if self.services_config_path.exists():
                backup_path = self.services_config_path.with_suffix('.json.backup')
                shutil.copy2(self.services_config_path, backup_path)

            # Write atomically using temporary file
            temp_path = self.services_config_path.with_suffix('.json.tmp')

            service_data = [service.model_dump(mode='json') for service in services]

            with open(temp_path, 'w') as f:
                json.dump(service_data, f, indent=2, ensure_ascii=False)

            # Atomic move
            temp_path.replace(self.services_config_path)

            # Set appropriate permissions
            self.services_config_path.chmod(0o600)

        except Exception as e:
            # Clean up temporary file if it exists
            temp_path = self.services_config_path.with_suffix('.json.tmp')
            if temp_path.exists():
                temp_path.unlink()
            raise ConfigurationError(f"Error saving services config: {e}")

    def get_installation_paths(self) -> dict[str, Path]:
        """Get all installation-related paths."""
        return {
            "config_dir": self.config_dir,
            "data_dir": self.data_dir,
            "cache_dir": self.cache_dir,
            "installation_config": self.installation_config_path,
            "services_config": self.services_config_path
        }

    def detect_existing_installation(self) -> dict[str, Any] | None:
        """Detect existing manual installation that could be migrated."""
        possible_paths = [
            Path.home() / ".bablib",
            Path.home() / ".local" / "share" / "bablib",
            Path("/opt/bablib"),
            Path("/usr/local/share/bablib")
        ]

        for path in possible_paths:
            if path.exists() and (path / "projects").exists():
                return {
                    "path": path,
                    "type": "manual",
                    "projects_count": len(list((path / "projects").glob("*")))
                }

        return None

    def migrate_manual_installation(self, source_path: Path) -> bool:
        """Migrate existing manual installation to uvx structure."""
        try:
            logger.info(f"Migrating manual installation from {source_path}")

            # Ensure new directories exist
            self.ensure_directories()

            # Copy user data preserving structure
            if (source_path / "projects").exists():
                dest_projects = self.data_dir / "projects"
                if dest_projects.exists():
                    # Backup existing projects
                    backup_projects = self.data_dir / f"projects.backup.{int(datetime.now().timestamp())}"
                    dest_projects.rename(backup_projects)

                shutil.copytree(source_path / "projects", dest_projects)
                logger.info(f"Migrated projects from {source_path / 'projects'} to {dest_projects}")

            # Copy configuration if it exists
            old_config = source_path / "config"
            if old_config.exists():
                for config_file in old_config.glob("*.json"):
                    dest_file = self.config_dir / config_file.name
                    if not dest_file.exists():  # Don't overwrite new config
                        shutil.copy2(config_file, dest_file)

            # Create installation context for migrated installation
            context = self.create_installation_context(
                install_method="manual",  # Will be updated to uvx later
                version="1.0.0",  # Default version for migrated
            )

            logger.info("Migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise MigrationError(f"Failed to migrate from {source_path}: {e}")

    def repair_configuration(self) -> dict[str, bool]:
        """Attempt to repair corrupted configuration files."""
        results = {"installation": False, "services": False}

        # Try to repair installation config
        if self.installation_config_path.exists():
            backup_path = self.installation_config_path.with_suffix('.json.backup')
            if backup_path.exists():
                try:
                    shutil.copy2(backup_path, self.installation_config_path)
                    # Test if it loads
                    self.load_installation_context()
                    results["installation"] = True
                    logger.info("Repaired installation config from backup")
                except Exception:
                    pass

        # Try to repair services config
        if self.services_config_path.exists():
            backup_path = self.services_config_path.with_suffix('.json.backup')
            if backup_path.exists():
                try:
                    shutil.copy2(backup_path, self.services_config_path)
                    # Test if it loads
                    self.load_services_config()
                    results["services"] = True
                    logger.info("Repaired services config from backup")
                except Exception:
                    pass

        return results

    def create_package_metadata_from_pyproject(self, pyproject_path: Path) -> PackageMetadata:
        """Create PackageMetadata from pyproject.toml file."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        with open(pyproject_path, 'rb') as f:
            data = tomllib.load(f)

        project = data.get("project", {})

        # Extract URLs
        urls = project.get("urls", {})
        homepage = urls.get("Homepage", urls.get("homepage", ""))
        repository = urls.get("Repository", urls.get("repository", homepage))

        # Extract entry points
        scripts = project.get("scripts", {})
        entry_points = {}
        if scripts:
            entry_points["console_scripts"] = f"bablib = {scripts.get('bablib', 'src.cli.main:cli')}"

        return PackageMetadata(
            name=project.get("name", "bablib"),
            version=project.get("version", "1.0.0"),
            description=project.get("description", ""),
            homepage=homepage,
            repository_url=repository,
            entry_points=entry_points,
            dependencies=project.get("dependencies", []),
            python_requires=project.get("requires-python", ">=3.13"),
            install_source="git+https://github.com/user/local-doc-bro"
        )
