import os
import requests
import pefile
import sys
import threading
import time
from gui.version_window import VersionWindow


class VersionManager:
    def __init__(self, parent):
        self.root = parent
        self.start_version_check_thread(parent)

    def start_version_check_thread(self, parent):
        """Start serial communication thread."""

        thread = threading.Thread(
            target=self.check_for_updates, args=(parent,), daemon=True
        )
        thread.start()

    def get_current_version_from_exe(self):
        """Get the current version of the executable from its properties."""
        try:
            if getattr(sys, "frozen", False):
                self.exe_path = os.path.join(
                    os.path.dirname(sys.executable), "Hushmix.exe"
                )
            else:
                self.script_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                self.exe_path = os.path.join(self.script_dir, "Hushmix.exe")

            self.pe = pefile.PE(self.exe_path)

            for fileinfo in self.pe.FileInfo:

                for entry in fileinfo:
                    if entry.Key == b"StringFileInfo":
                        for st in entry.StringTable:
                            if b"ProductVersion" in st.entries:
                                product_version = st.entries[b"ProductVersion"].decode(
                                    "utf-8"
                                )
                                return "v" + product_version
        except Exception as e:
            print(f"Error reading version from executable: {e}")

            return None

    def check_for_updates(self, parent):
        """Check if a new version is available on GitHub."""

        current_version = self.get_current_version_from_exe()
        if current_version is None:
            return

        new_version = False
        url = f"https://api.github.com/repos/jennus17/Hushmix/releases/latest"

        while new_version is False:
            try:
                response = requests.get(url)
                response.raise_for_status()
                latest_release = response.json()
                latest_version = latest_release["tag_name"]

                print(
                    f"Current version: {current_version}, Latest version: {latest_version}"
                )
                if current_version != latest_version:
                    new_version = True
                    self.restore_parent_window(parent)
                    VersionWindow(latest_version, parent)
                    return
            except requests.RequestException as e:
                print(f"Error checking for updates: {e}")

            time.sleep(600)

    def restore_parent_window(self, parent):
        if not parent.winfo_viewable():
            parent.deiconify()
            parent.lift()
            parent.focus_force()
