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
from utils.settings_manager import SettingsManager
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
        self.serial_controller = SerialController(self.handle_volume_update, self.handle_button_update)
        self.settings_window = None
        self.buttonSettings_window = None

        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)

        self.settings_manager = SettingsManager(self)

        self.setup_gui()
        self.load_settings()

        self.setup_tray_icon()
        self.setup_window_position_tracking()

        if self.settings_manager.get_setting("launch_in_tray"):
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
        self.volume_labels = []
        self.running = True
        self.button_frame = None
        self.help_button = None
        self.settings_button = None
        self.profile_listbox = None
        self.mute = []
        self.muted_state = []
        self.current_mute_state = []
        self.app_launch_enabled = []
        self.app_launch_paths = []
        self.keyboard_shortcut_enabled = []
        self.keyboard_shortcuts = []

    def setup_gui(self):
        """Setup GUI components."""
        self.main_frame = ctk.CTkFrame(
            self.root,
            corner_radius=0,
            border_width=0,
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.bind("<Button-1>", lambda event: event.widget.focus_force())

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

        threading.Thread(target=self.icon.run_detached, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_window_position_tracking(self):
        """Setup window position tracking to save position when moved."""
        self.last_position = None
        self.root.bind("<Configure>", self.on_window_configure)
        
    def on_window_configure(self, event):
        """Handle window configuration changes (move, resize)."""
        if event.widget == self.root:
            current_position = (self.root.winfo_x(), self.root.winfo_y())
            
            if self.last_position != current_position:
                self.last_position = current_position
                self.save_window_position()
                
    def save_window_position(self):
        """Save current window position to settings."""
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            
            monitors = self.get_monitor_info()
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()
            
            target_monitor = self.find_monitor_for_position(x, y, monitors)
            
            if target_monitor is not None:
                self.settings_manager.set_setting("window_x", x)
                self.settings_manager.set_setting("window_y", y)
                
                self.settings_manager.save_to_config()
            else:
                print("Window position is not on any monitor, not saving position")
                
        except Exception as e:
            print(f"Error saving window position: {e}")
    
    def get_monitor_info(self):
        """Get information about all monitors."""
        import ctypes
        from ctypes.wintypes import RECT
        
        monitors = []
        
        def enum_monitor_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            monitors.append({
                'left': rect.left,
                'top': rect.top,
                'right': rect.right,
                'bottom': rect.bottom,
                'width': rect.right - rect.left,
                'height': rect.bottom - rect.top
            })
            return True
        
        enum_monitor_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_ulong)
        enum_monitor_proc_func = enum_monitor_proc_type(enum_monitor_proc)
        
        try:
            ctypes.windll.user32.EnumDisplayMonitors(None, None, enum_monitor_proc_func, 0)
        except Exception as e:
            print(f"Error enumerating monitors: {e}")
            monitors = [{
                'left': 0,
                'top': 0,
                'right': ctypes.windll.user32.GetSystemMetrics(0),
                'bottom': ctypes.windll.user32.GetSystemMetrics(1),
                'width': ctypes.windll.user32.GetSystemMetrics(0),
                'height': ctypes.windll.user32.GetSystemMetrics(1)
            }]
        
        return monitors
    
    def is_position_on_monitor(self, x, y, monitor):
        """Check if a position is within a specific monitor bounds."""
        return (monitor['left'] <= x <= monitor['right'] and 
                monitor['top'] <= y <= monitor['bottom'])
    
    def find_monitor_for_position(self, x, y, monitors):
        """Find which monitor contains the given position."""
        for monitor in monitors:
            if self.is_position_on_monitor(x, y, monitor):
                return monitor
        return None

    def toggle_mute(self, index):
        """Toggle mute/unmute and apply volume."""
        if index >= len(self.muted_state):
            print(f"Index {index} out of bounds for mute list.")
            return
    
        self.muted_state[index] = not self.muted_state[index]

        if index < len(self.current_mute_state):
            self.current_mute_state[index] = self.muted_state[index]
    
        if self.muted_state[index]:
            self.update_volume(index, 0)
        else:
            pass
        self.save_settings()

    def handle_button_update(self, button_states):
        """Handle button states from serial controller."""
        button_states = [int(state) for state in button_states]
        num_buttons = len(button_states)
        num_apps = len(self.current_apps)
        BUTTON_VOLUME_OFFSET = 1
    
        if not hasattr(self, "last_button_states") or len(self.last_button_states) != num_buttons:
            self.last_button_states = [0] * num_buttons
    
        if not hasattr(self, "mute") or len(self.mute) != num_buttons:
            self.mute = [ctk.BooleanVar(value=True) for _ in range(num_buttons)]
    
        if not hasattr(self, "muted_state") or len(self.muted_state) != num_apps:
            if hasattr(self, "current_mute_state") and len(self.current_mute_state) == num_apps:
                self.muted_state = self.current_mute_state.copy()
            else:
                self.muted_state = [False] * num_apps
    
        for i, (current, previous) in enumerate(zip(button_states, self.last_button_states)):
            if current == 1 and previous == 0:
                volume_index = i + BUTTON_VOLUME_OFFSET
                if i < len(self.mute) and self.mute[i].get() and volume_index < len(self.muted_state):
                    self.toggle_mute(volume_index)
                
                # Launch application if enabled
                if (i < len(self.app_launch_enabled) and 
                    self.app_launch_enabled[i].get() and 
                    i < len(self.app_launch_paths) and 
                    self.app_launch_paths[i].get()):
                    self.launch_application(i)
                
                # Send keyboard shortcut if enabled
                if (i < len(self.keyboard_shortcut_enabled) and 
                    self.keyboard_shortcut_enabled[i].get() and 
                    i < len(self.keyboard_shortcuts) and 
                    self.keyboard_shortcuts[i].get()):
                    self.send_keyboard_shortcut(i)
    
        self.last_button_states = button_states

    def launch_application(self, index):
        """Launch the application specified for the given button index."""
        try:
            import subprocess
            import os
            
            app_path = self.app_launch_paths[index].get()
            if app_path and os.path.exists(app_path):
                subprocess.Popen([app_path], shell=True)
                print(f"Launched application: {app_path}")
            else:
                print(f"Application path not found: {app_path}")
        except Exception as e:
            print(f"Error launching application: {e}")

    def send_keyboard_shortcut(self, index):
        """Send keyboard shortcut for the given button index."""
        try:
            import pyautogui
            import time
            
            if index >= len(self.keyboard_shortcuts):
                return
            
            shortcut = self.keyboard_shortcuts[index].get()
            if not shortcut:
                return
            
            keys = shortcut.split('+')
            key_mapping = {
                'Ctrl': 'ctrl',
                'Control': 'ctrl',
                'Shift': 'shift',
                'Alt': 'alt',
                'Win': 'win',
                'Windows': 'win',
                'Enter': 'enter',
                'Return': 'enter',
                'Tab': 'tab',
                'Space': 'space',
                'Escape': 'esc',
                'Esc': 'esc',
                'Backspace': 'backspace',
                'Delete': 'delete',
                'Del': 'delete',
                'Insert': 'insert',
                'Home': 'home',
                'End': 'end',
                'PageUp': 'pageup',
                'PageDown': 'pagedown',
                'Up': 'up',
                'Down': 'down',
                'Left': 'left',
                'Right': 'right',
                'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4',
                'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8',
                'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12',
                'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g', 'h': 'h', 'i': 'i', 'j': 'j',
                'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n', 'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't',
                'u': 'u', 'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z',
                '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
            }
            
            pyautogui_keys = []
            for key in keys:
                mapped_key = key_mapping.get(key, key.lower())
                pyautogui_keys.append(mapped_key)
            
            if len(pyautogui_keys) > 1:
                pyautogui.hotkey(*pyautogui_keys)
            else:
                pyautogui.press(pyautogui_keys[0])
            
            print(f"Sent keyboard shortcut: {shortcut}")
            
        except Exception as e:
            print(f"Error sending keyboard shortcut: {e}")

    def handle_volume_update(self, volumes):
        """Handle volume updates from serial controller."""
        if self.current_apps == []:
            self.current_apps = ["" for i in range(len(volumes))]
            self.root.after(20, self.refresh_gui)
            return

        if not hasattr(self, "muted_state") or len(self.muted_state) != len(volumes):
            if hasattr(self, "current_mute_state") and len(self.current_mute_state) == len(volumes):
                self.muted_state = self.current_mute_state.copy()
            else:
                self.muted_state = [False] * len(volumes)

        for i, volume in enumerate(volumes):
            self.update_volume(i, int(volume))

    def on_exit(self, icon=None, item=None):
        """Handle application exit."""
        self.save_window_position()
        
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
        self.save_window_position()
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
                placeholder_text=f"App {i + 1}",
                border_width=2,
                corner_radius=10,
            )
            if app_name != "":
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
            volume_label.bind("<Button-1>", lambda event: event.widget.focus_force())
            volume_label.default_text_color = volume_label.cget("text_color")


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

        self.buttonSettings_window = ButtonSettingsWindow(
            self.root,
            button_index,
            self.mute,
            self.app_launch_enabled,
            self.app_launch_paths,
            self.keyboard_shortcut_enabled,
            self.keyboard_shortcuts,
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

        self.settings_manager.settings_vars["mute_settings"] = [mute_state.get() for mute_state in self.mute]
        self.settings_manager.settings_vars["mute_state"] = self.current_mute_state
        self.settings_manager.settings_vars["app_launch_enabled"] = [enabled.get() for enabled in self.app_launch_enabled]
        self.settings_manager.settings_vars["app_launch_paths"] = [path.get() for path in self.app_launch_paths]
        self.settings_manager.settings_vars["keyboard_shortcut_enabled"] = [enabled.get() for enabled in self.keyboard_shortcut_enabled]
        self.settings_manager.settings_vars["keyboard_shortcuts"] = [shortcut.get() for shortcut in self.keyboard_shortcuts]
        if hasattr(self, 'profile_listbox') and self.profile_listbox:
            self.profile_listbox.set(current_profile)

        self.refresh_gui()
        self.save_settings()


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

        if hasattr(self, 'profile_listbox') and self.profile_listbox:
            self.settings_manager.settings_vars["current_profile"] = self.profile_listbox.get()
        
        if hasattr(self, 'entries'):
            self.settings_manager.settings_vars["applications"] = [entry.get() for entry in self.entries]
        
        self.settings_manager.settings_vars["mute_settings"] = [mute_state.get() for mute_state in self.mute]
        self.settings_manager.settings_vars["mute_state"] = self.current_mute_state
        self.settings_manager.settings_vars["app_launch_enabled"] = [enabled.get() for enabled in self.app_launch_enabled]
        self.settings_manager.settings_vars["app_launch_paths"] = [path.get() for path in self.app_launch_paths]
        self.settings_manager.settings_vars["keyboard_shortcut_enabled"] = [enabled.get() for enabled in self.keyboard_shortcut_enabled]
        self.settings_manager.settings_vars["keyboard_shortcuts"] = [shortcut.get() for shortcut in self.keyboard_shortcuts]

        current_profile = self.settings_manager.settings_vars.get("current_profile", "Profile 1")
        self.save_current_profile_data(current_profile)
        
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
            
            self.accent_color = get_windows_accent_color()
            self.accent_hover = darken_color(self.accent_color, 0.2)
            
            if hasattr(self, 'profile_listbox') and self.profile_listbox:
                self.profile_listbox.configure(
                    fg_color=self.accent_color,
                    button_color=self.accent_color,
                    button_hover_color=self.accent_hover,
                    dropdown_hover_color=self.accent_hover
                )
            
            if hasattr(self, 'help_button') and self.help_button:
                self.help_button.configure(
                    fg_color=self.accent_color,
                    hover_color=self.accent_hover
                )
            
            if hasattr(self, 'settings_button') and self.settings_button:
                self.settings_button.configure(
                    fg_color=self.accent_color,
                    hover_color=self.accent_hover
                )
            
            for button in self.buttons:
                if button.winfo_exists():
                    button.configure(
                        fg_color=self.accent_color,
                        hover_color=self.accent_hover
                    )
            
            print(f"Theme changed to {'dark' if dark_mode else 'light'} mode")
            
        except Exception as e:
            print(f"Error applying theme changes: {e}")

    def update_volume(self, index, volume_level):
        """Update volume for a specific application."""
        volume_level = min(max(volume_level, 0), 100)
        volume_level = round(volume_level / 2) * 2

        if self.settings_manager.get_setting("invert_volumes"):
            volume_level = 100 - volume_level

        if index < len(self.muted_state) and self.muted_state[index]:
            volume_level = 0

        if index < len(self.volume_labels):
            is_muted = (
                index < len(self.muted_state) and self.muted_state[index]
            )
            displayed_volume = 0 if is_muted else volume_level
            color = "red3" if is_muted else self.volume_labels[index].default_text_color

            self.root.after(
                10,
                lambda l=self.volume_labels[index]: l.configure(
                    text=f"{displayed_volume}%", text_color=color
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
            current_profile = self.settings_manager.settings_vars.get("current_profile", "Profile 1")
            
            self.save_current_profile_data(current_profile)

            settings = ConfigManager.load_settings()
            
            new_profile_apps = (
                settings.get("profiles", {}).get(profile, {}).get("applications", [])
            )
            new_profile_mute = (
                settings.get("profiles", {}).get(profile, {}).get("mute_settings", [])
            )
            new_profile_mute_state = (
                settings.get("profiles", {}).get(profile, {}).get("mute_state", [])
            )
            new_profile_app_launch_enabled = (
                settings.get("profiles", {}).get(profile, {}).get("app_launch_enabled", [])
            )
            new_profile_app_launch_paths = (
                settings.get("profiles", {}).get(profile, {}).get("app_launch_paths", [])
            )
            new_profile_keyboard_shortcut_enabled = (
                settings.get("profiles", {}).get(profile, {}).get("keyboard_shortcut_enabled", [])
            )
            new_profile_keyboard_shortcuts = (
                settings.get("profiles", {}).get(profile, {}).get("keyboard_shortcuts", [])
            )
            
            self.current_apps = new_profile_apps
            self.settings_manager.settings_vars["applications"] = new_profile_apps
            self.settings_manager.settings_vars["current_profile"] = profile

            self.mute = []
            if new_profile_mute:
                for mute_value in new_profile_mute:
                    var = ctk.BooleanVar(value=mute_value)
                    self.mute.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=True)
                    self.mute.append(var)

            if new_profile_mute_state:
                self.current_mute_state = new_profile_mute_state.copy()
            else:
                self.current_mute_state = [False] * 7
            self.muted_state = self.current_mute_state.copy()
            
            self.app_launch_enabled = []
            if new_profile_app_launch_enabled:
                for enabled_value in new_profile_app_launch_enabled:
                    var = ctk.BooleanVar(value=enabled_value)
                    self.app_launch_enabled.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=False)
                    self.app_launch_enabled.append(var)

            self.app_launch_paths = []
            if new_profile_app_launch_paths:
                for path_value in new_profile_app_launch_paths:
                    var = ctk.StringVar(value=path_value)
                    self.app_launch_paths.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="")
                    self.app_launch_paths.append(var)
            
            self.keyboard_shortcut_enabled = []
            if new_profile_keyboard_shortcut_enabled:
                for enabled_value in new_profile_keyboard_shortcut_enabled:
                    var = ctk.BooleanVar(value=enabled_value)
                    self.keyboard_shortcut_enabled.append(var)
            else:
                for _ in range(5):
                    var = ctk.BooleanVar(value=False)
                    self.keyboard_shortcut_enabled.append(var)

            self.keyboard_shortcuts = []
            if new_profile_keyboard_shortcuts:
                for shortcut_value in new_profile_keyboard_shortcuts:
                    var = ctk.StringVar(value=shortcut_value)
                    self.keyboard_shortcuts.append(var)
            else:
                for _ in range(5):
                    var = ctk.StringVar(value="")
                    self.keyboard_shortcuts.append(var)
            
            self.settings_manager.settings_vars["mute_settings"] = [mute_state.get() for mute_state in self.mute]
            self.settings_manager.settings_vars["mute_state"] = self.current_mute_state
            self.settings_manager.settings_vars["app_launch_enabled"] = [enabled.get() for enabled in self.app_launch_enabled]
            self.settings_manager.settings_vars["app_launch_paths"] = [path.get() for path in self.app_launch_paths]
            self.settings_manager.settings_vars["keyboard_shortcut_enabled"] = [enabled.get() for enabled in self.keyboard_shortcut_enabled]
            self.settings_manager.settings_vars["keyboard_shortcuts"] = [shortcut.get() for shortcut in self.keyboard_shortcuts]

            self.settings_manager.save_to_config()

            self.refresh_gui()

        except Exception as e:
            print(f"Error in profile change: {e}")
            import traceback
            traceback.print_exc()

    def save_current_profile_data(self, profile_name):
        """Save current profile-specific data to the specified profile."""
        try:
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

            current_apps = [entry.get() for entry in self.entries] if hasattr(self, 'entries') else []
            current_mute_settings = [mute_state.get() for mute_state in self.mute]
            current_mute_state = self.current_mute_state
            current_app_launch_enabled = [enabled.get() for enabled in self.app_launch_enabled]
            current_app_launch_paths = [path.get() for path in self.app_launch_paths]
            current_keyboard_shortcut_enabled = [enabled.get() for enabled in self.keyboard_shortcut_enabled]
            current_keyboard_shortcuts = [shortcut.get() for shortcut in self.keyboard_shortcuts]



            settings = ConfigManager.load_settings()
            
            if "profiles" not in settings:
                settings["profiles"] = {}
            if profile_name not in settings["profiles"]:
                settings["profiles"][profile_name] = {}
            
            settings["profiles"][profile_name]["applications"] = current_apps
            settings["profiles"][profile_name]["mute_settings"] = current_mute_settings
            settings["profiles"][profile_name]["mute_state"] = current_mute_state
            settings["profiles"][profile_name]["app_launch_enabled"] = current_app_launch_enabled
            settings["profiles"][profile_name]["app_launch_paths"] = current_app_launch_paths
            settings["profiles"][profile_name]["keyboard_shortcut_enabled"] = current_keyboard_shortcut_enabled
            settings["profiles"][profile_name]["keyboard_shortcuts"] = current_keyboard_shortcuts

            ConfigManager.save_all_settings(settings)

        except Exception as e:
            print(f"Error in save_current_profile_data: {e}")
            import traceback
            traceback.print_exc()

    def save_applications(self, event=None):
        """Save applications when a key is released in the entry fields."""
        try:
            if hasattr(self, 'entries'):
                self.settings_manager.settings_vars["applications"] = [entry.get() for entry in self.entries]
            
            current_profile = self.settings_manager.settings_vars.get("current_profile", "Profile 1")
            self.save_current_profile_data(current_profile)

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

    return "#{:02x}{:02x}{:02x}".format(r, g, b)
