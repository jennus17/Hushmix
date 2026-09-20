"""Windows display and single-instance helpers.

The monitor enumeration code previously existed in three slightly different
copies (``main.py``, ``window_manager.py`` and ``help_window.py``); it lives
here once so the behaviour cannot drift.
"""

import ctypes
from ctypes import wintypes

from utils.app_paths import single_instance_lock_file
from utils.logging_setup import get_logger

logger = get_logger("win_utils")

_MONITOR_DEFAULTTONEAREST = 2
_ERROR_ALREADY_EXISTS = 183
_ERROR_FILE_EXISTS = 17
_ERROR_SHARING_VIOLATION = 32


def enum_monitors():
    """Return a list of monitor rectangles as dicts."""
    monitors = []

    def _callback(monitor_handle, device_context, monitor_rect, data):
        rect = monitor_rect.contents
        monitors.append(
            {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
            }
        )
        return True

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(wintypes.RECT),
        ctypes.c_ulong,
    )

    try:
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, callback_type(_callback), 0
        )
    except Exception as error:  # pragma: no cover - defensive
        logger.warning("Could not enumerate monitors: %s", error)

    if not monitors:
        width = ctypes.windll.user32.GetSystemMetrics(0)
        height = ctypes.windll.user32.GetSystemMetrics(1)
        monitors.append(
            {
                "left": 0,
                "top": 0,
                "right": width,
                "bottom": height,
                "width": width,
                "height": height,
            }
        )

    return monitors


def find_monitor_for_position(x, y, monitors):
    """Return the monitor containing ``(x, y)`` or ``None``."""
    for monitor in monitors:
        if (
            monitor["left"] <= x <= monitor["right"]
            and monitor["top"] <= y <= monitor["bottom"]
        ):
            return monitor
    return None


def nearest_monitor(x, y, monitors):
    """Return the monitor whose centre is closest to ``(x, y)``."""
    if not monitors:
        return None

    best = monitors[0]
    best_distance = float("inf")
    for monitor in monitors:
        centre_x = monitor["left"] + monitor["width"] / 2
        centre_y = monitor["top"] + monitor["height"] / 2
        distance = (x - centre_x) ** 2 + (y - centre_y) ** 2
        if distance < best_distance:
            best_distance = distance
            best = monitor
    return best


def clamp_to_monitor(x, y, width, height, monitors):
    """Pull a window rectangle back onto a visible monitor.

    Returns ``(x, y)``.  When ``(x, y)`` is not inside any monitor the window
    is centred on the nearest one.
    """
    target = find_monitor_for_position(x, y, monitors)
    if target is None:
        target = nearest_monitor(x, y, monitors)

    if target is None:  # no monitor information at all
        return max(0, x), max(0, y)

    max_x = target["right"] - width
    max_y = target["bottom"] - height
    x = max(target["left"], min(x, max_x)) if max_x > target["left"] else target["left"]
    y = max(target["top"], min(y, max_y)) if max_y > target["top"] else target["top"]
    return x, y


def center_on_monitor(width, height, monitors, monitor=None):
    """Return ``(x, y)`` centring a window of the given size on a monitor."""
    target = monitor or (monitors[0] if monitors else None)
    if target is None:
        return 0, 0
    x = target["left"] + (target["width"] - width) // 2
    y = target["top"] + (target["height"] - height) // 2
    return x, y


def get_monitor_dpi(x, y):
    """Effective DPI scale factor (1.0 == 96 DPI) for the monitor at x, y."""
    try:
        handle = ctypes.windll.user32.MonitorFromPoint(
            wintypes.POINT(int(x), int(y)), _MONITOR_DEFAULTTONEAREST
        )
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        ctypes.windll.shcore.GetDpiForMonitor(
            handle, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
        )
        if dpi_x.value:
            return dpi_x.value / 96.0
    except Exception as error:  # pragma: no cover - defensive
        logger.debug("Could not read monitor DPI: %s", error)
    return 1.0


class SingleInstanceGuard:
    """Named-mutex based single-instance guard.

    Uses a kernel object rather than a PID file, so it is immune to the stale
    lock files (PID reuse, killed processes, temp cleaners) that the previous
    implementation tried to work around with a lot of fragile code.
    """

    MUTEX_NAME = "Hushmix_SingleInstance_Mutex"

    def __init__(self, name=None):
        self.name = name or self.MUTEX_NAME
        self._handle = None
        self.acquired = False

    def acquire(self):
        """Try to become the only running instance."""
        try:
            import win32api
            import win32event

            self._handle = win32event.CreateMutex(None, False, self.name)
            already_running = win32api.GetLastError() == _ERROR_ALREADY_EXISTS
            self.acquired = not already_running
            if already_running:
                logger.info("Another Hushmix instance is already running")
                self._close_handle()
            return self.acquired
        except Exception as error:
            logger.warning("Mutex single-instance check failed: %s", error)

        return self._acquire_file_lock()

    def _acquire_file_lock(self):
        """Fallback guard used when win32event is unavailable."""
        import os

        lock_file = single_instance_lock_file()
        try:
            handle = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(handle, "w") as stream:
                stream.write(str(os.getpid()))
            self.acquired = True
            return True
        except OSError as error:
            if error.errno == _ERROR_FILE_EXISTS or getattr(error, "winerror", None) == _ERROR_FILE_EXISTS:
                logger.info("Lock file %s already exists", lock_file)
                self.acquired = False
                return False
            logger.warning("Could not create lock file: %s", error)
            # Never block the user because of a filesystem hiccup.
            self.acquired = True
            return True

    def _close_handle(self):
        if self._handle:
            try:
                import win32api

                win32api.CloseHandle(self._handle)
            except Exception as error:  # pragma: no cover - defensive
                logger.debug("Could not close mutex handle: %s", error)
            finally:
                self._handle = None

    def release(self):
        """Release the guard (idempotent)."""
        self._close_handle()

        import os

        lock_file = single_instance_lock_file()
        try:
            if os.path.exists(lock_file):
                with open(lock_file, "r", encoding="utf-8") as stream:
                    owner = stream.read().strip()
                if not owner.isdigit() or int(owner) == os.getpid():
                    os.remove(lock_file)
        except OSError as error:
            if getattr(error, "winerror", None) == _ERROR_SHARING_VIOLATION:
                logger.debug("Lock file is in use, leaving it alone")
            else:
                logger.debug("Could not remove lock file: %s", error)

        self.acquired = False

    # Convenience aliases kept for readability at call sites.
    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc_info):
        self.release()
