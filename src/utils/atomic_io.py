"""Durable JSON persistence helpers.

All configuration writes go through here so a crash, a power loss or a
simultaneous reader can never observe a half-written settings file.
"""

import json
import os
import tempfile


def ensure_parent_dir(path):
    """Create the directory that contains *path* (if any)."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _replace_with_retry(src, dst, attempts=5, delay=0.05):
    """os.replace with a short retry loop.

    Windows can briefly refuse the replace when an antivirus or a backup
    tool holds the destination open.  A few retries make that transient.
    """
    import time

    last_error = None
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return True
        except OSError as error:
            last_error = error
            if attempt < attempts - 1:
                time.sleep(delay * (attempt + 1))
    raise last_error


def atomic_write_text(path, text, encoding="utf-8"):
    """Write *text* to *path* atomically (temp file in the same directory)."""
    ensure_parent_dir(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    handle, temp_path = tempfile.mkstemp(
        prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        _replace_with_retry(temp_path, path)
        return True
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path, data, indent=4):
    """Serialise *data* to JSON and store it atomically."""
    return atomic_write_text(path, json.dumps(data, indent=indent))


def read_json(path, default=None, encoding="utf-8"):
    """Read JSON from *path*.

    Returns ``(data, error_message)``.  ``data`` is *default* when the file is
    missing, empty, unreadable or contains invalid JSON.
    """
    if not os.path.exists(path):
        return default, None

    try:
        with open(path, "r", encoding=encoding) as stream:
            raw = stream.read().strip()
    except OSError as error:
        return default, f"could not read {os.path.basename(path)}: {error}"

    if not raw:
        return default, f"{os.path.basename(path)} is empty"

    try:
        return json.loads(raw), None
    except json.JSONDecodeError as error:
        return default, f"{os.path.basename(path)} contains invalid JSON: {error}"
