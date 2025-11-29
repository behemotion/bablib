"""Compatibility layer for old config imports."""

# Re-export from the new location
from src.core.config import BablibConfig

__all__ = ["BablibConfig"]