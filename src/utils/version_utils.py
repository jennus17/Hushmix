"""Version string helpers.

The previous update check compared version strings with ``!=`` and prompted to
"update" whenever they differed - including when the local build was *newer*
(for example a beta build) or when the tags were written differently
(``1.2.0`` vs ``v1.2.0``).
"""

import re

_TOKEN_PATTERN = re.compile(r"[0-9]+|[A-Za-z]+")


def _tokens(version):
    """Split a version string into comparable tokens."""
    if version is None:
        return []
    text = str(version).strip().lstrip("vV").strip()
    if not text:
        return []

    tokens = []
    for token in _TOKEN_PATTERN.findall(text):
        if token.isdigit():
            tokens.append((0, int(token), ""))
        else:
            tokens.append((1, 0, token.lower()))
    return tokens


def compare_versions(left, right):
    """Compare two version strings.

    Returns -1 when *left* is older, 0 when equal, 1 when *left* is newer.
    Pre-release identifiers (``1.2.0-beta``) sort before the plain release.
    """
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)

    if not left_tokens or not right_tokens:
        left_text = str(left or "").strip().lstrip("vV")
        right_text = str(right or "").strip().lstrip("vV")
        return (left_text > right_text) - (left_text < right_text)

    length = max(len(left_tokens), len(right_tokens))
    for index in range(length):
        left_token = left_tokens[index] if index < len(left_tokens) else (0, 0, "")
        right_token = right_tokens[index] if index < len(right_tokens) else (0, 0, "")

        if left_token == right_token:
            continue

        # A numeric token outranks a pre-release identifier, and "no further
        # token" (a release) outranks a pre-release identifier: 1.0.0 > 1.0.0-rc.
        if left_token[0] != right_token[0]:
            return -1 if left_token[0] > right_token[0] else 1

        if left_token[1] != right_token[1]:
            return -1 if left_token[1] < right_token[1] else 1

        if left_token[2] != right_token[2]:
            return -1 if left_token[2] < right_token[2] else 1

    return 0


def is_newer(candidate, current):
    """True when *candidate* is a strictly newer version than *current*."""
    return compare_versions(candidate, current) > 0


def normalize(version):
    """Return a display/cache friendly version string (``v`` prefix removed)."""
    if version is None:
        return ""
    return str(version).strip().lstrip("vV").strip()
