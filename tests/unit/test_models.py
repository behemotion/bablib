"""Comprehensive unit tests for all installation models validation."""

import pytest
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch
from uuid import uuid4
from pydantic import ValidationError

from src.models.installation import (
    InstallationContext,
    ServiceStatus,
    SetupWizardState,
    PackageMetadata,
    InstallationRequest,
    InstallationResponse,
    SystemRequirements,
    CriticalDecisionPoint
)


class TestInstallationContext:
    """Test cases for InstallationContext model validation and behavior."""

    def test_valid_installation_context_creation(self):
        """Test creating a valid InstallationContext instance."""
        context = InstallationContext(
            install_method="uvx",
            install_date=datetime.now(),
            version="1.0.0",
            python_version="3.13.1",
            uv_version="0.4.0",
            install_path=Path("/usr/local/bin/bablib"),
            is_global=True,
            user_data_dir=Path.home() / ".local" / "share" / "bablib",
            config_dir=Path.home() / ".config" / "bablib",
            cache_dir=Path.home() / ".cache" / "bablib"
        )

        assert context.install_method == "uvx"
        assert context.version == "1.0.0"
        assert context.python_version == "3.13.1"
        assert context.is_global is True
        assert isinstance(context.install_path, Path)

    def test_install_method_validation(self):
        """Test that install_method must be one of allowed values."""
        valid_methods = ["uvx", "manual", "development"]

        for method in valid_methods:
            context = InstallationContext(
                install_method=method,
                install_date=datetime.now(),
                version="1.0.0",
                python_version="3.13.1",
                install_path=Path("/usr/local/bin/bablib"),
                is_global=True,
                user_data_dir=Path.home() / ".local" / "share" / "bablib",
                config_dir=Path.home() / ".config" / "bablib",
                cache_dir=Path.home() / ".cache" / "bablib"
            )
            assert context.install_method == method

        # Test invalid method
        with pytest.raises(ValidationError) as exc_info:
            InstallationContext(
                install_method="invalid",
                install_date=datetime.now(),
                version="1.0.0",
                python_version="3.13.1",
                install_path=Path("/usr/local/bin/bablib"),
                is_global=True,
                user_data_dir=Path.home() / ".local" / "share" / "bablib",
                config_dir=Path.home() / ".config" / "bablib",
                cache_dir=Path.home() / ".cache" / "bablib"
            )
        assert "install_method must be one of" in str(exc_info.value)

    def test_version_format_validation(self):
        """Test that version must follow semantic versioning."""
        valid_versions = ["1.0.0", "2.1.3", "0.1.0", "10.20.30"]

        for version in valid_versions:
            context = InstallationContext(
                install_method="uvx",
                install_date=datetime.now(),
                version=version,
                python_version="3.13.1",
                install_path=Path("/usr/local/bin/bablib"),
                is_global=True,
                user_data_dir=Path.home() / ".local" / "share" / "bablib",
                config_dir=Path.home() / ".config" / "bablib",
                cache_dir=Path.home() / ".cache" / "bablib"
            )
            assert context.version == version

        # Test invalid version formats
        invalid_versions = ["1.0", "v1.0.0", "1.0.0-alpha", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                InstallationContext(
                    install_method="uvx",
                    install_date=datetime.now(),
                    version=version,
                    python_version="3.13.1",
                    install_path=Path("/usr/local/bin/bablib"),
                    is_global=True,
                    user_data_dir=Path.home() / ".local" / "share" / "bablib",
                    config_dir=Path.home() / ".config" / "bablib",
                    cache_dir=Path.home() / ".cache" / "bablib"
                )

    def test_python_version_validation(self):
        """Test that python_version must be 3.13.x."""
        valid_versions = ["3.13.0", "3.13.1", "3.13.10"]

        for py_version in valid_versions:
            context = InstallationContext(
                install_method="uvx",
                install_date=datetime.now(),
                version="1.0.0",
                python_version=py_version,
                install_path=Path("/usr/local/bin/bablib"),
                is_global=True,
                user_data_dir=Path.home() / ".local" / "share" / "bablib",
                config_dir=Path.home() / ".config" / "bablib",
                cache_dir=Path.home() / ".cache" / "bablib"
            )
            assert context.python_version == py_version

        # Test invalid Python versions
        invalid_versions = ["3.12.0", "3.11.5", "3.14.0", "python3.13"]
        for py_version in invalid_versions:
            with pytest.raises(ValidationError):
                InstallationContext(
                    install_method="uvx",
                    install_date=datetime.now(),
                    version="1.0.0",
                    python_version=py_version,
                    install_path=Path("/usr/local/bin/bablib"),
                    is_global=True,
                    user_data_dir=Path.home() / ".local" / "share" / "bablib",
                    config_dir=Path.home() / ".config" / "bablib",
                    cache_dir=Path.home() / ".cache" / "bablib"
                )

    def test_path_validation(self):
        """Test that paths must be absolute."""
        # Test with absolute paths (valid)
        context = InstallationContext(
            install_method="uvx",
            install_date=datetime.now(),
            version="1.0.0",
            python_version="3.13.1",
            install_path=Path("/usr/local/bin/bablib").absolute(),
            is_global=True,
            user_data_dir=Path.home().absolute() / "data",
            config_dir=Path.home().absolute() / "config",
            cache_dir=Path.home().absolute() / "cache"
        )

        assert context.install_path.is_absolute()
        assert context.user_data_dir.is_absolute()
        assert context.config_dir.is_absolute()
        assert context.cache_dir.is_absolute()

    def test_json_serialization(self):
        """Test that InstallationContext can be serialized to/from JSON."""
        original = InstallationContext(
            install_method="uvx",
            install_date=datetime(2025, 1, 25, 10, 30, 0),
            version="1.0.0",
            python_version="3.13.1",
            uv_version="0.4.0",
            install_path=Path("/usr/local/bin/bablib"),
            is_global=True,
            user_data_dir=Path.home() / ".local" / "share" / "bablib",
            config_dir=Path.home() / ".config" / "bablib",
            cache_dir=Path.home() / ".cache" / "bablib"
        )

        # Serialize to JSON
        json_data = original.model_dump(mode='json')
        assert isinstance(json_data, dict)
        assert json_data["install_method"] == "uvx"
        assert json_data["version"] == "1.0.0"

        # Deserialize from JSON
        restored = InstallationContext.model_validate(json_data)
        assert restored.install_method == original.install_method
        assert restored.version == original.version
        assert restored.python_version == original.python_version

    def test_optional_uv_version(self):
        """Test that uv_version can be None."""
        context = InstallationContext(
            install_method="manual",
            install_date=datetime.now(),
            version="1.0.0",
            python_version="3.13.1",
            uv_version=None,
            install_path=Path("/usr/local/bin/bablib"),
            is_global=True,
            user_data_dir=Path.home() / ".local" / "share" / "bablib",
            config_dir=Path.home() / ".config" / "bablib",
            cache_dir=Path.home() / ".cache" / "bablib"
        )

        assert context.uv_version is None


class TestServiceStatus:
    """Test cases for ServiceStatus model validation and behavior."""

    def test_valid_service_status_creation(self):
        """Test creating a valid ServiceStatus instance."""
        status = ServiceStatus(
            name="docker",
            available=True,
            version="24.0.0",
            endpoint="unix:///var/run/docker.sock",
            last_checked=datetime.now(),
            error_message=None,
            setup_completed=True
        )

        assert status.name == "docker"
        assert status.available is True
        assert status.version == "24.0.0"
        assert status.setup_completed is True

    def test_service_name_validation(self):
        """Test that service name must be one of supported values."""
        supported_services = {"docker", "ollama", "qdrant"}

        for service in supported_services:
            status = ServiceStatus(
                name=service,
                available=True,
                last_checked=datetime.now(),
                setup_completed=True
            )
            assert status.name == service

        # Test invalid service name
        with pytest.raises(ValidationError) as exc_info:
            ServiceStatus(
                name="redis",  # Not in supported list
                available=True,
                last_checked=datetime.now(),
                setup_completed=True
            )
        assert "name must be one of" in str(exc_info.value)

    def test_unavailable_service_with_error(self):
        """Test service status when unavailable with error message."""
        status = ServiceStatus(
            name="ollama",
            available=False,
            version=None,
            endpoint=None,
            last_checked=datetime.now(),
            error_message="Connection refused",
            setup_completed=False
        )

        assert status.available is False
        assert status.error_message == "Connection refused"
        assert status.setup_completed is False

    def test_optional_fields(self):
        """Test that version, endpoint, and error_message are optional."""
        status = ServiceStatus(
            name="qdrant",
            available=True,
            last_checked=datetime.now(),
            setup_completed=True
        )

        assert status.version is None
        assert status.endpoint is None
        assert status.error_message is None


class TestSetupWizardState:
    """Test cases for SetupWizardState model validation and behavior."""

    def test_valid_setup_wizard_state_creation(self):
        """Test creating a valid SetupWizardState instance."""
        state = SetupWizardState(
            current_step="service_check",
            completed_steps=["welcome", "python_check"],
            services_to_install=["docker", "ollama"],
            user_preferences={"dark_mode": True},
            skip_services=["qdrant"],
            setup_start_time=datetime.now()
        )

        assert state.current_step == "service_check"
        assert "welcome" in state.completed_steps
        assert "docker" in state.services_to_install
        assert "qdrant" in state.skip_services

    def test_current_step_validation(self):
        """Test that current_step must be one of valid steps."""
        valid_steps = {
            "welcome", "python_check", "service_check", "service_install",
            "config_setup", "complete"
        }

        for step in valid_steps:
            state = SetupWizardState(
                current_step=step,
                setup_start_time=datetime.now()
            )
            assert state.current_step == step

        # Test invalid step
        with pytest.raises(ValidationError):
            SetupWizardState(
                current_step="invalid_step",
                setup_start_time=datetime.now()
            )

    def test_service_list_validation(self):
        """Test validation of services_to_install and skip_services."""
        valid_services = ["docker", "ollama", "qdrant"]

        state = SetupWizardState(
            current_step="welcome",
            services_to_install=valid_services,
            skip_services=[],
            setup_start_time=datetime.now()
        )
        assert set(state.services_to_install) == set(valid_services)

        # Test invalid service in list
        with pytest.raises(ValidationError):
            SetupWizardState(
                current_step="welcome",
                services_to_install=["docker", "invalid_service"],
                setup_start_time=datetime.now()
            )

    def test_completed_steps_validation(self):
        """Test validation of completed steps order."""
        valid_sequences = [
            ["welcome"],
            ["welcome", "python_check"],
            ["welcome", "python_check", "service_check"],
        ]

        for steps in valid_sequences:
            state = SetupWizardState(
                current_step=steps[-1] if steps else "welcome",
                completed_steps=steps,
                setup_start_time=datetime.now()
            )
            assert state.completed_steps == steps

    def test_no_overlap_validation(self):
        """Test that services can't be in both install and skip lists."""
        # This should work - no overlap
        state = SetupWizardState(
            current_step="welcome",
            services_to_install=["docker"],
            skip_services=["ollama"],
            setup_start_time=datetime.now()
        )
        assert "docker" in state.services_to_install
        assert "ollama" in state.skip_services

        # This should fail - overlap between lists
        with pytest.raises(ValidationError) as exc_info:
            SetupWizardState(
                current_step="welcome",
                services_to_install=["docker", "ollama"],
                skip_services=["ollama", "qdrant"],
                setup_start_time=datetime.now()
            )
        assert "cannot be in both install and skip lists" in str(exc_info.value)

    def test_default_values(self):
        """Test default values for optional fields."""
        state = SetupWizardState(
            current_step="welcome",
            setup_start_time=datetime.now()
        )

        assert state.completed_steps == []
        assert state.services_to_install == []
        assert state.skip_services == []
        assert state.user_preferences == {}


class TestPackageMetadata:
    """Test cases for PackageMetadata model validation and behavior."""

    def test_valid_package_metadata_creation(self):
        """Test creating a valid PackageMetadata instance."""
        metadata = PackageMetadata(
            name="bablib",
            version="1.0.0",
            description="Documentation crawler and search tool",
            homepage="https://github.com/behemotion/doc-bro",
            repository_url="https://github.com/behemotion/doc-bro.git",
            entry_points={"console_scripts": "bablib = src.cli.main:main"},
            dependencies=["pydantic>=2.0", "click>=8.0"],
            python_requires=">=3.13",
            install_source="git+https://github.com/behemotion/doc-bro"
        )

        assert metadata.name == "bablib"
        assert metadata.version == "1.0.0"
        assert metadata.homepage.startswith("https://")

    def test_package_name_validation(self):
        """Test that package name must be 'bablib'."""
        # Valid name
        metadata = PackageMetadata(
            name="bablib",
            version="1.0.0",
            description="Test",
            homepage="https://example.com",
            repository_url="https://example.com/repo",
            install_source="test"
        )
        assert metadata.name == "bablib"

        # Invalid name
        with pytest.raises(ValidationError) as exc_info:
            PackageMetadata(
                name="other-package",
                version="1.0.0",
                description="Test",
                homepage="https://example.com",
                repository_url="https://example.com/repo",
                install_source="test"
            )
        assert "name must be 'bablib'" in str(exc_info.value)

    def test_version_validation(self):
        """Test that version must follow semantic versioning."""
        valid_versions = ["1.0.0", "2.1.3", "0.1.0", "10.20.30"]

        for version in valid_versions:
            metadata = PackageMetadata(
                version=version,
                description="Test",
                homepage="https://example.com",
                repository_url="https://example.com/repo",
                install_source="test"
            )
            assert metadata.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0-alpha", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                PackageMetadata(
                    version=version,
                    description="Test",
                    homepage="https://example.com",
                    repository_url="https://example.com/repo",
                    install_source="test"
                )

    def test_url_validation(self):
        """Test that homepage and repository URLs must be HTTP/HTTPS."""
        valid_urls = ["http://example.com", "https://example.com", "https://github.com/user/repo"]

        for url in valid_urls:
            metadata = PackageMetadata(
                version="1.0.0",
                description="Test",
                homepage=url,
                repository_url=url,
                install_source="test"
            )
            assert metadata.homepage == url
            assert metadata.repository_url == url

        # Invalid URLs
        invalid_urls = ["ftp://example.com", "example.com", "ssh://git@github.com"]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                PackageMetadata(
                    version="1.0.0",
                    description="Test",
                    homepage=url,
                    repository_url="https://example.com",
                    install_source="test"
                )

    def test_default_values(self):
        """Test default values for optional fields."""
        metadata = PackageMetadata(
            version="1.0.0",
            description="Test",
            homepage="https://example.com",
            repository_url="https://example.com/repo",
            install_source="test"
        )

        assert metadata.name == "bablib"  # default
        assert metadata.entry_points == {}
        assert metadata.dependencies == []
        assert metadata.python_requires == ">=3.13"


