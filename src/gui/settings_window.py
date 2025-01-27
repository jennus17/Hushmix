import tkinter as tk
from gui.themes import THEMES
import ctypes

class SettingsWindow:
    def __init__(self, parent, config_manager, dark_mode, invert_volumes, auto_startup, on_close):
        self.window = tk.Toplevel(parent)
        self.window.title("Settings")
        self.window.resizable(False, False)
        
        # Make it modal
        self.window.transient(parent)
        self.window.grab_set()
        
        # Store references
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self.invert_volumes = invert_volumes
        self.auto_startup = auto_startup
        self.on_close = on_close
        
        self.title_font_size = 20
        self.normal_font_size = 10
        self.padding = 20
        
        # Setup GUI and update title bar immediately
        self.setup_gui()
        self.update_title_bar()
        self.center_window(parent)
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        
        # Track dark mode changes
        self.dark_mode.trace_add("write", self.update_theme)

    def setup_gui(self):
        theme = THEMES["dark" if self.dark_mode.get() else "light"]
        
        # Update window background
        self.window.configure(bg=theme["bg"])
        
        # Main frame
        self.frame = tk.Frame(
            self.window,
            bg=theme["bg"],
            padx=self.padding,
            pady=self.padding
        )
        self.frame.pack(expand=True, fill="both")
        
        # Title
        title = tk.Label(
            self.frame,
            text="Settings",
            font=("Segoe UI", self.title_font_size, "bold"),
            bg=theme["bg"],
            fg=theme["fg"]
        )
        title.pack(pady=(0, self.padding))
        
        # Settings checkboxes
        self.create_checkbox(
            "Invert Volume Range (100 - 0)",
            self.invert_volumes,
            theme
        )
        
        self.create_checkbox(
            "Enable Auto Startup",
            self.auto_startup,
            theme
        )
        
        self.create_checkbox(
            "Dark Mode",
            self.dark_mode,
            theme
        )
        
        # Close button
        close_btn = tk.Button(
            self.frame,
            text="Close",
            command=self.close,
            font=("Segoe UI", self.normal_font_size),
            bg=theme["accent"],
            fg="white",
            activebackground=theme["accent_hover"],
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=20,
            pady=5,
            cursor="hand2"
        )
        close_btn.pack(pady=(self.padding, 0))

    def create_checkbox(self, text, variable, theme):
        checkbox = tk.Checkbutton(
            self.frame,
            text=text,
            variable=variable,
            font=("Segoe UI", self.normal_font_size),
            bg=theme["bg"],
            fg=theme["fg"],
            selectcolor=theme["button_bg"],
            activebackground=theme["bg"],
            activeforeground=theme["fg"]
        )
        checkbox.pack(pady=5, anchor="w")

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
        
        # Set position
        self.window.geometry(f"+{x}+{y}")

    def close(self):
        self.window.grab_release()
        self.window.destroy()
        if self.on_close:
            self.on_close()

    def update_title_bar(self):
        """Update the window title bar color"""
        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            hwnd = self.window.winfo_id()
            rendering_policy = ctypes.c_int(2 if self.dark_mode.get() else 0)
            set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                               ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            
            # Force immediate redraw of the title bar
            self.window.update_idletasks()
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0004 | 0x0400  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )
        except Exception as e:
            print(f"Error setting settings window title bar theme: {e}")

    def update_theme(self, *args):
        """Update the window theme when dark mode changes"""
        if not hasattr(self, 'window') or not self.window.winfo_exists():
            return
            
        theme = THEMES["dark" if self.dark_mode.get() else "light"]
        self.window.configure(bg=theme["bg"])
        
        # Update window and frame
        self.frame.configure(bg=theme["bg"])
        
        # Update title bar
        self.update_title_bar()
        
        # Update all widgets
        for child in self.frame.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=theme["bg"], fg=theme["fg"])
            elif isinstance(child, tk.Checkbutton):
                child.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectcolor=theme["button_bg"],
                    activebackground=theme["bg"],
                    activeforeground=theme["fg"]
                )
            elif isinstance(child, tk.Button):
                child.configure(
                    bg=theme["accent"],
                    fg="white",
                    activebackground=theme["accent_hover"],
                    activeforeground="white"
                )
        
        # Force update
        self.window.update_idletasks() 