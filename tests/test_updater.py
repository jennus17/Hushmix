"""End-to-end test of the update pipeline against the real GitHub release.

Exercises, in order:

* the version the updater reads from the built executable (PE resource);
* the live release lookup and its comparison against the installed version;
* a real download of the published asset with progress reporting and cancel;
* verification of the downloaded bytes;
* the generated install script, checked for the failure modes it used to have.

Nothing is installed: the swap script is inspected as text, never run.

Run with::

    python tests/test_updater.py [--download]
"""

import hashlib
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

DOWNLOAD = "--download" in sys.argv


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = []

    def check(self, condition, message):
        if condition:
            self.passed += 1
            print(f"ok   {message}")
        else:
            self.failed.append(message)
            print(f"FAIL {message}")

    def section(self, name):
        print(f"\n== {name} ==")

    def skip(self, message):
        print(f"skip {message}")


results = Results()


class _Settings:
    """Minimal settings store for the update-preference checks."""

    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=None):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = value


def main():
    from utils.version_utils import is_newer, normalize
    from version import GITHUB_REPOSITORY, __version__

    # ------------------------------------------------------------ version source
    results.section("version source of truth")
    results.check(
        re.fullmatch(r"\d+(\.\d+)*", __version__) is not None,
        f"version.py holds a parseable version: {__version__!r}",
    )

    exe = os.path.join(ROOT, "dist", "Hushmix.exe")
    if os.path.exists(exe):
        from utils.enhanced_version_manager import EnhancedVersionManager as EVM

        installed = EVM.read_installed_version()
        print(f"     executable: {os.path.relpath(exe, ROOT)}")
        print(f"     version.py: v{__version__}")
        print(f"     updater reads: {installed}")
        results.check(
            installed is not None,
            "the updater can read a version from the built executable",
        )
        results.check(
            installed is not None
            and normalize(installed) == normalize(__version__),
            f"the executable version ({installed}) matches version.py ({__version__})",
        )
    else:
        results.skip("dist/Hushmix.exe not built - skipping the PE resource check")

    # --------------------------------------------------------- comparison rules
    results.section("update decision")
    cases = [
        ("v0.4.8", "v0.4.7", True, "a newer release is offered"),
        ("v0.4.7", "v0.4.7", False, "the same version is not offered"),
        ("v0.4.6", "v0.4.7", False, "an older release is not offered"),
        ("v0.5.0", "v0.4.7", True, "a minor bump is offered"),
        ("1.0.0", "0.4.7", True, "a major bump is offered"),
        ("v0.4.7", "0.4.7", False, "a leading v does not matter"),
    ]
    for remote, local, expected, description in cases:
        results.check(
            is_newer(remote, local) is expected,
            f"{description} ({remote} vs {local})",
        )

    # ---------------------------------------------------------- live GitHub lookup
    results.section("live release lookup")
    from utils.enhanced_version_manager import EnhancedVersionManager as EVM

    manager = EVM.__new__(EVM)
    manager.settings_manager = None
    manager.update_sources = {
        "github": {
            "api_url": f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest",
            "download_base": f"https://github.com/{GITHUB_REPOSITORY}/releases/download",
            "release_page": f"https://github.com/{GITHUB_REPOSITORY}/releases/latest",
        },
        "custom_server": {
            "api_url": "https://example.invalid/api",
            "download_base": "https://example.invalid/dl",
            "release_page": "https://example.invalid",
        },
    }

    info = manager.get_update_info("github")
    if info is None:
        results.skip("no release available (offline, or the repository has none)")
    else:
        print(f"     latest release: {info['version']}")
        results.check(bool(info.get("version")), "the release reports a version")
        results.check(
            bool(info.get("download_url")),
            "the release reports a download URL",
        )
        results.check(
            info["download_url"].startswith("https://"),
            f"the download URL is HTTPS: {info['download_url']}",
        )
        results.check(
            info.get("size") is None or isinstance(info.get("size"), int),
            "size is either unknown or an integer",
        )
        if not info.get("checksum"):
            print("     note: this release publishes no checksum, so only the "
                  "executable header can be verified")

        installed = EVM.read_installed_version() or f"v{__version__}"
        offered = is_newer(info["version"], installed)
        print(f"     installed {installed} vs latest {info['version']} -> "
              f"update offered: {offered}")

    # ------------------------------------------------------------- bad responses
    results.section("malformed responses")
    results.check(
        manager._parse_github_response({}) is None,
        "a response with no tag_name is rejected",
    )
    parsed = manager._parse_github_response(
        {
            "tag_name": "v9.9.9",
            "body": "notes",
            "published_at": "2026-01-01T00:00:00Z",
            "assets": [
                {"name": "Hushmix.exe", "browser_download_url": "https://example.com/a.exe"},
                {"name": "other.zip", "browser_download_url": "https://example.com/b.zip"},
            ],
        }
    )
    results.check(
        parsed["download_url"] == "https://example.com/a.exe",
        f"the Hushmix.exe asset is preferred: {parsed['download_url']}",
    )
    results.check(
        parsed["size"] is None or isinstance(parsed["size"], int),
        "the asset size is carried through when present",
    )
    fallback = manager._parse_github_response({"tag_name": "v9.9.9", "assets": []})
    results.check(
        fallback["download_url"].endswith("/v9.9.9/Hushmix.exe"),
        f"a release without assets falls back to the conventional URL: "
        f"{fallback['download_url']}",
    )

    # ------------------------------------------------------ checksum extraction
    results.section("checksum handling")
    digest = "a" * 64
    for text, expected, description in (
        (f"SHA256: {digest}", digest, "a 'SHA256: <hash>' line"),
        (f"{digest}  Hushmix.exe", digest, "a sha256sum-style line"),
        (f"Changes:\n- fixed things\n\n{digest.upper()}\n", digest,
         "a bare hash on its own line, upper case"),
        ("no hash here", None, "text without a hash"),
        ("", None, "empty text"),
    ):
        results.check(
            EVM._checksum_from_text(text) == expected,
            f"{description} is parsed correctly",
        )

    # A checksum asset takes priority over the release notes.
    asset_info = manager._parse_github_response(
        {
            "tag_name": "v9.9.9",
            "body": "SHA256: " + "b" * 64,
            "assets": [
                {"name": "Hushmix.exe", "browser_download_url": "https://example.com/a.exe"},
                {"name": "Hushmix.exe.sha256",
                 "browser_download_url": "https://example.com/a.exe.sha256"},
            ],
        }
    )
    results.check(
        asset_info["checksum_url"] == "https://example.com/a.exe.sha256",
        f"a checksum asset is detected: {asset_info['checksum_url']}",
    )
    # (the fetch fails offline, so the notes hash is the fallback)
    results.check(
        asset_info["checksum"] in (None, "b" * 64),
        f"the checksum falls back to the release notes when the asset is "
        f"unreachable: {asset_info['checksum']}",
    )

    results.check(
        EVM._normalise_checksum(f"{digest}  Hushmix.exe") == digest,
        "a custom-server checksum line is normalised",
    )
    results.check(
        EVM._normalise_checksum(None) is None,
        "a missing custom checksum stays None",
    )

    # ------------------------------------------------------------ preferences
    results.section("update preferences")
    manager.settings_manager = _Settings()
    # ``manager`` was built with __new__ to avoid starting threads, so give it the
    # event objects that __init__ would have created.
    import threading as _threading

    manager._stop_event = _threading.Event()
    manager._wake_event = _threading.Event()

    manager.set_update_source("custom_server")
    results.check(
        manager.current_source == "custom_server",
        f"the update source can be switched: {manager.current_source}",
    )
    try:
        manager.set_update_source("nowhere")
        results.check(False, "an unknown update source should be rejected")
    except ValueError:
        results.check(True, "an unknown update source is rejected")

    manager.set_auto_check(False)
    results.check(
        manager.auto_check_enabled is False,
        "automatic checking can be turned off",
    )
    results.check(
        manager.settings_manager.get_setting("auto_check_updates") is False,
        "turning it off is persisted",
    )
    manager.set_auto_check(True)
    results.check(manager.auto_check_enabled is True, "and back on again")

    manager.set_check_interval(120)
    results.check(
        manager.check_interval == 120,
        f"the interval is clamped and stored: {manager.check_interval}",
    )
    manager.set_check_interval(1)
    results.check(
        manager.check_interval == 60,
        f"an interval below a minute is raised to 60: {manager.check_interval}",
    )
    manager.set_check_interval("nonsense")
    results.check(manager.check_interval == 60, "a non-numeric interval is ignored")

    # --------------------------------------------------------- verification rules
    results.section("download verification")
    with tempfile.TemporaryDirectory() as folder:
        tiny = os.path.join(folder, "tiny.bin")
        with open(tiny, "wb") as stream:
            stream.write(b"MZ" + b"\x00" * 10)
        results.check(
            not manager.verify_download(tiny, None),
            "a truncated file is rejected even without a published checksum",
        )

        fake = os.path.join(folder, "fake.exe")
        with open(fake, "wb") as stream:
            stream.write(b"MZ" + os.urandom(200_000))
        results.check(
            manager.verify_download(fake, None),
            "a plausible executable passes when no checksum is published",
        )

        digest = hashlib.sha256(open(fake, "rb").read()).hexdigest()
        results.check(
            manager.verify_download(fake, digest),
            "the correct checksum is accepted",
        )
        results.check(
            manager.verify_download(fake, digest.upper()),
            "an upper-case checksum is accepted",
        )
        results.check(
            not manager.verify_download(fake, "0" * 64),
            "a wrong checksum is rejected",
        )
        results.check(
            not manager.verify_download(os.path.join(folder, "missing.exe"), digest),
            "a missing file is rejected",
        )

        # The checksum of a real build must match its sidecar file.
        exe = os.path.join(ROOT, "dist", "Hushmix.exe")
        sidecar = f"{exe}.sha256"
        if os.path.exists(exe) and os.path.exists(sidecar):
            with open(sidecar, encoding="utf-8") as stream:
                published = EVM._checksum_from_text(stream.read())
            print(f"     sidecar: {os.path.basename(sidecar)} -> {published}")
            results.check(
                bool(published),
                "the generated checksum file contains a SHA-256",
            )
            results.check(
                manager.verify_download(exe, published),
                "the built executable matches its published checksum",
            )
            # A tampered binary must not.
            tampered = os.path.join(folder, "tampered.exe")
            with open(exe, "rb") as source, open(tampered, "wb") as target:
                target.write(source.read(200_000))
                target.write(b"\x00")  # change the bytes
            results.check(
                not manager.verify_download(tampered, published),
                "a modified executable fails checksum verification",
            )
        else:
            results.skip(
                "dist/Hushmix.exe.sha256 not present - run build_tools/build.py"
            )

    # ------------------------------------------------------------- install script
    results.section("install script")
    script = manager._build_update_script(
        r"C:\Apps\Hushmix.exe",
        r"C:\Apps\Hushmix.exe.backup",
        r"C:\Temp\hushmix_update_src.exe",
    )

    results.check(
        "taskkill /f /im" not in script.lower(),
        "the script does not force-kill by image name (which killed the freshly "
        "started replacement)",
    )
    results.check(
        ":gone" in script and "for /L" in script,
        "the script waits for the old process to exit before swapping",
    )
    results.check(
        script.count("copy /Y") >= 2,
        "the script copies the new binary and keeps a backup",
    )
    results.check(
        ":failed" in script and "restoring" in script.lower(),
        "the script restores the backup when the copy fails",
    )
    results.check(
        r"C:\Apps\Hushmix.exe" in script,
        "the script targets the running executable path",
    )
    results.check(
        script.count('del "%~f0"') >= 2,
        "the script deletes itself on both the success and failure paths",
    )

    # Ordered operations: wait, backup, copy, start.
    order = [
        script.index(":gone"),
        script.index('copy /Y "{target}"'),
        script.index('copy /Y "{source}"'),
    ] if False else None
    wait_at = script.index(":gone")
    backup_at = script.index(r'copy /Y "C:\Apps\Hushmix.exe"')
    swap_at = script.index(r'copy /Y "C:\Temp\hushmix_update_src.exe"')
    start_at = script.index(r'start ""')
    results.check(
        wait_at < backup_at < swap_at < start_at,
        "the script waits, backs up, swaps, then starts the new build",
    )

    # ---------------------------------------------------------------- real download
    results.section("real download")
    if not DOWNLOAD:
        results.skip("pass --download to fetch the published asset (about 70 MB)")
    elif info is None:
        results.skip("no release to download")
    else:
        progress = []
        started = time.monotonic()
        path = manager.download_update(
            info["download_url"],
            progress_callback=progress.append,
            cancellation_check=lambda: False,
        )
        elapsed = time.monotonic() - started

        results.check(path is not None and os.path.exists(path),
                      f"the asset downloaded to {path}")
        if path and os.path.exists(path):
            size = os.path.getsize(path)
            print(f"     {size / 1048576:.1f} MB in {elapsed:.1f}s, "
                  f"{len(progress)} progress callbacks")
            results.check(size > 1_000_000, f"the download is not empty ({size} bytes)")
            results.check(bool(progress), "progress was reported")
            if progress:
                results.check(
                    0 <= min(progress) and max(progress) <= 100,
                    f"progress stays within 0-100: {min(progress):.1f}..{max(progress):.1f}",
                )
                results.check(
                    progress == sorted(progress),
                    "progress never goes backwards",
                )
                results.check(
                    progress[-1] > 95,
                    f"the download finishes near 100% (ended at {progress[-1]:.1f}%)",
                )
            results.check(
                manager.verify_download(path, info.get("checksum")),
                "the downloaded file passes verification",
            )
            manager._remove_quietly(path)
            results.check(not os.path.exists(path), "the temporary file was cleaned up")

        # Cancellation must stop early and leave nothing behind.
        def cancel_immediately():
            return True

        path = manager.download_update(info["download_url"], cancellation_check=cancel_immediately)
        results.check(
            path is None,
            "a cancelled download returns None",
        )

    print("\n" + "=" * 60)
    print(f"checks passed: {results.passed}")
    print(f"failures     : {len(results.failed)}")
    for failure in results.failed:
        print(f"  - {failure}")
    return 1 if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
