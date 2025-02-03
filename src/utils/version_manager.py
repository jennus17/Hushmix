import os
import requests
import pefile
import sys
import customtkinter as ctk
import webbrowser
import threading
import queue
import time
import gui.app as app
from utils.icon_manager import IconManager
class VersionManager:

    def __init__(self):
        self.popup = None
        self.start_version_check_thread()

    def start_version_check_thread(self):
        """Start serial communication thread."""

        thread = threading.Thread(target=self.check_for_updates, daemon=True)
        thread.start()


    def get_current_version_from_exe(self):
        """Get the current version of the executable from its properties."""
        try:

            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            exe_path = os.path.join(script_dir, "Hushmix.exe")
            pe = pefile.PE(exe_path)
            # Access the version information
            for fileinfo in pe.FileInfo:

                for entry in fileinfo:
                    if entry.Key == b'StringFileInfo':
                        for st in entry.StringTable:
                            if b'ProductVersion' in st.entries:
                                return st.entries[b'ProductVersion'].decode('utf-8')
        except Exception as e:
            print(f"Error reading version from executable: {e}")

            return None

    def check_for_updates(self):
        """Check if a new version is available on GitHub."""

        current_version = self.get_current_version_from_exe()
        if current_version is None:

            return

        new_version = False
        # GitHub API URL for releases
        url = f"https://api.github.com/repos/jennus17/Hushmix/releases/latest"
    
        while not new_version:
            try:
                response = requests.get(url)
                response.raise_for_status()  # Raise an error for bad responses
                latest_release = response.json()
                latest_version = latest_release['tag_name']


                print(f"Current version: {current_version}, Latest version: {latest_version}")
                if current_version != latest_version:
                    new_version = True
                    self.show_update_popup(latest_version)  # Put the latest version in the queue
                time.sleep(600)
            except requests.RequestException as e:
                print(f"Error checking for updates: {e}")

                time.sleep(600)
                

    def show_update_popup(self, latest_version):
        """Show a pop-up window to inform the user about the update."""
        # Create a new window
        self.popup = ctk.CTkToplevel()
        self.popup.title("Update Available")
        self.popup.tk.call('tk', 'scaling', 1.0)
        self.popup.resizable(False, False)

        # Set window icon
        ico_path = IconManager.create_ico_file() 
        if ico_path:
            try:
                self.popup.after(200, lambda: self.popup.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

        normal_font_size = 14

        self.popup.transient()
        self.popup.grab_set()  


        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)


        self.message = f"A new version ({latest_version}) is available!"

        self.frame = ctk.CTkFrame(
            self.popup,
            corner_radius=0,
            border_width=0
        )
        self.frame.pack(expand=True, fill="both")


        self.label = ctk.CTkLabel(
            self.frame, 
            text=self.message,
            font=("Segoe UI", normal_font_size)
            )
        self.label.pack(pady=(20, 10), padx=10)


        self.open_button = ctk.CTkButton(
            self.frame, 
            text="Update", 
            command=lambda: webbrowser.open("https://github.com/jennus17/Hushmix/releases/latest"),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            font=("Segoe UI", normal_font_size)
            )
        self.open_button.pack(pady=(5, 10))




    

