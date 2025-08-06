import ctypes
import threading
from pystray import Icon, MenuItem, Menu
from PIL import Image
import customtkinter as ctk
from utils.icon_manager import IconManager


class WindowManager:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.icon = None
        self.last_position = None
        
        self.setup_window()
        self.setup_tray_icon()
        self.setup_window_position_tracking()
    
    def setup_window(self):
        """Setup main window properties."""
        self.root.title("Hushmix")
        self.root.resizable(False, False)
        
        self.root.configure(bg=self.get_theme_bg_color())

        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                myappid = "Hushmix"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                self.root.iconbitmap(default=ico_path)
                self.root.wm_iconbitmap(ico_path)
            except Exception as e:
                print(f"Error setting taskbar icon: {e}")
    
    def get_theme_bg_color(self):
        """Get the appropriate background color based on theme."""
        try:
            if self.app.settings_manager.get_setting("dark_mode", True):
                return "#2b2b2b"  # Dark theme background
            else:
                return "#f0f0f0"  # Light theme background
        except:
            return "#2b2b2b"  # Default to dark theme

    def setup_tray_icon(self):
        """Setup system tray icon."""
        menu = Menu(
            MenuItem("Restore", self.restore_window, default=True, visible=False),
            MenuItem("Exit", self.app.on_exit),
        )

        ico_path = IconManager.get_ico_file()

        try:
            icon_image = Image.open(ico_path)
            self.icon = Icon("Hushmix", icon=icon_image, menu=menu, title="Hushmix")
        except Exception as e:
            print(f"Error setting up tray icon: {e}")

        threading.Thread(target=self.icon.run_detached, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_close)

    def setup_window_position_tracking(self):
        """Setup window position tracking to save position when moved."""
        self.last_position = None
        self.root.bind("<Configure>", self.on_window_configure)
        
    def on_window_configure(self, event):
        """Handle window configuration changes (move, resize)."""
        if event.widget == self.root:
            current_position = (self.root.winfo_x(), self.root.winfo_y())
            
            if self.last_position != current_position:
                self.last_position = current_position
                self.save_window_position()
                
    def save_window_position(self):
        """Save current window position to settings."""
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            
            monitors = self.get_monitor_info()
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()
            
            target_monitor = self.find_monitor_for_position(x, y, monitors)
            
            if target_monitor is not None:
                self.app.settings_manager.set_setting("window_x", x)
                self.app.settings_manager.set_setting("window_y", y)
                
                self.app.settings_manager.save_to_config()
            else:
                print("Window position is not on any monitor, not saving position")
                
        except Exception as e:
            print(f"Error saving window position: {e}")
    
    def get_monitor_info(self):
        """Get information about all monitors."""
        import ctypes
        from ctypes.wintypes import RECT
        
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
    
    def is_position_on_monitor(self, x, y, monitor):
        """Check if a position is within a specific monitor bounds."""
        return (monitor['left'] <= x <= monitor['right'] and 
                monitor['top'] <= y <= monitor['bottom'])
    
    def find_monitor_for_position(self, x, y, monitors):
        """Find which monitor contains the given position."""
        for monitor in monitors:
            if self.is_position_on_monitor(x, y, monitor):
                return monitor
        return None

    def restore_window(self, icon=None, item=None):
        """Restore window from tray."""
        if not self.root.winfo_viewable():
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after_idle(lambda: self.root.attributes('-topmost', False))
            self.root.focus_force()

    def cleanup(self):
        """Cleanup tray icon."""
        if self.icon:
            self.icon.visible = False
            self.icon.stop() 