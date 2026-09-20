"""Utility helpers for Hushmix.

Only dependency-light modules are re-exported here: importing
``EnhancedVersionManager`` (or the deprecated ``VersionManager``) pulls in the
GUI layer and should be done explicitly by the caller.
"""

from .config_manager import ConfigManager
from .icon_manager import IconManager

__all__ = ["ConfigManager", "IconManager"]
