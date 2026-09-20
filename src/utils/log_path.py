"""Where the log file goes (and what to do when it cannot go there).

Kept deliberately dependent on nothing but the standard library: the logging
setup imports this module, so it must not be able to fail for import reasons.
"""

import os
import sys


def _candidate_locations():
    """Directories to try for the log file, most preferred first."""
    candidates = []

    for variable in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates.append(os.path.join(base, "Hushmix"))

    candidates.append(os.path.join(os.path.expanduser("~"), "Hushmix"))

    # Last resort: beside the executable (a portable copy may live in a
    # write-protected folder, so this is only a fallback).
    try:
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
    except Exception:
        pass

    try:
        import tempfile

        candidates.append(tempfile.gettempdir())
    except Exception:
        pass

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def log_filename():
    """Name of the log file."""
    return "hushmix.log"


def resolve_log_file():
    """Ordered list of candidate log file paths."""
    return [os.path.join(folder, log_filename()) for folder in _candidate_locations()]
