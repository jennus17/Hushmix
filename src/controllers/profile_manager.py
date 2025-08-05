import customtkinter as ctk
from utils.config_manager import ConfigManager


class ProfileManager:
    def __init__(self, app_instance):
        self.app = app_instance
    
    def on_profile_change(self, profile):
        """Handle profile selection changes."""
        try:
            current_profile = self.app.settings_manager.settings_vars.get("current_profile", "Profile 1")
            
            self.save_current_profile_data(current_profile)

            settings = ConfigManager.load_settings()
            
            new_profile_apps = (
                settings.get("profiles", {}).get(profile, {}).get("applications", [])
            )
            new_profile_mute = (
                settings.get("profiles", {}).get(profile, {}).get("mute_settings", [])
            )
            new_profile_mute_state = (
                settings.get("profiles", {}).get(profile, {}).get("mute_state", [])
            )
            new_profile_app_launch_enabled = (
                settings.get("profiles", {}).get(profile, {}).get("app_launch_enabled", [])
            )
            new_profile_app_launch_paths = (
                settings.get("profiles", {}).get(profile, {}).get("app_launch_paths", [])
            )
            new_profile_keyboard_shortcut_enabled = (
                settings.get("profiles", {}).get(profile, {}).get("keyboard_shortcut_enabled", [])
            )
            new_profile_keyboard_shortcuts = (
                settings.get("profiles", {}).get(profile, {}).get("keyboard_shortcuts", [])
            )
            new_profile_mute_button_modes = (
                settings.get("profiles", {}).get(profile, {}).get("mute_button_modes", [])
            )
            new_profile_app_button_modes = (
                settings.get("profiles", {}).get(profile, {}).get("app_button_modes", [])
            )
            new_profile_shortcut_button_modes = (
                settings.get("profiles", {}).get(profile, {}).get("shortcut_button_modes", [])
            )
            new_profile_media_control_enabled = (
                settings.get("profiles", {}).get(profile, {}).get("media_control_enabled", [])
            )
            new_profile_media_control_actions = (
                settings.get("profiles", {}).get(profile, {}).get("media_control_actions", [])
            )
            new_profile_media_control_button_modes = (
                settings.get("profiles", {}).get(profile, {}).get("media_control_button_modes", [])
            )
            
            self.app.current_apps = new_profile_apps
            self.app.settings_manager.settings_vars["applications"] = new_profile_apps
            self.app.settings_manager.settings_vars["current_profile"] = profile

            self.app.mute = []
            if new_profile_mute:
                for mute_value in new_profile_mute:
                    var = ctk.BooleanVar(value=mute_value)
                    self.app.mute.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=True)
                    self.app.mute.append(var)

            if new_profile_mute_state:
                self.app.current_mute_state = new_profile_mute_state.copy()
            else:
                self.app.current_mute_state = [False] * 7
            self.app.muted_state = self.app.current_mute_state.copy()
            
            self.app.app_launch_enabled = []
            if new_profile_app_launch_enabled:
                for enabled_value in new_profile_app_launch_enabled:
                    var = ctk.BooleanVar(value=enabled_value)
                    self.app.app_launch_enabled.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=False)
                    self.app.app_launch_enabled.append(var)

            self.app.app_launch_paths = []
            if new_profile_app_launch_paths:
                for path_value in new_profile_app_launch_paths:
                    var = ctk.StringVar(value=path_value)
                    self.app.app_launch_paths.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="")
                    self.app.app_launch_paths.append(var)
            
            self.app.keyboard_shortcut_enabled = []
            if new_profile_keyboard_shortcut_enabled:
                for enabled_value in new_profile_keyboard_shortcut_enabled:
                    var = ctk.BooleanVar(value=enabled_value)
                    self.app.keyboard_shortcut_enabled.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=False)
                    self.app.keyboard_shortcut_enabled.append(var)

            self.app.keyboard_shortcuts = []
            if new_profile_keyboard_shortcuts:
                for shortcut_value in new_profile_keyboard_shortcuts:
                    var = ctk.StringVar(value=shortcut_value)
                    self.app.keyboard_shortcuts.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="")
                    self.app.keyboard_shortcuts.append(var)
            
            self.app.mute_button_modes = []
            if new_profile_mute_button_modes:
                for mode_value in new_profile_mute_button_modes:
                    var = ctk.StringVar(value=mode_value)
                    self.app.mute_button_modes.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="Click")
                    self.app.mute_button_modes.append(var)

            self.app.app_button_modes = []
            if new_profile_app_button_modes:
                for mode_value in new_profile_app_button_modes:
                    var = ctk.StringVar(value=mode_value)
                    self.app.app_button_modes.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="Click")
                    self.app.app_button_modes.append(var)

            self.app.shortcut_button_modes = []
            if new_profile_shortcut_button_modes:
                for mode_value in new_profile_shortcut_button_modes:
                    var = ctk.StringVar(value=mode_value)
                    self.app.shortcut_button_modes.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="Click")
                    self.app.shortcut_button_modes.append(var)
            
            self.app.media_control_enabled = []
            if new_profile_media_control_enabled:
                for enabled_value in new_profile_media_control_enabled:
                    var = ctk.BooleanVar(value=enabled_value)
                    self.app.media_control_enabled.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=False)
                    self.app.media_control_enabled.append(var)

            self.app.media_control_actions = []
            if new_profile_media_control_actions:
                for action_value in new_profile_media_control_actions:
                    var = ctk.StringVar(value=action_value)
                    self.app.media_control_actions.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="Play/Pause")
                    self.app.media_control_actions.append(var)

            self.app.media_control_button_modes = []
            if new_profile_media_control_button_modes:
                for mode_value in new_profile_media_control_button_modes:
                    var = ctk.StringVar(value=mode_value)
                    self.app.media_control_button_modes.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="Click")
                    self.app.media_control_button_modes.append(var)
            
            self.app.settings_manager.settings_vars["mute_settings"] = [mute_state.get() for mute_state in self.app.mute]
            self.app.settings_manager.settings_vars["mute_state"] = self.app.current_mute_state
            self.app.settings_manager.settings_vars["app_launch_enabled"] = [enabled.get() for enabled in self.app.app_launch_enabled]
            self.app.settings_manager.settings_vars["app_launch_paths"] = [path.get() for path in self.app.app_launch_paths]
            self.app.settings_manager.settings_vars["keyboard_shortcut_enabled"] = [enabled.get() for enabled in self.app.keyboard_shortcut_enabled]
            self.app.settings_manager.settings_vars["keyboard_shortcuts"] = [shortcut.get() for shortcut in self.app.keyboard_shortcuts]
            self.app.settings_manager.settings_vars["mute_button_modes"] = [mode.get() for mode in self.app.mute_button_modes]
            self.app.settings_manager.settings_vars["app_button_modes"] = [mode.get() for mode in self.app.app_button_modes]
            self.app.settings_manager.settings_vars["shortcut_button_modes"] = [mode.get() for mode in self.app.shortcut_button_modes]
            self.app.settings_manager.settings_vars["media_control_enabled"] = [enabled.get() for enabled in self.app.media_control_enabled]
            self.app.settings_manager.settings_vars["media_control_actions"] = [action.get() for action in self.app.media_control_actions]
            self.app.settings_manager.settings_vars["media_control_button_modes"] = [mode.get() for mode in self.app.media_control_button_modes]

            self.app.settings_manager.save_to_config()

            self.app.gui_components.refresh_gui()

        except Exception as e:
            print(f"Error in profile change: {e}")
            import traceback
            traceback.print_exc()

    def save_current_profile_data(self, profile_name):
        """Save current profile-specific data to the specified profile."""
        try:
            if self.app.mute == []:
                self.app.mute = [
                    ctk.BooleanVar(value=True),
                    ctk.BooleanVar(value=True),
                    ctk.BooleanVar(value=True),
                    ctk.BooleanVar(value=True),
                    ctk.BooleanVar(value=True),
                ]
            if self.app.current_mute_state == []:
                self.app.current_mute_state = [
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                ]
            if self.app.app_launch_paths == []:
                self.app.app_launch_paths = [
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                ]
            if self.app.keyboard_shortcut_enabled == []:
                self.app.keyboard_shortcut_enabled = [
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                ]
            if self.app.keyboard_shortcuts == []:
                self.app.keyboard_shortcuts = [
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                    ctk.StringVar(value=""),
                ]
            if self.app.mute_button_modes == []:
                self.app.mute_button_modes = [
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                ]
            if self.app.app_button_modes == []:
                self.app.app_button_modes = [
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                ]
            if self.app.shortcut_button_modes == []:
                self.app.shortcut_button_modes = [
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                ]
            
            if self.app.media_control_enabled == []:
                self.app.media_control_enabled = [
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                    ctk.BooleanVar(value=False),
                ]
            
            if self.app.media_control_actions == []:
                self.app.media_control_actions = [
                    ctk.StringVar(value="Play/Pause"),
                    ctk.StringVar(value="Play/Pause"),
                    ctk.StringVar(value="Play/Pause"),
                    ctk.StringVar(value="Play/Pause"),
                    ctk.StringVar(value="Play/Pause"),
                ]
            
            if self.app.media_control_button_modes == []:
                self.app.media_control_button_modes = [
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                    ctk.StringVar(value="Click"),
                ]

            current_apps = [entry.get() for entry in self.app.gui_components.entries] if hasattr(self.app, 'gui_components') else []
            current_mute_settings = [mute_state.get() for mute_state in self.app.mute]
            current_mute_state = self.app.current_mute_state
            current_app_launch_enabled = [enabled.get() for enabled in self.app.app_launch_enabled]
            current_app_launch_paths = [path.get() for path in self.app.app_launch_paths]
            current_keyboard_shortcut_enabled = [enabled.get() for enabled in self.app.keyboard_shortcut_enabled]
            current_keyboard_shortcuts = [shortcut.get() for shortcut in self.app.keyboard_shortcuts]
            current_mute_button_modes = [mode.get() for mode in self.app.mute_button_modes]
            current_app_button_modes = [mode.get() for mode in self.app.app_button_modes]
            current_shortcut_button_modes = [mode.get() for mode in self.app.shortcut_button_modes]
            current_media_control_enabled = [enabled.get() for enabled in self.app.media_control_enabled]
            current_media_control_actions = [action.get() for action in self.app.media_control_actions]
            current_media_control_button_modes = [mode.get() for mode in self.app.media_control_button_modes]

            settings = ConfigManager.load_settings()
            
            if "profiles" not in settings:
                settings["profiles"] = {}
            if profile_name not in settings["profiles"]:
                settings["profiles"][profile_name] = {}
            
            settings["profiles"][profile_name]["applications"] = current_apps
            settings["profiles"][profile_name]["mute_settings"] = current_mute_settings
            settings["profiles"][profile_name]["mute_state"] = current_mute_state
            settings["profiles"][profile_name]["app_launch_enabled"] = current_app_launch_enabled
            settings["profiles"][profile_name]["app_launch_paths"] = current_app_launch_paths
            settings["profiles"][profile_name]["keyboard_shortcut_enabled"] = current_keyboard_shortcut_enabled
            settings["profiles"][profile_name]["keyboard_shortcuts"] = current_keyboard_shortcuts
            settings["profiles"][profile_name]["mute_button_modes"] = current_mute_button_modes
            settings["profiles"][profile_name]["app_button_modes"] = current_app_button_modes
            settings["profiles"][profile_name]["shortcut_button_modes"] = current_shortcut_button_modes
            settings["profiles"][profile_name]["media_control_enabled"] = current_media_control_enabled
            settings["profiles"][profile_name]["media_control_actions"] = current_media_control_actions
            settings["profiles"][profile_name]["media_control_button_modes"] = current_media_control_button_modes

            ConfigManager.save_all_settings(settings)

        except Exception as e:
            print(f"Error in save_current_profile_data: {e}")
            import traceback
            traceback.print_exc()

    def save_applications(self, event=None):
        """Save applications when a key is released in the entry fields."""
        try:
            if hasattr(self.app, 'gui_components') and hasattr(self.app.gui_components, 'entries'):
                self.app.settings_manager.settings_vars["applications"] = [entry.get() for entry in self.app.gui_components.entries]
            
            current_profile = self.app.settings_manager.settings_vars.get("current_profile", "Profile 1")
            self.save_current_profile_data(current_profile)

        except Exception as e:
            print(f"Error in save_applications: {e}")
            import traceback
            traceback.print_exc() 