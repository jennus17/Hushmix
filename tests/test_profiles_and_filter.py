"""Unit tests for profile isolation, lane ownership and the signal filter.

These do not need Tk or audio hardware: the profile manager talks to the
application through a narrow interface, so a stub app exercises the real
save/load logic.

Covers three reported bugs:

* editing applications and switching profiles mixed one profile's data into
  another (the current profile was read back from the dropdown while the
  channel data still belonged to the outgoing profile);
* the ``current`` lane controlled an application that another lane named
  explicitly, so two sliders fought over the same application;
* a parked slider drifted by a couple of units on its own.

Run with::

    python tests/test_profiles_and_filter.py
"""

import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


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


# ------------------------------------------------------------------ stub types
class StubVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


VAR_SPECS = {
    "mute": (True, False),
    "mute_settings": (True, False),
    "app_launch_enabled": (False, False),
    "app_launch_paths": ("", True),
    "keyboard_shortcut_enabled": (False, False),
    "keyboard_shortcuts": ("", True),
    "mute_button_modes": ("Click", True),
    "app_button_modes": ("Click", True),
    "shortcut_button_modes": ("Click", True),
    "media_control_enabled": (False, False),
    "media_control_actions": ("Play/Pause", True),
    "media_control_button_modes": ("Click", True),
}
BOOLEAN_FIELDS = {"mute", "mute_settings", "app_launch_enabled",
                  "keyboard_shortcut_enabled", "media_control_enabled"}


class StubGUI:
    def __init__(self):
        self.entries = []
        self.volume_labels = []
        self.profile_names = []
        self.selected = None

    def set_profile_names(self, names, current=None):
        self.profile_names = list(names)
        if current:
            self.selected = current

    def refresh_gui(self):
        pass


class StubSettingsManager:
    def __init__(self, app):
        self.app = app
        self.settings_vars = {"current_profile": "Profile 1"}

    def get_setting(self, key, default=None):
        return self.settings_vars.get(key, default)

    def set_setting(self, key, value):
        self.settings_vars[key] = value

    def save_to_config(self):
        return True


class StubApp:
    """The narrow interface ProfileManager actually uses."""

    def __init__(self):
        self.current_apps = [""] * 7
        self.current_mute_state = [False] * 7
        self.muted_state = [False] * 7
        self.previous_volumes = [None] * 7
        self.gui_components = StubGUI()
        self.settings_manager = StubSettingsManager(self)
        for field in VAR_SPECS:
            setattr(self, field, [])

    # --- the helpers ProfileManager delegates to (mirrors gui.app) ---
    def _build_var_list(self, field, values, length):
        stored = list(values) if isinstance(values, (list, tuple)) else []
        default = VAR_SPECS[field][0]
        variables = [StubVar(value) for value in stored[:length]]
        while len(variables) < length:
            variables.append(StubVar(default))
        return variables

    @staticmethod
    def _fit_mute_state(values):
        state = [bool(value) for value in (values or [])][:7]
        while len(state) < 7:
            state.append(False)
        return state

    def _collect_profile_state(self):
        """Snapshot the GUI state, exactly like the real app does."""
        self.current_apps = [entry.get() for entry in self.gui_components.entries] or list(self.current_apps)
        variables = self.settings_manager.settings_vars
        variables["applications"] = list(self.current_apps)
        variables["mute_state"] = list(self.current_mute_state)
        for field in VAR_SPECS:
            variables[field] = [variable.get() for variable in getattr(self, field)]
        return variables

    # --- helpers the tests use to behave like the user ---
    def rebuild_entries(self):
        self.gui_components.entries = [
            StubVar(name) for name in self.current_apps
        ]

    def type_into(self, index, text):
        self.gui_components.entries[index].set(text)


