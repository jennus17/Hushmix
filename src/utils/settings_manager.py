import customtkinter as ctk
import sys
from .config_manager import ConfigManager


class SettingsManager:
    def __init__(self, app):
        self.app = app
        self.settings_vars = {}
        self._setup_settings_vars()
    
    def _setup_settings_vars(self):
        """Setup all settings variables with their default values."""
        self.settings_vars.update({
            "invert_volumes": ctk.BooleanVar(value=False),
            "auto_startup": ctk.BooleanVar(value=False),
            "dark_mode": ctk.BooleanVar(value=True),
            "launch_in_tray": ctk.BooleanVar(value=False),
        })
        
        self.settings_vars.update({
            "window_x": None,
            "window_y": None,
        })
        
        self.settings_vars.update({
            "applications": [],
            "mute_settings": [],
            "mute_state": [],
            "app_launch_enabled": [],
            "app_launch_paths": [],
        })
    
    def get_setting(self, key, default=None):
        """Get a setting value."""
        if key in self.settings_vars:
            var = self.settings_vars[key]
            if hasattr(var, 'get'):
                return var.get()
            return var
        return default
    
    def set_setting(self, key, value):
        """Set a setting value."""
        if key in self.settings_vars:
            var = self.settings_vars[key]
            if hasattr(var, 'set'):
                var.set(value)
            else:
                self.settings_vars[key] = value
    
    def load_from_config(self):
        """Load all settings from config file."""
        settings = ConfigManager.load_settings()
        
        for key in ["invert_volumes", "auto_startup", "dark_mode", "launch_in_tray", "window_x", "window_y"]:
            if key in settings:
                self.set_setting(key, settings[key])
        
        for key in ["applications", "mute_settings", "mute_state", "app_launch_enabled", "app_launch_paths"]:
            if key in settings:
                self.settings_vars[key] = settings[key]
        
        if "current_profile" in settings:
            self.settings_vars["current_profile"] = settings["current_profile"]
        
        return settings
    
    def save_to_config(self):
        """Save global settings to config file."""
        settings = {
            "current_profile": self.settings_vars.get("current_profile", "Profile 1"),
        }
        
        for key in ["invert_volumes", "auto_startup", "dark_mode", "launch_in_tray", "window_x", "window_y"]:
            settings[key] = self.get_setting(key)
        
        ConfigManager.toggle_auto_startup(
            self.get_setting("auto_startup"), "Hushmix", sys.executable
        )
        
        ConfigManager.save_settings(settings)
    
    def get_all_settings(self):
        """Get all settings as a dictionary."""
        all_settings = {}
        
        for key in ["invert_volumes", "auto_startup", "dark_mode", "launch_in_tray", "window_x", "window_y"]:
            all_settings[key] = self.get_setting(key)

        for key in ["applications", "mute_settings", "mute_state", "app_launch_enabled", "app_launch_paths"]:
            if key in self.settings_vars:
                all_settings[key] = self.settings_vars[key]
        
        all_settings["current_profile"] = self.settings_vars.get("current_profile", "Profile 1")
        
        return all_settings 