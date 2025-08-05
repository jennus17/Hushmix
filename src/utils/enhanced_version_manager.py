import os
import requests
import pefile
import sys
import threading
import time
import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse
import subprocess
import tempfile
import shutil
from gui.version_window import VersionWindow
from gui.update_progress_window import UpdateProgressWindow


class EnhancedVersionManager:
    def __init__(self, parent, settings_manager):
        self.root = parent
        self.settings_manager = settings_manager
        
        self.update_sources = {
            'github': {
                'api_url': 'https://api.github.com/repos/jennus17/Hushmix/releases/latest',
                'download_base': 'https://github.com/jennus17/Hushmix/releases/download',
                'release_page': 'https://github.com/jennus17/Hushmix/releases/latest'
            },
            'custom_server': {
                'api_url': 'https://your-update-server.com/api/version',
                'download_base': 'https://your-update-server.com/downloads',
                'release_page': 'https://your-update-server.com/releases'
            }
        }
        
        self.current_source = self.settings_manager.get_setting('update_source', 'github')
        self.check_interval = self.settings_manager.get_setting('update_check_interval', 1800)
        self.auto_check_enabled = self.settings_manager.get_setting('auto_check_updates', True)
        self.download_path = None
        
        self.start_version_check_thread(parent)

    def start_version_check_thread(self, parent):
        """Start version checking thread."""
        thread = threading.Thread(
            target=self.check_for_updates, args=(parent,), daemon=True
        )
        thread.start()

    def get_current_version_from_exe(self):
        """Get the current version of the executable from its properties."""
        try:
            if getattr(sys, "frozen", False):
                exe_path = os.path.join(
                    os.path.dirname(sys.executable), "Hushmix.exe"
                )
            else:
                script_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                exe_path = os.path.join(script_dir, "Hushmix.exe")

            if not os.path.exists(exe_path):
                print(f"Executable not found at: {exe_path}")
                return None

            pe = pefile.PE(exe_path)

            for fileinfo in pe.FileInfo:
                for entry in fileinfo:
                    if entry.Key == b"StringFileInfo":
                        for st in entry.StringTable:
                            if b"ProductVersion" in st.entries:
                                product_version = st.entries[b"ProductVersion"].decode("utf-8")
                                return "v" + product_version
        except Exception as e:
            print(f"Error reading version from executable: {e}")
            return None

    def get_update_info(self, source='github'):
        """Get update information from the specified source."""
        source_config = self.update_sources.get(source)
        if not source_config:
            raise ValueError(f"Unknown update source: {source}")

        try:
            response = requests.get(source_config['api_url'], timeout=10)
            response.raise_for_status()
            
            if source == 'github':
                return self._parse_github_response(response.json())
            elif source == 'custom_server':
                return self._parse_custom_response(response.json())
                
        except requests.RequestException as e:
            print(f"Error checking for updates from {source}: {e}")
            return None

    def _parse_github_response(self, data):
        """Parse GitHub API response."""
        return {
            'version': data['tag_name'],
            'download_url': f"{self.update_sources['github']['download_base']}/{data['tag_name']}/Hushmix.exe",
            'release_notes': data.get('body', ''),
            'published_at': data.get('published_at', ''),
            'size': None
        }

    def _parse_custom_response(self, data):
        """Parse custom server response."""
        return {
            'version': data.get('version'),
            'download_url': data.get('download_url'),
            'release_notes': data.get('release_notes', ''),
            'published_at': data.get('published_at', ''),
            'size': data.get('size'),
            'checksum': data.get('checksum')
        }

    def check_for_updates(self, parent):
        """Check if a new version is available."""
        current_version = self.get_current_version_from_exe()
        if current_version is None:
            return

        while self.auto_check_enabled:
            try:
                skip_version = self.settings_manager.get_setting('skip_version')
                if skip_version and skip_version == current_version:
                    time.sleep(self.check_interval)
                    continue
                
                update_info = self.get_update_info(self.current_source)
                if update_info and update_info['version'] != current_version:
                    print(f"Current version: {current_version}, Latest version: {update_info['version']}")
                    self.restore_parent_window(parent)
                    self.show_update_dialog(parent, update_info)
                    break
                
                self.settings_manager.set_setting('last_update_check', time.time())
                    
            except Exception as e:
                print(f"Error during update check: {e}")

            time.sleep(self.check_interval)

    def show_update_dialog(self, parent, update_info):
        """Show update dialog with enhanced options."""
        VersionWindow(update_info['version'], parent, update_info, self, self.settings_manager)

    def download_update(self, download_url, progress_callback=None):
        """Download update with progress tracking."""
        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.exe') as temp_file:
                self.download_path = temp_file.name
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_callback(progress)
                            
            return self.download_path
            
        except Exception as e:
            print(f"Error downloading update: {e}")
            if self.download_path and os.path.exists(self.download_path):
                os.unlink(self.download_path)
            return None

    def verify_download(self, file_path, expected_checksum=None):
        """Verify downloaded file integrity."""
        if not expected_checksum:
            return True
            
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            return file_hash == expected_checksum
        except Exception as e:
            print(f"Error verifying download: {e}")
            return False

    def install_update(self, installer_path):
        """Install the update."""
        try:
            current_exe_dir = os.path.dirname(sys.executable)
            current_exe_name = os.path.basename(sys.executable)
            
            batch_content = f'''@echo off
echo Updating Hushmix...

REM Kill any running instances of the application
taskkill /f /im "{current_exe_name}" 2>nul

REM Wait for processes to close completely
timeout /t 1 /nobreak > nul

REM Double-check no processes are running
tasklist /fi "imagename eq {current_exe_name}" 2>nul | find /i "{current_exe_name}" >nul
if not errorlevel 1 (
    echo Waiting for processes to close...
    timeout /t 1 /nobreak > nul
    taskkill /f /im "{current_exe_name}" 2>nul
    timeout /t 1 /nobreak > nul
)

REM Backup the old executable
if exist "{sys.executable}.backup" del "{sys.executable}.backup"
copy "{sys.executable}" "{sys.executable}.backup"

REM Replace with new executable
copy "{installer_path}" "{sys.executable}" /Y

REM Wait for file to be fully written and verify
timeout /t 1 /nobreak > nul

REM Verify the new executable exists and is accessible
if exist "{sys.executable}" (
    echo Update successful! Starting new version...
    
    REM Start the new version immediately
    start "" "{sys.executable}"
    
    REM Clean up after successful start
    timeout /t 1 /nobreak > nul
    del "{installer_path}"
    del "%~f0"
    
    REM Remove backup after successful start
    timeout /t 1 /nobreak > nul
    if exist "{sys.executable}.backup" del "{sys.executable}.backup"
) else (
    echo Update failed! Restoring backup...
    copy "{sys.executable}.backup" "{sys.executable}" /Y
    timeout /t 1 /nobreak > nul
    start "" "{sys.executable}"
    del "{installer_path}"
    del "%~f0"
)
'''
            
            batch_path = os.path.join(tempfile.gettempdir(), 'hushmix_update.bat')
            with open(batch_path, 'w') as f:
                f.write(batch_content)
            
            subprocess.Popen(['cmd', '/c', batch_path], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            
            os._exit(0)
            
        except Exception as e:
            print(f"Error installing update: {e}")
            return False

    def restore_parent_window(self, parent):
        """Restore parent window if minimized."""
        if not parent.winfo_viewable():
            parent.deiconify()
            parent.lift()
            parent.focus_force()

    def set_check_interval(self, seconds):
        """Set the update check interval."""
        self.check_interval = seconds
        self.settings_manager.set_setting('update_check_interval', seconds)

    def set_auto_check(self, enabled):
        """Enable or disable automatic update checking."""
        self.auto_check_enabled = enabled
        self.settings_manager.set_setting('auto_check_updates', enabled)

    def set_update_source(self, source):
        """Set the update source."""
        if source in self.update_sources:
            self.current_source = source
            self.settings_manager.set_setting('update_source', source)
        else:
            raise ValueError(f"Unknown update source: {source}")

    def skip_version(self, version):
        """Skip a specific version."""
        self.settings_manager.set_setting('skip_version', version) 