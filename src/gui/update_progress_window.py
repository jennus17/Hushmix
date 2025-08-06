import customtkinter as ctk
import threading
import gui.app as app
from utils.dpi_manager import DPIManager


class UpdateProgressWindow:
    def __init__(self, parent, update_info, version_manager):
        self.window = ctk.CTkToplevel(parent)
        self.window.tk.call("tk", "scaling", 1.0)
        self.window.withdraw()
        
        self.parent = parent
        self.update_info = update_info
        self.version_manager = version_manager
        
        self.setup_window()
        self.window.transient(parent)
        
        self.accent_color = app.get_windows_accent_color()
        self.accent_hover = app.darken_color(self.accent_color, 0.2)
        self.dpi_manager = DPIManager()
        self.normal_font_size = 14
        
        self.setup_gui()
        self.window.after(50, lambda: (self.window.deiconify(), self.center_window(parent)))
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        
    def setup_window(self):
        self.window.title("Updating Hushmix")
        self.window.resizable(False, False)
        self.window.geometry("400x200")
        self.window.transient(self.parent)
        self.window.grab_release()
        
        from utils.icon_manager import IconManager
        ico_path = IconManager.get_ico_file()
        if ico_path:
            try:
                self.window.after(200, lambda: self.window.iconbitmap(ico_path))
            except Exception as e:
                print(f"Error setting icon: {e}")
    
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
        y = center_y - window_height // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def setup_gui(self):
        self.frame = ctk.CTkFrame(self.window, corner_radius=0, border_width=0)
        self.frame.pack(expand=True, fill="both")
        
        self.dpi_manager.adjust_dpi_scaling_delayed(self.window, "update progress window")
        
        self.status_label = ctk.CTkLabel(
            self.frame, 
            text="Preparing to download update...", 
            font=("Segoe UI", self.normal_font_size)
        )
        self.status_label.pack(pady=(20, 10), padx=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.frame)
        self.progress_bar.pack(pady=(10, 20), padx=20, fill="x")
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(
            self.frame, 
            text="0%", 
            font=("Segoe UI", 12)
        )
        self.progress_label.pack(pady=(0, 10))
        
        self.cancel_button = ctk.CTkButton(
            self.frame,
            text="Cancel",
            command=self.cancel_update,
            fg_color="red",
            hover_color="#8B0000",
            font=("Segoe UI", self.normal_font_size),
            corner_radius=10,
        )
        self.cancel_button.pack(pady=(10, 20))
        
        self.cancelled = False
        self.start_download()


    
    def start_download(self):
        self.download_thread = threading.Thread(target=self.download_update, daemon=True)
        self.download_thread.start()
    
    def download_update(self):
        """Download the update with progress tracking."""
        try:
            self.update_status("Downloading update...")
            
            def progress_callback(progress):
                if not self.cancelled:
                    self.window.after(0, lambda: self.update_progress(progress))
            
            def cancellation_check():
                return self.cancelled
            
            download_path = self.version_manager.download_update(
                self.update_info['download_url'], 
                progress_callback,
                cancellation_check
            )
            
            if self.cancelled:
                return
            
            if download_path:
                self.update_status("Verifying download...")
                self.update_progress(100)
                
                if self.cancelled:
                    return
                
                if self.version_manager.verify_download(download_path, self.update_info.get('checksum')):
                    if self.cancelled:
                        return
                    
                    self.update_status("Installing update...")
                    self.install_update(download_path)
                else:
                    self.update_status("Download verification failed!")
                    self.show_error("The downloaded file could not be verified. Please try again.")
            else:
                if not self.cancelled:
                    self.update_status("Download failed!")
                    self.show_error("Failed to download the update. Please check your internet connection.")
                
        except Exception as e:
            if not self.cancelled: 
                self.update_status("Update failed!")
                self.show_error(f"An error occurred during the update: {str(e)}")
    
    def install_update(self, download_path):
        """Install the update."""
        try:
            if self.cancelled:
                return
                
            self.update_status("Opening download page...")
            self.version_manager.install_update(download_path)
        except Exception as e:
            if not self.cancelled:
                self.update_status("Update process failed!")
                self.show_error(f"Failed to complete the update process: {str(e)}\n\nPlease download and install the update manually from the GitHub releases page.")
                import webbrowser
                release_page = self.update_info.get('release_page', "https://github.com/jennus17/Hushmix/releases/latest")
                webbrowser.open(release_page)
    
    def update_status(self, status):
        """Update the status label."""
        self.window.after(0, lambda: self.status_label.configure(text=status))
    
    def update_progress(self, progress):
        """Update the progress bar."""
        self.window.after(0, lambda: self.progress_bar.set(progress / 100))
        self.window.after(0, lambda: self.progress_label.configure(text=f"{int(progress)}%"))
    
    def show_error(self, message):
        """Show an error message."""
        self.cancel_button.configure(text="Close", command=self.close)
        self.status_label.configure(text=message)
    
    def cancel_update(self):
        """Cancel the update process."""
        self.cancelled = True
        self.update_status("Cancelling update...")
        self.cancel_button.configure(state="disabled")
        
        self.window.after(1000, self.handle_cancellation_complete)
    
    def handle_cancellation_complete(self):
        """Handle the completion of cancellation."""
        self.update_status("Update cancelled")
        self.cancel_button.configure(text="Close", command=self.close, state="normal")
    
    def close(self):
        """Close the progress window."""
        self.window.destroy() 