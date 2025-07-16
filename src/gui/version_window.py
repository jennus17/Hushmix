import gui.app as app
from utils.icon_manager import IconManager
import webbrowser
import customtkinter as ctk

class VersionWindow:
    def __init__(self, latest_version, parent):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call('tk', 'scaling', 1.0)
        self.window.withdraw()

        self.setup_window()

        self.window.transient(parent)
        self.window.grab_set()  

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)

        self.normal_font_size = 14

        self.setup_gui(latest_version)
        self.window.after(50, lambda: (self.window.deiconify(), self.center_window(parent)))

        self.window.protocol("WM_DELETE_WINDOW", self.close)


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

    def setup_window(self):
        self.window.title("Update")
        self.window.resizable(False, False)

        ico_path = IconManager.get_ico_file() 
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


        self.update_button = ctk.CTkButton(
            self.frame, 
            text="Update", 
            command=lambda: [webbrowser.open(f"https://github.com/jennus17/Hushmix/releases/download/{latest_version}/Hushmix.exe"),
                              webbrowser.open("https://github.com/jennus17/Hushmix/releases/latest"), self.close()],
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            font=("Segoe UI", self.normal_font_size),
            corner_radius=10
            )
        self.update_button.pack(pady=(5, 10))

    def close(self):
        self.window.destroy()

