# PyInstaller build for the Homeport desktop app (macOS, Windows, Linux).
#   pyinstaller packaging/homeport.spec --noconfirm
# Produces dist/Homeport/ (Windows/Linux) or dist/Homeport.app (macOS).
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("HOMEPORT_VERSION", "0.0.0")

hidden = (
    collect_submodules("backend")
    + collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + ["launch", "segno", "psutil", "httpx", "anyio", "h11"]
)
if sys.version_info < (3, 10):
    hidden.append("eval_type_backport")

a = Analysis(
    [os.path.join(ROOT, "desktop", "homeport_app.py")],
    pathex=[ROOT],
    datas=[
        (os.path.join(ROOT, "ui"), "ui"),
        (os.path.join(ROOT, "recipes"), "recipes"),
        (os.path.join(ROOT, "skills"), "skills"),
    ],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Homeport",
    console=False,  # GUI app: no terminal window
    icon=os.path.join(SPECPATH, "homeport.ico" if sys.platform == "win32" else "homeport.icns"),
)

coll = COLLECT(exe, a.binaries, a.datas, name="Homeport")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Homeport.app",
        icon=os.path.join(SPECPATH, "homeport.icns"),
        bundle_identifier="com.localhostmanager.homeport",
        version=VERSION,
        info_plist={
            "CFBundleName": "Homeport",
            "CFBundleDisplayName": "Homeport",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
        },
    )
