from tkinter import messagebox
import threading
import pythoncom
import ctypes
from pystray import Icon, MenuItem, Menu
import sys
import os
import time
from controllers.audio_controller import AudioController
from controllers.serial_controller import SerialController
from utils.config_manager import ConfigManager
from utils.icon_manager import IconManager
from gui.settings_window import SettingsWindow
from utils.version_manager import VersionManager
from gui.help_window import HelpWindow
from gui.buttonSettings_window import ButtonSettingsWindow
import winreg
from PIL import Image
import customtkinter as ctk


class HushmixApp:
    def __init__(self, root):
        self.root = root

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception as e:
            print(f"Error setting DPI awareness: {e}")

        self.root.tk.call("tk", "scaling", 1.0)

        self.normal_font_size = 16

        self.setup_window()
        self.setup_variables()

        self.audio_controller = AudioController()
        self.serial_controller = SerialController(self.handle_volume_update)
        self.settings_window = None
        self.buttonSettings_window = None

        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)

        self.setup_gui()
        self.load_settings()

        self.setup_tray_icon()

        if self.launch_in_tray.get():
            self.root.withdraw()
        else:
            self.root.deiconify()

        self.version_manager = VersionManager(root)

    def setup_window(self):
        """Setup main window properties."""
        self.root.title("Hushmix")
        self.root.resizable(False, False)

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                myappid = "Hushmix"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                self.root.iconbitmap(default=ico_path)
                self.root.wm_iconbitmap(ico_path)
            except Exception as e:
                print(f"Error setting taskbar icon: {e}")

    def setup_variables(self):
        """Initialize application variables."""
        self.current_apps = []
        self.volumes = []
        self.entries = []
        self.labels = []
        self.buttons = []
        self.help_label = ctk.CTkLabel(None)
        self.previous_volumes = []
        self.invert_volumes = ctk.BooleanVar(value=False)
        self.auto_startup = ctk.BooleanVar(value=False)
        self.dark_mode = ctk.BooleanVar(value=True)
        self.launch_in_tray = ctk.BooleanVar(value=False)
        self.volume_labels = []
        self.running = True
        self.button_frame = None
        self.help_button = None
        self.settings_button = None
        self.profile_listbox = None
        self.mute = [
            ctk.BooleanVar(value=True),
            ctk.BooleanVar(value=True),
            ctk.BooleanVar(value=True),
            ctk.BooleanVar(value=True),
            ctk.BooleanVar(value=True),
        ]

    def setup_gui(self):
        """Setup GUI components."""
        self.main_frame = ctk.CTkFrame(
            self.root,
            corner_radius=0,
            border_width=0,
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        self.profile_listbox = ctk.CTkOptionMenu(
            self.main_frame,
            values=["Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"],
            command=self.on_profile_change,
            font=("Segoe UI", self.normal_font_size, "bold"),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=190,
            height=40,
            corner_radius=10,
        )

        self.help_button = ctk.CTkButton(
            self.main_frame,
            text=" ⓘ ",
            command=lambda: HelpWindow(self.root),
            font=("Segoe UI", self.normal_font_size, "bold"),
            hover_color=self.accent_hover,
            fg_color=self.accent_color,
            cursor="hand2",
            width=30,
            height=40,
            corner_radius=10,
        )

        self.settings_button = ctk.CTkButton(
            self.main_frame,
            text="⚙️",
            command=self.show_settings,
            font=("Segoe UI", self.normal_font_size + 1),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            cursor="hand2",
            width=40,
            height=40,
            corner_radius=10,
        )

        for entry in self.entries:
            entry.configure(width=170, height=30)
            entry.bind("<KeyRelease>", self.save_applications)

        self.refresh_gui()

    def setup_tray_icon(self):
        """Setup system tray icon."""
        menu = Menu(
            MenuItem("Restore", self.restore_window, default=True, visible=False),
            MenuItem("Exit", self.on_exit),
        )

        ico_path = IconManager.get_ico_file()

        try:
            icon_image = Image.open(ico_path)
            self.icon = Icon("Hushmix", icon=icon_image, menu=menu, title="Hushmix")
        except Exception as e:
            print(f"Error setting up tray icon: {e}")

        # Run the icon in a separate thread
        threading.Thread(target=self.icon.run_detached, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def handle_volume_update(self, volumes):
        """Handle volume updates from serial controller."""
        # Update GUI if number of inputs changes
        if self.current_apps == []:
            self.current_apps = [f"App {i + 1}" for i in range(len(volumes))]
            self.root.after(20, self.refresh_gui)
            return

        for i, volume in enumerate(volumes):
            self.update_volume(i, int(volume))

    def on_exit(self, icon=None, item=None):
        """Handle application exit."""
        self.icon.visible = False
        self.icon.stop()

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

    def restore_window(self, icon=None, item=None):
        """Restore window from tray."""
        if not self.root.winfo_viewable():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

    def on_close(self):
        """Handle window close button."""
        self.root.withdraw()

    def refresh_gui(self):
        """Refresh the GUI to match the current applications."""

        for entry in self.entries:
            entry.destroy()
        for buttons in self.buttons:
            buttons.destroy()
        for label in self.volume_labels:
            label.destroy()

        self.buttons.clear()
        self.entries.clear()
        self.volume_labels.clear()

        for i, app_name in enumerate(self.current_apps):

            sliders = len(self.current_apps)

            if i > 0 and i < sliders - 1:
                button = ctk.CTkButton(
                    self.main_frame,
                    text="⋮",
                    command=lambda idx=i: self.show_buttonSettings(idx),
                    hover_color=self.accent_hover,
                    fg_color=self.accent_color,
                    cursor="hand2",
                    width=5,
                    height=25,
                    corner_radius=8,
                )
                button.grid(
                    row=i, column=2, columnspan=1, pady=7, padx=3, sticky="nsew"
                )
                self.buttons.append(button)

            entry = ctk.CTkEntry(
                self.main_frame,
                font=("Segoe UI", self.normal_font_size),
                height=30,
                border_width=2,
                corner_radius=10,
            )
            entry.insert(0, app_name)
            if i == 0:
                entry.grid(
                    row=i,
                    column=0,
                    columnspan=3,
                    pady=(10, 4),
                    padx=(10, 1),
                    sticky="nsew",
                )
            elif i == sliders - 1:
                entry.grid(
                    row=i,
                    column=0,
                    columnspan=3,
                    pady=4,
                    padx=(10, 1),
                    sticky="nsew",
                )
            else:
                entry.grid(
                    row=i, column=0, columnspan=2, pady=4, padx=(10, 1), sticky="nsew"
                )

            entry.bind("<KeyRelease>", lambda e: self.save_applications())

            volume_label = ctk.CTkLabel(
                self.main_frame,
                text="100%",
                width=45,
                font=("Segoe UI", self.normal_font_size, "bold"),
            )
            volume_label.grid(row=i, column=3, pady=6, padx=5, sticky="w")

            self.entries.append(entry)
            self.volume_labels.append(volume_label)

        self.profile_listbox.grid(
            row=len(self.current_apps), column=0, columnspan=1, padx=(10, 0), pady=10
        )
        self.help_button.grid(
            row=len(self.current_apps),
            column=1,
            columnspan=2,
            pady=10,
            padx=5,
            sticky="ew",
        )
        self.settings_button.grid(
            row=len(self.current_apps),
            column=2,
            columnspan=2,
            pady=10,
            padx=(0, 10),
            sticky="e",
        )

        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.columnconfigure(2, weight=0)

        self.previous_volumes = [None] * len(self.current_apps)

        if self.entries:
            entry_names = [entry.get() for entry in self.entries]
            if entry_names != self.current_apps:
                self.load_settings()
                return

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

        self.buttonSettings_window = ButtonSettingsWindow(
            self.root,
            index - 1,
            self.mute,
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
        self.apply_theme()

    def apply_theme(self):
        """Apply the current theme to all widgets."""
        if self.dark_mode.get():
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")

        self.root.update_idletasks()

    def load_settings(self):
        """Load settings from config file."""
        settings = ConfigManager.load_settings()

        current_profile = settings.get("current_profile")

        profile_apps = (
            settings.get("profiles", {})
            .get(current_profile, {})
            .get("applications", [])
        )

        profile_mute = (
            settings.get("profiles", {}).get(current_profile, {}).get("mute", [])
        )

        self.current_apps = profile_apps if profile_apps else []

        self.invert_volumes.set(settings.get("invert_volumes", False))
        self.auto_startup.set(settings.get("auto_startup", False))
        self.dark_mode.set(settings.get("dark_mode", True))
        self.launch_in_tray.set(settings.get("launch_in_tray", False))

        self.profile_listbox.set(current_profile)

        for i, mute_state in enumerate(profile_mute):
            if i < len(self.mute):
                self.mute[i].set(mute_state)

        self.refresh_gui()

    def save_settings(self):
        """Save current settings to config file."""
        if len(self.mute) == 0:
            self.mute = [
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
                ctk.BooleanVar(value=True),
            ]

        settings = {
            "current_profile": self.profile_listbox.get(),
            "applications": [entry.get() for entry in self.entries],
            "invert_volumes": self.invert_volumes.get(),
            "auto_startup": self.auto_startup.get(),
            "dark_mode": self.dark_mode.get(),
            "launch_in_tray": self.launch_in_tray.get(),
            "mute": [mute_state.get() for mute_state in self.mute],
        }
        ConfigManager.toggle_auto_startup(
            self.auto_startup.get(), "Hushmix", sys.executable
        )
        ConfigManager.save_settings(settings)

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
            self.dark_mode,
            self.invert_volumes,
            self.auto_startup,
            self.launch_in_tray,
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
        self.apply_theme()

    def update_volume(self, index, volume_level):
        """Update volume for a specific application."""
        volume_level = min(max(volume_level, 0), 100)
        volume_level = round(volume_level / 2) * 2

        if self.invert_volumes.get():
            volume_level = 100 - volume_level

        if index < len(self.volume_labels):
            self.root.after(
                10,
                lambda l=self.volume_labels[index], v=volume_level: l.configure(
                    text=f"{v}%"
                ),
            )

        if (
            index < len(self.current_apps)
            and volume_level != self.previous_volumes[index]
        ):
            app_name = self.entries[index].get()
            if app_name:
                self.audio_controller.set_application_volume(app_name, volume_level)
                self.previous_volumes[index] = volume_level

    def on_profile_change(self, profile):
        """Handle profile selection changes."""
        try:
            old_profile = self.profile_listbox.get()
            old_apps = [entry.get() for entry in self.entries]
            old_mute = [mute_state.get() for mute_state in self.mute]

            settings = ConfigManager.load_settings()

            settings_to_save = {
                "current_profile": old_profile,
                "applications": old_apps,
                "mute": old_mute,
                "invert_volumes": self.invert_volumes.get(),
                "auto_startup": self.auto_startup.get(),
                "dark_mode": self.dark_mode.get(),
                "launch_in_tray": self.launch_in_tray.get(),
            }
            ConfigManager.save_settings(settings_to_save)

            new_profile_apps = (
                settings.get("profiles", {}).get(profile, {}).get("applications", [])
            )
            new_profile_mute = (
                settings.get("profiles", {}).get(profile, {}).get("mute", [])
            )
            self.current_apps = new_profile_apps

            for i, mute_state in enumerate(new_profile_mute):
                if i < len(self.mute):
                    self.mute[i].set(mute_state)

            settings_to_save = {
                "current_profile": profile,
                "applications": new_profile_apps,
                "mute": new_profile_mute,
                "invert_volumes": self.invert_volumes.get(),
                "auto_startup": self.auto_startup.get(),
                "dark_mode": self.dark_mode.get(),
                "launch_in_tray": self.launch_in_tray.get(),
            }
            ConfigManager.save_settings(settings_to_save)

            self.save_settings()

            self.refresh_gui()

        except Exception as e:
            print(f"Error in profile change: {e}")
            import traceback

            traceback.print_exc()

    def save_applications(self, event=None):
        """Save applications when a key is released in the entry fields."""
        try:
            current_profile = self.profile_listbox.get()
            current_apps = [entry.get() for entry in self.entries]

            settings = {
                "current_profile": current_profile,
                "applications": current_apps,
                "invert_volumes": self.invert_volumes.get(),
                "auto_startup": self.auto_startup.get(),
                "dark_mode": self.dark_mode.get(),
                "launch_in_tray": self.launch_in_tray.get(),
            }

            ConfigManager.save_settings(settings)

        except Exception as e:
            print(f"Error in save_applications: {e}")
            import traceback

            traceback.print_exc()


def get_windows_accent_color():
    """Retrieve the Windows accent color from the registry."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM"
        ) as key:
            accent_color = winreg.QueryValueEx(key, "ColorizationColor")[0]
            blue = accent_color & 0xFF
            green = (accent_color >> 8) & 0xFF
            red = (accent_color >> 16) & 0xFF
            return "#{:02x}{:02x}{:02x}".format(red, green, blue)
    except OSError as e:
        print(f"Error accessing registry: {e}")
    return "#2196F3"


def darken_color(hex_color, percentage):
    """Darken a hex color by a given percentage."""
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    r = int(r * (1 - percentage))
    g = int(g * (1 - percentage))
    b = int(b * (1 - percentage))

    # Convert back to hex
    return "#{:02x}{:02x}{:02x}".format(r, g, b)
