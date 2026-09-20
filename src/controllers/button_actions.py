"""Hardware button behaviour: mute, app launch, shortcuts and media keys.

This ran on the serial reader thread, where blocking calls (``pyautogui`` waits
for the input queue, ``Popen`` waits for process creation) stalled packet
reading, and where touching Tk state was undefined behaviour.  Actions are now
queued to the GUI thread.

Shortcut parsing was also rewritten.  The old code switched on
``shortcut.count('+') >= 2`` and then re-split the string, which handled
``Ctrl+Shift+S`` by accident and broke simpler combinations; modifiers such as
``Win`` were lower-cased to a key name pyscreeze does not know.
"""

import os
import subprocess
import threading
import time

import customtkinter as ctk
import pyautogui

from utils.logging_setup import get_logger

logger = get_logger("button_actions")

#: Names accepted in a recorded shortcut -> pyautogui key.
MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "win": "winleft",
    "windows": "winleft",
    "super": "winleft",
    "meta": "winleft",
    "cmd": "winleft",
}

#: Special (non-alphanumeric) key names -> pyautogui key.
SPECIAL_KEY_ALIASES = {
    "enter": "enter",
    "return": "enter",
    "tab": "tab",
    "space": "space",
    "spacebar": "space",
    "escape": "esc",
    "esc": "esc",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "insert": "insert",
    "ins": "insert",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "prior": "pageup",
    "next": "pagedown",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "printscreen": "printscreen",
    "prtsc": "printscreen",
    "pause": "pause",
    "capslock": "capslock",
    "numlock": "numlock",
    "scrolllock": "scrolllock",
    "apps": "apps",
    "menu": "apps",
}

MODIFIER_KEYS = frozenset({"ctrl", "shift", "alt", "winleft", "winright", "win"})

MEDIA_KEY_MAPPING = {
    "Play/Pause": "playpause",
    "Next Track": "nexttrack",
    "Previous Track": "prevtrack",
}

BUTTON_VOLUME_OFFSET = 1


def _pyautogui_key_names():
    """Set of key names pyscreeze accepts, or an empty set if unavailable."""
    names = getattr(pyautogui, "KEY_NAMES", None) or getattr(
        pyautogui, "KEYBOARD_KEYS", None
    )
    return set(names) if names else set()


def normalize_key(token):
    """Map a recorded key token to a pyautogui key name, or ``None``."""
    if token is None:
        return None

    token = token.strip()
    if not token:
        return None

    lowered = token.lower()

    if lowered in MODIFIER_ALIASES:
        return MODIFIER_ALIASES[lowered]
    if lowered in SPECIAL_KEY_ALIASES:
        return SPECIAL_KEY_ALIASES[lowered]
    if lowered.startswith("f") and lowered[1:].isdigit():
        if 1 <= int(lowered[1:]) <= 24:
            return lowered

    # The recorder writes shifted punctuation using its symbol (e.g. "!").
    known = _pyautogui_key_names()
    if known:
        if lowered in known:
            return lowered
        symbol_aliases = {
            "!": "!",
            "+": "add",
            "(": "(",
            ")": ")",
            "*": "multiply",
        }
        alias = symbol_aliases.get(token)
        if alias and alias in known:
            return alias
        return None

    # No key list available: pass single characters through, drop the rest.
    return lowered if len(lowered) == 1 else None


def parse_shortcut(shortcut):
    """Split ``"Ctrl+Shift+S"`` into modifiers and regular keys.

    Returns ``(modifiers, keys, unknown)`` where *unknown* holds tokens that
    could not be mapped.
    """
    if not shortcut:
        return [], [], []

    tokens = [token for token in str(shortcut).split("+") if token.strip()]
    modifiers = []
    keys = []
    unknown = []

    for token in tokens:
        key = normalize_key(token)
        if key is None:
            unknown.append(token.strip())
            continue
        if key in MODIFIER_KEYS:
            if key not in modifiers:
                modifiers.append(key)
        else:
            keys.append(key)

    return modifiers, keys, unknown


