# Hushmix v0.5.1

An interface release with one significant hardware fix. Hushmix now paints
itself from a single design system built on your Windows accent colour, the
light theme works for the first time, and a mixer that has been unplugged for a
while reconnects by itself instead of needing a restart.

If you use the light theme, this release is a real fix rather than a cosmetic
one: the setting had no effect at all before, and the window stayed dark
whatever you chose.

If you have ever had to restart Hushmix to get the mixer back after unplugging
it, that was a bug, and this release fixes it.

If you updated to 0.5.0 and saw a "Security validation failure" error while it
relaunched, that was a bug in the updater; it is fixed here, so updating to this
version will relaunch cleanly.

## Download

| File | |
| --- | --- |
| **Hushmix.exe** | Windows 10/11 64-bit |
| **Hushmix.exe.sha256** | verify your download |

## Verify your download

```powershell
# Download both files into the same folder, then:
(Get-FileHash .\Hushmix.exe -Algorithm SHA256).Hash.ToLower()
Get-Content .\Hushmix.exe.sha256
```

The two values must match. Hushmix checks this automatically before installing an
update, so an interrupted or substituted download is rejected instead of
installed.

## The interface

Hushmix now takes its colours from one palette derived from two things: your
Windows accent colour and the dark/light setting. Everything else - button
hovers, selected rows, borders, secondary text, the error colour - is derived
from those, so the interface is consistent instead of each window inventing its
own shades.

- **Accent colours are now actually visible.** Windows reports a single accent
  colour, and with a dark custom accent it can be very dark indeed - the accent
  on the machine this was developed against is `#181a35`, which is almost
  black. Painted onto a dark window, buttons and the profile dropdown were
  nearly invisible. Hushmix keeps your hue and saturation and moves only the
  lightness, until the colour is readable. If your accent is already usable
  (`#2196f3`, `#4caf50` and similar), it is left exactly as it is.
- **Button labels adapt to the fill**, so an accent button is never white text on
  a pale background.
- **The lane buttons are quieter.** Six solid accent `⋮` buttons made the lanes
  the loudest thing on the window; they are now transparent until you hover them,
  so the profile controls in the footer get the attention.
- **Volume percentages no longer jitter.** They use a fixed-width font, so the
  column stops shifting sideways when a reading crosses 99% → 100%.
- **Muted channels and the "Mixer Disconnected" banner use the theme's error
  colour.** Both used a Windows colour name (`red3`) that is unreadable on the
  dark theme.
- **The update window, settings, help, button settings and shortcut recorder all
  follow the theme**, including their dropdowns and text fields. "Manual
  Download" is a proper secondary button instead of flat grey.

## Fixes

- **The light theme never applied.** Hushmix created its colour palette before it
  had read your settings, so it always assumed the dark theme - choosing Light
  changed nothing. The window stayed dark no matter what the setting said.
- **Dark bands behind the rounded corners in the light theme.** The plain
  Windows window underneath CustomTkinter's widgets kept the colour it was
  created with; it is now repainted along with everything else.
- **Logging could break itself.** Reconfiguring the log could close the stream
  other code was still writing to, after which records were replaced by
  `--- Logging error ---`.
- **Modifier keys could stay stuck.** If releasing one of Ctrl/Shift/Alt/Win
  failed, the others were never released either.
- **Updating from 0.4.6 to 0.5.0 finished, then showed
  "Security validation failure: unexpected name of application's home
  directory!" instead of starting.** The update itself worked - opening Hushmix
  again ran the new version - but the automatic relaunch failed. Hushmix is a
  single-file executable, so when it runs it unpacks itself into a temporary
  folder and passes that folder to its own child process through an environment
  variable. The replaced build left those variables behind, the new build
  inherited them, tried to reuse a folder that belonged to the version being
  replaced, and its bootloader's security check rejected that. The relaunch now
  starts the new build with those variables cleared, so this cannot happen on
  any future update.

