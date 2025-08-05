import subprocess
import os
import pyautogui
import time
import customtkinter as ctk


class ButtonActions:
    def __init__(self, app_instance):
        self.app = app_instance
    
    def launch_application(self, index):
        """Launch the application specified for the given button index."""
        try:
            app_path = self.app.app_launch_paths[index].get()
            if app_path and os.path.exists(app_path):
                subprocess.Popen([app_path], shell=True)
                print(f"Launched application: {app_path}")
            else:
                print(f"Application path not found: {app_path}")
        except Exception as e:
            print(f"Error launching application: {e}")

    def send_keyboard_shortcut(self, index):
        """Send keyboard shortcut for the given button index."""
        try:
            if index >= len(self.app.keyboard_shortcuts):
                return
            
            shortcut = self.app.keyboard_shortcuts[index].get()
            if not shortcut:
                return
            
            keys = shortcut.split('+')
            key_mapping = {
                'Ctrl': 'ctrl',
                'Control': 'ctrl',
                'Shift': 'shift',
                'Alt': 'alt',
                'Win': 'win',
                'Windows': 'win',
                'Enter': 'enter',
                'Return': 'enter',
                'Tab': 'tab',
                'Space': 'space',
                'Escape': 'esc',
                'Esc': 'esc',
                'Backspace': 'backspace',
                'Delete': 'delete',
                'Del': 'delete',
                'Insert': 'insert',
                'Home': 'home',
                'End': 'end',
                'PageUp': 'pageup',
                'PageDown': 'pagedown',
                'Up': 'up',
                'Down': 'down',
                'Left': 'left',
                'Right': 'right',
                'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4',
                'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8',
                'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12',
                'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g', 'h': 'h', 'i': 'i', 'j': 'j',
                'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n', 'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't',
                'u': 'u', 'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z',
                '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
            }
            
            pyautogui_keys = []
            for key in keys:
                mapped_key = key_mapping.get(key, key.lower())
                pyautogui_keys.append(mapped_key)
            
            if len(pyautogui_keys) > 1:
                pyautogui.hotkey(*pyautogui_keys)
            else:
                pyautogui.press(pyautogui_keys[0])
            
            print(f"Sent keyboard shortcut: {shortcut}")
            
        except Exception as e:
            print(f"Error sending keyboard shortcut: {e}")

    def send_media_control(self, index):
        """Send media control command for the given button index."""
        try:
            if index >= len(self.app.media_control_actions):
                return
            
            action = self.app.media_control_actions[index].get()
            if not action:
                return
            
            media_key_mapping = {
                'Play/Pause': 'playpause',
                'Next Track': 'nexttrack',
                'Previous Track': 'prevtrack'
            }
            
            media_key = media_key_mapping.get(action)
            if media_key:
                pyautogui.press(media_key)
                print(f"Sent media control: {action}")
            else:
                print(f"Unknown media control action: {action}")
            
        except Exception as e:
            print(f"Error sending media control: {e}")

    def handle_button_update(self, button_states):
        """Handle button states from serial controller."""
        button_states = [int(state) for state in button_states]
        num_buttons = len(button_states)
        num_apps = len(self.app.current_apps)
        BUTTON_VOLUME_OFFSET = 1
    
        if not hasattr(self.app, "last_button_states") or len(self.app.last_button_states) != num_buttons:
            self.app.last_button_states = [0] * num_buttons
    
        if not hasattr(self.app, "mute") or len(self.app.mute) != num_buttons:
            self.app.mute = [ctk.BooleanVar(value=True) for _ in range(num_buttons)]
    
        if not hasattr(self.app, "muted_state") or len(self.app.muted_state) != num_apps:
            if hasattr(self.app, "current_mute_state") and len(self.app.current_mute_state) == num_apps:
                self.app.muted_state = self.app.current_mute_state.copy()
            else:
                self.app.muted_state = [False] * num_apps
    
        for i, (current, previous) in enumerate(zip(button_states, self.app.last_button_states)):
            if current > 0 and previous == 0:
                volume_index = i + BUTTON_VOLUME_OFFSET
                
                if i < len(self.app.mute) and self.app.mute[i].get() and volume_index < len(self.app.muted_state):
                    mute_mode = "Click" 
                    if i < len(self.app.mute_button_modes):
                        mute_mode = self.app.mute_button_modes[i].get()
                    
                    should_trigger_mute = False
                    if mute_mode == "Click" and current == 1:
                        should_trigger_mute = True
                    elif mute_mode == "Double Click" and current == 3:
                        should_trigger_mute = True
                    elif mute_mode == "Hold" and current == 2:
                        should_trigger_mute = True
                    
                    if should_trigger_mute:
                        self.app.toggle_mute(volume_index)
                
                if (i < len(self.app.app_launch_enabled) and 
                    self.app.app_launch_enabled[i].get() and 
                    i < len(self.app.app_launch_paths) and 
                    self.app.app_launch_paths[i].get()):
                    app_mode = "Click"
                    if i < len(self.app.app_button_modes):
                        app_mode = self.app.app_button_modes[i].get()
                    
                    should_trigger_app = False
                    if app_mode == "Click" and current == 1:
                        should_trigger_app = True
                    elif app_mode == "Double Click" and current == 3:
                        should_trigger_app = True
                    elif app_mode == "Hold" and current == 2:
                        should_trigger_app = True
                    
                    if should_trigger_app:
                        self.launch_application(i)
                
                if (i < len(self.app.keyboard_shortcut_enabled) and 
                    self.app.keyboard_shortcut_enabled[i].get() and 
                    i < len(self.app.keyboard_shortcuts) and 
                    self.app.keyboard_shortcuts[i].get()):
                    shortcut_mode = "Click"
                    if i < len(self.app.shortcut_button_modes):
                        shortcut_mode = self.app.shortcut_button_modes[i].get()
                    
                    should_trigger_shortcut = False
                    if shortcut_mode == "Click" and current == 1:
                        should_trigger_shortcut = True
                    elif shortcut_mode == "Double Click" and current == 3:
                        should_trigger_shortcut = True
                    elif shortcut_mode == "Hold" and current == 2:
                        should_trigger_shortcut = True
                    
                    if should_trigger_shortcut:
                        self.send_keyboard_shortcut(i)
                
                if (i < len(self.app.media_control_enabled) and 
                    self.app.media_control_enabled[i].get() and 
                    i < len(self.app.media_control_actions) and 
                    self.app.media_control_actions[i].get()):
                    media_mode = "Click"
                    if i < len(self.app.media_control_button_modes):
                        media_mode = self.app.media_control_button_modes[i].get()
                    
                    should_trigger_media = False
                    if media_mode == "Click" and current == 1:
                        should_trigger_media = True
                    elif media_mode == "Double Click" and current == 3:
                        should_trigger_media = True
                    elif media_mode == "Hold" and current == 2:
                        should_trigger_media = True
                    
                    if should_trigger_media:
                        self.send_media_control(i)
    
        self.app.last_button_states = button_states 