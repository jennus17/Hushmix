"""Regression test: window and content must scale together across monitors.

Scaling is owned by CustomTkinter's ``ScalingTracker``: it polls the window DPI
every 100 ms and, when it changes, calls ``_set_scaling`` on every widget and on
the window.  ``CTk._set_scaling`` then resizes the window from the *scaled*
dimensions.

The application used to fight that: on ``<Configure>`` it called
``tk scaling`` itself and rebuilt the whole GUI.  The window ended up resized
from the scaled dimensions while its widgets were rebuilt at the old scale, so
dragging the window from a 1080p monitor to a 4K one made it grow without its
content keeping up.

This test drives the same scaling path CustomTkinter uses on a monitor change and
asserts that the window request and the widget sizes move together, then that
everything returns to its original size.

Needs an interactive Windows session with the real packages; run with::

    python tests/test_dpi_scaling.py
"""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

FAILURES = []
CHECKS = [0]


def check(condition, message):
    CHECKS[0] += 1
    if condition:
        print(f"ok   {message}")
    else:
        FAILURES.append(message)
        print(f"FAIL {message}")


sandbox = tempfile.mkdtemp(prefix="hushmix_dpi_test_")
os.environ["APPDATA"] = sandbox

from utils.config_manager import ConfigManager  # noqa: E402

ConfigManager.CONFIG_FILE = os.path.join(sandbox, "settings.json")
ConfigManager._last_written = None
ConfigManager._last_written_path = None

import customtkinter as ctk  # noqa: E402

from utils.win_utils import enum_monitors, get_monitor_dpi  # noqa: E402

root = ctk.CTk()
root.withdraw()


def pump(seconds=0.6):
    end = time.time() + seconds
    while time.time() < end:
        root.update_idletasks()
        root.update()
        time.sleep(0.004)


def metrics(app):
    frame = app.gui_components.main_frame
    entry = app.gui_components.entries[0]
    label = app.gui_components.profile_listbox
    return {
        "window_req": (root.winfo_reqwidth(), root.winfo_reqheight()),
        "window_actual": (root.winfo_width(), root.winfo_height()),
        "frame_req": (frame.winfo_reqwidth(), frame.winfo_reqheight()),
        "entry_height": entry.winfo_reqheight(),
        "dropdown_height": label.winfo_reqheight(),
        "tk_scaling": float(root.tk.call("tk", "scaling")),
    }


def settled(app):
    """Window and content size, after any pending correction has run."""
    pump(1.2)
    frame = app.gui_components.main_frame
    return (
        (root.winfo_width(), root.winfo_height()),
        (frame.winfo_reqwidth(), frame.winfo_reqheight()),
    )


