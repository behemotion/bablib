"""Exception handling for schema compatibility and unified project operations."""

from typing import Any, Dict, List, Optional


class BablibError(Exception):
    """Base exception for all Bablib errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize Bablib error."""
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


class SchemaCompatibilityError(BablibError):
    """Raised when project schema is incompatible with current version."""

    def __init__(
        self,
        message: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        current_version: Optional[int] = None,
        project_version: Optional[int] = None,
        missing_fields: Optional[List[str]] = None,
        extra_fields: Optional[List[str]] = None,
        compatibility_issues: Optional[List[str]] = None
    ):
        """Initialize schema compatibility error."""
        details = {}
        if project_id:
            details["project_id"] = project_id
        if project_name:
            details["project_name"] = project_name
        if current_version is not None:
            details["current_version"] = current_version
        if project_version is not None:
            details["project_version"] = project_version
        if missing_fields:
            details["missing_fields"] = missing_fields
        if extra_fields:
            details["extra_fields"] = extra_fields
        if compatibility_issues:
            details["compatibility_issues"] = compatibility_issues

        super().__init__(message, details)

    @classmethod
    def from_compatibility_result(cls, result: Any, project_id: str, project_name: str) -> "SchemaCompatibilityError":
        """Create exception from compatibility check result."""
        message = f"Project '{project_name}' is incompatible with current schema version {result.current_version}"

        return cls(
            message=message,
            project_id=project_id,
            project_name=project_name,
            current_version=result.current_version,
            project_version=result.project_version,
            missing_fields=result.missing_fields,
            extra_fields=result.extra_fields,
            compatibility_issues=result.issues
        )


class MigrationRequiredError(BablibError):
    """Raised when project requires migration before operation can proceed."""

    def __init__(
        self,
        message: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        from_version: Optional[int] = None,
        to_version: Optional[int] = None,
        migration_type: Optional[str] = None,
        can_auto_migrate: bool = False
    ):
        """Initialize migration required error."""
        details = {}
        if project_id:
            details["project_id"] = project_id
        if project_name:
            details["project_name"] = project_name
        if from_version is not None:
            details["from_version"] = from_version
        if to_version is not None:
            details["to_version"] = to_version
        if migration_type:
            details["migration_type"] = migration_type
        details["can_auto_migrate"] = can_auto_migrate

        super().__init__(message, details)


class RecreationRequiredError(BablibError):
    """Raised when project must be recreated due to incompatible schema."""

    def __init__(
        self,
        message: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        current_version: Optional[int] = None,
        project_version: Optional[int] = None,
        recreation_reason: Optional[str] = None,
        suggested_action: Optional[str] = None
    ):
        """Initialize recreation required error."""
        details = {}
        if project_id:
            details["project_id"] = project_id
        if project_name:
            details["project_name"] = project_name
        if current_version is not None:
            details["current_version"] = current_version
        if project_version is not None:
            details["project_version"] = project_version
        if recreation_reason:
            details["recreation_reason"] = recreation_reason
        if suggested_action:
            details["suggested_action"] = suggested_action

        super().__init__(message, details)


class ProjectValidationError(BablibError):
    """Raised when project data fails validation."""

    def __init__(
        self,
        message: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        validation_errors: Optional[List[str]] = None,
        field_errors: Optional[Dict[str, str]] = None
    ):
        """Initialize project validation error."""
        details = {}
        if project_id:
            details["project_id"] = project_id
        if project_name:
            details["project_name"] = project_name
        if validation_errors:
            details["validation_errors"] = validation_errors
        if field_errors:
            details["field_errors"] = field_errors

        super().__init__(message, details)


class MigrationError(BablibError):
    """Raised when database migration fails."""

    def __init__(
        self,
        message: str,
        migration_id: Optional[str] = None,
        from_version: Optional[int] = None,
        to_version: Optional[int] = None,
        migration_step: Optional[str] = None,
        rollback_available: bool = False
    ):
        """Initialize migration error."""
        details = {}
        if migration_id:
            details["migration_id"] = migration_id
        if from_version is not None:
            details["from_version"] = from_version
        if to_version is not None:
            details["to_version"] = to_version
        if migration_step:
            details["migration_step"] = migration_step
        details["rollback_available"] = rollback_available

        super().__init__(message, details)


