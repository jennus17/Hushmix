"""Filesystem locations used by Hushmix.

Every path is absolute and independent of the current working directory so the
application behaves the same when started from a shortcut, from Explorer, or
from a terminal in an unrelated folder (and also when frozen with PyInstaller).
"""

import os
import sys


def is_frozen():
    """True when running from a packaged executable."""
    return bool(getattr(sys, "frozen", False))


def app_data_dir():
    """Writable per-user directory for settings and logs."""
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.expanduser("~")
    return os.path.join(base, "Hushmix")


def settings_file():
    """Path of the JSON settings file."""
    return os.path.join(app_data_dir(), "settings.json")


def log_file():
    """Path of the rotating log file."""
    from utils.log_path import resolve_log_file

    return resolve_log_file()[0]


def ensure_app_data_dir():
    """Create the writable application data directory.

    Called before the first write (settings or logs) so a fresh install cannot
    fail for a missing folder.
    """
    folder = app_data_dir()
    os.makedirs(folder, exist_ok=True)
    return folder


def resource_dir():
    """Directory that holds bundled read-only resources (``assets``)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def asset_path(*parts):
    """Absolute path of a bundled asset."""
    return os.path.join(resource_dir(), "assets", *parts)


def executable_path():
    """Path of Hushmix.exe (the frozen executable, or the dev convention)."""
    if is_frozen():
        return os.path.join(os.path.dirname(sys.executable), "Hushmix.exe")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "Hushmix.exe")


def startup_command():
    """Command line used for the Run-key auto-start entry."""
    if is_frozen():
        return f'"{sys.executable}"'
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return f'"{sys.executable}" "{script}"'


def temp_dir():
    """Directory for short-lived files."""
    import tempfile

    return tempfile.gettempdir()


def single_instance_lock_file():
    """Path of the single-instance lock file."""
    return os.path.join(temp_dir(), "hushmix_single_instance.lock")
