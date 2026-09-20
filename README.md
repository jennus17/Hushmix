# Hushmix

A modern Windows application for controlling individual application volumes using hardware controls. Hushmix provides an intuitive interface to manage audio levels for specific applications, system master volume, and microphone.

## ✨ Features

- **Individual Application Volume Control** - Control volume for specific applications independently
- **Group Application Volume Control** - Control volume for specific applications in a group
- **System Audio Management** - Control system master volume and microphone levels
- **Hardware Integration** - Use physical controllers (knobs, slider and buttons) for volume adjustment
- **Profile System** - Save and switch between different audio configurations, add or remove profiles from the main window
- **Button Actions** - Mute, launch an application, send a keyboard shortcut or a media key from each hardware button
- **Modern UI** - Clean, responsive interface with dark/light theme support and live Windows accent colour
- **System Tray Integration** - Run in background with easy access from system tray
- **Auto-startup Option** - Configure to start automatically with Windows
- **Automatic Updates** - Checks GitHub releases, verifies and installs new versions
- **Diagnostics** - Rotating log file and a built-in diagnostics panel in the help window

## 🚀 Installation

### Option 1: Download from GitHub Releases (Recommended)

1. Go to the [Releases page](https://github.com/jennus17/Hushmix/releases)
2. Download the latest release for Windows
3. Extract the ZIP file to your desired location
4. Run `Hushmix.exe` to start the application

### Option 2: Build from Source

#### Prerequisites
- Python 3.10 or higher (64-bit)
- Git

#### Build Steps
1. Clone this repository:
   ```bash
   git clone https://github.com/jennus17/Hushmix.git
   cd Hushmix
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python src/main.py
   ```

### Option 3: Build Hushmix.exe

```bash
python -m venv build/.venv
build/.venv/Scripts/python -m pip install -r requirements.txt pyinstaller

python build_tools/build.py --clean
```

The result is `dist/Hushmix.exe` (single file, no console window, with the
application icon and a version resource generated from `src/version.py`), plus
`dist/Hushmix.exe.sha256`.

Fix a release version by editing `__version__` in `src/version.py`; the version
resource, the update checker and the built binary all read it from there.

### Publishing a release

1. Bump `__version__` in `src/version.py` and run `python build_tools/build.py`.
2. Create a GitHub release tagged `v<version>` and upload **both**
   `dist/Hushmix.exe` and `dist/Hushmix.exe.sha256`.
3. Verify what you published:

   ```bash
   python build_tools/verify_release.py v0.5.0 --from v0.4.6
   ```

   That fetches the release through the same code path the application uses:
   it confirms both assets are attached, downloads the published executable and
   compares its SHA-256 with the published checksum, checks the checksum file's
   format, and (with `--from`) that the release really is newer than the version
   it should replace. Exit code 0 means an installed Hushmix will verify the
   download too.

Uploading the checksum matters: without it the updater can only confirm that a
downloaded file looks like a Windows executable, so a truncated or substituted
download would pass. With it, the download is verified byte for byte.

If you prefer not to upload the file, paste the hash into the release notes
instead - the updater reads a `SHA256: <hash>` line from there:

```bash
python build_tools/make_checksum.py    # prints both the file and that line
```

### Smart App Control

Windows Smart App Control blocks unsigned executables. On a machine where it is
enabled you may see "This command cannot be run due to the error: an Application
Control policy blocked this file", and Code Integrity logs *"did not meet the
Enterprise signing level requirements"* for `dist\Hushmix.exe`. That is a machine
policy, not a fault in the build: `Hushmix.exe` is unsigned. Distributing the
application therefore requires signing it with a code-signing certificate;
running from source (`python src/main.py`) is unaffected.

## 📖 Usage

### Getting Started

1. **Connect Mixer** - Connect your mixer controller (the status banner disappears once it is detected)
2. **Launch Hushmix** - Start the application from the executable
3. **Configure Applications** - Enter application names in the fields (e.g., "chrome", "spotify")
4. **Adjust Volumes** - Use the mixer controller to adjust individual application volumes

### Special Commands

- **`master`** - Controls the system master volume
- **`system`** - Controls the system sounds
- **`current`** - Controls the currently focused application
- **`mic`** - Controls the default microphone volume

### Finding application names

Right-click an application field to pick from the processes that are **currently
playing audio**, or use the process name from Task Manager (without `.exe`). The
list is gathered in the background, so the menu opens immediately.

### Profiles

- **Save Configurations** - Create and save different audio profiles for different scenarios
- **Quick Switching** - Switch between profiles using the dropdown menu
- **Add / Remove** - Use the `＋` and `－` buttons next to the dropdown
- **Persistent Settings** - All settings are automatically saved and restored

### System Tray

- **Background Operation** - Minimize to system tray for background operation
- **Quick Access** - Right-click the tray icon for Restore / Settings / Exit

## 🔧 Configuration

### Settings Window
Access settings through the gear icon (⚙️) to configure:
- Theme preferences (Dark/Light mode)
- Auto-startup settings
- Launch in the tray option
- Volume inversion options
- Update checking

### Button Settings
Configure hardware button behaviour for each application slot:
- Mute/unmute functionality
- Launch an application
- Keyboard shortcut
- Media control (play/pause, next, previous)
- Trigger mode per action: Click, Double Click or Hold

## 📁 Project structure

```
src/
├── main.py                       # Entry point, single-instance guard, startup
├── version.py                    # Application version (update checking)
├── controllers/                  # Audio, serial and action controllers
│   ├── audio_controller.py       # Core Audio (master, mic, per-app sessions)
│   ├── serial_controller.py      # Mixer protocol, filtering, reconnection
│   ├── volume_manager.py         # Slider packet -> application volume
│   ├── button_actions.py         # Mute / launch / shortcut / media keys
│   └── profile_manager.py        # Profile switching and persistence
├── gui/                          # Windows and widgets
│   ├── app.py                    # Application object that wires everything
│   ├── base_window.py            # Shared popup window behaviour
│   ├── gui_components.py         # Main window contents
│   ├── window_manager.py         # Tray icon, DPI, window position
│   ├── settings_window.py        # Settings dialog
│   ├── buttonSettings_window.py  # Per-button settings dialog
│   ├── shortcut_recorder.py      # Keyboard shortcut recorder widget
│   ├── help_window.py            # Help and diagnostics
│   ├── version_window.py         # Update available dialog
│   └── update_progress_window.py # Download progress dialog
└── utils/                        # Infrastructure helpers
    ├── config_manager.py         # Settings schema and persistence
    ├── settings_manager.py       # In-memory settings during a session
    ├── enhanced_version_manager.py # Update check / download / install
    ├── atomic_io.py              # Crash-safe JSON writes
    ├── app_paths.py              # Absolute paths (works when frozen)
    ├── logging_setup.py          # Rotating log file
    ├── log_path.py               # Where the log goes, and fallbacks
    ├── deferred_actions.py       # Thread-safe hand-off to the Tk thread
    ├── signal_filter.py          # Mixer reading -> stable slider value
    ├── icon_manager.py           # Icon lookup and generation
    ├── png2ico.py                # Dependency-free PNG -> ICO converter
    ├── version_utils.py          # Version parsing and comparison
    └── win_utils.py              # Monitors, DPI, single-instance guard
```
## 🧪 Development

```bash
# Byte-compile every module
python -m compileall src

# Library-level smoke tests (no GUI required)
python tests/test_core.py

# GUI wiring integration test (stubs out customtkinter/audio/serial)
python tests/test_gui_pipeline.py

# Live GUI tests - need an interactive Windows session and the real packages.
# Run them one at a time: several of them open the audio device and the serial
# port, and they contend when started together.
python tests/smoke_live_gui.py     # drives the whole application
python tests/smoke_fixes.py        # regression checks for reported GUI bugs

# Cross-module consistency checks (renames that miss a call site)
python tests/check_consistency.py
```

### Versioning

`src/version.py` is the single source of truth. Bump `__version__` there, then
build; `build_tools/make_version_info.py` writes the matching Windows version
resource so the update checker compares like with like.

### Logs

Settings and logs live in `%APPDATA%\Hushmix\`:

- `settings.json` - all profiles and global settings
- `hushmix.log` - rotating log (512 KB × 3) with warnings and errors

### Regenerating the icon

The application ships `src/utils/assets/volume_icon.ico`. If it is missing it is
rebuilt from `volume_icon.png` at startup; to rebuild it manually:

```bash
cd src/utils
python png2ico.py assets/volume_icon.png assets/volume_icon.ico
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.

## 📞 Support

If you encounter any issues or have questions:
1. Check the [Issues page](https://github.com/jennus17/Hushmix/issues) for existing solutions
2. Create a new issue with detailed information about your problem
3. Include the diagnostics shown in the help window (ⓘ) and `hushmix.log`

---

**Made with ❤️ for those who want easy control of the Windows volume mixer**
