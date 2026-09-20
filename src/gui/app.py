"""Application object: wires the controllers, the GUI and the settings together.

Changes worth noting:

* **Every profile field is round-tripped.**  ``load_settings``/``save_settings``
  used to handle seven of the thirteen profile fields, so app-launch paths,
  keyboard shortcuts, media-control settings and button modes were lost when the
  app was restarted.  They are now driven by :data:`utils.config_manager.ConfigManager.PROFILE_SETTINGS`.
* **Actions are marshalled onto the Tk thread.**  The tray menu runs on the
  pystray thread and the serial reader on its own thread; both now hand work to
  :class:`utils.deferred_actions.DeferredActions`.
* **Shutdown is ordered.**  The tray icon is stopped first, the serial and audio
  resources are released, and only then does the process exit - the old code
  called ``os._exit(0)`` while the tray thread was still running.
"""

import ctypes
import os
import tkinter.messagebox as messagebox

import customtkinter as ctk

from controllers.audio_controller import AudioController
from controllers.button_actions import ButtonActions
from controllers.profile_manager import ProfileManager
from controllers.serial_controller import SerialController
from controllers.volume_manager import VolumeManager

from gui.gui_components import GUIComponents
from gui.help_window import HelpWindow
from gui.buttonSettings_window import ButtonSettingsWindow
from gui.settings_window import SettingsWindow
from gui.window_manager import WindowManager

from utils.color_utils import darken_color, get_windows_accent_color
from utils.config_manager import ConfigManager
from utils.deferred_actions import DeferredActions
from utils.dpi_manager import DPIManager
from utils.enhanced_version_manager import EnhancedVersionManager
from utils.logging_setup import get_logger
from utils.settings_manager import SettingsManager

logger = get_logger("app")

CHANNEL_COUNT = ConfigManager.CHANNEL_COUNT
BUTTON_COUNT = ConfigManager.BUTTON_COUNT

#: "list of Tk variables" fields and how to build one default entry.
#: ``mute`` is the per-button "mute action enabled" list, ``mute_settings`` is
#: the same list as stored in the settings file.
VAR_FIELDS = {
    "mute": ("BooleanVar", True),
    "mute_settings": ("BooleanVar", True),
    "app_launch_enabled": ("BooleanVar", False),
    "app_launch_paths": ("StringVar", ""),
    "keyboard_shortcut_enabled": ("BooleanVar", False),
    "keyboard_shortcuts": ("StringVar", ""),
    "mute_button_modes": ("StringVar", "Click"),
    "app_button_modes": ("StringVar", "Click"),
    "shortcut_button_modes": ("StringVar", "Click"),
    "media_control_enabled": ("BooleanVar", False),
    "media_control_actions": ("StringVar", "Play/Pause"),
    "media_control_button_modes": ("StringVar", "Click"),
}


def _make_var(kind, value):
    if kind == "BooleanVar":
        return ctk.BooleanVar(value=bool(value))
    return ctk.StringVar(value="" if value is None else str(value))


def _make_default_var(field):
    kind, default = VAR_FIELDS[field]
    return _make_var(kind, default)


