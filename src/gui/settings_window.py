"""Settings window (theme, startup behaviour, update preferences)."""

import customtkinter as ctk

from gui.base_window import BaseWindow
from utils.logging_setup import get_logger

logger = get_logger("settings_window")

GENERAL_SETTINGS = [
    ("Invert Volume Range (100 - 0)", "invert_volumes"),
    ("Enable Auto Startup", "auto_startup"),
    ("Launch in Tray", "launch_in_tray"),
    ("Dark Mode", "dark_mode"),
]

UPDATE_SETTINGS = [
    ("Automatically check for updates", "auto_check_updates"),
]

INTERVAL_OPTIONS = ["15 minutes", "30 minutes", "1 hour", "2 hours", "4 hours", "8 hours"]


def interval_to_label(seconds):
    """Render a check interval in seconds as one of the dropdown labels."""
    minutes = max(1, int(seconds) // 60)
    if minutes % 60 == 0:
        hours = minutes // 60
        return "1 hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minutes"


def label_to_seconds(label):
    """Parse a dropdown label back into seconds."""
    parts = label.split()
    value = int(parts[0])
    return value * 3600 if "hour" in label.lower() else value * 60


class SettingsWindow(BaseWindow):
    window_name = "settings window"
    default_size = (380, 430)

    def __init__(self, parent, config_manager, settings_manager, on_close, version_manager=None):
        super().__init__(parent, on_close=on_close)
        self.config_manager = config_manager
        self.settings_manager = settings_manager
        # Passed in explicitly: ``parent`` is the Tk root, which does not carry
        # the application object, so looking it up through the window would not
        # find the update manager.
        self.version_manager = version_manager

        self.palette = self.build_palette(settings_manager)
        self.normal_font_size = 14

        self.build("Settings")
        self.build_gui()
        self.apply_dpi_scaling()
        self.show()

    # ------------------------------------------------------------------ layout

    def build_gui(self):
        self.frame = ctk.CTkFrame(
            self.window,
            corner_radius=0,
            border_width=0,
            fg_color=self.palette.background,
        )
        self.frame.pack(expand=True, fill="both")

        self._add_section_label("General Settings", first=True)
        for text, key in GENERAL_SETTINGS:
            self._add_checkbox(text, key)

        self._add_section_label("Update Settings")
        for text, key in UPDATE_SETTINGS:
            self._add_checkbox(text, key)

        self._add_update_interval()

    def _add_section_label(self, text, first=False):
        label = ctk.CTkLabel(
            self.frame,
            text=text,
            font=("Segoe UI", 16, "bold"),
            text_color=self.palette.text,
        )
        label.pack(pady=(8 if first else 20, 10), padx=15, anchor="w")

    def _add_checkbox(self, text, setting_key):
        # ``get_setting`` unwraps Tk variables, so it must not be used here: a
        # checkbox needs the variable object itself.  ``ensure_setting`` returns
        # the existing BooleanVar or creates one for keys a config file may
        # predate.
        variable = self.settings_manager.ensure_setting(setting_key)

        checkbox = ctk.CTkCheckBox(
            self.frame,
            text=text,
            variable=variable,
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.palette.accent,
            hover_color=self.palette.accent_hover,
            text_color=self.palette.text,
            border_color=self.palette.border_strong,
            checkmark_color=self.palette.accent_text,
        )
        checkbox.pack(pady=8, padx=15, anchor="w")

    def _add_update_interval(self):
        frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        frame.pack(pady=(5, 15), padx=15, fill="x")

        label = ctk.CTkLabel(
            frame,
            text="Check for updates every:",
            font=("Segoe UI", self.normal_font_size),
            text_color=self.palette.text,
        )
        label.pack(side="left", padx=(0, 10))

        current = self.settings_manager.get_setting("update_check_interval", 1800)
        self.interval_var = ctk.StringVar(value=interval_to_label(current))

        menu = ctk.CTkOptionMenu(
            frame,
            values=INTERVAL_OPTIONS,
            variable=self.interval_var,
            command=self.change_update_interval,
            font=("Segoe UI", self.normal_font_size),
            text_color=self.palette.accent_text,
            fg_color=self.palette.accent,
            button_color=self.palette.accent,
            button_hover_color=self.palette.accent_hover,
            dropdown_hover_color=self.palette.accent_soft,
            dropdown_fg_color=self.palette.surface_high,
            dropdown_text_color=self.palette.text,
        )
        menu.pack(side="left")

        self.check_now_button = ctk.CTkButton(
            self.frame,
            text="Check now",
            command=self.check_for_updates_now,
            font=("Segoe UI", self.normal_font_size),
            text_color=self.palette.accent_text,
            fg_color=self.palette.accent,
            hover_color=self.palette.accent_hover,
            cursor="hand2",
            height=30,
        )
        self.check_now_button.pack(pady=(0, 10), padx=15, anchor="w")

        self.update_status_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=("Segoe UI", 11),
            justify="left",
            wraplength=330,
            text_color=self.palette.text_muted,
        )
        self.update_status_label.pack(pady=(0, 10), padx=15, anchor="w")

    # ---------------------------------------------------------------- behaviour

    def check_for_updates_now(self):
        """Ask the update manager to check immediately."""
        version_manager = self.version_manager
        if version_manager is None or not hasattr(version_manager, "check_now"):
            self._set_update_status("Update checking is unavailable.")
            return

        try:
            started = version_manager.check_now()
        except Exception as error:
            self._set_update_status(f"Could not check for updates: {error}")
            return

        if started:
            self._set_update_status(
                "Checking for updates... You will be told if a new version is found."
            )
        else:
            self._set_update_status("An update window is already open.")

    def _set_update_status(self, text):
        try:
            self.update_status_label.configure(text=text)
        except Exception as error:
            logger.debug("Could not update the status label: %s", error)

    def change_update_interval(self, value):
        """Store the chosen interval and let the running checker pick it up."""
        try:
            seconds = label_to_seconds(value)
        except (ValueError, IndexError):
            return

        self.settings_manager.set_setting("update_check_interval", seconds)
        version_manager = self.version_manager
        if version_manager is not None and hasattr(version_manager, "set_check_interval"):
            version_manager.set_check_interval(seconds)

    def on_shown(self):
        self.window.focus_force()
