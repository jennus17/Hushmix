# Interface design system

The interface is painted from one object - `utils.color_utils.Palette` - built by
`build_palette()` from two inputs: the Windows accent colour and the dark/light
setting. Nothing in the GUI hard-codes a colour, and no window derives its own
hover shade any more.

```python
from utils.color_utils import palette_for

palette = palette_for(settings_manager)   # honours dark_mode
palette.accent          # the accent, adjusted until it is actually visible
palette.accent_hover    # hover state for an accent fill
palette.accent_text     # the label colour to use ON an accent fill
palette.background      # the window
palette.surface         # cards, text fields
palette.surface_high    # hover highlight, dropdown body
palette.border          # hairlines
palette.text            # body text
palette.text_muted      # secondary text, volume read-outs
palette.danger          # errors, muted channels
```

Secondary windows inherit `build_palette()` from `gui.base_window.BaseWindow`,
so a new window gets the theme for free.

## Why the accent is not used as reported

Windows reports one accent colour, and on a machine with a dark custom accent it
is frequently near-black. This machine reports `#181a35`, a luminance of 27 out
of 255: painting buttons with it on a dark background left them almost
invisible, which is what made the profile dropdown and the footer buttons look
broken.

`visible_accent()` keeps the hue and saturation and rescales the lightness in
HLS until the colour clears a luminance floor (95) on the dark theme, or a
ceiling (172) on the light one. Accents that are already usable - `#2196f3`,
`#4caf50`, `#ff9800` - come back untouched. A neutral accent stays neutral
rather than being given a hue it never had.

`readable_text_color()` then picks the label colour for the resulting fill, so
accent buttons are legible instead of white-on-pale.

## Layout is not part of the theme

The window sizes itself to its content (`WindowManager.fit_window_to_content`),
so **changing a colour is safe but changing a control's height, padding or font
size is not**. A larger widget makes the window grow; that path is guarded by
`tests/test_dpi_scaling.py`, which checks the window still matches its content
after monitor moves.

The two font changes made for legibility (`Consolas` for the volume read-outs,
`Segoe UI 15` for the lane `⋮` buttons) were checked against the content size:
the window stayed at 387x332 at 100% scale.

## Theme defects fixed

- **Light mode never applied.** `HushmixApp.__init__` built the palette before
  `load_settings()` had read `dark_mode`, so the palette was always derived from
  the default (`True`) and the window stayed dark whatever the setting said.
  `refresh_palette()` now runs at the end of `load_settings()` and re-derives the
  tokens, handing the result to the GUI components. Guarded by
  `tests/test_themes.py`.
- **Bare Tk root colour.** CustomTkinter only paints its own widgets, so the
  root's background shows through anywhere they do not cover. It kept whatever
  colour it was created with, which left dark bands behind the rounded corners
  in the light theme. `WindowManager.apply_palette()` repaints it on a theme
  change.
- **Unreadable status colours.** The disconnected banner and the muted-channel
  volume read-out used the Tk colour name `red3`, which is too dark to read on
  the dark background. Both now use the palette's `danger` colour.
- **Muted volume read-out.** Muted channels are still shown in red, but the red
  is now the theme's.

## Visual changes

| Before | After |
| --- | --- |
| Every lane had a solid accent `⋮` button | Transparent until hovered, so the footer holds the attention |
| Accent fill nearly identical to the background | Accent lifted to a readable luminance, with a contrasting label |
| Profile dropdown and footer buttons in one flat accent | Accent fill, darker accent hover, tinted dropdown rows |
| Grey placeholder-coloured volume text | Muted theme colour in `Consolas`, so the column stops jittering at 99% -> 100% |
| Update dialog text box on the default dark grey | Themed surface, border and text; "Manual Download" is a secondary button instead of `gray` |
| Cancel button in flat `red` | Outlined danger button |
| Help window headings in raw accent | `accent_on_label`, legibility-adjusted for text rather than fill |

## Reviewing the interface

`build/shot.py` captures the real windows to PNG for visual review. It runs the
application against a throwaway `%APPDATA%`, so it cannot touch real settings:

```powershell
python build\shot.py build\ui.png --theme dark --dialogs settings,help
python build\shot.py build\ui-light.png --theme light
```

It captures with `PrintWindow` rather than a screen grab, because a screen grab
copies whatever is on top - an always-on-top camera preview ended up in the file
instead of the app.
