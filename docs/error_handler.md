# Error Handler Service

The `ErrorHandlerService` provides comprehensive error handling and rollback capabilities for Bablib installations. It includes error categorization, user-friendly messages, rollback functionality, and integration with the installation wizard.

## Features

- **Custom Exception Hierarchy**: Specific exceptions for different error categories
- **Error Categorization**: Automatic categorization of errors into meaningful groups
- **Rollback Logic**: Comprehensive rollback capabilities for failed installations
- **Service Setup Recovery**: Recovery options for service setup failures
- **User-Friendly Messages**: Clear, actionable error messages for users
- **Partial Installation Cleanup**: Safe cleanup of incomplete installations
- **Timeout/Cancellation Handling**: Graceful handling of interruptions
- **Structured Logging**: Detailed error logging for debugging
- **Wizard Integration**: Seamless integration with InstallationWizardService

## Usage

### Basic Error Handling

```python
from services.error_handler import ErrorHandlerService

async def handle_installation_error():
    error_handler = ErrorHandlerService()

    # Set up progress callback
    def progress_callback(data):
        print(f"Progress: {data['type']} - {data.get('message', '')}")

    error_handler.set_progress_callback(progress_callback)

    try:
        # Your installation code here
        pass
    except Exception as error:
        context = {
            "phase": "service_setup",
            "step": "docker_detection",
            "component": "service_detector",
            "operation": "check_docker_status"
        }

        error_context = await error_handler.handle_error(error, context)

        print(f"Error: {error_context.user_message}")
        print(f"Suggested actions: {[a.value for a in error_context.suggested_actions]}")
```

### Snapshot Creation and Rollback

```python
async def installation_with_snapshots():
    error_handler = ErrorHandlerService()

    # Create snapshot before critical operation
    snapshot_id = await error_handler.create_snapshot(
        "service_setup",
        "configure_docker",
        "Before Docker configuration"
    )

    try:
        # Perform critical installation step
        configure_docker_service()
    except Exception as error:
        # Handle error
        await error_handler.handle_error(error)

        # Rollback to previous state
        success = await error_handler.rollback_to_snapshot(
            snapshot_id,
            partial_ok=True  # Allow partial rollback
        )

        if success:
            print("Successfully rolled back installation")
        else:
            print("Rollback failed, manual cleanup required")
```

### Integration with Installation Wizard

```python
async def installation_with_error_handling():
    error_handler = ErrorHandlerService()
    wizard = InstallationWizardService()

    # Add cleanup callback
    def cleanup_temp_files():
        # Clean up temporary files
        pass

    error_handler.add_cleanup_callback(cleanup_temp_files)

    try:
        # Start installation
        request = InstallationRequest(
            install_method="uvx",
            version="1.0.0"
        )

        response = await wizard.start_installation(request)

    except Exception as error:
        # Handle with comprehensive error handling
        error_context = await error_handler.handle_error(error, {}, wizard)

        # Clean up partial installation
        await error_handler.cleanup_partial_installation(wizard)

        raise
```

### Handling Cancellations and Timeouts

```python
async def handle_cancellation():
    error_handler = ErrorHandlerService()
    wizard = InstallationWizardService()

    # Handle user cancellation
    await error_handler.handle_cancellation(
        "User cancelled during service setup",
        wizard
    )

async def handle_timeout():
    error_handler = ErrorHandlerService()
    wizard = InstallationWizardService()

    # Handle operation timeout
    error_context = await error_handler.handle_timeout(
        "service_detection",
        30.0,  # timeout in seconds
        wizard
    )
```

## Error Categories

The service automatically categorizes errors into these categories:

- **SYSTEM_REQUIREMENTS**: Python version, UV, memory, disk space issues
- **NETWORK_CONNECTIVITY**: Connection failures, timeouts
- **PERMISSION_DENIED**: File access, directory permissions
- **SERVICE_UNAVAILABLE**: Docker, Ollama, Qdrant service issues
- **CONFIGURATION**: Config file format, validation errors
- **DISK_SPACE**: Insufficient storage space
- **DEPENDENCY_MISSING**: Missing packages or dependencies
- **TIMEOUT**: Operation timeouts
- **CANCELLATION**: User or system cancellations
- **DATA_CORRUPTION**: Corrupted files or data
- **VERSION_CONFLICT**: Version compatibility issues
- **UNKNOWN**: Uncategorized errors

## Error Severity Levels

- **CRITICAL**: Installation cannot proceed (system requirements, permissions, disk space)
- **HIGH**: Major functionality affected (network issues in critical phases, timeouts)
- **MEDIUM**: Some functionality affected (service unavailable, configuration issues)
- **LOW**: Minor issues
- **INFO**: Informational warnings

## Recovery Actions

The service suggests appropriate recovery actions:

- **RETRY**: Try the operation again
- **ROLLBACK**: Revert to previous state
- **SKIP**: Skip the failing operation if possible
- **MANUAL**: Manual intervention required
- **ABORT**: Stop the installation
- **CLEANUP**: Clean up partial installation

## Custom Exception Classes

Use specific exception types for better categorization:

```python
from services.error_handler import (
    SystemRequirementsError,
    NetworkConnectivityError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ConfigurationError,
    DiskSpaceError,
    DependencyMissingError,
    InstallationTimeoutError,
    InstallationCancellationError,
    DataCorruptionError,
    VersionConflictError
)

# Example usage
if python_version < "3.13":
    raise SystemRequirementsError("Python 3.13+ required for Bablib installation")

if not can_connect_to_service():
    raise ServiceUnavailableError("Docker service is not running")
```

## Configuration

The error handler uses the same configuration as other Bablib services through `ConfigService`. It automatically:

- Creates snapshot directories in the cache directory
- Logs errors to structured log files
- Respects XDG Base Directory specification
- Integrates with the existing logging system

## Best Practices

1. **Create snapshots before critical operations**
2. **Use specific exception types when possible**
3. **Provide meaningful context information**
4. **Set up progress callbacks for user feedback**
5. **Add cleanup callbacks for temporary resources**
6. **Use partial rollback for better user experience**
7. **Check error history for debugging patterns**

## Testing

The service includes comprehensive unit tests covering:

- Error categorization logic
- Severity determination
- Recovery action suggestions
- User-friendly message generation
- Snapshot creation and rollback
- Integration with installation wizard
- Timeout and cancellation handling
- Cleanup operations
- Error history tracking

Run tests with:
```bash
pytest tests/unit/test_error_handler.py -v
```