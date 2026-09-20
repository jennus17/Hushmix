"""Settings persistence for Hushmix.

Two long-standing problems are fixed here:

* **Profile fields were silently dropped.**  ``save_settings`` only copied keys
  listed in ``PROFILE_SETTINGS`` (three of them) into the current profile, so
  saving after changing the button settings could erase app-launch paths,
  keyboard shortcuts and button modes.  The schema below is now the single
  source of truth for every profile field, and unknown keys are preserved
  instead of discarded.
* **Non-atomic writes.**  Settings were written in place and read through a
  ``time.sleep(0.1)`` to dodge partial reads.  Writes are now atomic, which
  makes the sleep unnecessary and protects against corruption on crash.
"""

import json
import os
import re
import winreg

from utils.atomic_io import atomic_write_json, read_json
from utils.logging_setup import get_logger
from utils.app_paths import ensure_app_data_dir, settings_file

logger = get_logger("config_manager")


class ConfigManager:
    #: Path of the settings file.  Resolved from ``app_paths`` at import time so
    #: it never depends on the current working directory.
    CONFIG_FILE = settings_file()

    #: Path and serialised content of the last successful write.  Used to skip
    #: redundant disk writes: window position, theme changes and mute toggles
    #: all trigger saves, and rewriting an unchanged 4 KB file each time is
    #: wasteful (and blocks the GUI thread).
    _last_written = None
    _last_written_path = None

    #: The starting profile set for a fresh install.  Users add more from the
    #: main window, so there is no reason to pre-create five of them.
    DEFAULT_PROFILE_NAMES = ["Profile 1"]

    #: Profiles that were seeded by older versions and are removed when the user
    #: never put anything in them.
    LEGACY_DEFAULT_PROFILE_NAMES = ["Profile 2", "Profile 3", "Profile 4", "Profile 5"]

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

    # Every per-profile field, with the value used when it is missing.
    PROFILE_SETTINGS = {
        "applications": [],
        "mute_settings": [],
        "mute_state": [],
        "app_launch_enabled": [],
        "app_launch_paths": [],
        "keyboard_shortcut_enabled": [],
        "keyboard_shortcuts": [],
        "mute_button_modes": [],
        "app_button_modes": [],
        "shortcut_button_modes": [],
        "media_control_enabled": [],
        "media_control_actions": [],
        "media_control_button_modes": [],
    }

    #: Sentinels used to size a fresh profile when nothing is stored yet.
    BUTTON_COUNT = 5
    CHANNEL_COUNT = 7

    DEFAULT_PROFILES = DEFAULT_PROFILE_NAMES  # backwards compatible alias

    # ------------------------------------------------------------------ schema

    @staticmethod
    def _default_profile_data():
        """A fresh profile payload (deep, no shared mutable values)."""
        return {
            "applications": [""] * ConfigManager.CHANNEL_COUNT,
            "mute_settings": [True] * ConfigManager.BUTTON_COUNT,
            "mute_state": [False] * ConfigManager.CHANNEL_COUNT,
            "app_launch_enabled": [False] * ConfigManager.BUTTON_COUNT,
            "app_launch_paths": [""] * ConfigManager.BUTTON_COUNT,
            "keyboard_shortcut_enabled": [False] * ConfigManager.BUTTON_COUNT,
            "keyboard_shortcuts": [""] * ConfigManager.BUTTON_COUNT,
            "mute_button_modes": ["Click"] * ConfigManager.BUTTON_COUNT,
            "app_button_modes": ["Click"] * ConfigManager.BUTTON_COUNT,
            "shortcut_button_modes": ["Click"] * ConfigManager.BUTTON_COUNT,
            "media_control_enabled": [False] * ConfigManager.BUTTON_COUNT,
            "media_control_actions": ["Play/Pause"] * ConfigManager.BUTTON_COUNT,
            "media_control_button_modes": ["Click"] * ConfigManager.BUTTON_COUNT,
        }

    @staticmethod
    def empty_profile_data():
        """Profile payload with empty lists (no fabricated channels).

        Used when adding a brand new profile so the GUI can decide the sizes.
        """
        return {key: [] for key in ConfigManager.PROFILE_SETTINGS}

    @staticmethod
    def get_default_settings():
        """Complete default settings structure."""
        profiles = {
            name: ConfigManager._default_profile_data()
            for name in ConfigManager.DEFAULT_PROFILE_NAMES
        }
        return {
            "current_profile": ConfigManager.DEFAULT_PROFILE_NAMES[0],
            "profiles": profiles,
            **ConfigManager.GLOBAL_SETTINGS,
        }

    # ------------------------------------------------------------------ saving

    @staticmethod
    def save_settings(settings):
        """Merge *settings* into the config file.

        Global keys overwrite their counterparts; every other key is treated as
        profile data for ``current_profile`` and merged, so nothing is lost.
        """
        try:
            existing = ConfigManager._read_raw_settings()

            profiles = existing.get("profiles")
            if not isinstance(profiles, dict):
                profiles = {}

            for name in ConfigManager.DEFAULT_PROFILE_NAMES:
                profiles.setdefault(name, ConfigManager._default_profile_data())

            current_profile = settings.get("current_profile") or ConfigManager.DEFAULT_PROFILE_NAMES[0]
            if not isinstance(current_profile, str) or not current_profile.strip():
                current_profile = ConfigManager.DEFAULT_PROFILE_NAMES[0]
            profiles.setdefault(current_profile, ConfigManager._default_profile_data())

            profile_data = profiles[current_profile]
            if not isinstance(profile_data, dict):
                profile_data = ConfigManager._default_profile_data()
                profiles[current_profile] = profile_data

            for key, value in settings.items():
                if key == "current_profile" or key == "profiles":
                    continue
                if key in ConfigManager.GLOBAL_SETTINGS:
                    existing[key] = value
                else:
                    # Previously dropped: any profile-scoped key is now stored.
                    profile_data[key] = value

            existing["current_profile"] = current_profile
            existing["profiles"] = profiles

            ConfigManager._write_raw_settings(existing)
            logger.debug("Settings saved to %s", ConfigManager.CONFIG_FILE)
            return True

        except Exception as error:
            logger.exception("Error saving settings: %s", error)
            return False

    @staticmethod
    def save_all_settings(all_settings):
        """Write a complete settings structure (used by profile management)."""
        try:
            if not isinstance(all_settings, dict):
                raise TypeError("settings payload must be a dict")
            ConfigManager._write_raw_settings(all_settings)
            logger.debug("Full settings saved to %s", ConfigManager.CONFIG_FILE)
            return True
        except Exception as error:
            logger.exception("Error saving all settings: %s", error)
            return False

    @staticmethod
    def _write_raw_settings(data):
        """Serialise *data* and store it, skipping no-op writes.

        Returns ``True`` when the file is (or already was) up to date.
        """
        serialised = json.dumps(data, indent=4, sort_keys=True)
        path = ConfigManager.CONFIG_FILE
        if (
            serialised == ConfigManager._last_written
            and ConfigManager._last_written_path == path
            and os.path.exists(path)
        ):
            logger.debug("Settings unchanged - skipping the write")
            return True

        ensure_app_data_dir()
        atomic_write_json(path, data)
        ConfigManager._last_written = serialised
        ConfigManager._last_written_path = path
        return True

    # ----------------------------------------------------------------- loading

    @staticmethod
    def _read_raw_settings():
        data, error = read_json(ConfigManager.CONFIG_FILE, default={})
        if error:
            logger.warning("%s - using defaults for missing data", error)
        if not isinstance(data, dict):
            return {}
        return data

    @staticmethod
    def load_settings():
        """Load the current profile merged with the global settings."""
        full = ConfigManager.load_all()
        current_profile = full.get("current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0])
        profile = (full.get("profiles") or {}).get(current_profile) or {}

        return {
            "current_profile": current_profile,
            "profiles": full.get("profiles", {}),
            **profile,
            **{key: full.get(key, ConfigManager.GLOBAL_SETTINGS[key])
               for key in ConfigManager.GLOBAL_SETTINGS},
        }

    @staticmethod
    def load_all():
        """Load the complete structure (every profile) and repair it."""
        try:
            if not os.path.exists(ConfigManager.CONFIG_FILE):
                logger.info("No settings file found, using defaults")
                return ConfigManager._validate_and_fix_settings(
                    ConfigManager.get_default_settings()
                )

            data = ConfigManager._read_raw_settings()
            if not data:
                return ConfigManager._validate_and_fix_settings(
                    ConfigManager.get_default_settings()
                )

            return ConfigManager._validate_and_fix_settings(data)

        except Exception as error:
            logger.exception("Error loading settings: %s", error)
            return ConfigManager.get_default_settings()

    @staticmethod
    def _attempt_settings_recovery(content):
        """Recover what we can from a corrupted settings file."""
        logger.info("Attempting to recover settings from a corrupted file")
        try:
            recovered = {}
            for match in re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content):
                try:
                    partial = json.loads(match)
                except json.JSONDecodeError:
                    continue
                if isinstance(partial, dict):
                    recovered.update(partial)

            defaults = ConfigManager.get_default_settings()
            if recovered:
                logger.info("Recovered %d settings keys", len(recovered))
                defaults.update(recovered)
            else:
                logger.warning("Could not recover any settings - using defaults")
            return ConfigManager._validate_and_fix_settings(defaults)

        except Exception as error:
            logger.warning("Settings recovery failed: %s", error)
            return ConfigManager.get_default_settings()

    @staticmethod
    def _coerce_list(value, fallback):
        if isinstance(value, list):
            return list(value)
        if isinstance(value, tuple):
            return list(value)
        return list(fallback)

    @staticmethod
    def _validate_and_fix_settings(settings):
        """Repair a settings dict without throwing user data away."""
        if not isinstance(settings, dict):
            logger.warning("Settings is not a dictionary - using defaults")
            return ConfigManager.get_default_settings()

        profiles = settings.get("profiles")
        if not isinstance(profiles, dict):
            profiles = {}
        settings["profiles"] = profiles

        for name in ConfigManager.DEFAULT_PROFILE_NAMES:
            profiles.setdefault(name, {})

        current_profile = settings.get("current_profile")
        if not isinstance(current_profile, str) or not current_profile:
            current_profile = ConfigManager.DEFAULT_PROFILE_NAMES[0]
        profiles.setdefault(current_profile, {})

        defaults = ConfigManager._default_profile_data()
        for name, data in list(profiles.items()):
            if not isinstance(data, dict):
                profiles[name] = dict(defaults)
                logger.warning("Profile %r was not a dictionary - reset", name)
                continue
            for key, fallback in defaults.items():
                data[key] = ConfigManager._coerce_list(data.get(key), fallback)

        for key, fallback in ConfigManager.GLOBAL_SETTINGS.items():
            if key not in settings:
                settings[key] = fallback

        # Repair a window position that is not a number.
        for axis in ("window_x", "window_y"):
            value = settings.get(axis)
            if value is not None:
                try:
                    settings[axis] = int(value)
                except (TypeError, ValueError):
                    settings[axis] = None

        try:
            interval = int(settings.get("update_check_interval") or 1800)
        except (TypeError, ValueError):
            interval = 1800
        settings["update_check_interval"] = max(60, interval)

        current_profile = ConfigManager._promote_current_profile(profiles, current_profile)
        ConfigManager._drop_unused_default_profiles(profiles, current_profile)

        settings["current_profile"] = current_profile

        return {
            "current_profile": current_profile,
            "profiles": profiles,
            **profiles[current_profile],
            **{key: settings[key] for key in ConfigManager.GLOBAL_SETTINGS},
        }

    # --------------------------------------------------------------- accessors

    @staticmethod
    def _promote_current_profile(profiles, current_profile):
        """Move an empty selected profile's index onto the first used profile.

        The default profile is now ``Profile 1`` alone.  A settings file written
        by an older version may still point at an empty ``Profile 3``, which
        would otherwise greet the user with a blank window.
        """
        selected = profiles.get(current_profile)
        if not isinstance(selected, dict) or ConfigManager.profile_has_data(selected):
            return current_profile

        for name, data in profiles.items():
            if name == current_profile:
                continue
            if isinstance(data, dict) and ConfigManager.profile_has_data(data):
                logger.info(
                    "Profile %r is empty - switching the current profile to %r",
                    current_profile,
                    name,
                )
                return name

        return current_profile

    @staticmethod
    def is_prunable_default(name, profile, current_profile):
        """True for a legacy default slot the user never touched."""
        if name in ConfigManager.DEFAULT_PROFILE_NAMES:
            return False
        if name == current_profile or name not in ConfigManager.LEGACY_DEFAULT_PROFILE_NAMES:
            return False
        return isinstance(profile, dict) and not ConfigManager.profile_has_data(profile)

    @staticmethod
    def _drop_unused_default_profiles(profiles, current_profile):
        """Delete the empty profile slots older versions used to pre-create."""
        for name in list(profiles):
            if ConfigManager.is_prunable_default(
                name, profiles.get(name), current_profile
            ):
                del profiles[name]
                logger.info("Removed the unused default profile %r", name)

        if not profiles:
            profiles[ConfigManager.DEFAULT_PROFILE_NAMES[0]] = (
                ConfigManager._default_profile_data()
            )

    @staticmethod
    def profile_has_data(profile):
        """True when a profile holds something the user actually configured.

        Only fields the user edits count.  The defaults themselves are *not*
        evidence of use: ``mute_settings`` is ``[True] * 5`` and
        ``media_control_actions`` is ``["Play/Pause"] * 5``, so a naive
        "any non-empty value" test marked every untouched profile as used and
        made pruning impossible.
        """
        if not isinstance(profile, dict):
            return False

        for key in ("applications", "app_launch_paths", "keyboard_shortcuts",
                    "mute_button_modes", "app_button_modes", "shortcut_button_modes",
                    "media_control_actions", "media_control_button_modes"):
            value = profile.get(key) or []
            # Both "Click" (button mode) and "Play/Pause" (media action) are
            # defaults, so only deviations from them count.
            if any(
                item and str(item).strip() and str(item).strip() not in ("Click", "Play/Pause")
                for item in value
            ):
                return True

        for key in ("app_launch_enabled", "keyboard_shortcut_enabled",
                    "media_control_enabled"):
            if any(bool(item) for item in profile.get(key) or []):
                return True

        # The user muted a channel by hand.
        return any(bool(item) for item in profile.get("mute_state") or [])

    @staticmethod
    def prune_unused_default_profiles():
        """Drop leftover empty default profiles from the config file.

        Returns the names that were removed.
        """
        settings = ConfigManager._read_raw_settings()
        profiles = settings.get("profiles")
        if not isinstance(profiles, dict):
            return []

        before = set(profiles)
        current = settings.get("current_profile") or ConfigManager.DEFAULT_PROFILE_NAMES[0]
        ConfigManager._drop_unused_default_profiles(profiles, current)
        removed = sorted(before - set(profiles))

        if removed:
            settings["profiles"] = profiles
            ConfigManager._write_raw_settings(settings)

        return removed

    @staticmethod
    def get_all_settings():
        """Backwards compatible alias for :meth:`load_settings`."""
        return ConfigManager.load_settings()

    @staticmethod
    def get_profile_names():
        """Ordered list of known profile names."""
        settings = ConfigManager._read_raw_settings()
        names = list(ConfigManager.DEFAULT_PROFILE_NAMES)

        stored = settings.get("profiles")
        if isinstance(stored, dict):
            for name in stored:
                if name not in names:
                    names.append(name)

        current = settings.get("current_profile")
        if isinstance(current, str) and current and current not in names:
            names.append(current)

        # Hide legacy empty default slots even before the file is rewritten, so
        # the dropdown never lists profiles the user did not create.
        profiles = settings.get("profiles")
        if isinstance(profiles, dict):
            names = [
                name
                for name in names
                if not ConfigManager.is_prunable_default(
                    name, profiles.get(name), current
                )
            ]

        return names

    @staticmethod
    def add_profile(name, copy_from=None):
        """Create a profile, optionally seeded from another one."""
        name = (name or "").strip()
        if not name:
            return False, "Profile name cannot be empty"

        settings = ConfigManager._read_raw_settings()
        profiles = settings.setdefault("profiles", {})
        if name in profiles:
            return False, f"Profile '{name}' already exists"

        if copy_from and isinstance(profiles.get(copy_from), dict):
            profiles[name] = {
                key: ConfigManager._coerce_list(value, [])
                for key, value in profiles[copy_from].items()
            }
        else:
            profiles[name] = ConfigManager.empty_profile_data()

        ConfigManager._write_raw_settings(settings)
        return True, name

    @staticmethod
    def delete_profile(name):
        """Delete a profile (the last remaining one cannot be removed)."""
        settings = ConfigManager._read_raw_settings()
        profiles = settings.get("profiles") or {}
        if name not in profiles:
            return False, f"Profile '{name}' does not exist"
        if len(profiles) <= 1:
            return False, "At least one profile must remain"

        del profiles[name]

        if settings.get("current_profile") == name:
            settings["current_profile"] = next(iter(profiles))

        ConfigManager._write_raw_settings(settings)
        return True, settings["current_profile"]

    @staticmethod
    def rename_profile(old_name, new_name):
        """Rename a profile, keeping its order."""
        new_name = (new_name or "").strip()
        if not new_name:
            return False, "Profile name cannot be empty"

        settings = ConfigManager._read_raw_settings()
        profiles = settings.get("profiles") or {}
        if old_name not in profiles:
            return False, f"Profile '{old_name}' does not exist"
        if new_name in profiles:
            return False, f"Profile '{new_name}' already exists"

        renamed = {}
        for key, value in profiles.items():
            renamed[new_name if key == old_name else key] = value
        settings["profiles"] = renamed

        if settings.get("current_profile") == old_name:
            settings["current_profile"] = new_name

        ConfigManager._write_raw_settings(settings)
        return True, new_name

    # --------------------------------------------------------------- autostart

    RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "Hushmix"

    @staticmethod
    def toggle_auto_startup(enable, app_name=None, executable_path=None):
        """Add or remove the auto-startup registry entry."""
        app_name = app_name or ConfigManager.APP_NAME
        try:
            if enable:
                if not executable_path:
                    from utils.app_paths import startup_command

                    executable_path = startup_command()
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    ConfigManager.RUN_KEY,
                    0,
                    winreg.KEY_SET_VALUE,
                ) as registry_key:
                    winreg.SetValueEx(
                        registry_key, app_name, 0, winreg.REG_SZ, executable_path
                    )
                logger.info("Auto-startup enabled for %s", app_name)
            else:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        ConfigManager.RUN_KEY,
                        0,
                        winreg.KEY_SET_VALUE,
                    ) as registry_key:
                        winreg.DeleteValue(registry_key, app_name)
                    logger.info("Auto-startup disabled for %s", app_name)
                except FileNotFoundError:
                    logger.debug("Auto-startup was already disabled")
            return True
        except OSError as error:
            logger.warning("Error managing auto-startup: %s", error)
            return False

    @staticmethod
    def is_auto_startup_enabled(app_name=None):
        """True when the Run-key entry exists."""
        app_name = app_name or ConfigManager.APP_NAME
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, ConfigManager.RUN_KEY, 0, winreg.KEY_READ
            ) as registry_key:
                value, _ = winreg.QueryValueEx(registry_key, app_name)
                return bool(value)
        except FileNotFoundError:
            return False
        except OSError as error:
            logger.warning("Error checking auto-startup status: %s", error)
            return False

    # ------------------------------------------------------- integrity helpers

    @staticmethod
    def check_corrupted_files():
        """Warn about a damaged settings file without touching it."""
        path = ConfigManager.CONFIG_FILE
        if not os.path.exists(path):
            return True

        data, error = read_json(path, default=None)
        if error:
            logger.warning("Settings file problem: %s", error)
            return False
        if data is None:
            return False
        return True

    @staticmethod
    def cleanup_corrupted_files():
        """Backwards compatible alias; stale lock files are no longer used."""
        return ConfigManager.check_corrupted_files()
