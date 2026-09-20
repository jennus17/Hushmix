"""Core Audio control (master volume, microphone, per-application sessions).

Important threading note: this object is used from both the Tk main thread and
the serial reader thread.  COM interfaces belong to the apartment that created
them, so every piece of COM state is kept in thread-local storage.  The previous
version stored ``self.volume`` / ``self.devices`` on the shared instance, which
meant the serial thread could overwrite the interface the main thread was using
(or vice versa) and produce sporadic ``COMError`` failures.

The session list and endpoint volume interface are also cached: the old code
called ``AudioUtilities.GetSpeakers()`` on *every* volume change, which is an
expensive Core Audio round-trip on a path that runs dozens of times per second.
"""

import time
from threading import Lock, local

import psutil
import pythoncom
import win32.win32gui as win32gui
import win32.win32process as win32process
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

from utils.logging_setup import get_logger

logger = get_logger("audio_controller")

SESSION_CACHE_SECONDS = 2.0


class AudioController:
    """Singleton wrapper around the Windows Core Audio API."""

    _instance = None
    _instance_lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._local = local()
        self._lock = Lock()
        self._ensure_thread_state()

    # --------------------------------------------------------------- internals

    def _ensure_thread_state(self):
        """Initialise COM and the per-thread caches for the calling thread."""
        state = self._local
        if getattr(state, "ready", False):
            return state

        pythoncom.CoInitialize()
        state.ready = True
        state.initialized_com = True
        state.devices = None
        state.volume = None
        state.sessions = None
        state.sessions_at = 0.0
        return state

    @property
    def _state(self):
        return self._ensure_thread_state()

    def _get_sessions(self, max_age=SESSION_CACHE_SECONDS):
        """Cached ``AudioUtilities.GetAllSessions()``."""
        state = self._state
        now = time.time()
        if state.sessions is None or (now - state.sessions_at) > max_age:
            # The lock keeps the main and serial threads from enumerating at once.
            with self._lock:
                now = time.time()
                if state.sessions is None or (now - state.sessions_at) > max_age:
                    state.sessions = AudioUtilities.GetAllSessions()
                    state.sessions_at = now
        return state.sessions

    @staticmethod
    def _endpoint_volume_from_device(device):
        """Return an ``IAudioEndpointVolume`` for a device object.

        ``AudioUtilities.GetSpeakers()`` changed shape between pycaw releases:
        current versions return an ``AudioDevice`` wrapper exposing an
        ``EndpointVolume`` property, while older ones returned the ``IMMDevice``
        itself, which has to be ``Activate``-d.  Supporting both keeps the app
        working on either, instead of failing with
        ``'AudioDevice' object has no attribute 'Activate'``.
        """
        endpoint = getattr(device, "EndpointVolume", None)
        if endpoint is not None:
            return endpoint

        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)

    def _get_endpoint_volume(self):
        """The default playback endpoint volume interface for this thread."""
        state = self._state
        if state.volume is None:
            state.devices = AudioUtilities.GetSpeakers()
            state.volume = self._endpoint_volume_from_device(state.devices)
        return state.volume

    def _reset_endpoint(self):
        """Drop the cached endpoint so the next call re-activates it.

        Called when a Core Audio call fails, which usually means the default
        playback device changed or was removed.
        """
        state = self._state
        state.volume = None
        state.devices = None

    @staticmethod
    def _session_process_name(session):
        process = getattr(session, "Process", None)
        if not process:
            return None
        try:
            return process.name()
        except Exception:
            return None

    @staticmethod
    def get_current_process_name():
        """Name of the process owning the foreground window, or ``None``."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if not process_id:
                return None
            return psutil.Process(process_id).name()
        except Exception as error:
            logger.debug("Could not resolve the focused process: %s", error)
            return None

    def _iter_targets(self, app_name):
        """Yield ``(kind, session)`` candidates for a target name.

        ``kind`` is ``"system"`` for the system-sounds session, otherwise
        ``"app"``.  Lookup is a plain substring match, as before, but the first
        exact (case-insensitive) match wins so "spotify" no longer accidentally
        binds to "spotifyhelper" when both are playing.
        """
        lowered = app_name.lower()
        exact = []
        partial = []

        for session in self._get_sessions():
            if session.ProcessId == 0:
                if lowered == "system":
                    yield "system", session
                continue

            name = self._session_process_name(session)
            if not name:
                continue
            name_lower = name.lower()
            if name_lower == lowered:
                exact.append(session)
            elif lowered in name_lower:
                partial.append(session)

        for session in exact:
            yield "app", session
        for session in partial:
            yield "app", session

    @staticmethod
    def _get_session_volume(session):
        return session._ctl.QueryInterface(ISimpleAudioVolume)

    def _set_session_volume(self, session, level):
        volume = self._get_session_volume(session)
        volume.SetMasterVolume(max(0.0, min(1.0, level / 100.0)), None)
        return True

    # ------------------------------------------------------------------- public

    @staticmethod
    def resolve_lanes(app_names, focused_process=None):
        """Decide which lane controls what.

        Returns ``(resolved, claimed)`` where *resolved* maps a lane index to the
        target that lane should apply (``None`` when nothing matched) and
        *claimed* maps a lowercased process name to the lane index that controls
        it explicitly.

        This exists so the ``current`` lane cannot hijack an application that a
        named lane already owns: with ``App 1 = firefox`` and
        ``App 2 = current``, focusing Firefox must leave it under App 1 and do
        nothing for App 2.  Previously every packet wrote the focused
        application through *both* lanes, so the two sliders fought over it.
        """
        names = [str(name).strip() for name in (app_names or [])]
        special = {"", "master", "mic", "system", "current"}

        resolved = [""] * len(names)
        claimed = {}

        # Pass 1: special targets, and record which processes named lanes own.
        for index, name in enumerate(names):
            lowered = name.lower()
            if not name or lowered == "current":
                continue

            resolved[index] = name
            if lowered in special:  # master / mic / system
                continue

            # A lane naming several applications owns all of them.
            for token in (part.strip().lower() for part in name.split(",")):
                if token and token not in special:
                    claimed.setdefault(token, index)

        # Pass 2: the ``current`` lane, unless a named lane already owns the
        # focused application.
        focused = (focused_process or "").lower()
        for index, name in enumerate(names):
            if name.lower() != "current":
                continue

            if not focused or focused in claimed:
                continue

            # An application can also be owned by a lane that names it as part
            # of a group (``chrome, firefox``); treat those as owned too.
            if AudioController._claims_process(claimed, focused):
                continue

            resolved[index] = "current"

        return resolved, claimed

    def set_application_volume(self, app_names, level):
        """Set the volume (0-100) for one or more comma-separated targets.

        Targets may be application names or the special values ``master``,
        ``mic``, ``system`` and ``current``.
        """
        self._ensure_thread_state()

        if isinstance(app_names, (list, tuple)):
            targets = [str(name).strip() for name in app_names]
        else:
            targets = [name.strip() for name in str(app_names).split(",")]
        targets = [target for target in targets if target]

        for target in targets:
            try:
                self._apply_target(target, level)
            except Exception as error:
                logger.warning("Could not set volume for %r: %s", target, error)
                self._reset_endpoint()

    @staticmethod
    def _claims_process(claimed, process_name):
        """True when a named lane already controls *process_name*."""
        if not process_name:
            return False

        lowered = process_name.lower()
        for token in claimed:
            if not token:
                continue
            # Compare without the .exe suffix so ``firefox`` owns firefox.exe.
            if token == lowered or token in lowered or lowered in token:
                return True
        return False

    def _apply_target(self, target, level, claimed=None):
        lowered = target.lower()

        if lowered == "master":
            self.set_master_volume(level)
            return

        if lowered == "mic":
            self.set_microphone_volume(level)
            return

        if lowered == "current":
            process_name = self.get_current_process_name()
            if not process_name:
                logger.debug("No foreground process to control")
                return

            # Do not let the ``current`` lane take over an application that a
            # named lane already controls.
            if claimed and self._claims_process(claimed, process_name):
                logger.debug(
                    "Skipping 'current': %s is controlled by a named lane",
                    process_name,
                )
                return

            target = process_name
            lowered = process_name.lower()

        for _kind, session in self._iter_targets(target):
            if self._set_session_volume(session, level):
                return

        logger.debug("No audio session matched %r", target)

    def set_master_volume(self, level):
        """Set the default playback device volume (0-100)."""
        self._get_endpoint_volume().SetMasterVolumeLevelScalar(
            max(0.0, min(1.0, level / 100.0)), None
        )

    def set_microphone_volume(self, level):
        """Set the default microphone volume (0-100); 0 also mutes it."""
        volume = self._get_microphone_volume_interface()
        if level <= 0:
            volume.SetMute(1, None)
        else:
            volume.SetMute(0, None)
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100.0)), None)

    def _get_microphone_volume_interface(self):
        """Endpoint volume for the default capture device.

        ``GetMicrophone()`` returns the ``IMMDevice`` in current pycaw versions,
        but older ones may wrap it like ``GetSpeakers()`` does, so delegate to
        the same compatibility helper.
        """
        return self._endpoint_volume_from_device(AudioUtilities.GetMicrophone())

    def get_microphone_volume(self, default=50):
        """Current microphone volume as an int percentage."""
        try:
            level = self._get_microphone_volume_interface().GetMasterVolumeLevelScalar()
            return int(round(level * 100))
        except Exception as error:
            logger.warning("Could not read microphone volume: %s", error)
            return default

    def get_master_volume(self, default=None):
        """Current master volume as an int percentage."""
        try:
            level = self._get_endpoint_volume().GetMasterVolumeLevelScalar()
            return int(round(level * 100))
        except Exception as error:
            logger.warning("Could not read master volume: %s", error)
            return default

    def get_application_volume(self, app_name, default=None):
        """Current volume of the first session matching *app_name*.

        Used when un-muting, so the previous level can be restored instead of
        guessing 50%.
        """
        try:
            for _kind, session in self._iter_targets(app_name):
                volume = self._get_session_volume(session)
                level = volume.GetMasterVolume()
                if level is not None:
                    return int(round(level * 100))
        except Exception as error:
            logger.warning("Could not read volume for %r: %s", app_name, error)
        return default
    def list_audio_applications(self):
        """Process names that currently have an audio session.

        Used by the UI to offer suggestions instead of asking the user to dig
        through Task Manager.
        """
        names = set()
        try:
            for session in self._get_sessions(max_age=0.5):
                name = self._session_process_name(session)
                if name:
                    names.add(name)
        except Exception as error:
            logger.warning("Could not enumerate audio sessions: %s", error)
        return sorted(names, key=str.lower)

    def cleanup(self):
        """Release COM state for the calling thread."""
        state = self._local
        state.volume = None
        state.devices = None
        state.sessions = None
        state.sessions_at = 0.0

        if getattr(state, "initialized_com", False):
            try:
                pythoncom.CoUninitialize()
            except Exception as error:  # pragma: no cover - defensive
                logger.debug("CoUninitialize failed: %s", error)
            finally:
                state.initialized_com = False
                state.ready = False
