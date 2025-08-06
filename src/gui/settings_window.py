import customtkinter as ctk
import gui.app as app
import ctypes
from utils.icon_manager import IconManager


class SettingsWindow:
    def __init__(
        self,
        parent,
        config_manager,
        settings_manager,
        on_close,
    ):
        self.parent = parent
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call("tk", "scaling", 1.0)
        self.window.withdraw()

        self.setup_window()

        self.window.transient(parent)

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)

        self.config_manager = config_manager
        self.settings_manager = settings_manager
        self.on_close = on_close

        self.normal_font_size = 14

        self.setup_gui()
        self.window.after(
            50, lambda: (self.window.deiconify(), self.center_window(parent))
        )

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def setup_window(self):
        """Setup main window properties."""
        self.window.title("Settings")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_release()

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

    def setup_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")

        general_label = ctk.CTkLabel(
            self.frame,
            text="General Settings",
            font=("Segoe UI", 16, "bold")
        )
        general_label.pack(pady=(20, 10), padx=15, anchor="w")

        general_settings = [
            ("Invert Volume Range (100 - 0)", "invert_volumes"),
            ("Enable Auto Startup", "auto_startup"),
            ("Launch in Tray", "launch_in_tray"),
            ("Dark Mode", "dark_mode"),
        ]

        for text, setting_key in general_settings:
            self.create_checkbox(text, setting_key)

        update_label = ctk.CTkLabel(
            self.frame,
            text="Update Settings",
            font=("Segoe UI", 16, "bold")
        )
        update_label.pack(pady=(20, 10), padx=15, anchor="w")

        update_settings = [
            ("Automatically check for updates", "auto_check_updates"),
        ]

        for text, setting_key in update_settings:
            self.create_checkbox(text, setting_key)

        self.create_update_interval_setting()

    def create_checkbox(self, text, setting_key):
        """Create a checkbox for a setting."""
        variable = self.settings_manager.settings_vars.get(setting_key)
        if variable is None:
            print(f"Warning: Setting '{setting_key}' not found in settings manager")
            return
            
        checkbox = ctk.CTkCheckBox(
            self.frame,
            text=text,
            variable=variable,
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
        )
        checkbox.pack(pady=10, padx=15, anchor="w")

    def create_update_interval_setting(self):
        """Create the update interval setting."""
        interval_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        interval_frame.pack(pady=(5, 10), padx=15, fill="x")
        
        interval_label = ctk.CTkLabel(
            interval_frame,
            text="Check for updates every:",
            font=("Segoe UI", self.normal_font_size)
        )
        interval_label.pack(side="left", padx=(0, 10))
        
        current_interval = self.settings_manager.get_setting('update_check_interval', 1800)
        interval_minutes = current_interval // 60
        
        interval_options = ["15 minutes", "30 minutes", "1 hour", "2 hours", "4 hours", "8 hours"]
        
        interval_var = ctk.StringVar()
        if interval_minutes >= 60:
            hours = interval_minutes // 60
            if hours == 1:
                interval_var.set("1 hour")
            else:
                interval_var.set(f"{hours} hours")
        else:
            interval_var.set(f"{interval_minutes} minutes")
        
        interval_menu = ctk.CTkOptionMenu(
            interval_frame,
            values=interval_options,
            variable=interval_var,
            command=self.change_update_interval,
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
        )
        interval_menu.pack(side="left")
        
        self.interval_var = interval_var

    def change_update_interval(self, value):
        """Change the update check interval."""
        try:
            if "hour" in value.lower():
                if value.startswith("1"):
                    minutes = 60
                else:
                    hours = int(value.split()[0])
                    minutes = hours * 60
            else:
                minutes = int(value.split()[0])
            
            seconds = minutes * 60
            self.settings_manager.set_setting('update_check_interval', seconds)
        except ValueError:
            pass



    def center_window(self, parent):
        self.window.update_idletasks()
        parent.update_idletasks()

        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        center_x = parent_x + parent_width // 2
        center_y = parent_y + parent_height // 2

        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()

        x = center_x - window_width // 2
        y = center_y - window_height // 1.8

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def close(self):
        self.window.grab_release()
        self.window.destroy()
        if self.on_close:
            self.on_close()
