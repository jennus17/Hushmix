from tkinter import messagebox
import threading
import pythoncom
import ctypes
import sys
import os
import time
import customtkinter as ctk

from controllers.audio_controller import AudioController
from controllers.serial_controller import SerialController
from controllers.button_actions import ButtonActions
from controllers.volume_manager import VolumeManager
from controllers.profile_manager import ProfileManager

from utils.config_manager import ConfigManager
from utils.settings_manager import SettingsManager
from utils.icon_manager import IconManager
from utils.color_utils import get_windows_accent_color, darken_color

from gui.settings_window import SettingsWindow
from gui.buttonSettings_window import ButtonSettingsWindow
from gui.window_manager import WindowManager
from gui.gui_components import GUIComponents

from utils.enhanced_version_manager import EnhancedVersionManager


class HushmixApp:
    def __init__(self, root):
        self.root = root

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception as e:
            print(f"Error setting DPI awareness: {e}")

        self.root.tk.call("tk", "scaling", 1.0)

        self.setup_variables()

        self.audio_controller = AudioController()
        
        self.settings_window = None
        self.buttonSettings_window = None

        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)

        self.settings_manager = SettingsManager(self)

        self.window_manager = WindowManager(self.root, self)
        self.gui_components = GUIComponents(self)
        self.button_actions = ButtonActions(self)
        self.volume_manager = VolumeManager(self)
        
        self.serial_controller = SerialController(
            self.volume_manager.handle_volume_update, 
            self.button_actions.handle_button_update, 
            self.handle_connection_status
        )

        self.load_settings()
        
        self.profile_manager = ProfileManager(self)

        self.window_manager.setup_window()
        self.gui_components.setup_gui()
        self.gui_components.refresh_gui()

        if self.settings_manager.get_setting("launch_in_tray"):
            self.root.withdraw()
        else:
            self.root.deiconify()

        self.version_manager = EnhancedVersionManager(root, self.settings_manager)

    def setup_variables(self):
        """Initialize application variables."""
        self.current_apps = []
        self.volumes = []
        self.previous_volumes = []
        self.running = True
        
        self.mute = []
        self.muted_state = []
        self.current_mute_state = []
        self.app_launch_enabled = []
        self.app_launch_paths = []
        self.keyboard_shortcut_enabled = []
        self.keyboard_shortcuts = []
        self.mute_button_modes = []
        self.app_button_modes = []
        self.shortcut_button_modes = []
        self.media_control_enabled = []
        self.media_control_actions = []
        self.media_control_button_modes = []

    def handle_connection_status(self, is_connected):
        """Handle connection status changes from serial controller."""
        def update_ui():
            self.update_connection_status()
        self.root.after(0, update_ui)
    
    def update_connection_status(self):
        """Update the connection status label."""
        if self.gui_components.connection_status_label:
            is_connected = self.serial_controller.get_connection_status()
            if is_connected:
                self.gui_components.connection_status_label.grid_remove()
            else:
                self.gui_components.connection_status_label.grid()
                self.gui_components.connection_status_label.configure(
                    text="Mixer Disconnected",
                    text_color="red3"
                )

    def toggle_mute(self, index):
        """Toggle mute/unmute and apply volume."""
        self.volume_manager.toggle_mute(index)

    def on_exit(self, icon=None, item=None):
        """Handle application exit."""
        self.window_manager.save_window_position()
        
        self.window_manager.cleanup()

        self.running = False

        if hasattr(self, "serial_controller"):
            try:
                self.serial_controller.cleanup()
            except Exception as e:
                print(f"Error cleaning up serial controller: {e}")

        if hasattr(self, "audio_controller"):
            try:
                self.audio_controller.cleanup()
            except Exception as e:
                print(f"Error cleaning up audio controller: {e}")

        if hasattr(self, "settings_window") and self.settings_window:
            try:
                self.settings_window.window.destroy()
            except Exception as e:
                print(f"Error destroying settings window: {e}")

        if hasattr(self, "root") and self.root:
            try:
                self.root.quit()
            except Exception as e:
                print(f"Error quitting root: {e}")

        try:
            import os
            os._exit(0)
        except Exception as e:
            print(f"Error during force exit: {e}")
            sys.exit(0)

    def on_close(self):
        """Handle window close button."""
        self.window_manager.save_window_position()
        self.root.withdraw()

    def show_buttonSettings(self, index):
        """Show settings window."""
        if self.buttonSettings_window is not None:
            try:
                if (
                    hasattr(self.buttonSettings_window, "window")
                    and self.buttonSettings_window.window.winfo_exists()
                ):
                    self.buttonSettings_window.window.lift()
                    return
                else:
                    self.buttonSettings_window = None
            except Exception:
                self.buttonSettings_window = None

        button_index = index - 1
        while len(self.mute) <= button_index:
            self.mute.append(ctk.BooleanVar(value=True))
        while len(self.app_launch_enabled) <= button_index:
            self.app_launch_enabled.append(ctk.BooleanVar(value=False))
        while len(self.app_launch_paths) <= button_index:
            self.app_launch_paths.append(ctk.StringVar(value=""))
        while len(self.keyboard_shortcut_enabled) <= button_index:
            self.keyboard_shortcut_enabled.append(ctk.BooleanVar(value=False))
        while len(self.keyboard_shortcuts) <= button_index:
            self.keyboard_shortcuts.append(ctk.StringVar(value=""))
        while len(self.mute_button_modes) <= button_index:
            self.mute_button_modes.append(ctk.StringVar(value="Click"))
        while len(self.app_button_modes) <= button_index:
            self.app_button_modes.append(ctk.StringVar(value="Click"))
        while len(self.shortcut_button_modes) <= button_index:
            self.shortcut_button_modes.append(ctk.StringVar(value="Click"))
        while len(self.media_control_enabled) <= button_index:
            self.media_control_enabled.append(ctk.BooleanVar(value=False))
        while len(self.media_control_actions) <= button_index:
            self.media_control_actions.append(ctk.StringVar(value="Play/Pause"))
        while len(self.media_control_button_modes) <= button_index:
            self.media_control_button_modes.append(ctk.StringVar(value="Click"))

        self.buttonSettings_window = ButtonSettingsWindow(
            self.root,
            button_index,
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

    def on_buttonSettings_close(self):
        """Handle settings window close."""
        if self.buttonSettings_window and hasattr(self.buttonSettings_window, "window"):
            try:
                self.buttonSettings_window.window.destroy()
            except Exception:
                pass
        self.buttonSettings_window = None
        self.save_settings()
        
        self.apply_theme_changes()

    def load_settings(self):
        """Load settings from config file."""
        settings = self.settings_manager.load_from_config()

        current_profile = settings.get("current_profile")
        self.settings_manager.settings_vars["current_profile"] = current_profile

        self.current_apps = settings.get("applications", [])
        self.settings_manager.settings_vars["applications"] = self.current_apps
        profile_mute = settings.get("mute_settings", [])
        profile_mute_state = settings.get("mute_state", [])

        self.mute = []
        if profile_mute:
            for mute_value in profile_mute:
                var = ctk.BooleanVar(value=mute_value)
                self.mute.append(var)
        else:
            for _ in range(5):
                var = ctk.BooleanVar(value=True)
                self.mute.append(var)

        if profile_mute_state:
            self.current_mute_state = profile_mute_state.copy()
        else:
            self.current_mute_state = [False] * 7
        self.muted_state = self.current_mute_state.copy()

        profile_app_launch_enabled = settings.get("app_launch_enabled", [])
        profile_app_launch_paths = settings.get("app_launch_paths", [])

        self.app_launch_enabled = []
        if profile_app_launch_enabled:
            for enabled_value in profile_app_launch_enabled:
                var = ctk.BooleanVar(value=enabled_value)
                self.app_launch_enabled.append(var)
        else:
            for _ in range(5):
                var = ctk.BooleanVar(value=False)
                self.app_launch_enabled.append(var)

        self.app_launch_paths = []
        if profile_app_launch_paths:
            for path_value in profile_app_launch_paths:
                var = ctk.StringVar(value=path_value)
                self.app_launch_paths.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="")
                self.app_launch_paths.append(var)

        profile_keyboard_shortcut_enabled = settings.get("keyboard_shortcut_enabled", [])
        profile_keyboard_shortcuts = settings.get("keyboard_shortcuts", [])

        self.keyboard_shortcut_enabled = []
        if profile_keyboard_shortcut_enabled:
            for enabled_value in profile_keyboard_shortcut_enabled:
                var = ctk.BooleanVar(value=enabled_value)
                self.keyboard_shortcut_enabled.append(var)
        else:
            for _ in range(5):
                var = ctk.BooleanVar(value=False)
                self.keyboard_shortcut_enabled.append(var)

        self.keyboard_shortcuts = []
        if profile_keyboard_shortcuts:
            for shortcut_value in profile_keyboard_shortcuts:
                var = ctk.StringVar(value=shortcut_value)
                self.keyboard_shortcuts.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="")
                self.keyboard_shortcuts.append(var)

        profile_mute_button_modes = settings.get("mute_button_modes", [])
        profile_app_button_modes = settings.get("app_button_modes", [])
        profile_shortcut_button_modes = settings.get("shortcut_button_modes", [])

        self.mute_button_modes = []
        if profile_mute_button_modes:
            for mode_value in profile_mute_button_modes:
                var = ctk.StringVar(value=mode_value)
                self.mute_button_modes.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="Click")
                self.mute_button_modes.append(var)

        self.app_button_modes = []
        if profile_app_button_modes:
            for mode_value in profile_app_button_modes:
                var = ctk.StringVar(value=mode_value)
                self.app_button_modes.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="Click")
                self.app_button_modes.append(var)

        self.shortcut_button_modes = []
        if profile_shortcut_button_modes:
            for mode_value in profile_shortcut_button_modes:
                var = ctk.StringVar(value=mode_value)
                self.shortcut_button_modes.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="Click")
                self.shortcut_button_modes.append(var)

        profile_media_control_enabled = settings.get("media_control_enabled", [])
        profile_media_control_actions = settings.get("media_control_actions", [])
        profile_media_control_button_modes = settings.get("media_control_button_modes", [])

        self.media_control_enabled = []
        if profile_media_control_enabled:
            for enabled_value in profile_media_control_enabled:
                var = ctk.BooleanVar(value=enabled_value)
                self.media_control_enabled.append(var)
        else:
            for _ in range(5):
                var = ctk.BooleanVar(value=False)
                self.media_control_enabled.append(var)

        self.media_control_actions = []
        if profile_media_control_actions:
            for action_value in profile_media_control_actions:
                var = ctk.StringVar(value=action_value)
                self.media_control_actions.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="Play/Pause")
                self.media_control_actions.append(var)

        self.media_control_button_modes = []
        if profile_media_control_button_modes:
            for mode_value in profile_media_control_button_modes:
                var = ctk.StringVar(value=mode_value)
                self.media_control_button_modes.append(var)
        else:
            for _ in range(5):
                var = ctk.StringVar(value="Click")
                self.media_control_button_modes.append(var)

        self.settings_manager.settings_vars["mute_settings"] = [mute_state.get() for mute_state in self.mute]
        self.settings_manager.settings_vars["mute_state"] = self.current_mute_state
        self.settings_manager.settings_vars["app_launch_enabled"] = [enabled.get() for enabled in self.app_launch_enabled]
        self.settings_manager.settings_vars["app_launch_paths"] = [path.get() for path in self.app_launch_paths]
        self.settings_manager.settings_vars["keyboard_shortcut_enabled"] = [enabled.get() for enabled in self.keyboard_shortcut_enabled]
        self.settings_manager.settings_vars["keyboard_shortcuts"] = [shortcut.get() for shortcut in self.keyboard_shortcuts]
        self.settings_manager.settings_vars["mute_button_modes"] = [mode.get() for mode in self.mute_button_modes]
        self.settings_manager.settings_vars["app_button_modes"] = [mode.get() for mode in self.app_button_modes]
        self.settings_manager.settings_vars["shortcut_button_modes"] = [mode.get() for mode in self.shortcut_button_modes]
        self.settings_manager.settings_vars["media_control_enabled"] = [enabled.get() for enabled in self.media_control_enabled]
        self.settings_manager.settings_vars["media_control_actions"] = [action.get() for action in self.media_control_actions]
        self.settings_manager.settings_vars["media_control_button_modes"] = [mode.get() for mode in self.media_control_button_modes]
        
        if hasattr(self, 'gui_components') and hasattr(self.gui_components, 'profile_listbox') and self.gui_components.profile_listbox:
            self.gui_components.profile_listbox.set(current_profile)

    def save_settings(self):
        """Save current settings to config file."""
        if self.mute == []:
            self.mute = [
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
            ]
        if self.current_mute_state == []:
            self.current_mute_state = [
                False,
                False,
                False,
                False,
                False,
                False,
                False,
            ]
        
        if self.app_launch_enabled == []:
            self.app_launch_enabled = [
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
            ]
        
        if self.app_launch_paths == []:
            self.app_launch_paths = [
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
            ]
        
        if self.keyboard_shortcut_enabled == []:
            self.keyboard_shortcut_enabled = [
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
            ]
        
        if self.keyboard_shortcuts == []:
            self.keyboard_shortcuts = [
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
                ctk.StringVar(value=""),
            ]
        
        if self.mute_button_modes == []:
            self.mute_button_modes = [
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
            ]
        if self.app_button_modes == []:
            self.app_button_modes = [
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
            ]
        if self.shortcut_button_modes == []:
            self.shortcut_button_modes = [
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
            ]
        
        if self.media_control_enabled == []:
            self.media_control_enabled = [
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
                ctk.BooleanVar(value=False),
            ]
        
        if self.media_control_actions == []:
            self.media_control_actions = [
                ctk.StringVar(value="Play/Pause"),
                ctk.StringVar(value="Play/Pause"),
                ctk.StringVar(value="Play/Pause"),
                ctk.StringVar(value="Play/Pause"),
                ctk.StringVar(value="Play/Pause"),
            ]
        
        if self.media_control_button_modes == []:
            self.media_control_button_modes = [
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
                ctk.StringVar(value="Click"),
            ]

        if hasattr(self, 'gui_components') and hasattr(self.gui_components, 'profile_listbox') and self.gui_components.profile_listbox:
            self.settings_manager.settings_vars["current_profile"] = self.gui_components.profile_listbox.get()
        
        if hasattr(self, 'gui_components') and hasattr(self.gui_components, 'entries'):
            self.settings_manager.settings_vars["applications"] = [entry.get() for entry in self.gui_components.entries]
        
        self.settings_manager.settings_vars["mute_settings"] = [mute_state.get() for mute_state in self.mute]
        self.settings_manager.settings_vars["mute_state"] = self.current_mute_state
        self.settings_manager.settings_vars["app_launch_enabled"] = [enabled.get() for enabled in self.app_launch_enabled]
        self.settings_manager.settings_vars["app_launch_paths"] = [path.get() for path in self.app_launch_paths]
        self.settings_manager.settings_vars["keyboard_shortcut_enabled"] = [enabled.get() for enabled in self.keyboard_shortcut_enabled]
        self.settings_manager.settings_vars["keyboard_shortcuts"] = [shortcut.get() for shortcut in self.keyboard_shortcuts]
        self.settings_manager.settings_vars["mute_button_modes"] = [mode.get() for mode in self.mute_button_modes]
        self.settings_manager.settings_vars["app_button_modes"] = [mode.get() for mode in self.app_button_modes]
        self.settings_manager.settings_vars["shortcut_button_modes"] = [mode.get() for mode in self.shortcut_button_modes]
        self.settings_manager.settings_vars["media_control_enabled"] = [enabled.get() for enabled in self.media_control_enabled]
        self.settings_manager.settings_vars["media_control_actions"] = [action.get() for action in self.media_control_actions]
        self.settings_manager.settings_vars["media_control_button_modes"] = [mode.get() for mode in self.media_control_button_modes]

        current_profile = self.settings_manager.settings_vars.get("current_profile", "Profile 1")
        self.profile_manager.save_current_profile_data(current_profile)
        
        self.settings_manager.save_to_config()

    def show_settings(self):
        """Show settings window."""
        if self.settings_window is not None:
            try:
                if (
                    hasattr(self.settings_window, "window")
                    and self.settings_window.window.winfo_exists()
                ):
                    self.settings_window.window.lift()
                    return
                else:
                    self.settings_window = None
            except Exception:
                self.settings_window = None

        self.settings_window = SettingsWindow(
            self.root,
            ConfigManager,
            self.settings_manager,
            self.on_settings_close,
        )

    def on_settings_close(self):
        """Handle settings window close."""
        if self.settings_window and hasattr(self.settings_window, "window"):
            try:
                self.settings_window.window.destroy()
            except Exception:
                pass
        self.settings_window = None
        self.save_settings()
        
        self.apply_theme_changes()

    def apply_theme_changes(self):
        """Apply theme changes dynamically without restart."""
        try:
            dark_mode = self.settings_manager.get_setting("dark_mode")
            
            if dark_mode:
                ctk.set_appearance_mode("dark")
            else:
                ctk.set_appearance_mode("light")
            
            self.root.update_idletasks()
            
            self.gui_components.update_theme_colors()
            
            print(f"Theme changed to {'dark' if dark_mode else 'light'} mode")
            
        except Exception as e:
            print(f"Error applying theme changes: {e}")

    def on_profile_change(self, profile):
        """Handle profile selection changes."""
        self.profile_manager.on_profile_change(profile)

    def save_applications(self, event=None):
        """Save applications when a key is released in the entry fields."""
        self.profile_manager.save_applications(event) 