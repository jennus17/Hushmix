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


def main():
    from utils.version_utils import compare_versions, is_newer, normalize
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
    fallback = manager._parse_github_response({"tag_name": "v9.9.9", "assets": []})
    results.check(
        fallback["download_url"].endswith("/v9.9.9/Hushmix.exe"),
        f"a release without assets falls back to the conventional URL: "
        f"{fallback['download_url']}",
    )

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
            not manager.verify_download(fake, "0" * 64),
            "a wrong checksum is rejected",
        )
        results.check(
            not manager.verify_download(os.path.join(folder, "missing.exe"), digest),
            "a missing file is rejected",
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
