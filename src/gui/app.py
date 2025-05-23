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

        self.root.tk.call('tk', 'scaling', 1.0)

        self.normal_font_size = 16
        
        # Setup window and components
        self.setup_window()
        self.setup_variables()
        
        # Initialize controllers and managers
        self.audio_controller = AudioController()
        self.serial_controller = SerialController(self.handle_volume_update)
        self.settings_window = None
        
        # Set the accent color dynamically
        self.accent_color = get_windows_accent_color()
        
        # Set the accent_hover color to be darker
        self.accent_hover = darken_color(self.accent_color, 0.2)

        self.setup_gui()
        self.load_settings()

        self.setup_tray_icon()

        # Check if the application should launch in the tray
        if self.launch_in_tray.get():
            self.root.withdraw()
        else:
            self.root.deiconify()

        self.version_manager = VersionManager(root)

    def setup_window(self):
        """Setup main window properties."""
        self.root.title("Hushmix")
        self.root.resizable(False, False)
        
        # Set window icon
        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                myappid = 'Hushmix'
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
        self.help_label = ctk.CTkLabel(None)
        self.previous_volumes = []
        self.invert_volumes = ctk.BooleanVar(value=False)
        self.auto_startup = ctk.BooleanVar(value=False)
        self.dark_mode = ctk.BooleanVar(value=True)
        self.launch_in_tray = ctk.BooleanVar(value=False)
        self.volume_labels = []
        self.help_visible = ctk.BooleanVar(value=False)
        self.running = True
        self.button_frame = None
        self.help_button = None
        self.settings_button = None

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
            corner_radius=10
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
            corner_radius=10
        )

        self.settings_button = ctk.CTkButton(
            self.main_frame,
            text="⚙️",
            command=self.show_settings,
            font=("Segoe UI", self.normal_font_size + 1, "bold"),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            cursor="hand2",
            width=30,
            height=40,
            corner_radius=10
        )

        for entry in self.entries:
            entry.configure(width=170, height=30)
            entry.bind("<KeyRelease>", self.save_applications)

        self.refresh_gui()

    def setup_tray_icon(self):
        """Setup system tray icon."""
        menu = Menu(
            MenuItem("Restore", self.restore_window, default=True, visible=False),
            MenuItem("Exit", self.on_exit)
        )
        
        ico_path = IconManager.get_ico_file()

        try:
            icon_image = Image.open(ico_path)
            self.icon = Icon(
                "Hushmix",
                icon=icon_image,
                menu=menu,
                title="Hushmix"
            )
        except Exception as e:
            print(f"Error setting up tray icon: {e}")

        # Run the icon in a separate thread
        threading.Thread(target=self.icon.run_detached, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)     


    def handle_volume_update(self, volumes):
        """Handle volume updates from serial controller."""
        # Update GUI if number of inputs changes
        if len(volumes) != len(self.current_apps):
            self.current_apps = [f"App {i + 1}" for i in range(len(volumes))]
            self.root.after(20, self.refresh_gui)
            return

        # Process each volume value
        for i, volume in enumerate(volumes):
            self.update_volume(i, int(volume))

    def on_exit(self, icon=None, item=None):
        """Handle application exit."""
        self.icon.visible = False
        self.icon.stop()
        
        self.running = False

     # Cleanup controllers
        if hasattr(self, 'serial_controller'):
            try:
                self.serial_controller.cleanup()
            except Exception as e:
                print(f"Error cleaning up serial controller: {e}")

        if hasattr(self, 'audio_controller'):
            try:
                self.audio_controller.cleanup()
            except Exception as e:
                print(f"Error cleaning up audio controller: {e}")

        # Destroy windows
        if hasattr(self, 'settings_window') and self.settings_window:
            try:
                self.settings_window.window.destroy()
            except Exception as e:
                print(f"Error destroying settings window: {e}")

        if hasattr(self, 'root') and self.root:
            try:
                self.root.quit()
            except Exception as e:
                print(f"Error quitting root: {e}")

        # Force exit the application
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

        # Clear existing widgets
        for label in self.labels:
            label.destroy()
        for entry in self.entries:
            entry.destroy()
        for label in self.volume_labels:
            label.destroy()

        self.labels.clear()
        self.entries.clear()
        self.volume_labels.clear()

        # Create new widgets for each application
        for i, app_name in enumerate(self.current_apps):
            # Application label
            label = ctk.CTkLabel(
                self.main_frame,
                text=f"App {i+1}:",
                font=("Segoe UI", self.normal_font_size, "bold")
            )
            label.grid(row=i, column=0, sticky="nsew", pady=6, padx=(10, 0))

            entry = ctk.CTkEntry(
                self.main_frame,
                font=("Segoe UI", self.normal_font_size),
                width=190,
                height=30,
                border_width=2,
                corner_radius=10
            )
            entry.insert(0, app_name)
            entry.grid(row=i, column=1, pady=6, padx=10, sticky="w")
            
            # Bind to any changes in the entry
            entry.bind('<KeyRelease>', lambda e: self.save_applications())

            volume_label = ctk.CTkLabel(
                self.main_frame,
                text="100%",
                font=("Segoe UI", self.normal_font_size, "bold")
            )
            volume_label.grid(row=i, column=2, pady=6, padx=(0, 10), sticky="nsew")
            
            self.labels.append(label)
            self.entries.append(entry)
            self.volume_labels.append(volume_label)
        

        self.profile_listbox.grid(row=len(self.current_apps), column=1, columnspan=1, pady=10)
        self.help_button.grid(row=len(self.current_apps), column=0, padx=(10, 0), sticky="e")
        self.settings_button.grid(row=len(self.current_apps), column=2, padx=(0, 10), sticky="w")

        if self.help_visible.get():
            self.help_label.grid(row=len(self.current_apps) + 2, column=0, columnspan=3, pady=0)
        else:
            self.help_label.grid_remove()

        # Configure grid columns
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.columnconfigure(2, weight=0)

        self.previous_volumes = [None] * len(self.current_apps)

        if self.entries:
            entry_names = [entry.get() for entry in self.entries]
            if entry_names != self.current_apps:
                self.load_settings()
                return

    def apply_theme(self):
        """Apply the current theme to all widgets."""
        if self.dark_mode.get():
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")
        
        # Force update
        self.root.update_idletasks()

    def load_settings(self):
        """Load settings from config file."""
        settings = ConfigManager.load_settings()
        
        # Get the last used profile
        current_profile = settings.get("current_profile")
        
        # Get the applications for the last used profile
        profile_apps = settings.get("profiles", {}).get(current_profile, {}).get("applications", [])
        self.current_apps = profile_apps if profile_apps else []
        
        # Load other settings
        self.invert_volumes.set(settings.get("invert_volumes", False))
        self.auto_startup.set(settings.get("auto_startup", False))
        self.dark_mode.set(settings.get("dark_mode", True))
        self.launch_in_tray.set(settings.get("launch_in_tray", False))
        
        # Set the correct profile in the dropdown
        self.profile_listbox.set(current_profile)
        
        self.refresh_gui()
        
        print(f"Loaded settings for profile {current_profile}")
        print(f"Loaded applications: {self.current_apps}")

    def save_settings(self):
        """Save current settings to config file."""
        settings = {
            "current_profile": self.profile_listbox.get(),
            "applications": [entry.get() for entry in self.entries],
            "invert_volumes": self.invert_volumes.get(),
            "auto_startup": self.auto_startup.get(),
            "dark_mode": self.dark_mode.get(),
            "launch_in_tray": self.launch_in_tray.get()
        }      
        ConfigManager.toggle_auto_startup(self.auto_startup.get(), "Hushmix", sys.executable)  
        ConfigManager.save_settings(settings)
        print("Settings saved:", settings)

    def show_settings(self):
        """Show settings window."""
        # If settings window exists but is invalid, clean it up first
        if self.settings_window is not None:
            try:
                if hasattr(self.settings_window, 'window') and self.settings_window.window.winfo_exists():
                    self.settings_window.window.lift()
                    return
                else:
                    self.settings_window = None
            except Exception:
                self.settings_window = None
        
        # Create new settings window
        self.settings_window = SettingsWindow(
            self.root,
            ConfigManager,
            self.dark_mode,
            self.invert_volumes,
            self.auto_startup,
            self.launch_in_tray,
            self.on_settings_close
            
        )

    def on_settings_close(self):
        """Handle settings window close."""
        if self.settings_window and hasattr(self.settings_window, 'window'):
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

        # Update volume label
        if index < len(self.volume_labels):
            self.root.after(20, lambda l=self.volume_labels[index], v=volume_level: 
                          l.configure(text=f"{v}%"))

        if index < len(self.current_apps) and volume_level != self.previous_volumes[index]:
            app_name = self.entries[index].get()
            if app_name:
                self.audio_controller.set_application_volume(app_name, volume_level)
                self.previous_volumes[index] = volume_level

    def on_profile_change(self, profile):
        """Handle profile selection changes."""
        try:
            old_profile = self.profile_listbox.get()
            old_apps = [entry.get() for entry in self.entries]
            
            settings = ConfigManager.load_settings()
            
            settings_to_save = {
                "current_profile": old_profile,
                "applications": old_apps,
                "invert_volumes": self.invert_volumes.get(),
                "auto_startup": self.auto_startup.get(),
                "dark_mode": self.dark_mode.get(),
                "launch_in_tray": self.launch_in_tray.get()
            }
            ConfigManager.save_settings(settings_to_save)
            
            new_profile_apps = settings.get("profiles", {}).get(profile, {}).get("applications", [])
            self.current_apps = new_profile_apps
        
            self.refresh_gui()
            
            settings_to_save = {
                "current_profile": profile,
                "applications": new_profile_apps,
                "invert_volumes": self.invert_volumes.get(),
                "auto_startup": self.auto_startup.get(),
                "dark_mode": self.dark_mode.get(),
                "launch_in_tray": self.launch_in_tray.get()
            }
            ConfigManager.save_settings(settings_to_save)
            
            print(f"Switched from {old_profile} to {profile}")
            print(f"Old apps: {old_apps}")
            print(f"New apps: {new_profile_apps}")
            
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
                "launch_in_tray": self.launch_in_tray.get()
            }
            
            print(f"Attempting to save apps for {current_profile}: {current_apps}")
            ConfigManager.save_settings(settings)
            
        except Exception as e:
            print(f"Error in save_applications: {e}")
            import traceback
            traceback.print_exc()

def get_windows_accent_color():
    """Retrieve the Windows accent color from the registry."""
    try:
        # Check the DWM registry key for ColorizationColor
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            accent_color = winreg.QueryValueEx(key, "ColorizationColor")[0]
            # Extract RGB values from ARGB
            blue = accent_color & 0xFF
            green = (accent_color >> 8) & 0xFF
            red = (accent_color >> 16) & 0xFF
            # Return the color in hex format
            return "#{:02x}{:02x}{:02x}".format(red, green, blue)
    except OSError as e:
        print(f"Error accessing registry: {e}")
    # Fallback to a default color if any error occurs
    return "#2196F3"  # Default color

def darken_color(hex_color, percentage):
    """Darken a hex color by a given percentage."""
    # Convert hex to RGB
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    
    # Calculate the darkened color
    r = int(r * (1 - percentage))
    g = int(g * (1 - percentage))
    b = int(b * (1 - percentage))
    
    # Convert back to hex
    return "#{:02x}{:02x}{:02x}".format(r, g, b)