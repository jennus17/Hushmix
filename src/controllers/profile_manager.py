"""Profile switching and persistence.

All per-profile fields are handled from the canonical list in
:data:`utils.config_manager.ConfigManager.PROFILE_SETTINGS`.  The previous
version hard-coded thirteen near-identical blocks (and three different guesses
at the channel/button count: 5, 7, or the length of the stored list) and only
persisted a subset of the fields, so switching profiles could silently drop
application launchers and shortcuts.
"""

from utils.config_manager import ConfigManager
from utils.logging_setup import get_logger

logger = get_logger("profile_manager")


class ProfileManager:
    def __init__(self, app_instance):
        self.app = app_instance

    # ---------------------------------------------------------------- profiles

    def refresh_profile_list(self, current=None):
        """Reload the dropdown after profiles are added, renamed or removed."""
        names = ConfigManager.get_profile_names()
        current = current or self.app.settings_manager.settings_vars.get("current_profile")
        self.app.gui_components.set_profile_names(names, current)
        return names

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _list(values, length, default):
        """Pad/truncate *values* to *length*, filling gaps with *default*."""
        if not isinstance(values, (list, tuple)):
            values = []
        result = list(values[:length])
        while len(result) < length:
            result.append(default)
        return result

    # ----------------------------------------------------------- profile switch

    def on_profile_change(self, profile):
        """Save the current profile and load *profile*."""
        if not profile:
            return

        app = self.app
        current_profile = app.settings_manager.settings_vars.get(
            "current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0]
        )

        if profile == current_profile:
            return

        # Persist what is on screen before switching away from it.
        self.save_current_profile_data(current_profile)

        full = ConfigManager.load_all()
        stored = (full.get("profiles") or {}).get(profile) or {}

        app.current_apps = list(stored.get("applications") or [])
        if not app.current_apps:
            app.current_apps = [""] * ConfigManager.CHANNEL_COUNT

        app.mute = app._build_var_list(
            "mute_settings", stored.get("mute_settings"), ConfigManager.BUTTON_COUNT
        )
        app.app_launch_enabled = app._build_var_list(
            "app_launch_enabled", stored.get("app_launch_enabled"), ConfigManager.BUTTON_COUNT
        )
        app.app_launch_paths = app._build_var_list(
            "app_launch_paths", stored.get("app_launch_paths"), ConfigManager.BUTTON_COUNT
        )
        app.keyboard_shortcut_enabled = app._build_var_list(
            "keyboard_shortcut_enabled",
            stored.get("keyboard_shortcut_enabled"),
            ConfigManager.BUTTON_COUNT,
        )
        app.keyboard_shortcuts = app._build_var_list(
            "keyboard_shortcuts", stored.get("keyboard_shortcuts"), ConfigManager.BUTTON_COUNT
        )
        app.mute_button_modes = app._build_var_list(
            "mute_button_modes", stored.get("mute_button_modes"), ConfigManager.BUTTON_COUNT
        )
        app.app_button_modes = app._build_var_list(
            "app_button_modes", stored.get("app_button_modes"), ConfigManager.BUTTON_COUNT
        )
        app.shortcut_button_modes = app._build_var_list(
            "shortcut_button_modes", stored.get("shortcut_button_modes"), ConfigManager.BUTTON_COUNT
        )
        app.media_control_enabled = app._build_var_list(
            "media_control_enabled",
            stored.get("media_control_enabled"),
            ConfigManager.BUTTON_COUNT,
        )
        app.media_control_actions = app._build_var_list(
            "media_control_actions",
            stored.get("media_control_actions"),
            ConfigManager.BUTTON_COUNT,
        )
        app.media_control_button_modes = app._build_var_list(
            "media_control_button_modes",
            stored.get("media_control_button_modes"),
            ConfigManager.BUTTON_COUNT,
        )

        mute_state = self._list(
            stored.get("mute_state"), len(app.current_apps), False
        )
        app.current_mute_state = [bool(value) for value in mute_state]
        app.muted_state = list(app.current_mute_state)
        app.previous_volumes = [None] * len(app.current_apps)

        app.settings_manager.settings_vars["current_profile"] = profile
        app._publish_profile_state()

        app.gui_components.refresh_gui()
        logger.info("Switched to profile %s", profile)

    # --------------------------------------------------------------- persisting

    def save_current_profile_data(self, profile_name):
        """Write the current GUI state into *profile_name*."""
        try:
            app = self.app
            app._collect_profile_state()

            full = ConfigManager.load_all()
            profiles = full.setdefault("profiles", {})
            profile = profiles.setdefault(profile_name, {})

            for field in ConfigManager.PROFILE_SETTINGS:
                profile[field] = list(app.settings_manager.settings_vars.get(field, []))

            profile["applications"] = list(app.current_apps)
            profile["mute_state"] = list(app.current_mute_state)
            full["current_profile"] = app.settings_manager.settings_vars.get(
                "current_profile", profile_name
            )

            ConfigManager.save_all_settings(full)
            return True

        except Exception as error:
            logger.exception("Error saving profile data: %s", error)
            return False

    def save_applications(self, event=None):
        """Persist application names when the user edits a field."""
        try:
            app = self.app
            entries = getattr(getattr(app, "gui_components", None), "entries", None)
            if entries:
                app.current_apps = [entry.get() for entry in entries]

            current_profile = app.settings_manager.settings_vars.get(
                "current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0]
            )
            self.save_current_profile_data(current_profile)

        except Exception as error:
            logger.exception("Error saving applications: %s", error)
