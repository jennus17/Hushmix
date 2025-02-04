import customtkinter as ctk
from utils.icon_manager import IconManager
import gui.app as app

class HelpWindow:
    def __init__(self, parent):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call('tk', 'scaling', 1.0)

        self.setup_window()

        self.window.transient(parent)
        self.window.grab_set()

        self.accent_color = app.get_windows_accent_color()
        self.normal_font_size = 14

        self.setup_gui()
        self.center_window(parent)

    def setup_window(self):
        self.window.title("Help")
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

        # Bold label for "Special commands:"
        self.special_commands_label = ctk.CTkLabel(
            self.frame, 
            text="Special commands:", 
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color
        )
        self.special_commands_label.pack(anchor="w", padx=10, pady=5)

        # Create labels for commands with descriptions
        self.commands = [
            ("master", "Controls the speaker volume"),
            ("system", "Controls the system sounds volume"),
            ("mic", "Controls the default microphone"),
            ("current", "Controls the current application in focus")
        ]
        
        for command, description in self.commands:
            command_frame = ctk.CTkFrame(self.frame)
            command_frame.pack(anchor="w", padx=10)

            self.command_label = ctk.CTkLabel(
                command_frame, 
                text=f"• {command}:", 
                text_color=self.accent_color,
                font=("Segoe UI", self.normal_font_size + 2, "bold")
                )
            self.command_label.pack(side="left") 

            self.description_label = ctk.CTkLabel(
                command_frame, 
                text=description,
                font=("Segoe UI", self.normal_font_size)
                )
            self.description_label.pack(side="left", padx=(10, 0))

        self.extra_text_label = ctk.CTkLabel(
            self.frame,
            text="For specific applications, use the full name\n(e.g., chrome.exe, discord.exe, etc.)\n\nYou can also group applications by using a comma\n(e.g.,App 1: chrome.exe, discord.exe, master, etc.)",
            font=("Segoe UI", self.normal_font_size),
            justify="center"
        )
        self.extra_text_label.pack(anchor="center", padx=5, pady=10)

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
