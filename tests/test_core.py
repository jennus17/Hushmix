"""Smoke tests for the non-GUI parts of Hushmix.

These run with the standard library only (plus whatever is installed), so they
work even on a machine without pycaw/pystray: the modules under test import
their heavy dependencies lazily or not at all.

Run with::

    python tests/test_core.py
"""

import json
import os
import sys
import tempfile
import traceback

# Make ``src`` importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)


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


def stub_heavy_imports():
    """Install stand-ins for pyautogui/psutil/customtkinter when missing.

    ``controllers.button_actions`` only needs ``pyautogui.KEY_NAMES``,
    ``pyautogui.keyDown/keyUp/press`` and two ``customtkinter`` variable classes
    at import time, so the pure shortcut-parsing logic can be exercised without
    the real packages (which need a Tk installation and a build toolchain).
    """
    import types

    if "pyautogui" not in sys.modules:
        try:
            import pyautogui  # noqa: F401
        except ImportError:
            stub = types.ModuleType("pyautogui")
            stub.KEY_NAMES = [
                "a", "b", "c", "d", "s", "f5", "enter", "esc", "space", "tab",
                "ctrl", "shift", "alt", "winleft", "add", "multiply",
            ]
            stub.keyDown = lambda *a, **k: None
            stub.keyUp = lambda *a, **k: None
            stub.press = lambda *a, **k: None
            sys.modules["pyautogui"] = stub

    if "psutil" not in sys.modules:
        try:
            import psutil  # noqa: F401
        except ImportError:
            stub = types.ModuleType("psutil")
            stub.Process = lambda *a, **k: None
            stub.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
            stub.AccessDenied = type("AccessDenied", (Exception,), {})
            stub.ZombieProcess = type("ZombieProcess", (Exception,), {})
            stub.pid_exists = lambda pid: False
            sys.modules["psutil"] = stub

    if "customtkinter" not in sys.modules:
        try:
            import customtkinter  # noqa: F401
        except ImportError:
            stub = types.ModuleType("customtkinter")

            class _Var:
                def __init__(self, value=None):
                    self._value = value

                def get(self):
                    return self._value

                def set(self, value):
                    self._value = value

            class _Widget:
                def __init__(self, *args, **kwargs):
                    pass

            stub.BooleanVar = _Var
            stub.StringVar = _Var
            stub.CTk = _Widget
            stub.CTkFrame = _Widget
            stub.CTkLabel = _Widget
            sys.modules["customtkinter"] = stub

    # Windows-only COM modules needed at import time by the audio controller,
    # which controllers.button_actions imports indirectly.
    for name in ("pythoncom", "comtypes", "pycaw"):
        if name in sys.modules:
            continue
        try:
            __import__(name)
        except ImportError:
            stub = types.ModuleType(name)
            if name == "comtypes":
                stub.CLSCTX_ALL = 0
            if name == "pycaw":
                sub = types.ModuleType("pycaw.pycaw")
                sub.AudioUtilities = object
                sub.IAudioEndpointVolume = object
                sub.ISimpleAudioVolume = object
                stub.pycaw = sub
                stub.__path__ = []  # mark it as a package
                sys.modules["pycaw.pycaw"] = sub
            sys.modules[name] = stub

    for name in ("win32.win32gui", "win32.win32process"):
        if name in sys.modules:
            continue
        try:
            __import__(name)
        except ImportError:
            if "win32" not in sys.modules:
                sys.modules["win32"] = types.ModuleType("win32")
            stub = types.ModuleType(name)
            stub.GetForegroundWindow = lambda: 0
            stub.GetWindowThreadProcessId = lambda hwnd: (0, 0)
            sys.modules[name] = stub
            setattr(sys.modules["win32"], name.split(".")[-1], stub)

    if "serial" not in sys.modules:
        try:
            import serial  # noqa: F401
        except ImportError:
            stub = types.ModuleType("serial")
            stub.SerialException = type("SerialException", (OSError,), {})

            class _Serial:
                def __init__(self, *args, **kwargs):
                    self.is_open = False

                def close(self):
                    pass

                def readline(self):
                    return b""

            stub.Serial = _Serial
            tools = types.ModuleType("serial.tools")
            list_ports = types.ModuleType("serial.tools.list_ports")
            list_ports.comports = lambda *a, **k: []
            tools.list_ports = list_ports
            stub.tools = tools
            stub.__path__ = []
            sys.modules["serial"] = stub
            sys.modules["serial.tools"] = tools
            sys.modules["serial.tools.list_ports"] = list_ports