class ProjectAccessDeniedError(BablibError):
    """Raised when access to project is denied due to compatibility issues."""

    def __init__(
        self,
        message: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        requested_operation: Optional[str] = None,
        compatibility_status: Optional[str] = None,
        suggested_action: Optional[str] = None
    ):
        """Initialize project access denied error."""
        details = {}
        if project_id:
            details["project_id"] = project_id
        if project_name:
            details["project_name"] = project_name
        if requested_operation:
            details["requested_operation"] = requested_operation
        if compatibility_status:
            details["compatibility_status"] = compatibility_status
        if suggested_action:
            details["suggested_action"] = suggested_action

        super().__init__(message, details)


class DatabaseSchemaError(BablibError):
    """Raised when database schema is corrupted or invalid."""

    def __init__(
        self,
        message: str,
        database_path: Optional[str] = None,
        expected_version: Optional[int] = None,
        actual_version: Optional[int] = None,
        corruption_type: Optional[str] = None,
        recovery_possible: bool = False
    ):
        """Initialize database schema error."""
        details = {}
        if database_path:
            details["database_path"] = database_path
        if expected_version is not None:
            details["expected_version"] = expected_version
        if actual_version is not None:
            details["actual_version"] = actual_version
        if corruption_type:
            details["corruption_type"] = corruption_type
        details["recovery_possible"] = recovery_possible

        super().__init__(message, details)


class UnifiedProjectError(BablibError):
    """Raised for unified project model errors."""

    def __init__(
        self,
        message: str,
        project_id: Optional[str] = None,
        operation: Optional[str] = None,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        constraint_violated: Optional[str] = None
    ):
        """Initialize unified project error."""
        details = {}
        if project_id:
            details["project_id"] = project_id
        if operation:
            details["operation"] = operation
        if field_name:
            details["field_name"] = field_name
        if field_value is not None:
            details["field_value"] = field_value
        if constraint_violated:
            details["constraint_violated"] = constraint_violated

        super().__init__(message, details)


# Exception helper functions

def handle_schema_compatibility(compatibility_result: Any, project_id: str, project_name: str) -> None:
    """Handle schema compatibility check results and raise appropriate exceptions."""
    if not compatibility_result.is_compatible:
        if compatibility_result.needs_recreation:
            raise RecreationRequiredError(
                message=f"Project '{project_name}' requires recreation due to incompatible schema",
                project_id=project_id,
                project_name=project_name,
                current_version=compatibility_result.current_version,
                project_version=compatibility_result.project_version,
                recreation_reason="Schema version incompatibility",
                suggested_action=f"Recreate using the new Shelf-Box system: Create a new shelf and box, then refill with content"
            )
        elif compatibility_result.migration_required:
            raise MigrationRequiredError(
                message=f"Project '{project_name}' requires migration from version {compatibility_result.project_version} to {compatibility_result.current_version}",
                project_id=project_id,
                project_name=project_name,
                from_version=compatibility_result.project_version,
                to_version=compatibility_result.current_version,
                migration_type="schema_upgrade",
                can_auto_migrate=compatibility_result.can_be_migrated
            )
        else:
            raise SchemaCompatibilityError.from_compatibility_result(
                compatibility_result, project_id, project_name
            )


def handle_project_access(
    project_name: str,
    compatibility_status: str,
    operation: str,
    project_id: Optional[str] = None
) -> None:
    """Handle project access based on compatibility status."""
    if compatibility_status == "incompatible":
        if operation in ["update", "crawl", "upload", "modify"]:
            raise ProjectAccessDeniedError(
                message=f"Cannot {operation} project '{project_name}' - project is incompatible with current schema",
                project_id=project_id,
                project_name=project_name,
                requested_operation=operation,
                compatibility_status=compatibility_status,
                suggested_action=f"Recreate using the new Shelf-Box system: Create a new shelf and box, then refill with content"
            )
    elif compatibility_status == "migrating":
        raise ProjectAccessDeniedError(
            message=f"Cannot {operation} project '{project_name}' - project is currently being migrated",
            project_id=project_id,
            project_name=project_name,
            requested_operation=operation,
            compatibility_status=compatibility_status,
            suggested_action="Wait for migration to complete or check migration status"
        )