# ---------------------------------------------------------------------- tests
def test_profile_isolation():
    results.section("profile isolation")
    from controllers.profile_manager import ProfileManager
    from utils.config_manager import ConfigManager

    with tempfile.TemporaryDirectory() as folder:
        ConfigManager.CONFIG_FILE = os.path.join(folder, "settings.json")
        ConfigManager._last_written = None
        ConfigManager._last_written_path = None

        app = StubApp()
        manager = ProfileManager(app)
        app.rebuild_entries()

        ConfigManager.add_profile("Alpha")
        ConfigManager.add_profile("Beta")

        # Fill Profile 1.
        app.type_into(1, "base-app")
        manager.save_profile("Profile 1")

        # Fill Alpha via a real switch.
        manager.switch_to("Alpha")
        app.rebuild_entries()
        results.check(
            app.settings_manager.settings_vars["current_profile"] == "Alpha",
            "the switch did not publish the new profile name",
        )
        app.type_into(1, "alpha-app")
        manager.save_profile("Alpha")

        # Fill Beta.
        manager.switch_to("Beta")
        app.rebuild_entries()
        app.type_into(1, "beta-app")
        manager.save_profile("Beta")

        stored = ConfigManager.load_all()["profiles"]
        results.check(
            [a for a in stored["Profile 1"]["applications"] if a] == ["base-app"],
            f"Profile 1 has {stored['Profile 1']['applications']}",
        )
        results.check(
            [a for a in stored["Alpha"]["applications"] if a] == ["alpha-app"],
            f"Alpha has {stored['Alpha']['applications']}",
        )
        results.check(
            [a for a in stored["Beta"]["applications"] if a] == ["beta-app"],
            f"Beta has {stored['Beta']['applications']}",
        )

        # Switch back and forth several times: nothing may move between slots.
        for _ in range(3):
            manager.switch_to("Alpha")
            app.rebuild_entries()
            manager.switch_to("Beta")
            app.rebuild_entries()
            manager.switch_to("Profile 1")
            app.rebuild_entries()

        stored = ConfigManager.load_all()["profiles"]
        results.check(
            [a for a in stored["Profile 1"]["applications"] if a] == ["base-app"],
            f"Profile 1 changed after switching: {stored['Profile 1']['applications']}",
        )
        results.check(
            [a for a in stored["Alpha"]["applications"] if a] == ["alpha-app"],
            f"Alpha changed after switching: {stored['Alpha']['applications']}",
        )
        results.check(
            [a for a in stored["Beta"]["applications"] if a] == ["beta-app"],
            f"Beta changed after switching: {stored['Beta']['applications']}",
        )

        # A save that lands while a switch is in progress must be ignored.
        manager.switch_to("Alpha")
        app.rebuild_entries()
        app.type_into(1, "half-switched")
        manager._switching = True
        try:
            manager.save_applications()
            manager.save_profile("Profile 1")
        finally:
            manager._switching = False

        stored = ConfigManager.load_all()["profiles"]
        results.check(
            [a for a in stored["Profile 1"]["applications"] if a] == ["base-app"],
            "a save during a switch leaked into another profile",
        )

        # Removing a profile must not disturb the others.
        ConfigManager.delete_profile("Beta")
        stored = ConfigManager.load_all()["profiles"]
        results.check("Beta" not in stored, "Beta was not removed")
        results.check(
            [a for a in stored["Alpha"]["applications"] if a] == ["alpha-app"],
            "deleting Beta changed Alpha",
        )
        results.check(
            [a for a in stored["Profile 1"]["applications"] if a] == ["base-app"],
            "deleting Beta changed Profile 1",
        )

        # Deleting the active profile switches first, then removes it.
        manager.switch_to("Alpha")
        app.rebuild_entries()
        replacement = "Profile 1"
        manager.switch_to(replacement)
        ConfigManager.delete_profile("Alpha")
        names = ConfigManager.get_profile_names()
        results.check("Alpha" not in names, f"Alpha survived deletion: {names}")
        results.check(
            manager.current_profile() == replacement,
            f"current profile is {manager.current_profile()!r} after deleting the active one",
        )
        results.check(
            [a for a in ConfigManager.load_all()["profiles"][replacement]["applications"] if a]
            == ["base-app"],
            "the surviving profile was changed by the deletion",
        )


