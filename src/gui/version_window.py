import gui.app as app
from utils.icon_manager import IconManager
import webbrowser
import customtkinter as ctk

class VersionWindow:
    def __init__(self, latest_version, parent):
        self.setup_window(parent)

        self.window.transient()
        self.window.grab_set()  

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)

        self.normal_font_size = 14

        self.setup_gui(latest_version)
        self.center_window(parent)


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

    def setup_window(self, parent):
        """Show a pop-up window to inform the user about the update."""
        # Create a new window
        self.window = ctk.CTkToplevel(parent)
        self.window.title("Update")
        self.window.tk.call('tk', 'scaling', 1.0)
        self.window.resizable(False, False)

        # Set window icon
        ico_path = IconManager.create_ico_file() 
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")


    def setup_gui(self, latest_version):
        self.message = f"A new version ({latest_version}) is available!"

        self.frame = ctk.CTkFrame(
            self.window,
            corner_radius=0,
            border_width=0
        )
        self.frame.pack(expand=True, fill="both")


        self.label = ctk.CTkLabel(
            self.frame, 
            text=self.message,
            font=("Segoe UI", self.normal_font_size)
            )
        self.label.pack(pady=(20, 10), padx=10)


        self.open_button = ctk.CTkButton(
            self.frame, 
            text="Update", 
            command=lambda: webbrowser.open("https://github.com/jennus17/Hushmix/releases/latest"),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            font=("Segoe UI", self.normal_font_size)
            )
        self.open_button.pack(pady=(5, 10))