import customtkinter as ctk
from gui.help_window import HelpWindow
from utils.color_utils import get_windows_accent_color, darken_color


class GUIComponents:
    def __init__(self, app_instance):
        self.app = app_instance
        self.root = app_instance.root
        self.main_frame = None
        self.profile_listbox = None
        self.help_button = None
        self.settings_button = None
        self.connection_status_label = None
        self.entries = []
        self.buttons = []
        self.volume_labels = []
        
        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)
        self.normal_font_size = 16
    
    def setup_gui(self):
        """Setup GUI components."""
        self.main_frame = ctk.CTkFrame(
            self.root,
            corner_radius=0,
            border_width=0,
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.bind("<Button-1>", lambda event: event.widget.focus_force())

        self.profile_listbox = ctk.CTkOptionMenu(
            self.main_frame,
            values=["Profile 1", "Profile 2", "Profile 3", "Profile 4", "Profile 5"],
            command=self.app.on_profile_change,
            font=("Segoe UI", self.normal_font_size, "bold"),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=190,
            height=40,
            corner_radius=10,
        )

        self.help_button = ctk.CTkButton(
            self.main_frame,
            text=" ⓘ ",
            command=lambda: HelpWindow(self.root),
            font=("Segoe UI", self.normal_font_size, "bold"),
            hover_color=self.accent_hover,
            fg_color=self.accent_color,
            cursor="hand2",
            width=30,
            height=40,
            corner_radius=10,
        )

        self.settings_button = ctk.CTkButton(
            self.main_frame,
            text="⚙️",
            command=self.app.show_settings,
            font=("Segoe UI", self.normal_font_size + 1),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            cursor="hand2",
            width=40,
            height=40,
            corner_radius=10,
        )

        self.connection_status_label = ctk.CTkLabel(
            self.main_frame,
            text="Mixer Disconnected",
            font=("Segoe UI", 12, "bold"),
            text_color="red3"
        )
        self.connection_status_label.grid(
            row=0, 
            column=0, 
            columnspan=4, 
            pady=(10, 5), 
            padx=10, 
            sticky="ew"
        )
        
        self.app.update_connection_status()
        
        self.refresh_gui()

    def refresh_gui(self):
        """Refresh the GUI to match the current applications."""
        for entry in self.entries:
            entry.destroy()
        for buttons in self.buttons:
            buttons.destroy()
        for label in self.volume_labels:
            label.destroy()

        self.buttons.clear()
        self.entries.clear()
        self.volume_labels.clear()

        for i, app_name in enumerate(self.app.current_apps):
            sliders = len(self.app.current_apps)

            if i > 0 and i < sliders - 1:
                button = ctk.CTkButton(
                    self.main_frame,
                    text="⋮",
                    command=lambda idx=i: self.app.show_buttonSettings(idx),
                    hover_color=self.accent_hover,
                    fg_color=self.accent_color,
                    cursor="hand2",
                    width=5,
                    height=25,
                    corner_radius=8,
                )
                button.grid(
                    row=i + 1, column=2, columnspan=1, pady=7, padx=3, sticky="nsew"
                )
                self.buttons.append(button)

            entry = ctk.CTkEntry(
                self.main_frame,
                font=("Segoe UI", self.normal_font_size),
                height=30,
                placeholder_text=f"App {i + 1}",
                border_width=2,
                corner_radius=10,
            )
            if app_name != "":
                entry.insert(0, app_name)
            if i == 0:
                entry.grid(
                    row=i + 1,
                    column=0,
                    columnspan=3,
                    pady=(10, 4),
                    padx=(10, 1),
                    sticky="nsew",
                )
            elif i == sliders - 1:
                entry.grid(
                    row=i + 1,
                    column=0,
                    columnspan=3,
                    pady=4,
                    padx=(10, 1),
                    sticky="nsew",
                )
            else:
                entry.grid(
                    row=i + 1, column=0, columnspan=2, pady=4, padx=(10, 1), sticky="nsew"
                )

            entry.bind("<KeyRelease>", lambda e: self.app.save_applications())

            volume_label = ctk.CTkLabel(
                self.main_frame,
                text="100%",
                width=45,
                font=("Segoe UI", self.normal_font_size, "bold"),
            )
            volume_label.grid(row=i + 1, column=3, pady=6, padx=5, sticky="w")
            volume_label.bind("<Button-1>", lambda event: event.widget.focus_force())
            volume_label.default_text_color = volume_label.cget("text_color")

            self.entries.append(entry)
            self.volume_labels.append(volume_label)

        self.profile_listbox.grid(
            row=len(self.app.current_apps) + 1, column=0, columnspan=1, padx=(10, 0), pady=10
        )
        self.help_button.grid(
            row=len(self.app.current_apps) + 1,
            column=1,
            columnspan=2,
            pady=10,
            padx=5,
            sticky="ew",
        )
        self.settings_button.grid(
            row=len(self.app.current_apps) + 1,
            column=2,
            columnspan=2,
            pady=10,
            padx=(0, 10),
            sticky="e",
        )

        if self.connection_status_label:
            self.connection_status_label.grid(
                row=0, 
                column=0, 
                columnspan=4, 
                pady=(10, 0), 
                padx=10, 
                sticky="ew"
            )

        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.columnconfigure(2, weight=0)

        self.app.previous_volumes = [None] * len(self.app.current_apps)

        if self.entries:
            entry_names = [entry.get() for entry in self.entries]
            if entry_names != self.app.current_apps:
                self.app.load_settings()
                return
        
        self.app.update_connection_status()

    def update_theme_colors(self):
        """Update theme colors for all GUI components."""
        self.accent_color = get_windows_accent_color()
        self.accent_hover = darken_color(self.accent_color, 0.2)
        
        if self.profile_listbox:
            self.profile_listbox.configure(
                fg_color=self.accent_color,
                button_color=self.accent_color,
                button_hover_color=self.accent_hover,
                dropdown_hover_color=self.accent_hover
            )
        
        if self.help_button:
            self.help_button.configure(
                fg_color=self.accent_color,
                hover_color=self.accent_hover
            )
        
        if self.settings_button:
            self.settings_button.configure(
                fg_color=self.accent_color,
                hover_color=self.accent_hover
            )
        
        for button in self.buttons:
            if button.winfo_exists():
                button.configure(
                    fg_color=self.accent_color,
                    hover_color=self.accent_hover
                ) 