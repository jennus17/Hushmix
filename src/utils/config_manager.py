import json
import os
import winreg
import time
import requests


class ConfigManager:
    CONFIG_FILE = os.path.join(os.getenv("APPDATA"), "Hushmix", "settings.json")
    
    GLOBAL_SETTINGS = {
        "invert_volumes": False,
        "auto_startup": False,
        "dark_mode": True,
        "launch_in_tray": False,
        "auto_check_updates": True,
        "window_x": None,
        "window_y": None,
        "update_source": "github",
        "update_check_interval": 1800,
        "skip_version": None,
        "last_update_check": None,
    }
    
    PROFILE_SETTINGS = {
        "applications": [],
        "mute_settings": [],
        "mute_state": [],
    }
    
    DEFAULT_PROFILES = ["Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"]

    @staticmethod
    def get_default_settings():
        """Get complete default settings structure."""
        profiles = {}
        for profile_name in ConfigManager.DEFAULT_PROFILES:
            profiles[profile_name] = ConfigManager.PROFILE_SETTINGS.copy()
        
        return {
            "current_profile": "Profile 1",
            "profiles": profiles,
            **ConfigManager.GLOBAL_SETTINGS
        }

    @staticmethod
    def save_settings(settings):
        """Save settings to JSON file."""
        try:
            os.makedirs(os.path.dirname(ConfigManager.CONFIG_FILE), exist_ok=True)

            existing_settings = {}
            if os.path.exists(ConfigManager.CONFIG_FILE):
                with open(ConfigManager.CONFIG_FILE, "r") as file:
                    existing_settings = json.load(file)

            if "profiles" not in existing_settings:
                existing_settings["profiles"] = {}

            current_profile = settings.get("current_profile")
            if current_profile not in existing_settings["profiles"]:
                existing_settings["profiles"][current_profile] = {}

            for key, value in settings.items():
                if key in ConfigManager.PROFILE_SETTINGS:
                    existing_settings["profiles"][current_profile][key] = value
                elif key in ConfigManager.GLOBAL_SETTINGS or key == "current_profile":
                    existing_settings[key] = value

            with open(ConfigManager.CONFIG_FILE, "w") as file:
                json.dump(existing_settings, file, indent=4)

            print(f"Settings successfully saved to {ConfigManager.CONFIG_FILE}")

        except Exception as e:
            print(f"Error saving settings: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def load_settings():
        """Load settings from JSON file."""
        try:
            time.sleep(0.1)

            if not os.path.exists(ConfigManager.CONFIG_FILE):
                print("No settings file found, using defaults")
                return ConfigManager.get_default_settings()

            with open(ConfigManager.CONFIG_FILE, "r") as file:
                settings = json.load(file)

            if "profiles" not in settings:
                settings["profiles"] = {}
            
            for profile_name in ConfigManager.DEFAULT_PROFILES:
                if profile_name not in settings["profiles"]:
                    settings["profiles"][profile_name] = ConfigManager.PROFILE_SETTINGS.copy()

            current_profile = settings.get("current_profile", "Profile 1")
            if current_profile not in settings["profiles"]:
                settings["profiles"][current_profile] = ConfigManager.PROFILE_SETTINGS.copy()
            
            for profile_name in settings["profiles"]:
                for key, default_value in ConfigManager.PROFILE_SETTINGS.items():
                    if key not in settings["profiles"][profile_name]:
                        settings["profiles"][profile_name][key] = default_value

            for key, default_value in ConfigManager.GLOBAL_SETTINGS.items():
                if key not in settings:
                    settings[key] = default_value

            profile_settings = settings["profiles"][current_profile]

            return {
                "current_profile": current_profile,
                "profiles": settings["profiles"],
                **profile_settings,
                **{k: settings[k] for k in ConfigManager.GLOBAL_SETTINGS}
            }

        except Exception as e:
            time.sleep(1)
            print(f"Error loading settings: {e}")
            return ConfigManager.load_settings()

    @staticmethod
    def get_all_settings():
        """Get all settings including profiles for advanced operations."""
        return ConfigManager.load_settings()

    @staticmethod
    def save_all_settings(all_settings):
        """Save complete settings structure including all profiles."""
        try:
            os.makedirs(os.path.dirname(ConfigManager.CONFIG_FILE), exist_ok=True)
            
            with open(ConfigManager.CONFIG_FILE, "w") as file:
                json.dump(all_settings, file, indent=4)
                
            print(f"All settings successfully saved to {ConfigManager.CONFIG_FILE}")
            
        except Exception as e:
            print(f"Error saving all settings: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def toggle_auto_startup(enable, app_name="Hushmix", executable_path=None):
        """Toggle auto-startup in Windows registry."""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

            if enable:
                with winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE) as registry_key:
                    winreg.SetValueEx(
                        registry_key, app_name, 0, winreg.REG_SZ, executable_path
                    )
                print(f"Auto-startup enabled for {app_name}")
            else:
                try:
                    with winreg.OpenKey(key, subkey, 0, winreg.KEY_READ) as registry_key:
                        winreg.QueryValueEx(registry_key, app_name)
                    with winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE) as registry_key:
                        winreg.DeleteValue(registry_key, app_name)
                    print(f"Auto-startup disabled for {app_name}")
                except FileNotFoundError:
                    print(f"Auto-startup was already disabled for {app_name}")
        except Exception as e:
            print(f"Error managing auto-startup: {e}")

    @staticmethod
    def is_auto_startup_enabled(app_name="Hushmix"):
        """Check if auto-startup is enabled."""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_READ) as registry_key:
                value, _ = winreg.QueryValueEx(registry_key, app_name)
                return bool(value)
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Error checking auto-startup status: {e}")
            return False
