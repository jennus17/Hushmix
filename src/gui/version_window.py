import gui.app as app
from utils.icon_manager import IconManager
import webbrowser
import customtkinter as ctk


class VersionWindow:
    def __init__(self, latest_version, parent, update_info=None, version_manager=None):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call("tk", "scaling", 1.0)
        self.window.withdraw()

        self.parent = parent
        self.latest_version = latest_version
        self.update_info = update_info or {}
        self.version_manager = version_manager

        self.setup_window()

        self.window.transient(parent)
        self.window.grab_set()

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)

        self.normal_font_size = 14

        self.setup_gui(latest_version)
        self.window.after(
            50, lambda: (self.window.deiconify(), self.center_window(parent))
        )

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

        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")

        self.label = ctk.CTkLabel(
            self.frame, text=self.message, font=("Segoe UI", self.normal_font_size)
        )
        self.label.pack(pady=(20, 10), padx=10)

        self.view_release_button = ctk.CTkButton(
            self.frame,
            text="View Release",
            command=self.view_release,
            fg_color="transparent",
            hover_color="#333333",
            font=("Segoe UI", 12),
            corner_radius=10,
        )
        self.view_release_button.pack(pady=(0, 10), padx=10)

        self.button_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.button_frame.pack(pady=(5, 10))

        if self.version_manager:
            self.auto_update_button = ctk.CTkButton(
                self.button_frame,
                text="Auto Update",
                command=self.auto_update,
                fg_color=self.accent_color,
                hover_color=self.accent_hover,
                font=("Segoe UI", self.normal_font_size),
                corner_radius=10,
            )
            self.auto_update_button.pack(side="left", padx=(0, 5))

        self.manual_update_button = ctk.CTkButton(
            self.button_frame,
            text="Manual Download",
            command=self.manual_download,
            fg_color="gray",
            hover_color="#555555",
            font=("Segoe UI", self.normal_font_size),
            corner_radius=10,
        )
        self.manual_update_button.pack(side="left", padx=(5, 0))

        self.remind_button = ctk.CTkButton(
            self.frame,
            text="Remind Later",
            command=self.close,
            fg_color="transparent",
            hover_color="#333333",
            font=("Segoe UI", 12),
            corner_radius=10,
        )
        self.remind_button.pack(pady=(10, 5))

    def auto_update(self):
        """Start automatic update process."""
        self.close()
        from gui.update_progress_window import UpdateProgressWindow
        UpdateProgressWindow(self.parent, self.update_info, self.version_manager)

    def view_release(self):
        """Open the GitHub release page."""
        release_page = self.update_info.get('release_page', "https://github.com/jennus17/Hushmix/releases/latest")
        webbrowser.open(release_page)

    def manual_download(self):
        """Open manual download links."""
        download_url = self.update_info.get('download_url', f"https://github.com/jennus17/Hushmix/releases/download/{self.latest_version}/Hushmix.exe")
        release_page = self.update_info.get('release_page', "https://github.com/jennus17/Hushmix/releases/latest")
        
        webbrowser.open(download_url)
        webbrowser.open(release_page)
        self.close()

    def close(self):
        self.window.destroy()
