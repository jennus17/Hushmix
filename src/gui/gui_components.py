"""Main window GUI construction.

Layout notes (all of these were real defects):

* ``refresh_gui`` used to create a brand new footer frame on every call and
  never destroy the previous ones.  A ``CTkFrame`` defaults to a 200x200
  request, so each refresh left an orphaned frame gridded in the last row and
  the window grew by 220 px per refresh - that is why the window ended up much
  taller than its content.
* The per-slider button handed the *volume* index to ``show_buttonSettings``,
  which expects a 0-based button index, so the wrong channel's settings opened.
* The footer was laid out with spans that overlapped the channel grid.
"""

import tkinter as tk

import customtkinter as ctk

from utils.color_utils import darken_color, get_windows_accent_color
from utils.config_manager import ConfigManager
from utils.logging_setup import get_logger

logger = get_logger("gui_components")


class GUIComponents:
    def __init__(self, app_instance):
        self.app = app_instance
        self.root = app_instance.root

        self.main_frame = None
        self.footer_frame = None
        self.profile_listbox = None
        self.help_button = None
        self.settings_button = None
        self.add_profile_button = None
        self.delete_profile_button = None
        self.connection_status_label = None

        self.entries = []
        self.buttons = []
        self.volume_labels = []

        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)
        self.normal_font_size = 16

        self._refreshing = False

    # ------------------------------------------------------------------ layout

    def setup_gui(self):
        """Build the main window contents (called once)."""
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=0, border_width=0)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.bind("<Button-1>", lambda event: event.widget.focus_force())

        self.connection_status_label = ctk.CTkLabel(
            self.main_frame,
            text="Mixer Disconnected",
            font=("Segoe UI", 12, "bold"),
            text_color="red3",
            width=1,
            height=1,
        )

        self.refresh_gui()

    def _accent_button(self, master, text, command, font, width, height):
        return ctk.CTkButton(
            master,
            text=text,
            command=command,
            font=font,
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            cursor="hand2",
            width=width,
            height=height,
            corner_radius=10,
        )

    def refresh_gui(self):
        """Rebuild the channel rows to match ``app.current_apps``."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._destroy_channel_widgets()

            for index, app_name in enumerate(self.app.current_apps):
                self._create_channel_row(index, app_name, len(self.app.current_apps))

            self._layout_footer()
            self._configure_grid()

            self.app.previous_volumes = [None] * len(self.app.current_apps)
            self.app.update_connection_status()
        finally:
            self._refreshing = False

    def _destroy_channel_widgets(self):
        """Destroy every widget this class creates, so nothing is orphaned.

        Anything left gridded keeps reserving space - that is how the window
        grew to twice its content height.
        """
        widgets = (
            self.entries
            + self.volume_labels
            + self.buttons
            + [
                self.profile_listbox,
                self.help_button,
                self.settings_button,
                self.add_profile_button,
                self.delete_profile_button,
                self.footer_frame,
            ]
        )
        for widget in widgets:
            if widget is None:
                continue
            try:
                widget.destroy()
            except Exception:
                pass

        self.buttons.clear()
        self.entries.clear()
        self.volume_labels.clear()
        self.footer_frame = None
        self.profile_listbox = None
        self.help_button = None
        self.settings_button = None
        self.add_profile_button = None
        self.delete_profile_button = None

    def _create_channel_row(self, index, app_name, total):
        # Channel 0 is master and the last one is the microphone, so only the
        # channels in between get a per-button settings entry point.
        if 0 < index < total - 1:
            button = ctk.CTkButton(
                self.main_frame,
                text="⋮",
                command=lambda button_index=index: self.app.show_buttonSettings(
                    button_index
                ),
                hover_color=self.accent_hover,
                fg_color=self.accent_color,
                cursor="hand2",
                width=24,
                height=26,
                corner_radius=8,
            )
            button.grid(row=index + 1, column=2, pady=4, padx=3, sticky="nsew")
            self.buttons.append(button)

        entry = ctk.CTkEntry(
            self.main_frame,
            font=("Segoe UI", self.normal_font_size),
            height=30,
            placeholder_text=f"App {index + 1}",
            border_width=2,
            corner_radius=10,
        )
        if app_name:
            entry.insert(0, app_name)

        if index == 0:
            entry.grid(
                row=index + 1, column=0, columnspan=3, pady=(8, 4), padx=(10, 1), sticky="nsew"
            )
        elif index == total - 1:
            entry.grid(
                row=index + 1, column=0, columnspan=3, pady=4, padx=(10, 1), sticky="nsew"
            )
        else:
            entry.grid(
                row=index + 1, column=0, columnspan=2, pady=4, padx=(10, 1), sticky="nsew"
            )

        entry.bind("<KeyRelease>", self._on_entry_changed)
        entry.bind(
            "<Button-3>", lambda event, idx=index: self._show_app_suggestions(event, idx)
        )

        volume_label = ctk.CTkLabel(
            self.main_frame,
            text="100%",
            width=45,
            font=("Segoe UI", self.normal_font_size, "bold"),
        )
        volume_label.grid(row=index + 1, column=3, pady=6, padx=5, sticky="w")
        volume_label.bind("<Button-1>", lambda event: event.widget.focus_force())
        volume_label.default_text_color = volume_label.cget("text_color")

        self.entries.append(entry)
        self.volume_labels.append(volume_label)

    def _on_entry_changed(self, event=None):
        self.app.save_applications()

    def _layout_footer(self):
        """Create and place the profile controls and the window buttons.

        The footer inherits the default 200x200 request of a ``CTkFrame``, so it
        is created with an explicit 1x1 size; otherwise it alone dictates the
        window height.
        """
        footer = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
            width=1,
            height=1,
        )
        footer.grid(
            row=len(self.app.current_apps) + 1,
            column=0,
            columnspan=4,
            padx=10,
            pady=(6, 10),
            sticky="ew",
        )
        footer.columnconfigure(0, weight=1)
        self.footer_frame = footer

        self.profile_listbox = ctk.CTkOptionMenu(
            footer,
            values=ConfigManager.get_profile_names(),
            command=self.app.on_profile_change,
            font=("Segoe UI", self.normal_font_size, "bold"),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=170,
            height=34,
            corner_radius=10,
        )
        self.profile_listbox.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.add_profile_button = self._accent_button(
            footer,
            text="＋",
            command=self._prompt_add_profile,
            font=("Segoe UI", self.normal_font_size, "bold"),
            width=32,
            height=34,
        )
        self.add_profile_button.grid(row=0, column=1, padx=(0, 2))

        self.delete_profile_button = self._accent_button(
            footer,
            text="－",
            command=self._prompt_delete_profile,
            font=("Segoe UI", self.normal_font_size, "bold"),
            width=32,
            height=34,
        )
        self.delete_profile_button.grid(row=0, column=2, padx=(6, 0))

        self.help_button = self._accent_button(
            footer,
            text=" ⓘ ",
            command=self.app.show_help,
            font=("Segoe UI", self.normal_font_size, "bold"),
            width=30,
            height=34,
        )
        self.help_button.grid(row=0, column=3, padx=8)

        self.settings_button = self._accent_button(
            footer,
            text="⚙️",
            command=self.app.show_settings,
            font=("Segoe UI", self.normal_font_size + 1),
            width=38,
            height=34,
        )
        self.settings_button.grid(row=0, column=4, sticky="e")

        if self.connection_status_label:
            self.connection_status_label.grid(
                row=0, column=0, columnspan=4, pady=(8, 0), padx=10, sticky="ew"
            )

    def _configure_grid(self):
        self.main_frame.columnconfigure(0, weight=1)
        for column in (1, 2, 3):
            self.main_frame.columnconfigure(column, weight=0)

    # ---------------------------------------------------------- profile actions

    def _prompt_add_profile(self):
        """Ask for a name and create a profile copied from the current one."""
        from tkinter import simpledialog

        name = simpledialog.askstring(
            "New profile",
            "Name for the new profile:",
            parent=self.root,
        )
        if not name:
            return

        # ``app.add_profile`` refreshes the dropdown itself.
        self.app.add_profile(name)

    def _prompt_delete_profile(self):
        current = self.profile_listbox.get() if self.profile_listbox else None
        if current:
            self.app.delete_profile(current)

    # ----------------------------------------------------- right-click helpers

    def _show_app_suggestions(self, event, index):
        """Offer the processes that are currently playing audio."""
        try:
            names = self.app.audio_controller.list_audio_applications()
        except Exception as error:
            logger.warning("Could not list audio applications: %s", error)
            names = []

        if not names:
            return

        popup = tk.Toplevel(self.root)
        popup.title("Audio applications")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.geometry(f"+{event.x_root + 5}+{event.y_root + 5}")

        ctk.CTkLabel(
            popup, text="Double-click to use this name", font=("Segoe UI", 11)
        ).pack(padx=8, pady=(8, 2), anchor="w")

        listbox = tk.Listbox(popup, height=min(12, len(names)), activestyle="none")
        for name in names:
            listbox.insert("end", name)
        listbox.pack(fill="both", expand=True, padx=8, pady=4)

        def choose(_event=None):
            selection = listbox.curselection()
            if selection:
                entry = self.entries[index]
                entry.delete(0, "end")
                entry.insert(0, listbox.get(selection[0]))
                self.app.save_applications()
            dismiss()

        def dismiss(_event=None):
            try:
                popup.destroy()
            except Exception:
                pass

        listbox.bind("<Double-Button-1>", choose)
        listbox.bind("<Return>", choose)
        listbox.bind("<Escape>", dismiss)
        popup.bind("<Escape>", dismiss)
        listbox.focus_set()

    # ------------------------------------------------------------------- theme

    def update_theme_colors(self):
        """Re-read the Windows accent colour and restyle the widgets."""
        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)

        for widget in (
            self.profile_listbox,
            self.help_button,
            self.settings_button,
            self.add_profile_button,
            self.delete_profile_button,
        ):
            if widget is None:
                continue
            try:
                widget.configure(fg_color=self.accent_color, hover_color=self.accent_hover)
            except Exception:
                pass

        try:
            self.profile_listbox.configure(
                button_color=self.accent_color,
                button_hover_color=self.accent_hover,
                dropdown_hover_color=self.accent_hover,
            )
        except Exception:
            pass

        for button in self.buttons:
            if button.winfo_exists():
                button.configure(fg_color=self.accent_color, hover_color=self.accent_hover)

    def set_profile_names(self, names, current=None):
        """Refresh the profile dropdown after profiles are added or removed."""
        if not self.profile_listbox:
            return
        self.profile_listbox.configure(values=list(names))
        if current and current in names:
            self.profile_listbox.set(current)
