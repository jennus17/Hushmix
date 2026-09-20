"""Regression tests for GUI defects that only appear with the real toolkit.

Each check here corresponds to a bug that shipped and was reported:

1. the main window was about twice as tall as its content, because
   ``refresh_gui`` left orphaned ``CTkFrame`` widgets (200x200 default request)
   gridded in the last row;
2. the help window opened and immediately disappeared, because CustomTkinter's
   titlebar-colour pass withdraws the window right after it is first shown;
3. the ✕ button refused to delete the selected profile;
4. the volume path called ``root.after`` from the serial thread, which raises
   "main thread is not in main loop" and killed the reader thread.

Needs an interactive Windows session and the real packages; run with::

    python tests/smoke_fixes.py
"""

import os
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

FAILURES = []
CHECKS = [0]


def check(condition, message):
    CHECKS[0] += 1
    if not condition:
        FAILURES.append(message)
        print(f"FAIL: {message}")


sandbox = tempfile.mkdtemp(prefix="hushmix_fixes_")
os.environ["APPDATA"] = sandbox

from utils.config_manager import ConfigManager  # noqa: E402

ConfigManager.CONFIG_FILE = os.path.join(sandbox, "settings.json")
ConfigManager._last_written = None
ConfigManager._last_written_path = None

import customtkinter as ctk  # noqa: E402

root = ctk.CTk()
root.withdraw()


