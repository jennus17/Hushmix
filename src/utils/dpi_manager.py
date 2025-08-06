import ctypes
import ctypes.wintypes


class DPIManager:
    """Manages DPI scaling for Tkinter windows across different monitors."""
    
    def __init__(self):
        self.last_monitor_dpi = None
    
    def get_monitor_dpi(self, x, y):
        """Get the DPI scaling factor for the monitor at the given position."""
        try:
            monitor_handle = ctypes.windll.user32.MonitorFromPoint(
                ctypes.wintypes.POINT(x, y),
                2  # MONITOR_DEFAULTTONEAREST
            )
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            ctypes.windll.shcore.GetDpiForMonitor(
                monitor_handle,
                0,  # MDT_EFFECTIVE_DPI
                ctypes.byref(dpi_x),
                ctypes.byref(dpi_y)
            )
            return dpi_x.value / 96.0
        except Exception as e:
            print(f"Error getting monitor DPI: {e}")
            return 1.0
    
    def adjust_dpi_scaling(self, window, x, y, window_name="window", refresh_callback=None):
        """Adjust DPI scaling when moving between monitors."""
        try:
            current_dpi = self.get_monitor_dpi(x, y)
            if self.last_monitor_dpi is not None and abs(current_dpi - self.last_monitor_dpi) > 0.01:
                print(f"DPI changed from {self.last_monitor_dpi:.2f} to {current_dpi:.2f}")
                window.tk.call("tk", "scaling", current_dpi)
                window.update_idletasks()
                if refresh_callback:
                    refresh_callback()
                print(f"{window_name} DPI scaling adjusted to {current_dpi:.2f}")
            self.last_monitor_dpi = current_dpi
        except Exception as e:
            print(f"Error adjusting DPI scaling for {window_name}: {e}")
    
    def initialize_dpi_scaling(self, window, window_name="window", refresh_callback=None, delay=100):
        """Initialize DPI scaling for the current monitor position."""
        try:
            window.after(delay, lambda: self._do_initialize_dpi_scaling(window, window_name, refresh_callback, delay))
        except Exception as e:
            print(f"Error scheduling DPI scaling initialization for {window_name}: {e}")
            window.tk.call("tk", "scaling", 1.0)
    
    def _do_initialize_dpi_scaling(self, window, window_name="window", refresh_callback=None, delay=100):
        """Actually perform the DPI scaling initialization."""
        try:
            x = window.winfo_x()
            y = window.winfo_y()
            if x == 0 and y == 0:
                window.after(delay, lambda: self._do_initialize_dpi_scaling(window, window_name, refresh_callback, delay))
                return
            
            current_dpi = self.get_monitor_dpi(x, y)
            window.tk.call("tk", "scaling", current_dpi)
            self.last_monitor_dpi = current_dpi
            if refresh_callback:
                refresh_callback()
            print(f"Initialized {window_name} DPI scaling to {current_dpi:.2f}")
        except Exception as e:
            print(f"Error initializing DPI scaling for {window_name}: {e}")
            window.tk.call("tk", "scaling", 1.0)
    
    def adjust_dpi_scaling_delayed(self, window, window_name="window", refresh_callback=None, delay=50):
        """Schedule DPI scaling adjustment with delay for popup windows."""
        try:
            window.after(delay, lambda: self._do_adjust_dpi_scaling_delayed(window, window_name, refresh_callback, delay))
        except Exception as e:
            print(f"Error scheduling DPI scaling adjustment for {window_name}: {e}")
            window.tk.call("tk", "scaling", 1.0)
    
    def _do_adjust_dpi_scaling_delayed(self, window, window_name="window", refresh_callback=None, delay=50):
        """Actually perform the delayed DPI scaling adjustment."""
        try:
            x = window.winfo_x()
            y = window.winfo_y()
            if x == 0 and y == 0:
                window.after(delay, lambda: self._do_adjust_dpi_scaling_delayed(window, window_name, refresh_callback, delay))
                return
            
            current_dpi = self.get_monitor_dpi(x, y)
            window.tk.call("tk", "scaling", current_dpi)
            if refresh_callback:
                refresh_callback()
            print(f"{window_name} DPI scaling set to {current_dpi:.2f}")
        except Exception as e:
            print(f"Error adjusting DPI scaling for {window_name}: {e}")
            window.tk.call("tk", "scaling", 1.0) 