**The mixer no longer needs a restart after being unplugged**

Unplugging the mixer for a while and plugging it back in could leave Hushmix
waiting forever, with only a restart bringing it back. There were three separate
reasons, and all three are fixed:

- **A quiet port looked exactly like a working one.** Unplugging a CH340 does not
  reliably make a read fail. Windows leaves the handle open and every read simply
  times out, so Hushmix kept believing it was connected and the reconnect logic
  never ran. The link is now judged by traffic: the mixer sends about 25 packets
  a second, so ten seconds of silence closes the port and reopens it. Measured on
  the real hardware, the worst gap between packets is 66 ms, so the margin is
  large enough that a busy machine cannot trip it.
- **The mixer could not be recognised after re-enumerating.** The port was found
  by matching the adapter's USB *description*. When Windows gives the device a
  different COM number, an empty description, or a generic one, nothing matched
  and the mixer was invisible however many times Hushmix looked. Hushmix now
  remembers the port that last worked, and the adapter's USB identity
  (`VID_1A86&PID_7523` for the CH340), and as a last resort asks each port
  directly - the mixer streams continuously, so the port that answers with valid
  packets is the mixer.
- **The reader could stop reading and never come back.** Closing the port from
  the reconnect logic while a read was in progress, which is exactly what happens
  when the cable is pulled, failed with an internal error that was not handled.
  That ended the reading thread silently and permanently: Hushmix stayed
  connected on screen and received nothing. The read path now survives it.

A mixer that is unplugged now reconnects within a second or two of being plugged
back in. The "Mixer Disconnected" banner also appears when it should, since a
silent link is no longer mistaken for a healthy one.

- **"Mixer not found" now says what it actually saw** - every serial port and its
  description - so a missing device can be told apart from one that simply did
  not match.

## Improvements

- **The log file is written at debug level.** `%APPDATA%\Hushmix\hushmix.log`
  now contains the detail needed to diagnose a report - which channel controls
  which application, why a channel was skipped, which monitor scale was applied.
  The console stays quiet at INFO; set `HUSH_DEBUG=1` to see the same detail in
  a terminal.
- **Release builds are pinned.** `constraints.txt` records the exact version of
  every dependency the release was built and tested against, so a rebuild does
  not silently pull in a different library.
- **The release verifier sets itself up.** `build_tools/verify_release.py` now
  re-runs inside the build environment when it is missing dependencies, instead
  of failing with an import error.
- **Fewer silent failures.** Two dozen error handlers that discarded their
  exception now log it, which is why some problems were previously invisible.
- Help window sections no longer use raw accent colour for headings, so they stay
  readable whichever accent you have.

## Build

```bash
python -m venv build/.venv
build/.venv/Scripts/python -m pip install -r requirements.txt -c constraints.txt
python build_tools/build.py
```

Produces `dist/Hushmix.exe` and `dist/Hushmix.exe.sha256`. The version resource is
generated from `src/version.py`, so the binary and the update checker cannot
disagree.

Verify a published release at any time:

```bash
build/.venv/Scripts/python build_tools/verify_release.py v0.5.1 --from v0.5.0
```

## Known issues

- **The executable is not code signed.** On machines with Windows Smart App
  Control enabled, Windows may refuse to run it, reporting that an Application
  Control policy blocked the file. Signing needs a code-signing certificate;
  running from source is unaffected. A checksum confirms the file is the one that
  was published, but it does not tell Windows who built it.
- Updating closes the application while the executable is replaced. Settings and
  profiles are preserved.
- A profile stores which application each channel controls, its mute state, and
  the button actions - not a volume level. The mixer's physical position is the
  source of truth, so volumes come from the hardware when the application starts.
- A window taller than your screen is clipped: the window is not resizable and
  does not scroll.

## Requirements

- Windows 10 or 11, 64-bit
- A USB-SERIAL CH340 based mixer is optional: without one, the application still
  manages Windows volumes, but there is nothing physical to turn