def test_lane_ownership():
    results.section("lane ownership")
    from controllers.audio_controller import AudioController

    resolve = AudioController.resolve_lanes

    # The reported case: firefox named in App 2, "current" in App 3.
    resolved, claimed = resolve(["master", "firefox", "current", "mic"], "firefox.exe")
    results.check(resolved[1] == "firefox", f"App 2 should own firefox: {resolved}")
    results.check(resolved[2] == "", f"the current lane must not act: {resolved}")
    results.check(claimed == {"firefox": 1}, f"claimed: {claimed}")

    # Focusing something else lets the current lane work again.
    resolved, _ = resolve(["master", "firefox", "current", "mic"], "notepad.exe")
    results.check(resolved[2] == "current", f"the current lane should act: {resolved}")

    # A group owns each of its applications.
    resolved, _ = resolve(["", "chrome, firefox", "current"], "firefox.exe")
    results.check(resolved[2] == "", f"a grouped app must be owned: {resolved}")

    # Suffix and case differences do not matter.
    resolved, _ = resolve(["firefox", "current"], "FIREFOX.EXE")
    results.check(resolved[1] == "", f"matching must ignore case/.exe: {resolved}")

    # With no named lane, "current" still works.
    resolved, _ = resolve(["current", "current"], "firefox.exe")
    results.check(resolved == ["current", "current"], f"both lanes should act: {resolved}")

    # No foreground window: nothing to control.
    resolved, _ = resolve(["firefox", "current"], None)
    results.check(resolved[1] == "", f"no foreground window means no action: {resolved}")

    # Special targets are never treated as process names.
    resolved, claimed = resolve(["master", "mic", "system", "current"], "system.exe")
    results.check(claimed == {}, f"special targets must not claim processes: {claimed}")
    results.check(resolved[3] == "current", f"the current lane should act: {resolved}")

    # Blank lanes resolve to nothing.
    resolved, _ = resolve(["", "   ", "current"], "firefox.exe")
    results.check(resolved[0] == "" and resolved[1] == "", f"blank lanes: {resolved}")