# --------------------------------------------------------------------- atomic IO
def test_atomic_io():
    results.section("atomic_io")
    from utils.atomic_io import atomic_write_json, atomic_write_text, read_json

    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "nested", "data.json")
        atomic_write_json(path, {"a": 1})
        data, error = read_json(path)
        results.check(error is None, f"read_json returned error: {error}")
        results.check(data == {"a": 1}, f"round-trip mismatch: {data}")

        # A crashed write must not leave a partial file behind.
        atomic_write_text(path, "{not json")
        broken, error = read_json(path)
        results.check(broken is None and error is not None, "invalid JSON should report an error")

        # Missing file is not an error.
        missing, error = read_json(os.path.join(folder, "nope.json"))
        results.check(missing is None and error is None, "missing file should be silent")

        # No temporary files left behind.
        leftovers = [name for name in os.listdir(folder) if name.endswith(".tmp")]
        results.check(not leftovers, f"temporary files left behind: {leftovers}")


# ------------------------------------------------------------------- versioning
def test_version_utils():
    results.section("version_utils")
    from utils.version_utils import compare_versions, is_newer, normalize

    cases = [
        ("1.0.0", "1.0.0", 0),
        ("v1.0.0", "1.0.0", 0),
        ("1.0.1", "1.0.0", 1),
        ("1.0.0", "1.0.1", -1),
        ("1.10.0", "1.9.0", 1),
        ("2.0", "1.9.9", 1),
        ("1.0.0", "1.0.0-beta", 1),
        ("1.0.0-beta", "1.0.0", -1),
        ("1.0.0-rc1", "1.0.0-rc2", -1),
    ]
    for left, right, expected in cases:
        actual = compare_versions(left, right)
        results.check(
            actual == expected, f"compare_versions({left!r}, {right!r}) = {actual}, want {expected}"
        )

    results.check(is_newer("1.0.1", "1.0.0"), "is_newer should detect a newer release")
    results.check(not is_newer("1.0.0", "1.0.0"), "is_newer must not fire on equal versions")
    results.check(not is_newer("0.9.0", "1.0.0"), "is_newer must not fire on older versions")
    results.check(normalize("v1.2.3") == "1.2.3", "normalize should strip the v prefix")


# ------------------------------------------------------------------- packaging
def test_png_to_ico():
    results.section("png2ico")
    from utils import png2ico

    source = os.path.join(SRC, "utils", "assets", "volume_icon.png")
    if not os.path.exists(source):
        print("SKIP: sample artwork not found")
        return

    with tempfile.TemporaryDirectory() as folder:
        target = os.path.join(folder, "out.ico")
        _, sizes = png2ico.png_to_ico(source, target)
        results.check(os.path.getsize(target) > 0, "generated icon is empty")
        results.check(16 in sizes and 32 in sizes, f"unexpected icon sizes: {sizes}")

        with open(target, "rb") as stream:
            header = stream.read(6)
        reserved, kind, count = __import__("struct").unpack("<HHH", header)
        results.check(
            (reserved, kind, count) == (0, 1, len(sizes)),
            f"invalid ICO header: {reserved}, {kind}, {count}",
        )