class ButtonActions:
    def __init__(self, app_instance):
        self.app = app_instance
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------ dispatching

    def _submit(self, function, *args):
        """Run *function* on the GUI thread when possible."""
        deferred = getattr(self.app, "deferred_actions", None)
        if deferred is not None:
            return deferred.submit(function, *args)
        # No deferrer configured (e.g. a unit test): run inline.
        return function(*args)

    # ------------------------------------------------------------- mute toggle

    def _toggle_mute(self, volume_index):
        self.app.toggle_mute(volume_index)

    # --------------------------------------------------------- app launching

    def launch_application(self, index):
        """Start the executable configured for a button."""
        try:
            if index >= len(self.app.app_launch_paths):
                return
            app_path = self.app.app_launch_paths[index].get()
            if not app_path or not os.path.exists(app_path):
                logger.warning("Application path not found: %r", app_path)
                return

            workdir = os.path.dirname(app_path) or None
            if hasattr(os, "startfile"):
                # Preferred on Windows: no shell, no quoting pitfalls.
                os.startfile(app_path, "open")  # noqa: S606 - user-chosen path
            else:  # pragma: no cover - non-Windows fallback
                subprocess.Popen([app_path], cwd=workdir)
            logger.info("Launched %s", app_path)
        except Exception as error:
            logger.warning("Error launching application: %s", error)

    # ------------------------------------------------------ keyboard shortcuts

    def send_keyboard_shortcut(self, index):
        """Send the recorded shortcut for a button."""
        try:
            if index >= len(self.app.keyboard_shortcuts):
                return
            shortcut = self.app.keyboard_shortcuts[index].get()
            if not shortcut:
                return

            modifiers, keys, unknown = parse_shortcut(shortcut)
            if unknown:
                logger.warning(
                    "Ignoring unsupported key(s) %s in shortcut %r", unknown, shortcut
                )
            if not modifiers and not keys:
                return

            time.sleep(0.05)

            for modifier in modifiers:
                pyautogui.keyDown(modifier)
                time.sleep(0.01)

            try:
                if keys:
                    pyautogui.press(keys)
                elif modifiers:
                    # A modifiers-only shortcut (e.g. "Ctrl") is pressed once.
                    pyautogui.press(modifiers[-1])
            finally:
                for modifier in reversed(modifiers):
                    pyautogui.keyUp(modifier)
                    time.sleep(0.01)

            logger.debug("Sent keyboard shortcut %r", shortcut)
        except Exception as error:
            logger.warning("Error sending keyboard shortcut: %s", error)
            # Never leave a modifier stuck down.
            try:
                for modifier in ("ctrl", "shift", "alt", "winleft"):
                    pyautogui.keyUp(modifier)
            except Exception:
                pass

    # ----------------------------------------------------------- media control

    def send_media_control(self, index):
        """Send the configured media key."""
        try:
            if index >= len(self.app.media_control_actions):
                return
            action = self.app.media_control_actions[index].get()
            if not action:
                return

            media_key = MEDIA_KEY_MAPPING.get(action)
            if not media_key:
                logger.warning("Unknown media control action: %r", action)
                return

            pyautogui.press(media_key)
            logger.debug("Sent media control %r", action)
        except Exception as error:
            logger.warning("Error sending media control: %s", error)

    # ------------------------------------------------------- hardware dispatch

    def handle_button_update(self, button_states):
        """React to a button packet from the mixer (runs on the serial thread)."""
        try:
            states = [int(state) for state in button_states]
        except (TypeError, ValueError) as error:
            logger.debug("Ignoring malformed button states %r: %s", button_states, error)
            return

        app = self.app
        num_buttons = len(states)
        with self._state_lock:
            self._ensure_state_sized(num_buttons)

            for index, (current, previous) in enumerate(
                zip(states, list(app.last_button_states))
            ):
                if current > 0 and previous == 0:
                    self._handle_press(index, current)

            app.last_button_states = states

    def _ensure_state_sized(self, num_buttons):
        """Grow the per-button state lists to match the hardware."""
        app = self.app
        num_apps = len(app.current_apps)

        if not getattr(app, "last_button_states", None) or len(app.last_button_states) != num_buttons:
            app.last_button_states = [0] * num_buttons

        if not getattr(app, "mute", None) or len(app.mute) != num_buttons:
            app.mute = [ctk.BooleanVar(value=True) for _ in range(num_buttons)]

        if not getattr(app, "muted_state", None) or len(app.muted_state) != num_apps:
            if len(getattr(app, "current_mute_state", [])) == num_apps:
                app.muted_state = list(app.current_mute_state)
            else:
                app.muted_state = [False] * num_apps

    @staticmethod
    def _mode_matches(mode, current):
        """Whether a press value triggers the configured button mode."""
        if mode == "Click":
            return current == 1
        if mode == "Double Click":
            return current == 3
        if mode == "Hold":
            return current == 2
        return False

    def _get_mode(self, modes, index, default="Click"):
        if index < len(modes):
            return modes[index].get()
        return default

    def _handle_press(self, index, current):
        """Run every action enabled for button *index* (0-based).

        The button settings window is opened with the same 0-based index that
        the GUI's ⚙ button uses, so the settings shown always belong to the
        button that was pressed.
        """
        app = self.app
        # Button 0 sits next to channel 1: the first slider is reserved for the
        # master volume, so mute/edit actions are offset by one.
        volume_index = index + BUTTON_VOLUME_OFFSET

        if (
            index < len(app.mute)
            and app.mute[index].get()
            and volume_index < len(app.muted_state)
        ):
            if self._mode_matches(self._get_mode(app.mute_button_modes, index), current):
                self._submit(self._toggle_mute, volume_index)

        if (
            index < len(app.app_launch_enabled)
            and app.app_launch_enabled[index].get()
            and index < len(app.app_launch_paths)
            and app.app_launch_paths[index].get()
        ):
            if self._mode_matches(self._get_mode(app.app_button_modes, index), current):
                self._submit(self.launch_application, index)

        if (
            index < len(app.keyboard_shortcut_enabled)
            and app.keyboard_shortcut_enabled[index].get()
            and index < len(app.keyboard_shortcuts)
            and app.keyboard_shortcuts[index].get()
        ):
            if self._mode_matches(
                self._get_mode(app.shortcut_button_modes, index), current
            ):
                self._submit(self.send_keyboard_shortcut, index)

        if (
            index < len(app.media_control_enabled)
            and app.media_control_enabled[index].get()
            and index < len(app.media_control_actions)
            and app.media_control_actions[index].get()
        ):
            if self._mode_matches(
                self._get_mode(app.media_control_button_modes, index), current
            ):
                self._submit(self.send_media_control, index)
