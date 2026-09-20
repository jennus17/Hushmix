"""Colour maths and the design tokens the interface is painted with.

Windows reports one accent colour and nothing else, and out of the box that is a
poor fit for a UI:

* The value is frequently very dark.  This machine reports ``#181a35`` - a
  luminance of 27 out of 255 - and painting a button with it on the dark
  background left the control almost invisible, which made the profile dropdown
  and the footer buttons look broken.
* A single flat colour is not enough to build an interface from anyway.  Buttons
  need a hover state, selected rows need a tint, body text needs to be quieter
  than headings, and an error banner needs a colour that reads as "error" in
  both themes.

So this module does two jobs.  The small helpers at the top are the colour
maths; :func:`build_palette` uses them to turn one accent colour into the whole
set of tokens, and everything in the GUI reads its colours from that palette
instead of hard-coding hex values or re-deriving a hover colour on the spot.
"""

import colorsys

try:
    import winreg
except ImportError:  # pragma: no cover - the app is Windows-only
    winreg = None

DEFAULT_ACCENT = "#2196F3"

#: Blending fraction: 0 keeps the reported colour, 1 becomes the target grey.
BLEND_STRENGTH = 0.7

#: Perceived luminance (0-255) an accent must reach to be legible as a control
#: fill on a dark background, or must stay under to work on a light one.
ACCENT_MIN_LUMINANCE = 95.0
ACCENT_MAX_LUMINANCE = 172.0

#: How far apart an accent fill and its label must be before the label is
#: considered readable on it.  The accent floor above already guarantees this for
#: text chosen by luminance, so :func:`readable_text_color` only has to pick the
#: side; the constant documents the margin the numeric rules leave.
MIN_FILL_CONTRAST = 90.0

#: Surfaces: the window itself, then one step up for rows, then two steps up for
#: a hover highlight.  ``surface_low`` is a step *down*, for recessed areas.
_SURFACES = {
    "dark": {
        "background": "#1b1b1f",
        "surface": "#242429",
        "surface_high": "#2e2e35",
        "surface_low": "#141417",
        "border": "#3a3a43",
        "border_strong": "#4c4c58",
    },
    "light": {
        "background": "#f4f4f7",
        "surface": "#ffffff",
        "surface_high": "#e8e8ef",
        "surface_low": "#e3e3e8",
        "border": "#d0d0d9",
        "border_strong": "#b0b0bd",
    },
}

#: Text is deliberately a warm-neutral grey rather than pure black or white:
#: full-contrast text on every label looks harsh and reads as unpolished.
_TEXT = {
    "dark": {
        "text": "#f2f2f5",
        "text_muted": "#a0a0ad",
        "text_subtle": "#7c7c89",
    },
    "light": {
        "text": "#1c1c22",
        "text_muted": "#55555f",
        "text_subtle": "#77777f",
    },
}

#: Status colours are fixed per theme instead of derived from the accent - a red
#: banner has to stay red whatever colour the user picked for Windows.
_STATUS = {
    "dark": {
        "danger": "#ff6b6b",
        "danger_surface": "#3a2024",
        "success": "#4ade80",
        "warning": "#fbbf24",
    },
    "light": {
        "danger": "#c62828",
        "danger_surface": "#fdecea",
        "success": "#1b7f4b",
        "warning": "#a86a00",
    },
}


# --------------------------------------------------------------------- parsing


def parse_color(value, default=None):
    """Return ``(r, g, b)`` for a Tk colour name, or *default* if unparseable.

    Tk colour names (``"red3"``, ``"transparent"``) cannot be read as hex, and
    the GUI does use a few of them, so callers get ``None`` rather than an
    exception when they hand one over.
    """
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    if len(text) != 6:
        return default
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return default


def _to_rgb(hex_color):
    rgb = parse_color(hex_color)
    if rgb is None:
        raise ValueError(f"Not a hex colour: {hex_color!r}")
    return rgb


def _to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        *(max(0, min(255, int(round(channel)))) for channel in rgb)
    )


