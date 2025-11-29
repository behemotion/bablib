"""Unit tests for MCP types (Tool, Resource, Prompt)."""

from src.logic.mcp.models.mcp_types import (
    Prompt,
    PromptsList,
    Resource,
    ResourceContents,
    ResourceTemplate,
    ResourceTemplatesList,
    ResourcesList,
    Tool,
    ToolsList,
)


class TestTool:
    """Test MCP Tool model."""

    def test_create_tool_with_schema(self):
        """Test creating tool with input schema."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "arg1": {"type": "string"},
                },
            },
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert "properties" in tool.input_schema

    def test_create_tool_helper(self):
        """Test Tool.create helper method."""
        tool = Tool.create(
            name="simple_tool",
            description="Simple tool",
        )

        assert tool.name == "simple_tool"
        assert tool.input_schema == {"type": "object", "properties": {}}

    def test_tool_serialization(self):
        """Test tool serialization with camelCase."""
        tool = Tool.create("test", "Test tool")
        data = tool.model_dump(by_alias=True)

        assert "inputSchema" in data


class TestResource:
    """Test MCP Resource model."""

    def test_create_resource(self):
        """Test creating resource."""
        resource = Resource(
            uri="bablib://shelf/test",
            name="Test Shelf",
            description="A test shelf",
            mime_type="application/json",
        )

        assert resource.uri == "bablib://shelf/test"
        assert resource.name == "Test Shelf"
        assert resource.description == "A test shelf"
        assert resource.mime_type == "application/json"

    def test_create_resource_helper(self):
        """Test Resource.create helper method."""
        resource = Resource.create(
            uri="bablib://box/test",
            name="Test Box",
        )

        assert resource.uri == "bablib://box/test"
        assert resource.name == "Test Box"
        assert resource.mime_type == "application/json"

    def test_resource_serialization(self):
        """Test resource serialization with camelCase."""
        resource = Resource.create("uri://test", "Test")
        data = resource.model_dump(by_alias=True)

        assert "mimeType" in data


class TestResourceContents:
    """Test MCP ResourceContents model."""

    def test_create_text_contents(self):
        """Test creating text resource contents."""
        contents = ResourceContents(
            uri="bablib://shelf/test",
            mime_type="text/plain",
            text="Test content",
        )

        assert contents.uri == "bablib://shelf/test"
        assert contents.mime_type == "text/plain"
        assert contents.text == "Test content"
        assert contents.blob is None

    def test_create_binary_contents(self):
        """Test creating binary resource contents."""
        contents = ResourceContents(
            uri="bablib://file/test",
            mime_type="application/octet-stream",
            blob="base64encodeddata",
        )

        assert contents.blob == "base64encodeddata"
        assert contents.text is None


class TestResourceTemplate:
    """Test MCP ResourceTemplate model."""

    def test_create_template(self):
        """Test creating resource template."""
        template = ResourceTemplate(
            uri_template="bablib://shelf/{name}",
            name="Shelf Template",
            description="Access any shelf by name",
            mime_type="application/json",
        )

        assert template.uri_template == "bablib://shelf/{name}"
        assert template.name == "Shelf Template"

    def test_template_serialization(self):
        """Test template serialization."""
        template = ResourceTemplate(
            uri_template="bablib://box/{shelf}/{name}",
            name="Box Template",
        )
        data = template.model_dump(by_alias=True)

        assert "uriTemplate" in data
        assert "mimeType" in data


class TestPrompt:
    """Test MCP Prompt model."""

    def test_create_prompt(self):
        """Test creating prompt."""
        prompt = Prompt(
            name="test_prompt",
            description="A test prompt",
            arguments=[
                {"name": "arg1", "type": "string"},
            ],
        )

        assert prompt.name == "test_prompt"
        assert prompt.description == "A test prompt"
        assert len(prompt.arguments) == 1

    def test_prompt_without_arguments(self):
        """Test prompt without arguments."""
        prompt = Prompt(name="simple_prompt")
        assert prompt.arguments is None


class TestListModels:
    """Test list response models."""

    def test_tools_list(self):
        """Test ToolsList model."""
        tools = [
            Tool.create("tool1", "First tool"),
            Tool.create("tool2", "Second tool"),
        ]
        tools_list = ToolsList(tools=tools)

        assert len(tools_list.tools) == 2
        assert tools_list.tools[0].name == "tool1"

    def test_resources_list(self):
        """Test ResourcesList model."""
        resources = [
            Resource.create("uri://1", "Resource 1"),
            Resource.create("uri://2", "Resource 2"),
        ]
        resources_list = ResourcesList(resources=resources)

        assert len(resources_list.resources) == 2

    def test_resource_templates_list(self):
        """Test ResourceTemplatesList model."""
        templates = [
            ResourceTemplate(uri_template="uri://{id}", name="Template 1"),
        ]
        templates_list = ResourceTemplatesList(resource_templates=templates)

        assert len(templates_list.resource_templates) == 1

        # Test serialization with camelCase
        data = templates_list.model_dump(by_alias=True)
        assert "resourceTemplates" in data

    def test_prompts_list(self):
        """Test PromptsList model."""
        prompts = [
            Prompt(name="prompt1", description="First prompt"),
            Prompt(name="prompt2", description="Second prompt"),
        ]
        prompts_list = PromptsList(prompts=prompts)

        assert len(prompts_list.prompts) == 2
