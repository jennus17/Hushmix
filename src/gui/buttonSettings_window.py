import customtkinter as ctk
import gui.app as app
import ctypes
from utils.icon_manager import IconManager


class ButtonSettingsWindow:
    def __init__(
        self,
        parent,
        index,
        mute,
        on_close,
        
    ):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call("tk", "scaling", 1.0)
        self.window.withdraw()

        self.setup_window()

        self.window.transient(parent)
        self.window.grab_set()

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)

        self.on_close = on_close
        self.index = index
        self.mute = mute

        self.normal_font_size = 14

        self.setup_gui()
        self.window.after(
            50, lambda: (self.window.deiconify(), self.center_window(parent))
        )

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def setup_window(self):
        """Setup main window properties."""
        self.window.title("Button Settings")
        self.window.resizable(False, False)

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

    def setup_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")

        self.create_checkbox(
            "Mute",
            self.mute[self.index]
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