class TestInstallationRequest:
    """Test cases for InstallationRequest model validation and behavior."""

    def test_valid_installation_request_creation(self):
        """Test creating a valid InstallationRequest instance."""
        request = InstallationRequest(
            install_method="uvx",
            version="1.0.0",
            user_preferences={"install_services": True},
            force_reinstall=False
        )

        assert request.install_method == "uvx"
        assert request.version == "1.0.0"
        assert request.force_reinstall is False

    def test_install_method_validation(self):
        """Test that install_method must be one of valid literals."""
        valid_methods = ["uvx", "uv-tool", "development"]

        for method in valid_methods:
            request = InstallationRequest(
                install_method=method,
                version="1.0.0"
            )
            assert request.install_method == method

        # Invalid method should be caught by Pydantic literal validation
        with pytest.raises(ValidationError):
            InstallationRequest(
                install_method="invalid",
                version="1.0.0"
            )

    def test_version_format_validation(self):
        """Test that version must follow semantic versioning."""
        valid_versions = ["1.0.0", "2.1.3", "0.1.0"]

        for version in valid_versions:
            request = InstallationRequest(
                install_method="uvx",
                version=version
            )
            assert request.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0-beta"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                InstallationRequest(
                    install_method="uvx",
                    version=version
                )

    def test_optional_fields(self):
        """Test optional fields have correct defaults."""
        request = InstallationRequest(
            install_method="uvx",
            version="1.0.0"
        )

        assert request.user_preferences is None
        assert request.force_reinstall is False


