"""Hushmix entry point.

The 400-line, five-levels-deep single-instance check was replaced by
:class:`utils.win_utils.SingleInstanceGuard`: a named mutex (plus a simple lock
file fallback) instead of PID files with stale-entry heuristics.  The window
geometry is now derived from the real requested size rather than
``winfo_width()`` on a withdrawn window, which always reported ``1x1`` and made
the saved-position clamp meaningless.
"""

import atexit
import os
import sys
import tkinter.messagebox as messagebox

# Make the application package importable no matter which directory the app was
# started from (double-clicked shortcut, Explorer, or a terminal elsewhere).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from utils.app_paths import settings_file
from utils.config_manager import ConfigManager
from utils.logging_setup import get_logger, setup_logging
from utils.win_utils import SingleInstanceGuard, center_on_monitor, clamp_to_monitor, enum_monitors

logger = get_logger("main")

APP_NAME = "Hushmix"


def _show_error(title, message, parent=None):
    """Show an error the user can actually see and dismiss.

    A plain ``messagebox.showerror`` during startup can open *behind* other
    windows (the app has no visible window yet), which looks exactly like the
    process hanging: the second instance of Hushmix sat waiting on an invisible
    modal dialog instead of exiting.  The box is now owned by a temporary
    topmost root window.
    """
    owner = parent
    temporary = None

    if owner is None:
        try:
            temporary = ctk.CTk()
            temporary.withdraw()
            temporary.attributes("-topmost", True)
            owner = temporary
        except Exception:
            temporary = None
            owner = None

    try:
        messagebox.showerror(title, message, parent=owner)
    except Exception:
        logger.error("%s: %s", title, message)
    finally:
        if temporary is not None:
            try:
                temporary.destroy()
            except Exception:
                pass


def _install_signal_handlers(guard):
    """Exit cleanly on SIGINT/SIGTERM (Windows only delivers SIGINT)."""
    import signal

    def _handler(signum, frame):
        logger.info("Received signal %s - shutting down", signum)
        guard.release()
        raise SystemExit(0)

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signal_number = getattr(signal, name, None)
        if signal_number is None:
            continue
        try:
            signal.signal(signal_number, _handler)
        except (ValueError, OSError, AttributeError):
            pass


def _initial_window_position(root, settings):
    """Compute the startup window position, clamped onto a real monitor."""
    root.update_idletasks()

    width = max(root.winfo_reqwidth(), 1)
    height = max(root.winfo_reqheight(), 1)

    monitors = enum_monitors()
    saved_x = settings.get("window_x")
    saved_y = settings.get("window_y")

    if saved_x is not None and saved_y is not None:
        return clamp_to_monitor(int(saved_x), int(saved_y), width, height, monitors)

    return center_on_monitor(width, height, monitors)


def main():
    setup_logging()

    try:
        ConfigManager.check_corrupted_files()
    except Exception as error:
        logger.warning("Settings check failed: %s", error)

    guard = SingleInstanceGuard()
    if not guard.acquire():
        logger.info("Another instance is already running - exiting")
        _show_error(
            APP_NAME,
            "Hushmix is already running!\n\n"
            "Please close the existing instance before opening a new one.",
        )
        # The guard was not acquired, so there is nothing to release.
        return 1

    atexit.register(guard.release)
    _install_signal_handlers(guard)

    settings = ConfigManager.load_settings()
    ctk.set_appearance_mode("dark" if settings.get("dark_mode", True) else "light")

    # Creating the CTk root also enables per-monitor DPI awareness; CustomTkinter
    # scales the widgets and the window as it moves between monitors, so nothing
    # here (and nothing in HushmixApp) sets `tk scaling` by hand.
    root = ctk.CTk()
    root.withdraw()

    from gui.app import HushmixApp

    try:
        position_x, position_y = _initial_window_position(root, settings)
        root.geometry(f"+{position_x}+{position_y}")

        app = HushmixApp(root)

        def show_window():
            if app.settings_manager.get_setting("launch_in_tray"):
                logger.info("Starting minimised to the tray")
                return
            root.deiconify()
            root.lift()
            root.attributes("-topmost", True)
            root.after_idle(lambda: root.attributes("-topmost", False))
            root.focus_force()

        root.after_idle(lambda: root.after(10, show_window))

        logger.info("Settings file: %s", settings_file())
        root.mainloop()
    except Exception as error:
        logger.exception("Fatal error: %s", error)
        _show_error(APP_NAME, f"Hushmix encountered a fatal error:\n\n{error}")
        return 1
    finally:
        guard.release()

    return 0


if __name__ == "__main__":
    sys.exit(main())