def relative_luminance(hex_color):
    """Perceived brightness of a colour, 0 (black) to 255 (white)."""
    rgb = parse_color(hex_color)
    if rgb is None:
        return 0.0
    red, green, blue = rgb
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_difference(first, second):
    """Luminance gap between two colours, 0-255.

    A cheap stand-in for the WCAG contrast ratio that is enough to answer "is
    this text readable on this fill" without the gamma maths.
    """
    return abs(relative_luminance(first) - relative_luminance(second))


# -------------------------------------------------------------------- adjusting


def mix(first, second, amount):
    """Blend *first* towards *second*; ``amount`` 0-1."""
    amount = max(0.0, min(1.0, float(amount)))
    left = _to_rgb(first)
    right = _to_rgb(second)
    return _to_hex(
        tuple(a + (b - a) * amount for a, b in zip(left, right))
    )


def darken_color(hex_color, percentage):
    """Darken a hex colour by a given percentage."""
    red, green, blue = _to_rgb(hex_color)
    return _to_hex((red * (1 - percentage), green * (1 - percentage), blue * (1 - percentage)))


def lighten_color(hex_color, percentage):
    """Lighten a hex colour towards white by a given percentage."""
    red, green, blue = _to_rgb(hex_color)
    return _to_hex(
        (
            red + (255 - red) * percentage,
            green + (255 - green) * percentage,
            blue + (255 - blue) * percentage,
        )
    )


def _set_lightness(hex_color, lightness):
    """Move a colour to an HLS lightness, keeping its hue and saturation."""
    red, green, blue = _to_rgb(hex_color)
    hue, _, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    new_rgb = colorsys.hls_to_rgb(hue, max(0.0, min(1.0, lightness)), saturation)
    return _to_hex(tuple(channel * 255 for channel in new_rgb))


def visible_accent(accent, dark_mode=True):
    """Return *accent* moved to a lightness that can actually be seen.

    The hue and saturation are kept, so the result still reads as the colour the
    user chose; only the lightness moves.  When the reported colour is already
    usable it is returned untouched, which is the common case for people who
    picked one of Windows' brighter accents.

    Raising lightness by a *fraction* does not work - ``#181a35`` needs several
    hundred percent of it to become visible - so the colour is rescaled in HLS,
    where lightness is the coordinate being targeted.
    """
    rgb = parse_color(accent)
    if rgb is None:
        accent = DEFAULT_ACCENT
        rgb = parse_color(accent)

    luminance = relative_luminance(accent)
    if dark_mode:
        if luminance >= ACCENT_MIN_LUMINANCE:
            return accent
        target = 0.56
    else:
        if luminance <= ACCENT_MAX_LUMINANCE:
            return accent
        target = 0.42

    red, green, blue = rgb
    hue, _, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)

    # A near-grey accent stays grey when only its lightness moves, and grey
    # controls look like disabled ones.  Give it a little saturation back - but
    # only if it had any hue to begin with, otherwise the hue channel is
    # meaningless and the floor would invent a colour (white would turn pink).
    if saturation > 0.02:
        saturation = max(saturation, 0.25)

    adjusted = _to_hex(
        tuple(
            channel * 255
            for channel in colorsys.hls_to_rgb(hue, target, saturation)
        )
    )

    # Guard the target: for an unusual hue it could land on the wrong side.
    luminance = relative_luminance(adjusted)
    if dark_mode and luminance < ACCENT_MIN_LUMINANCE:
        return _set_lightness(accent, 0.62)
    if not dark_mode and luminance > ACCENT_MAX_LUMINANCE:
        return _set_lightness(accent, 0.34)
    return adjusted


def readable_text_color(fill, dark="#101014", light="#ffffff"):
    """Pick the label colour that stays legible on *fill*."""
    return dark if relative_luminance(fill) >= 128 else light


def _towards(hex_color, minimum=None, maximum=None, step=0.08, rounds=12):
    """Nudge a colour brighter or darker until it clears a luminance bound."""
    luminance = relative_luminance(hex_color)
    if minimum is not None and luminance < minimum:
        adjust = lambda value: lighten_color(value, step)
    elif maximum is not None and luminance > maximum:
        adjust = lambda value: darken_color(value, step)
    else:
        return hex_color

    for _ in range(rounds):
        hex_color = adjust(hex_color)
        luminance = relative_luminance(hex_color)
        if (minimum is not None and luminance >= minimum) or (
            maximum is not None and luminance <= maximum
        ):
            break
    return hex_color


