"""Help window: feature documentation plus a diagnostics panel."""

import os
import platform
import sys
import webbrowser

import customtkinter as ctk

from gui.base_window import BaseWindow
from utils.app_paths import log_file
from utils.config_manager import ConfigManager
from utils.logging_setup import get_logger

logger = get_logger("help_window")

RELEASES_URL = "https://github.com/jennus17/Hushmix/releases/latest"
ISSUES_URL = "https://github.com/jennus17/Hushmix/issues"

SPECIAL_COMMANDS = [
    ("master", "Controls the main speaker/headphone volume"),
    ("system", "Controls Windows system sounds volume"),
    ("current", "Controls the currently focused application"),
    ("mic", "Controls the default microphone volume"),
]

OVERVIEW_TEXT = (
    "Hushmix is a volume control application that allows you to:\n"
    "• Control individual application volumes\n"
    "• Control system audio (master, system sounds, microphone)\n"
    "• Use hardware buttons for quick volume adjustments\n"
    "• Create multiple profiles for different scenarios\n"
    "• Launch applications and send keyboard shortcuts via buttons\n"
    "• Mute/unmute applications with customizable button actions"
)

APP_NAMES_TEXT = (
    "For specific applications, use the process name found in Task Manager:\n"
    "• Open Task Manager (Ctrl+Shift+Esc)\n"
    "• Go to the 'Details' tab\n"
    "• Use the process name without '.exe' extension\n"
    "• Examples: chrome, discord, spotify, steam\n\n"
    "Tip: right-click any application field in the main window to pick from the\n"
    "processes that are currently playing audio.\n\n"
    "You can group multiple applications by separating them with commas:\n"
    "• Example: chrome, firefox, msedge\n"
    "• This will control all browsers simultaneously"
)

BUTTON_SETTINGS_TEXT = (
    "Click the ⋮ button next to an application field to configure that button:\n\n"
    "Mute Function:\n"
    "• Enable to mute/unmute the corresponding application\n"
    "• Choose trigger mode: Click, Double Click, or Hold\n\n"
    "Launch Application:\n"
    "• Enable to launch a specific application\n"
    "• Browse and select the executable file (.exe)\n"
    "• Choose trigger mode: Click, Double Click, or Hold\n\n"
    "Keyboard Shortcut:\n"
    "• Enable to send keyboard shortcuts\n"
    "• Click the field and press your desired keys\n"
    "• Choose trigger mode: Click, Double Click, or Hold\n\n"
    "Media Control:\n"
    "• Play/Pause, Next Track, Previous Track\n\n"
    "Note: Multiple functions can be enabled simultaneously for the same button."
)

PROFILES_TEXT = (
    "Each profile saves:\n"
    "• Application names and per-channel mute state\n"
    "• Button settings (mute, app launch, shortcuts, media control)\n"
    "• Button trigger modes\n\n"
    "• Switch between profiles using the dropdown menu\n"
    "• Add a profile with ＋ (it starts as a copy of the current one)\n"
    "• Remove the selected profile with －\n"
    "• Changes are saved to the current profile automatically"
)

SETTINGS_TEXT = (
    "Access settings via the ⚙️ button:\n\n"
    "Invert Volume Range (100-0):\n"
    "• Reverses the volume control direction\n"
    "• Useful for certain hardware configurations\n\n"
    "Enable Auto Startup:\n"
    "• Starts Hushmix with Windows (per-user, no admin rights needed)\n\n"
    "Launch in Tray:\n"
    "• Starts Hushmix minimised to the system tray\n"
    "• Access it from the tray icon\n\n"
    "Dark Mode:\n"
    "• Toggles between light and dark themes\n"
    "• Accent colours follow your Windows accent colour"
)

TIPS_TEXT = (
    "• Use 'master' for overall volume control\n"
    "• Use 'system' to control Windows notification sounds\n"
    "• Use 'current' to control the application you're currently using\n"
    "• Use 'mic' to control your microphone volume\n"
    "• Group similar applications with commas for batch control\n"
    "• Create different profiles for work, gaming and entertainment\n"
    "• Muted applications show a red volume percentage\n"
    "• Volume changes are applied in real time\n"
    "• If the mixer is unplugged, Hushmix keeps retrying automatically"
)


