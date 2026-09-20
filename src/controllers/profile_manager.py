"""Profile switching and persistence.

The previous implementation lost data when a save landed during a profile
switch.  Traced cause:

* ``on_profile_change`` did not switch anything itself - it *scheduled*
  ``_load_profile`` (previously via ``ProfileManager.on_profile_change``) while
  the dropdown and ``settings_vars["current_profile"]`` were updated
  immediately.  For one event-loop turn the active name said "new profile"
  while ``app.current_apps`` still held the old profile's data.
* ``_collect_profile_state`` (called by every save) re-read the current profile
  **from the dropdown widget**, so a save in that window wrote the old
  profile's entries into the new profile's slot - and the reverse on the way
  back.  Profiles bled into each other and edits disappeared.

Now a switch is atomic: the outgoing profile is saved under its own name, the
new name is published, the incoming data is loaded, and saves are suppressed
for the duration.  The dropdown is an output only, never a source of truth.
"""

from utils.config_manager import ConfigManager
from utils.logging_setup import get_logger

logger = get_logger("profile_manager")


class ProfileManager:
    def __init__(self, app_instance):
        self.app = app_instance

        #: Re-entrancy guard: a save must never run while the profile state is
        #: half-swapped.
        self._switching = False

    # ------------------------------------------------------------------ helpers

    @property
    def is_switching(self):
        return self._switching

    def current_profile(self):
        """Name of the active profile (never empty)."""
        name = self.app.settings_manager.settings_vars.get("current_profile")
        if isinstance(name, str) and name.strip():
            return name
        return ConfigManager.DEFAULT_PROFILE_NAMES[0]

    def _load_profile(self, name):
        """Replace the in-memory state with the stored profile *name*."""
        # Imported lazily: gui.app imports this module, so a top-level import
        # here would be circular.
        from gui.app import VAR_FIELDS

        app = self.app
        stored = (ConfigManager.load_all().get("profiles") or {}).get(name) or {}

        applications = list(stored.get("applications") or [])
        if not applications:
            applications = [""] * ConfigManager.CHANNEL_COUNT
        app.current_apps = applications

        for field in VAR_FIELDS:
            setattr(
                app,
                field,
                app._build_var_list(field, stored.get(field), ConfigManager.BUTTON_COUNT),
            )

        mute_state = stored.get("mute_state") or []
        app.current_mute_state = app._fit_mute_state(mute_state)
        app.muted_state = list(app.current_mute_state)
        app.previous_volumes = [None] * len(app.current_apps)

    def _publish(self, name):
        """Point the settings and the dropdown at *name* (output only)."""
        self.app.settings_manager.settings_vars["current_profile"] = name
        self.app.gui_components.set_profile_names(
            ConfigManager.get_profile_names(), name
        )

    # ---------------------------------------------------------------- switching

    def on_profile_change(self, profile):
        """Switch to *profile* atomically (dropdown command handler)."""
        if not profile or self._switching:
            return

        if profile == self.current_profile():
            # Tk can echo the selection back; nothing to do.
            return

        if profile not in ConfigManager.get_profile_names():
            logger.warning("Ignoring a switch to the unknown profile %r", profile)
            self._publish(self.current_profile())
            return

        self.switch_to(profile)

    def switch_to(self, profile):
        """Save the outgoing profile, then load *profile*."""
        app = self.app
        outgoing = self.current_profile()

        self._switching = True
        try:
            # 1. Persist the outgoing profile under its own name, while the
            #    in-memory state still belongs to it.
            self.save_profile(outgoing)

            # 2. Load the incoming profile and publish the new name together,
            #    so a save can never observe a half-swapped pair.
            self._load_profile(profile)
            self._publish(profile)

            # 3. Rebuild the channel rows for the new data.
            app.gui_components.refresh_gui()
        finally:
            self._switching = False

        logger.info("Switched to profile %s", profile)

    # -------------------------------------------------------------- refreshing

    def refresh_profile_list(self, current=None):
        """Reload the dropdown after profiles are added, renamed or removed."""
        names = ConfigManager.get_profile_names()
        current = current or self.current_profile()
        if current not in names and names:
            current = names[0]
            self.app.settings_manager.settings_vars["current_profile"] = current
        self.app.gui_components.set_profile_names(names, current)
        return names

    # --------------------------------------------------------------- persisting

    def save_profile(self, profile_name):
        """Write the current GUI state into *profile_name*.

        *profile_name* is explicit: the previous version asked the dropdown
        which profile was active, which is exactly how data ended up in the
        wrong slot.
        """
        if self._switching:
            # A save triggered from within a switch would write a profile we are
            # in the middle of replacing.
            return False

        if not profile_name:
            logger.warning("Refusing to save a profile with no name")
            return False

        try:
            app = self.app
            snapshot = app._collect_profile_state()

            full = ConfigManager.load_all()
            profiles = full.setdefault("profiles", {})
            profile = profiles.setdefault(profile_name, {})

            for field in ConfigManager.PROFILE_SETTINGS:
                profile[field] = list(snapshot.get(field, []))
            profile["applications"] = list(app.current_apps)
            profile["mute_state"] = list(app.current_mute_state)

            full["current_profile"] = self.current_profile()
            ConfigManager.save_all_settings(full)
            return True

        except Exception as error:
            logger.exception("Error saving profile %r: %s", profile_name, error)
            return False

    # Backwards compatible alias.
    def save_applications(self, event=None):
        """Persist application names when the user edits a field."""
        if self._switching:
            return

        try:
            app = self.app
            entries = getattr(getattr(app, "gui_components", None), "entries", None)
            if entries:
                app.current_apps = [entry.get() for entry in entries]

            self.save_profile(self.current_profile())

        except Exception as error:
            logger.exception("Error saving applications: %s", error)
