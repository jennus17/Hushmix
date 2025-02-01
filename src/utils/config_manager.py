import json
import os
import winreg

class ConfigManager:
    CONFIG_FILE = "settings.json"

    @staticmethod
    def save_settings(settings):
        """Save settings to JSON file."""
        try:
            # Get the directory where the script is running
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(script_dir, ConfigManager.CONFIG_FILE)
            
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, "w") as file:
                json.dump(settings, file, indent=4)
            print(f"Settings saved to {config_path}")
        except Exception as e:
            print(f"Error saving settings: {e}")

    @staticmethod
    def load_settings():
        """Load settings from JSON file."""
        try:
            # Get the directory where the script is running
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(script_dir, ConfigManager.CONFIG_FILE)
            
            # Check if file exists
            if not os.path.exists(config_path):
                print("No settings file found, using defaults")
                return {
                    "applications": ["App 1", "App 2", "App 3"],
                    "invert_volumes": False,
                    "auto_startup": False,
                    "dark_mode": False
                }
            
            # Load settings from file
            with open(config_path, "r") as file:
                settings = json.load(file)
                print(f"Settings loaded from {config_path}")
                return settings
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {
                "applications": ["App 1", "App 2", "App 3"],
                "invert_volumes": False,
                "auto_startup": False,
                "dark_mode": False,
                "launch_in_tray": False  # Default value for launch mode
            }

    @staticmethod  
    def load_apps():
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        apps_path = os.path.join(script_dir, 'Apps.json')

        with open(apps_path, 'r') as file:
            apps = json.load(file)
        return [app['name'] for app in apps]

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