"""Per-button settings window.

Rewritten to remove the duplicated shortcut-recording implementation, the
copy-pasted "grow the list until index fits" blocks (identical in eleven
places) and the manual window resizing that ran three times per toggle.  It now
uses :class:`gui.shortcut_recorder.ShortcutRecorder` and
:class:`gui.base_window.BaseWindow`.

The index used here is the *button* index (0-based) - the same index the GUI's
⋮ button and the serial button packets use - so the settings shown always
belong to the button that was pressed.
"""

import os
from tkinter import filedialog

import customtkinter as ctk

from gui.base_window import BaseWindow
from gui.shortcut_recorder import ShortcutRecorder
from utils.color_utils import darken_color, get_windows_accent_color
from utils.logging_setup import get_logger

logger = get_logger("button_settings")

BUTTON_MODES = ["Click", "Double Click", "Hold"]
MEDIA_ACTIONS = ["Play/Pause", "Next Track", "Previous Track"]


class ButtonSettingsWindow(BaseWindow):
    window_name = "button settings window"
    default_size = (460, 560)

    def __init__(
        self,
        parent,
        index,
        mute,
        app_launch_enabled,
        app_launch_paths,
        keyboard_shortcut_enabled,
        keyboard_shortcuts,
        mute_button_modes,
        app_button_modes,
        shortcut_button_modes,
        media_control_enabled,
        media_control_actions,
        media_control_button_modes,
        on_close,
    ):
        super().__init__(parent, on_close=on_close)

        self.index = index
        self.mute = mute
        self.app_launch_enabled = app_launch_enabled
        self.app_launch_paths = app_launch_paths
        self.keyboard_shortcut_enabled = keyboard_shortcut_enabled
        self.keyboard_shortcuts = keyboard_shortcuts
        self.mute_button_modes = mute_button_modes
        self.app_button_modes = app_button_modes
        self.shortcut_button_modes = shortcut_button_modes
        self.media_control_enabled = media_control_enabled
        self.media_control_actions = media_control_actions
        self.media_control_button_modes = media_control_button_modes

        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)
        self.normal_font_size = 14

        self._ensure_state()
        self.build(f"Button Settings - Button {index + 1}")
        self.build_gui()
        self.show()
        self.apply_dpi_scaling()

    # ------------------------------------------------------------------- state

    @staticmethod
    def _grow(values, index, factory):
        """Pad *values* up to and including *index*."""
        while len(values) <= index:
            values.append(factory())

    def _ensure_state(self):
        """Make sure every list has an entry for this button."""
        index = self.index
        self._grow(self.mute, index, lambda: ctk.BooleanVar(value=True))
        self._grow(self.app_launch_enabled, index, lambda: ctk.BooleanVar(value=False))
        self._grow(self.app_launch_paths, index, lambda: ctk.StringVar(value=""))
        self._grow(self.keyboard_shortcut_enabled, index, lambda: ctk.BooleanVar(value=False))
        self._grow(self.keyboard_shortcuts, index, lambda: ctk.StringVar(value=""))
        self._grow(self.mute_button_modes, index, lambda: ctk.StringVar(value="Click"))
        self._grow(self.app_button_modes, index, lambda: ctk.StringVar(value="Click"))
        self._grow(self.shortcut_button_modes, index, lambda: ctk.StringVar(value="Click"))
        self._grow(self.media_control_enabled, index, lambda: ctk.BooleanVar(value=False))
        self._grow(self.media_control_actions, index, lambda: ctk.StringVar(value="Play/Pause"))
        self._grow(self.media_control_button_modes, index, lambda: ctk.StringVar(value="Click"))

    # ------------------------------------------------------------------ layout

    def build_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=0)

        self._build_mute_row(row=0)
        self._build_app_launch_row(row=1)
        self._build_shortcut_row(row=3)
        self._build_media_row(row=5)

        self._refresh_visibility()

    def _add_checkbox(self, row, text, variable, command):
        checkbox = ctk.CTkCheckBox(
            self.frame,
            text=text,
            variable=variable,
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=command,
        )
        checkbox.grid(row=row, column=0, pady=10, padx=15, sticky="w")
        return checkbox

    def _add_mode_dropdown(self, row, variable):
        dropdown = ctk.CTkOptionMenu(
            self.frame,
            values=BUTTON_MODES,
            variable=variable,
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=150,
            height=30,
            corner_radius=10,
        )
        dropdown.grid(row=row, column=1, pady=10, padx=15, sticky="e")
        return dropdown

    def _add_panel(self, row):
        panel = ctk.CTkFrame(self.frame, corner_radius=10, border_width=0)
        panel.grid(row=row, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")
        return panel

    def _build_mute_row(self, row):
        self.mute_checkbox = self._add_checkbox(
            row, "Mute", self.mute[self.index], self._refresh_visibility
        )
        self.mute_mode_dropdown = self._add_mode_dropdown(
            row, self.mute_button_modes[self.index]
        )

    def _build_app_launch_row(self, row):
        self.app_launch_checkbox = self._add_checkbox(
            row, "Launch Application", self.app_launch_enabled[self.index], self._refresh_visibility
        )
        self.app_mode_dropdown = self._add_mode_dropdown(
            row, self.app_button_modes[self.index]
        )

        self.file_panel = self._add_panel(row + 1)

        self.path_label = ctk.CTkLabel(
            self.file_panel, text="No application selected", font=("Segoe UI", 12), anchor="w"
        )
        self.path_label.pack(pady=(6, 4), padx=15, fill="x")

        self.browse_button = ctk.CTkButton(
            self.file_panel,
            text="Browse",
            font=("Segoe UI", 12),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.browse_file,
            width=80,
            height=30,
        )
        self.browse_button.pack(pady=(0, 8), padx=15, anchor="w")

    def _build_shortcut_row(self, row):
        self.shortcut_checkbox = self._add_checkbox(
            row, "Keyboard Shortcut", self.keyboard_shortcut_enabled[self.index],
            self._refresh_visibility,
        )
        self.shortcut_mode_dropdown = self._add_mode_dropdown(
            row, self.shortcut_button_modes[self.index]
        )

        self.shortcut_recorder = ShortcutRecorder(
            self.frame, on_change=self._on_shortcut_recorded
        )
        self.shortcut_recorder.grid(
            row=row + 1, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew"
        )
        self.shortcut_recorder.set_value(self.keyboard_shortcuts[self.index].get())

    def _build_media_row(self, row):
        self.media_control_checkbox = self._add_checkbox(
            row, "Media Control", self.media_control_enabled[self.index],
            self._refresh_visibility,
        )
        self.media_mode_dropdown = self._add_mode_dropdown(
            row, self.media_control_button_modes[self.index]
        )

        self.media_panel = self._add_panel(row + 1)

        ctk.CTkLabel(
            self.media_panel, text="Media Action:", font=("Segoe UI", 12), anchor="w"
        ).pack(pady=(6, 4), padx=15, fill="x")

        self.media_action_dropdown = ctk.CTkOptionMenu(
            self.media_panel,
            values=MEDIA_ACTIONS,
            variable=self.media_control_actions[self.index],
            font=("Segoe UI", 12),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=200,
            height=30,
            corner_radius=10,
        )
        self.media_action_dropdown.pack(pady=(0, 8), padx=15, anchor="w")

    # --------------------------------------------------------------- behaviour

    def _refresh_visibility(self):
        """Show or hide the detail panels for the enabled actions."""
        app_enabled = self.app_launch_enabled[self.index].get()
        shortcut_enabled = self.keyboard_shortcut_enabled[self.index].get()
        media_enabled = self.media_control_enabled[self.index].get()

        self._toggle_panel(self.file_panel, app_enabled)
        self.browse_button.configure(state="normal" if app_enabled else "disabled")
        if app_enabled:
            current_path = self.app_launch_paths[self.index].get()
            self.path_label.configure(
                text=os.path.basename(current_path) if current_path else "No application selected"
            )

        self._toggle_panel(self.shortcut_recorder, shortcut_enabled)
        self.shortcut_recorder.set_widget_state(shortcut_enabled)

        self._toggle_panel(self.media_panel, media_enabled)
        self.media_action_dropdown.configure(
            state="normal" if media_enabled else "disabled"
        )

        self.resize_to_content()

    @staticmethod
    def _toggle_panel(panel, visible):
        if visible:
            panel.grid()
        else:
            panel.grid_remove()

    def _on_shortcut_recorded(self, shortcut):
        self.keyboard_shortcuts[self.index].set(shortcut)

    def browse_file(self):
        """Pick an executable for the launch action."""
        file_path = filedialog.askopenfilename(
            title="Select Application",
            parent=self.window,
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
        )
        if file_path:
            self.app_launch_paths[self.index].set(file_path)
            self._refresh_visibility()
