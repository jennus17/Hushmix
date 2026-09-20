"""Tk scaling helper for the main window.

Windows are scaled by asking Tk to adopt the DPI of the monitor they are on.
The monitor lookup itself lives in :mod:`utils.win_utils` so this module, the
shared window base class and the window manager cannot drift apart.

``WindowManager`` re-applies scaling as the window is dragged between monitors;
this class provides the initial application at startup.
"""

from utils.logging_setup import get_logger
from utils.win_utils import get_monitor_dpi

logger = get_logger("dpi_manager")

RETRY_DELAY_MS = 100
MAX_RETRIES = 20


class DPIManager:
    """Applies a DPI-derived Tk scaling factor to a window."""

    def __init__(self):
        self.last_monitor_dpi = None

    def get_monitor_dpi(self, x, y):
        """Effective DPI scale factor (1.0 == 96 DPI)."""
        return get_monitor_dpi(x, y)

    def apply_scaling(self, window, x=None, y=None, window_name="window", refresh_callback=None):
        """Set Tk scaling for the monitor at ``(x, y)`` (defaults to the window)."""
        try:
            if x is None or y is None:
                x = window.winfo_x()
                y = window.winfo_y()

            scaling = get_monitor_dpi(x, y)
            window.tk.call("tk", "scaling", scaling)
            self.last_monitor_dpi = scaling

            if refresh_callback:
                refresh_callback()

            logger.debug("%s DPI scaling set to %.2f", window_name, scaling)
            return scaling
        except Exception as error:
            logger.debug("Error applying DPI scaling for %s: %s", window_name, error)
            return None

    def adjust_dpi_scaling(self, window, x, y, window_name="window", refresh_callback=None):
        """Apply scaling only when the monitor DPI actually changed."""
        current = get_monitor_dpi(x, y)
        if self.last_monitor_dpi is not None and abs(current - self.last_monitor_dpi) <= 0.01:
            return current

        return self.apply_scaling(window, x, y, window_name, refresh_callback)

    def adjust_dpi_scaling_delayed(self, window, window_name="window", refresh_callback=None, delay=50):
        """Schedule :meth:`apply_scaling` for a freshly created window."""
        self._schedule(window, window_name, refresh_callback, delay, retries=MAX_RETRIES)

    def initialize_dpi_scaling(self, window, window_name="window", refresh_callback=None, delay=100):
        """Apply the initial scaling once the window has a real position."""
        self._schedule(window, window_name, refresh_callback, delay, retries=MAX_RETRIES)

    def _schedule(self, window, window_name, refresh_callback, delay, retries):
        def _run(remaining):
            try:
                if not window.winfo_exists():
                    return

                x = window.winfo_x()
                y = window.winfo_y()

                # Tk reports 0,0 until the window manager has placed the window.
                if x == 0 and y == 0 and remaining > 0:
                    window.after(delay, lambda: _run(remaining - 1))
                    return

                self.apply_scaling(window, x, y, window_name, refresh_callback)
            except Exception as error:
                logger.debug("Error initialising DPI scaling for %s: %s", window_name, error)

        try:
            window.after(delay, lambda: _run(retries))
        except Exception as error:
            logger.debug("Could not schedule DPI scaling for %s: %s", window_name, error)
