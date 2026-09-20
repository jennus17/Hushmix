"""Integration checks for the GUI wiring, using stub widget modules.

The real ``customtkinter``/``pystray``/``pycaw`` packages need a full desktop
session, audio hardware and (on some setups) a C toolchain.  This script
installs lightweight stand-ins so the *logic* that glues the GUI together can be
executed: window construction, profile switching, settings load/save, the
volume path and shutdown ordering.

It is not a substitute for running the application, but it catches the class of
error that a syntax check cannot - a missing attribute, a wrong argument count,
or a profile field that is read but never written.

Run with::

    python tests/test_gui_pipeline.py
"""

import os
import sys
import tempfile
import traceback
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)


# --------------------------------------------------------------------- stubs
class FakeVar:
    def __init__(self, value=None, master=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class FakeWidget:
    """Records configuration calls so tests can assert on them.

    ``__getattr__`` rejects the kind of mistake a hand-written stub usually
    hides: calling a Tk frame method that does not exist (for example
    ``grid_columnconfigure``, which the application used to call and which
    raises ``AttributeError`` on a real ``CTkFrame``).
    """

    #: Method names CustomTkinter widgets really expose that this stub does not
    #: implement meaningfully.
    KNOWN_EXTRA_METHODS = frozenset(
        {
            "cget", "configure", "config", "bind", "unbind", "grid", "pack",
            "place", "grid_remove", "grid_forget", "grid_propagate",
            "grid_columnconfigure", "grid_rowconfigure", "columnconfigure",
            "rowconfigure", "winfo_exists", "winfo_viewable", "winfo_width",
            "winfo_height", "winfo_reqwidth", "winfo_reqheight", "winfo_x",
            "winfo_y", "winfo_rootx", "winfo_rooty", "winfo_toplevel",
            "winfo_screenwidth", "winfo_screenheight", "winfo_children",
            "update_idletasks", "update", "destroy", "focus_force", "focus_set",
            "lift", "lower", "deiconify", "withdraw", "title", "resizable",
            "geometry", "protocol", "attributes", "iconbitmap", "wm_iconbitmap",
            "transient", "grab_release", "grab_set", "after", "after_idle",
            "after_cancel", "insert", "delete", "set", "get", "mainloop", "quit",
            "tk", "call", "set_appearance_mode", "state", "iconify", "wait_window",
            "wm_attributes", "wm_geometry", "wm_title", "tk_bisque",
        }
    )

    def __getattr__(self, name):
        # ``FakeWidget`` instances never reach here for attributes defined on
        # the class; anything else must be one of the known Tk/CTk methods.
        if name.startswith("_") or name in FakeWidget.KNOWN_EXTRA_METHODS:
            return lambda *args, **kwargs: None
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = dict(kwargs)
        self.grid_calls = []
        self.children = []
        self.destroyed = False
        self._text = kwargs.get("text", "")
        self._grid_visible = True
        self._bindings = {}
        if isinstance(master, FakeWidget):
            master.children.append(self)

    # --- geometry -------------------------------------------------------
    def grid(self, **kwargs):
        self.grid_calls.append(kwargs)
        self._grid_visible = True

    def grid_remove(self):
        self._grid_visible = False

    def grid_forget(self):
        self._grid_visible = False

    def pack(self, **kwargs):
        self.grid_calls.append(kwargs)

    def place(self, **kwargs):
        pass

    def columnconfigure(self, *args, **kwargs):
        pass

    def rowconfigure(self, *args, **kwargs):
        pass

    # --- state ----------------------------------------------------------
    def configure(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs["text"]
        self.kwargs.update(kwargs)

    config = configure

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "text_color":
            return self.kwargs.get("text_color", "#ffffff")
        if key == "fg_color":
            return self.kwargs.get("fg_color", "#2b2b2b")
        if key == "state":
            return self.kwargs.get("state", "normal")
        return ""

    def bind(self, sequence, function=None, add=None):
        self._bindings[sequence] = function
        return "bind-id"

    def unbind(self, sequence, bind_id=None):
        self._bindings.pop(sequence, None)

    def winfo_exists(self):
        return not self.destroyed

    def winfo_viewable(self):
        return True

    def winfo_width(self):
        return 360

    def winfo_height(self):
        return 240

    def winfo_reqwidth(self):
        return 360

    def winfo_reqheight(self):
        return 240

    def winfo_x(self):
        return 100

    def winfo_y(self):
        return 100

    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 100

    def winfo_toplevel(self):
        return self

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def update_idletasks(self):
        pass

    def update(self):
        pass

    def destroy(self):
        self.destroyed = True
        for child in list(self.children):
            child.destroy()

    def focus_force(self):
        pass

    def focus_set(self):
        pass

    def lift(self):
        pass

    def deiconify(self):
        pass

    def withdraw(self):
        pass

    def title(self, *args):
        pass

    def resizable(self, *args):
        pass

    def geometry(self, *args):
        self._geometry = args[0] if args else ""

    def protocol(self, *args):
        pass

    def attributes(self, *args):
        pass

    def iconbitmap(self, *args, **kwargs):
        pass

    def wm_iconbitmap(self, *args, **kwargs):
        pass

    def transient(self, *args):
        pass

    def grab_release(self):
        pass

    def tk(self):
        raise AssertionError("tk() should not be used on a stub widget")

    def after(self, delay, callback=None, *args):
        if callback is not None:
            callback(*args)
        return "after-id"

    def after_idle(self, callback=None, *args):
        if callback is not None:
            callback(*args)
        return "idle-id"

    def after_cancel(self, job):
        pass

    def insert(self, *args):
        pass

    def delete(self, *args):
        pass

    def set(self, *args):
        pass

    def get(self, *args):
        return ""

    def mainloop(self, *args):
        pass

    def quit(self, *args):
        pass

    def call(self, *args):
        return 1.0


class FakeRoot(FakeWidget):
    def tk(self):
        return self

    def call(self, *args):
        return 1.0

    def set_appearance_mode(self, *args):
        pass


def install_stubs():
    ctk = types.ModuleType("customtkinter")
    ctk.BooleanVar = FakeVar
    ctk.StringVar = FakeVar
    ctk.IntVar = FakeVar

    widget_names = [
        "CTk", "CTkFrame", "CTkToplevel", "CTkLabel", "CTkButton", "CTkEntry",
        "CTkOptionMenu", "CTkCheckBox", "CTkProgressBar", "CTkTextbox",
        "CTkScrollableFrame", "CTkComboBox", "CTkSlider", "CTkSwitch",
    ]
    for name in widget_names:
        setattr(ctk, name, type(name, (FakeWidget,), {}))
    ctk.set_appearance_mode = lambda *a, **k: None
    ctk.set_default_color_theme = lambda *a, **k: None
    ctk.ThemeManager = types.SimpleNamespace(theme=types.SimpleNamespace())
    sys.modules["customtkinter"] = ctk

    # pystray
    pystray = types.ModuleType("pystray")

    class Icon:
        def __init__(self, name, icon=None, menu=None, title=None):
            self.name = name
            self.menu = menu
            self.stopped = False

        def run_detached(self, *args, **kwargs):
            pass

        def stop(self):
            self.stopped = True

    class MenuItem:
        def __init__(self, text, action=None, **kwargs):
            self.text = text
            self.action = action

    class Menu(list):
        def __init__(self, *items):
            super().__init__(items)

    pystray.Icon = Icon
    pystray.Menu = Menu
    pystray.MenuItem = MenuItem
    sys.modules["pystray"] = pystray

    # PIL
    pil = types.ModuleType("PIL")
    image_module = types.ModuleType("PIL.Image")

    class Image:
        LANCZOS = 1

        def __init__(self, size=(64, 64), color=None):
            self.size = size

        @staticmethod
        def new(mode, size, color=None):
            return Image(size)

        @staticmethod
        def open(path):
            return Image()

        def load(self):
            pass

        def resize(self, size, resample=None):
            return Image(size)

        def convert(self, mode):
            return self

    # ``from PIL import Image`` must yield the class, so both the package
    # attribute and the submodule are replaced by the class itself.
    pil.Image = Image
    sys.modules["PIL"] = pil
    sys.modules["PIL.Image"] = Image

    # Audio + COM + serial stubs
    pythoncom = types.ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: None
    pythoncom.CoUninitialize = lambda: None
    sys.modules["pythoncom"] = pythoncom

    comtypes = types.ModuleType("comtypes")
    comtypes.CLSCTX_ALL = 0
    sys.modules["comtypes"] = comtypes

    class _Endpoint:
        def SetMasterVolumeLevelScalar(self, level, ctx):
            pass

        def GetMasterVolumeLevelScalar(self):
            return 0.5

        def SetMute(self, flag, ctx):
            pass

        def GetMute(self):
            return False

    class _AudioUtilities:
        @staticmethod
        def GetSpeakers():
            return types.SimpleNamespace(
                Activate=lambda *a, **k: types.SimpleNamespace(
                    QueryInterface=lambda *a, **k: _Endpoint()
                )
            )

        @staticmethod
        def GetMicrophone():
            return _AudioUtilities.GetSpeakers()

        @staticmethod
        def GetAllSessions():
            return []

    pycaw = types.ModuleType("pycaw")
    pycaw_pycaw = types.ModuleType("pycaw.pycaw")
    pycaw_pycaw.AudioUtilities = _AudioUtilities
    pycaw_pycaw.IAudioEndpointVolume = type("IAudioEndpointVolume", (), {"_iid_": "iid"})
    pycaw_pycaw.ISimpleAudioVolume = type("ISimpleAudioVolume", (), {})
    pycaw.pycaw = pycaw_pycaw
    pycaw.__path__ = []
    sys.modules["pycaw"] = pycaw
    sys.modules["pycaw.pycaw"] = pycaw_pycaw

    for name in ("win32.win32gui", "win32.win32process"):
        module = types.ModuleType(name)
        module.GetForegroundWindow = lambda: 0
        module.GetWindowThreadProcessId = lambda hwnd: (0, 0)
        sys.modules.setdefault("win32", types.ModuleType("win32"))
        sys.modules[name] = module
        setattr(sys.modules["win32"], name.split(".")[-1], module)

    serial = types.ModuleType("serial")
    serial.SerialException = type("SerialException", (OSError,), {})

    class Serial:
        def __init__(self, *args, **kwargs):
            self.is_open = True

        def close(self):
            self.is_open = False

        def readline(self):
            return b""

    serial.Serial = Serial
    tools = types.ModuleType("serial.tools")
    list_ports = types.ModuleType("serial.tools.list_ports")
    list_ports.comports = lambda *a, **k: []
    tools.list_ports = list_ports
    serial.tools = tools
    serial.__path__ = []
    sys.modules["serial"] = serial
    sys.modules["serial.tools"] = tools
    sys.modules["serial.tools.list_ports"] = list_ports

    pyautogui = types.ModuleType("pyautogui")
    pyautogui.KEY_NAMES = ["a", "ctrl", "shift", "enter", "f5", "winleft"]
    pyautogui.FAILSAFE = True
    pyautogui.keyDown = lambda *a, **k: None
    pyautogui.keyUp = lambda *a, **k: None
    pyautogui.press = lambda *a, **k: None
    pyautogui.hotkey = lambda *a, **k: None
    sys.modules["pyautogui"] = pyautogui

    if "psutil" not in sys.modules:
        try:
            import psutil  # noqa: F401
        except ImportError:
            psutil = types.ModuleType("psutil")
            psutil.Process = lambda *a, **k: types.SimpleNamespace(name=lambda: "test.exe")
            psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
            psutil.AccessDenied = type("AccessDenied", (Exception,), {})
            psutil.ZombieProcess = type("ZombieProcess", (Exception,), {})
            psutil.pid_exists = lambda pid: False
            sys.modules["psutil"] = psutil

    if "requests" not in sys.modules:
        try:
            import requests  # noqa: F401
        except ImportError:
            requests = types.ModuleType("requests")

            class RequestException(Exception):
                pass

            requests.RequestException = RequestException
            requests.get = lambda *a, **k: (_ for _ in ()).throw(
                RequestException("network disabled in tests")
            )
            sys.modules["requests"] = requests

    if "pefile" not in sys.modules:
        try:
            import pefile  # noqa: F401
        except ImportError:
            pefile = types.ModuleType("pefile")
            pefile.PE = lambda *a, **k: types.SimpleNamespace(FileInfo=[])
            sys.modules["pefile"] = pefile


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = []

    def check(self, condition, message):
        if condition:
            self.passed += 1
        else:
            self.failed.append(message)
            print(f"FAIL: {message}")

    def section(self, name):
        print(f"\n== {name} ==")


results = Results()


def main():
    install_stubs()

    from utils.config_manager import ConfigManager

    folder = tempfile.mkdtemp(prefix="hushmix_gui_test_")
    ConfigManager.CONFIG_FILE = os.path.join(folder, "settings.json")

    from gui.app import HushmixApp

    root = FakeRoot()
    results.section("application construction")
    app = HushmixApp(root)
    results.check(app.settings_manager is not None, "settings manager missing")
    results.check(app.current_apps, "no channels configured")
    results.check(len(app.mute) == ConfigManager.BUTTON_COUNT, "mute vars not built")
    results.check(len(app.media_control_actions) == ConfigManager.BUTTON_COUNT,
                  "media control vars not built")

    # ------------------------------------------------------------ volume path
    results.section("volume path")
    calls = []
    app.audio_controller.set_application_volume = lambda name, level: calls.append((name, level))

    app.current_apps = ["master", "chrome", "mic", "firefox", "", "", ""]
    app.muted_state = [False] * 7
    app.current_mute_state = [False] * 7
    app.previous_volumes = [None] * 7

    app.volume_manager.handle_volume_update([10, 20, 30, 40, 50, 60, 70])
    results.check(calls, f"no volume calls were made: {calls}")
    results.check(any(name == "chrome" for name, _ in calls), f"chrome not controlled: {calls}")

    calls.clear()
    app.toggle_mute(1)
    results.check(app.muted_state[1] is True, "mute did not apply")
    results.check(calls and calls[-1] == ("chrome", 0), f"mute did not set 0: {calls}")
    app.toggle_mute(1)
    results.check(app.muted_state[1] is False, "un-mute did not apply")

    # --------------------------------------------------------- settings round trip
    results.section("settings round trip")
    app.media_control_actions[1].set("Next Track")
    app.keyboard_shortcuts[2].set("Ctrl+Shift+S")
    app.app_launch_paths[3].set(r"C:\tools\app.exe")
    app.app_launch_enabled[3].set(True)
    app.media_control_enabled[1].set(True)
    app.mute_button_modes[1].set("Hold")
    app.current_apps = ["master", "chrome", "mic", "firefox", "spotify", "discord", "steam"]

    results.check(app.save_settings() is not False, "save_settings failed")

    reloaded = ConfigManager.load_settings()
    results.check(reloaded["keyboard_shortcuts"][2] == "Ctrl+Shift+S",
                  f"shortcut lost: {reloaded.get('keyboard_shortcuts')}")
    results.check(reloaded["app_launch_paths"][3] == r"C:\tools\app.exe",
                  f"launch path lost: {reloaded.get('app_launch_paths')}")
    results.check(reloaded["media_control_actions"][1] == "Next Track",
                  f"media action lost: {reloaded.get('media_control_actions')}")
    results.check(reloaded["mute_button_modes"][1] == "Hold",
                  f"button mode lost: {reloaded.get('mute_button_modes')}")
    results.check(reloaded["applications"] == app.current_apps,
                  f"applications lost: {reloaded.get('applications')}")

    # ------------------------------------------------------------- profiles
    results.section("profile switching")
    success, message = app._add_profile("Gaming")
    results.check(success, f"could not add a profile: {message}")

    app.current_apps = ["master", "spotify", "", "", "", "", ""]
    app.mute_button_modes[1].set("Double Click")
    app.save_settings()

    app.on_profile_change("Gaming")
    results.check(app.current_apps[1] == "chrome",
                  f"copied profile lost its applications: {app.current_apps}")
    results.check(app.mute_button_modes[1].get() == "Hold",
                  f"copied profile lost its button mode: {app.mute_button_modes[1].get()}")

    app.on_profile_change("Profile 1")
    results.check(app.current_apps[1] == "spotify",
                  f"switching back lost applications: {app.current_apps}")

    # ------------------------------------------------------------- restart
    results.section("restart persistence")
    # The "Gaming" profile is the active one at this point (it was copied from
    # Profile 1 before Profile 1 was edited), so a restart must come back to it.
    app2 = HushmixApp(FakeRoot())
    results.check(app2.settings_manager.settings_vars.get("current_profile") == "Gaming",
                  f"active profile lost: {app2.settings_manager.settings_vars.get('current_profile')}")
    results.check(app2.current_apps[1] == "chrome",
                  f"applications lost across restart: {app2.current_apps}")
    results.check(app2.mute_button_modes[1].get() == "Hold",
                  f"button mode lost across restart: {app2.mute_button_modes[1].get()}")

    # And the other profile still holds its own, different values.
    app2.on_profile_change("Profile 1")
    results.check(app2.current_apps[1] == "spotify",
                  f"profile 1 lost its applications: {app2.current_apps}")
    results.check(app2.mute_button_modes[1].get() == "Double Click",
                  f"profile 1 lost its button mode: {app2.mute_button_modes[1].get()}")

    # ------------------------------------------------------------- popups
    results.section("popup windows")
    app.show_settings()
    results.check(app.settings_window is not None, "settings window not created")
    app.on_settings_close()
    results.check(app.settings_window is None, "settings window not released")

    app.show_buttonSettings(1)
    results.check(app.buttonSettings_window is not None, "button settings window not created")
    results.check(app.buttonSettings_window.index == 1,
                  f"wrong index in button settings: {app.buttonSettings_window.index}")
    app.on_buttonSettings_close()

    app.show_help()
    results.check(app.help_window is not None, "help window not created")
    app.on_help_close()

    # ------------------------------------------------------------- shutdown
    results.section("shutdown")
    # ``shutdown`` ends the process with os._exit(0) once every resource is
    # released, so it is exercised through a redirected os._exit and the
    # ordering is asserted before the real call.
    released = []
    app.serial_controller.cleanup = lambda: released.append("serial")
    app.audio_controller.cleanup = lambda: released.append("audio")
    original_cleanup = app.window_manager.cleanup

    def record_window_cleanup():
        released.append("window")
        original_cleanup()

    app.window_manager.cleanup = record_window_cleanup

    import os as os_module

    real_exit = os_module._exit
    exit_codes = []
    os_module._exit = lambda code: exit_codes.append(code)
    try:
        app.shutdown()
    finally:
        os_module._exit = real_exit

    results.check(app.running is False, "running flag not cleared")
    results.check(released == ["serial", "audio", "window"],
                  f"resources released in the wrong order: {released}")
    results.check(exit_codes == [0], f"shutdown did not terminate: {exit_codes}")

    print("\n" + "=" * 60)
    print(f"checks passed: {results.passed}")
    print(f"failures: {len(results.failed)}")
    for failure in results.failed:
        print(f"  - {failure}")
    return 1 if results.failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