def create_actionable_error_message(error: BablibError) -> str:
    """Create user-friendly error message with actionable instructions."""
    base_message = error.message

    if isinstance(error, RecreationRequiredError):
        project_name = error.details.get("project_name", "the project")
        current_version = error.details.get("current_version", "latest")
        project_version = error.details.get("project_version", "unknown")

        return f"""{base_message}

Schema Version Information:
  Current Schema: v{current_version}
  Project Schema: v{project_version}

To upgrade to the new Shelf-Box system:

1. BACKUP (Recommended):
   Export any important data before proceeding

2. RECREATE using Shelf-Box system:
   bablib shelf create 'my-shelf'
   bablib box create '{project_name}' --type drag  # or rag/bag as appropriate

3. REFILL with content:
   bablib fill '{project_name}' --source <your-source-url-or-path>

Note: This will create a new documentation structure using the modern
Shelf-Box system. You may need to reconfigure your content sources.

For help: bablib --help"""

    elif isinstance(error, MigrationRequiredError):
        project_name = error.details.get("project_name", "the project")
        from_version = error.details.get("from_version", "unknown")
        to_version = error.details.get("to_version", "latest")

        if error.details.get("can_auto_migrate", False):
            return f"""{base_message}

Migration Available: v{from_version} → v{to_version}

To migrate this project:

1. AUTOMATIC migration (if available):
   bablib migrate --project {project_name}

2. Or migrate ALL projects:
   bablib migrate --all

3. Check migration status:
   bablib box list  # to verify new system is working"""
        else:
            return f"""{base_message}

Schema Version: v{from_version} → v{to_version}

Automatic migration is not available. Manual recreation required:

1. BACKUP project settings:
   Export any important data before proceeding

2. RECREATE using Shelf-Box system:
   bablib shelf create 'my-shelf'
   bablib box create '{project_name}' --type drag  # or rag/bag as appropriate

3. REFILL with content:
   bablib fill '{project_name}' --source <your-source-url-or-path>"""

    elif isinstance(error, ProjectAccessDeniedError):
        project_name = error.details.get("project_name", "the project")
        operation = error.details.get("requested_operation", "operation")
        compatibility_status = error.details.get("compatibility_status", "unknown")
        suggested_action = error.details.get("suggested_action", "")

        if compatibility_status == "incompatible":
            return f"""{base_message}

Project Status: {compatibility_status.upper()}
Blocked Operation: {operation}

To enable {operation} operations using the new Shelf-Box system:

1. CHECK current system status:
   bablib health --detailed

2. BACKUP current data (recommended):
   Export any important data before proceeding

3. RECREATE using Shelf-Box system:
   bablib shelf create 'my-shelf'
   bablib box create '{project_name}' --type drag  # or rag/bag as appropriate
   bablib fill '{project_name}' --source <your-source-url-or-path>

After recreation, you can resume {operation} operations."""

        elif suggested_action:
            return f"{base_message}\n\nTo fix this issue:\n{suggested_action}"

    elif isinstance(error, SchemaCompatibilityError):
        project_name = error.details.get("project_name", "the project")
        current_version = error.details.get("current_version", "latest")
        project_version = error.details.get("project_version", "unknown")
        issues = error.details.get("compatibility_issues", [])
        missing_fields = error.details.get("missing_fields", [])
        extra_fields = error.details.get("extra_fields", [])

        message = f"""{base_message}

Schema Analysis:
  Current Schema: v{current_version}
  Project Schema: v{project_version}"""

        if missing_fields:
            message += f"\n  Missing Fields: {', '.join(missing_fields[:5])}"
            if len(missing_fields) > 5:
                message += f" (+{len(missing_fields) - 5} more)"

        if extra_fields:
            message += f"\n  Extra Fields: {', '.join(extra_fields[:5])}"
            if len(extra_fields) > 5:
                message += f" (+{len(extra_fields) - 5} more)"

        if issues:
            message += "\n\nCompatibility Issues:"
            for issue in issues[:3]:  # Show first 3 issues
                message += f"\n  • {issue}"
            if len(issues) > 3:
                message += f"\n  • ... and {len(issues) - 3} more issues"

        message += f"""

To resolve these compatibility issues:

1. GET detailed system status:
   bablib health --detailed

2. BACKUP your data:
   Export any important data before proceeding

3. RECREATE using Shelf-Box system:
   bablib shelf create 'my-shelf'
   bablib box create '{project_name}' --type drag  # or rag/bag as appropriate
   bablib fill '{project_name}' --source <your-source-url-or-path>

4. VERIFY new system is working:
   bablib box list"""

        return message

    return base_message


def format_error_for_api(error: Exception) -> Dict[str, Any]:
    """Format any exception for API response."""
    if isinstance(error, BablibError):
        response = error.to_dict()
        response["suggestion"] = create_actionable_error_message(error)
        return response
    else:
        return {
            "error": error.__class__.__name__,
            "message": str(error),
            "details": {},
            "suggestion": "Check the error message for details and try again"
        }


def format_error_for_cli(error: Exception) -> str:
    """Format any exception for CLI display."""
    if isinstance(error, BablibError):
        return create_actionable_error_message(error)
    else:
        return f"Error: {error}"