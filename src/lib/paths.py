"""
XDG-compliant directory utilities for Bablib settings.
"""

import os
from pathlib import Path


def get_xdg_config_home() -> Path:
    """Get XDG config home directory."""
    xdg_config = os.environ.get('XDG_CONFIG_HOME')
    if xdg_config:
        return Path(xdg_config)
    return Path.home() / '.config'

def get_xdg_data_home() -> Path:
    """Get XDG data home directory."""
    xdg_data = os.environ.get('XDG_DATA_HOME')
    if xdg_data:
        return Path(xdg_data)
    return Path.home() / '.local' / 'share'

def get_xdg_cache_home() -> Path:
    """Get XDG cache home directory."""
    xdg_cache = os.environ.get('XDG_CACHE_HOME')
    if xdg_cache:
        return Path(xdg_cache)
    return Path.home() / '.cache'

def get_bablib_config_dir() -> Path:
    """Get Bablib configuration directory."""
    config_dir = get_xdg_config_home() / 'bablib'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_bablib_data_dir() -> Path:
    """Get Bablib data directory."""
    data_dir = get_xdg_data_home() / 'bablib'
    data_dir.mkdir(parents=True, exist_ok=True)

    # Ensure projects subdirectory exists
    projects_dir = data_dir / 'projects'
    projects_dir.mkdir(parents=True, exist_ok=True)

    return data_dir

def get_bablib_cache_dir() -> Path:
    """Get Bablib cache directory."""
    cache_dir = get_xdg_cache_home() / 'bablib'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_bablib_projects_dir() -> Path:
    """Get Bablib projects directory."""
    # This will automatically create the projects directory via get_bablib_data_dir()
    return get_bablib_data_dir() / 'projects'

def get_bablib_boxes_dir() -> Path:
    """Get Bablib boxes directory."""
    boxes_dir = get_bablib_data_dir() / 'boxes'
    boxes_dir.mkdir(parents=True, exist_ok=True)
    return boxes_dir

def get_box_data_path(box_name: str) -> Path:
    """Get path to a specific box's data directory.

    Args:
        box_name: Name of the box

    Returns:
        Path to the box's data directory (~/.local/share/bablib/boxes/{box_name}/)
    """
    box_dir = get_bablib_boxes_dir() / box_name
    box_dir.mkdir(parents=True, exist_ok=True)
    return box_dir

def get_global_settings_path() -> Path:
    """Get path to global settings file."""
    return get_bablib_config_dir() / 'settings.yaml'

def get_project_settings_path(project_dir: Path | None = None) -> Path:
    """Get path to project settings file."""
    if project_dir is None:
        project_dir = Path.cwd()
    return project_dir / '.bablib' / 'settings.yaml'

def ensure_directory(path: Path) -> None:
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)

def expand_path(path: str) -> Path:
    """Expand user home directory and resolve path."""
    return Path(path).expanduser().resolve()
