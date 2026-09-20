"""Main window behaviour: icon, tray integration, DPI and position persistence.

**Scaling.**  CustomTkinter has two scaling factors and they conflict here:

* ``window_scaling`` is fed into ``CTk.geometry()`` via
  ``_apply_geometry_scaling``, so a request for "670x573" is turned into
  "1172x1002"; ``CTk.geometry`` then records the *unscaled* number as its cached
  size while the window really is the scaled size.  Yet another pass re-reads
  the real size and records that.  On a non-resizable window the resulting
  ``minsize``/``maxsize`` pins the window: measurements showed the window locked
  at 1172x1002 while the content wanted 670x573, and ``geometry`` was ignored
  completely afterwards - which is the deformation users see.
* ``widget_scaling`` scales every CustomTkinter widget, and it composes
  correctly: the frame's requested size doubles as the factor doubles.

So ``window_scaling`` is pinned to 1.0 and the DPI factor is applied as
``widget_scaling`` only.  Tk's own geometry is then the single source of truth
for the window rectangle, and because the window auto-sizes to its content it
grows and shrinks with the widgets - measured stable across 1.0 -> 1.75 -> 1.0
with the window and frame request always equal.
"""

import ctypes
import threading
import time
import tkinter as tk

from PIL import Image
from pystray import Icon, Menu, MenuItem

from utils.icon_manager import IconManager
from utils.logging_setup import get_logger
from utils.win_utils import enum_monitors, find_monitor_for_position, get_monitor_dpi

logger = get_logger("window_manager")

POSITION_SAVE_DELAY_MS = 400
#: How often to look for a monitor DPI change (ms).
DPI_POLL_MS = 500
#: Ignore tiny differences when comparing the window to its content.
FIT_TOLERANCE = 2
#: Delay before re-running a content fit that was requested while one was active.
FIT_RETRY_MS = 30
#: Hard floor between two content fits (seconds): a resize must never be able to
#: schedule the next one immediately, or the correction loops forever.
FIT_MIN_INTERVAL = 0.4
#: Passes allowed in one fit before giving up (the layout can lag a resize).
FIT_MAX_PASSES = 4
APP_USER_MODEL_ID = "Hushmix"


