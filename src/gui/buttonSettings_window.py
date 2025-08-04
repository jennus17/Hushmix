import customtkinter as ctk
import gui.app as app
import ctypes
import tkinter as tk
from tkinter import filedialog
from utils.icon_manager import IconManager


class ButtonSettingsWindow:
    def __init__(
        self,
        parent,
        index,
        mute,
        app_launch_enabled,
        app_launch_paths,
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
        self.app_launch_enabled = app_launch_enabled
        self.app_launch_paths = app_launch_paths

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
        self.window.geometry("350x300")

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

    def setup_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")

        if self.index >= len(self.mute):
            while len(self.mute) <= self.index:
                self.mute.append(ctk.BooleanVar(value=True))
        if self.index >= len(self.app_launch_enabled):
            while len(self.app_launch_enabled) <= self.index:
                self.app_launch_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.app_launch_paths):
            while len(self.app_launch_paths) <= self.index:
                self.app_launch_paths.append(ctk.StringVar(value=""))

        self.create_checkbox(
            "Mute",
            self.mute[self.index]
        )

        self.create_app_launch_section()

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

    def create_app_launch_section(self):
        """Create the app launch section with checkbox and file browser."""
        app_frame = ctk.CTkFrame(self.frame, corner_radius=0, border_width=0)
        app_frame.pack(pady=0, padx=0, fill="x")

        self.app_launch_checkbox = ctk.CTkCheckBox(
            app_frame,
            text="Launch Application",
            variable=self.app_launch_enabled[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.on_app_launch_toggle
        )
        self.app_launch_checkbox.pack(pady=(10, 5), padx=15, anchor="w")

        self.file_frame = ctk.CTkFrame(app_frame, corner_radius=10, border_width=0)
        self.file_frame.pack(pady=(0, 10), padx=15, fill="x")

        self.path_label = ctk.CTkLabel(
            self.file_frame,
            text="No application selected",
            font=("Segoe UI", 12),
        )
        self.path_label.pack(pady=(5, 5), padx=15, anchor="w")

        self.browse_button = ctk.CTkButton(
            self.file_frame,
            text="Browse",
            font=("Segoe UI", 12),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.browse_file,
            width=80,
            height=30
        )
        self.browse_button.pack(pady=(0, 5), padx=15, anchor="w")

        self.update_app_launch_ui()

    def on_app_launch_toggle(self):
        """Handle app launch checkbox toggle."""
        self.update_app_launch_ui()

    def update_app_launch_ui(self):
        """Update the UI based on the app launch checkbox state."""
        if self.index >= len(self.app_launch_enabled):
            while len(self.app_launch_enabled) <= self.index:
                self.app_launch_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.app_launch_paths):
            while len(self.app_launch_paths) <= self.index:
                self.app_launch_paths.append(ctk.StringVar(value=""))
        
        is_enabled = self.app_launch_enabled[self.index].get()
        
        if is_enabled:
            self.file_frame.pack(pady=(0, 10), padx=15, fill="x")
            self.browse_button.configure(state="normal")
            
            current_path = self.app_launch_paths[self.index].get()
            if current_path:
                import os
                filename = os.path.basename(current_path)
                self.path_label.configure(text=filename)
            else:
                self.path_label.configure(text="No application selected")
        else:
            self.file_frame.pack_forget()
            self.browse_button.configure(state="disabled")

    def browse_file(self):
        """Open file dialog to select an application."""
        if self.index >= len(self.app_launch_paths):
            while len(self.app_launch_paths) <= self.index:
                self.app_launch_paths.append(ctk.StringVar(value=""))
        
        file_path = filedialog.askopenfilename(
            title="Select Application",
            filetypes=[
                ("Executable files", "*.exe"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.app_launch_paths[self.index].set(file_path)
            self.update_app_launch_ui()

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
