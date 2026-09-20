"""Tk scaling compatibility shim.

Scaling is owned by CustomTkinter.  Creating a ``CTk``/``CTkToplevel`` sets
per-monitor DPI awareness and starts ``ScalingTracker``, which polls the window's
DPI every 100 ms and rescales every widget plus the window itself.  That is
exactly the behaviour this module used to approximate by hand, and doing it by
hand conflicted with it: the window was resized from the *scaled* dimensions
while the widgets were rebuilt at the previous scale, so moving the window to a
monitor with a different DPI made it grow without its content keeping up.

Nothing in the application should call ``tk scaling`` any more.  This class is
kept as the single place that documents the rule and as a convenience for
reading the scale CustomTkinter is currently applying.
"""

from utils.logging_setup import get_logger
from utils.win_utils import get_monitor_dpi

logger = get_logger("dpi_manager")


class DPIManager:
    """Read-only view of the scaling CustomTkinter is applying."""

    def __init__(self):
        self.last_monitor_dpi = None

    def get_monitor_dpi(self, x, y):
        """Effective DPI scale factor for the monitor at ``(x, y)`` (1.0 = 96 DPI)."""
        return get_monitor_dpi(x, y)

    def apply_scaling(self, window, x=None, y=None, window_name="window", refresh_callback=None):
        """No-op kept for call-site compatibility.

        Returns the scale CustomTkinter is using for *window* so callers that log
        or compare it keep working.
        """
        try:
            from customtkinter import ScalingTracker

            scaling = ScalingTracker.get_window_scaling(window)
            self.last_monitor_dpi = scaling
            return scaling
        except Exception as error:
            logger.debug("Could not read the scaling for %s: %s", window_name, error)
            return None

    def adjust_dpi_scaling(self, window, x, y, window_name="window", refresh_callback=None):
        """No-op; see :meth:`apply_scaling`."""
        return self.apply_scaling(window, x, y, window_name, refresh_callback)

    def initialize_dpi_scaling(self, window, window_name="window", refresh_callback=None, delay=100):
        """No-op; see :meth:`apply_scaling`."""
        return self.apply_scaling(window, window_name=window_name)

    def adjust_dpi_scaling_delayed(self, window, window_name="window", refresh_callback=None, delay=50):
        """No-op; see :meth:`apply_scaling`."""
        return self.apply_scaling(window, window_name=window_name)
