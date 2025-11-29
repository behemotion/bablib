"""Installation start service for POST /installation/start endpoint implementation.

This service implements the installation start endpoint according to the API contracts
defined in specs/002-uv-command-install/contracts/installation-service.yaml.

It handles:
1. InstallationRequest validation and processing
2. Integration with InstallationWizardService
3. HTTP status code handling (200, 400, 409)
4. UUID generation for installation profiles
5. Conflict detection for existing installations
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from src.models.installation import InstallationRequest
from src.services.installation_wizard import (
    InstallationWizardError,
    InstallationWizardService,
)

logger = logging.getLogger(__name__)


class InstallationStartService:
    """Service for handling installation start requests via POST /installation/start endpoint."""

    def __init__(self):
        """Initialize the installation start service."""
        self.installation_wizard = InstallationWizardService()
        self.active_installations: dict[str, dict[str, Any]] = {}

    async def start_installation(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Start a new Bablib installation process.

        Args:
            request_data: Raw request data dictionary

        Returns:
            Installation response dictionary

        Raises:
            HTTPException: For validation errors (400), conflicts (409), or server errors (500)
        """
        try:
            # Validate request data against InstallationRequest model
            try:
                installation_request = InstallationRequest.model_validate(request_data)
            except ValidationError as e:
                logger.warning(f"Invalid installation request: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid installation request: {str(e)}"
                )

            # Check for existing installations (409 conflict)
            await self._check_installation_conflicts(installation_request)

            # Start installation using InstallationWizardService
            try:
                wizard_response = await self.installation_wizard.start_installation(installation_request)

                # Convert InstallationResponse model to dict for API response
                response_dict = {
                    "installation_id": wizard_response.installation_id,
                    "status": wizard_response.status,
                    "message": wizard_response.message
                }

                if wizard_response.next_steps:
                    response_dict["next_steps"] = wizard_response.next_steps

                # Track active installation
                self.active_installations[wizard_response.installation_id] = {
                    "installation_id": wizard_response.installation_id,
                    "install_method": installation_request.install_method,
                    "version": installation_request.version,
                    "status": wizard_response.status,
                    "started_at": datetime.now().isoformat(),
                    "force_reinstall": installation_request.force_reinstall
                }

                logger.info(f"Installation started successfully: {wizard_response.installation_id}")
                return response_dict

            except InstallationWizardError as e:
                # Check if this is a conflict error
                if "already in progress" in str(e).lower():
                    logger.warning(f"Installation conflict: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=str(e)
                    )
                else:
                    logger.error(f"Installation wizard error: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Installation failed: {str(e)}"
                    )

        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in start_installation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during installation"
            )

    async def _check_installation_conflicts(self, request: InstallationRequest) -> None:
        """Check for installation conflicts and raise 409 if found.

        Args:
            request: The installation request to check

        Raises:
            HTTPException: 409 if installation conflict detected
        """
        # Check if there's already an active installation in wizard service
        try:
            existing_state = await self.installation_wizard.load_installation_state()
            if existing_state and existing_state.current_phase not in ["complete", "error"]:
                if not request.force_reinstall:
                    logger.warning("Installation already in progress, force_reinstall not set")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Installation already in progress. Use force_reinstall=true to override."
                    )
                else:
                    # Force reinstall requested - rollback existing installation
                    logger.info("Force reinstall requested, rolling back existing installation")
                    await self.installation_wizard.rollback_installation()

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.warning(f"Error checking installation conflicts: {e}")
            # Don't fail the request if we can't check conflicts
            pass

        # Check local active installations tracking
        active_non_complete = [
            inst for inst in self.active_installations.values()
            if inst.get("status") not in ["completed", "failed"]
        ]

        if active_non_complete and not request.force_reinstall:
            logger.warning(f"Found {len(active_non_complete)} active installations")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Installation already in progress. Use force_reinstall=true to override."
            )

    def get_installation_status(self, installation_id: str) -> dict[str, Any] | None:
        """Get status of a tracked installation.

        Args:
            installation_id: The installation ID to check

        Returns:
            Installation status dict or None if not found
        """
        return self.active_installations.get(installation_id)

    def list_active_installations(self) -> list[dict[str, Any]]:
        """List all currently tracked active installations.

        Returns:
            List of active installation status dicts
        """
        return list(self.active_installations.values())

    async def cleanup_completed_installations(self) -> None:
        """Clean up completed or failed installations from tracking."""
        # Get current status from wizard service for each tracked installation
        to_remove = []
        for installation_id, install_data in self.active_installations.items():
            try:
                wizard_status = self.installation_wizard.get_installation_status()
                if wizard_status.get("status") in ["not_started", "completed", "failed"]:
                    to_remove.append(installation_id)
            except Exception as e:
                logger.warning(f"Error checking status for {installation_id}: {e}")

        # Remove completed installations
        for installation_id in to_remove:
            del self.active_installations[installation_id]
            logger.info(f"Cleaned up completed installation: {installation_id}")