class TestInstallationResponse:
    """Test cases for InstallationResponse model validation and behavior."""

    def test_valid_installation_response_creation(self):
        """Test creating a valid InstallationResponse instance."""
        installation_id = str(uuid4())
        response = InstallationResponse(
            installation_id=installation_id,
            status="started",
            message="Installation started successfully",
            next_steps=["Check status", "Run setup"]
        )

        assert response.installation_id == installation_id
        assert response.status == "started"
        assert len(response.next_steps) == 2

    def test_installation_id_validation(self):
        """Test that installation_id must be a valid UUID."""
        valid_id = str(uuid4())
        response = InstallationResponse(
            installation_id=valid_id,
            status="started",
            message="Test message"
        )
        assert response.installation_id == valid_id

        # Invalid UUID format
        with pytest.raises(ValidationError):
            InstallationResponse(
                installation_id="not-a-uuid",
                status="started",
                message="Test message"
            )

    def test_status_validation(self):
        """Test that status must be one of valid literals."""
        valid_statuses = ["started", "in_progress", "completed", "failed"]

        for status in valid_statuses:
            response = InstallationResponse(
                installation_id=str(uuid4()),
                status=status,
                message="Test message"
            )
            assert response.status == status

        # Invalid status
        with pytest.raises(ValidationError):
            InstallationResponse(
                installation_id=str(uuid4()),
                status="invalid_status",
                message="Test message"
            )

    def test_optional_next_steps(self):
        """Test that next_steps is optional."""
        response = InstallationResponse(
            installation_id=str(uuid4()),
            status="completed",
            message="Installation completed"
        )
        assert response.next_steps is None


