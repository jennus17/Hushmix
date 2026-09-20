"""Keyboard shortcut recorder widget.

The recording logic was inlined in ``ButtonSettingsWindow`` with two identical
copies of a 30-entry ``key_mapping`` dictionary (one for ``<Key>`` and one for
``<KeyRelease>``) and a set of ``getattr(self, 'attr', default)`` guards to cope
with attributes that might not exist yet.  It is now a small self-contained
widget that publishes a normalised shortcut such as ``Ctrl+Shift+S``.
"""

import customtkinter as ctk

from utils.logging_setup import get_logger

logger = get_logger("shortcut_recorder")

# Tk keysym -> the name written into the shortcut string.
KEYSYM_ALIASES = {
    "period": ".",
    "comma": ",",
    "semicolon": ";",
    "colon": ":",
    "exclam": "!",
    "question": "?",
    "minus": "-",
    "underscore": "_",
    "equal": "=",
    "plus": "+",
    "bracketleft": "[",
    "bracketright": "]",
    "braceleft": "{",
    "braceright": "}",
    "backslash": "\\",
    "bar": "|",
    "slash": "/",
    "less": "<",
    "greater": ">",
    "quotedbl": '"',
    "apostrophe": "'",
    "grave": "`",
    "asciitilde": "~",
    "at": "@",
    "numbersign": "#",
    "dollar": "$",
    "percent": "%",
    "asciicircum": "^",
    "ampersand": "&",
    "asterisk": "*",
    "parenleft": "(",
    "parenright": ")",
    "space": "Space",
    "Return": "Enter",
    "KP_Enter": "Enter",
    "Escape": "Escape",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "Insert": "Insert",
    "Home": "Home",
    "End": "End",
    "Prior": "PageUp",
    "Next": "PageDown",
    "Tab": "Tab",
}

MODIFIER_KEYSYMS = {
    "Control_L": "Ctrl",
    "Control_R": "Ctrl",
    "Shift_L": "Shift",
    "Shift_R": "Shift",
    "Alt_L": "Alt",
    "Alt_R": "Alt",
    "Meta_L": "Win",
    "Meta_R": "Win",
    "Super_L": "Win",
    "Super_R": "Win",
}

MODIFIER_ORDER = ("Ctrl", "Shift", "Alt", "Win")