class WindowManager:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.icon = None
        self.last_position = None

        self._position_save_job = None
        self._dpi_job = None
        self._fit_job = None
        self._last_dpi = None
        self._fitting = False
        self._fit_again = False
        self._last_fit = 0.0

        self.use_content_sized_window()
        self.setup_window()
        self.setup_tray_icon()
        self.setup_window_position_tracking()
        self.start_dpi_watch()

    # ----------------------------------------------------------------- scaling

    def use_content_sized_window(self):
        """Take over DPI *window* handling, leaving widget scaling to CustomTkinter.

        ``ScalingTracker.update_scaling_callbacks_for_window`` applies
        ``window_dpi_scaling_dict[window] * widget_scaling`` to every widget, so
        calling ``set_widget_scaling(1.75)`` on a 175% monitor produced 3.06 -
        the factor was multiplied in twice.  Widget scaling therefore stays at
        1.0 and CustomTkinter's own detection drives it, which it does correctly.

        What it also does is resize the window: ``CTk._set_scaling`` applies
        ``_current_width`` through ``geometry()``, and ``geometry()`` multiplies
        its argument by the window scaling.  With automatic DPI awareness
        deactivated the tracker passes its fixed factors, so that resize stops and
        this class owns the window rectangle.
        """
        try:
            import customtkinter as ctk

            # Must happen after the CTk root exists: creating it is what sets
            # per-monitor DPI awareness for the process.  Only the *window*
            # rescaling is disabled; the tracker still scales every widget to the
            # detected DPI, which is the part it does correctly.
            self._tracker = ctk.ScalingTracker
            self._window_rescale_disabled = self._disable_window_rescaling()
            logger.debug(
                "CustomTkinter window rescaling disabled (%s); window sizing is in-app",
                self._window_rescale_disabled,
            )
        except Exception as error:
            logger.debug("Could not take over window sizing: %s", error)
            self._tracker = None

    def _disable_window_rescaling(self):
        """Stop CustomTkinter resizing the window, without losing widget scaling.

        Setting ``deactivate_automatic_dpi_awareness`` makes the tracker pass its
        fixed factors instead of the detected DPI, which also freezes widget
        scaling - so the CTk window entry is given a callback that only keeps its
        own scaling factors up to date and never touches the geometry.  Removing
        the entry outright is not an option: it holds the widget callbacks too.
        """
        try:
            import customtkinter as ctk

            tracker = ctk.ScalingTracker
            callbacks = tracker.window_widgets_dict.get(self.root)
            if not callbacks:
                return False

            def _scaling_only(new_widget_scaling, new_window_scaling):
                from customtkinter.windows.widgets.scaling.scaling_base_class import (
                    CTkScalingBaseClass,
                )

                CTkScalingBaseClass._set_scaling(
                    self.root, new_widget_scaling, new_window_scaling
                )

            # Replace only the window's own callback (the last one registered for
            # this window); the widget callbacks must keep working.
            callbacks[-1] = _scaling_only
            return True
        except Exception as error:
            logger.debug("Could not disable window rescaling: %s", error)
            return False

    def _set_geometry_pixels(self, width, height):
        """Resize the window with the size taken literally.

        ``CTk.geometry()`` runs the string through ``_apply_geometry_scaling``,
        which multiplied an already-correct "670x573" into "1172x1002" while the
        widget scaling was 1.75.  The plain tkinter ``Wm.geometry`` bypasses that
        and sets exact pixels.
        """
        try:
            tk.Wm.geometry(self.root, f"{int(width)}x{int(height)}")
        except Exception as error:
            logger.debug("Raw geometry failed (%s); falling back", error)
            self.root.geometry(f"{int(width)}x{int(height)}")

    def current_monitor_scale(self):
        """DPI scale factor of the monitor the window is on."""
        try:
            return get_monitor_dpi(self.root.winfo_x(), self.root.winfo_y())
        except Exception:
            return 1.0

    def start_dpi_watch(self):
        """Apply the monitor DPI to the widgets, and keep watching for changes.

        CustomTkinter's own tracker is left enabled (it sets per-monitor DPI
        awareness for the process); we only take over applying the *window*
        geometry it would otherwise fight us over.
        """
        self.apply_monitor_scale()
        self._schedule_dpi_poll()

    def _schedule_dpi_poll(self):
        try:
            self._dpi_job = self.root.after(DPI_POLL_MS, self._poll_dpi)
        except Exception as error:
            logger.debug("Could not schedule the DPI poll: %s", error)

    def _poll_dpi(self):
        self._dpi_job = None
        if getattr(self.app, "_shutting_down", False):
            return
        self.apply_monitor_scale()
        self._schedule_dpi_poll()

    def apply_monitor_scale(self):
        """Match widget scaling to the monitor the window is on.

        Only runs when the monitor scale actually changed: forcing the content fit
        on every poll would resize the window continuously.
        """
        return self._apply_scale(self.current_monitor_scale(), force_fit=False)
    def _apply_scale(self, scale, force_fit=False):
        try:
            if not force_fit and self._last_dpi is not None and abs(scale - self._last_dpi) < 0.01:
                return scale

            self._last_dpi = scale

            # Widgets are scaled by CustomTkinter's own DPI detection; this class
            # only has to make the window match the result.
            self.fit_window_to_content(force=True)
            logger.info("Monitor scale %.2f applied to the window", scale)
            return scale
        except Exception as error:
            logger.debug("Could not apply the monitor scale: %s", error)
            return None

    def _widget_scaling(self):
        """Widget scaling CustomTkinter is currently using."""
        try:
            frame = getattr(getattr(self.app, "gui_components", None), "main_frame", None)
            if frame is not None:
                return float(frame._get_widget_scaling())
        except Exception:
            pass
        try:
            import customtkinter as ctk

            return float(ctk.ScalingTracker.widget_scaling)
        except Exception:
            return 1.0

    def fit_window_to_content(self, force=False):
        """Grow or shrink the window so its content fills it exactly.

        Re-entrancy is collapsed, the correction is debounced, and a hard rate
        limit means a resize can never schedule another resize immediately.  All
        three are needed: ``<Configure>`` fires for the resizes this method makes,
        and an earlier version fed itself until the event queue stopped draining
        and the application froze.
        """
        now = time.monotonic()
        if not force and (now - self._last_fit) < FIT_MIN_INTERVAL:
            self._fit_again = True
            return

        if self._fitting:
            self._fit_again = True
            return

        self._fitting = True
        try:
            self._fit_window_to_content(force)
        finally:
            self._fitting = False
            self._last_fit = time.monotonic()
            if self._fit_again:
                self._fit_again = False
                self.schedule_content_fit()

    def schedule_content_fit(self, delay=FIT_RETRY_MS):
        """Re-run the content fit shortly, collapsing repeated requests."""
        try:
            if getattr(self, "_fit_job", None) is not None:
                self.root.after_cancel(self._fit_job)
            self._fit_job = self.root.after(delay, self._run_scheduled_fit)
        except Exception as error:
            logger.debug("Could not schedule a content fit: %s", error)

    def _run_scheduled_fit(self):
        self._fit_job = None
        if getattr(self.app, "_shutting_down", False):
            return
        # Never force from here: a forced fit always resizes, which fires another
        # <Configure> and would schedule the next forced fit.
        self.fit_window_to_content(force=False)

    def _fit_window_to_content(self, force):
        """Resize the window to its content, repeating until it matches.

        A single pass is not reliable: reading the frame's request immediately
        after a resize can still report the previous layout, which left the
        window one step behind (the reported window height was consistently the
        *previous* content height).  Looping to a tolerance converges.
        """
        for attempt in range(FIT_MAX_PASSES):
            if not self.root.winfo_exists() or getattr(self.app, "_shutting_down", False):
                return

            widgets = getattr(self.app, "gui_components", None)
            frame = getattr(widgets, "main_frame", None)
            if frame is None:
                return

            self.root.update_idletasks()
            self.root.update()

            # The window does not follow its content on its own (it stays at
            # CustomTkinter's 600x500 default), so it is sized explicitly.  The
            # frame's requested size is already in the pixels the window should
            # have: CustomTkinter scales the widgets, so the request grows with
            # the DPI, and ``winfo_width`` reports in the same units - no extra
            # multiplication is applied on either side.
            wanted = (
                max(int(frame.winfo_reqwidth()), 1),
                max(int(frame.winfo_reqheight()), 1),
            )
            current = (self.root.winfo_width(), self.root.winfo_height())

            if self._within_tolerance(current, wanted):
                if attempt > 0 or not force:
                    return

            # Clear any previous pinning *before* resizing: minsize/maxsize
            # re-apply the old size and would undo the resize.
            self._keep_ctk_in_step(wanted)
            self._set_geometry_pixels(*wanted)
            logger.debug(
                "Fitted the window to its content (pass %d): %sx%s (was %sx%s)",
                attempt + 1, wanted[0], wanted[1], current[0], current[1],
            )

    def scaling_report(self):
        """Current scaling factors, for the help window's diagnostics.

        A "the window looks wrong" report is otherwise impossible to reason about
        without this: it shows what the monitor reports, what CustomTkinter is
        scaling the widgets by, and what the window ended up as.
        """
        frame = getattr(getattr(self.app, "gui_components", None), "main_frame", None)
        window_scale = 1.0
        try:
            import customtkinter as ctk

            window_scale = float(ctk.ScalingTracker.get_window_scaling(self.root))
        except Exception:
            pass

        return {
            "monitor_scale": self.current_monitor_scale(),
            "widget_scale": self._widget_scaling(),
            "window_scale": window_scale,
            "window": (self.root.winfo_width(), self.root.winfo_height()),
            "content": (
                (frame.winfo_reqwidth(), frame.winfo_reqheight()) if frame else None
            ),
        }

    @staticmethod
    def _within_tolerance(current, expected):
        return (
            abs(current[0] - expected[0]) <= FIT_TOLERANCE
            and abs(current[1] - expected[1]) <= FIT_TOLERANCE
        )

    def _keep_ctk_in_step(self, logical):
        """Realign CustomTkinter's cached size with the logical content size.

        ``CTk._set_scaling`` derives the window size from ``_current_width`` and
        re-applies it through ``minsize``/``maxsize``.  Leaving a stale 600x500
        there is what made the window stay at the wrong size and grow on every
        monitor change.  The min/max are cleared rather than pinned: pinning them
        to the current size stops the window resizing when the DPI changes.
        """
        try:
            width, height = logical
            self.root._current_width = width
            self.root._current_height = height
            self.root._min_width = width
            self.root._min_height = height
            self.root._max_width = width
            self.root._max_height = height
            self.root.minsize(1, 1)
            self.root.maxsize(0, 0)
        except Exception as error:
            logger.debug("Could not realign CustomTkinter's size cache: %s", error)

    # ------------------------------------------------------------------ window

    def setup_window(self):
        """Apply the main window properties and icon."""
        self.root.title("Hushmix")
        self.root.resizable(False, False)
        self.root.configure(bg=self.get_theme_bg_color())

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
        except Exception as error:
            logger.debug("Could not set the AppUserModelID: %s", error)

        IconManager.apply_to_window(self.root)

    def get_theme_bg_color(self):
        """Background colour matching the active theme."""
        try:
            if self.app.settings_manager.get_setting("dark_mode", True):
                return "#2b2b2b"
            return "#f0f0f0"
        except Exception:
            return "#2b2b2b"

    # -------------------------------------------------------------------- tray

    def setup_tray_icon(self):
        """Create the system tray icon and run it on its own thread."""
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_close)

        image = IconManager.get_icon_image(size=64)
        if image is None:
            image = Image.new("RGBA", (64, 64), (33, 150, 243, 255))
            logger.warning("Using a placeholder tray icon")

        menu = Menu(
            MenuItem("Restore", self.restore_window, default=True),
            MenuItem("Settings", self.app.show_settings),
            MenuItem("Exit", self.app.on_exit),
        )

        try:
            self.icon = Icon("Hushmix", icon=image, menu=menu, title="Hushmix")
        except Exception as error:
            logger.warning("Could not create the tray icon: %s", error)
            self.icon = None
            return

        thread = threading.Thread(
            target=self._run_tray_icon, name="tray-icon", daemon=True
        )
        thread.start()

    def _run_tray_icon(self):
        try:
            self.icon.run_detached()
        except Exception as error:
            logger.warning("Tray icon stopped: %s", error)
            self.icon = None

    def restore_window(self, icon=None, item=None):
        """Bring the main window back from the tray or the taskbar."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after_idle(lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception as error:
            logger.warning("Could not restore the window: %s", error)

    # ----------------------------------------------------------------- position

    def setup_window_position_tracking(self):
        """Persist the window position without writing on every frame."""
        self.last_position = None
        self.root.bind("<Configure>", self.on_window_configure)

    def on_window_configure(self, event):
        """Track moves, persist later, and re-assert widget state.

        Deliberately does *no* resizing.  ``<Configure>`` fires for every
        geometry change, including the ones this class makes, so fitting the
        window from here fed itself: each resize produced another event, the
        queue never drained, and the application froze as soon as the window
        moved to a monitor with a different DPI.  Scaling changes are detected by
        the DPI poll instead, which runs at a bounded rate.

        ``<Configure>`` also fires when a widget re-grids itself during
        CustomTkinter's rescale - which is how the "Mixer Disconnected" banner
        used to reappear on a connected mixer - so the banner state is re-applied
        here.
        """
        if event.widget is not self.root:
            return

        # Re-assert the banner state first: re-gridding it changes the frame's
        # requested height, and fitting the window before that settles leaves the
        # window sized for a banner that is then hidden.
        self.app.update_connection_status()

        # Then re-measure on the next idle pass, once any re-grid has been
        # processed.  The fit itself is debounced and rate limited, so the resize
        # it performs cannot feed itself.
        self.schedule_content_fit()

        position = (event.x, event.y)
        if position == self.last_position:
            return
        self.last_position = position

        self.schedule_position_save()

    def schedule_position_save(self):
        """Debounce window-position writes (fires 400 ms after the last move)."""
        if self._position_save_job is not None:
            try:
                self.root.after_cancel(self._position_save_job)
            except Exception:
                pass

        self._position_save_job = self.root.after(
            POSITION_SAVE_DELAY_MS, self.save_window_position
        )

    def save_window_position(self):
        """Store the window position when it is visible on a monitor."""
        self._position_save_job = None
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()

            if find_monitor_for_position(x, y, enum_monitors()) is None:
                logger.debug("Window is off-screen (%d, %d) - not saving", x, y)
                return

            self.app.settings_manager.set_setting("window_x", x)
            self.app.settings_manager.set_setting("window_y", y)
            self.app.settings_manager.save_to_config()
        except Exception as error:
            logger.warning("Error saving window position: %s", error)

    # ----------------------------------------------------------------- cleanup

    def cleanup(self):
        """Stop the tray icon and cancel pending work (idempotent)."""
        for attribute in ("_position_save_job", "_dpi_job", "_fit_job"):
            job = getattr(self, attribute, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attribute, None)

        icon = self.icon
        self.icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception as error:
                logger.debug("Error stopping the tray icon: %s", error)
