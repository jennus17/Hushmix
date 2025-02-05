import customtkinter as ctk
import gui.app as app
import ctypes
from utils.icon_manager import IconManager


class SettingsWindow:
    def __init__(self, parent, config_manager, dark_mode, invert_volumes, auto_startup, launch_in_tray, on_close):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call('tk', 'scaling', 1.0)

        self.setup_window()
        
        self.window.transient(parent)
        self.window.grab_set()

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)
        
        # Store references
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self.invert_volumes = invert_volumes
        self.auto_startup = auto_startup
        self.launch_in_tray = launch_in_tray
        self.on_close = on_close
        

        self.normal_font_size = 14
        
        self.setup_gui()
        self.center_window(parent)

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def setup_window(self):
        """Setup main window properties."""
        self.window.title("Settings")
        self.window.resizable(False, False)
        
        # Set window icon
        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

    def setup_gui(self):  
        self.frame = ctk.CTkFrame(
            self.window,
            corner_radius=0,
            border_width=0
        )
        self.frame.pack(expand=True, fill="both")
        
        self.create_checkbox(
            "Invert Volume Range (100 - 0)",
            self.invert_volumes,
        )
        
        self.create_checkbox(
            "Enable Auto Startup",
            self.auto_startup,
        )

        self.create_checkbox(
            "Launch in Tray",
            self.launch_in_tray,
        )
        
        self.create_checkbox(
            "Dark Mode",
            self.dark_mode,
        )

    def create_checkbox(self, text, variable):
        checkbox = ctk.CTkCheckBox(
            self.frame,
            text=text,
            variable=variable,
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
        )
        checkbox.pack(pady=10, padx=15, anchor="w")

    def center_window(self, parent):
        self.window.update_idletasks()
        
        # Get parent window position and size
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        # Get this window's size
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        # Calculate position
        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2
        
        self.window.geometry(f"+{x}+{y}")

    def close(self):
        self.window.grab_release()
        self.window.destroy()
        if self.on_close:
            self.on_close()
