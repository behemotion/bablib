"""Contract tests for critical decision API endpoints."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json
import uuid

from src.services.mcp_server import create_app
from src.models.installation import CriticalDecisionPoint


class TestCriticalDecisionsEndpoints:
    """Contract tests for GET/PUT /installation/{id}/decisions endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        # This will fail initially until implementation exists
        try:
            self.app = create_app()
            self.client = TestClient(self.app)
        except (ImportError, AttributeError):
            self.app = None
            self.client = None

        # Test data
        self.installation_id = str(uuid.uuid4())
        self.sample_decision = {
            "decision_id": "data_dir_choice",
            "decision_type": "data_directory",
            "title": "Choose Data Directory",
            "description": "Select where Bablib should store its data files",
            "options": [
                {"id": "default", "label": "Default location (~/.local/share/bablib)"},
                {"id": "custom", "label": "Custom location", "allows_custom": True}
            ],
            "default_option": "default",
            "validation_pattern": r"^/[\w/\-\.]+$"
        }

    def test_get_installation_decisions_endpoint_exists(self):
        """Test that GET /installation/{id}/decisions endpoint exists."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        response = self.client.get(f"/installation/{self.installation_id}/decisions")
        # Should not return 404 (endpoint should exist)
        assert response.status_code != 404, "GET decisions endpoint should exist"

    def test_put_installation_decisions_endpoint_exists(self):
        """Test that PUT /installation/{id}/decisions endpoint exists."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        decision_data = {
            "decision_id": "test_decision",
            "user_choice": {"id": "default"}
        }

        response = self.client.put(
            f"/installation/{self.installation_id}/decisions",
            json=decision_data
        )
        # Should not return 404 (endpoint should exist)
        assert response.status_code != 404, "PUT decisions endpoint should exist"

    def test_critical_decision_point_schema_validation(self):
        """Test CriticalDecisionPoint schema validation."""
        # Test valid decision point
        valid_decision = CriticalDecisionPoint(
            decision_id="valid_id",
            decision_type="install_location",
            title="Test Decision",
            description="A test decision",
            options=[
                {"id": "option1", "label": "Option 1"},
                {"id": "option2", "label": "Option 2"}
            ]
        )
        assert valid_decision.decision_id == "valid_id"
        assert valid_decision.decision_type == "install_location"
        assert len(valid_decision.options) == 2

        # Test decision_type enum validation
        with pytest.raises(ValueError, match="Input should be"):
            CriticalDecisionPoint(
                decision_id="invalid_type",
                decision_type="invalid_type",  # Should fail enum validation
                title="Test",
                description="Test",
                options=[{"id": "test", "label": "Test"}]
            )

    def test_decision_type_enum_validation(self):
        """Test decision_type enum validation accepts only valid values."""
        valid_types = ["install_location", "service_port", "data_directory"]

        for decision_type in valid_types:
            decision = CriticalDecisionPoint(
                decision_id=f"test_{decision_type}",
                decision_type=decision_type,
                title="Test Decision",
                description="Test description",
                options=[{"id": "test", "label": "Test"}]
            )
            assert decision.decision_type == decision_type

        # Test invalid enum value
        with pytest.raises(ValueError):
            CriticalDecisionPoint(
                decision_id="invalid_enum",
                decision_type="invalid_enum_value",
                title="Test",
                description="Test",
                options=[{"id": "test", "label": "Test"}]
            )

    def test_validation_pattern_regex_testing(self):
        """Test validation pattern regex testing."""
        # Valid regex pattern
        decision = CriticalDecisionPoint(
            decision_id="regex_test",
            decision_type="data_directory",
            title="Regex Test",
            description="Test regex validation",
            options=[{"id": "test", "label": "Test"}],
            validation_pattern=r"^/[\w/\-\.]+$"
        )
        assert decision.validation_pattern == r"^/[\w/\-\.]+$"

        # Invalid regex pattern should raise error
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            CriticalDecisionPoint(
                decision_id="invalid_regex",
                decision_type="data_directory",
                title="Invalid Regex",
                description="Test invalid regex",
                options=[{"id": "test", "label": "Test"}],
                validation_pattern="[invalid regex pattern"  # Missing closing bracket
            )

    def test_date_time_format_validation(self):
        """Test date-time format validation."""
        # Test with explicit datetime
        test_time = datetime(2025, 1, 25, 10, 30, 0)
        decision = CriticalDecisionPoint(
            decision_id="datetime_test",
            decision_type="install_location",
            title="DateTime Test",
            description="Test datetime handling",
            options=[{"id": "test", "label": "Test"}],
            timestamp=test_time
        )
        assert decision.timestamp == test_time

        # Test JSON serialization includes proper datetime format
        decision_dict = decision.model_dump()
        assert 'timestamp' in decision_dict

        # Test that timestamp is properly formatted when serialized
        json_str = decision.model_dump_json()
        parsed = json.loads(json_str)
        assert 'timestamp' in parsed
        # Should be ISO format datetime string
        assert 'T' in parsed['timestamp']  # ISO format includes T separator

    def test_options_validation_requirements(self):
        """Test that options field validation requires proper structure."""
        # Valid options
        valid_options = [
            {"id": "option1", "label": "Option 1"},
            {"id": "option2", "label": "Option 2", "description": "Extra info"}
        ]

        decision = CriticalDecisionPoint(
            decision_id="options_test",
            decision_type="service_port",
            title="Options Test",
            description="Test options validation",
            options=valid_options
        )
        assert len(decision.options) == 2

        # Empty options should fail
        with pytest.raises(ValueError, match="At least one option must be provided"):
            CriticalDecisionPoint(
                decision_id="empty_options",
                decision_type="service_port",
                title="Empty Options",
                description="Test empty options",
                options=[]
            )

        # Options missing 'id' field should fail
        with pytest.raises(ValueError, match="Each option must have an 'id' field"):
            CriticalDecisionPoint(
                decision_id="missing_id",
                decision_type="service_port",
                title="Missing ID",
                description="Test missing id",
                options=[{"label": "No ID option"}]
            )

        # Options missing 'label' field should fail
        with pytest.raises(ValueError, match="Each option must have a 'label' field"):
            CriticalDecisionPoint(
                decision_id="missing_label",
                decision_type="service_port",
                title="Missing Label",
                description="Test missing label",
                options=[{"id": "no_label"}]
            )

    def test_decision_id_format_validation(self):
        """Test decision_id format validation."""
        # Valid decision IDs
        valid_ids = ["simple_id", "with-hyphens", "with_underscores", "mix-of_both123"]

        for valid_id in valid_ids:
            decision = CriticalDecisionPoint(
                decision_id=valid_id,
                decision_type="install_location",
                title="ID Test",
                description="Test ID validation",
                options=[{"id": "test", "label": "Test"}]
            )
            assert decision.decision_id == valid_id

        # Invalid decision IDs
        invalid_ids = ["with spaces", "with.dots", "with@symbols", "with/slashes"]

        for invalid_id in invalid_ids:
            with pytest.raises(ValueError, match="must contain only alphanumeric characters"):
                CriticalDecisionPoint(
                    decision_id=invalid_id,
                    decision_type="install_location",
                    title="Invalid ID",
                    description="Test invalid ID",
                    options=[{"id": "test", "label": "Test"}]
                )

    @patch('src.services.config.ConfigService')
    def test_get_decisions_returns_array(self, mock_config_service):
        """Test that GET /installation/{id}/decisions returns array of decisions."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        # Mock service to return decision data
        mock_config = Mock()
        mock_config.get_installation_decisions.return_value = [self.sample_decision]
        mock_config_service.return_value = mock_config

        response = self.client.get(f"/installation/{self.installation_id}/decisions")

        # This will fail initially - endpoint doesn't exist
        if response.status_code == 404:
            pytest.fail("GET decisions endpoint not implemented - expected for TDD")

        # Should return 200 and array
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @patch('src.services.config.ConfigService')
    def test_put_decisions_accepts_user_choices(self, mock_config_service):
        """Test that PUT /installation/{id}/decisions accepts user choices."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        # Mock service
        mock_config = Mock()
        mock_config.submit_installation_decision.return_value = True
        mock_config_service.return_value = mock_config

        decision_submission = {
            "decision_id": "data_dir_choice",
            "user_choice": {"id": "custom", "path": "/opt/bablib"}
        }

        response = self.client.put(
            f"/installation/{self.installation_id}/decisions",
            json=decision_submission
        )

        # This will fail initially - endpoint doesn't exist
        if response.status_code == 404:
            pytest.fail("PUT decisions endpoint not implemented - expected for TDD")

        # Should return success
        assert response.status_code in [200, 201, 204]

    def test_get_decisions_handles_invalid_installation_id(self):
        """Test GET decisions handles invalid installation ID."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        invalid_id = "invalid-uuid-format"
        response = self.client.get(f"/installation/{invalid_id}/decisions")

        # Should not crash, should return appropriate error
        if response.status_code == 404:
            # Endpoint doesn't exist yet
            pytest.fail("GET decisions endpoint not implemented - expected for TDD")

        # Should return 400 for invalid ID format
        assert response.status_code == 400

    def test_put_decisions_validates_json_format(self):
        """Test PUT decisions validates JSON format."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        # Invalid JSON structure
        invalid_data = {
            "missing_decision_id": True,
            "no_user_choice": "invalid"
        }

        response = self.client.put(
            f"/installation/{self.installation_id}/decisions",
            json=invalid_data
        )

        # This will fail initially - endpoint doesn't exist
        if response.status_code == 404:
            pytest.fail("PUT decisions endpoint not implemented - expected for TDD")

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_array_schema_validation_in_response(self):
        """Test that GET response follows array schema validation."""
        if not self.client:
            pytest.fail("MCP server not implemented yet - expected for TDD")

        response = self.client.get(f"/installation/{self.installation_id}/decisions")

        if response.status_code == 404:
            pytest.fail("GET decisions endpoint not implemented - expected for TDD")

        if response.status_code == 200:
            data = response.json()
            # Should be array
            assert isinstance(data, list)

            # Each item should match CriticalDecisionPoint schema
            for item in data:
                # Validate against our model
                decision = CriticalDecisionPoint(**item)
                assert decision.decision_id is not None
                assert decision.decision_type in ["install_location", "service_port", "data_directory"]
                assert isinstance(decision.options, list)
                assert len(decision.options) > 0