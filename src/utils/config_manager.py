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

            # Check if file is empty or corrupted
            file_size = os.path.getsize(ConfigManager.CONFIG_FILE)
            if file_size == 0:
                print("Settings file is empty, using defaults")
                # Don't delete the file - just use defaults and let user decide what to do
                return ConfigManager.get_default_settings()

            with open(ConfigManager.CONFIG_FILE, "r", encoding='utf-8') as file:
                content = file.read().strip()
                
                # Check if file contains only whitespace
                if not content:
                    print("Settings file contains only whitespace, using defaults")
                    # Don't delete the file - just use defaults
                    return ConfigManager.get_default_settings()
                
                # Try to parse JSON
                try:
                    settings = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"Settings file contains invalid JSON: {e}")
                    # Try to recover partial data instead of deleting
                    return ConfigManager._attempt_settings_recovery(content)

            # Validate and fix settings structure
            settings = ConfigManager._validate_and_fix_settings(settings)
            return settings

        except Exception as e:
            print(f"Error loading settings: {e}")
            # Use defaults but don't delete the original file
            return ConfigManager.get_default_settings()

    @staticmethod
    def _attempt_settings_recovery(content):
        """Attempt to recover partial settings from corrupted JSON."""
        print("Attempting to recover settings from corrupted file...")
        
        try:
            # Try to find valid JSON objects in the content
            import re
            
            # Look for any valid JSON objects
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, content)
            
            recovered_settings = {}
            
            for match in matches:
                try:
                    partial_settings = json.loads(match)
                    if isinstance(partial_settings, dict):
                        recovered_settings.update(partial_settings)
                except:
                    continue
            
            if recovered_settings:
                print(f"Recovered {len(recovered_settings)} settings from corrupted file")
                # Merge with defaults to ensure all required keys exist
                default_settings = ConfigManager.get_default_settings()
                default_settings.update(recovered_settings)
                return ConfigManager._validate_and_fix_settings(default_settings)
            else:
                print("Could not recover any settings from corrupted file")
                return ConfigManager.get_default_settings()
                
        except Exception as recovery_error:
            print(f"Settings recovery failed: {recovery_error}")
            return ConfigManager.get_default_settings()

    @staticmethod
    def _validate_and_fix_settings(settings):
        """Validate and fix settings structure without losing user data."""
        if not isinstance(settings, dict):
            print("Settings is not a dictionary, using defaults")
            return ConfigManager.get_default_settings()

        # Ensure profiles structure exists
        if "profiles" not in settings:
            settings["profiles"] = {}
        
        # Add missing default profiles
        for profile_name in ConfigManager.DEFAULT_PROFILES:
            if profile_name not in settings["profiles"]:
                settings["profiles"][profile_name] = ConfigManager.PROFILE_SETTINGS.copy()

        # Validate current profile
        current_profile = settings.get("current_profile", "Profile 1")
        if current_profile not in settings["profiles"]:
            settings["profiles"][current_profile] = ConfigManager.PROFILE_SETTINGS.copy()
        
        # Fill in missing profile settings (but don't overwrite existing ones)
        for profile_name in settings["profiles"]:
            for key, default_value in ConfigManager.PROFILE_SETTINGS.items():
                if key not in settings["profiles"][profile_name]:
                    settings["profiles"][profile_name][key] = default_value

        # Fill in missing global settings (but don't overwrite existing ones)
        for key, default_value in ConfigManager.GLOBAL_SETTINGS.items():
            if key not in settings:
                settings[key] = default_value

        # Get current profile settings
        profile_settings = settings["profiles"][current_profile]

        return {
            "current_profile": current_profile,
            "profiles": settings["profiles"],
            **profile_settings,
            **{k: settings[k] for k in ConfigManager.GLOBAL_SETTINGS}
        }

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

    @staticmethod
    def check_corrupted_files():
        """Check for corrupted files but don't aggressively clean them."""
        # Only check settings file - don't touch lock files during startup
        if os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                file_size = os.path.getsize(ConfigManager.CONFIG_FILE)
                if file_size == 0:
                    print("WARNING: Settings file is empty - using defaults")
                else:
                    with open(ConfigManager.CONFIG_FILE, "r", encoding='utf-8') as file:
                        content = file.read().strip()
                        if not content:
                            print("WARNING: Settings file contains only whitespace - using defaults")
                        else:
                            try:
                                json.loads(content)
                                # Settings file is valid - no action needed
                            except json.JSONDecodeError as e:
                                print(f"WARNING: Settings file contains invalid JSON: {e}")
                                print("Will attempt to recover data instead of deleting file")
            except Exception as e:
                print(f"WARNING: Error checking settings file: {e}")

    @staticmethod
    def cleanup_corrupted_files():
        """Clean up any corrupted lock files and settings files."""
        import tempfile
        
        # Clean up lock file (this is safe to do)
        lock_file = os.path.join(tempfile.gettempdir(), "hushmix_single_instance.lock")
        if os.path.exists(lock_file):
            try:
                # Check if the lock file is corrupted or belongs to a dead process
                with open(lock_file, 'r') as f:
                    pid_str = f.read().strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        import psutil
                        if not psutil.pid_exists(pid):
                            try:
                                os.remove(lock_file)
                                print(f"Cleaned up stale lock file from dead process {pid}")
                            except OSError as e:
                                if e.winerror == 32:
                                    print(f"Stale lock file from dead process {pid} is being used - skipping cleanup")
                                else:
                                    print(f"Could not clean up stale lock file from dead process {pid}: {e}")
                        else:
                            try:
                                process = psutil.Process(pid)
                                if process.name().lower() not in ['hushmix.exe', 'python.exe', 'pythonw.exe']:
                                    try:
                                        os.remove(lock_file)
                                        print(f"Cleaned up lock file from non-Hushmix process {pid}")
                                    except OSError as e:
                                        if e.winerror == 32:
                                            print(f"Lock file from non-Hushmix process {pid} is being used - skipping cleanup")
                                        else:
                                            print(f"Could not clean up lock file from non-Hushmix process {pid}: {e}")
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                try:
                                    os.remove(lock_file)
                                    print(f"Cleaned up lock file from inaccessible process {pid}")
                                except OSError as e:
                                    if e.winerror == 32:
                                        print(f"Lock file from inaccessible process {pid} is being used - skipping cleanup")
                                    else:
                                        print(f"Could not clean up lock file from inaccessible process {pid}: {e}")
                    else:
                        try:
                            os.remove(lock_file)
                            print("Cleaned up lock file with invalid PID")
                        except OSError as e:
                            if e.winerror == 32:
                                print("Lock file with invalid PID is being used - skipping cleanup")
                            else:
                                print(f"Could not clean up lock file with invalid PID: {e}")
            except Exception as e:
                try:
                    os.remove(lock_file)
                    print(f"Cleaned up corrupted lock file")
                except OSError as remove_error:
                    if remove_error.winerror == 32:
                        print(f"Lock file is being used by another process - skipping cleanup")
                    else:
                        print(f"Could not clean up corrupted lock file: {remove_error}")
                except Exception as remove_error:
                    print(f"Could not clean up corrupted lock file: {remove_error}")
        
        # For settings file, we only check and warn - we don't delete it
        if os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                file_size = os.path.getsize(ConfigManager.CONFIG_FILE)
                if file_size == 0:
                    print("WARNING: Settings file is empty - using defaults but preserving original file")
                else:
                    with open(ConfigManager.CONFIG_FILE, "r", encoding='utf-8') as file:
                        content = file.read().strip()
                        if not content:
                            print("WARNING: Settings file contains only whitespace - using defaults but preserving original file")
                        else:
                            # Try to parse JSON to check if it's valid
                            try:
                                json.loads(content)
                                print("Settings file appears to be valid")
                            except json.JSONDecodeError as e:
                                print(f"WARNING: Settings file contains invalid JSON: {e}")
                                print("Will attempt to recover data instead of deleting file")
            except Exception as e:
                print(f"Error checking settings file: {e}")