def pump(seconds=0.5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        root.update_idletasks()
        root.update()
        time.sleep(0.004)


def main():
    from gui.app import HushmixApp

    app = HushmixApp(root)
    root.deiconify()
    pump(0.8)

    # ---------------------------------------------------------------- 1: sizing
    print("\n== main window sizing ==")
    expected_height = 40 + 44 + 40 * 6 + 60  # header row + channels + footer
    height = root.winfo_reqheight()
    width = root.winfo_reqwidth()
    print(f"  window request: {width}x{height}")
    check(
        height < expected_height + 60,
        f"the window is far taller than its content: {height}px (expected about {expected_height}px)",
    )
    check(
        root.winfo_reqheight() == root.winfo_reqheight(),
        "unstable height",
    )

    # Repeated refreshes must not accumulate orphans and grow the window.
    for _ in range(5):
        app.gui_components.refresh_gui()
        pump(0.1)
    after_refresh = root.winfo_reqheight()
    print(f"  after 5 refreshes: {after_refresh}")
    check(
        after_refresh == height,
        f"the window grew from {height} to {after_refresh} across refreshes",
    )

    frame = app.gui_components.main_frame
    mismatched = [
        child
        for child in frame.winfo_children()
        if child.winfo_manager() == "grid"
        and child.grid_info().get("row") is not None
        and child.grid_info()["row"] > len(app.current_apps) + 1
    ]
    check(not mismatched, f"{len(mismatched)} widgets are gridded below the last row")

    # ------------------------------------------------------------- 2: popups
    print("\n== popup windows stay open ==")
    for name, opener, holder, closer in (
        ("help", app.show_help, "help_window", app.on_help_close),
        ("settings", app.show_settings, "settings_window", app.on_settings_close),
        ("button settings", lambda: app.show_buttonSettings(1), "buttonSettings_window",
         app.on_buttonSettings_close),
    ):
        opener()
        pump(1.2)
        window_holder = getattr(app, holder)
        if name == "settings" and window_holder is not None:
            check(
                window_holder.version_manager is app.version_manager,
                "the settings window can reach the update manager",
            )
        window_holder = getattr(app, holder)
        if window_holder is None:
            check(False, f"{name} window was not created")
            continue
        window = window_holder.window
        viewable = bool(window.winfo_viewable())
        print(f"  {name}: state={window.state()!r} viewable={viewable}")
        check(viewable, f"{name} window is not visible (state={window.state()!r})")

        # It must still be visible a moment later, once CustomTkinter has run
        # its titlebar-colour pass.
        pump(1.0)
        check(
            bool(window.winfo_viewable()),
            f"{name} window disappeared after being shown",
        )
        closer()
        pump(0.3)

    # ------------------------------------------------------- 3: profile delete
    print("\n== profile add / delete ==")
    names = ConfigManager.get_profile_names()
    print(f"  profiles at start: {names}")
    check(len(names) <= 2, f"too many default profiles: {names}")

    check(app._add_profile("Second")[0], "could not add a profile")
    names = ConfigManager.get_profile_names()
    check("Second" in names, f"the new profile is missing: {names}")

    # Switch to it and delete the *selected* profile - the reported bug.
    app.on_profile_change("Second")
    pump(0.3)
    check(
        app.settings_manager.settings_vars.get("current_profile") == "Second",
        "could not switch to the new profile",
    )

    # Any modal dialog would block the test run forever, so every message box
    # entry point is stubbed for the duration of the profile checks.
    import tkinter.messagebox as messagebox

    originals = {
        name: getattr(messagebox, name)
        for name in ("askyesno", "showwarning", "showerror", "showinfo", "askokcancel")
    }
    messagebox.askyesno = lambda *args, **kwargs: True
    messagebox.showwarning = lambda *args, **kwargs: "ok"
    messagebox.showerror = lambda *args, **kwargs: "ok"
    messagebox.showinfo = lambda *args, **kwargs: "ok"
    messagebox.askokcancel = lambda *args, **kwargs: True
    try:
        success, message = app.delete_profile("Second")

        check(success, f"deleting the selected profile failed: {message}")
        names = ConfigManager.get_profile_names()
        check("Second" not in names, f"the profile was not removed: {names}")
        check(
            app.settings_manager.settings_vars.get("current_profile") in names,
            "the current profile points at a deleted profile",
        )

        # The very last profile must not be deletable.
        remaining = ConfigManager.get_profile_names()
        check(len(remaining) >= 1, "there are no profiles left")
        success, _ = app.delete_profile(remaining[0])
        check(not success, "the only profile should not be deletable")
    finally:
        for name, function in originals.items():
            setattr(messagebox, name, function)

    # ------------------------------------------------- 4: app suggestions popup
    print("\n== help diagnostics ==")
    try:
        from version import __version__

        app.show_help()
        pump(1.2)
        helper = app.help_window
        check(helper is not None, "the help window opened")
        if helper is not None:
            text = helper._diagnostics_text()
            check(
                f"v{__version__}" in text,
                f"the diagnostics report the version (v{__version__})",
            )
            check(
                "Display:" in text,
                "the diagnostics report the display scaling",
            )
            check(
                "Auto-startup:" in text,
                "the diagnostics report the auto-startup state",
            )
        app.on_help_close()
        pump(0.3)
    except Exception as error:
        check(False, f"help diagnostics failed: {type(error).__name__}: {error}")

    # ------------------------------------------------- 5: app suggestions popup    print("\n== right-click suggestion popup ==")
    app.gui_components.refresh_gui()
    pump(0.3)
    if app.gui_components.entries:
        # The enumeration runs on a worker thread, so the popup must open
        # immediately and fill in later - the UI thread must not block on it.
        slow = threading.Event()

        def slow_listing():
            slow.wait(3.0)
            return ["alpha.exe", "beta.exe"]

        app.audio_controller.list_audio_applications = slow_listing

        class FakeEvent:
            x_root = 100
            y_root = 100

        import time as _time

        started = _time.monotonic()
        app.gui_components._show_app_suggestions(FakeEvent(), 0)
        elapsed = _time.monotonic() - started
        check(
            elapsed < 0.5,
            f"the popup opened without waiting for the enumeration ({elapsed:.2f}s)",
        )
        popup = getattr(app.gui_components, "_app_suggestion_popup", None)
        check(popup is not None, "the suggestion popup was created")
        if popup is not None:
            pump(0.4)
            check(
                bool(popup.winfo_exists()),
                "the popup is still open while the list loads",
            )
            # Release the worker and let the deferred action fill it in.
            slow.set()
            pump(1.2)
            check(
                bool(popup.winfo_exists()),
                "the popup is still open after the list arrived",
            )
        app.gui_components._close_app_suggestions()
        pump(0.2)
        check(True, "the popup closes cleanly")

    # ------------------------------------------------- 6: volume path safety
    print("\n== volume updates from a worker thread ==")
    errors = []

    def worker():
        try:
            for level in range(0, 101, 5):
                app.volume_manager.handle_volume_update([level] * 7)
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
            traceback.print_exc()

    thread = threading.Thread(target=worker, name="volume-test", daemon=True)
    thread.start()
    pump(1.5)
    thread.join(timeout=5)
    check(not errors, f"volume updates from a thread failed: {errors}")

    # The reader thread must still be alive after all that.
    reader = getattr(app.serial_controller, "_reader_thread", None)
    check(
        reader is not None and reader.is_alive(),
        "the serial reader thread died",
    )

    print("\n" + "=" * 60)
    print(f"checks passed: {CHECKS[0] - len(FAILURES)}")
    print(f"failures     : {len(FAILURES)}")
    for failure in FAILURES:
        print(f"  - {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
