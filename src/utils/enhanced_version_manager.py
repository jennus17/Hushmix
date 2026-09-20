"""Update checking, downloading and installing.

Rewritten around four defects in the previous implementation:

* **The loop ignored the settings it was started with.**  ``auto_check_enabled``
  and ``check_interval`` were captured in ``__init__``, so turning automatic
  checks off (or changing the interval) had no effect until the next restart.
* **It touched Tk from a background thread.**  ``restore_parent_window`` and
  ``show_update_dialog`` called ``deiconify``/``lift``/widget constructors off
  the main thread.  All UI work is now marshalled with ``parent.after``.
* **It stopped checking after the first dialog.**  The loop ``break``-ed once an
  update was found, so skipping a version ended update checks for the session.
* **It compared versions with ``!=``.**  A local build newer than the latest
  release (or a tag written as ``1.2.0`` instead of ``v1.2.0``) prompted for a
  bogus "update".  Comparisons now use :mod:`utils.version_utils`.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import requests

from utils.app_paths import executable_path, is_frozen
from utils.logging_setup import get_logger
from utils.version_utils import compare_versions, normalize
from version import GITHUB_REPOSITORY, __version__

logger = get_logger("version_manager")

DOWNLOAD_CHUNK = 65536
REQUEST_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 30


class EnhancedVersionManager:
    """Checks for, downloads and installs Hushmix updates."""

    def __init__(self, parent, settings_manager):
        self.root = parent
        self.settings_manager = settings_manager

        repository = GITHUB_REPOSITORY
        self.update_sources = {
            "github": {
                "api_url": f"https://api.github.com/repos/{repository}/releases/latest",
                "download_base": f"https://github.com/{repository}/releases/download",
                "release_page": f"https://github.com/{repository}/releases/latest",
            },
            "custom_server": {
                "api_url": "https://your-update-server.com/api/version",
                "download_base": "https://your-update-server.com/downloads",
                "release_page": "https://your-update-server.com/releases",
            },
        }

        self.download_path = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread = None
        self._dialog_open = False
        self._skipped_versions = set()

        self.start_version_check_thread(parent)

    # ------------------------------------------------------------- version info

    @staticmethod
    def read_installed_version():
        """Version of the running build (PE resource, else ``version.__version__``)."""
        version = EnhancedVersionManager._read_version_from_exe()
        if version:
            return version
        return f"v{__version__}" if __version__ else None

    @staticmethod
    def _read_version_from_exe():
        """Read ``ProductVersion`` from Hushmix.exe, or ``None``."""
        if not is_frozen():
            return None

        path = executable_path()
        if not os.path.exists(path):
            return None

        try:
            import pefile
        except ImportError:
            logger.debug("pefile is unavailable - using the bundled version constant")
            return None

        try:
            pe = pefile.PE(path)
            for fileinfo in getattr(pe, "FileInfo", []) or []:
                for entry in fileinfo:
                    if getattr(entry, "Key", None) != b"StringFileInfo":
                        continue
                    for table in entry.StringTable:
                        raw = table.entries.get(b"ProductVersion")
                        if not raw:
                            continue
                        product_version = raw.decode("utf-8", errors="ignore").strip()
                        if product_version:
                            return f"v{normalize(product_version)}"
        except Exception as error:
            logger.warning("Error reading version from executable: %s", error)
        return None

    # ------------------------------------------------------------- update check

    def start_version_check_thread(self, parent):
        """Start the background update checker."""
        self._thread = threading.Thread(
            target=self._check_loop, name="update-checker", daemon=True
        )
        self._thread.start()

    def stop(self):
        """Ask the checker to stop (used on shutdown)."""
        self._stop_event.set()

    @property
    def can_auto_install(self):
        """Automatic install is only possible from a packaged build."""
        return is_frozen()

    @property
    def auto_check_enabled(self):
        """Current setting - re-read every cycle so the UI toggle takes effect."""
        return bool(self.settings_manager.get_setting("auto_check_updates", True))

    @property
    def check_interval(self):
        """Current interval in seconds, re-read every cycle."""
        try:
            return max(60, int(self.settings_manager.get_setting("update_check_interval", 1800)))
        except (TypeError, ValueError):
            return 1800

    def _check_loop(self):
        current_version = self.read_installed_version()
        if not current_version:
            logger.info("Update checks disabled: the installed version is unknown")
            return

        logger.info("Running version %s", current_version)

        while not self._stop_event.is_set():
            try:
                if not self.auto_check_enabled:
                    logger.debug("Automatic update checks are disabled")
                else:
                    self._check_once(current_version)
            except Exception as error:
                logger.warning("Error during update check: %s", error)

            self.settings_manager.set_setting("last_update_check", time.time())
            self._wait_for_next_cycle()

    def _wait_for_next_cycle(self):
        """Sleep until the interval elapses, a setting changes, or we stop."""
        deadline = time.monotonic() + self.check_interval
        while not self._stop_event.is_set():
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                return
            # Either event wakes the wait; both are cleared before waiting.
            self._wake_event.wait(min(timeout, 1.0))
            if self._wake_event.is_set():
                self._wake_event.clear()
                return

    def _check_once(self, current_version):
        """Query the configured source once and offer an update if appropriate."""
        skip_version = self.settings_manager.get_setting("skip_version")
        source = self.settings_manager.get_setting("update_source", "github")

        update_info = self.get_update_info(source)
        if not update_info or not update_info.get("version"):
            return

        latest = update_info["version"]

        if skip_version and normalize(skip_version) == normalize(latest):
            logger.debug("Version %s was skipped by the user", latest)
            return

        if latest in self._skipped_versions:
            return

        if compare_versions(latest, current_version) <= 0:
            logger.debug(
                "Up to date: local %s, latest %s", current_version, latest
            )
            return

        logger.info("Update available: local %s, latest %s", current_version, latest)
        self._on_main_thread(self._offer_update, update_info)

    def get_update_info(self, source="github"):
        """Fetch update metadata from *source*."""
        source_config = self.update_sources.get(source)
        if not source_config:
            logger.warning("Unknown update source: %s", source)
            return None

        try:
            response = requests.get(
                source_config["api_url"],
                timeout=REQUEST_TIMEOUT,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"Hushmix/{__version__}",
                },
            )
            if response.status_code == 404:
                # No releases published yet - not an error worth warning about.
                logger.debug("No releases found at %s", source_config["api_url"])
                return None

            response.raise_for_status()
            if source == "github":
                return self._parse_github_response(response.json())
            if source == "custom_server":
                return self._parse_custom_response(response.json())
        except requests.RequestException as error:
            logger.warning("Error checking for updates from %s: %s", source, error)
        except ValueError as error:
            logger.warning("Malformed update response from %s: %s", source, error)

        return None

    def _parse_github_response(self, data):
        tag = data.get("tag_name")
        if not tag:
            return None

        asset_url = None
        for asset in data.get("assets", []) or []:
            if str(asset.get("name", "")).lower() == "hushmix.exe":
                asset_url = asset.get("browser_download_url")
                break

        base = self.update_sources["github"]["download_base"]
        return {
            "version": tag,
            "download_url": asset_url or f"{base}/{tag}/Hushmix.exe",
            "release_notes": data.get("body", "") or "",
            "published_at": data.get("published_at", "") or "",
            "release_page": data.get("html_url")
            or self.update_sources["github"]["release_page"],
            "size": None,
            "checksum": None,
        }

    def _parse_custom_response(self, data):
        return {
            "version": data.get("version"),
            "download_url": data.get("download_url"),
            "release_notes": data.get("release_notes", ""),
            "published_at": data.get("published_at", ""),
            "release_page": data.get("release_page", self.update_sources["custom_server"]["release_page"]),
            "size": data.get("size"),
            "checksum": data.get("checksum"),
        }

    # ------------------------------------------------------------- UI hand-off

    def _on_main_thread(self, function, *args):
        """Run *function* on the Tk main thread."""
        if self._stop_event.is_set():
            return
        try:
            self.root.after(0, lambda: function(*args))
        except Exception as error:
            logger.debug("Could not schedule UI work: %s", error)

    def _offer_update(self, update_info):
        """Show the update window (main thread only)."""
        if self._dialog_open:
            return
        self._dialog_open = True

        try:
            if not self.root.winfo_viewable():
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
        except Exception as error:
            logger.debug("Could not restore the main window: %s", error)

        from gui.version_window import VersionWindow

        VersionWindow(
            update_info["version"],
            self.root,
            update_info,
            self,
            self.settings_manager,
            on_close=self._on_dialog_closed,
        )

    def _on_dialog_closed(self):
        self._dialog_open = False

    # --------------------------------------------------------------- downloads

    def download_update(self, download_url, progress_callback=None, cancellation_check=None):
        """Download the new executable; returns the temp path or ``None``."""
        temp_path = None
        try:
            with requests.get(
                download_url, stream=True, timeout=DOWNLOAD_TIMEOUT
            ) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0) or 0)
                downloaded = 0

                handle, temp_path = tempfile.mkstemp(prefix="hushmix_update_", suffix=".exe")
                with os.fdopen(handle, "wb") as stream:
                    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK):
                        if cancellation_check and cancellation_check():
                            raise DownloadCancelled()

                        if not chunk:
                            continue

                        stream.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress_callback(min(100.0, downloaded / total_size * 100))

            self.download_path = temp_path
            logger.info("Downloaded update to %s (%d bytes)", temp_path, downloaded)
            return temp_path

        except DownloadCancelled:
            logger.info("Update download cancelled by the user")
            self._remove_quietly(temp_path)
            return None
        except Exception as error:
            logger.warning("Error downloading update: %s", error)
            self._remove_quietly(temp_path)
            return None

    @staticmethod
    def _remove_quietly(path):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as error:
                logger.debug("Could not remove %s: %s", path, error)

    def verify_download(self, file_path, expected_checksum=None):
        """Verify the SHA-256 of a download when a checksum is published."""
        if not expected_checksum:
            # No checksum available: at least require a plausible executable.
            return self._looks_like_executable(file_path)

        try:
            digest = hashlib.sha256()
            with open(file_path, "rb") as stream:
                for block in iter(lambda: stream.read(DOWNLOAD_CHUNK), b""):
                    digest.update(block)
            return digest.hexdigest().lower() == str(expected_checksum).lower()
        except Exception as error:
            logger.warning("Error verifying download: %s", error)
            return False

    @staticmethod
    def _looks_like_executable(file_path, minimum_size=64 * 1024):
        try:
            if not os.path.exists(file_path) or os.path.getsize(file_path) < minimum_size:
                return False
            with open(file_path, "rb") as stream:
                return stream.read(2) == b"MZ"
        except OSError:
            return False

    # --------------------------------------------------------------- installing

    def install_update(self, installer_path):
        """Replace the running executable and restart it.

        Only meaningful for a frozen build; running from source returns
        ``False`` so the caller can offer the manual download instead.
        """
        if not is_frozen():
            logger.info("Automatic install is unavailable in a development checkout")
            return False

        if not os.path.exists(installer_path):
            logger.warning("Installer %s does not exist", installer_path)
            return False

        try:
            target = sys.executable
            backup = f"{target}.backup"
            batch_path = os.path.join(tempfile.gettempdir(), "hushmix_update.bat")
            batch_source = os.path.join(tempfile.gettempdir(), "hushmix_update_src.exe")

            # The temp file must live next to the target for the copy to be a
            # cheap, same-volume operation.
            shutil.copy2(installer_path, batch_source)

            with open(batch_path, "w", encoding="utf-8") as stream:
                stream.write(self._build_update_script(target, backup, batch_source))

            subprocess.Popen(
                ["cmd", "/c", batch_path],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                close_fds=True,
            )
            logger.info("Update script launched; exiting to let it replace the binary")
            os._exit(0)

        except Exception as error:
            logger.exception("Error installing update: %s", error)
            return False

    @staticmethod
    def _build_update_script(target, backup, source):
        """Windows batch script that swaps the binary once we exit."""
        return f"""@echo off