class HushmixApp:
    def __init__(self, root):
        self.root = root

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception as error:
            logger.debug("Could not set DPI awareness: %s", error)

        try:
            self.root.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass

        self.setup_variables()

        self.audio_controller = AudioController()

        # Older versions pre-created five empty profiles; drop the untouched
        # ones so the dropdown only lists profiles that mean something.
        try:
            removed = ConfigManager.prune_unused_default_profiles()
            if removed:
                logger.info("Removed unused default profiles: %s", ", ".join(removed))
        except Exception as error:
            logger.warning("Could not prune unused default profiles: %s", error)

        self.settings_window = None
        self.buttonSettings_window = None
        self.help_window = None

        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)

        #: Runs queued work from the serial/tray threads on the Tk thread.
        self.deferred_actions = DeferredActions(self.root)

        self.settings_manager = SettingsManager(self)

        self.window_manager = WindowManager(self.root, self)
        self.gui_components = GUIComponents(self)
        self.button_actions = ButtonActions(self)
        self.volume_manager = VolumeManager(self)

        self.load_settings()

        self.serial_controller = SerialController(
            self.volume_manager.handle_volume_update,
            self.button_actions.handle_button_update,
            self.handle_connection_status,
        )

        self.profile_manager = ProfileManager(self)
        self.dpi_manager = DPIManager()

        self.window_manager.setup_window()
        self.gui_components.setup_gui()
        self.gui_components.refresh_gui()

        self.dpi_manager.initialize_dpi_scaling(
            self.root, "main window", self._on_dpi_changed
        )

        self.version_manager = EnhancedVersionManager(self.root, self.settings_manager)
        self._shutting_down = False
        self.settings_manager.settings_vars["profiles"] = ConfigManager.get_profile_names()

    # --------------------------------------------------------------- variables

    def setup_variables(self):
        """Initialise the in-memory state shared with the controllers."""
        self.current_apps = [""] * CHANNEL_COUNT
        self.volumes = []
        self.previous_volumes = [None] * CHANNEL_COUNT
        self.running = True

        self.muted_state = [False] * CHANNEL_COUNT
        self.current_mute_state = [False] * CHANNEL_COUNT

        # Every per-button list (including ``mute``) is created by load_settings
        # through VAR_FIELDS, so nothing is declared twice.
        for field in VAR_FIELDS:
            setattr(self, field, [])

    # ---------------------------------------------------------------- settings

    def _build_var_list(self, field, values, length):
        """Create the Tk variables for a profile field."""
        kind, default = VAR_FIELDS[field]
        stored = values if isinstance(values, (list, tuple)) else []

        variables = [_make_var(kind, value) for value in stored[:length]]

        while len(variables) < length:
            variables.append(_make_var(kind, default))

        return variables

    def load_settings(self):
        """Load the current profile into the in-memory state."""
        settings = self.settings_manager.load_from_config()

        current_profile = settings.get("current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0])
        self.settings_manager.settings_vars["current_profile"] = current_profile

        self.current_apps = list(settings.get("applications") or [])
        while len(self.current_apps) < CHANNEL_COUNT:
            self.current_apps.append("")

        for field in VAR_FIELDS:
            length = BUTTON_COUNT
            setattr(self, field, self._build_var_list(field, settings.get(field), length))

        mute_state = settings.get("mute_state") or []
        self.current_mute_state = self._fit_mute_state(mute_state)
        self.muted_state = list(self.current_mute_state)
        self.previous_volumes = [None] * len(self.current_apps)

        self._publish_profile_state()

        listbox = getattr(self.gui_components, "profile_listbox", None)
        if listbox is not None:
            try:
                listbox.set(current_profile)
            except Exception:
                pass

    @staticmethod
    def _fit_mute_state(values):
        state = [bool(value) for value in (values or [])][:CHANNEL_COUNT]
        while len(state) < CHANNEL_COUNT:
            state.append(False)
        return state

    def _collect_profile_state(self):
        """Read the current GUI state into ``settings_manager``."""
        variables = self.settings_manager.settings_vars

        if getattr(self, "gui_components", None) is not None:
            entries = getattr(self.gui_components, "entries", None)
            if entries:
                variables["applications"] = [entry.get() for entry in entries]
            listbox = getattr(self.gui_components, "profile_listbox", None)
            if listbox is not None:
                try:
                    selected = listbox.get()
                except Exception:
                    selected = None
                # Only trust a real selection - an empty or missing value must
                # not silently redirect the save to a different profile.
                if selected:
                    variables["current_profile"] = selected

        variables["applications"] = list(self.current_apps)
        variables["mute_state"] = list(self.current_mute_state)

        for field in VAR_FIELDS:
            variables[field] = [variable.get() for variable in getattr(self, field)]

        return variables

    def _publish_profile_state(self):
        """Mirror the in-memory state into ``settings_manager``."""
        variables = self.settings_manager.settings_vars
        variables["applications"] = list(self.current_apps)
        variables["mute_state"] = list(self.current_mute_state)
        for field in VAR_FIELDS:
            variables[field] = [variable.get() for variable in getattr(self, field)]

    def save_settings(self):
        """Persist the current profile and the global settings."""
        if self._shutting_down:
            return True

        self._collect_profile_state()
        current_profile = self.settings_manager.settings_vars.get(
            "current_profile", ConfigManager.DEFAULT_PROFILE_NAMES[0]
        )
        self.profile_manager.save_current_profile_data(current_profile)
        return self.settings_manager.save_to_config()

    def save_applications(self, event=None):
        """Save applications while the user types in a channel field."""
        if self._shutting_down:
            return
        self.profile_manager.save_applications(event)

    # ------------------------------------------------------------ connectivity

    def handle_connection_status(self, is_connected):
        """Serial thread callback - marshal onto the Tk thread."""
        self.deferred_actions.submit(self.update_connection_status)

    def update_connection_status(self):
        """Show or hide the "Mixer Disconnected" banner."""
        label = getattr(self.gui_components, "connection_status_label", None)
        if not label:
            return

        # ``SerialController`` reports its first status from its constructor,
        # which runs before ``self.serial_controller`` is assigned.
        controller = getattr(self, "serial_controller", None)
        is_connected = bool(controller and controller.get_connection_status())

        try:
            if is_connected:
                label.grid_remove()
            else:
                label.grid()
                label.configure(text="Mixer Disconnected", text_color="red3")
        except Exception as error:
            logger.debug("Could not update the connection banner: %s", error)

    def toggle_mute(self, index):
        """Toggle mute for a channel."""
        self.volume_manager.toggle_mute(index)

    # ---------------------------------------------------------------- profiles

    def on_profile_change(self, profile):
        """Switch to another profile."""
        self.profile_manager.on_profile_change(profile)

    def add_profile(self, name, copy_current=True):
        """Create a profile and refresh the dropdown.

        Returns ``True`` on success; on failure the reason is returned by
        :meth:`_add_profile` and surfaced here as a message box.  The GUI calls
        :meth:`_add_profile` directly when it wants to show its own message.
        """
        success, message = self._add_profile(name, copy_current)
        if not success:
            messagebox.showerror("Hushmix", message, parent=self.root)
        return success

    def _add_profile(self, name, copy_current=True):
        """Create a profile; returns ``(success, message)``."""
        current = self.settings_manager.settings_vars.get("current_profile")
        source = current if copy_current else None

        # Persist the current profile first so the copy is up to date.
        if copy_current:
            self.save_settings()

        success, result = ConfigManager.add_profile(name, copy_from=source)
        if not success:
            return False, result

        self.profile_manager.refresh_profile_list(current)
        logger.info("Created profile %s", result)
        return True, result

    def delete_profile(self, name):
        """Delete a profile, switching away from it first if necessary.

        Deleting the *current* profile used to be refused with "switch to
        another profile before deleting this one", which made the ✕ button look
        broken because the current profile is always the selected one.  The app
        now switches to a remaining profile and then deletes the requested one.
        """
        if not name:
            return False, "No profile selected"

        names = ConfigManager.get_profile_names()
        if name not in names:
            return False, f"Profile '{name}' does not exist"

        if len(names) <= 1:
            messagebox.showwarning(
                "Hushmix",
                "This is the only profile.\n\n"
                "Add another profile first if you want to remove this one.",
                parent=self.root,
            )
            return False, "only profile"

        if not messagebox.askyesno(
            "Hushmix", f"Delete profile '{name}'?", parent=self.root
        ):
            return False, "cancelled"

        current = self.settings_manager.settings_vars.get("current_profile")
        if name == current:
            # Move to the next profile before removing the active one, so the
            # application is never left without a profile to display.
            replacement = next(
                (candidate for candidate in names if candidate != name), None
            )
            if replacement:
                self.on_profile_change(replacement)

        success, result = ConfigManager.delete_profile(name)
        if not success:
            messagebox.showerror("Hushmix", result, parent=self.root)
            return False, result

        self.profile_manager.refresh_profile_list(
            self.settings_manager.settings_vars.get("current_profile")
        )
        logger.info("Deleted profile %s", name)
        return True, result

    # ------------------------------------------------------------------- popups

    def _reopen(self, attribute, opener, *args):
        """Close an existing popup and open a fresh one."""
        existing = getattr(self, attribute, None)
        if existing is not None:
            try:
                existing.close()
            except Exception:
                pass
            setattr(self, attribute, None)
            self.root.after(100, lambda: opener(*args))
            return
        opener(*args)

    def show_settings(self):
        """Open the settings window."""
        self._reopen("settings_window", self._open_settings)

    def _open_settings(self):
        self.settings_window = SettingsWindow(
            self.root, ConfigManager, self.settings_manager, self.on_settings_close
        )

    def show_buttonSettings(self, index):
        """Open the per-button settings window using a 0-based button index."""
        self._reopen("buttonSettings_window", self._open_buttonSettings, index)

    def _open_buttonSettings(self, index):
        self.buttonSettings_window = ButtonSettingsWindow(
            self.root,
            index,
            self.mute,
            self.app_launch_enabled,
            self.app_launch_paths,
            self.keyboard_shortcut_enabled,
            self.keyboard_shortcuts,
            self.mute_button_modes,
            self.app_button_modes,
            self.shortcut_button_modes,
            self.media_control_enabled,
            self.media_control_actions,
            self.media_control_button_modes,
            self.on_buttonSettings_close,
        )

    def show_help(self):
        """Open the help window."""
        self._reopen("help_window", self._open_help)

    def _open_help(self):
        self.help_window = HelpWindow(self.root, self)

    def on_settings_close(self):
        """Handle the settings window closing."""
        self.settings_window = None
        self.save_settings()
        self.apply_theme_changes()

    def on_buttonSettings_close(self):
        """Handle the button settings window closing."""
        self.buttonSettings_window = None
        self.save_settings()
        self.apply_theme_changes()

    def on_help_close(self):
        """Handle the help window closing."""
        self.help_window = None

    def apply_theme_changes(self):
        """Apply a theme change without restarting."""
        try:
            dark_mode = self.settings_manager.get_setting("dark_mode", True)
            ctk.set_appearance_mode("dark" if dark_mode else "light")
            self.root.update_idletasks()
            self.gui_components.update_theme_colors()
            logger.info("Theme switched to %s", "dark" if dark_mode else "light")
        except Exception as error:
            logger.warning("Error applying theme changes: %s", error)

    # ------------------------------------------------------------------ shutdown

    def on_close(self):
        """Hide to the tray instead of exiting."""
        self.window_manager.save_window_position()
        self.root.withdraw()

    def on_exit(self, icon=None, item=None):
        """Exit from the tray menu (runs on the pystray thread)."""
        # Hop onto the Tk thread; everything below touches widgets.
        try:
            self.root.after(0, self.shutdown)
        except Exception:
            self.shutdown()

    def shutdown(self):
        """Release every resource and terminate the process."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self.running = False

        logger.info("Shutting down")

        try:
            self.window_manager.save_window_position()
        except Exception as error:
            logger.debug("Could not save the window position: %s", error)

        if self.deferred_actions is not None:
            self.deferred_actions.stop()

        for name, attribute in (
            ("settings window", "settings_window"),
            ("button settings window", "buttonSettings_window"),
            ("help window", "help_window"),
        ):
            window = getattr(self, attribute, None)
            if window is not None:
                try:
                    window.close()
                except Exception as error:
                    logger.debug("Error closing the %s: %s", name, error)

        if self.version_manager is not None:
            try:
                self.version_manager.stop()
            except Exception as error:
                logger.debug("Error stopping the update checker: %s", error)

        for name, controller in (
            ("serial controller", getattr(self, "serial_controller", None)),
            ("audio controller", getattr(self, "audio_controller", None)),
        ):
            if controller is None:
                continue
            try:
                controller.cleanup()
            except Exception as error:
                logger.debug("Error cleaning up the %s: %s", name, error)

        try:
            self.window_manager.cleanup()
        except Exception as error:
            logger.debug("Error cleaning up the window manager: %s", error)

        try:
            self.root.quit()
            self.root.destroy()
        except Exception as error:
            logger.debug("Error destroying the root window: %s", error)

        logger.info("Hushmix stopped")
        # All resources are released; skip atexit handlers that would only
        # re-run cleanup on a half-torn-down interpreter.
        os._exit(0)

    def _on_dpi_changed(self):
        if getattr(self, "gui_components", None) is not None:
            self.gui_components.refresh_gui()
