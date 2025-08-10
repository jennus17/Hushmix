import customtkinter as ctk
import gui.app as app
import tkinter as tk
from tkinter import filedialog
from utils.icon_manager import IconManager
from utils.dpi_manager import DPIManager


class ButtonSettingsWindow:
    def __init__(
        self,
        parent,
        index,
        mute,
        app_launch_enabled,
        app_launch_paths,
        keyboard_shortcut_enabled,
        keyboard_shortcuts,
        mute_button_modes,
        app_button_modes,
        shortcut_button_modes,
        media_control_enabled,
        media_control_actions,
        media_control_button_modes,
        on_close,
        
    ):
        self.parent = parent
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call("tk", "scaling", 1.0)
        self.window.withdraw()

        self.setup_window()

        self.window.transient(parent)

        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)

        self.on_close = on_close
        self.index = index
        self.mute = mute
        self.app_launch_enabled = app_launch_enabled
        self.app_launch_paths = app_launch_paths
        self.keyboard_shortcut_enabled = keyboard_shortcut_enabled
        self.keyboard_shortcuts = keyboard_shortcuts
        self.mute_button_modes = mute_button_modes
        self.app_button_modes = app_button_modes
        self.shortcut_button_modes = shortcut_button_modes
        self.media_control_enabled = media_control_enabled
        self.media_control_actions = media_control_actions
        self.media_control_button_modes = media_control_button_modes
        self.dpi_manager = DPIManager()

        self.normal_font_size = 14

        self.setup_gui()
        self.window.after(
            50, lambda: (self.window.deiconify(), self.center_window(parent))
        )

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def setup_window(self):
        """Setup main window properties."""
        self.window.title("Button Settings")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_release()

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

    def setup_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")

        self.dpi_manager.adjust_dpi_scaling_delayed(self.window, "button settings window")

        if self.index >= len(self.mute):
            while len(self.mute) <= self.index:
                self.mute.append(ctk.BooleanVar(value=True))
        if self.index >= len(self.app_launch_enabled):
            while len(self.app_launch_enabled) <= self.index:
                self.app_launch_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.app_launch_paths):
            while len(self.app_launch_paths) <= self.index:
                self.app_launch_paths.append(ctk.StringVar(value=""))
        if self.index >= len(self.keyboard_shortcut_enabled):
            while len(self.keyboard_shortcut_enabled) <= self.index:
                self.keyboard_shortcut_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.keyboard_shortcuts):
            while len(self.keyboard_shortcuts) <= self.index:
                self.keyboard_shortcuts.append(ctk.StringVar(value=""))
        if self.index >= len(self.mute_button_modes):
            while len(self.mute_button_modes) <= self.index:
                self.mute_button_modes.append(ctk.StringVar(value="Click"))
        if self.index >= len(self.app_button_modes):
            while len(self.app_button_modes) <= self.index:
                self.app_button_modes.append(ctk.StringVar(value="Click"))
        if self.index >= len(self.shortcut_button_modes):
            while len(self.shortcut_button_modes) <= self.index:
                self.shortcut_button_modes.append(ctk.StringVar(value="Click"))
        if self.index >= len(self.media_control_enabled):
            while len(self.media_control_enabled) <= self.index:
                self.media_control_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.media_control_actions):
            while len(self.media_control_actions) <= self.index:
                self.media_control_actions.append(ctk.StringVar(value="Play/Pause"))
        if self.index >= len(self.media_control_button_modes):
            while len(self.media_control_button_modes) <= self.index:
                self.media_control_button_modes.append(ctk.StringVar(value="Click"))

        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=0)

        self.create_mute_row()
        
        self.create_app_launch_row()
        
        self.create_keyboard_shortcut_row()
        
        self.create_media_control_row()



    def create_mute_row(self):
        """Create the mute checkbox with button mode dropdown in a row."""
        self.mute_checkbox = ctk.CTkCheckBox(
            self.frame,
            text="Mute",
            variable=self.mute[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
        )
        self.mute_checkbox.grid(row=0, column=0, pady=10, padx=15, sticky="w")

        self.mute_mode_dropdown = ctk.CTkOptionMenu(
            self.frame,
            values=["Click", "Double Click", "Hold"],
            variable=self.mute_button_modes[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=150,
            height=30,
            corner_radius=10,
        )
        self.mute_mode_dropdown.grid(row=0, column=1, pady=10, padx=15, sticky="e")

    def create_app_launch_row(self):
        """Create the app launch checkbox with button mode dropdown in a row."""
        self.app_launch_checkbox = ctk.CTkCheckBox(
            self.frame,
            text="Launch Application",
            variable=self.app_launch_enabled[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.on_app_launch_toggle
        )
        self.app_launch_checkbox.grid(row=1, column=0, pady=10, padx=15, sticky="w")

        self.app_mode_dropdown = ctk.CTkOptionMenu(
            self.frame,
            values=["Click", "Double Click", "Hold"],
            variable=self.app_button_modes[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=150,
            height=30,
            corner_radius=10,
        )
        self.app_mode_dropdown.grid(row=1, column=1, pady=10, padx=15, sticky="e")

        self.file_frame = ctk.CTkFrame(self.frame, corner_radius=10, border_width=0)
        self.file_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")

        self.path_label = ctk.CTkLabel(
            self.file_frame,
            text="No application selected",
            font=("Segoe UI", 12),
        )
        self.path_label.pack(pady=(5, 5), padx=15, anchor="w")

        self.browse_button = ctk.CTkButton(
            self.file_frame,
            text="Browse",
            font=("Segoe UI", 12),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.browse_file,
            width=80,
            height=30
        )
        self.browse_button.pack(pady=(0, 5), padx=15, anchor="w")

        self.update_app_launch_ui()

    def create_keyboard_shortcut_row(self):
        """Create the keyboard shortcut checkbox with button mode dropdown in a row."""
        self.shortcut_checkbox = ctk.CTkCheckBox(
            self.frame,
            text="Keyboard Shortcut",
            variable=self.keyboard_shortcut_enabled[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.on_shortcut_toggle
        )
        self.shortcut_checkbox.grid(row=3, column=0, pady=10, padx=15, sticky="w")

        self.shortcut_mode_dropdown = ctk.CTkOptionMenu(
            self.frame,
            values=["Click", "Double Click", "Hold"],
            variable=self.shortcut_button_modes[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=150,
            height=30,
            corner_radius=10,
        )
        self.shortcut_mode_dropdown.grid(row=3, column=1, pady=10, padx=15, sticky="e")

        self.shortcut_input_frame = ctk.CTkFrame(self.frame, corner_radius=10, border_width=0)
        self.shortcut_input_frame.grid(row=4, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")

        self.shortcut_label = ctk.CTkLabel(
            self.shortcut_input_frame,
            text="Click to record shortcut:",
            font=("Segoe UI", 12),
        )
        self.shortcut_label.pack(pady=(5, 5), padx=15, anchor="w")

        self.shortcut_entry = ctk.CTkEntry(
            self.shortcut_input_frame,
            font=("Segoe UI", 12),
            height=30,
            placeholder_text="Press keys here...",
            state="readonly"
        )
        self.shortcut_entry.pack(pady=(0, 5), padx=15, fill="x")
        self.shortcut_entry.bind("<Button-1>", self.start_shortcut_recording)

        self.clear_shortcut_button = ctk.CTkButton(
            self.shortcut_input_frame,
            text="Clear",
            font=("Segoe UI", 12),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.clear_shortcut,
            width=80,
            height=30
        )
        self.clear_shortcut_button.pack(pady=(0, 5), padx=15, anchor="w")

        self.update_shortcut_ui()



    def on_app_launch_toggle(self):
        """Handle app launch checkbox toggle."""
        self.update_app_launch_ui()

    def on_shortcut_toggle(self):
        """Handle keyboard shortcut checkbox toggle."""
        self.update_shortcut_ui()

    def update_app_launch_ui(self):
        """Update the UI based on the app launch checkbox state."""
        if self.index >= len(self.app_launch_enabled):
            while len(self.app_launch_enabled) <= self.index:
                self.app_launch_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.app_launch_paths):
            while len(self.app_launch_paths) <= self.index:
                self.app_launch_paths.append(ctk.StringVar(value=""))
        
        is_enabled = self.app_launch_enabled[self.index].get()
        
        if is_enabled:
            self.file_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")
            self.browse_button.configure(state="normal")
            
            current_path = self.app_launch_paths[self.index].get()
            if current_path:
                import os
                filename = os.path.basename(current_path)
                self.path_label.configure(text=filename)
            else:
                self.path_label.configure(text="No application selected")
        else:
            self.file_frame.grid_remove()
            self.browse_button.configure(state="disabled")
        
        self.window.update_idletasks()
        
        current_x = self.window.winfo_x()
        current_y = self.window.winfo_y()
        
        required_width = self.window.winfo_reqwidth()
        required_height = self.window.winfo_reqheight()
        
        self.window.geometry(f"{required_width}x{required_height}+{current_x}+{current_y}")

    def update_shortcut_ui(self):
        """Update the UI based on the keyboard shortcut checkbox state."""
        if self.index >= len(self.keyboard_shortcut_enabled):
            while len(self.keyboard_shortcut_enabled) <= self.index:
                self.keyboard_shortcut_enabled.append(ctk.BooleanVar(value=False))
        if self.index >= len(self.keyboard_shortcuts):
            while len(self.keyboard_shortcuts) <= self.index:
                self.keyboard_shortcuts.append(ctk.StringVar(value=""))
        
        is_enabled = self.keyboard_shortcut_enabled[self.index].get()
        
        if is_enabled:
            self.shortcut_input_frame.grid(row=4, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")
            self.shortcut_entry.configure(state="normal")
            self.clear_shortcut_button.configure(state="normal")
            
            current_shortcut = self.keyboard_shortcuts[self.index].get()
            if current_shortcut:
                self.shortcut_entry.configure(state="normal")
                self.shortcut_entry.delete(0, "end")
                self.shortcut_entry.insert(0, current_shortcut)
                self.shortcut_entry.configure(state="readonly")
            else:
                self.shortcut_entry.configure(state="normal")
                self.shortcut_entry.delete(0, "end")
                self.shortcut_entry.configure(state="readonly")
        else:
            self.shortcut_input_frame.grid_remove()
            self.shortcut_entry.configure(state="disabled")
            self.clear_shortcut_button.configure(state="disabled")
        
        self.window.update_idletasks()
        
        current_x = self.window.winfo_x()
        current_y = self.window.winfo_y()
        
        required_width = self.window.winfo_reqwidth()
        required_height = self.window.winfo_reqheight()
        
        self.window.geometry(f"{required_width}x{required_height}+{current_x}+{current_y}")

    def create_media_control_row(self):
        """Create the media control checkbox with button mode dropdown in a row."""
        self.media_control_checkbox = ctk.CTkCheckBox(
            self.frame,
            text="Media Control",
            variable=self.media_control_enabled[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            hover_color=self.accent_hover,
            command=self.on_media_control_toggle
        )
        self.media_control_checkbox.grid(row=5, column=0, pady=10, padx=15, sticky="w")

        self.media_mode_dropdown = ctk.CTkOptionMenu(
            self.frame,
            values=["Click", "Double Click", "Hold"],
            variable=self.media_control_button_modes[self.index],
            font=("Segoe UI", self.normal_font_size),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=150,
            height=30,
            corner_radius=10,
        )
        self.media_mode_dropdown.grid(row=5, column=1, pady=10, padx=15, sticky="e")

        self.media_action_frame = ctk.CTkFrame(self.frame, corner_radius=10, border_width=0)
        self.media_action_frame.grid(row=6, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")

        self.media_action_label = ctk.CTkLabel(
            self.media_action_frame,
            text="Media Action:",
            font=("Segoe UI", 12),
        )
        self.media_action_label.pack(pady=(5, 5), padx=15, anchor="w")

        self.media_action_dropdown = ctk.CTkOptionMenu(
            self.media_action_frame,
            values=["Play/Pause", "Next Track", "Previous Track"],
            variable=self.media_control_actions[self.index],
            font=("Segoe UI", 12),
            fg_color=self.accent_color,
            button_color=self.accent_color,
            button_hover_color=self.accent_hover,
            dropdown_hover_color=self.accent_hover,
            width=200,
            height=30,
            corner_radius=10,
        )
        self.media_action_dropdown.pack(pady=(0, 5), padx=15, anchor="w")

        self.update_media_control_ui()

    def on_media_control_toggle(self):
        """Handle media control checkbox toggle."""
        self.update_media_control_ui()

    def update_media_control_ui(self):
        """Update the UI based on the media control checkbox state."""
        if self.index >= len(self.media_control_enabled):
            while len(self.media_control_enabled) <= self.index:
                self.media_control_enabled.append(ctk.BooleanVar(value=False))
        
        is_enabled = self.media_control_enabled[self.index].get()
        
        if is_enabled:
            self.media_action_frame.grid(row=6, column=0, columnspan=2, pady=(0, 10), padx=15, sticky="ew")
            self.media_action_dropdown.configure(state="normal")
        else:
            self.media_action_frame.grid_remove()
            self.media_action_dropdown.configure(state="disabled")
        
        self.window.update_idletasks()
        
        current_x = self.window.winfo_x()
        current_y = self.window.winfo_y()
        
        required_width = self.window.winfo_reqwidth()
        required_height = self.window.winfo_reqheight()
        
        self.window.geometry(f"{required_width}x{required_height}+{current_x}+{current_y}")

    def start_shortcut_recording(self, event=None):
        """Start recording keyboard shortcut."""
        if self.index >= len(self.keyboard_shortcuts):
            while len(self.keyboard_shortcuts) <= self.index:
                self.keyboard_shortcuts.append(ctk.StringVar(value=""))
        
        self.shortcut_entry.configure(state="normal")
        self.shortcut_entry.delete(0, "end")
        self.shortcut_entry.insert(0, "Press keys... (Escape to cancel)")
        self.shortcut_entry.configure(state="readonly")
        
        self.window.focus_force()
        
        self.window.bind("<Key>", self.on_key_press)
        self.window.bind("<KeyRelease>", self.on_key_release)
        
        self.recording_shortcut = True
        self.current_shortcut = []
        self.recorded_keys = []
        self.pressed_keys = set()
        self.modifier_keys = set()
        self.final_shortcut = ""

    def on_key_press(self, event):
        """Handle key press during shortcut recording."""
        if not hasattr(self, 'recording_shortcut') or not self.recording_shortcut:
            return
        
        if event.keysym == "Escape":
            self.recorded_keys = []
            self.shortcut_entry.configure(state="normal")
            self.shortcut_entry.delete(0, "end")
            self.shortcut_entry.insert(0, "")
            self.shortcut_entry.configure(state="readonly")
            self.stop_shortcut_recording()
            return
        
        key_mapping = {
            'period': '.',
            'comma': ',',
            'semicolon': ';',
            'colon': ':',
            'exclam': '!',
            'question': '?',
            'minus': '-',
            'underscore': '_',
            'equal': '=',
            'plus': '+',
            'bracketleft': '[',
            'bracketright': ']',
            'braceleft': '{',
            'braceright': '}',
            'backslash': '\\',
            'bar': '|',
            'slash': '/',
            'less': '<',
            'greater': '>',
            'quotedbl': '"',
            'apostrophe': "'",
            'grave': '`',
            'asciitilde': '~',
            'at': '@',
            'numbersign': '#',
            'dollar': '$',
            'percent': '%',
            'asciicircum': '^',
            'ampersand': '&',
            'asterisk': '*',
            'parenleft': '(',
            'parenright': ')'
        }
        
        key = event.keysym
        if key in key_mapping:
            key = key_mapping[key]
        
        if key in ["Control_L", "Control_R", "Ctrl"]:
            return
        if key in ["Shift_L", "Shift_R", "Shift"]:
            return
        if key in ["Alt_L", "Alt_R", "Alt"]:
            return
        if key in ["Meta_L", "Meta_R", "Win", "Windows"]:
            return
        
        self.pressed_keys.add(key)
        
        if key in ["Control_L", "Control_R", "Ctrl"]:
            self.modifier_keys.add("Ctrl")
        elif key in ["Shift_L", "Shift_R", "Shift"]:
            self.modifier_keys.add("Shift")
        elif key in ["Alt_L", "Alt_R", "Alt"]:
            self.modifier_keys.add("Alt")
        elif key in ["Meta_L", "Meta_R", "Win", "Windows"]:
            self.modifier_keys.add("Win")
        
        if event.state & 0x4:  # Control
            self.modifier_keys.add("Ctrl")
        if event.state & 0x1:  # Shift
            self.modifier_keys.add("Shift")
        if event.state & 0x8:  # Alt
            self.modifier_keys.add("Alt")
        if event.state & 0x20000:  # Windows key
            self.modifier_keys.add("Win")
        
        modifiers = list(self.modifier_keys)
        if modifiers:
            current_key_combo = "+".join(modifiers) + "+" + key
        else:
            current_key_combo = key
        
        if current_key_combo not in self.recorded_keys:
            self.recorded_keys.append(current_key_combo)
        
        display_text = " + ".join(self.recorded_keys) + " (Escape to cancel)"
        self.shortcut_entry.configure(state="normal")
        self.shortcut_entry.delete(0, "end")
        self.shortcut_entry.insert(0, display_text)
        self.shortcut_entry.configure(state="readonly")

    def on_key_release(self, event):
        """Handle key release during shortcut recording."""
        if not hasattr(self, 'recording_shortcut') or not self.recording_shortcut:
            return
        
        key_mapping = {
            'period': '.',
            'comma': ',',
            'semicolon': ';',
            'colon': ':',
            'exclam': '!',
            'question': '?',
            'minus': '-',
            'underscore': '_',
            'equal': '=',
            'plus': '+',
            'bracketleft': '[',
            'bracketright': ']',
            'braceleft': '{',
            'braceright': '}',
            'backslash': '\\',
            'bar': '|',
            'slash': '/',
            'less': '<',
            'greater': '>',
            'quotedbl': '"',
            'apostrophe': "'",
            'grave': '`',
            'asciitilde': '~',
            'at': '@',
            'numbersign': '#',
            'dollar': '$',
            'percent': '%',
            'asciicircum': '^',
            'ampersand': '&',
            'asterisk': '*',
            'parenleft': '(',
            'parenright': ')'
        }
        
        key = event.keysym
        if key in key_mapping:
            key = key_mapping[key]
        
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
        
        if key == "Control_L" or key == "Control_R" or key == "Ctrl":
            self.modifier_keys.discard("Ctrl")
        elif key == "Shift_L" or key == "Shift_R" or key == "Shift":
            self.modifier_keys.discard("Shift")
        elif key == "Alt_L" or key == "Alt_R" or key == "Alt":
            self.modifier_keys.discard("Alt")
        elif key == "Meta_L" or key == "Meta_R" or key == "Win" or key == "Windows":
            self.modifier_keys.discard("Win")
        
        if not self.pressed_keys and self.recorded_keys:
            modifiers = list(self.modifier_keys)
            non_modifier_keys = []
            
            for combo in self.recorded_keys:
                if '+' in combo:
                    parts = combo.split('+')
                    if parts:
                        non_modifier_keys.append(parts[-1])
                else:
                    non_modifier_keys.append(combo)
            
            if modifiers and non_modifier_keys:
                self.final_shortcut = "+".join(modifiers + non_modifier_keys)
            elif non_modifier_keys:
                self.final_shortcut = "+".join(non_modifier_keys)
            else:
                self.final_shortcut = ""
            
            if self.final_shortcut:
                self.keyboard_shortcuts[self.index].set(self.final_shortcut)
                self.shortcut_entry.configure(state="normal")
                self.shortcut_entry.delete(0, "end")
                self.shortcut_entry.insert(0, self.final_shortcut)
                self.shortcut_entry.configure(state="readonly")
            
            self.stop_shortcut_recording()

    def stop_shortcut_recording(self):
        """Stop recording keyboard shortcut."""
        self.recording_shortcut = False
        self.window.unbind("<Key>")
        self.window.unbind("<KeyRelease>")
        self.pressed_keys = set()
        self.modifier_keys = set()
        self.final_shortcut = ""

    def clear_shortcut(self):
        """Clear the current keyboard shortcut."""
        if self.index >= len(self.keyboard_shortcuts):
            while len(self.keyboard_shortcuts) <= self.index:
                self.keyboard_shortcuts.append(ctk.StringVar(value=""))
        
        self.keyboard_shortcuts[self.index].set("")
        self.shortcut_entry.configure(state="normal")
        self.shortcut_entry.delete(0, "end")
        self.shortcut_entry.configure(state="readonly")
        if hasattr(self, 'pressed_keys'):
            self.pressed_keys = set()
        if hasattr(self, 'modifier_keys'):
            self.modifier_keys = set()
        if hasattr(self, 'final_shortcut'):
            self.final_shortcut = ""

    def browse_file(self):
        """Open file dialog to select an application."""
        if self.index >= len(self.app_launch_paths):
            while len(self.app_launch_paths) <= self.index:
                self.app_launch_paths.append(ctk.StringVar(value=""))
        
        file_path = filedialog.askopenfilename(
            title="Select Application",
            filetypes=[
                ("Executable files", "*.exe"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.app_launch_paths[self.index].set(file_path)
            self.update_app_launch_ui()

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

    def close(self):
        self.window.grab_release()
        self.window.destroy()
        if self.on_close:
            self.on_close()
