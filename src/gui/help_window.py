import customtkinter as ctk
from utils.icon_manager import IconManager

class HelpWindow:
    def __init__(self, parent):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call('tk', 'scaling', 1.0)

        self.setup_window()

        self.window.transient(parent)
        self.window.grab_set()

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

        self.help_label = ctk.CTkLabel(
            self.frame,
            text=self.get_help_text(),
            font=("Segoe UI", 14),
            justify=ctk.LEFT,
        )
        self.help_label.pack(pady=10, padx=10)


    @staticmethod
    def get_help_text():
        """Return help text for the application."""
        return (
            "Special commands:"
            "\n• master - Controls the speaker volume"
            "\n• system - Controls the system sounds volume"
            "\n• mic - Controls the default microphone"
            "\n• current - Controls the current application" 
            "\n\t in focus"
            "\n\n For specific applications, use the full name\n"         
            "       (e.g., chrome.exe, discord.exe, etc.)"
        )

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
