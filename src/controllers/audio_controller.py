import pythoncom
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import win32.win32gui as win32gui
import win32.win32process as win32process
import psutil
from threading import Lock, local

class AudioController:
    _instance = None
    _thread_local = local()
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AudioController, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._init_com()
            self._sessions_cache = None
            self._last_session_refresh = 0

    def _init_com(self):
        """Initialize COM for the current thread if not already initialized"""
        if not hasattr(self._thread_local, 'initialized'):
            pythoncom.CoInitialize()
            self._thread_local.initialized = True
            self.devices = AudioUtilities.GetSpeakers()
            self.interface = self.devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self.volume = self.interface.QueryInterface(IAudioEndpointVolume)

    def _get_sessions(self):
        """Cache audio sessions to reduce CPU usage"""
        import time
        current_time = time.time()
        
        with self._lock:
            if self._sessions_cache is None or (current_time - self._last_session_refresh) > 2:
                self._sessions_cache = AudioUtilities.GetAllSessions()
                self._last_session_refresh = current_time
            return self._sessions_cache

    def set_application_volume(self, app_name, level):
        self._init_com()
        
        try:
            if app_name.lower() == "current":
                hwnd = win32gui.GetForegroundWindow()
                _, process_id = win32process.GetWindowThreadProcessId(hwnd)

                if not process_id:
                    return

                process = psutil.Process(process_id)
                process_name = process.name()

                for session in self._get_sessions():
                    if session.Process and session.Process.name().lower() == process_name.lower():
                        with self._lock:
                            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                            volume.SetMasterVolume(level / 100, None)
                            volume = None
                        return

            elif app_name.lower() == "master":
                with self._lock:
                    self.volume.SetMasterVolumeLevelScalar(level / 100, None)
                return

            elif app_name.lower() == "mic":
                with self._lock:
                    mic_device = AudioUtilities.GetMicrophone()
                    mic_volume_interface = mic_device.Activate(
                        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                    )
                    mic_volume = mic_volume_interface.QueryInterface(IAudioEndpointVolume)
                    mic_volume.SetMasterVolumeLevelScalar(level / 100, None)
                    mic_volume = None
                return

            else:
                for session in self._get_sessions():
                    if session.Process and app_name.lower() in session.Process.name().lower():
                        with self._lock:
                            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                            volume.SetMasterVolume(level / 100, None)
                            volume = None
                        return

        except Exception as e:
            print(f"Error setting volume: {e}")

    def cleanup(self):
        """Explicit cleanup method to be called when shutting down"""
        with self._lock:
            if hasattr(self, 'volume'):
                self.volume = None
            if hasattr(self, 'interface'):
                self.interface = None
            if hasattr(self._thread_local, 'initialized'):
                pythoncom.CoUninitialize()
                self._thread_local.initialized = False 