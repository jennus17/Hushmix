"""Update available dialog."""

import webbrowser

import customtkinter as ctk

from gui.base_window import BaseWindow
from utils.logging_setup import get_logger

logger = get_logger("version_window")

RELEASES_PAGE = "https://github.com/jennus17/Hushmix/releases/latest"


class VersionWindow(BaseWindow):
    window_name = "version window"
    default_size = (420, 300)

    def __init__(
        self,
        latest_version,
        parent,
        update_info=None,
        version_manager=None,
        settings_manager=None,
        on_close=None,
    ):
        super().__init__(parent, on_close=on_close)
        self.latest_version = latest_version
        self.update_info = update_info or {}
        self.version_manager = version_manager
        self.settings_manager = settings_manager

        self.palette = self.build_palette(settings_manager)
        self.normal_font_size = 14

        self.build("Update available", topmost=True)
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

        body = self.update_info.get("release_notes") or ""
        published = self.update_info.get("published_at") or ""

        ctk.CTkLabel(
            self.frame,
            text=f"A new version ({self.latest_version}) is available!",
            font=("Segoe UI", self.normal_font_size + 1, "bold"),
            wraplength=380,
            justify="left",
            text_color=self.palette.text,
        ).pack(pady=(20, 6), padx=15)

        if published:
            ctk.CTkLabel(
                self.frame,
                text=f"Published: {published[:10]}",
                font=("Segoe UI", 11),
                text_color=self.palette.text_muted,
            ).pack(pady=(0, 6), padx=15)

        if body:
            notes = body.strip()
            if len(notes) > 600:
                notes = notes[:600] + "…"
            box = ctk.CTkTextbox(
                self.frame,
                height=110,
                font=("Segoe UI", 11),
                wrap="word",
                fg_color=self.palette.surface,
                border_color=self.palette.border,
                border_width=1,
                text_color=self.palette.text_muted,
            )
            box.pack(pady=(0, 10), padx=15, fill="both", expand=True)
            box.insert("1.0", notes)
            box.configure(state="disabled")

        theme = self.get_theme_colors()

        ctk.CTkButton(
            self.frame,
            text="View Release",
            command=self.view_release,
            font=("Segoe UI", 12),
            corner_radius=10,
            fg_color=theme["fg_color"],
            hover_color=theme["hover_color"],
            text_color=theme["text_color"],
        ).pack(pady=(4, 8), padx=15, fill="x")

        buttons = ctk.CTkFrame(self.frame, fg_color="transparent")
        buttons.pack(pady=(0, 8))

        if self.version_manager and getattr(self.version_manager, "can_auto_install", True):
            ctk.CTkButton(
                buttons,
                text="Update Now",
                command=self.auto_update,
                fg_color=self.palette.accent,
                hover_color=self.palette.accent_hover,
                text_color=self.palette.accent_text,
                font=("Segoe UI", self.normal_font_size),
                corner_radius=10,
            ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons,
            text="Manual Download",
            command=self.manual_download,
            fg_color="transparent",
            hover_color=theme["hover_color"],
            text_color=theme["text_color"],
            border_width=1,
            border_color=self.palette.border_strong,
            font=("Segoe UI", self.normal_font_size),
            corner_radius=10,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.frame,
            text="Remind Me Later",
            command=self.close,
            font=("Segoe UI", 12),
            corner_radius=10,
            fg_color=theme["fg_color"],
            hover_color=theme["hover_color"],
            text_color=theme["text_color"],
        ).pack(pady=(4, 4))

        if self.version_manager is not None:
            ctk.CTkButton(
                self.frame,
                text=f"Skip version {self.latest_version}",
                command=self.skip_this_version,
                font=("Segoe UI", 11),
                corner_radius=10,
                fg_color="transparent",
                hover_color=theme["hover_color"],
                text_color=theme["text_color"],
                height=24,
            ).pack(pady=(0, 12))

    def get_theme_colors(self):
        """Colours for the window's secondary (non-accent) controls."""
        return {
            "fg_color": self.palette.surface_high,
            "hover_color": self.palette.surface_low,
            "text_color": self.palette.text,
        }

    # --------------------------------------------------------------- behaviour

    def auto_update(self):
        """Open the download progress window."""
        from gui.update_progress_window import UpdateProgressWindow

        self.close()
        UpdateProgressWindow(self.parent, self.update_info, self.version_manager)

    def view_release(self):
        webbrowser.open(self.update_info.get("release_page", RELEASES_PAGE))

    def manual_download(self):
        download_url = self.update_info.get("download_url")
        if download_url:
            webbrowser.open(download_url)
        webbrowser.open(self.update_info.get("release_page", RELEASES_PAGE))
        self.close()

    def skip_this_version(self):
        """Persistently ignore this release (no further prompts for it)."""
        if self.version_manager is not None:
            try:
                self.version_manager.skip_version(self.latest_version)
            except Exception as error:
                logger.warning("Could not remember the skipped version: %s", error)
        self.close()