# --------------------------------------------------------------------- config
def test_config_manager():
    results.section("config_manager")
    from utils.config_manager import ConfigManager

    with tempfile.TemporaryDirectory() as folder:
        ConfigManager.CONFIG_FILE = os.path.join(folder, "settings.json")
        # The "skip identical writes" cache is keyed by path, but reset it so a
        # stale entry from another test can never mask a real write.
        ConfigManager._last_written = None
        ConfigManager._last_written_path = None

        defaults = ConfigManager.get_default_settings()
        results.check(
            set(ConfigManager.PROFILE_SETTINGS) <= set(defaults["profiles"]["Profile 1"]),
            "default profile is missing declared fields",
        )
        results.check(
            list(defaults["profiles"]) == ["Profile 1"],
            f"a fresh install should have a single profile, got {list(defaults['profiles'])}",
        )

        # Two profiles, so the "one profile does not affect another" checks can
        # run.  A fresh install only seeds one.
        ConfigManager.save_all_settings(defaults)
        ConfigManager.add_profile("Second", copy_from="Profile 1")
        defaults = ConfigManager.load_all()
        results.check(
            "chrome" not in defaults["profiles"]["Second"]["applications"],
            "get_default_settings returns shared list objects",
        )

        # A profile-scoped key that is not in the GUI's short list must survive.
        ConfigManager.save_settings(
            {
                "current_profile": "Second",
                "keyboard_shortcuts": ["Ctrl+Shift+S"],
                "app_launch_paths": ["C:/tools/app.exe"],
                "dark_mode": False,
            }
        )
        loaded = ConfigManager.load_settings()
        results.check(
            loaded["keyboard_shortcuts"] == ["Ctrl+Shift+S"],
            f"keyboard_shortcuts were dropped: {loaded.get('keyboard_shortcuts')}",
        )
        results.check(
            loaded["app_launch_paths"] == ["C:/tools/app.exe"],
            f"app_launch_paths were dropped: {loaded.get('app_launch_paths')}",
        )
        results.check(loaded["dark_mode"] is False, "global setting was not saved")

        # Saving global settings must not wipe profile data.
        ConfigManager.save_settings({"current_profile": "Second", "invert_volumes": True})
        loaded = ConfigManager.load_settings()
        results.check(
            loaded["keyboard_shortcuts"] == ["Ctrl+Shift+S"],
            "a later global save erased profile data",
        )

        # Writing one profile must leave the other profiles alone.
        ConfigManager.save_settings(
            {"current_profile": "Profile 1", "applications": ["spotify"]}
        )
        loaded = ConfigManager.load_settings()
        results.check(
            loaded["profiles"]["Second"]["keyboard_shortcuts"] == ["Ctrl+Shift+S"],
            f"Second was overwritten: {loaded['profiles'].get('Second', {}).get('keyboard_shortcuts')}",
        )
        results.check(
            loaded["profiles"]["Profile 1"]["applications"][0] == "spotify",
            f"Profile 1 was not updated: {loaded['profiles']['Profile 1'].get('applications')}",
        )

        # Profile management.
        ok, _ = ConfigManager.add_profile("Gaming", copy_from="Second")
        results.check(ok, "add_profile failed")
        results.check("Gaming" in ConfigManager.get_profile_names(), "new profile not listed")

        ok, _ = ConfigManager.add_profile("Gaming")
        results.check(not ok, "duplicate profile name should be rejected")

        ok, _ = ConfigManager.rename_profile("Gaming", "Games")
        results.check(ok, "rename_profile failed")
        results.check("Games" in ConfigManager.get_profile_names(), "rename did not apply")

        ok, _ = ConfigManager.delete_profile("Games")
        results.check(ok, "delete_profile failed")
        results.check("Games" not in ConfigManager.get_profile_names(), "delete did not apply")

        # A profile copied from another one keeps its values.
        results.check(
            ConfigManager.load_all()["profiles"].get("Second", {}).get("keyboard_shortcuts")
            == ["Ctrl+Shift+S"],
            "the source profile was changed by copying it",
        )

        # Legacy empty default profiles are pruned, used ones are kept.
        # Written straight to disk: ``load`` repairs the file, so this checks
        # that repair itself drops them.
        from utils.atomic_io import atomic_write_json

        atomic_write_json(
            ConfigManager.CONFIG_FILE,
            {
                "current_profile": "Profile 1",
                "profiles": {
                    "Profile 1": ConfigManager._default_profile_data(),
                    "Profile 2": ConfigManager._default_profile_data(),
                    "Profile 5": ConfigManager._default_profile_data(),
                    "Work": {**ConfigManager._default_profile_data(), "applications": ["slack"]},
                },
            },
        )
        names = ConfigManager.get_profile_names()
        results.check("Work" in names, f"a used profile was pruned: {names}")
        results.check(
            "Profile 2" not in names and "Profile 5" not in names,
            f"unused default profiles survived loading: {names}",
        )
        results.check("Profile 1" in names, "the current profile was pruned")

        # ``prune_unused_default_profiles`` cleans up an on-disk file directly.
        atomic_write_json(
            ConfigManager.CONFIG_FILE,
            {
                "current_profile": "Profile 1",
                "profiles": {
                    "Profile 1": ConfigManager._default_profile_data(),
                    "Profile 3": ConfigManager._default_profile_data(),
                    "Profile 4": ConfigManager._default_profile_data(),
                },
            },
        )
        removed = ConfigManager.prune_unused_default_profiles()
        results.check(
            set(removed) == {"Profile 3", "Profile 4"},
            f"unexpected profiles pruned: {removed}",
        )

        # A settings file whose selected profile is empty falls back to a used
        # one, so the app does not open on a blank window.
        atomic_write_json(
            ConfigManager.CONFIG_FILE,
            {
                "current_profile": "Profile 2",
                "profiles": {
                    "Profile 1": {
                        **ConfigManager._default_profile_data(),
                        "applications": ["firefox"],
                    },
                    "Profile 2": ConfigManager._default_profile_data(),
                },
            },
        )
        promoted = ConfigManager.load_settings()
        results.check(
            promoted["current_profile"] == "Profile 1",
            f"an empty selected profile was not skipped: {promoted['current_profile']}",
        )

        # A corrupt file must fall back to defaults instead of raising.
        with open(ConfigManager.CONFIG_FILE, "w", encoding="utf-8") as stream:
            stream.write('{"current_profile": "Profile 1", "profiles": {')
        fallback = ConfigManager.load_settings()
        results.check(
            fallback["current_profile"] == "Profile 1",
            "corrupt settings did not fall back to defaults",
        )

        # Repairing a settings file with junk profile entries.
        with open(ConfigManager.CONFIG_FILE, "w", encoding="utf-8") as stream:
            json.dump({"profiles": {"Profile 1": "not-a-dict"}, "window_x": "abc"}, stream)
        repaired = ConfigManager.load_settings()
        results.check(isinstance(repaired["profiles"]["Profile 1"], dict), "profile was not repaired")
        results.check(repaired["window_x"] is None, "bad window_x was not cleared")


