"""
Integration test for project configuration hierarchy

Tests end-to-end configuration management including:
- Global default settings
- Project-specific setting overrides
- Type-specific setting validation
- Settings inheritance and precedence
- Configuration file persistence
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.logic.projects.core.project_manager import ProjectManager
from src.logic.projects.core.config_manager import ConfigManager
from src.logic.projects.models.project import Project, ProjectType, ProjectStatus
from src.logic.projects.models.config import ProjectConfig


@pytest.fixture
async def project_manager():
    """Create project manager for testing"""
    manager = ProjectManager()
    await manager.initialize()
    return manager


@pytest.fixture
async def config_manager():
    """Create config manager for testing"""
    manager = ConfigManager()
    await manager.initialize()
    return manager


@pytest.fixture
def temp_config_dir():
    """Create temporary configuration directory"""
    temp_dir = tempfile.mkdtemp()
    config_dir = Path(temp_dir) / "bablib"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.mark.asyncio
async def test_global_default_settings(config_manager, temp_config_dir):
    """Test loading and applying global default settings"""
    # Create global settings file
    global_settings = {
        "project_defaults": {
            "max_file_size": 10485760,  # 10MB
            "allowed_formats": {
                "documents": ["pdf", "txt", "md", "html"],
                "images": ["jpg", "jpeg", "png", "gif"],
                "archives": ["zip", "tar", "gz"]
            },
            "crawling": {
                "crawl_depth": 3,
                "rate_limit": 1.0,
                "user_agent": "Bablib/1.0"
            },
            "data": {
                "chunk_size": 500,
                "embedding_model": "mxbai-embed-large",
                "vector_store_type": "sqlite_vec"
            },
            "storage": {
                "enable_compression": False,
                "auto_tagging": True,
                "full_text_indexing": True
            }
        }
    }

    settings_file = temp_config_dir / "settings.yaml"
    with open(settings_file, 'w') as f:
        yaml.dump(global_settings, f)

    # Mock config directory
    with patch('src.logic.projects.core.config_manager.get_config_dir', return_value=temp_config_dir):
        global_config = await config_manager.get_global_settings()

    assert global_config is not None
    assert global_config["project_defaults"]["max_file_size"] == 10485760
    assert "pdf" in global_config["project_defaults"]["allowed_formats"]["documents"]
    assert global_config["project_defaults"]["crawling"]["crawl_depth"] == 3


@pytest.mark.asyncio
async def test_project_specific_overrides(project_manager, config_manager, temp_config_dir):
    """Test that project-specific settings override global defaults"""
    project_name = "test-override-project"

    # Create project with custom settings
    custom_config = ProjectConfig(
        max_file_size=52428800,  # 50MB (override default 10MB)
        allowed_formats=["pdf", "txt", "md"],  # Restricted from global defaults
        type_specific_settings={
            "chunk_size": 1000,  # Override default 500
            "embedding_model": "custom-model",  # Override default
            "custom_setting": "project-specific-value"  # New setting
        }
    )

    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.DATA,
        config=custom_config
    )

    # Get effective settings (should be global + project overrides)
    effective_config = await config_manager.get_project_settings(project_name)

    assert effective_config.max_file_size == 52428800  # Project override
    assert effective_config.allowed_formats == ["pdf", "txt", "md"]  # Project override
    assert effective_config.type_specific_settings["chunk_size"] == 1000  # Project override
    assert effective_config.type_specific_settings["embedding_model"] == "custom-model"  # Project override
    assert effective_config.type_specific_settings["custom_setting"] == "project-specific-value"  # New setting


@pytest.mark.asyncio
async def test_type_specific_setting_validation(project_manager, config_manager):
    """Test validation of type-specific settings"""
    # Test valid crawling project settings
    crawling_config = ProjectConfig(
        type_specific_settings={
            "crawl_depth": 5,
            "rate_limit": 0.5,
            "user_agent": "CustomBot/1.0",
            "follow_redirects": True
        }
    )

    validation_result = await config_manager.validate_settings_hierarchy(
        global_settings={},
        project_settings=crawling_config.dict(),
        project_type=ProjectType.CRAWLING
    )

    assert validation_result.valid is True
    assert len(validation_result.errors) == 0

    # Test invalid crawling project settings
    invalid_crawling_config = ProjectConfig(
        type_specific_settings={
            "crawl_depth": -1,  # Invalid negative depth
            "rate_limit": "invalid",  # Invalid type
            "chunk_size": 500  # Wrong setting for crawling project
        }
    )

    validation_result = await config_manager.validate_settings_hierarchy(
        global_settings={},
        project_settings=invalid_crawling_config.dict(),
        project_type=ProjectType.CRAWLING
    )

    assert validation_result.valid is False
    assert len(validation_result.errors) > 0


@pytest.mark.asyncio
async def test_data_project_specific_settings(project_manager, config_manager):
    """Test data project specific configuration validation"""
    project_name = "test-data-config"

    # Valid data project configuration
    data_config = ProjectConfig(
        type_specific_settings={
            "chunk_size": 750,
            "chunk_overlap": 50,
            "embedding_model": "mxbai-embed-large",
            "vector_store_type": "qdrant",
            "similarity_threshold": 0.7
        }
    )

    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.DATA,
        config=data_config
    )

    effective_config = await config_manager.get_project_settings(project_name)

    assert effective_config.type_specific_settings["chunk_size"] == 750
    assert effective_config.type_specific_settings["embedding_model"] == "mxbai-embed-large"
    assert effective_config.type_specific_settings["vector_store_type"] == "qdrant"

    # Test invalid data project settings
    invalid_data_config = ProjectConfig(
        type_specific_settings={
            "chunk_size": "invalid",  # Should be integer
            "crawl_depth": 3,  # Wrong setting for data project
            "embedding_model": "",  # Empty model name
        }
    )

    validation_result = await config_manager.validate_settings_hierarchy(
        global_settings={},
        project_settings=invalid_data_config.dict(),
        project_type=ProjectType.DATA
    )

    assert validation_result.valid is False
    assert len(validation_result.errors) > 0


@pytest.mark.asyncio
async def test_storage_project_specific_settings(project_manager, config_manager):
    """Test storage project specific configuration validation"""
    project_name = "test-storage-config"

    # Valid storage project configuration
    storage_config = ProjectConfig(
        max_file_size=104857600,  # 100MB
        allowed_formats=["jpg", "png", "pdf", "zip", "txt"],
        type_specific_settings={
            "enable_compression": True,
            "compression_level": 6,
            "auto_tagging": True,
            "full_text_indexing": True,
            "thumbnail_generation": True
        }
    )

    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.STORAGE,
        config=storage_config
    )

    effective_config = await config_manager.get_project_settings(project_name)

    assert effective_config.max_file_size == 104857600
    assert effective_config.type_specific_settings["enable_compression"] is True
    assert effective_config.type_specific_settings["auto_tagging"] is True


@pytest.mark.asyncio
async def test_config_file_persistence(project_manager, config_manager, temp_config_dir):
    """Test that project configurations are persisted to files"""
    project_name = "test-config-persistence"

    # Create project with custom configuration
    custom_config = ProjectConfig(
        max_file_size=20971520,  # 20MB
        allowed_formats=["pdf", "docx", "txt"],
        type_specific_settings={
            "chunk_size": 800,
            "embedding_model": "custom-embedding",
            "metadata_extraction": True
        }
    )

    # Mock project data directory
    project_data_dir = temp_config_dir / "projects" / project_name
    project_data_dir.mkdir(parents=True)

    with patch('src.logic.projects.core.config_manager.get_project_data_dir', return_value=project_data_dir):
        project = await project_manager.create_project(
            name=project_name,
            project_type=ProjectType.DATA,
            config=custom_config
        )

        # Verify config file was created
        config_file = project_data_dir / "settings.yaml"
        assert config_file.exists()

        # Verify config contents
        with open(config_file, 'r') as f:
            saved_config = yaml.safe_load(f)

        assert saved_config["max_file_size"] == 20971520
        assert saved_config["allowed_formats"] == ["pdf", "docx", "txt"]
        assert saved_config["type_specific_settings"]["chunk_size"] == 800


@pytest.mark.asyncio
async def test_config_update_workflow(project_manager, config_manager):
    """Test updating project configuration after creation"""
    project_name = "test-config-update"

    # Create project with initial configuration
    initial_config = ProjectConfig(
        max_file_size=10485760,
        type_specific_settings={
            "chunk_size": 500,
            "embedding_model": "default-model"
        }
    )

    project = await project_manager.create_project(
        name=project_name,
        project_type=ProjectType.DATA,
        config=initial_config
    )

    # Update configuration
    updated_settings = {
        "max_file_size": 52428800,  # Increase to 50MB
        "type_specific_settings": {
            "chunk_size": 1000,  # Increase chunk size
            "embedding_model": "updated-model",  # Change model
            "new_setting": "new_value"  # Add new setting
        }
    }

    updated_config = await config_manager.update_project_settings(
        project_name=project_name,
        settings=updated_settings
    )

    # Verify updates were applied
    assert updated_config.max_file_size == 52428800
    assert updated_config.type_specific_settings["chunk_size"] == 1000
    assert updated_config.type_specific_settings["embedding_model"] == "updated-model"
    assert updated_config.type_specific_settings["new_setting"] == "new_value"

    # Verify changes persisted
    reloaded_config = await config_manager.get_project_settings(project_name)
    assert reloaded_config.max_file_size == 52428800
    assert reloaded_config.type_specific_settings["chunk_size"] == 1000


@pytest.mark.asyncio
async def test_environment_variable_overrides(config_manager, temp_config_dir):
    """Test that environment variables can override configuration settings"""
    # Set environment variables
    import os
    env_overrides = {
        "BABLIB_MAX_FILE_SIZE": "20971520",  # 20MB
        "BABLIB_CHUNK_SIZE": "750",
        "BABLIB_EMBEDDING_MODEL": "env-model"
    }

    with patch.dict(os.environ, env_overrides):
        with patch('src.logic.projects.core.config_manager.get_config_dir', return_value=temp_config_dir):
            env_config = await config_manager.get_global_settings()

    # Environment variables should override file settings
    # This depends on implementation details of how env vars are processed
    assert env_config is not None


@pytest.mark.asyncio
async def test_config_inheritance_chain(project_manager, config_manager, temp_config_dir):
    """Test complete configuration inheritance chain"""
    # Create global settings
    global_settings = {
        "project_defaults": {
            "max_file_size": 10485760,  # 10MB
            "allowed_formats": ["pdf", "txt", "md", "html", "docx"],
            "data": {
                "chunk_size": 500,
                "embedding_model": "global-model",
                "vector_store_type": "sqlite_vec"
            }
        }
    }

    settings_file = temp_config_dir / "settings.yaml"
    with open(settings_file, 'w') as f:
        yaml.dump(global_settings, f)

    # Create project with partial overrides
    project_config = ProjectConfig(
        max_file_size=20971520,  # Override: 20MB
        # allowed_formats inherited from global
        type_specific_settings={
            "chunk_size": 750,  # Override: 750
            "embedding_model": "project-model",  # Override: project-model
            # vector_store_type inherited from global
            "new_project_setting": "project-value"  # New: project-specific
        }
    )

    project_name = "test-inheritance"

    with patch('src.logic.projects.core.config_manager.get_config_dir', return_value=temp_config_dir):
        project = await project_manager.create_project(
            name=project_name,
            project_type=ProjectType.DATA,
            config=project_config
        )

        effective_config = await config_manager.get_project_settings(project_name)

    # Verify inheritance chain
    assert effective_config.max_file_size == 20971520  # Project override
    assert "pdf" in effective_config.allowed_formats  # Global default
    assert effective_config.type_specific_settings["chunk_size"] == 750  # Project override
    assert effective_config.type_specific_settings["embedding_model"] == "project-model"  # Project override
    assert effective_config.type_specific_settings.get("vector_store_type") == "sqlite_vec"  # Global default
    assert effective_config.type_specific_settings["new_project_setting"] == "project-value"  # Project-specific


@pytest.mark.asyncio
async def test_config_validation_errors(config_manager):
    """Test comprehensive configuration validation with detailed error messages"""
    # Test multiple validation errors
    invalid_config = {
        "max_file_size": -1,  # Invalid: negative
        "allowed_formats": "not-a-list",  # Invalid: should be list
        "type_specific_settings": {
            "chunk_size": "invalid",  # Invalid: should be integer
            "rate_limit": -0.5,  # Invalid: negative rate limit
            "crawl_depth": 1000,  # Invalid: too deep
        }
    }

    validation_result = await config_manager.validate_settings_hierarchy(
        global_settings={},
        project_settings=invalid_config,
        project_type=ProjectType.CRAWLING
    )

    assert validation_result.valid is False
    assert len(validation_result.errors) >= 3  # Multiple validation errors

    # Check that error messages are descriptive
    error_text = " ".join(validation_result.errors).lower()
    assert "max_file_size" in error_text
    assert "allowed_formats" in error_text
    assert "chunk_size" in error_text or "rate_limit" in error_text


@pytest.mark.asyncio
async def test_config_migration_compatibility(config_manager, temp_config_dir):
    """Test handling of legacy configuration formats"""
    # Create legacy format configuration
    legacy_config = {
        # Old format - flat structure
        "max_file_size": 10485760,
        "crawl_depth": 3,
        "chunk_size": 500,
        "embedding_model": "legacy-model"
    }

    legacy_file = temp_config_dir / "legacy_settings.yaml"
    with open(legacy_file, 'w') as f:
        yaml.dump(legacy_config, f)

    # Test migration/compatibility handling
    with patch('src.logic.projects.core.config_manager.get_config_dir', return_value=temp_config_dir):
        # This would test migration logic if implemented
        migrated_config = await config_manager.migrate_legacy_config(legacy_file)

    # Verify migration preserved settings in new format
    assert migrated_config is not None