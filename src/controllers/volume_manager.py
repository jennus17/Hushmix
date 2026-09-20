"""Maps hardware slider packets onto application volumes.

The previous implementation asked the Entry widgets for the application name
(``entries[index].get()``) on every volume change, which coupled the audio path
to the GUI and silently did nothing during a profile refresh, when the widgets
were destroyed and rebuilt.  It now reads the same authoritative
``app.current_apps`` list the rest of the app uses.
"""

from utils.logging_setup import get_logger

logger = get_logger("volume_manager")

DEFAULT_UNMUTE_LEVEL = 50
STEP = 2


class VolumeManager:
    def __init__(self, app_instance):
        self.app = app_instance
        #: Last logged lane resolution, so only changes are written to the log.
        self._last_resolution = None

    def _run_on_gui_thread(self, function, *args):
        """Schedule GUI work from the serial thread.

        Never call ``root.after`` directly here: Tk only accepts it from the
        thread running the event loop.
        """
        deferred = getattr(self.app, "deferred_actions", None)
        if deferred is not None:
            deferred.submit(function, *args)
        else:  # pragma: no cover - only when no event loop is configured
            function(*args)

    # ------------------------------------------------------------------ lookup

    def _target_name(self, index):
        """Application/special target configured for a slider."""
        if 0 <= index < len(self.app.current_apps):
            return self.app.current_apps[index] or ""
        return ""

    def _sync_mute_lists(self, count):
        """Keep the mute bookkeeping lists the same length as the hardware."""
        app = self.app

        if len(app.muted_state) != count:
            if len(app.current_mute_state) == count:
                app.muted_state = list(app.current_mute_state)
            else:
                app.muted_state = [False] * count

        if len(app.current_mute_state) != count:
            padded = list(app.current_mute_state) + [False] * count
            app.current_mute_state = padded[:count]

    # -------------------------------------------------------------------- mute

    def toggle_mute(self, index):
        """Toggle mute for a slider and apply the resulting volume."""
        app = self.app

        if index < 0 or index >= len(app.muted_state):
            logger.warning("Mute index %s is out of range", index)
            return

        app.muted_state[index] = not app.muted_state[index]

        if index < len(app.current_mute_state):
            app.current_mute_state[index] = app.muted_state[index]

        if app.muted_state[index]:
            self.update_volume(index, 0)
        else:
            self.update_volume(index, self._restore_level(index))

        app.save_settings()

    def _restore_level(self, index):
        """Level to apply when un-muting.

        Read back from the device rather than assuming a value, so un-muting
        never jumps to an arbitrary level: the master device and the microphone
        have their own readers, applications go through their audio session.
        """
        app = self.app
        target = self._target_name(index)
        lowered = target.lower()

        if lowered == "mic":
            mic_volume = app.audio_controller.get_microphone_volume()
            return mic_volume if mic_volume and mic_volume > 0 else DEFAULT_UNMUTE_LEVEL

        if lowered == "master":
            master_volume = app.audio_controller.get_master_volume()
            return master_volume if master_volume else DEFAULT_UNMUTE_LEVEL

        previous = app.previous_volumes[index] if index < len(app.previous_volumes) else None
        if previous:
            return previous

        if target:
            current = app.audio_controller.get_application_volume(target)
            if current:
                return current

        return DEFAULT_UNMUTE_LEVEL

    # ----------------------------------------------------------------- volumes

    def handle_volume_update(self, volumes):
        """Receive a smoothed slider packet from the serial controller."""
        app = self.app

        # Before any application is configured there is nothing to control yet.
        if not app.current_apps:
            app.current_apps = ["" for _ in volumes]
            self._run_on_gui_thread(app.gui_components.refresh_gui)
            return

        self._sync_mute_lists(len(volumes))

        # Resolve every lane against the same focused application, once per
        # packet.  This is what keeps a lane that names an application explicitly
        # in charge of it, so the ``current`` lane does not also write to it.
        focused = app.audio_controller.get_current_process_name()
        resolved, claimed = app.audio_controller.resolve_lanes(
            app.current_apps, focused
        )

        # Log only when the resolution *changes*: on every packet would flood the
        # file, but a change is exactly what explains "why did that lane stop
        # responding?", for instance when another lane claims the focused
        # application and this one is left with nothing to do.
        signature = (focused, tuple(resolved))
        if signature != self._last_resolution:
            self._last_resolution = signature
            logger.debug(
                "Lane resolution changed: focused=%r resolved=%s owned=%s",
                focused, resolved, claimed,
            )

        for index, volume in enumerate(volumes):
            self.update_volume(index, int(volume), resolved)

    def update_volume(self, index, volume_level, resolved=None):
        """Apply and display a volume for one channel.

        *resolved* is the per-lane resolution from
        :meth:`AudioController.resolve_lanes`; when omitted it is computed here,
        which is what the mute/un-mute path does.
        """
        app = self.app

        volume_level = max(0, min(100, int(round(volume_level))))
        volume_level = int(round(volume_level / STEP) * STEP)

        if app.settings_manager.get_setting("invert_volumes"):
            volume_level = 100 - volume_level

        is_muted = index < len(app.muted_state) and app.muted_state[index]
        if is_muted:
            volume_level = 0

        self._update_label(index, volume_level, is_muted)

        if index >= len(app.current_apps) or not app.current_apps[index]:
            return

        if resolved is None:
            resolved, _claimed = app.audio_controller.resolve_lanes(
                app.current_apps, app.audio_controller.get_current_process_name()
            )

        # An empty resolution means this lane controls nothing: either it is
        # blank, or it is the ``current`` lane and another lane owns the focused
        # application.
        if index < len(resolved) and not resolved[index]:
            return

        if index < len(app.previous_volumes) and volume_level == app.previous_volumes[index]:
            return

        target = app.current_apps[index]

        # Un-muting the microphone restores the device level rather than 0.
        if (
            target.lower() == "mic"
            and not is_muted
            and index < len(app.previous_volumes)
            and not app.previous_volumes[index]
        ):
            mic_volume = app.audio_controller.get_microphone_volume()
            if mic_volume and mic_volume > 0:
                volume_level = mic_volume

        app.audio_controller.set_application_volume(target, volume_level)

        if index < len(app.previous_volumes):
            app.previous_volumes[index] = volume_level

    def _update_label(self, index, volume_level, is_muted):
        """Reflect the level in the GUI without blocking the audio path.

        This runs on the serial reader thread, so the widget update has to go
        through the deferred-action queue.  Calling ``root.after`` directly from
        a worker thread raises ``RuntimeError: main thread is not in main loop``
        whenever the Tk event loop is busy, which killed the reader thread and
        silently stopped all further volume updates.
        """
        app = self.app
        if index >= len(app.gui_components.volume_labels):
            return

        label = app.gui_components.volume_labels[index]
        color = "red3" if is_muted else getattr(label, "default_text_color", None)

        def _apply():
            try:
                if label.winfo_exists():
                    label.configure(text=f"{volume_level}%", text_color=color)
            except Exception:
                pass

        deferred = getattr(app, "deferred_actions", None)
        if deferred is not None:
            deferred.submit(_apply)
        else:  # pragma: no cover - only when no event loop is configured
            _apply()
