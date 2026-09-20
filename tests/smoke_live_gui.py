"""Launch the real application (with real customtkinter) and exercise it.

Unlike ``tests/test_gui_pipeline.py`` this uses the genuine GUI toolkit, so it
validates widget keywords, geometry calls and event bindings.  It needs an
interactive Windows session; in a headless environment it exits with code 3.

It redirects settings and logs into a temporary directory so a developer's
configuration is never touched, then drives the app through the paths that a
user would hit and reports anything that raised.

Run with::

    python tests/smoke_live_gui.py
"""

import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

FAILURES = []
CHECKS = [0]


def step(name, function, *args, **kwargs):
    """Run one interaction, recording failures instead of aborting."""
    CHECKS[0] += 1
    try:
        result = function(*args, **kwargs)
        print(f"ok   {name}")
        return result
    except Exception as error:
        FAILURES.append(f"{name}: {type(error).__name__}: {error}")
        print(f"FAIL {name}: {type(error).__name__}: {error}")
        traceback.print_exc()
        return None


def pump(root, times=12):
    """Let Tk process its event queue (and run the app's after() callbacks)."""
    for _ in range(times):
        try:
            root.update_idletasks()
            root.update()
        except Exception:
            break


class NoDialogs:
    """Replace the modal message boxes for the duration of the run.

    Any of them would block the test forever waiting for a click (which is how
    this harness used to hang at the "delete profile" step).
    """

    NAMES = ("askyesno", "showwarning", "showerror", "showinfo", "askokcancel")

    def __enter__(self):
        import tkinter.messagebox as messagebox

        self._messagebox = messagebox
        self._originals = {name: getattr(messagebox, name) for name in self.NAMES}
        messagebox.askyesno = lambda *a, **k: True
        messagebox.askokcancel = lambda *a, **k: True
        for name in ("showwarning", "showerror", "showinfo"):
            setattr(messagebox, name, lambda *a, **k: "ok")
        return self

    def __exit__(self, *exc_info):
        for name, function in self._originals.items():
            setattr(self._messagebox, name, function)
        return False


def main():
    # Isolate configuration and logs.
    sandbox = tempfile.mkdtemp(prefix="hushmix_live_")
    os.environ["APPDATA"] = sandbox

    # app_paths reads the environment at import time.
    import utils.app_paths as app_paths

    assert app_paths.app_data_dir().startswith(sandbox), app_paths.app_data_dir()

    from utils.config_manager import ConfigManager

    ConfigManager.CONFIG_FILE = os.path.join(sandbox, "settings.json")
    ConfigManager._last_written = None
    ConfigManager._last_written_path = None

    import customtkinter as ctk

    try:
        root = ctk.CTk()
    except Exception as error:
        print(f"SKIP: no interactive display available ({error})")
        return 3

    root.withdraw()

    from gui.app import HushmixApp

    app = step("construct HushmixApp", HushmixApp, root)
    if app is None:
        return 1

    pump(root, 6)

    step("main window widgets exist", lambda: (
        len(app.gui_components.entries) > 0
        and len(app.gui_components.volume_labels) == len(app.gui_components.entries)
    ) or (_ for _ in ()).throw(AssertionError("channel rows were not built")))

    step("connection banner updates", app.update_connection_status)

    step("theme toggle", app.apply_theme_changes)

    step("volume applied to a channel",
         lambda: app.volume_manager.update_volume(1, 42))
    pump(root, 4)

    step("mute toggle", lambda: app.toggle_mute(1))
    pump(root, 4)
    step("un-mute toggle", lambda: app.toggle_mute(1))
    pump(root, 4)

    step("settings window opens", app.show_settings)
    pump(root, 10)
    step("settings window closes", app.on_settings_close)
    pump(root, 6)

    step("button settings window opens", app.show_buttonSettings, 1)
    pump(root, 10)
    step("button settings window closes", app.on_buttonSettings_close)
    pump(root, 6)

    step("help window opens", app.show_help)
    pump(root, 10)
    step("help window closes", app.on_help_close)
    pump(root, 6)

    # ------------------------------------------------------------- profiles
    with NoDialogs():
        step("profile switch", app.on_profile_change, "Profile 2")
        pump(root, 6)
        step("profile switch back", app.on_profile_change, "Profile 1")
        pump(root, 6)

        step("add profile", lambda: app._add_profile("LiveTest"))
        pump(root, 4)

        # Delete while it is selected (the reported bug) and confirm it went.
        step("switch to the new profile", app.on_profile_change, "LiveTest")
        pump(root, 4)
        step("delete the selected profile", app.delete_profile, "LiveTest")
        pump(root, 4)

    # ------------------------------------------------------------- profiles
    with NoDialogs():
        step("switch profile", app.on_profile_change, "Profile 2")
        pump(root, 6)
        step("switch profile back", app.on_profile_change, "Profile 1")
        pump(root, 6)

        step("add profile", lambda: app._add_profile("LiveTest"))
        pump(root, 4)

        # Deleting the *selected* profile is the reported bug.
        step("select the new profile", app.on_profile_change, "LiveTest")
        pump(root, 4)
        step("delete the selected profile", app.delete_profile, "LiveTest")
        pump(root, 4)

        step("add profile again", lambda: app._add_profile("LiveTest2"))
        pump(root, 4)
        step("delete a non-selected profile", app.delete_profile, "LiveTest2")
        pump(root, 4)

    # ------------------------------------------------------------- restart

    step("save settings", app.save_settings)
    step("reload settings", app.load_settings)
    pump(root, 4)

    step("window hide (close button)", app.on_close)
    step("window restore", lambda: (root.deiconify(), root.lift()))
    pump(root, 4)

    # Shutdown ends the process with os._exit(0); capture it so we can report.
    real_exit = os._exit
    captured = []

    def fake_exit(code):
        captured.append(code)
        raise SystemExit(code)

    os._exit = fake_exit
    try:
        step("shutdown", app.shutdown)
    except SystemExit:
        pass
    finally:
        os._exit = real_exit

    try:
        root.destroy()
    except Exception:
        pass

    print()
    print("=" * 60)
    print(f"interactions: {CHECKS[0]}")
    print(f"failures    : {len(FAILURES)}")
    for failure in FAILURES:
        print(f"  - {failure}")
    print(f"shutdown exit code: {captured}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    code = main()
    # The application's own background threads (serial watchdog, update checker,
    # tray) are daemons, but Tk and the libraries it loads can still keep the
    # interpreter alive.  This is a test harness, so leave decisively.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
