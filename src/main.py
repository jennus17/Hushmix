import customtkinter as ctk
from gui.app import HushmixApp
from utils.config_manager import ConfigManager
import ctypes
from ctypes.wintypes import RECT, POINT


def get_monitor_info():
    """Get information about all monitors."""
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
    """Check if a position is within a specific monitor bounds."""
    return (monitor['left'] <= x <= monitor['right'] and 
            monitor['top'] <= y <= monitor['bottom'])


def find_monitor_for_position(x, y, monitors):
    """Find which monitor contains the given position."""
    for monitor in monitors:
        if is_position_on_monitor(x, y, monitor):
            return monitor
    return None


def validate_window_position(x, y, window_width, window_height, monitors):
    """Validate and adjust window position to ensure it's visible on a monitor."""
    target_monitor = find_monitor_for_position(x, y, monitors)
    
    if target_monitor is None:
        best_monitor = monitors[0]
        min_distance = float('inf')
        
        for monitor in monitors:
            monitor_center_x = monitor['left'] + monitor['width'] // 2
            monitor_center_y = monitor['top'] + monitor['height'] // 2
            
            distance = ((x - monitor_center_x) ** 2 + (y - monitor_center_y) ** 2) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                best_monitor = monitor
        
        x = best_monitor['left'] + (best_monitor['width'] - window_width) // 2
        y = best_monitor['top'] + (best_monitor['height'] - window_height) // 2
    else:
        x = max(target_monitor['left'], min(x, target_monitor['right'] - window_width))
        y = max(target_monitor['top'], min(y, target_monitor['bottom'] - window_height))
    
    return x, y


def main():
    settings = ConfigManager.load_settings()
    dark_mode = settings.get("dark_mode", True)
    
    if dark_mode:
        ctk.set_appearance_mode("dark")
    else:
        ctk.set_appearance_mode("light")
    
    root = ctk.CTk()  
    root.update_idletasks()

    saved_x = settings.get("window_x")
    saved_y = settings.get("window_y")
    
    window_width = root.winfo_width()
    window_height = root.winfo_height()
    
    monitors = get_monitor_info()
    
    if saved_x is not None and saved_y is not None:
        position_x, position_y = validate_window_position(saved_x, saved_y, window_width, window_height, monitors)
    else:
        primary_monitor = monitors[0]
        position_x = primary_monitor['left'] + (primary_monitor['width'] - window_width) // 2
        position_y = primary_monitor['top'] + (primary_monitor['height'] - window_height) // 2

    root.geometry(f"+{position_x}+{position_y}")

    app = HushmixApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
