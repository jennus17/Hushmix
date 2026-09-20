"""Tests for the theme palette and how it reaches the interface.

The interesting failures here are visual, so most of these are numeric
assertions about the colours that come out of :mod:`utils.color_utils`:

* a near-black Windows accent must not leave controls invisible on the dark
  theme - the reported defect, with ``#181a35`` as the real-world input;
* a label on an accent fill must contrast with it in both themes;
* the light theme must actually be light.

The last section guards the *ordering* bug that made the light theme dead:
``HushmixApp.__init__`` builds the palette before ``load_settings`` runs, so the
palette has to be rebuilt once the settings are known.  That is checked against
the source, because the symptom (a permanently dark window) is invisible to any
test that constructs the app without reading a settings file.

Run with::

    python tests/test_themes.py
"""

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from utils.color_utils import (  # noqa: E402
    ACCENT_MIN_LUMINANCE,
    build_palette,
    contrast_difference,
    get_windows_accent_color,
    readable_text_color,
    relative_luminance,
    visible_accent,
)

FAILURES = []
CHECKS = [0]

#: The accent this machine's Windows reports, and the one that started all this.
REPORTED_ACCENT = "#181a35"


def check(condition, message):
    CHECKS[0] += 1
    if condition:
        print(f"ok   {message}")
    else:
        FAILURES.append(message)
        print(f"FAIL {message}")


def section(name):
    print(f"\n== {name} ==")


def raises(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except Exception as error:
        return error
    return None


def main():
    # ------------------------------------------------------------ accent legibility
    section("accent legibility")

    dark = build_palette(REPORTED_ACCENT, dark_mode=True)
    light = build_palette(REPORTED_ACCENT, dark_mode=False)

    check(
        relative_luminance(dark.accent) >= ACCENT_MIN_LUMINANCE,
        f"the dark theme lifts a near-black accent to a visible luminance "
        f"({REPORTED_ACCENT} -> {dark.accent}, {relative_luminance(dark.accent):.0f})",
    )
    check(
        contrast_difference(dark.accent, dark.background) >= 60,
        f"the accent stands off the dark background "
        f"({contrast_difference(dark.accent, dark.background):.0f})",
    )
    check(
        contrast_difference(dark.accent_text, dark.accent) >= 90,
        f"the accent label is readable on the accent fill "
        f"({dark.accent_text} on {dark.accent})",
    )
    check(
        contrast_difference(light.accent_text, light.accent) >= 90,
        f"the accent label is readable in the light theme "
        f"({light.accent_text} on {light.accent})",
    )

    for palette, name in ((dark, "dark"), (light, "light")):
        check(
            contrast_difference(palette.text, palette.background) >= 120,
            f"{name} body text is clearly separated from the background",
        )
        check(
            contrast_difference(palette.text_muted, palette.surface) >= 60,
            f"{name} muted text is still legible on a surface",
        )
        check(
            palette.accent_hover != palette.accent,
            f"{name} accent has a distinct hover colour",
        )

    # ------------------------------------------------------- preserving the accent
    section("accents that already work")

    for accent in ("#2196f3", "#4caf50", "#ff9800", "#00bcd4"):
        check(
            visible_accent(accent, dark_mode=True) == accent,
            f"a visible accent is left alone on the dark theme ({accent})",
        )

    # A neutral accent must not gain a hue: the lightness rescale moves in HLS,
    # where a greyscale colour has a meaningless hue value.
    for accent in ("#ffffff", "#000000", "#808080"):
        result = visible_accent(accent, dark_mode=True)
        channels = [int(result[index : index + 2], 16) for index in (1, 3, 5)]
        check(
            max(channels) - min(channels) <= 2,
            f"a neutral accent stays neutral ({accent} -> {result})",
        )

    # ------------------------------------------------------------------- readable text
    section("label colour on a fill")

    check(
        readable_text_color("#ffffff") == "#101014",
        "white fills get dark labels",
    )
    check(
        readable_text_color("#000000") == "#ffffff",
        "black fills get light labels",
    )

    # --------------------------------------------------------------- theme polarity
    section("theme polarity")

    check(dark.dark_mode is True, "the dark palette reports itself as dark")
    check(light.dark_mode is False, "the light palette reports itself as light")
    check(
        relative_luminance(light.background) > relative_luminance(dark.background) + 100,
        "the light background really is much lighter than the dark one",
    )
    check(
        relative_luminance(dark.background) < 80,
        f"the dark background really is dark ({dark.background})",
    )

    # ------------------------------------------------------------------- robustness
    section("robustness")

    check(
        raises(build_palette, "not a colour") is None,
        "a malformed accent does not raise",
    )
    check(
        build_palette("not a colour").accent,
        "a malformed accent still produces a usable accent",
    )
    check(
        relative_luminance("red3") == 0.0,
        "a Tk colour name is reported as unknown rather than raising",
    )
    check(
        contrast_difference(None, "#ffffff") >= 0,
        "an unparseable colour does not raise from contrast_difference",
    )

    registry_accent = get_windows_accent_color()
    check(
        registry_accent.startswith("#") and len(registry_accent) == 7,
        f"the Windows accent is read as a hex colour ({registry_accent})",
    )

    # ------------------------------------------------- palette reaches the widgets
    section("the palette follows the loaded settings")

    app_source = open(os.path.join(SRC, "gui", "app.py"), encoding="utf-8").read()
    tree = ast.parse(app_source)

    load_settings = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "HushmixApp":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "load_settings":
                    load_settings = child

    check(load_settings is not None, "HushmixApp.load_settings was found")

    if load_settings is not None:
        called = [
            node.func.attr
            for node in ast.walk(load_settings)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        ]
        check(
            "refresh_palette" in called,
            "load_settings rebuilds the palette once dark_mode is known",
        )

    components_source = open(
        os.path.join(SRC, "gui", "gui_components.py"), encoding="utf-8"
    ).read()
    check(
        "self.palette" in components_source,
        "the main window paints itself from the palette",
    )
    check(
        "get_windows_accent_color" not in components_source,
        "no widget derives its own accent any more",
    )

    print("\n" + "=" * 60)
    print(f"checks passed: {CHECKS[0] - len(FAILURES)}")
    print(f"failures     : {len(FAILURES)}")
    for failure in FAILURES:
        print(f"  - {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.exit(code)