# -------------------------------------------------------------------- shortcuts
def test_shortcut_parsing():
    results.section("button_actions.parse_shortcut")
    stub_heavy_imports()
    try:
        from controllers.button_actions import parse_shortcut
    except ImportError as error:
        print(f"SKIP: {error}")
        return

    modifiers, keys, unknown = parse_shortcut("Ctrl+Shift+S")
    results.check(modifiers == ["ctrl", "shift"], f"modifiers: {modifiers}")
    results.check(keys == ["s"], f"keys: {keys}")
    results.check(not unknown, f"unexpected unknown keys: {unknown}")

    # The old implementation only handled this case by accident.
    modifiers, keys, _ = parse_shortcut("Ctrl+A")
    results.check((modifiers, keys) == (["ctrl"], ["a"]), f"Ctrl+A parsed as {modifiers}, {keys}")

    modifiers, keys, _ = parse_shortcut("F5")
    results.check(not modifiers and keys == ["f5"], f"F5 parsed as {modifiers}, {keys}")

    modifiers, keys, _ = parse_shortcut("Win+D")
    results.check(
        modifiers == ["winleft"] and keys == ["d"],
        f"Win+D parsed as {modifiers}, {keys}",
    )

    modifiers, keys, _ = parse_shortcut("Enter")
    results.check(keys == ["enter"], f"Enter parsed as {keys}")

    # Unknown tokens are reported, not silently pressed.
    _, _, unknown = parse_shortcut("Ctrl+NotAKey")
    results.check(unknown == ["NotAKey"], f"unknown key not reported: {unknown}")

    results.check(parse_shortcut("") == ([], [], []), "empty shortcut should be empty")


