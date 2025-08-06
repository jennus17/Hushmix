import customtkinter as ctk
from gui.app import HushmixApp
from utils.config_manager import ConfigManager
import ctypes
from ctypes.wintypes import RECT, POINT
import win32event
import win32api
import sys
import tkinter.messagebox as messagebox
import time


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


_mutex_handle = None

def check_single_instance():
    """Check if another instance of the application is already running."""
    global _mutex_handle
    mutex_name = "Hushmix_SingleInstance_Mutex"
    
    try:
        print(f"Attempting to create mutex: {mutex_name}")
        
        _mutex_handle = win32event.CreateMutex(None, False, mutex_name)
        
        last_error = win32api.GetLastError()
        print(f"Last error after mutex creation: {last_error}")
        
        if last_error == 183:
            print("Another instance of Hushmix is already running!")
            return False
        
        print("Single instance check passed - no other instances found")
        return True
        
    except Exception as e:
        print(f"Error with mutex approach: {e}")
    
    try:
        import os
        import tempfile
        
        lock_file = os.path.join(tempfile.gettempdir(), "hushmix_single_instance.lock")
        print(f"Trying file-based lock: {lock_file}")
        
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    pid = int(f.read().strip())
                
                import psutil
                if psutil.pid_exists(pid):
                    print(f"Another instance (PID: {pid}) is already running!")
                    return False
                else:
                    os.remove(lock_file)
                    print("Removed stale lock file")
            except:
                os.remove(lock_file)
                print("Removed corrupted lock file")
        
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        print("File-based lock created successfully")
        return True
        
    except Exception as file_error:
        print(f"Error with file-based approach: {file_error}")
        return True

def check_single_instance_simple():
    try:
        import os
        import tempfile
        
        lock_file = os.path.join(tempfile.gettempdir(), "hushmix_single_instance.lock")
        
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    pid_str = f.read().strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        
                        import psutil
                        if not psutil.pid_exists(pid):
                            os.remove(lock_file)
                            print(f"Removed stale lock file from dead process {pid}")
                        else:
                            if pid == os.getpid():
                                print("Lock file belongs to this process - continuing")
                                return True
                            else:
                                print(f"Process {pid} is still running - another instance detected!")
                                return False
                    else:
                        os.remove(lock_file)
                        print("Removed lock file with invalid PID")
            except Exception as e:
                os.remove(lock_file)
                print(f"Removed corrupted lock file: {e}")
        
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except OSError as e:
            if e.errno == 17:  # File exists
                try:
                    with open(lock_file, 'r') as f:
                        pid_str = f.read().strip()
                        if pid_str.isdigit() and int(pid_str) == os.getpid():
                            print("Lock file belongs to this process - continuing")
                            return True
                except:
                    pass
                print("Lock file already exists - another instance is running!")
                return False
            else:
                print(f"Unexpected error: {e}")
                return True
        
    except Exception as e:
        print(f"Error in simple approach: {e}")
        return True


def cleanup_mutex():
    """Clean up the mutex handle and lock file when the application exits."""
    global _mutex_handle
    
    if _mutex_handle:
        try:
            win32api.CloseHandle(_mutex_handle)
            print("Mutex handle cleaned up")
        except Exception as e:
            print(f"Error cleaning up mutex: {e}")
    
    try:
        import os
        import tempfile
        
        lock_file = os.path.join(tempfile.gettempdir(), "hushmix_single_instance.lock")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    pid_str = f.read().strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid == os.getpid():
                            os.remove(lock_file)
                            print("Lock file cleaned up")
            except Exception as e:
                print(f"Error reading lock file during cleanup: {e}")
                try:
                    os.remove(lock_file)
                    print("Removed corrupted lock file during cleanup")
                except:
                    pass
    except Exception as e:
        print(f"Error cleaning up lock file: {e}")

def main():
    if not check_single_instance_simple():
        try:
            messagebox.showerror("Hushmix", "Hushmix is already running!\n\nPlease close the existing instance before opening a new one.")
        except:
            print("ERROR: Hushmix is already running! Please close the existing instance before opening a new one.")
        sys.exit(1)
    
    time.sleep(0.1)
    
    settings = ConfigManager.load_settings()
    dark_mode = settings.get("dark_mode", True)
    
    if dark_mode:
        ctk.set_appearance_mode("dark")
    else:
        ctk.set_appearance_mode("light")
    
    root = ctk.CTk()
    
    root.withdraw()
    
    saved_x = settings.get("window_x")
    saved_y = settings.get("window_y")
    
    root.update_idletasks()
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
    
    def show_window():
        if not app.settings_manager.get_setting("launch_in_tray"):
            root.deiconify()
            root.lift()
            root.attributes('-topmost', True)
            root.after_idle(lambda: root.attributes('-topmost', False))
            root.focus_force()
    
    root.after_idle(lambda: root.after(10, show_window))
    
    import atexit
    atexit.register(cleanup_mutex)
    
    root.mainloop()


if __name__ == "__main__":
    main()
