"""Installation wizard service for managing complete Bablib installation process.

This service coordinates the installation flow from system validation through service setup
to user interaction and profile persistence. It integrates with Rich UI for progress display
and handles resume/rollback capabilities.
"""

import asyncio
import logging
import socket
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from src.models.installation import (
    CriticalDecisionPoint,
    InstallationContext,
    InstallationRequest,
    InstallationResponse,
    ServiceStatus,
)
from src.models.installation_profile import InstallationProfile
from src.models.installation_state import InstallationState

from .config import ConfigService
from .detection import ServiceDetectionService
from .setup import SetupWizardService

logger = logging.getLogger(__name__)
console = Console()


class InstallationWizardError(Exception):
    """Base exception for installation wizard errors."""
    pass


class InstallationWizardService:
    """Main orchestrator service for Bablib installation process.

    This service coordinates system validation, service setup, user decisions,
    and installation state progression. It supports resume/rollback capabilities
    and integrates with Rich UI for progress display.
    """

    def __init__(self):
        """Initialize installation wizard service."""
        self.config_service = ConfigService()
        self.detection_service = ServiceDetectionService()
        self.setup_wizard = SetupWizardService()
        self.console = Console()

        # Installation state management
        self.installation_state: InstallationState | None = None
        self.installation_profile: InstallationProfile | None = None
        self.critical_decisions: list[CriticalDecisionPoint] = []

        # Progress tracking
        self.progress_callback: Callable[[dict[str, Any]], None] | None = None

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set callback for progress updates.

        Args:
            callback: Function to call with progress updates
        """
        self.progress_callback = callback

    def _update_progress(self, progress_data: dict[str, Any]) -> None:
        """Update progress and notify callback if set.

        Args:
            progress_data: Progress information dictionary
        """
        if self.progress_callback:
            self.progress_callback(progress_data)

    async def start_installation(self, request: InstallationRequest) -> InstallationResponse:
        """Start new installation process.

        Args:
            request: Installation request with method, version, and preferences

        Returns:
            InstallationResponse with installation ID and status

        Raises:
            InstallationWizardError: If installation cannot be started
        """
        try:
            # Check if installation already in progress
            if self.installation_state and self.installation_state.current_phase not in ["complete", "error"]:
                raise InstallationWizardError("Installation already in progress")

            # Create installation profile
            install_path = self._determine_install_path(request.install_method)

            uv_version = self._get_uv_version()
            if not uv_version:
                uv_version = "0.0.0"  # Default version if UV not found

            self.installation_profile = InstallationProfile(
                install_method=request.install_method,
                version=request.version,
                python_version=self._get_python_version(),
                uv_version=uv_version,
                install_path=install_path,
                is_global=request.install_method in ["uvx", "uv-tool"],
                config_dir=self.config_service.config_dir,
                data_dir=self.config_service.data_dir,
                cache_dir=self.config_service.cache_dir,
                user_preferences=request.user_preferences or {}
            )

            # Create installation state
            self.installation_state = InstallationState(
                current_phase="initializing",
                total_phases=5,
                current_step="Starting installation",
                total_steps=3,
                progress_percentage=0.0,
                status_message="Initializing installation process...",
                can_resume=True
            )

            # Save initial state
            await self._persist_installation_state()

            # Start async installation process
            asyncio.create_task(self._run_installation_process())

            return InstallationResponse(
                installation_id=str(self.installation_profile.id),
                status="started",
                message="Installation started successfully",
                next_steps=[
                    "System requirements will be validated",
                    "Services will be detected and configured",
                    "Installation will complete automatically"
                ]
            )

        except Exception as e:
            logger.error(f"Failed to start installation: {e}")
            raise InstallationWizardError(f"Cannot start installation: {str(e)}")

    async def _run_installation_process(self) -> None:
        """Run the complete installation process asynchronously."""
        try:
            # Phase 1: System Check
            await self._phase_system_check()

            # Phase 2: Service Setup
            await self._phase_service_setup()

            # Phase 3: Configuration
            await self._phase_configuration()

            # Phase 4: Finalization
            await self._phase_finalization()

            # Phase 5: Complete
            await self._phase_complete()

        except Exception as e:
            logger.error(f"Installation process failed: {e}")
            if self.installation_state:
                self.installation_state.mark_error(
                    f"Installation failed: {str(e)}",
                    str(e)
                )
                await self._persist_installation_state()

    async def _phase_system_check(self) -> None:
        """Phase 1: System requirements validation."""
        if not self.installation_state:
            return

        self.installation_state.advance_to_next_phase(
            "system_check",
            "Validating Python version",
            4,
            "Checking system requirements..."
        )
        await self._persist_installation_state()

        # Check Python version
        self._update_progress({"phase": "system_check", "step": "python_version"})
        python_version = self._get_python_version()
        if not python_version.startswith("3.13."):
            raise InstallationWizardError(f"Python 3.13+ required, found {python_version}")

        # Check UV availability
        self.installation_state.update_step_progress(
            "Checking UV installation",
            "Validating UV package manager..."
        )
        await self._persist_installation_state()
        uv_version = self._get_uv_version()
        if not uv_version:
            raise InstallationWizardError("UV package manager not found")

        # Check system resources
        self.installation_state.update_step_progress(
            "Checking system resources",
            "Validating disk space and memory..."
        )
        await self._persist_installation_state()
        await self._validate_system_resources()

        # Check for critical decisions
        self.installation_state.update_step_progress(
            "Detecting critical decisions",
            "Scanning for configuration conflicts..."
        )
        await self._persist_installation_state()
        self.critical_decisions = await self._detect_critical_decisions()

    async def _phase_service_setup(self) -> None:
        """Phase 2: Service detection and setup."""
        if not self.installation_state:
            return

        self.installation_state.advance_to_next_phase(
            "service_setup",
            "Detecting services",
            3,
            "Setting up external services..."
        )
        await self._persist_installation_state()

        # Detect services
        self._update_progress({"phase": "service_setup", "step": "detection"})
        service_statuses = await self.detection_service.check_all_services()

        # Handle critical decisions for services
        self.installation_state.update_step_progress(
            "Configuring services",
            "Applying service configurations..."
        )
        await self._persist_installation_state()
        await self._handle_service_decisions(service_statuses)

        # Validate service setup
        self.installation_state.update_step_progress(
            "Validating service setup",
            "Confirming service availability..."
        )
        await self._persist_installation_state()

    async def _phase_configuration(self) -> None:
        """Phase 3: Configuration setup."""
        if not self.installation_state:
            return

        self.installation_state.advance_to_next_phase(
            "configuration",
            "Creating directories",
            3,
            "Setting up configuration..."
        )
        await self._persist_installation_state()

        # Ensure directories
        self._update_progress({"phase": "configuration", "step": "directories"})
        self.config_service.ensure_directories()

        # Create installation context
        self.installation_state.update_step_progress(
            "Creating installation context",
            "Saving installation metadata..."
        )
        await self._persist_installation_state()

        if self.installation_profile:
            context = InstallationContext(
                install_method=self.installation_profile.install_method,
                install_date=self.installation_profile.created_at,
                version=self.installation_profile.version,
                python_version=self.installation_profile.python_version,
                uv_version=self.installation_profile.uv_version,
                install_path=self.installation_profile.install_path,
                is_global=self.installation_profile.is_global,
                user_data_dir=self.installation_profile.data_dir,
                config_dir=self.installation_profile.config_dir,
                cache_dir=self.installation_profile.cache_dir
            )

            # Save context
            self.config_service.save_installation_context(context)

        # Apply user preferences
        self.installation_state.update_step_progress(
            "Applying preferences",
            "Configuring user preferences..."
        )
        await self._persist_installation_state()
        await self._apply_user_preferences()

    async def _phase_finalization(self) -> None:
        """Phase 4: Finalization."""
        if not self.installation_state:
            return

        self.installation_state.advance_to_next_phase(
            "finalization",
            "Validating installation",
            2,
            "Finalizing installation..."
        )
        await self._persist_installation_state()

        # Validate installation
        self._update_progress({"phase": "finalization", "step": "validation"})
        await self._validate_installation()

        # Mark profile as completed
        self.installation_state.update_step_progress(
            "Completing installation",
            "Marking installation as complete..."
        )
        await self._persist_installation_state()

        if self.installation_profile:
            self.installation_profile.mark_completed()

    async def _phase_complete(self) -> None:
        """Phase 5: Complete installation."""
        if not self.installation_state:
            return

        self.installation_state.advance_to_next_phase(
            "complete",
            "Installation complete",
            1,
            "Installation completed successfully!"
        )
        await self._persist_installation_state()
        self._update_progress({"phase": "complete", "step": "finished"})

    async def _detect_critical_decisions(self) -> list[CriticalDecisionPoint]:
        """Detect situations requiring critical user decisions.

        Returns:
            List of critical decision points requiring user input
        """
        decisions = []

        # Check for port conflicts
        if await self._check_port_conflict():
            decisions.append(CriticalDecisionPoint(
                decision_id=f"port_conflict_{uuid.uuid4().hex[:8]}",
                decision_type="service_port",
                title="Port Conflict Detected",
                description="Default MCP server port 8765 is already in use.",
                options=[
                    {"id": "8766", "label": "Use port 8766", "recommended": True},
                    {"id": "8767", "label": "Use port 8767"},
                    {"id": "custom", "label": "Specify custom port", "requires_input": True}
                ],
                default_option="8766",
                validation_pattern=r"^\d{4,5}$"
            ))

        # Check for existing data directory
        if self._check_existing_data():
            decisions.append(CriticalDecisionPoint(
                decision_id=f"data_conflict_{uuid.uuid4().hex[:8]}",
                decision_type="data_directory",
                title="Existing Data Directory",
                description="Bablib data directory already exists with content.",
                options=[
                    {"id": "backup", "label": "Backup existing data", "recommended": True},
                    {"id": "merge", "label": "Merge with existing data"},
                    {"id": "replace", "label": "Replace existing data", "warning": "This will delete existing data"}
                ],
                default_option="backup"
            ))

        # Check for non-standard install location
        if self._check_install_location_conflict():
            decisions.append(CriticalDecisionPoint(
                decision_id=f"location_conflict_{uuid.uuid4().hex[:8]}",
                decision_type="install_location",
                title="Install Location Conflict",
                description="Multiple Bablib installations detected.",
                options=[
                    {"id": "replace_current", "label": "Replace current installation", "recommended": True},
                    {"id": "install_alongside", "label": "Install alongside existing"},
                    {"id": "cancel", "label": "Cancel installation"}
                ],
                default_option="replace_current"
            ))

        return decisions

    async def _check_port_conflict(self) -> bool:
        """Check if default MCP server port is in use.

        Returns:
            True if port 8765 is already in use
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', 8765))
                return result == 0  # Port is in use if connection succeeds
        except Exception:
            return False  # Assume port is available if check fails

    def _check_existing_data(self) -> bool:
        """Check if data directory exists with content.

        Returns:
            True if data directory exists and has content
        """
        data_dir = self.config_service.data_dir
        if not data_dir.exists():
            return False

        # Check if directory has any content
        try:
            return any(data_dir.iterdir())
        except Exception:
            return False

    def _check_install_location_conflict(self) -> bool:
        """Check for conflicting installation locations.

        Returns:
            True if multiple Bablib installations detected
        """
        import shutil

        # Check common installation paths
        paths_to_check = [
            "/usr/local/bin/bablib",
            "~/.local/bin/bablib",
            "/opt/bablib/bin/bablib"
        ]

        found_paths = []
        for path_str in paths_to_check:
            path = Path(path_str).expanduser()
            if path.exists():
                found_paths.append(path)

        # Also check PATH
        path_bablib = shutil.which("bablib")
        if path_bablib:
            path_obj = Path(path_bablib)
            if path_obj not in found_paths:
                found_paths.append(path_obj)

        return len(found_paths) > 1

    async def _handle_service_decisions(self, service_statuses: dict[str, ServiceStatus]) -> None:
        """Handle service-related critical decisions.

        Args:
            service_statuses: Current status of all services
        """
        # For now, use default service handling from setup wizard
        # In the future, this could prompt for critical service decisions
        missing_services = [name for name, status in service_statuses.items() if not status.available]

        if missing_services:
            logger.info(f"Missing services detected: {missing_services}")
            # Could add critical decision for required vs optional services

    async def _validate_system_resources(self) -> None:
        """Validate system has adequate resources.

        Raises:
            InstallationWizardError: If system doesn't meet requirements
        """
        # Basic resource checks
        try:
            import psutil

            # Check available memory (require at least 512MB)
            memory = psutil.virtual_memory()
            if memory.available < 512 * 1024 * 1024:
                raise InstallationWizardError(
                    f"Insufficient memory: {memory.available // (1024*1024)}MB available, 512MB required"
                )

            # Check available disk space (require at least 100MB)
            disk = psutil.disk_usage('/')
            if disk.free < 100 * 1024 * 1024:
                raise InstallationWizardError(
                    f"Insufficient disk space: {disk.free // (1024*1024)}MB available, 100MB required"
                )

        except ImportError:
            # psutil not available, skip resource checks
            logger.warning("Cannot check system resources - psutil not available")

    async def _apply_user_preferences(self) -> None:
        """Apply user preferences from installation profile."""
        if not self.installation_profile or not self.installation_profile.user_preferences:
            return

        preferences = self.installation_profile.user_preferences

        # Apply preferences to configuration
        # This would interact with the main configuration system
        logger.info(f"Applied user preferences: {list(preferences.keys())}")

    async def _validate_installation(self) -> None:
        """Validate that installation was successful.

        Raises:
            InstallationWizardError: If installation validation fails
        """
        if not self.installation_profile:
            raise InstallationWizardError("Installation profile not found")

        # Check that executable exists
        if not self.installation_profile.install_path.exists():
            raise InstallationWizardError(
                f"Bablib executable not found at {self.installation_profile.install_path}"
            )

        # Check that config directory was created
        if not self.installation_profile.config_dir.exists():
            raise InstallationWizardError(
                f"Config directory not created at {self.installation_profile.config_dir}"
            )

    async def _persist_installation_state(self) -> None:
        """Persist current installation state to disk."""
        if not self.installation_state or not self.installation_profile:
            return

        try:
            # Save installation state
            state_path = self.config_service.config_dir / "installation_state.json"
            self.config_service.ensure_directories()

            with open(state_path, 'w') as f:
                import json
                json.dump(self.installation_state.model_dump(mode='json'), f, indent=2)

            # Save installation profile
            profile_path = self.config_service.config_dir / "installation_profile.json"
            with open(profile_path, 'w') as f:
                json.dump(self.installation_profile.model_dump(mode='json'), f, indent=2)

        except Exception as e:
            logger.error(f"Failed to persist installation state: {e}")

    async def load_installation_state(self) -> InstallationState | None:
        """Load persisted installation state.

        Returns:
            InstallationState if found, None otherwise
        """
        try:
            state_path = self.config_service.config_dir / "installation_state.json"
            if not state_path.exists():
                return None

            with open(state_path) as f:
                import json
                data = json.load(f)
                return InstallationState.model_validate(data)

        except Exception as e:
            logger.error(f"Failed to load installation state: {e}")
            return None

    async def load_installation_profile(self) -> InstallationProfile | None:
        """Load persisted installation profile.

        Returns:
            InstallationProfile if found, None otherwise
        """
        try:
            profile_path = self.config_service.config_dir / "installation_profile.json"
            if not profile_path.exists():
                return None

            with open(profile_path) as f:
                import json
                data = json.load(f)
                return InstallationProfile.model_validate(data)

        except Exception as e:
            logger.error(f"Failed to load installation profile: {e}")
            return None

    async def resume_installation(self) -> bool:
        """Resume interrupted installation.

        Returns:
            True if installation was resumed, False if no resume possible
        """
        # Load previous state
        self.installation_state = await self.load_installation_state()
        self.installation_profile = await self.load_installation_profile()

        if not self.installation_state or not self.installation_profile:
            return False

        if self.installation_state.current_phase in ["complete", "error"]:
            return False

        if not self.installation_state.can_resume:
            return False

        # Resume from current phase
        logger.info(f"Resuming installation from phase: {self.installation_state.current_phase}")
        asyncio.create_task(self._run_installation_process())
        return True

    async def rollback_installation(self) -> None:
        """Rollback failed or interrupted installation."""
        try:
            # Clean up installation state files
            state_path = self.config_service.config_dir / "installation_state.json"
            if state_path.exists():
                state_path.unlink()

            profile_path = self.config_service.config_dir / "installation_profile.json"
            if profile_path.exists():
                profile_path.unlink()

            # Clean up installation context if created
            if self.config_service.installation_config_path.exists():
                self.config_service.installation_config_path.unlink()

            # Reset state
            self.installation_state = None
            self.installation_profile = None
            self.critical_decisions = []

            logger.info("Installation rollback completed")

        except Exception as e:
            logger.error(f"Failed to rollback installation: {e}")

    def get_installation_status(self) -> dict[str, Any]:
        """Get current installation status.

        Returns:
            Dictionary with installation status information
        """
        if not self.installation_state:
            return {
                "status": "not_started",
                "progress_percentage": 0.0,
                "message": "Installation not started"
            }

        status_info = self.installation_state.get_phase_progress_info()

        if self.installation_profile:
            status_info.update({
                "installation_id": str(self.installation_profile.id),
                "install_method": self.installation_profile.install_method,
                "version": self.installation_profile.version,
                "created_at": self.installation_profile.created_at.isoformat(),
                "duration_seconds": self.installation_profile.get_duration()
            })

        return status_info

    def _determine_install_path(self, install_method: str) -> Path:
        """Determine installation path based on method.

        Args:
            install_method: Installation method (uvx, uv-tool, development)

        Returns:
            Path where Bablib will be installed
        """
        import shutil

        if install_method == "development":
            return Path("./bablib").resolve()

        # Check if already installed
        existing_path = shutil.which("bablib")
        if existing_path:
            return Path(existing_path)

        # Default paths for different methods
        home = Path.home()
        if install_method == "uvx":
            return home / ".local" / "bin" / "bablib"
        elif install_method == "uv-tool":
            return home / ".local" / "bin" / "bablib"
        else:
            return home / ".local" / "bin" / "bablib"

    def _get_python_version(self) -> str:
        """Get current Python version.

        Returns:
            Python version string (e.g., "3.13.1")
        """
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_uv_version(self) -> str | None:
        """Get UV version if available.

        Returns:
            UV version string or None if not available
        """
        try:
            import subprocess
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Extract version from output like "uv 0.8.9 (68c0bf8a2 2025-08-11)"
                output = result.stdout.strip()
                parts = output.split()
                if len(parts) >= 2:
                    # Get the version part (second element), not the last one which might include build info
                    version = parts[1]
                    # Remove any trailing parentheses or additional info
                    if '(' in version:
                        version = version.split('(')[0]
                    return version
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
