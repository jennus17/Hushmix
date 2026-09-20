"""Verify a published GitHub release end to end.

Run this straight after publishing, before telling anyone to update. It checks
the release through the same code path the application uses, so a green result
means an installed Hushmix will verify the download too.

It confirms:

* the release exists and carries a ``Hushmix.exe`` asset;
* a checksum is published (as an asset, or a ``SHA256:`` line in the notes);
* the published executable downloads and its SHA-256 matches that checksum;
* the checksum file's own format is one the updater can parse;
* the version tag is newer than the version that would be updating from.

Usage::

    python build_tools/verify_release.py                  # verifies version.py's tag
    python build_tools/verify_release.py v0.5.0
    python build_tools/verify_release.py --from v0.4.6    # also check it is newer
    python build_tools/verify_release.py --keep           # keep the download

Exit codes: 0 verified, 1 verification failed, 2 usage or network problem.
"""

import argparse
import hashlib
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from utils.enhanced_version_manager import (  # noqa: E402
    CHECKSUM_SUFFIXES,
    EnhancedVersionManager,
    GITHUB_REPOSITORY,
)
from version import __version__, version_tag  # noqa: E402

API = "https://api.github.com"
CHUNK = 1024 * 1024


class Failed(Exception):
    """A check did not pass."""


def _github(url, timeout=30):
    import requests

    return requests.get(
        url,
        timeout=timeout,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Hushmix-verify/{__version__}",
        },
    )


def fetch_release(tag):
    """Return the release JSON for *tag*, or raise :class:`Failed`."""
    response = _github(f"{API}/repos/{GITHUB_REPOSITORY}/releases/tags/{tag}")
    if response.status_code == 404:
        expected = version_tag()
        if tag == expected:
            raise Failed(
                f"no release tagged {tag}. Create it on GitHub and attach "
                "dist/Hushmix.exe and dist/Hushmix.exe.sha256."
            )
        raise Failed(
            f"no release tagged {tag!r}. Tags are case sensitive and must match "
            f"the version exactly; this build is {expected!r}."
        )
    if response.status_code != 200:
        raise Failed(f"GitHub returned {response.status_code} for tag {tag}")
    return response.json()


def describe_assets(release):
    """Split the release assets into (exe, checksum) and report what was found."""
    exe = None
    checksum = None
    for asset in release.get("assets", []) or []:
        name = str(asset.get("name", ""))
        lowered = name.lower()
        if lowered == "hushmix.exe":
            exe = asset
        elif lowered.endswith(CHECKSUM_SUFFIXES):
            checksum = asset
    return exe, checksum


