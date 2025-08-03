# Hushmix

A modern Windows application for controlling individual application volumes using hardware controls. Hushmix provides an intuitive interface to manage audio levels for specific applications, system master volume, and microphone.

## ✨ Features

- **Individual Application Volume Control** - Control volume for specific applications independently
- **Group Application Volume Control** - Control volume for specific applications in a group
- **System Audio Management** - Control system master volume and microphone levels
- **Hardware Integration** - Use physical controllers (knobs, slider and buttons) for volume adjustment
- **Profile System** - Save and switch between different audio configurations
- **Modern UI** - Clean, responsive interface with dark/light theme support
- **System Tray Integration** - Run in background with easy access from system tray
- **Auto-startup Option** - Configure to start automatically with Windows

## 🚀 Installation

### Option 1: Download from GitHub Releases (Recommended)

1. Go to the [Releases page](https://github.com/jennus17/Hushmix/releases)
2. Download the latest release for Windows
3. Extract the ZIP file to your desired location
4. Run `Hushmix.exe` to start the application

### Option 2: Build from Source

#### Prerequisites
- Python 3.7 or higher
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

## 📖 Usage

### Getting Started

1. **Connect Mixer** - Connect your mixer controller
2. **Launch Hushmix** - Start the application from the executable
3. **Configure Applications** - Enter application names in the fields (e.g., "chrome", "spotify")
4. **Adjust Volumes** - Use the mixer controller to adjust individual application volumes

### Special Commands

- **`master`** - Controls the system master volume
- **`system`** - Controls the system sounds
- **`current`** - Controls the currently focused application
- **`mic`** - Controls the default microphone volume

### Profiles

- **Save Configurations** - Create and save different audio profiles for different scenarios
- **Quick Switching** - Switch between profiles using the dropdown menu
- **Persistent Settings** - All settings are automatically saved and restored

### System Tray

- **Background Operation** - Minimize to system tray for background operation
- **Quick Access** - Right-click the tray icon for quick actions

## 🔧 Configuration

### Settings Window
Access settings through the gear icon (⚙️) to configure:
- Theme preferences (Dark/Light mode)
- Auto-startup settings
- Launch in the tray option
- Volume inversion options

### Button Settings
Configure hardware button behavior for each application slot:
- Mute/unmute functionality
- Custom button actions (in the future)


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.

## 📞 Support

If you encounter any issues or have questions:
1. Check the [Issues page](https://github.com/jennus17/Hushmix/issues) for existing solutions
2. Create a new issue with detailed information about your problem
3. Include system information and error messages when possible

---

**Made with ❤️ for those who want easy control of the Windows volume mixer** 
