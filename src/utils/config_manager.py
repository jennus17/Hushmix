import json
import os
import winreg
import time
import requests

class ConfigManager:
    CONFIG_FILE = os.path.join(os.getenv('APPDATA'), 'Hushmix', 'settings.json')


    @staticmethod
    def save_settings(settings):
        """Save settings to JSON file."""
        try:
            os.makedirs(os.path.dirname(ConfigManager.CONFIG_FILE), exist_ok=True)
            
            # Load existing settings first
            existing_settings = {}
            if os.path.exists(ConfigManager.CONFIG_FILE):
                with open(ConfigManager.CONFIG_FILE, "r") as file:
                    existing_settings = json.load(file)
            
            if "profiles" not in existing_settings:
                existing_settings["profiles"] = {}
            
            current_profile = settings.get("current_profile")
            
            if current_profile not in existing_settings["profiles"]:
                existing_settings["profiles"][current_profile] = {}
                
            existing_settings["profiles"][current_profile]["applications"] = settings.get("applications")
            
            existing_settings.update({
                "current_profile": current_profile,
                "invert_volumes": settings.get("invert_volumes", False),
                "auto_startup": settings.get("auto_startup", False),
                "dark_mode": settings.get("dark_mode", True),
                "launch_in_tray": settings.get("launch_in_tray", False)
            })
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
                default_settings = {
                    "current_profile": "Profile 1",
                    "profiles": {
                        "Profile 1": {"applications": []},
                        "Profile 2": {"applications": []},
                        "Profile 3": {"applications": []},
                        "Profile 4": {"applications": []},
                        "Profile 5": {"applications": []}
                    },
                    "invert_volumes": False,
                    "auto_startup": False,
                    "dark_mode": True,
                    "launch_in_tray": False
                }
                return default_settings
            
            with open(ConfigManager.CONFIG_FILE, "r") as file:
                settings = json.load(file)
                
                if "profiles" not in settings:
                    settings["profiles"] = {
                        "Profile 1": {"applications": []},
                        "Profile 2": {"applications": []},
                        "Profile 3": {"applications": []},
                        "Profile 4": {"applications": []},
                        "Profile 5": {"applications": []}
                    }
                
                current_profile = settings.get("current_profile")
                profile_settings = settings.get("profiles", {}).get(current_profile, {"applications": []})
                
                return {
                    "current_profile": current_profile,
                    "profiles": settings.get("profiles", {}),
                    "applications": profile_settings.get("applications", []),
                    "invert_volumes": settings.get("invert_volumes", False),
                    "auto_startup": settings.get("auto_startup", False),
                    "dark_mode": settings.get("dark_mode", True),
                    "launch_in_tray": settings.get("launch_in_tray", False)
                }
                
        except Exception as e:
            time.sleep(1)
            print(f"Error loading settings: {e}")
            return ConfigManager.load_settings()


    @staticmethod
    def toggle_auto_startup(enable, app_name="Hushmix", executable_path=None):
        """Toggle auto-startup in Windows registry."""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            
            if enable:
                with winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE) as registry_key:
                    winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, executable_path)
                print(f"Auto-startup enabled for {app_name}")
            else:
                with winreg.OpenKey(key, subkey, 0, winreg.KEY_WRITE) as registry_key:
                    winreg.DeleteValue(registry_key, app_name)
                print(f"Auto-startup disabled for {app_name}")
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
        