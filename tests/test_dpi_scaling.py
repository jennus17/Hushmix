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


def force_scale(scale):
    """Apply a scaling factor exactly the way ScalingTracker does.

    CustomTkinter exposes the two factors the tracker multiplies the detected
    monitor scale by, so driving them is equivalent to the window moving to a
    monitor whose DPI differs by this factor.
    """
    ctk.set_widget_scaling(scale)
    ctk.set_window_scaling(scale)
    pump(1.2)


def main():
    from gui.app import HushmixApp

    app = HushmixApp(root)
    root.deiconify()
    pump(1.2)

    print("\n== baseline at scale 1.0 ==")
    base = metrics(app)
    for key, value in base.items():
        print(f"  {key:<16} {value}")

    check(
        base["window_req"] == base["window_actual"],
        f"window request {base['window_req']} does not match the actual size "
        f"{base['window_actual']}",
    )
    check(
        base["window_req"][0] > 0 and base["window_req"][1] > 0,
        "the window has no size",
    )

    # ------------------------------------------------------------- scale 1.75
    print("\n== scaled to 1.75 (4K-class monitor) ==")
    force_scale(1.75)
    scaled = metrics(app)
    for key, value in scaled.items():
        print(f"  {key:<16} {value}")

    width_ratio = scaled["window_req"][0] / base["window_req"][0]
    height_ratio = scaled["window_req"][1] / base["window_req"][1]
    entry_ratio = scaled["entry_height"] / base["entry_height"]
    dropdown_ratio = scaled["dropdown_height"] / base["dropdown_height"]

    check(
        abs(width_ratio - 1.75) < 0.06,
        f"the window width scaled by {width_ratio:.2f}, expected 1.75 "
        f"({base['window_req'][0]} -> {scaled['window_req'][0]})",
    )
    check(
        abs(height_ratio - 1.75) < 0.06,
        f"the window height scaled by {height_ratio:.2f}, expected 1.75 "
        f"({base['window_req'][1]} -> {scaled['window_req'][1]})",
    )
    check(
        abs(entry_ratio - 1.75) < 0.06,
        f"the channel fields scaled by {entry_ratio:.2f}, expected 1.75 "
        f"({base['entry_height']} -> {scaled['entry_height']})",
    )
    check(
        abs(dropdown_ratio - 1.75) < 0.06,
        f"the profile dropdown scaled by {dropdown_ratio:.2f}, expected 1.75 "
        f"({base['dropdown_height']} -> {scaled['dropdown_height']})",
    )
    check(
        abs(width_ratio - entry_ratio) < 0.12,
        f"the window ({width_ratio:.2f}) and its content ({entry_ratio:.2f}) "
        "scaled by different amounts - this is the reported bug",
    )
    check(
        abs(height_ratio - entry_ratio) < 0.12,
        f"the window height ({height_ratio:.2f}) and its content ({entry_ratio:.2f}) "
        "scaled by different amounts",
    )

    # A scaled window must not clip its content.
    check(
        scaled["frame_req"][1] <= scaled["window_req"][1] + 2,
        f"the content ({scaled['frame_req'][1]}px) is taller than the window "
        f"({scaled['window_req'][1]}px) - it would be cut off",
    )

    # ---------------------------------------------------------- back to 1.0
    print("\n== back to 1.0 ==")
    force_scale(1.0)
    restored = metrics(app)
    for key, value in restored.items():
        print(f"  {key:<16} {value}")

    check(
        restored["window_req"] == base["window_req"],
        f"the window did not return to its original size: "
        f"{restored['window_req']} vs {base['window_req']}",
    )
    check(
        restored["entry_height"] == base["entry_height"],
        f"widgets did not return to their original size: "
        f"{restored['entry_height']} vs {base['entry_height']}",
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