def get_windows_accent_color(default=DEFAULT_ACCENT):
    """Retrieve the Windows accent colour from the registry."""
    if winreg is None:  # pragma: no cover - the app is Windows-only
        return default
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM"
        ) as key:
            accent_color = winreg.QueryValueEx(key, "ColorizationColor")[0]
            blue = accent_color & 0xFF
            green = (accent_color >> 8) & 0xFF
            red = (accent_color >> 16) & 0xFF
            return "#{:02x}{:02x}{:02x}".format(red, green, blue)
    except OSError:
        # A missing key just means "no custom accent"; that is not an error worth
        # logging, and returning the default keeps the UI fully styled.
        return default


# ---------------------------------------------------------------------- palette


class Palette:
    """The concrete colours the interface is painted with.

    Attributes are plain hex strings so they can be handed straight to
    CustomTkinter.  ``accent_text`` is the label colour to use *on* an accent
    fill - accent buttons in the dark theme end up light, so a white label on
    them would be unreadable.
    """

    __slots__ = (
        "dark_mode",
        "accent",
        "accent_hover",
        "accent_text",
        "accent_soft",
        "accent_border",
        "accent_on_label",
        "background",
        "surface",
        "surface_high",
        "surface_low",
        "border",
        "border_strong",
        "text",
        "text_muted",
        "text_subtle",
        "danger",
        "danger_surface",
        "success",
        "warning",
        "focus_ring",
    )

    def __init__(self, dark_mode, accent, **values):
        self.dark_mode = bool(dark_mode)
        self.accent = accent
        for name in self.__slots__:
            if name in ("dark_mode", "accent"):
                continue
            setattr(self, name, values.get(name, "#000000"))

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__slots__}

    def __repr__(self):  # pragma: no cover - debugging aid
        mode = "dark" if self.dark_mode else "light"
        return f"<Palette {mode} accent={self.accent}>"


def build_palette(accent=None, dark_mode=True):
    """Turn one accent colour into every colour the interface needs.

    *accent* defaults to the Windows accent; pass ``None`` explicitly through
    :func:`get_windows_accent_color` to keep that behaviour.
    """
    key = "dark" if dark_mode else "light"
    if accent is None:
        accent = get_windows_accent_color()

    base = visible_accent(accent, dark_mode=dark_mode)

    # Hover moves away from the surface: brighter in the dark theme, deeper in
    # the light one, so the direction of feedback matches the theme.
    if dark_mode:
        hover = _towards(lighten_color(base, 0.10), minimum=relative_luminance(base) + 8)
    else:
        hover = darken_color(base, 0.14)

    accent_text = readable_text_color(base)

    # A very low-alpha accent for selected rows and hovered lanes.  Blending
    # against the surface keeps it looking translucent without needing Tk to
    # support alpha.
    accent_soft = mix(_SURFACES[key]["surface"], base, 0.16)
    accent_border = mix(_SURFACES[key]["border"], base, 0.45)

    # Informational labels printed directly on the background (help window
    # headings) need the accent itself to be readable as text, not as a fill.
    accent_on_label = base
    if dark_mode:
        accent_on_label = _towards(base, minimum=120)
    else:
        accent_on_label = _towards(base, maximum=150)

    values = dict(_SURFACES[key])
    values.update(_TEXT[key])
    values.update(_STATUS[key])
    values.update(
        accent_hover=hover,
        accent_text=accent_text,
        accent_soft=accent_soft,
        accent_border=accent_border,
        accent_on_label=accent_on_label,
        focus_ring=accent_border,
    )
    return Palette(dark_mode, base, **values)


def palette_for(settings_manager=None, dark_mode=None):
    """Build a palette from the app's settings, falling back to the defaults."""
    if dark_mode is None:
        try:
            dark_mode = bool(settings_manager.get_setting("dark_mode", True))
        except Exception:
            dark_mode = True
    return build_palette(None, dark_mode=dark_mode)