# ----------------------------------------------------------------- serial data
def test_serial_parsing():
    results.section("serial_controller parsing")
    stub_heavy_imports()
    try:
        import serial  # noqa: F401
    except ImportError:
        print("SKIP: pyserial is not installed")
        return

    from controllers.serial_controller import SerialController

    def build_controller():
        controller = SerialController.__new__(SerialController)
        controller.volume_filters = []
        controller.volume_callback = None
        controller.button_callback = None
        controller._filter_settings = None
        return controller

    controller = build_controller()
    volumes = []
    buttons = []
    controller.volume_callback = volumes.append
    controller.button_callback = buttons.append

    # A well-formed packet (a fresh controller reports the first value as-is).
    controller.handle_line("50|60|70-1|0|2")
    results.check(volumes == [[50, 60, 70]], f"volumes: {volumes}")
    results.check(buttons == [[1, 0, 2]], f"buttons: {buttons}")

    # No button section - this used to raise IndexError.
    fresh = build_controller()
    fresh_volumes = []
    fresh.volume_callback = fresh_volumes.append
    fresh.button_callback = buttons.append
    fresh.handle_line("10|20")
    results.check(fresh_volumes == [[10, 20]], f"volumes without buttons: {fresh_volumes}")
    results.check(buttons == [[1, 0, 2]], "button callback should not have fired")

    # Smoothing converges towards a stable slider value.
    steady = build_controller()
    steady_volumes = []
    steady.volume_callback = steady_volumes.append
    for _ in range(40):
        steady.handle_line("80-0")
    results.check(
        steady_volumes[-1] == [80],
        f"smoothing did not converge: got {steady_volumes[-1]}",
    )

    # Garbage is ignored rather than crashing the reader thread.
    controller.handle_line("abc|def-xyz")
    results.check(True, "garbage packet handled")
    results.check(controller._filter_for(0) is not None, "filters are created lazily")

    # Empty lines and separators are harmless.
    controller.handle_line("")
    controller.handle_line("-")
    results.check(True, "empty packets handled")


def test_button_modes():
    results.section("button_actions button modes")
    stub_heavy_imports()
    try:
        from controllers.button_actions import ButtonActions
    except ImportError as error:
        print(f"SKIP: {error}")
        return

    matches = ButtonActions._mode_matches
    results.check(matches("Click", 1), "Click should fire on a single press")
    results.check(not matches("Click", 2), "Click should not fire on a hold")
    results.check(matches("Double Click", 3), "Double Click should fire on 3")
    results.check(not matches("Double Click", 1), "Double Click should not fire on 1")
    results.check(matches("Hold", 2), "Hold should fire on 2")
    results.check(not matches("Hold", 3), "Hold should not fire on 3")


