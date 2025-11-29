"""Installation state tracking model for Bablib installation process."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InstallationState(BaseModel):
    """Track the complete state of Bablib installation process.

    This model tracks the installation through multiple phases with detailed
    progress information, error handling, and resume capabilities.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )

    # Phase tracking
    current_phase: Literal[
        "initializing", "system_check", "service_setup",
        "configuration", "finalization", "complete", "error"
    ] = Field(..., description="Current installation phase")

    total_phases: int = Field(..., description="Total number of phases in installation", gt=0)
    completed_phases: list[str] = Field(
        default_factory=list,
        description="List of completed phase names"
    )

    # Step tracking within current phase
    current_step: str = Field(..., description="Current step within the phase")
    total_steps: int = Field(..., description="Total steps in current phase", gt=0)

    # Progress information
    progress_percentage: float = Field(
        ...,
        description="Overall installation progress as percentage",
        ge=0.0,
        le=100.0
    )

    # Status and error handling
    status_message: str = Field(..., description="Human-readable status message")
    can_resume: bool = Field(..., description="Whether installation can be resumed if interrupted")
    error_occurred: bool = Field(default=False, description="Whether an error has occurred")
    error_details: str | None = Field(
        default=None,
        description="Detailed error information if error occurred"
    )

    @field_validator('current_phase')
    @classmethod
    def validate_current_phase(cls, v: str) -> str:
        """Validate current phase is a valid phase name."""
        valid_phases = {
            "initializing", "system_check", "service_setup",
            "configuration", "finalization", "complete", "error"
        }
        if v not in valid_phases:
            raise ValueError(f"current_phase must be one of {valid_phases}")
        return v

    @field_validator('completed_phases')
    @classmethod
    def validate_completed_phases(cls, v: list[str]) -> list[str]:
        """Validate completed phases are valid phase names."""
        valid_phases = {
            "initializing", "system_check", "service_setup",
            "configuration", "finalization", "complete"
        }
        for phase in v:
            if phase not in valid_phases:
                raise ValueError(f"Invalid completed phase: '{phase}'. Must be one of {valid_phases}")
        return v

    @field_validator('progress_percentage')
    @classmethod
    def validate_progress_percentage(cls, v: float) -> float:
        """Validate progress percentage is within valid range."""
        if not 0.0 <= v <= 100.0:
            raise ValueError("progress_percentage must be between 0.0 and 100.0")
        return v

    @model_validator(mode='after')
    def validate_state_consistency(self) -> 'InstallationState':
        """Validate that the installation state is internally consistent."""

        # Error state validation
        if self.current_phase == "error":
            if not self.error_occurred:
                raise ValueError("error_occurred must be True when current_phase is 'error'")
            if not self.error_details:
                raise ValueError("error_details must be provided when current_phase is 'error'")

        # Complete state validation
        if self.current_phase == "complete":
            if self.progress_percentage != 100.0:
                raise ValueError("progress_percentage must be 100.0 when current_phase is 'complete'")
            if self.error_occurred:
                raise ValueError("error_occurred must be False when current_phase is 'complete'")

        # Phase progression validation
        phase_order = ["initializing", "system_check", "service_setup", "configuration", "finalization"]

        if self.current_phase in phase_order:
            current_index = phase_order.index(self.current_phase)

            # Check that all previous phases are completed
            for i in range(current_index):
                required_phase = phase_order[i]
                if required_phase not in self.completed_phases:
                    raise ValueError(
                        f"Phase '{required_phase}' must be completed before '{self.current_phase}'"
                    )

        # Completed phases should not include current phase (unless complete/error)
        if self.current_phase not in ["complete", "error"]:
            if self.current_phase in self.completed_phases:
                raise ValueError(f"current_phase '{self.current_phase}' cannot be in completed_phases")

        # Resume capability validation
        if self.current_phase in ["complete", "error"]:
            if self.can_resume:
                raise ValueError("can_resume must be False when installation is complete or errored")

        return self

    def advance_to_next_phase(
        self,
        next_phase: str,
        next_step: str,
        total_steps: int,
        status_message: str
    ) -> None:
        """Advance to the next phase of installation.

        Args:
            next_phase: The next phase to advance to
            next_step: The first step in the new phase
            total_steps: Total steps in the new phase
            status_message: Status message for the new phase
        """
        # Add current phase to completed phases (if not already there)
        if (self.current_phase not in self.completed_phases and
            self.current_phase not in ["initializing", "complete", "error"]):
            self.completed_phases.append(self.current_phase)

        # Special handling for initializing phase - it gets completed when moving to next phase
        if self.current_phase == "initializing" and next_phase != "initializing":
            self.completed_phases.append("initializing")

        # Update progress based on phase completion
        phase_weights = {
            "initializing": 5,    # 5%
            "system_check": 15,   # 15%
            "service_setup": 40,  # 40%
            "configuration": 25,  # 25%
            "finalization": 15,   # 15%
        }

        completed_weight = sum(phase_weights.get(phase, 0) for phase in self.completed_phases)

        # Update to new phase (disable validation temporarily)
        object.__setattr__(self, 'current_phase', next_phase)
        object.__setattr__(self, 'current_step', next_step)
        object.__setattr__(self, 'total_steps', total_steps)
        object.__setattr__(self, 'status_message', status_message)

        if next_phase == "complete":
            object.__setattr__(self, 'progress_percentage', 100.0)
            object.__setattr__(self, 'can_resume', False)
        else:
            object.__setattr__(self, 'progress_percentage', min(completed_weight, 95.0))  # Cap at 95% until complete

    def mark_error(self, error_message: str, error_details: str | None = None) -> None:
        """Mark the installation as errored.

        Args:
            error_message: Brief error message for status
            error_details: Detailed error information
        """
        object.__setattr__(self, 'current_phase', "error")
        object.__setattr__(self, 'error_occurred', True)
        object.__setattr__(self, 'status_message', error_message)
        object.__setattr__(self, 'error_details', error_details)
        object.__setattr__(self, 'can_resume', True)  # Allow retry from error state

    def update_step_progress(self, current_step: str, status_message: str) -> None:
        """Update the current step and status message within the current phase.

        Args:
            current_step: The current step description
            status_message: Updated status message
        """
        object.__setattr__(self, 'current_step', current_step)
        object.__setattr__(self, 'status_message', status_message)

    def get_phase_progress_info(self) -> dict:
        """Get detailed progress information about the current installation state.

        Returns:
            Dict with progress details including phase, step, and percentage info
        """
        return {
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "completed_phases": self.completed_phases.copy(),
            "progress_percentage": self.progress_percentage,
            "total_phases": self.total_phases,
            "total_steps": self.total_steps,
            "status_message": self.status_message,
            "can_resume": self.can_resume,
            "error_occurred": self.error_occurred,
            "error_details": self.error_details,
            "is_complete": self.current_phase == "complete",
            "has_error": self.current_phase == "error"
        }
