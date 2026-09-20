# Hushmix v0.5.1

An interface release. Hushmix now paints itself from a single design system built
on your Windows accent colour, and the light theme works for the first time.

If you use the light theme, this release is a real fix rather than a
cosmetic one: the setting had no effect at all before, and the window stayed dark
whatever you chose.

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
