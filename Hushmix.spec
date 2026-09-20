# PyInstaller build definition for Hushmix.
#
# Build with:  python build_tools/build.py
#
# Notes:
#  * ``src`` is prepended to ``pathex`` because the application uses flat
#    imports (``from utils... import ...``) and expects to be run from there.
#  * The icon is bundled twice: as the executable icon *and* as a data file,
#    because IconManager looks for ``utils/assets/volume_icon.ico`` at runtime.
#  * ``customtkinter`` ships JSON themes and fonts that must be collected.

import os

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.getcwd())
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(SRC, "utils", "assets")
VERSION_FILE = os.path.join(ROOT, "build", "version_info.txt")
ICON_FILE = os.path.join(ASSETS, "volume_icon.ico")

datas = [
    # ``utils/app_paths.resource_dir()`` returns ``sys._MEIPASS`` when frozen,
    # so the assets must land in ``<bundle>/assets`` - not under
    # ``utils/assets``, which is where a source checkout keeps them.
    (os.path.join(ASSETS, "volume_icon.ico"), "assets"),
    (os.path.join(ASSETS, "volume_icon.png"), "assets"),
    (os.path.join(ASSETS, "volume_icon32.png"), "assets"),
]

# CustomTkinter needs its theme JSON files next to the frozen package.
datas += collect_data_files("customtkinter")

hiddenimports = [
    "PIL._tkinter_finder",
    "comtypes.gen",
    "win32timezone",
]

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not used by the application; trimming them keeps the binary smaller.
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "pytest",
        "setuptools",
        "test",
        "unittest",
        "pydoc_data",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Hushmix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed application - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
    version=VERSION_FILE,
)