setlocal
echo Updating Hushmix...

REM Wait for the running instance to exit (up to ~15 seconds)
for /L %%i in (1,1,30) do (
    tasklist /fi "imagename eq {os.path.basename(target)}" 2>nul | find /i "{os.path.basename(target)}" >nul
    if errorlevel 1 goto :gone
    timeout /t 1 /nobreak > nul
)
echo Hushmix did not exit; aborting the update.
del "{source}" 2>nul
del "%~f0" 2>nul
exit /b 1

:gone
if exist "{backup}" del "{backup}"
copy /Y "{target}" "{backup}" >nul

copy /Y "{source}" "{target}" >nul
if errorlevel 1 goto :failed

start "" "{target}"
timeout /t 2 /nobreak > nul
del "{source}" 2>nul
if exist "{backup}" del "{backup}" 2>nul
del "%~f0" 2>nul
exit /b 0

:failed
echo Update failed - restoring the previous version.
if exist "{backup}" copy /Y "{backup}" "{target}" >nul
start "" "{target}"
del "{source}" 2>nul
del "%~f0" 2>nul
exit /b 1
"""

    # -------------------------------------------------------------- preferences

    def set_check_interval(self, seconds):
        """Store the check interval and apply it immediately."""
        try:
            seconds = max(60, int(seconds))
        except (TypeError, ValueError):
            return
        self.settings_manager.set_setting("update_check_interval", seconds)
        self._wake()

    def set_auto_check(self, enabled):
        """Enable or disable automatic checks immediately."""
        self.settings_manager.set_setting("auto_check_updates", bool(enabled))
        self._wake()

    def _wake(self):
        """Interrupt the idle wait so a changed setting takes effect now."""
        self._wake_event.set()

    def set_update_source(self, source):
        """Switch between built-in update sources."""
        if source not in self.update_sources:
            raise ValueError(f"Unknown update source: {source}")
        self.settings_manager.set_setting("update_source", source)

    def skip_version(self, version):
        """Do not offer *version* again in this session."""
        if version:
            self._skipped_versions.add(version)
        self.settings_manager.set_setting("skip_version", version)


class DownloadCancelled(Exception):
    """Raised internally when the user cancels a download."""
