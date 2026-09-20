"""Shared plumbing for the popup windows.

``settings_window``, ``help_window``, ``buttonSettings_window``,
``version_window`` and ``update_progress_window`` each carried their own copy
of the icon handling, DPI bootstrap, centring maths and teardown.  They now
share this base class, which fixes three defects in one place:

* ``self.window.after(200, lambda: self.window.iconbitmap(ico_path))`` executed
  *outside* the ``try`` block, so a missing icon file raised from the Tk
  callback instead of being handled;
* centring ran before the window was mapped, so ``winfo_width()`` returned the
  placeholder size and windows landed off-centre;
* ``grab_release()`` was called on windows that never grabbed anything.
"""

import customtkinter as ctk

from utils.icon_manager import IconManager
from utils.logging_setup import get_logger
from utils.win_utils import center_on_monitor, clamp_to_monitor, enum_monitors

logger = get_logger("base_window")

#: How long after the first reveal to re-assert visibility (ms).  Must comfortably
#: exceed the delay CustomTkinter uses for its titlebar colour pass.
REVEAL_REASSERT_DELAY_MS = 250


class BaseWindow:
    """Common behaviour for the app's secondary windows."""

    #: Overridden by subclasses; used for logs and DPI messages.
    window_name = "window"
    #: Fallback size used when the window has not been laid out yet.
    default_size = (400, 300)
    #: Vertical centring bias - popups sit slightly above the parent centre.
    vertical_divisor = 1.8

    def __init__(self, parent, on_close=None):
        self.parent = parent
        self.on_close = on_close
        self.window = ctk.CTkToplevel(parent)
        self.window.withdraw()

        self._ready = False

    # ---------------------------------------------------------------- bootstrapping

    def build(self, title, resizable=(False, False), topmost=False, geometry=None):
        """Apply window properties; call before :meth:`show`."""
        self.window.title(title)
        self.window.resizable(*resizable)
        if topmost:
            self.window.attributes("-topmost", True)
        if geometry:
            self.window.geometry(geometry)
        self.window.transient(self.parent)
        self.apply_icon()
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def apply_icon(self):
        """Set the window icon, from inside a Tk callback so errors are caught."""
        IconManager.apply_to_window(self.window)

    def show(self, delay=50):
        """Deiconify and centre the window after Tk has laid it out.

        A single ``deiconify`` is not enough: on Windows, CustomTkinter runs its
        own titlebar-colour pass whenever the window first becomes visible
        (``CTkToplevel._windows_set_titlebar_color``), which withdraws the window
        and re-shows it a few milliseconds later.  When its restore races with
        ours the window is left hidden, which looked like the help window
        "opening and closing immediately".  Re-asserting the visible state after
        that pass has finished makes the outcome deterministic.
        """
        self.window.after(delay, self._reveal)
        self.window.after(delay + REVEAL_REASSERT_DELAY_MS, self._assert_visible)

    def _assert_visible(self):
        """Idempotently make sure the window is on screen and centred."""
        try:
            if not self.window.winfo_exists():
                return
            if self.window.state() != "normal":
                self.window.deiconify()
            if self.window.state() == "normal" and self.window.winfo_x() <= 0 and self.window.winfo_y() <= 0:
                self.center()
        except Exception as error:  # pragma: no cover - defensive
            logger.debug("Could not re-assert visibility of %s: %s", self.window_name, error)

    def _reveal(self):
        try:
            self.window.deiconify()
            self.center()
            self.on_shown()
        except Exception as error:  # pragma: no cover - defensive
            logger.warning("Could not show %s: %s", self.window_name, error)
        finally:
            self._ready = True

    def on_shown(self):
        """Hook for subclasses that need to run code once the window is visible."""

    # ------------------------------------------------------------------- geometry

    def center(self):
        """Centre the window over its parent, clamped to the parent's monitor."""
        self.window.update_idletasks()
        self.parent.update_idletasks()

        width = self.window.winfo_width()
        height = self.window.winfo_height()
        if width <= 1 or height <= 1:
            width, height = self.default_size
            self.window.geometry(f"{width}x{height}")

        if not self.parent.winfo_viewable():
            x, y = center_on_monitor(width, height, enum_monitors())
        else:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            centre_x = parent_x + self.parent.winfo_width() // 2
            centre_y = parent_y + self.parent.winfo_height() // 2
            x = centre_x - width // 2
            y = centre_y - int(height / self.vertical_divisor)
            x, y = clamp_to_monitor(x, y, width, height, enum_monitors())

        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def resize_to_content(self):
        """Shrink/grow the window to fit its current contents, keeping the corner."""
        self.window.update_idletasks()
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        width = max(self.window.winfo_reqwidth(), 1)
        height = max(self.window.winfo_reqheight(), 1)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    # ---------------------------------------------------------------------- DPI

    def apply_dpi_scaling(self, delay=50):
        """Deprecated no-op.

        CustomTkinter's ``ScalingTracker`` rescales popups automatically when the
        monitor DPI changes, so setting ``tk scaling`` here only conflicted with
        it.  Kept so existing call sites keep working.
        """
        return None

    # ------------------------------------------------------------------- teardown

    def close(self):
        """Destroy the window and notify the owner (idempotent)."""
        callback = self.on_close
        self.on_close = None

        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception as error:
            logger.debug("Error destroying %s: %s", self.window_name, error)

        if callback:
            try:
                callback()
            except Exception as error:
                logger.warning("Close callback for %s failed: %s", self.window_name, error)
