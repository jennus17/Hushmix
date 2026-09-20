"""Main window behaviour: icon, tray integration and position persistence.

**Scaling is left to CustomTkinter.**  It detects the DPI of the monitor a
window is on (``ScalingTracker``, polled every 100 ms) and rescales every widget
plus the window itself.  An earlier attempt to drive this manually - setting
``tk scaling`` on a ``<Configure>`` event and rebuilding the GUI - fought that
machinery: the window was resized from the scaled dimensions while the widgets
were rebuilt at the previous scale, so dragging the window to a 4K monitor made
it grow without its content keeping up.

The first ``<Configure>`` for a window is also reported for child widgets during
startup, so the manual path could fire a full GUI rebuild before the window had
a real size.
"""

import ctypes
import threading

from PIL import Image
from pystray import Icon, Menu, MenuItem

from utils.icon_manager import IconManager
from utils.logging_setup import get_logger
from utils.win_utils import enum_monitors, find_monitor_for_position

logger = get_logger("window_manager")

POSITION_SAVE_DELAY_MS = 400
APP_USER_MODEL_ID = "Hushmix"


class WindowManager:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.icon = None
        self.last_position = None

        self._position_save_job = None

        self.setup_window()
        self.setup_tray_icon()
        self.setup_window_position_tracking()

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

        ``<Configure>`` also fires when CustomTkinter rescales the window for a
        new monitor DPI.  That rescale re-runs ``_set_dimensions`` on every
        widget, and a widget can re-grid itself in the process - which is how the
        "Mixer Disconnected" banner used to reappear on a connected mixer after
        the window moved between monitors.  Re-applying the banner state here
        keeps it truthful no matter what rebuilt the layout.
        """
        if event.widget is not self.root:
            return

        self.app.update_connection_status()

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

    def clamp_position(self, x, y, width, height):
        """Deprecated: use :func:`utils.win_utils.clamp_to_monitor`."""
        from utils.win_utils import clamp_to_monitor

        return clamp_to_monitor(x, y, width, height, enum_monitors())

    # ----------------------------------------------------------------- cleanup

    def cleanup(self):
        """Stop the tray icon and cancel pending work (idempotent)."""
        if self._position_save_job is not None:
            try:
                self.root.after_cancel(self._position_save_job)
            except Exception:
                pass
            self._position_save_job = None

        icon = self.icon
        self.icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception as error:
                logger.debug("Error stopping the tray icon: %s", error)