class HelpWindow(BaseWindow):
    window_name = "help window"
    default_size = (620, 700)

    def __init__(self, parent, app=None):
        super().__init__(parent, on_close=None)
        self.app = app

        settings_manager = getattr(app, "settings_manager", None)
        self.palette = self.build_palette(settings_manager)
        self.normal_font_size = 14

        self.build("Hushmix Help", geometry="620x700")
        self.build_gui()
        self.show(delay=10)
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

        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.frame,
            corner_radius=0,
            border_width=0,
            fg_color="transparent",
            scrollbar_button_color=self.palette.border_strong,
            scrollbar_button_hover_color=self.palette.accent,
        )
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self._title("Hushmix Overview", padding=(5, 10))
        self._body(OVERVIEW_TEXT)

        self._title("Special Commands")
        for command, description in SPECIAL_COMMANDS:
            self._command_row(command, description)
        self._divider()

        self._title("Application Names")
        self._body(APP_NAMES_TEXT)
        self._divider()

        self._title("Button Settings")
        self._body(BUTTON_SETTINGS_TEXT)
        self._divider()

        self._title("Profiles")
        self._body(PROFILES_TEXT)
        self._divider()

        self._title("Settings")
        self._body(SETTINGS_TEXT)
        self._divider()

        self._title("Tips & Tricks")
        self._body(TIPS_TEXT)
        self._divider()

        self._build_diagnostics()

    # ---------------------------------------------------------------- sections

    def _title(self, text, padding=(15, 10)):
        label = ctk.CTkLabel(
            self.scrollable_frame,
            text=text,
            font=("Segoe UI", self.normal_font_size + 6, "bold"),
            text_color=self.palette.accent_on_label,
        )
        label.pack(anchor="w", padx=10, pady=padding)

    def _body(self, text):
        label = ctk.CTkLabel(
            self.scrollable_frame,
            text=text,
            font=("Segoe UI", self.normal_font_size),
            justify="left",
            text_color=self.palette.text_muted,
        )
        label.pack(anchor="w", padx=10, pady=(0, 15))

    def _command_row(self, command, description):
        frame = ctk.CTkFrame(self.scrollable_frame, corner_radius=0, border_width=0)
        frame.pack(anchor="w", padx=10, pady=2)

        ctk.CTkLabel(
            frame,
            text=f"• {command}:",
            text_color=self.palette.accent_on_label,
            font=("Segoe UI", self.normal_font_size, "bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            frame,
            text=description,
            font=("Segoe UI", self.normal_font_size),
            text_color=self.palette.text_muted,
        ).pack(side="left", padx=(10, 0))

    def _divider(self):
        ctk.CTkLabel(
            self.scrollable_frame,
            text="─" * 60,
            font=("Segoe UI", self.normal_font_size),
            text_color=self.palette.border_strong,
        ).pack(anchor="center", padx=5, pady=10)

    # ------------------------------------------------------------- diagnostics

    def _build_diagnostics(self):
        """Surface the information needed to report a problem."""
        self._title("Diagnostics")
        self._body(self._diagnostics_text())

        button_row = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        button_row.pack(anchor="w", padx=10, pady=(0, 15))

        ctk.CTkButton(
            button_row,
            text="Open log file",
            command=self._open_log,
            text_color=self.palette.accent_text,
            fg_color=self.palette.accent,
            hover_color=self.palette.accent_hover,
            font=("Segoe UI", 12),
            corner_radius=10,
            width=120,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            button_row,
            text="Report an issue",
            command=lambda: webbrowser.open(ISSUES_URL),
            text_color=self.palette.accent_text,
            fg_color=self.palette.accent,
            hover_color=self.palette.accent_hover,
            font=("Segoe UI", 12),
            corner_radius=10,
            width=130,
        ).pack(side="left")

    def _diagnostics_text(self):
        """Everything needed to report a problem, gathered defensively.

        Each probe is independent: one failing must not remove the others from
        the report, which is exactly what a single surrounding ``try`` did - a
        failure in the display probe silently dropped the auto-startup line too.
        """
        lines = []

        for probe in (
            self._runtime_lines,
            self._mixer_lines,
            self._display_lines,
            self._startup_lines,
        ):
            try:
                lines.extend(probe())
            except Exception as error:
                lines.append(f"• {probe.__name__.strip('_').replace('_', ' ')}: "
                             f"unavailable ({type(error).__name__}: {error})")

        lines.append(f"• Log file: {log_file()}")
        return "\n".join(lines)

    @staticmethod
    def _runtime_lines():
        from utils.app_paths import executable_path, is_frozen
        from utils.enhanced_version_manager import EnhancedVersionManager

        version = EnhancedVersionManager.read_installed_version()
        suffix = "" if is_frozen() else " (from source)"
        lines = [
            f"• Hushmix: {version or 'unknown'}{suffix}",
            f"• Python: {platform.python_version()}",
            f"• Executable: {sys.executable}",
        ]
        if not is_frozen() and not os.path.exists(executable_path()):
            lines.append("• Build: Hushmix.exe not present (development checkout)")
        return lines

    def _mixer_lines(self):
        if self.app is None:
            return []

        connected = bool(self.app.serial_controller.get_connection_status())
        return [
            f"• Mixer: {'connected' if connected else 'disconnected'}",
            f"• Profile: {self.app.settings_manager.get_setting('current_profile')}",
            f"• Update source: {self.app.version_manager.current_source}",
        ]

    def _display_lines(self):
        """Screen layout - a "the window looks wrong" report needs this."""
        if self.app is None:
            return []

        report = self.app.window_manager.scaling_report()
        lines = [
            "• Display: monitor scale {:.2f}, widget scale {:.2f}, "
            "window scale {:.2f}".format(
                report["monitor_scale"], report["widget_scale"], report["window_scale"]
            ),
            f"• Window: {report['window']}",
        ]
        if report["content"]:
            lines.append(f"• Content wants: {report['content']}")
        return lines

    @staticmethod
    def _startup_lines():
        """Whether the Run-key entry matches the stored setting."""
        wants = bool(ConfigManager.load_settings().get("auto_startup"))
        registered = ConfigManager.is_auto_startup_enabled()
        if wants == registered:
            return [f"• Auto-startup: {'enabled' if registered else 'disabled'}"]
        return [
            f"• Auto-startup: setting says {wants}, Windows registration says "
            f"{registered} (they disagree)"
        ]

    def _open_log(self):
        try:
            if os.path.exists(log_file()):
                os.startfile(log_file())
            else:
                os.startfile(os.path.dirname(log_file()))
        except Exception as error:
            logger.warning("Could not open the log location: %s", error)