class ShortcutRecorder(ctk.CTkFrame):
    """Read-only entry that captures a key combination when clicked.

    Colours come from the owner through :data:`COLOR_KEYS` rather than being
    derived here, so the recorder cannot drift away from the window it sits in.
    Every one of them is optional; the CustomTkinter defaults apply otherwise.
    """

    #: Keyword arguments this widget understands, and where each is applied.
    COLOR_KEYS = (
        "fg_color",
        "label_color",
        "entry_fg_color",
        "entry_border_color",
        "entry_text_color",
        "button_fg_color",
        "button_hover_color",
        "button_text_color",
    )

    def __init__(self, master, on_change=None, **kwargs):
        colors = {key: kwargs.pop(key) for key in self.COLOR_KEYS if key in kwargs}
        super().__init__(master, corner_radius=10, border_width=0, **kwargs)

        self.on_change = on_change
        self.recording = False
        self._enabled = True
        self._modifiers = set()
        self._captured_modifiers = set()
        self._pressed = set()
        self._keys = []

        label = ctk.CTkLabel(
            self,
            text="Click to record shortcut:",
            font=("Segoe UI", 12),
            text_color=colors.get("label_color"),
        )
        label.pack(pady=(5, 5), padx=15, anchor="w")

        self.entry = ctk.CTkEntry(
            self,
            font=("Segoe UI", 12),
            height=30,
            placeholder_text="Press keys here...",
            state="readonly",
            fg_color=colors.get("entry_fg_color"),
            border_color=colors.get("entry_border_color"),
            text_color=colors.get("entry_text_color"),
        )
        self.entry.pack(pady=(0, 5), padx=15, fill="x")
        self.entry.bind("<Button-1>", self.start_recording)

        self.clear_button = ctk.CTkButton(
            self,
            text="Clear",
            font=("Segoe UI", 12),
            command=self.clear,
            width=80,
            height=30,
            fg_color=colors.get("button_fg_color"),
            hover_color=colors.get("button_hover_color"),
            text_color=colors.get("button_text_color"),
        )
        self.clear_button.pack(pady=(0, 8), padx=15, anchor="w")

    # ------------------------------------------------------------------ state

    def set_value(self, shortcut):
        """Display a shortcut without starting a recording session."""
        self._write(shortcut or "")

    def clear(self):
        """Erase the recorded shortcut."""
        self._stop()
        self._write("")
        if self.on_change:
            self.on_change("")

    def _write(self, text):
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        if text:
            self.entry.insert(0, text)
        self.entry.configure(state="readonly" if self._enabled else "disabled")

    def set_widget_state(self, enabled):
        """Enable or disable the whole recorder."""
        self._enabled = bool(enabled)
        self.entry.configure(state="readonly" if enabled else "disabled")
        self.clear_button.configure(state="normal" if enabled else "disabled")
        if not enabled:
            self._stop()

    # -------------------------------------------------------------- recording

    def start_recording(self, event=None):
        """Capture the next key combination."""
        if not self._enabled:
            return

        self.recording = True
        self._modifiers.clear()
        self._captured_modifiers.clear()
        self._pressed.clear()
        self._keys = []
        self._write("Press keys... (Escape to cancel)")

        self.window = self.winfo_toplevel()
        self.window.focus_force()
        self._bind_id = self.window.bind("<Key>", self._on_key_press, add="+")
        self._bind_release_id = self.window.bind(
            "<KeyRelease>", self._on_key_release, add="+"
        )

    def _stop(self):
        self.recording = False
        window = getattr(self, "window", None)
        if window is not None:
            for sequence, bind_id in (
                ("<Key>", getattr(self, "_bind_id", None)),
                ("<KeyRelease>", getattr(self, "_bind_release_id", None)),
            ):
                if bind_id:
                    try:
                        window.unbind(sequence, bind_id)
                    except Exception as error:
                        logger.debug("Could not unbind %s: %s", sequence, error)
        self._bind_id = None
        self._bind_release_id = None
        self._modifiers.clear()
        self._captured_modifiers.clear()
        self._pressed.clear()
        self._keys = []

    @staticmethod
    def _normalise(keysym):
        if keysym in MODIFIER_KEYSYMS:
            return MODIFIER_KEYSYMS[keysym], True
        if keysym in KEYSYM_ALIASES:
            return KEYSYM_ALIASES[keysym], False
        if len(keysym) == 1:
            return keysym.upper(), False
        if keysym.startswith("F") and keysym[1:].isdigit():
            return keysym, False
        return keysym, False

    def _on_key_press(self, event):
        if not self.recording:
            return

        if event.keysym == "Escape":
            self._write("")
            self._stop()
            return

        key, is_modifier = self._normalise(event.keysym)

        if is_modifier:
            self._modifiers.add(key)
            self._captured_modifiers.add(key)
            preview = self._build()
            if preview:
                self._write(f"{preview} (Escape to cancel)")
            return

        self._pressed.add(key)
        if key not in self._keys:
            self._keys.append(key)

        preview = self._build()
        self._write(f"{preview} (Escape to cancel)")

    def _on_key_release(self, event):
        if not self.recording:
            return

        key, is_modifier = self._normalise(event.keysym)

        if is_modifier:
            self._modifiers.discard(key)
            return

        self._pressed.discard(key)

        if not self._pressed and self._keys:
            shortcut = self._build()
            self._write(shortcut)
            self._stop()
            if self.on_change:
                self.on_change(shortcut)

    def _build(self):
        """Assemble ``Ctrl+Shift+S`` from the recorded modifiers and keys.

        Modifiers are remembered for the whole session: users routinely release
        Ctrl before Shift when letting go of a combination.
        """
        modifiers = [name for name in MODIFIER_ORDER if name in self._captured_modifiers]
        return "+".join(modifiers + self._keys)
