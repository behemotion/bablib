"""CLI module for Bablib."""

# Import main only when explicitly requested to avoid circular import warnings
def get_main():
    """Get the main CLI function."""
    from .main import main
    return main

__all__ = ["get_main"]
