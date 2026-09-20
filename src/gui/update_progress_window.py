"""Download progress window.

The download runs on a worker thread, but every widget update is marshalled
back with ``after``.  The previous version called ``update_progress`` directly
from the worker once (the "Verifying download" path), which is a Tk call from a
non-Tk thread.
"""

import threading

import customtkinter as ctk

from gui.base_window import BaseWindow
from utils.logging_setup import get_logger

logger = get_logger("update_progress_window")


class UpdateProgressWindow(BaseWindow):
    window_name = "update progress window"
    default_size = (420, 230)

    def __init__(self, parent, update_info, version_manager):
        super().__init__(parent, on_close=None)
        self.update_info = update_info
        self.version_manager = version_manager
        self.cancelled = False
        self._worker = None

        self.palette = self.build_palette()
        self.normal_font_size = 14

        self.build("Updating Hushmix", geometry="420x230", topmost=True)
        self.build_gui()
        self.show()
        self.apply_dpi_scaling()

    # ------------------------------------------------------------------ layout

    def build_gui(self):
        self.frame = ctk.CTkFrame(
            self.window,
            corner_radius=0,
            border_width=0,
            fg_color=self.palette.background,
        )
        self.frame.pack(expand=True, fill="both")

        self.status_label = ctk.CTkLabel(
            self.frame,
            text="Preparing to download update...",
            font=("Segoe UI", self.normal_font_size),
            wraplength=380,
            justify="left",
            text_color=self.palette.text,
        )
        self.status_label.pack(pady=(20, 10), padx=15)

        self.progress_bar = ctk.CTkProgressBar(
            self.frame,
            progress_color=self.palette.accent,
            fg_color=self.palette.surface_high,
        )
        self.progress_bar.pack(pady=(10, 6), padx=20, fill="x")
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.frame,
            text="0%",
            font=("Consolas", 12),
            text_color=self.palette.text_muted,
        )
        self.progress_label.pack(pady=(0, 10))

        self.cancel_button = ctk.CTkButton(
            self.frame,
            text="Cancel",
            command=self.cancel_update,
            fg_color="transparent",
            hover_color=self.palette.danger_surface,
            text_color=self.palette.danger,
            border_width=1,
            border_color=self.palette.danger,
            font=("Segoe UI", self.normal_font_size),
            corner_radius=10,
        )
        self.cancel_button.pack(pady=(6, 16))

    def on_shown(self):
        self.start_download()

    # --------------------------------------------------------------- download

    def start_download(self):
        self._worker = threading.Thread(
            target=self._download_worker, name="update-download", daemon=True
        )
        self._worker.start()

    def _download_worker(self):
        try:
            self._set_status("Downloading update...")

            path = self.version_manager.download_update(
                self.update_info["download_url"],
                progress_callback=self._on_progress,
                cancellation_check=lambda: self.cancelled,
            )

            if self.cancelled:
                return

            if not path:
                self._fail("Failed to download the update. Please check your internet connection.")
                return

            self._set_status("Verifying download...")
            self._set_progress(100)

            if self.cancelled:
                return

            if not self.version_manager.verify_download(
                path, self.update_info.get("checksum")
            ):
                self._fail("The downloaded file could not be verified. Please try again.")
                return

            if not getattr(self.version_manager, "can_auto_install", True):
                self._fail(
                    "Automatic install is unavailable in a development checkout.\n"
                    "Use Manual Download instead."
                )
                return

            self._set_status("Installing update...")
            installed = self.version_manager.install_update(path)
            if not installed and not self.cancelled:
                self._fail(
                    "The update could not be installed automatically. "
                    "Please download it manually."
                )
                self._open_release_page()

        except Exception as error:
            logger.exception("Update failed: %s", error)
            if not self.cancelled:
                self._fail(f"An error occurred during the update: {error}")

    # ------------------------------------------------------------- marshalling

    def _on_progress(self, progress):
        """Called from the worker thread."""
        self._set_progress(progress)

    def _set_status(self, text):
        self._post(lambda: self.status_label.configure(text=text))

    def _set_progress(self, progress):
        def _apply():
            value = max(0.0, min(100.0, float(progress)))
            self.progress_bar.set(value / 100.0)
            self.progress_label.configure(text=f"{int(value)}%")

        self._post(_apply)

    def _post(self, function):
        if self.cancelled:
            return
        try:
            if self.window.winfo_exists():
                self.window.after(0, function)
        except Exception as error:
            logger.debug("Could not update the progress window: %s", error)

    def _fail(self, message):
        def _apply():
            self.status_label.configure(text=message)
            self.cancel_button.configure(text="Close", command=self.close, state="normal")

        self._post(_apply)

    @staticmethod
    def _open_release_page():
        import webbrowser

        webbrowser.open("https://github.com/jennus17/Hushmix/releases/latest")

    # -------------------------------------------------------------- cancelling

    def cancel_update(self):
        self.cancelled = True
        self._set_status("Cancelling update...")
        self.cancel_button.configure(state="disabled")
        self.window.after(300, self._finish_cancellation)

    def _finish_cancellation(self):
        """Let the user close the window once the worker has noticed the flag."""
        self._set_status("Update cancelled - you can close this window now")

    def close(self):
        self.cancelled = True
        super().close()
