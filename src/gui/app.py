import tkinter as tk
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
from gui.themes import THEMES
from gui.settings_window import SettingsWindow
import winreg
from PIL import Image

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

class HushmixApp:
    def __init__(self, root):
        self.root = root
        self.dark_mode = tk.BooleanVar(value=False)
        
        # Add dark mode trace
        self.dark_mode.trace_add("write", self.on_theme_change)
        
        # Initialize screen scaling
        self.setup_scaling()
        
        # Setup window and components
        self.setup_window()
        self.setup_variables()
        
        # Initialize controllers and managers
        self.audio_controller = AudioController()
        self.serial_controller = SerialController(self.handle_volume_update)
        self.settings_window = None
        
        # Set the accent color dynamically
        accent_color = get_windows_accent_color()
        THEMES["light"]["accent"] = accent_color
        THEMES["dark"]["accent"] = accent_color
        
        # Set the accent_hover color to be darker
        THEMES["light"]["accent_hover"] = darken_color(accent_color, 0.2)
        THEMES["dark"]["accent_hover"] = darken_color(accent_color, 0.2)
        
        self.setup_gui()
        self.load_settings()
        self.setup_tray_icon()

        # Check if the application should launch in the tray
        if self.launch_in_tray.get():
            self.root.withdraw()
            self.icon.visible = True
        else:
            self.root.deiconify()

    def setup_scaling(self):
        """Initialize screen scaling parameters."""
        self.normal_font_size = 10
        self.frame_padding = 20
        self.entry_width = 25

    def setup_window(self):
        """Setup main window properties."""
        self.root.title("Hushmix")
        self.root.resizable(False, False)
        
        # Set window icon
        ico_path = IconManager.create_ico_file()
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
        self.help_label = tk.Label()
        self.previous_volumes = []
        self.invert_volumes = tk.BooleanVar(value=False)
        self.auto_startup = tk.BooleanVar(value=False)
        self.volume_labels = []
        self.help_visible = tk.BooleanVar(value=False)
        self.running = True
        self.button_frame = None
        self.help_button = None
        self.settings_button = None

    def setup_gui(self):
        """Setup GUI components."""
        theme = THEMES["dark" if self.dark_mode.get() else "light"]
        
        self.main_frame = tk.Frame(
            self.root,
            bg=theme["bg"],
            padx=5,
            pady=10
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        self.set_button = tk.Button(
            self.main_frame,
            text="Set Applications",
            command=self.set_applications,
            font=("Segoe UI", self.normal_font_size + 2),
            bg=theme["accent"],
            fg="white",
            activebackground=theme["accent_hover"],
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
            padx=31,
            pady=5
        )

        self.help_button = tk.Button(
            self.main_frame,
            text="ⓘ ▼" if not self.help_visible.get() else "ⓘ ▲",
            command=self.toggle_help,
            font=("Segoe UI", self.normal_font_size),
            bg=theme["button_bg"],
            fg=theme["fg"],
            activebackground=theme["accent"],
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8
        )

        self.help_label = tk.Label(
            self.main_frame,
            text=self.get_help_text(),
            font=("Segoe UI", self.normal_font_size),
            bg=theme["button_bg"],
            fg=theme["fg"],
            justify=tk.LEFT
        )

        self.settings_button = tk.Button(
            self.main_frame,
            text="⚙️",
            command=self.show_settings,
            font=("Segoe UI", self.normal_font_size),
            bg=theme["button_bg"],
            fg=theme["fg"],
            activebackground=theme["accent"],
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8
        )

        for entry in self.entries:
            entry.config(width=30, height=1)

        self.refresh_gui()

    def setup_tray_icon(self):
        """Setup system tray icon."""
        menu = Menu(
            MenuItem("Restore", self.restore_window, default=True, visible=False),
            MenuItem("Exit", self.on_exit)
        )
        
        icon_image = IconManager.create_tray_icon()
        if icon_image is None:
            raise ValueError("Failed to create tray icon image.")

        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Attempt to load the image to check for integrity
                icon_image.load() 
                
                self.icon = Icon(
                    "Hushmix",
                    icon=icon_image,
                    menu=menu,
                    title="Hushmix"
                )
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(0.1)  # Wait before retrying

        # Run the icon in a separate thread
        threading.Thread(target=self.icon.run_detached, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
                
        if not self.launch_in_tray.get():
            self.root.after(50, self.hide_tray_icon)        

    def hide_tray_icon(self):
        """Hide the tray icon."""
        time.sleep(0.01)
        if self.icon.visible is True:
            self.icon.visible = False
        else:
            self.hide_tray_icon()

    def handle_volume_update(self, volumes):
        """Handle volume updates from serial controller."""
        # Update GUI if number of inputs changes
        if len(volumes) != len(self.current_apps):
            self.current_apps = [f"App {i + 1}" for i in range(len(volumes))]
            self.root.after(0, self.refresh_gui)
            return

        # Process each volume value
        for i, volume in enumerate(volumes):
            self.update_volume(i, int(volume))

    def on_exit(self, icon=None, item=None):
        """Handle application exit."""
        if hasattr(self, 'icon') and self.icon:
            self.icon.visible = False
            self.icon.stop()
        
        self.running = False
        
        try:
            self.save_settings()
        except Exception as e:
            print(f"Error saving settings during exit: {e}")

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
            self.icon.visible = False

    def on_close(self):
        """Handle window close button."""
        self.root.withdraw()
        if hasattr(self, 'icon'):
            self.icon.visible = True

    @staticmethod
    def get_help_text():
        """Return help text for the application."""
        return (
            "Special commands:\n"
            "• current - Controls the current application in focus\n"
            "• master - Controls the default speaker volume\n"
            "• mic - Controls the default microphone\n"
            "\n    For specific applications, use the full name\n         (e.g., chrome.exe, discord.exe, etc.)"
        )

    def refresh_gui(self):  
        """Refresh the GUI to match the current applications."""
        theme = THEMES["dark" if self.dark_mode.get() else "light"]

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
            label = tk.Label(
                self.main_frame,
                text=f"App {i+1}:",
                font=("Segoe UI", self.normal_font_size, "bold"),
                bg=theme["bg"],
                fg=theme["fg"]
            )
            label.grid(row=i, column=0, sticky="e", pady=6, padx=6)

            entry = tk.Entry(
                self.main_frame,
                width=self.entry_width,
                font=("Segoe UI", self.normal_font_size),
                relief="solid",
                bd=1,
                bg=theme["entry_bg"],
                fg=theme["fg"],
                insertbackground=theme["fg"],
                highlightthickness=1,
                highlightcolor=theme["accent"]
            )
            entry.insert(0, app_name)
            entry.grid(row=i, column=1, pady=6, padx=10, sticky="w")
            
            volume_label = tk.Label(
                self.main_frame,
                text="0%",
                font=("Segoe UI", self.normal_font_size, "bold"),
                bg=theme["bg"],
                fg=theme["fg"],
                width=4
            )
            volume_label.grid(row=i, column=2, pady=6, padx=5, sticky="w")
            
            self.labels.append(label)
            self.entries.append(entry)
            self.volume_labels.append(volume_label)

        self.help_button.grid(row=len(self.current_apps), column=0, padx=5, sticky="e")
        self.set_button.grid(row=len(self.current_apps), column=1, columnspan=1, pady=10)
        self.settings_button.grid(row=len(self.current_apps), column=2, padx=5, sticky="w")

        if self.help_visible.get():
            self.help_label.grid(row=len(self.current_apps) + 2, column=0, columnspan=3, pady=15)
        else:
            self.help_label.grid_remove()

        # Configure grid columns
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.columnconfigure(2, weight=0)

        self.previous_volumes = [None] * len(self.current_apps)

    def apply_theme(self):
        """Apply the current theme to all widgets."""
        theme = THEMES["dark" if self.dark_mode.get() else "light"]
        
        # Update main window and frame
        self.root.configure(bg=theme["bg"])
        self.main_frame.configure(bg=theme["bg"])
        
        # Update button frame
        if self.button_frame:
            self.button_frame.configure(bg=theme["bg"])
        
        self.update_title_bar_color()
        
        # Update all widgets with new theme
        for label in self.labels:
            label.configure(bg=theme["bg"], fg=theme["fg"])
        
        for entry in self.entries:
            entry.configure(
                bg=theme["entry_bg"],
                fg=theme["fg"],
                insertbackground=theme["fg"]
            )
        
        for label in self.volume_labels:
            label.configure(bg=theme["bg"], fg=theme["fg"])
        
        self.set_button.configure(
            bg=theme["accent"],
            fg="white",
            activebackground=theme["accent_hover"],
            activeforeground="white"
        )
        
        if self.help_button:
            self.help_button.configure(
                bg=theme["button_bg"],
                fg=theme["fg"],
                activebackground=theme["accent"],
                activeforeground="white"
            )
            
        if self.settings_button:
            self.settings_button.configure(
                bg=theme["button_bg"],
                fg=theme["fg"],
                activebackground=theme["accent"],
                activeforeground="white"
            )
            
        if hasattr(self, 'help_label'):
            self.help_label.configure(bg=theme["bg"], fg=theme["fg"])
        
        # Force update
        self.root.update_idletasks()

    def update_title_bar_color(self):
        """Update the Windows title bar color."""
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ctypes.windll.user32.GetParent
            hwnd = get_parent(self.root.winfo_id())
            rendering_policy = ctypes.c_int(2 if self.dark_mode.get() else 0)
            set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                               ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            
            # Force immediate redraw of the title bar
            self.root.update_idletasks()
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0004 | 0x0400  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )
        except Exception as e:
            print(f"Error setting title bar theme: {e}")

    def toggle_help(self):
        """Toggle help text visibility."""
        self.help_visible.set(not self.help_visible.get())
        if self.help_visible.get():
            self.help_label.grid(row=len(self.current_apps) + 2, column=0, columnspan=3, pady=15)
            self.help_button.config(text="ⓘ ▲")
        else:
            self.help_label.grid_remove()
            self.help_button.config(text="ⓘ ▼")

    def on_theme_change(self, *args):
        """Handle theme changes."""
        self.apply_theme()
        # Update settings window if it exists and is valid
        if self.settings_window and hasattr(self.settings_window, 'window') and self.settings_window.window.winfo_exists():
            self.settings_window.update_theme()

    def set_applications(self):
        """Update application names from entry fields."""
        self.current_apps = [entry.get() for entry in self.entries]
        self.save_settings()

    def load_settings(self):
        """Load settings from config file."""
        settings = ConfigManager.load_settings()
        
        self.current_apps = settings.get("applications", ["App 1"])
        if not self.current_apps:
            self.current_apps = ["App 1"]
            
        # Load other settings with defaults
        self.invert_volumes.set(settings.get("invert_volumes", False))
        self.auto_startup.set(settings.get("auto_startup", False))
        self.dark_mode.set(settings.get("dark_mode", False))
        self.launch_in_tray = tk.BooleanVar(value=settings.get("launch_in_tray", False))
        
        self.apply_theme()
        self.refresh_gui()
        
        print("Settings loaded:", settings)

    def save_settings(self):
        """Save current settings to config file."""
        settings = {
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
            self.root.after(0, lambda l=self.volume_labels[index], v=volume_level: 
                          l.config(text=f"{v}%"))

        if index < len(self.current_apps) and volume_level != self.previous_volumes[index]:
            app_name = self.entries[index].get()
            if app_name:
                self.audio_controller.set_application_volume(app_name, volume_level)
                self.previous_volumes[index] = volume_level