# --------------------------------------------------------------- volume manager
def test_volume_manager():
    results.section("volume_manager")
    stub_heavy_imports()
    from controllers.audio_controller import AudioController
    from controllers.volume_manager import VolumeManager

    class FakeVar:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    class FakeAudio:
        #: Use the real lane resolution so the ownership rule is exercised here
        #: as well, not just in the dedicated lane tests.  Wrapped in
        #: staticmethod so it is not treated as a bound instance method.
        resolve_lanes = staticmethod(AudioController.resolve_lanes)

        def __init__(self):
            self.calls = []

        def set_application_volume(self, name, level):
            self.calls.append((name, level))

        def get_microphone_volume(self):
            return 65

        def get_application_volume(self, name):
            return 42

        def get_current_process_name(self):
            return None

    class FakeSettings:
        def get_setting(self, key, default=None):
            return {"invert_volumes": False}.get(key, default)

    class FakeRoot:
        def after(self, delay, callback):
            callback()
            return 1

    class FakeLabels:
        def __init__(self):
            self.labels = [FakeVar("") for _ in range(7)]
            self.volume_labels = [FakeLabel() for _ in range(7)]

    class FakeLabel:
        default_text_color = "#ffffff"

        def __init__(self):
            self.options = {}

        def winfo_exists(self):
            return True

        def configure(self, **kwargs):
            self.options.update(kwargs)

    class FakeGUI:
        def __init__(self):
            self.volume_labels = [FakeLabel() for _ in range(7)]
            self.entries = [FakeVar("") for _ in range(7)]

    class FakeApp:
        def __init__(self):
            self.current_apps = ["master", "chrome", "mic", "", "", "", ""]
            self.muted_state = [False] * 7
            self.current_mute_state = [False] * 7
            self.previous_volumes = [None] * 7
            self.audio_controller = FakeAudio()
            self.settings_manager = FakeSettings()
            self.gui_components = FakeGUI()
            self.root = FakeRoot()
            self.saved = 0

        def save_settings(self):
            self.saved += 1

    app = FakeApp()
    manager = VolumeManager(app)

    # Volume changes reach the audio controller with the configured target.
    manager.update_volume(1, 64)
    results.check(
        ("chrome", 64) in app.audio_controller.calls,
        f"volume not applied: {app.audio_controller.calls}",
    )

    # Values are clamped and quantised to the 2% step.
    manager.update_volume(1, 250)
    results.check(app.audio_controller.calls[-1] == ("chrome", 100), "volume not clamped up")
    manager.update_volume(1, -10)
    results.check(app.audio_controller.calls[-2][1] <= 100, "negative volume not clamped")

    # Muting forces 0 and un-muting restores the previous level.
    manager.toggle_mute(1)
    results.check(app.muted_state[1] is True, "mute state not toggled")
    results.check(app.audio_controller.calls[-1] == ("chrome", 0), "muted volume is not 0")
    manager.toggle_mute(1)
    results.check(app.muted_state[1] is False, "mute state not toggled back")
    results.check(
        app.audio_controller.calls[-1][1] > 0, "un-mute did not restore a level"
    )

    # Un-muting the microphone uses the device level, not the slider value.
    app.muted_state[2] = True
    app.previous_volumes[2] = 0
    manager.toggle_mute(2)
    results.check(
        app.audio_controller.calls[-1] == ("mic", 65),
        f"microphone level not restored: {app.audio_controller.calls[-1]}",
    )

    # Out-of-range indices are rejected instead of raising.
    manager.toggle_mute(99)
    results.check(True, "out-of-range mute handled")


# --------------------------------------------------------------- deferred work
def test_deferred_actions():
    results.section("deferred_actions")
    from utils.deferred_actions import DeferredActions

    class FakeRoot:
        def __init__(self):
            self.callbacks = []

        def after(self, delay, callback):
            self.callbacks.append(callback)
            return len(self.callbacks)

    root = FakeRoot()
    queue = DeferredActions(root, interval_ms=1, max_pending=4)

    calls = []
    for index in range(20):
        queue.submit(calls.append, index)

    results.check(len(queue._queue.queue) <= 4, "queue exceeded its capacity")

    while root.callbacks:
        callback = root.callbacks.pop(0)
        callback()

    results.check(calls, "no actions ran")
    results.check(calls[-1] == 19, f"newest action should survive, got {calls[-1]}")

    queue.stop()
    results.check(not queue.submit(calls.append, 99), "submit after stop should be refused")


# ------------------------------------------------------------------ win utils
def test_win_utils():
    results.section("win_utils")
    from utils.win_utils import center_on_monitor, clamp_to_monitor, nearest_monitor

    monitors = [
        {"left": 0, "top": 0, "right": 1920, "bottom": 1080, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "right": 3840, "bottom": 1080, "width": 1920, "height": 1080},
    ]

    x, y = clamp_to_monitor(1900, 1000, 400, 300, monitors)
    results.check(0 <= x <= 1520, f"clamped x out of range: {x}")
    results.check(y <= 780, f"clamped y out of range: {y}")

    x, y = clamp_to_monitor(-500, -500, 400, 300, monitors)
    results.check((x, y) == (0, 0), f"negative position mapped to {x}, {y}")

    x, y = center_on_monitor(400, 300, monitors)
    results.check((x, y) == (760, 390), f"centred at {x}, {y}")

    nearest = nearest_monitor(3800, 500, monitors)
    results.check(nearest["left"] == 1920, "nearest monitor picked incorrectly")


