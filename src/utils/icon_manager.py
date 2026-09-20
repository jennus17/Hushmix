"""Application icon handling.

The previous implementation built its path from the *current working
directory* and pointed at a ``.ico`` file that was never shipped (``.gitignore``
even excluded ``*.ico``), so every icon lookup failed and the app ran without a
tray or taskbar icon.  This module resolves the bundled artwork by absolute
path, generates the ``.ico`` on demand if it is missing, and never returns a
value that the callers cannot use.
"""

import os

from utils.app_paths import app_data_dir, asset_path
from utils.logging_setup import get_logger

logger = get_logger("icon_manager")

_BUNDLED_ICO = "volume_icon.ico"
_SOURCE_PNGS = ("volume_icon.png", "volume_icon32.png")


class IconManager:
    """Locates (and if needed builds) the Windows icon file."""

    _resolved_path = None
    _attempted = False

    @staticmethod
    def get_source_png():
        """Absolute path of the bundled PNG artwork, or ``None``."""
        for name in _SOURCE_PNGS:
            candidate = asset_path(name)
            if os.path.exists(candidate):
                return candidate
        return None

    @staticmethod
    def get_ico_file():
        """Absolute path of an existing ``.ico`` file, or ``None``.

        Callers must handle ``None``; it means the application simply runs
        without a custom icon instead of raising.
        """
        if IconManager._resolved_path and os.path.exists(IconManager._resolved_path):
            return IconManager._resolved_path

        if IconManager._attempted:
            return IconManager._resolved_path

        IconManager._attempted = True

        bundled = asset_path(_BUNDLED_ICO)
        if os.path.exists(bundled):
            IconManager._resolved_path = bundled
            return bundled

        generated = IconManager._generate_ico()
        IconManager._resolved_path = generated
        return generated

    @staticmethod
    def _generate_ico():
        """Build the ``.ico`` from PNG artwork into a writable directory."""
        source = IconManager.get_source_png()
        if not source:
            logger.warning("No icon artwork found next to %s", asset_path())
            return None

        targets = []
        # Prefer writing next to the artwork (works for a source checkout).
        targets.append(asset_path(_BUNDLED_ICO))
        # Fall back to the per-user data directory (read-only installs).
        targets.append(os.path.join(app_data_dir(), _BUNDLED_ICO))

        from utils import png2ico

        for target in targets:
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if not os.access(os.path.dirname(target), os.W_OK):
                    continue
                path, sizes = png2ico.png_to_ico(source, target)
                logger.info("Generated icon %s with sizes %s", path, sizes)
                return path
            except Exception as error:
                logger.debug("Could not generate icon at %s: %s", target, error)

        logger.warning("Falling back to a placeholder icon")
        fallback = os.path.join(app_data_dir(), _BUNDLED_ICO)
        try:
            os.makedirs(os.path.dirname(fallback), exist_ok=True)
            return png2ico.write_placeholder_ico(fallback)
        except Exception as error:
            logger.warning("Could not create placeholder icon: %s", error)
            return None

    @staticmethod
    def get_icon_image(size=None):
        """Return a PIL image for the tray icon, or ``None`` on failure."""
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow is not installed - tray icon unavailable")
            return None

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                image = Image.open(ico_path)
                image.load()
                if size:
                    image = image.resize((size, size), Image.LANCZOS)
                return image.convert("RGBA")
            except Exception as error:
                logger.debug("Could not load %s: %s", ico_path, error)

        png_path = IconManager.get_source_png()
        if png_path:
            try:
                image = Image.open(png_path)
                image.load()
                if size:
                    image = image.resize((size, size), Image.LANCZOS)
                return image.convert("RGBA")
            except Exception as error:
                logger.warning("Could not load %s: %s", png_path, error)

        return None

    @staticmethod
    def apply_to_window(window):
        """Set the window/taskbar icon, tolerating a missing icon file."""
        ico_path = IconManager.get_ico_file()
        if not ico_path:
            return False

        try:
            window.iconbitmap(default=ico_path)
            window.wm_iconbitmap(ico_path)
            return True
        except Exception as error:
            logger.debug("Could not set window icon: %s", error)
            return False