def main():
    from gui.app import HushmixApp

    app = HushmixApp(root)
    root.deiconify()
    pump(2.0)

    print("\n== baseline at scale 1.0 ==")
    base = metrics(app)
    for key, value in base.items():
        print(f"  {key:<16} {value}")

    # The window must have been fitted to its content at startup - it does not
    # follow its content on its own (CustomTkinter leaves it at 600x500).
    check(
        base["window_actual"][0] <= base["frame_req"][0] + 2
        and base["window_actual"][1] <= base["frame_req"][1] + 2,
        f"the window {base['window_actual']} was fitted to its content "
        f"{base['frame_req']} at startup",
    )
    check(
        base["window_req"][0] > 0 and base["window_req"][1] > 0,
        "the window has no size",
    )

    # -------------------------------------------------------- real monitor moves
    # This is the path that matters: the window is physically moved onto each
    # monitor and Windows reports the DPI change to the process.
    monitors = sorted(
        enum_monitors(), key=lambda m: get_monitor_dpi(m["left"] + 5, m["top"] + 5)
    )
    if len(monitors) > 1 and get_monitor_dpi(monitors[0]["left"] + 5, monitors[0]["top"] + 5) != get_monitor_dpi(
        monitors[-1]["left"] + 5, monitors[-1]["top"] + 5
    ):
        print("\n== moving the real window between monitors ==")
        sizes = []
        for monitor in (monitors[0], monitors[-1], monitors[0], monitors[-1]):
            root.geometry(f"+{monitor['left'] + 50}+{monitor['top'] + 50}")
            pump(3.0)
            app.window_manager.fit_window_to_content(force=True)
            window, content = settled(app)
            frame = app.gui_components.main_frame
            widget_scale = float(ctk.ScalingTracker.get_widget_scaling(frame))
            print(
                f"  {monitor['width']}x{monitor['height']}: window={window} "
                f"content={content} widget_scale={widget_scale:.2f}"
            )
            check(
                abs(window[0] - content[0]) <= 2 and abs(window[1] - content[1]) <= 2,
                f"on the {monitor['width']}x{monitor['height']} monitor the window "
                f"{window} matches its content {content}",
            )
            sizes.append(window)

        check(
            sizes[1][0] > sizes[0][0] and sizes[1][1] > sizes[0][1],
            f"the window grew on the higher-DPI monitor: {sizes[0]} -> {sizes[1]}",
        )
        check(
            sizes[0] == sizes[2],
            f"returning to the first monitor restored the size: {sizes[0]} vs {sizes[2]}",
        )
        check(
            sizes[1] == sizes[3],
            f"the second monitor is repeatable: {sizes[1]} vs {sizes[3]}",
        )
        check(
            sizes[0] == base["window_actual"],
            f"the low-DPI size matches the startup size: {sizes[0]} vs "
            f"{base['window_actual']}",
        )
    else:
        print("\n(single-DPI setup - the real monitor move cannot be exercised)")

    # ------------------------------------------- repeated polling must not drift
    # Widget scaling is owned by CustomTkinter's DPI detection and the window
    # size by the application.  The failure mode this guards against is the two
    # multiplying: polling repeatedly must not change the widget scaling, and the
    # window must stay matched to its content.
    print("\n== repeated DPI polls must not drift ==")
    root.geometry(f"+{monitors[0]['left'] + 50}+{monitors[0]['top'] + 50}")
    pump(3.0)
    app.window_manager.fit_window_to_content(force=True)
    frame = app.gui_components.main_frame

    first_scale = float(ctk.ScalingTracker.get_widget_scaling(frame))
    first_size = settled(app)
    print(f"  before: widget_scale={first_scale:.2f} window={first_size[0]}")

    for _ in range(5):
        app.window_manager.apply_monitor_scale()
        pump(0.5)
    after_scale = float(ctk.ScalingTracker.get_widget_scaling(frame))
    after_size = settled(app)
    print(f"  after : widget_scale={after_scale:.2f} window={after_size[0]}")

    check(
        abs(after_scale - first_scale) < 0.01,
        f"five polls left the widget scaling unchanged ({first_scale:.2f} -> "
        f"{after_scale:.2f}); a growing value means the DPI is being applied twice",
    )
    check(
        after_size == first_size,
        f"five polls left the window size unchanged: {first_size} -> {after_size}",
    )
    check(
        abs(after_scale - app.window_manager.current_monitor_scale()) < 0.02,
        f"widget scaling ({after_scale:.2f}) still matches the monitor "
        f"({app.window_manager.current_monitor_scale():.2f})",
    )
    check(
        abs(after_size[0][0] - after_size[1][0]) <= 2
        and abs(after_size[0][1] - after_size[1][1]) <= 2,
        f"the window {after_size[0]} still matches its content {after_size[1]}",
    )

    window, content = settled(app)
    check(
        window == base["window_actual"] and content == base["frame_req"],
        f"on the low-DPI monitor the window/content are {window}/{content}, "
        f"expected {base['window_actual']}/{base['frame_req']}",
    )
    check(
        app.gui_components.entries[0].winfo_reqheight() == base["entry_height"],
        f"widgets are their original size: "
        f"{app.gui_components.entries[0].winfo_reqheight()} vs {base['entry_height']}",
    )

    # ------------------------------------------- the banner must be truthful
    print("\n== connection banner ==")
    label = app.gui_components.connection_status_label
    for _ in range(4):
        pump(0.4)
        connected = app.serial_controller.get_connection_status()
        visible = bool(label.winfo_ismapped())
        check(
            connected == (not visible),
            f"banner visible={visible} while serial connected={connected}",
        )

    # After a refresh the banner must still agree with the serial state.
    app.gui_components.refresh_gui()
    pump(0.4)
    connected = app.serial_controller.get_connection_status()
    visible = bool(label.winfo_ismapped())
    check(
        connected == (not visible),
        f"after refresh_gui: banner visible={visible} while connected={connected}",
    )

    # ------------------------------------------------ manual update check button
    print("\n== 'Check now' in the settings window ==")
    settings = None
    try:
        app.show_settings()
        pump(1.2)
        settings = app.settings_window
        check(settings is not None, "the settings window opened")
        if settings is not None:
            check(
                hasattr(settings, "check_for_updates_now"),
                "the settings window exposes a manual update check",
            )

            # Stub the network-touching method and make sure the button reaches it.
            calls = []
            app.version_manager.check_now = lambda: calls.append(1) or True
            settings.check_for_updates_now()
            pump(0.3)
            check(bool(calls), "the button asks the update manager to check")

            status = settings.update_status_label.cget("text")
            check(bool(status), f"the button reports what it is doing: {status!r}")

            # Unavailable manager must not raise.
            app.version_manager.check_now = lambda: False
            settings.check_for_updates_now()
            pump(0.2)
            check(True, "a refused check is handled without raising")
    finally:
        if settings is not None:
            try:
                app.on_settings_close()
            except Exception:
                pass

    # ------------------------------------------------- update-manager integration
    print("\n== update manager wiring ==")
    check(
        callable(getattr(app.version_manager, "save_pending_state", None)),
        "the updater can flush pending settings before replacing the binary",
    )
    check(
        hasattr(app.version_manager, "check_now"),
        "the update manager supports an on-demand check",
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