def download(url, target, label="download"):
    """Stream a URL to *target*, reporting progress, and return (bytes, seconds)."""
    import requests

    started = time.monotonic()
    written = 0
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0) or 0)
        with open(target, "wb") as stream:
            for chunk in response.iter_content(chunk_size=CHUNK):
                if chunk:
                    stream.write(chunk)
                    written += len(chunk)
                    if total:
                        percent = written / total * 100
                        print(f"\r    {label}: {percent:5.1f}%", end="", flush=True)
    if total:
        print()
    return written, time.monotonic() - started


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(tag, from_version=None, keep=False):
    """Run every check for *tag*. Raises :class:`Failed` on the first problem."""
    print(f"Release  : {GITHUB_REPOSITORY} @ {tag}")

    release = fetch_release(tag)
    print(f"Name     : {release.get('name') or '(unnamed)'}")
    print(f"Published: {release.get('published_at') or 'unknown'}")
    if release.get("draft"):
        raise Failed("this release is still a draft, so it is not visible to users")
    if release.get("prerelease"):
        print("Warning  : marked as a pre-release; the updater reads /releases/latest,")
        print("           so a pre-release will not be offered unless it is the only one")

    exe, checksum_asset = describe_assets(release)
    names = [a.get("name") for a in release.get("assets", []) or []]
    print(f"Assets   : {', '.join(str(n) for n in names) if names else '(none)'}")

    # ---------------------------------------------------------------- the exe
    if exe is None:
        raise Failed(
            "no Hushmix.exe asset. The updater resolves the download from the "
            "asset list, and falls back to a conventionally named URL that only "
            "works if the file is attached."
        )
    size_mb = exe.get("size", 0) / 1048576
    print(f"Executable: {exe['name']}  {size_mb:.1f} MB")

    # ------------------------------------------------------------ the checksum
    notes = release.get("body") or ""
    notes_checksum = EnhancedVersionManager._checksum_from_text(notes)

    published = None
    source = None
    if checksum_asset is not None:
        url = checksum_asset.get("browser_download_url")
        print(f"Checksum : asset {checksum_asset['name']}")
        response = _github(url)
        if response.status_code != 200:
            raise Failed(f"the checksum asset could not be downloaded ({response.status_code})")
        published = EnhancedVersionManager._checksum_from_text(response.text)
        if published is None:
            raise Failed(
                f"{checksum_asset['name']} contains no SHA-256. Expected a line "
                "like '<64 hex chars>  Hushmix.exe'."
            )
        source = checksum_asset["name"]
    elif notes_checksum:
        published = notes_checksum
        source = "release notes"
        print("Checksum : from the release notes (no checksum asset)")
    else:
        raise Failed(
            "no checksum is published. Attach dist/Hushmix.exe.sha256 as a release "
            "asset, or put a 'SHA256: <hash>' line in the release notes. Without "
            "one the updater can only confirm the download looks like an "
            "executable, so a corrupted or substituted file would be accepted."
        )
    print(f"           {published}  (from {source})")

    if notes_checksum and published and notes_checksum != published:
        print(
            f"Warning  : the release notes carry a different hash "
            f"({notes_checksum[:16]}...); the asset wins, but the notes are stale"
        )

    # -------------------------------------------------------------- the download
    path = None
    temp_dir = tempfile.mkdtemp(prefix="hushmix_verify_")
    path = os.path.join(temp_dir, "Hushmix.exe")
    try:
        written, elapsed = download(
            exe["browser_download_url"], path, label="downloading"
        )
        speed = written / elapsed / 1048576 if elapsed else 0
        print(f"Downloaded: {written / 1048576:.1f} MB in {elapsed:.1f}s ({speed:.1f} MB/s)")

        if written != exe.get("size"):
            print(
                f"Warning  : downloaded {written} bytes but the API reported "
                f"{exe.get('size')}"
            )

        actual = sha256_of(path)
        print(f"SHA-256  : {actual}")
        if actual != published:
            raise Failed(
                "the published checksum does not match the published executable.\n"
                f"    published: {published}\n"
                f"    actual   : {actual}\n"
                "  The usual cause is a stale checksum file uploaded next to a "
                "rebuilt exe. Rebuild and upload both together."
            )
        print("           matches the published checksum")

        # The updater's own verification is the authority.
        manager = EnhancedVersionManager.__new__(EnhancedVersionManager)
        if not manager.verify_download(path, published):
            raise Failed("verify_download rejected the file the updater would use")
        print("           accepted by the updater's own verification")

        # ------------------------------------------------------------ version
        if from_version:
            from utils.version_utils import is_newer

            if not is_newer(tag, from_version):
                raise Failed(
                    f"{tag} is not newer than {from_version}, so an installation "
                    "on that version would not be offered this release"
                )
            print(f"Version  : {tag} is newer than {from_version}")

        if keep:
            kept = os.path.join(os.getcwd(), "verified-Hushmix.exe")
            os.replace(path, kept)
            path = None
            print(f"Kept     : {os.path.relpath(kept, os.getcwd())}")
    finally:
        if path and os.path.exists(path):
            os.remove(path)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Verify a published Hushmix release (checksum, assets, version)."
    )
    parser.add_argument(
        "tag",
        nargs="?",
        default=None,
        help=f"release tag to verify (default: v{__version__})",
    )
    parser.add_argument(
        "--from",
        dest="from_version",
        default=None,
        help="also check the release is newer than this version, e.g. v0.4.6",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the downloaded executable as ./verified-Hushmix.exe",
    )
    args = parser.parse_args()

    tag = args.tag or version_tag()

    try:
        import requests  # noqa: F401
    except ImportError:
        print("error: the 'requests' package is required")
        return 2

    try:
        verify(tag, from_version=args.from_version, keep=args.keep)
    except Failed as error:
        print()
        print(f"FAILED: {error}")
        return 1
    except Exception as error:
        print()
        print(f"error: {type(error).__name__}: {error}")
        return 2

    print()
    print("=" * 60)
    print(f"VERIFIED: {tag} is publishable and verifiable")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
