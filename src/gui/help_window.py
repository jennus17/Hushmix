import customtkinter as ctk
from utils.icon_manager import IconManager
import gui.app as app


class HelpWindow:
    def __init__(self, parent):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call("tk", "scaling", 1.0)
        
        self.setup_window()
        self.window.transient(parent)
        self.window.grab_set()

        self.accent_color = app.get_windows_accent_color()
        self.normal_font_size = 14

        self.setup_gui()
        self.center_window(parent)
        self.window.lift()
        self.window.focus_force()

    def setup_window(self):
        self.window.title("Hushmix Help")
        self.window.resizable(False, False)
        self.window.geometry("600x400")

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")

    def setup_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")

        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.frame,
            corner_radius=0,
            border_width=0,
            fg_color=self.frame.cget("fg_color")
        )
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.create_sections()

    def create_sections(self):
        """Create all help sections."""
        self.create_overview_section()
        self.create_special_commands_section()
        self.create_application_names_section()
        self.create_button_settings_section()
        self.create_profiles_section()
        self.create_settings_section()
        self.create_tips_section()

    def create_overview_section(self):
        """Create the overview section."""
        self.overview_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Hushmix Overview",
            font=("Segoe UI", self.normal_font_size + 8, "bold"),
            text_color=self.accent_color,
        )
        self.overview_label.pack(anchor="w", padx=10, pady=(5, 10))

        overview_text = (
            "Hushmix is a volume control application that allows you to:\n"
            "• Control individual application volumes\n"
            "• Control system audio (master, system sounds, microphone)\n"
            "• Use hardware buttons for quick volume adjustments\n"
            "• Create multiple profiles for different scenarios\n"
            "• Launch applications and send keyboard shortcuts via buttons\n"
            "• Mute/unmute applications with customizable button actions"
        )

        self.overview_text_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=overview_text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
        )
        self.overview_text_label.pack(anchor="w", padx=10, pady=(0, 15))

    def create_special_commands_section(self):
        """Create the special commands section."""
        self.special_commands_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Special Commands",
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color,
        )
        self.special_commands_label.pack(anchor="w", padx=10, pady=(5, 10))

        self.commands = [
            ("master", "Controls the main speaker/headphone volume"),
            ("system", "Controls Windows system sounds volume"),
            ("current", "Controls the currently focused application"),
            ("mic", "Controls the default microphone volume"),
        ]

        for command, description in self.commands:
            command_frame = ctk.CTkFrame(
                self.scrollable_frame,
                corner_radius=0,
                border_width=0,
                fg_color=self.scrollable_frame.cget("fg_color"),
            )
            command_frame.pack(anchor="w", padx=10, pady=2)

            command_label = ctk.CTkLabel(
                command_frame,
                text=f"• {command}:",
                text_color=self.accent_color,
                font=("Segoe UI", self.normal_font_size, "bold"),
            )
            command_label.pack(side="left")

            description_label = ctk.CTkLabel(
                command_frame,
                text=description,
                font=("Segoe UI", self.normal_font_size),
            )
            description_label.pack(side="left", padx=(10, 0))

        self.add_divider()

    def create_application_names_section(self):
        """Create the application names section."""
        self.app_names_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Application Names",
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color,
        )
        self.app_names_label.pack(anchor="w", padx=10, pady=(5, 10))

        app_names_text = (
            "For specific applications, use the process name found in Task Manager:\n"
            "• Open Task Manager (Ctrl+Shift+Esc)\n"
            "• Go to the 'Details' tab\n"
            "• Use the process name without '.exe' extension\n"
            "• Examples: chrome, discord, spotify, steam\n\n"
            "You can group multiple applications by separating them with commas:\n"
            "• Example: chrome, firefox, msedge\n"
            "• This will control all browsers simultaneously"
        )

        self.app_names_text_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=app_names_text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
        )
        self.app_names_text_label.pack(anchor="w", padx=10, pady=(0, 15))

        self.add_divider()

    def create_button_settings_section(self):
        """Create the button settings section."""
        self.button_settings_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Button Settings",
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color,
        )
        self.button_settings_label.pack(anchor="w", padx=10, pady=(5, 10))

        button_settings_text = (
            "Click the ⋮ button next to any volume slider to configure button actions:\n\n"
            "Mute Function:\n"
            "• Enable to mute/unmute the corresponding application\n"
            "• Choose trigger mode: Click, Double Click, or Hold\n\n"
            "Launch Application:\n"
            "• Enable to launch a specific application\n"
            "• Browse and select the executable file (.exe)\n"
            "• Choose trigger mode: Click, Double Click, or Hold\n\n"
            "Keyboard Shortcut:\n"
            "• Enable to send keyboard shortcuts\n"
            "• Click 'Record Shortcut' and press your desired keys\n"
            "• Choose trigger mode: Click, Double Click, or Hold\n\n"
            "Note: Multiple functions can be enabled simultaneously for the same button."
        )

        self.button_settings_text_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=button_settings_text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
        )
        self.button_settings_text_label.pack(anchor="w", padx=10, pady=(0, 15))

        self.add_divider()

    def create_profiles_section(self):
        """Create the profiles section."""
        self.profiles_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Profiles",
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color,
        )
        self.profiles_label.pack(anchor="w", padx=10, pady=(5, 10))

        profiles_text = (
            "Hushmix supports up to 5 profiles for different scenarios:\n\n"
            "• Each profile saves:\n"
            "  - Application names and volumes\n"
            "  - Button settings (mute, app launch, shortcuts)\n"
            "  - Button trigger modes\n\n"
            "• Switch between profiles using the dropdown menu\n"
            "• Changes are automatically saved to the current profile\n"
            "• Perfect for different work scenarios, gaming, or entertainment setups"
        )

        self.profiles_text_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=profiles_text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
        )
        self.profiles_text_label.pack(anchor="w", padx=10, pady=(0, 15))

        self.add_divider()

    def create_settings_section(self):
        """Create the settings section."""
        self.settings_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Settings",
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color,
        )
        self.settings_label.pack(anchor="w", padx=10, pady=(5, 10))

        settings_text = (
            "Access settings via the ⚙️ button:\n\n"
            "Invert Volume Range (100-0):\n"
            "• Reverses the volume control direction\n"
            "• Useful for certain hardware configurations\n\n"
            "Enable Auto Startup:\n"
            "• Automatically starts Hushmix with Windows\n"
            "• Requires administrator privileges\n\n"
            "Launch in Tray:\n"
            "• Starts Hushmix minimized to system tray\n"
            "• Access via tray icon\n\n"
            "Dark Mode:\n"
            "• Toggles between light and dark themes\n"
            "• Automatically matches Windows accent color"
        )

        self.settings_text_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=settings_text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
        )
        self.settings_text_label.pack(anchor="w", padx=10, pady=(0, 15))

        self.add_divider()

    def create_tips_section(self):
        """Create the tips section."""
        self.tips_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Tips & Tricks",
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.accent_color,
        )
        self.tips_label.pack(anchor="w", padx=10, pady=(5, 10))

        tips_text = (
            "• Use 'master' for overall volume control\n"
            "• Use 'system' to control Windows notification sounds\n"
            "• Use 'current' to control the application you're currently using\n"
            "• Use 'mic' to control your microphone volume\n"
            "• Group similar applications with commas for batch control\n"
            "• Create different profiles for work, gaming, and entertainment\n"
            "• Use button settings to create custom shortcuts and actions\n"
            "• The app runs in the system tray - left-click to restore\n"
            "• Volume changes are applied in real-time\n"
            "• Muted applications show red volume percentage"
        )

        self.tips_text_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=tips_text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
        )
        self.tips_text_label.pack(anchor="w", padx=10, pady=(0, 15))

    def add_divider(self):
        """Add a visual divider between sections."""
        divider_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="─" * 50,
            font=("Segoe UI", self.normal_font_size),
            text_color=self.accent_color,
        )
        divider_label.pack(anchor="center", padx=5, pady=10)

    def center_window(self, parent):
        self.window.update_idletasks()
        parent.update_idletasks()

        # Get parent window position and size
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        # Calculate center of parent window
        center_x = parent_x + parent_width // 2
        center_y = parent_y + parent_height // 2

        window_width = 600
        window_height = 700

        # Position window relative to parent center
        x = center_x - window_width // 2
        y = center_y - window_height // 2

        # Get screen dimensions for the monitor where the parent window is located
        # We need to find which monitor contains the parent window
        import ctypes
        from ctypes.wintypes import RECT, POINT
        
        def get_monitor_info():
            monitors = []
            
            def enum_monitor_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                rect = lprcMonitor.contents
                monitors.append({
                    'left': rect.left,
                    'top': rect.top,
                    'right': rect.right,
                    'bottom': rect.bottom,
                    'width': rect.right - rect.left,
                    'height': rect.bottom - rect.top
                })
                return True
            
            enum_monitor_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_ulong)
            enum_monitor_proc_func = enum_monitor_proc_type(enum_monitor_proc)
            
            try:
                ctypes.windll.user32.EnumDisplayMonitors(None, None, enum_monitor_proc_func, 0)
            except Exception as e:
                print(f"Error enumerating monitors: {e}")
                monitors = [{
                    'left': 0,
                    'top': 0,
                    'right': ctypes.windll.user32.GetSystemMetrics(0),
                    'bottom': ctypes.windll.user32.GetSystemMetrics(1),
                    'width': ctypes.windll.user32.GetSystemMetrics(0),
                    'height': ctypes.windll.user32.GetSystemMetrics(1)
                }]
            
            return monitors

        def is_position_on_monitor(x, y, monitor):
            return (monitor['left'] <= x <= monitor['right'] and 
                    monitor['top'] <= y <= monitor['bottom'])

        def find_monitor_for_position(x, y, monitors):
            for monitor in monitors:
                if is_position_on_monitor(x, y, monitor):
                    return monitor
            return None

        # Get monitor information
        monitors = get_monitor_info()
        
        # Find which monitor contains the parent window center
        target_monitor = find_monitor_for_position(center_x, center_y, monitors)
        
        if target_monitor is not None:
            # Ensure window stays within the target monitor bounds
            if x < target_monitor['left']:
                x = target_monitor['left']
            if y < target_monitor['top']:
                y = target_monitor['top']
            if x + window_width > target_monitor['right']:
                x = target_monitor['right'] - window_width
            if y + window_height > target_monitor['bottom']:
                y = target_monitor['bottom'] - window_height
        else:
            # Fallback: ensure window is on screen
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            if x < 0:
                x = 0
            if y < 0:
                y = 0
            if x + window_width > screen_width:
                x = screen_width - window_width
            if y + window_height > screen_height:
                y = screen_height - window_height

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
