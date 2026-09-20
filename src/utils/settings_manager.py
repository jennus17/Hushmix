"""Typed access to the settings that live in memory during a session."""

import customtkinter as ctk

from utils.config_manager import ConfigManager

#: Global keys stored as Tk variables (checkboxes and friends).
BOOLEAN_KEYS = (
    "invert_volumes",
    "auto_startup",
    "dark_mode",
    "launch_in_tray",
    "auto_check_updates",
)

#: Global keys that are read/written directly (no Tk variable).
ALL_GLOBAL_KEYS = tuple(ConfigManager.GLOBAL_SETTINGS)

#: Profile-scoped keys held as plain lists (no Tk variable needed).
PROFILE_KEYS = tuple(ConfigManager.PROFILE_SETTINGS)


class SettingsManager:
    """Holds the working copy of the settings for the running application."""

    def __init__(self, app):
        self.app = app
        self.settings_vars = {}
        self._setup_settings_vars()

    def _setup_settings_vars(self):
        """Create the Tk variables used by the settings widgets."""
        self.settings_vars.update(
            {
                "invert_volumes": ctk.BooleanVar(value=False),
                "auto_startup": ctk.BooleanVar(value=False),
                "dark_mode": ctk.BooleanVar(value=True),
                "launch_in_tray": ctk.BooleanVar(value=False),
                "auto_check_updates": ctk.BooleanVar(value=True),
            }
        )

        self.settings_vars.update(
            {key: ConfigManager.GLOBAL_SETTINGS[key] for key in ALL_GLOBAL_KEYS}
        )

        self.settings_vars.update({key: [] for key in PROFILE_KEYS})
        self.settings_vars["current_profile"] = ConfigManager.DEFAULT_PROFILE_NAMES[0]

    # ------------------------------------------------------------------ access

    def get_setting(self, key, default=None):
        """Return a setting, unwrapping Tk variables."""
        if key not in self.settings_vars:
            return default

        value = self.settings_vars[key]
        if hasattr(value, "get"):
            try:
                return value.get()
            except Exception:
                return default
        return value

    def set_setting(self, key, value):
        """Set a setting, writing through Tk variables when present.

        Unknown keys are created rather than ignored, so a newly added setting
        is never silently discarded (the old implementation returned silently
        for any key that had not been pre-declared).
        """
        if key in self.settings_vars:
            variable = self.settings_vars[key]
            if hasattr(variable, "set"):
                variable.set(value)
                return
        self.settings_vars[key] = value

    def ensure_setting(self, key, value=None):
        """Return a Tk variable for *key*, creating it when necessary.

        Widgets (checkboxes especially) need the variable object, never the
        unwrapped value that :meth:`get_setting` returns.  A key that currently
        holds a plain value is promoted to a variable here so a call site can
        never hand a bare ``bool`` to a widget.
        """
        variable = self.settings_vars.get(key)
        if variable is not None and hasattr(variable, "get"):
            return variable

        current = variable if variable is not None else value
        boolean = key in BOOLEAN_KEYS or key == "auto_startup" or isinstance(current, bool)

        if boolean:
            variable = ctk.BooleanVar(value=bool(current))
        else:
            variable = ctk.StringVar(value="" if current is None else str(current))

        self.settings_vars[key] = variable
        return variable

    # -------------------------------------------------------------- persistence

    def load_from_config(self):
        """Load every setting from disk and return the raw mapping."""
        settings = ConfigManager.load_settings()

        for key in ALL_GLOBAL_KEYS:
            if key in settings:
                self.set_setting(key, settings[key])

        for key in PROFILE_KEYS:
            if key in settings:
                self.settings_vars[key] = list(settings[key])

        self.settings_vars["current_profile"] = settings.get(
            "current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0]
        )

        return settings

    def get_global_settings(self):
        """The global (non-profile) part of the settings."""
        return {
            "current_profile": self.settings_vars.get(
                "current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0]
            ),
            **{key: self.get_setting(key, ConfigManager.GLOBAL_SETTINGS[key])
               for key in ALL_GLOBAL_KEYS},
        }

    def get_profile_settings(self):
        """The per-profile part of the settings, as plain values."""
        data = {}
        for key in PROFILE_KEYS:
            value = self.settings_vars.get(key, [])
            if hasattr(value, "get"):
                value = value.get()
            data[key] = value
        return data

    def save_to_config(self):
        """Persist the global settings, syncing the Run key first."""
        settings = self.get_global_settings()

        ConfigManager.toggle_auto_startup(
            bool(self.get_setting("auto_startup")),
            ConfigManager.APP_NAME,
            self._startup_command(),
        )

        return ConfigManager.save_settings(settings)

    @staticmethod
    def _startup_command():
        from utils.app_paths import startup_command

        return startup_command()

    def get_all_settings(self):
        """Global plus profile settings, for callers that need both."""
        return {**self.get_global_settings(), **self.get_profile_settings()}