def test_signal_filter():
    results.section("signal filter")
    from utils.signal_filter import MedianFilter, MixerSignalFilter

    # Median works for even and odd windows.
    for window in (1, 2, 3, 4, 5, 7, 9):
        median = MedianFilter(window_size=window)
        values = [1, 2, 3, 4, 5, 6, 7]
        output = [median.filter(value) for value in values]
        results.check(
            len(output) == len(values) and all(isinstance(v, (int, float)) for v in output),
            f"median of window {window} produced {output}",
        )

    def quantise(value):
        return int(round(max(0.0, min(100.0, value)) / 2) * 2)

    def run(signal, instance=None):
        instance = instance or MixerSignalFilter()
        return [quantise(instance.filter(value)) for value in signal], instance

    # Parked slider: no visible movement at all.
    for level, noise, seed in ((27.0, 1.4, 1), (5.0, 1.4, 5), (50.0, 2.2, 50), (95.0, 1.4, 95)):
        rng = random.Random(seed)
        parked = [level + rng.gauss(0, noise) for _ in range(200)]
        outputs, _ = run(parked)
        settled = outputs[60:]
        changes = sum(1 for a, b in zip(settled, settled[1:]) if a != b)
        results.check(
            changes <= 2,
            f"parked at {level} with sigma {noise}: {changes} output changes, "
            f"range {max(settled) - min(settled)}",
        )

    # A deliberate step must be followed promptly.
    rng = random.Random(2)
    step = [30.0 + rng.gauss(0, 1.4) for _ in range(40)]
    step += [60.0 + rng.gauss(0, 1.4) for _ in range(60)]
    outputs, _ = run(step)
    reached = next(
        (index - 40 for index, value in enumerate(outputs[40:], start=40) if value >= 58),
        None,
    )
    results.check(
        reached is not None and reached <= 8,
        f"a step took {reached} samples to be followed (expected <= 8)",
    )

    # A slow sweep must land on the right value.
    rng = random.Random(7)
    sweep = [10 + index * 0.5 + rng.gauss(0, 1.4) for index in range(120)]
    outputs, _ = run(sweep)
    expected = quantise(sweep[-1])
    results.check(
        abs(outputs[-1] - expected) <= 2,
        f"sweep ended at {outputs[-1]}, expected about {expected}",
    )

    # A large flick is tracked immediately.
    rng = random.Random(3)
    flick = [27.0 + rng.gauss(0, 1.4) for _ in range(20)]
    flick += [42.0 + rng.gauss(0, 1.4) for _ in range(20)]
    outputs, _ = run(flick)
    results.check(
        outputs[22] == 42,
        f"a flick was not followed immediately: {outputs[20:26]}",
    )

    # Reset forgets the previous reading.
    instance = MixerSignalFilter()
    for _ in range(30):
        instance.filter(20.0)
    instance.reset()
    first = instance.filter(80.0)
    results.check(
        abs(first - 80.0) < 1.0,
        f"after reset the first reading should pass through, got {first}",
    )

    # Settings overrides are honoured, invalid values fall back.
    class FakeSettings:
        def __init__(self, values):
            self.values = values

        def get_setting(self, key, default=None):
            return self.values.get(key, default)

    tuned = MixerSignalFilter.from_settings(FakeSettings({"deadband": 3.5, "median_window": 9}))
    results.check(tuned.deadband == 3.5, f"deadband override ignored: {tuned.deadband}")
    results.check(tuned.median_window == 9, f"median override ignored: {tuned.median_window}")
    results.check(tuned.drift_threshold == 1.0, "an unset tunable should keep its default")

    broken = MixerSignalFilter.from_settings(FakeSettings({"deadband": "wide"}))
    results.check(broken.deadband == 1.6, f"an invalid override was accepted: {broken.deadband}")


def test_profile_switch_is_synchronous():
    """A switch must not be deferrable: the name and the data move together."""
    results.section("switch atomicity")
    from controllers.profile_manager import ProfileManager
    from utils.config_manager import ConfigManager

    with tempfile.TemporaryDirectory() as folder:
        ConfigManager.CONFIG_FILE = os.path.join(folder, "settings.json")
        ConfigManager._last_written = None
        ConfigManager._last_written_path = None

        app = StubApp()
        manager = ProfileManager(app)
        app.rebuild_entries()
        ConfigManager.add_profile("Other")

        app.type_into(1, "first")
        manager.save_profile("Profile 1")

        manager.switch_to("Other")
        app.rebuild_entries()

        # Immediately after the call, name and data must already agree.
        results.check(
            manager.current_profile() == "Other",
            "the switch did not publish the name synchronously",
        )
        results.check(
            [a for a in app.current_apps if a] == [],
            f"the incoming profile's data was not loaded synchronously: {app.current_apps}",
        )
        results.check(
            app.gui_components.selected == "Other",
            f"the dropdown shows {app.gui_components.selected!r}",
        )

        # An echo of the current selection is a no-op, not a re-switch.
        before = ConfigManager.load_all()["profiles"]["Other"]["applications"]
        manager.on_profile_change("Other")
        results.check(
            ConfigManager.load_all()["profiles"]["Other"]["applications"] == before,
            "an echo of the current selection rewrote the profile",
        )


def main():
    tests = [
        test_profile_isolation,
        test_profile_switch_is_synchronous,
        test_lane_ownership,
        test_signal_filter,
    ]
    for test in tests:
        try:
            test()
        except Exception:
            import traceback

            results.failed.append(f"{test.__name__} raised")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"checks passed: {results.passed}")
    print(f"failures    : {len(results.failed)}")
    for failure in results.failed:
        print(f"  - {failure}")
    return 1 if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
