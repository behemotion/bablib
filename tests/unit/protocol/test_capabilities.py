"""Unit tests for MCP capability negotiation."""

from src.logic.mcp.protocol.capabilities import (
    InitializeResponse,
    LoggingCapability,
    PromptsCapability,
    ResourcesCapability,
    ServerCapabilities,
    ServerInfo,
    ToolsCapability,
)


class TestToolsCapability:
    """Test tools capability."""

    def test_default_tools_capability(self):
        """Test default tools capability."""
        capability = ToolsCapability()
        assert capability.list_changed is True


class TestResourcesCapability:
    """Test resources capability."""

    def test_default_resources_capability(self):
        """Test default resources capability."""
        capability = ResourcesCapability()
        assert capability.subscribe is False
        assert capability.list_changed is True


class TestPromptsCapability:
    """Test prompts capability."""

    def test_default_prompts_capability(self):
        """Test default prompts capability."""
        capability = PromptsCapability()
        assert capability.list_changed is False


class TestServerCapabilities:
    """Test server capabilities."""

    def test_create_default_read_only_capabilities(self):
        """Test creating default read-only server capabilities."""
        capabilities = ServerCapabilities.default_read_only()

        assert capabilities.tools is not None
        assert capabilities.tools.list_changed is True

        assert capabilities.resources is not None
        assert capabilities.resources.subscribe is False
        assert capabilities.resources.list_changed is True

        assert capabilities.prompts is not None
        assert capabilities.prompts.list_changed is False

        assert capabilities.logging is not None

    def test_create_default_admin_capabilities(self):
        """Test creating default admin server capabilities."""
        capabilities = ServerCapabilities.default_admin()

        assert capabilities.tools is not None
        assert capabilities.tools.list_changed is True

        assert capabilities.resources is not None
        assert capabilities.resources.subscribe is False
        assert capabilities.resources.list_changed is True

    def test_custom_capabilities(self):
        """Test creating custom capabilities."""
        capabilities = ServerCapabilities(
            tools=ToolsCapability(list_changed=False),
            resources=ResourcesCapability(subscribe=True, list_changed=True),
        )

        assert capabilities.tools.list_changed is False
        assert capabilities.resources.subscribe is True


class TestServerInfo:
    """Test server info."""

    def test_create_server_info(self):
        """Test creating server info."""
        info = ServerInfo(name="bablib", version="1.0.0")
        assert info.name == "bablib"
        assert info.version == "1.0.0"


class TestInitializeResponse:
    """Test initialize response."""

    def test_create_initialize_response(self):
        """Test creating initialize response."""
        capabilities = ServerCapabilities.default_read_only()
        response = InitializeResponse.create(
            server_name="bablib",
            server_version="1.0.0",
            capabilities=capabilities,
        )

        assert response.protocol_version == "2024-11-05"
        assert response.server_info.name == "bablib"
        assert response.server_info.version == "1.0.0"
        assert response.capabilities == capabilities

    def test_initialize_response_with_custom_protocol_version(self):
        """Test initialize response with custom protocol version."""
        capabilities = ServerCapabilities.default_admin()
        response = InitializeResponse.create(
            server_name="bablib-admin",
            server_version="1.0.0",
            capabilities=capabilities,
            protocol_version="2025-01-01",
        )

        assert response.protocol_version == "2025-01-01"

    def test_initialize_response_serialization(self):
        """Test that response serializes with camelCase aliases."""
        capabilities = ServerCapabilities.default_read_only()
        response = InitializeResponse.create(
            server_name="bablib",
            server_version="1.0.0",
            capabilities=capabilities,
        )

        data = response.model_dump(by_alias=True)
        assert "protocolVersion" in data
        assert "serverInfo" in data
        assert "capabilities" in data