class TestSystemRequirements:
    """Test cases for SystemRequirements model validation and behavior."""

    def test_valid_system_requirements_creation(self):
        """Test creating a valid SystemRequirements instance."""
        requirements = SystemRequirements(
            python_version="3.13.0",
            platform="darwin",
            memory_mb=1024,
            disk_space_mb=500,
            has_internet=True,
            supports_docker=True,
            requires_admin=False
        )

        assert requirements.python_version == "3.13.0"
        assert requirements.platform == "darwin"
        assert requirements.memory_mb == 1024
        assert requirements.has_internet is True

    def test_python_version_pattern_validation(self):
        """Test that python_version must match 3.13.x pattern."""
        valid_versions = ["3.13.0", "3.13.1", "3.13.10", "3.13.999"]

        for version in valid_versions:
            requirements = SystemRequirements(
                python_version=version,
                platform="linux",
                memory_mb=512,
                disk_space_mb=100,
                has_internet=True
            )
            assert requirements.python_version == version

        # Invalid versions
        invalid_versions = ["3.12.0", "3.14.0", "3.13", "3.13.0.1", "python3.13.0"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                SystemRequirements(
                    python_version=version,
                    platform="linux",
                    memory_mb=512,
                    disk_space_mb=100,
                    has_internet=True
                )

    def test_platform_validation(self):
        """Test that platform must be one of supported values."""
        valid_platforms = ["darwin", "linux", "windows"]

        for platform in valid_platforms:
            requirements = SystemRequirements(
                python_version="3.13.0",
                platform=platform,
                memory_mb=512,
                disk_space_mb=100,
                has_internet=True
            )
            assert requirements.platform == platform

        # Invalid platform
        with pytest.raises(ValidationError):
            SystemRequirements(
                python_version="3.13.0",
                platform="freebsd",
                memory_mb=512,
                disk_space_mb=100,
                has_internet=True
            )

    def test_memory_and_disk_validation(self):
        """Test validation of memory_mb and disk_space_mb fields."""
        # Valid values
        requirements = SystemRequirements(
            python_version="3.13.0",
            platform="linux",
            memory_mb=512,  # minimum value
            disk_space_mb=100,  # minimum value
            has_internet=True
        )
        assert requirements.memory_mb == 512
        assert requirements.disk_space_mb == 100

        # Test minimum constraints
        with pytest.raises(ValidationError):
            SystemRequirements(
                python_version="3.13.0",
                platform="linux",
                memory_mb=400,  # below minimum
                disk_space_mb=100,
                has_internet=True
            )

        with pytest.raises(ValidationError):
            SystemRequirements(
                python_version="3.13.0",
                platform="linux",
                memory_mb=512,
                disk_space_mb=50,  # below minimum
                has_internet=True
            )

    def test_default_values(self):
        """Test default values for optional fields."""
        requirements = SystemRequirements(
            python_version="3.13.0",
            platform="linux",
            memory_mb=512,
            disk_space_mb=100,
            has_internet=True
        )

        assert requirements.supports_docker is True  # default
        assert requirements.requires_admin is False  # default


class TestCriticalDecisionPoint:
    """Test cases for CriticalDecisionPoint model validation and behavior."""

    def test_valid_critical_decision_point_creation(self):
        """Test creating a valid CriticalDecisionPoint instance."""
        decision = CriticalDecisionPoint(
            decision_id="install_location_001",
            decision_type="install_location",
            title="Choose Installation Location",
            description="Select where to install Bablib",
            options=[
                {"id": "global", "label": "Global installation"},
                {"id": "local", "label": "Local installation"}
            ],
            default_option="global",
            validation_pattern=r"^(global|local)$"
        )

        assert decision.decision_id == "install_location_001"
        assert decision.decision_type == "install_location"
        assert len(decision.options) == 2
        assert decision.resolved is False

    def test_decision_id_validation(self):
        """Test that decision_id follows correct format."""
        valid_ids = ["install_001", "service-port", "data_dir_choice", "decision123"]

        for decision_id in valid_ids:
            decision = CriticalDecisionPoint(
                decision_id=decision_id,
                decision_type="install_location",
                title="Test Decision",
                description="Test description",
                options=[{"id": "option1", "label": "Option 1"}]
            )
            assert decision.decision_id == decision_id

        # Invalid decision IDs
        invalid_ids = ["decision with spaces", "decision@#$", ""]
        for decision_id in invalid_ids:
            with pytest.raises(ValidationError):
                CriticalDecisionPoint(
                    decision_id=decision_id,
                    decision_type="install_location",
                    title="Test Decision",
                    description="Test description",
                    options=[{"id": "option1", "label": "Option 1"}]
                )

    def test_decision_type_validation(self):
        """Test that decision_type must be one of valid literals."""
        valid_types = ["install_location", "service_port", "data_directory"]

        for decision_type in valid_types:
            decision = CriticalDecisionPoint(
                decision_id="test_001",
                decision_type=decision_type,
                title="Test Decision",
                description="Test description",
                options=[{"id": "option1", "label": "Option 1"}]
            )
            assert decision.decision_type == decision_type

        # Invalid decision type
        with pytest.raises(ValidationError):
            CriticalDecisionPoint(
                decision_id="test_001",
                decision_type="invalid_type",
                title="Test Decision",
                description="Test description",
                options=[{"id": "option1", "label": "Option 1"}]
            )

    def test_options_validation(self):
        """Test validation of options format."""
        # Valid options
        decision = CriticalDecisionPoint(
            decision_id="test_001",
            decision_type="install_location",
            title="Test Decision",
            description="Test description",
            options=[
                {"id": "opt1", "label": "Option 1", "description": "First option"},
                {"id": "opt2", "label": "Option 2"}
            ]
        )
        assert len(decision.options) == 2

        # Empty options list
        with pytest.raises(ValidationError) as exc_info:
            CriticalDecisionPoint(
                decision_id="test_001",
                decision_type="install_location",
                title="Test Decision",
                description="Test description",
                options=[]
            )
        assert "At least one option must be provided" in str(exc_info.value)

        # Missing required fields in options
        with pytest.raises(ValidationError) as exc_info:
            CriticalDecisionPoint(
                decision_id="test_001",
                decision_type="install_location",
                title="Test Decision",
                description="Test description",
                options=[{"label": "Option without ID"}]
            )
        assert "Each option must have an 'id' field" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            CriticalDecisionPoint(
                decision_id="test_001",
                decision_type="install_location",
                title="Test Decision",
                description="Test description",
                options=[{"id": "opt1"}]  # Missing label
            )
        assert "Each option must have a 'label' field" in str(exc_info.value)

    def test_validation_pattern_validation(self):
        """Test that validation_pattern must be a valid regex."""
        # Valid regex pattern
        decision = CriticalDecisionPoint(
            decision_id="test_001",
            decision_type="service_port",
            title="Service Port",
            description="Enter service port",
            options=[{"id": "custom", "label": "Custom port"}],
            validation_pattern=r"^\d{4,5}$"
        )
        assert decision.validation_pattern == r"^\d{4,5}$"

        # Invalid regex pattern
        with pytest.raises(ValidationError) as exc_info:
            CriticalDecisionPoint(
                decision_id="test_001",
                decision_type="service_port",
                title="Service Port",
                description="Enter service port",
                options=[{"id": "custom", "label": "Custom port"}],
                validation_pattern="[invalid regex"
            )
        assert "Invalid regex pattern" in str(exc_info.value)

    def test_timestamp_default(self):
        """Test that timestamp defaults to current time."""
        before_creation = datetime.now()
        decision = CriticalDecisionPoint(
            decision_id="test_001",
            decision_type="install_location",
            title="Test Decision",
            description="Test description",
            options=[{"id": "option1", "label": "Option 1"}]
        )
        after_creation = datetime.now()

        assert before_creation <= decision.timestamp <= after_creation

    def test_optional_fields(self):
        """Test that optional fields have correct defaults."""
        decision = CriticalDecisionPoint(
            decision_id="test_001",
            decision_type="install_location",
            title="Test Decision",
            description="Test description",
            options=[{"id": "option1", "label": "Option 1"}]
        )

        assert decision.default_option is None
        assert decision.user_choice is None
        assert decision.resolved is False
        assert decision.validation_pattern is None

    def test_user_choice_types(self):
        """Test that user_choice accepts both string and dict values."""
        # String choice
        decision1 = CriticalDecisionPoint(
            decision_id="test_001",
            decision_type="install_location",
            title="Test Decision",
            description="Test description",
            options=[{"id": "option1", "label": "Option 1"}],
            user_choice="option1"
        )
        assert decision1.user_choice == "option1"

        # Dict choice
        decision2 = CriticalDecisionPoint(
            decision_id="test_002",
            decision_type="service_port",
            title="Port Decision",
            description="Test description",
            options=[{"id": "custom", "label": "Custom"}],
            user_choice={"port": 8080, "protocol": "http"}
        )
        assert isinstance(decision2.user_choice, dict)
        assert decision2.user_choice["port"] == 8080

    def test_json_serialization_with_datetime(self):
        """Test JSON serialization handles datetime fields correctly."""
        decision = CriticalDecisionPoint(
            decision_id="test_001",
            decision_type="install_location",
            title="Test Decision",
            description="Test description",
            options=[{"id": "option1", "label": "Option 1"}],
            timestamp=datetime(2025, 1, 25, 12, 0, 0)
        )

        json_data = decision.model_dump(mode='json')
        assert isinstance(json_data['timestamp'], str)
        assert json_data['timestamp'] == "2025-01-25T12:00:00"

        # Deserialize from JSON
        restored = CriticalDecisionPoint.model_validate(json_data)
        assert restored.timestamp == decision.timestamp