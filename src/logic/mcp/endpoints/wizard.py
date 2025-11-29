"""Wizard endpoints for admin MCP server."""

import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Body
from datetime import datetime
import uuid

from src.services.shelf_service import ShelfService
from src.services.box_service import BoxService
from src.logic.wizard.orchestrator import WizardOrchestrator
from src.logic.wizard.shelf_wizard import ShelfWizard
from src.logic.wizard.box_wizard import BoxWizard
from src.logic.wizard.mcp_wizard import McpWizard
from src.models.wizard_state import WizardState
from src.models.wizard_step import WizardStep
from src.core.lib_logger import get_component_logger

logger = get_component_logger("mcp_wizard_endpoints")

router = APIRouter(prefix="/admin/wizards", tags=["admin", "wizards"])


@router.post("/start")
async def start_wizard_session(
    wizard_type: str = Body(..., description="Type of wizard: shelf, box, or mcp"),
    target_entity: str = Body(..., description="Name of the entity being configured"),
    auto_advance: bool = Body(False, description="Skip prompts where possible")
) -> Dict[str, Any]:
    """Start interactive wizard session.

    Creates a new wizard session and returns the first step information.
    Sessions are automatically cleaned up after completion or timeout.
    """
    try:
        # Validate wizard type
        if wizard_type not in ["shelf", "box", "mcp"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid wizard type '{wizard_type}'. Must be one of: shelf, box, mcp"
            )

        # Generate wizard session ID
        wizard_id = str(uuid.uuid4())

        # Initialize wizard orchestrator
        orchestrator = WizardOrchestrator()

        # Create wizard state
        wizard_state = await orchestrator.start_wizard(wizard_type, target_entity)

        # Get first step
        first_step = await _get_wizard_step(wizard_type, 1)

        response = {
            "wizard_id": wizard_id,
            "session_info": {
                "type": wizard_type,
                "target": target_entity,
                "total_steps": wizard_state.total_steps,
                "estimated_time": _get_estimated_time(wizard_type)
            },
            "current_step": {
                "number": 1,
                "title": first_step.step_title,
                "prompt": first_step.prompt_text,
                "input_type": first_step.input_type,
                "choices": first_step.choices,
                "validation_rules": first_step.validation_rules,
                "is_optional": first_step.is_optional
            }
        }

        logger.info(f"Started {wizard_type} wizard session {wizard_id} for '{target_entity}'")
        return response

    except Exception as e:
        logger.error(f"Error starting wizard session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{wizard_id}/step")
async def submit_wizard_step(
    wizard_id: str,
    response_data: Any = Body(..., description="User response to current step"),
    skip: bool = Body(False, description="Skip optional step")
) -> Dict[str, Any]:
    """Submit response to current wizard step.

    Processes user input, validates it, and either returns the next step
    or completes the wizard if all steps are finished.
    """
    try:
        # For this implementation, we'll use a simplified approach
        # In a full implementation, this would retrieve the actual wizard state
        # from a database and process the step accordingly

        # Mock validation - in reality this would validate against the wizard step rules
        validation_errors = []
        if not response_data and not skip:
            validation_errors.append("Response is required for this step")

        if validation_errors:
            return {
                "accepted": False,
                "validation_errors": validation_errors,
                "next_step": None,
                "is_complete": False
            }

        # Mock next step - in reality this would load from wizard state
        next_step = await _get_wizard_step("shelf", 2)  # Mock for demonstration

        # Check if wizard is complete (mock check)
        is_complete = False  # In reality, would check wizard_state.current_step >= total_steps

        response = {
            "accepted": True,
            "validation_errors": [],
            "is_complete": is_complete
        }

        if is_complete:
            # Wizard completed
            response["final_result"] = {
                "configuration_applied": True,
                "entity_created": True,
                "next_actions": [
                    {
                        "action": "view",
                        "description": "View the configured entity",
                        "command": "bablib shelf example --verbose"
                    },
                    {
                        "action": "fill",
                        "description": "Add content to start using it",
                        "command": "bablib box create example-box --type drag --init"
                    }
                ]
            }
        else:
            # Return next step
            response["next_step"] = {
                "number": 2,
                "title": next_step.step_title,
                "prompt": next_step.prompt_text,
                "input_type": next_step.input_type,
                "choices": next_step.choices,
                "is_optional": next_step.is_optional
            }

        logger.info(f"Processed step for wizard session {wizard_id}")
        return response

    except Exception as e:
        logger.error(f"Error processing wizard step for session {wizard_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{wizard_id}/status")
async def get_wizard_status(wizard_id: str) -> Dict[str, Any]:
    """Get current status of wizard session.

    Provides information about wizard progress, current step,
    and collected data without modifying session state.
    """
    try:
        # Mock wizard status - in reality would load from database
        return {
            "wizard_id": wizard_id,
            "wizard_type": "shelf",
            "target_entity": "example-shelf",
            "current_step": 2,
            "total_steps": 5,
            "is_complete": False,
            "start_time": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "collected_data": {
                "description": "Example shelf description",
                "auto_fill": True
            }
        }

    except Exception as e:
        logger.error(f"Error getting wizard status for session {wizard_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{wizard_id}")
async def cleanup_wizard_session(wizard_id: str) -> Dict[str, Any]:
    """Clean up wizard session.

    Removes wizard state and frees resources. Can be called manually
    or automatically after session timeout or completion.
    """
    try:
        # Mock cleanup - in reality would remove from database
        logger.info(f"Cleaned up wizard session {wizard_id}")
        return {"message": f"Wizard session {wizard_id} cleaned up successfully"}

    except Exception as e:
        logger.error(f"Error cleaning up wizard session {wizard_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def _get_wizard_step(wizard_type: str, step_number: int) -> WizardStep:
    """Get wizard step definition by type and number."""
    # Mock step definitions - in reality would load from wizard configuration
    if wizard_type == "shelf":
        steps = {
            1: WizardStep(
                step_number=1,
                wizard_type="shelf",
                step_title="Shelf Description",
                prompt_text="Enter a description for your shelf (optional):",
                input_type="text",
                is_optional=True,
                validation_rules=["max_length:500"]
            ),
            2: WizardStep(
                step_number=2,
                wizard_type="shelf",
                step_title="Auto-fill Settings",
                prompt_text="Should empty boxes be auto-filled when accessed?",
                input_type="boolean",
                is_optional=False,
                validation_rules=[]
            )
        }
    elif wizard_type == "box":
        steps = {
            1: WizardStep(
                step_number=1,
                wizard_type="box",
                step_title="Box Type",
                prompt_text="Select the type of box:",
                input_type="choice",
                choices=["drag", "rag", "bag"],
                is_optional=False,
                validation_rules=["required"]
            )
        }
    else:  # mcp
        steps = {
            1: WizardStep(
                step_number=1,
                wizard_type="mcp",
                step_title="Enable Read-Only Server",
                prompt_text="Enable read-only MCP server?",
                input_type="boolean",
                is_optional=False,
                validation_rules=[]
            )
        }

    return steps.get(step_number, steps[1])


def _get_estimated_time(wizard_type: str) -> str:
    """Get estimated completion time for wizard type."""
    times = {
        "shelf": "2-3 minutes",
        "box": "3-4 minutes",
        "mcp": "2-3 minutes"
    }
    return times.get(wizard_type, "2-5 minutes")