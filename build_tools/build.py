"""Build Hushmix.exe.

Steps:
  1. regenerate ``build/version_info.txt`` from ``src/version.py``;
  2. run PyInstaller against ``Hushmix.spec``;
  3. report the resulting binary and its version resource.

Usage::

    python build_tools/build.py              # normal build
    python build_tools/build.py --clean      # wipe build/ and dist/ first
    python build_tools/build.py --console    # keep a console (debugging)

The build venv created by the instructions in the README is used automatically
when it exists (``build/.venv``); otherwise the current interpreter is used.
"""

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
VENV_PYTHON = os.path.join(ROOT, "build", ".venv", "Scripts", "python.exe")
SPEC_FILE = os.path.join(ROOT, "Hushmix.spec")
DIST_DIR = os.path.join(ROOT, "dist")
EXE_PATH = os.path.join(DIST_DIR, "Hushmix.exe")

sys.path.insert(0, SRC)


def find_python():
    """Prefer the build virtualenv, fall back to the running interpreter."""
    if os.path.exists(VENV_PYTHON):
        return VENV_PYTHON
    return sys.executable


def run(command, **kwargs):
    print(f"$ {' '.join(command)}", flush=True)
    return subprocess.run(command, check=True, **kwargs)


def ensure_pyinstaller(python):
    try:
        subprocess.run(
            [python, "-c", "import PyInstaller"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    except subprocess.CalledProcessError:
        pass

    print("PyInstaller is not installed - installing it now")
    run([python, "-m", "pip", "install", "--quiet", "pyinstaller"])


def clean():
    for folder in (os.path.join(ROOT, "build", "Hushmix"), DIST_DIR):
        if os.path.exists(folder):
            print(f"Removing {os.path.relpath(folder, ROOT)}")
            shutil.rmtree(folder, ignore_errors=True)


def write_version_info(python):
    run([python, os.path.join(ROOT, "build_tools", "make_version_info.py")])


def build(python, console=False):
    command = [python, "-m", "PyInstaller", "--noconfirm", "--clean", SPEC_FILE]
    if console:
        # ``--console`` cannot override the spec, so patch it via an env var the
        # spec would need to read; instead we simply warn and continue.
        print("note: Hushmix.spec builds a windowed binary; --console is ignored")
    run(command, cwd=ROOT)


def describe():
    from make_version_info import __name__ as _  # noqa: F401  (path setup)
    from make_checksum import write_checksum

    import version

    if not os.path.exists(EXE_PATH):
        print("Build did not produce dist/Hushmix.exe")
        return 1

    size_mb = os.path.getsize(EXE_PATH) / (1024 * 1024)
    print()
    print("=" * 60)
    print(f"Built  : {os.path.relpath(EXE_PATH, ROOT)}")
    print(f"Version: {version.__version__}")
    print(f"Size   : {size_mb:.1f} MB")

    # Publish-ready checksum: without one the updater can only confirm that a
    # download looks like an executable.
    try:
        path, digest, _size = write_checksum(EXE_PATH)
        print(f"SHA256 : {digest}")
        print(f"         written to {os.path.relpath(path, ROOT)}")
        print()
        print("Upload both files to the release, or paste this into the notes:")
        print(f"  SHA256: {digest}")
    except Exception as error:
        print(f"SHA256 : could not be generated ({error})")

    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Build Hushmix.exe")
    parser.add_argument("--clean", action="store_true", help="remove previous build output")
    parser.add_argument("--console", action="store_true", help="(ignored) debug console")
    args = parser.parse_args()

    python = find_python()
    print(f"Interpreter: {python}")

    if args.clean:
        clean()

    ensure_pyinstaller(python)
    write_version_info(python)
    build(python, console=args.console)
    return describe()


if __name__ == "__main__":
    sys.exit(main())
