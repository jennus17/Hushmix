"""Deprecated: superseded by :mod:`utils.enhanced_version_manager`.

This module only performs a naive string comparison of the local and remote
version, so it prompts for an "update" even when the local build is newer.
It is kept for backwards compatibility and will be removed in a future release.
"""

import warnings

warnings.warn(
    "utils.version_manager is deprecated; use utils.enhanced_version_manager",
    DeprecationWarning,
    stacklevel=2,
)

from utils.enhanced_version_manager import EnhancedVersionManager  # noqa: E402


class VersionManager(EnhancedVersionManager):
    """Deprecated alias for :class:`EnhancedVersionManager`."""

    def __init__(self, parent, settings_manager=None):
        if settings_manager is None:
            from utils.settings_manager import SettingsManager

            settings_manager = SettingsManager(app=None)
        super().__init__(parent, settings_manager)
