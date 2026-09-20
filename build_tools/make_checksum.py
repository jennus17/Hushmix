"""Write the release checksum for Hushmix.exe.

Uploading ``Hushmix.exe.sha256`` next to the executable lets the updater verify
a download exactly.  Without it, ``verify_download`` can only confirm that the
bytes look like a Windows executable - a truncated or substituted download would
pass.

Also prints a ready-to-paste line for the GitHub release notes, because the
updater reads a SHA-256 out of the release body when no checksum asset is
present.

Usage::

    python build_tools/make_checksum.py [path-to-exe]
"""

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EXE = os.path.join(ROOT, "dist", "Hushmix.exe")
CHUNK = 1024 * 1024


def sha256_of(path, chunk_size=CHUNK):
    """Streaming SHA-256 of a file, so large binaries need no extra memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def write_checksum(exe_path=DEFAULT_EXE, output_path=None):
    """Write ``<exe>.sha256`` and return ``(path, digest, size)``.

    The file uses the ``sha256sum`` convention (``<hash>  <filename>``), which is
    what the updater parses and what users expect.
    """
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"No executable at {exe_path} - build it first")

    digest = sha256_of(exe_path)
    filename = os.path.basename(exe_path)
    output_path = output_path or f"{exe_path}.sha256"

    with open(output_path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"{digest}  {filename}\n")

    return output_path, digest, os.path.getsize(exe_path)


def main():
    exe_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXE
    try:
        path, digest, size = write_checksum(exe_path)
    except FileNotFoundError as error:
        print(f"error: {error}")
        return 1

    print(f"Wrote {os.path.relpath(path, ROOT)}")
    print(f"  file  : {os.path.relpath(exe_path, ROOT)} ({size / 1048576:.1f} MB)")
    print(f"  sha256: {digest}")
    print()
    print("Upload that file as a release asset alongside Hushmix.exe, or paste")
    print("this line into the release notes:")
    print()
    print(f"  SHA256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
