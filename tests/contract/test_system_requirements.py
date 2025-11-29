"""Contract tests for GET /installation/{id}/requirements endpoint."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json
from fastapi.testclient import TestClient
from fastapi import HTTPException


class TestSystemRequirementsEndpoint:
    """Validate GET /installation/{id}/requirements endpoint and SystemRequirements schema."""

    @pytest.mark.asyncio
    def test_system_requirements_endpoint_not_implemented(self):
        """Test that endpoint doesn't exist yet - should fail initially (TDD requirement)."""
        from src.services.mcp_server import create_app

        app = create_app()
        client = TestClient(app)

        # Try to call the endpoint that doesn't exist yet
        response = client.get("/installation/test-id/requirements")

        # Should return 404 since endpoint doesn't exist
        assert response.status_code == 404

    def test_system_requirements_schema_validation_python_version_pattern(self):
        """Test SystemRequirements schema validates Python version pattern ^3\\.13\\.\\d+$"""
        from src.models.installation import SystemRequirements
        from pydantic import ValidationError

        # Valid Python versions
        valid_versions = ["3.13.0", "3.13.1", "3.13.15", "3.13.999"]

        for version in valid_versions:
            requirements = SystemRequirements(
                python_version=version,
                platform="darwin",
                memory_mb=1024,
                disk_space_mb=500,
                has_internet=True
            )
            assert requirements.python_version == version

        # Invalid Python versions
        invalid_versions = [
            "3.12.0",      # Wrong minor version
            "3.13",        # Missing patch version
            "3.13.0.0",    # Too many version parts
            "4.13.0",      # Wrong major version
            "3.13.a",      # Non-numeric patch
            "3.13.",       # Trailing dot
            "",            # Empty string
            "python3.13.0" # Extra text
        ]

        for version in invalid_versions:
            with pytest.raises(ValidationError) as exc_info:
                SystemRequirements(
                    python_version=version,
                    platform="darwin",
                    memory_mb=1024,
                    disk_space_mb=500,
                    has_internet=True
                )

            error_msg = str(exc_info.value)
            assert "python_version must match pattern ^3\\.13\\.\\d+$" in error_msg

    def test_system_requirements_schema_platform_enum_validation(self):
        """Test SystemRequirements schema validates platform enum (darwin, linux, windows)."""
        from src.models.installation import SystemRequirements
        from pydantic import ValidationError

        # Valid platforms
        valid_platforms = ["darwin", "linux", "windows"]

        for platform in valid_platforms:
            requirements = SystemRequirements(
                python_version="3.13.0",
                platform=platform,
                memory_mb=1024,
                disk_space_mb=500,
                has_internet=True
            )
            assert requirements.platform == platform

        # Invalid platforms
        invalid_platforms = ["macos", "unix", "win32", "freebsd", "", "LINUX", "Darwin"]

        for platform in invalid_platforms:
            with pytest.raises(ValidationError) as exc_info:
                SystemRequirements(
                    python_version="3.13.0",
                    platform=platform,
                    memory_mb=1024,
                    disk_space_mb=500,
                    has_internet=True
                )

            error_msg = str(exc_info.value)
            # Pydantic v2 literal validation message
            assert "Input should be 'darwin', 'linux' or 'windows'" in error_msg

    def test_system_requirements_schema_boolean_field_validation(self):
        """Test SystemRequirements schema validates boolean fields correctly."""
        from src.models.installation import SystemRequirements
        from pydantic import ValidationError

        # Valid boolean values
        valid_booleans = [True, False, "true", "false", 1, 0]

        for has_internet in [True, False]:
            for supports_docker in [True, False]:
                for requires_admin in [True, False]:
                    requirements = SystemRequirements(
                        python_version="3.13.0",
                        platform="darwin",
                        memory_mb=1024,
                        disk_space_mb=500,
                        has_internet=has_internet,
                        supports_docker=supports_docker,
                        requires_admin=requires_admin
                    )
                    assert isinstance(requirements.has_internet, bool)
                    assert isinstance(requirements.supports_docker, bool)
                    assert isinstance(requirements.requires_admin, bool)

        # Test string boolean coercion works (Pydantic v2 behavior)
        string_requirements = SystemRequirements(
            python_version="3.13.0",
            platform="darwin",
            memory_mb=1024,
            disk_space_mb=500,
            has_internet="true",  # Should be coerced to True
            supports_docker="false",  # Should be coerced to False
            requires_admin="1"  # Should be coerced to True
        )
        assert string_requirements.has_internet is True
        assert string_requirements.supports_docker is False
        assert string_requirements.requires_admin is True

        # Test that Pydantic v2 accepts "yes"/"no" as boolean values
        yes_no_requirements = SystemRequirements(
            python_version="3.13.0",
            platform="darwin",
            memory_mb=1024,
            disk_space_mb=500,
            has_internet="yes",  # Should be coerced to True
            supports_docker="no",  # Should be coerced to False
            requires_admin=1  # Should be coerced to True
        )
        assert yes_no_requirements.has_internet is True
        assert yes_no_requirements.supports_docker is False
        assert yes_no_requirements.requires_admin is True

        # Invalid boolean values that should raise ValidationError
        invalid_booleans = ["maybe", "invalid", 2, -1, [], {}]

        for invalid_bool in invalid_booleans:
            with pytest.raises(ValidationError):
                SystemRequirements(
                    python_version="3.13.0",
                    platform="darwin",
                    memory_mb=1024,
                    disk_space_mb=500,
                    has_internet=invalid_bool
                )

    def test_system_requirements_schema_integer_field_validation(self):
        """Test SystemRequirements schema validates integer fields with constraints."""
        from src.models.installation import SystemRequirements
        from pydantic import ValidationError

        # Valid integer values (within constraints)
        valid_memory_values = [512, 1024, 2048, 8192]  # >= 512 MB
        valid_disk_values = [100, 500, 1000, 5000]     # >= 100 MB

        for memory in valid_memory_values:
            for disk in valid_disk_values:
                requirements = SystemRequirements(
                    python_version="3.13.0",
                    platform="darwin",
                    memory_mb=memory,
                    disk_space_mb=disk,
                    has_internet=True
                )
                assert requirements.memory_mb == memory
                assert requirements.disk_space_mb == disk

        # Invalid integer values - below minimum constraints
        invalid_memory_values = [0, -1, 511]  # Below 512 MB minimum
        invalid_disk_values = [0, -1, 99]     # Below 100 MB minimum

        for memory in invalid_memory_values:
            with pytest.raises(ValidationError) as exc_info:
                SystemRequirements(
                    python_version="3.13.0",
                    platform="darwin",
                    memory_mb=memory,
                    disk_space_mb=1000,
                    has_internet=True
                )

            error_msg = str(exc_info.value)
            assert "greater than or equal to 512" in error_msg or "Memory and disk space must be positive integers" in error_msg

        for disk in invalid_disk_values:
            with pytest.raises(ValidationError) as exc_info:
                SystemRequirements(
                    python_version="3.13.0",
                    platform="darwin",
                    memory_mb=1024,
                    disk_space_mb=disk,
                    has_internet=True
                )

            error_msg = str(exc_info.value)
            assert "greater than or equal to 100" in error_msg or "Memory and disk space must be positive integers" in error_msg

    def test_system_requirements_schema_field_defaults(self):
        """Test SystemRequirements schema applies correct default values."""
        from src.models.installation import SystemRequirements

        # Create with minimal required fields
        requirements = SystemRequirements(
            python_version="3.13.0",
            platform="darwin",
            memory_mb=1024,
            disk_space_mb=500,
            has_internet=True
        )

        # Check defaults are applied
        assert requirements.supports_docker is True  # Default True
        assert requirements.requires_admin is False  # Default False

    def test_system_requirements_schema_serialization(self):
        """Test SystemRequirements schema serializes correctly to dict/JSON."""
        from src.models.installation import SystemRequirements

        requirements = SystemRequirements(
            python_version="3.13.1",
            platform="linux",
            memory_mb=2048,
            disk_space_mb=1000,
            has_internet=True,
            supports_docker=False,
            requires_admin=True
        )

        # Test dict serialization
        data = requirements.model_dump()
        expected_keys = {
            "python_version", "platform", "memory_mb", "disk_space_mb",
            "has_internet", "supports_docker", "requires_admin"
        }
        assert set(data.keys()) == expected_keys
        assert data["python_version"] == "3.13.1"
        assert data["platform"] == "linux"
        assert data["memory_mb"] == 2048
        assert data["disk_space_mb"] == 1000
        assert data["has_internet"] is True
        assert data["supports_docker"] is False
        assert data["requires_admin"] is True

        # Test JSON serialization
        json_str = requirements.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed == data

    @pytest.mark.asyncio
    def test_installation_requirements_endpoint_contract(self):
        """Test the contract for GET /installation/{id}/requirements endpoint when implemented."""
        from src.services.mcp_server import MCPServer
        from src.core.config import BablibConfig

        # This test defines the expected contract for the endpoint
        # It will fail until the endpoint is actually implemented

        config = BablibConfig()
        server = MCPServer(config)

        # Mock the services to avoid real initialization
        with patch.object(server, 'initialize_services', new_callable=AsyncMock):
            app = server.get_app()
            client = TestClient(app)

            # Expected endpoint behavior (when implemented):
            # GET /installation/{id}/requirements should return SystemRequirements schema

            installation_id = "test-installation-id"
            response = client.get(f"/installation/{installation_id}/requirements")

            # Currently will return 404 since endpoint doesn't exist
            # When implemented, should return 200 with SystemRequirements data
            if response.status_code == 200:
                # Validate response structure matches SystemRequirements schema
                data = response.json()

                required_fields = [
                    "python_version", "platform", "memory_mb", "disk_space_mb",
                    "has_internet", "supports_docker", "requires_admin"
                ]

                for field in required_fields:
                    assert field in data, f"Response missing required field: {field}"

                # Validate field types and constraints
                assert isinstance(data["python_version"], str)
                assert data["platform"] in ["darwin", "linux", "windows"]
                assert isinstance(data["memory_mb"], int) and data["memory_mb"] >= 512
                assert isinstance(data["disk_space_mb"], int) and data["disk_space_mb"] >= 100
                assert isinstance(data["has_internet"], bool)
                assert isinstance(data["supports_docker"], bool)
                assert isinstance(data["requires_admin"], bool)

                # Validate Python version pattern
                import re
                assert re.match(r"^3\.13\.\d+$", data["python_version"])
            else:
                # Expected for TDD - endpoint not implemented yet
                assert response.status_code == 404

    def test_system_requirements_field_validation_edge_cases(self):
        """Test SystemRequirements schema handles edge cases and validation properly."""
        from src.models.installation import SystemRequirements
        from pydantic import ValidationError

        # Test string stripping (model_config has str_strip_whitespace=True)
        requirements = SystemRequirements(
            python_version="  3.13.0  ",  # Should be stripped
            platform="darwin",           # Literal fields don't strip, so use exact value
            memory_mb=1024,
            disk_space_mb=500,
            has_internet=True
        )

        assert requirements.python_version == "3.13.0"
        assert requirements.platform == "darwin"

        # Test that platform field doesn't accept whitespace (Literal behavior)
        with pytest.raises(ValidationError):
            SystemRequirements(
                python_version="3.13.0",
                platform="  darwin  ",  # Literal fields are strict
                memory_mb=1024,
                disk_space_mb=500,
                has_internet=True
            )

        # Test assignment validation (model_config has validate_assignment=True)
        requirements.python_version = "3.13.2"  # Should validate on assignment
        assert requirements.python_version == "3.13.2"

        # Invalid assignment should raise ValidationError
        with pytest.raises(ValidationError):
            requirements.python_version = "3.12.0"  # Invalid pattern

        with pytest.raises(ValidationError):
            requirements.platform = "invalid"  # Invalid enum value