# ------------------------------------------------------------------ app paths
def test_app_paths():
    results.section("app_paths")
    from utils.app_paths import app_data_dir, asset_path, settings_file, startup_command

    results.check(os.path.isabs(app_data_dir()), "app_data_dir must be absolute")
    results.check(os.path.isabs(settings_file()), "settings_file must be absolute")
    results.check(not os.path.isabs(asset_path("x.png")) is False, "asset_path must be absolute")
    results.check(os.path.isabs(asset_path("volume_icon.png")), "asset_path must be absolute")
    results.check(
        os.path.exists(asset_path("volume_icon.png")), "bundled PNG artwork is missing"
    )
    results.check(
        os.path.exists(asset_path("volume_icon.ico")), "bundled ICO artwork is missing"
    )
    results.check(startup_command().strip(), "startup command is empty")


# ------------------------------------------------------------------ icon paths
def test_icon_manager():
    results.section("icon_manager")
    from utils.icon_manager import IconManager

    path = IconManager.get_ico_file()
    results.check(path is not None, "no usable icon file was found")
    if path:
        results.check(os.path.isabs(path), f"icon path must be absolute: {path}")
        results.check(os.path.exists(path), f"icon path does not exist: {path}")

    # The old implementation returned a path relative to the CWD.
    before = os.getcwd()
    try:
        os.chdir(tempfile.gettempdir())
        again = IconManager.get_ico_file()
        results.check(again == path, f"icon path depends on the CWD: {again} != {path}")
    finally:
        os.chdir(before)


# ---------------------------------------------------------------- log handling
def test_logging():
    results.section("logging_setup")
    from utils.logging_setup import get_logger, setup_logging

    logger = setup_logging()
    results.check(logger is get_logger(), "get_logger should return the configured logger")
    logger.info("smoke test log line")
    results.check(len(logger.handlers) >= 1, "no log handlers configured")


def test_fresh_install_logging():
    """The log file must be created on a machine that has never run Hushmix."""
    results.section("logging on a fresh install")
    import importlib

    from utils import log_path

    sandbox = tempfile.mkdtemp(prefix="hushmix_fresh_")
    previous = os.environ.get("APPDATA")
    os.environ["APPDATA"] = sandbox
    try:
        importlib.reload(log_path)
        candidates = log_path.resolve_log_file()
        results.check(candidates, "no log file candidates were produced")
        results.check(
            candidates[0].startswith(sandbox),
            f"the primary log path ignores APPDATA: {candidates[0]}",
        )

        # setup_logging must create the folder itself.
        import utils.logging_setup as logging_setup

        logging_setup._configured = False
        logging_setup._LOGGER_NAME = "hushmix_fresh"
        fresh_logger = logging_setup.setup_logging(console=False)
        fresh_logger.info("fresh install")
        for handler in fresh_logger.handlers:
            handler.flush()

        expected = os.path.join(sandbox, "Hushmix", "hushmix.log")
        results.check(
            os.path.exists(expected),
            f"the log file was not created at {expected}",
        )
        if os.path.exists(expected):
            with open(expected, encoding="utf-8") as stream:
                results.check("fresh install" in stream.read(), "the log line was not written")
    finally:
        if previous is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = previous
        importlib.reload(log_path)

        import utils.logging_setup as logging_setup

        logging_setup._LOGGER_NAME = "hushmix"
        logging_setup._configured = True


def main():
    tests = [
        test_atomic_io,
        test_app_paths,
        test_version_utils,
        test_png_to_ico,
        test_config_manager,
        test_win_utils,
        test_logging,
        test_fresh_install_logging,
        test_icon_manager,
        test_shortcut_parsing,
        test_serial_parsing,
        test_button_modes,
        test_volume_manager,
        test_deferred_actions,
    ]

    for test in tests:
        try:
            test()
        except Exception:
            results.failed.append(f"{test.__name__} raised an exception")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"checks passed: {results.passed}")
    print(f"failures: {len(results.failed)}")
    for failure in results.failed:
        print(f"  - {failure}")
    return 1 if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
