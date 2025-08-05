import customtkinter as ctk


class VolumeManager:
    def __init__(self, app_instance):
        self.app = app_instance
    
    def toggle_mute(self, index):
        """Toggle mute/unmute and apply volume."""
        if index >= len(self.app.muted_state):
            print(f"Index {index} out of bounds for mute list.")
            return
    
        self.app.muted_state[index] = not self.app.muted_state[index]

        if index < len(self.app.current_mute_state):
            self.app.current_mute_state[index] = self.app.muted_state[index]
    
        if self.app.muted_state[index]:
            self.update_volume(index, 0)
        else:
            app_name = self.app.gui_components.entries[index].get() if index < len(self.app.gui_components.entries) else ""
            if app_name and app_name.lower() == "mic":
                mic_volume = self.app.audio_controller.get_microphone_volume()
                if mic_volume > 0:
                    self.update_volume(index, mic_volume)
                else:
                    self.update_volume(index, 50)
            elif index < len(self.app.previous_volumes) and self.app.previous_volumes[index] is not None:
                self.update_volume(index, self.app.previous_volumes[index])
            else:
                self.update_volume(index, 50)
        self.app.save_settings()

    def handle_volume_update(self, volumes):
        """Handle volume updates from serial controller."""
        if self.app.current_apps == []:
            self.app.current_apps = ["" for i in range(len(volumes))]
            self.app.root.after(20, self.app.gui_components.refresh_gui)
            return

        if not hasattr(self.app, "muted_state") or len(self.app.muted_state) != len(volumes):
            if hasattr(self.app, "current_mute_state") and len(self.app.current_mute_state) == len(volumes):
                self.app.muted_state = self.app.current_mute_state.copy()
            else:
                self.app.muted_state = [False] * len(volumes)

        for i, volume in enumerate(volumes):
            self.update_volume(i, int(volume))

    def update_volume(self, index, volume_level):
        """Update volume for a specific application."""
        volume_level = min(max(volume_level, 0), 100)
        volume_level = round(volume_level / 2) * 2

        if self.app.settings_manager.get_setting("invert_volumes"):
            volume_level = 100 - volume_level

        if index < len(self.app.muted_state) and self.app.muted_state[index]:
            volume_level = 0

        if index < len(self.app.gui_components.volume_labels):
            is_muted = (
                index < len(self.app.muted_state) and self.app.muted_state[index]
            )
            displayed_volume = 0 if is_muted else volume_level
            color = "red3" if is_muted else self.app.gui_components.volume_labels[index].default_text_color

            self.app.root.after(
                10,
                lambda l=self.app.gui_components.volume_labels[index]: l.configure(
                    text=f"{displayed_volume}%", text_color=color
                ),
            )

        if (
            index < len(self.app.current_apps)
            and volume_level != self.app.previous_volumes[index]
        ):
            app_name = self.app.gui_components.entries[index].get()
            if app_name:
                if app_name.lower() == "mic" and not self.app.muted_state[index] and self.app.previous_volumes[index] == 0:
                    mic_volume = self.app.audio_controller.get_microphone_volume()
                    if mic_volume > 0:
                        volume_level = mic_volume
                
                self.app.audio_controller.set_application_volume(app_name, volume_level)
                self.app.previous_volumes[index] = volume_level 