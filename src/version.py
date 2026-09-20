"""Single source of truth for the application version.

The build script writes the same value into the executable's version resource;
the update checker reads that resource when frozen and falls back to this
constant when running from source (where there is no ``Hushmix.exe`` to read,
which previously disabled update checking entirely in development).

``0.0.0`` means "development build": it never claims to be newer than a release
and never suppresses a real update prompt.
"""

__version__ = "0.5.0"

#: Owner/repository used by the built-in GitHub update source.
GITHUB_REPOSITORY = "jennus17/Hushmix"


def version_tag():
    """Version formatted the way release tags are (``v0.5.0``)."""
    return f"v{__version__}"


def version_info_tuple():
    """Version as the four integers Windows version resources expect.

    Returns ``(parts, padded)`` where *parts* is a 4-tuple such as
    ``(0, 5, 0, 0)`` and *padded* is the single integer some tools want.
    """
    parts = []
    for chunk in __version__.split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 4:
        parts.append(0)
    padded = parts[0] * 65536 + parts[1] * 256 + parts[2]
    return tuple(parts[:4]), padded
