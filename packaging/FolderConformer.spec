from pathlib import Path
import tomllib
from PyInstaller.utils.win32.versioninfo import FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo

root = Path(SPECPATH).parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
version_tuple = (*map(int, version.split(".")), 0)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable("040904B0", [
        StringStruct("ProductName", "FolderConformer"),
        StringStruct("FileDescription", "FolderConformer"),
        StringStruct("FileVersion", version), StringStruct("ProductVersion", version),
    ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])],
)
a = Analysis(
    [str(root / "main.py")], pathex=[str(root)],
    datas=[(str(root / "folderconformer/qml"), "folderconformer/qml"),
           (str(root / "pyproject.toml"), "."),
           (str(root / "build/tools"), "tools"),
           (str(root / "packaging/licenses"), "licenses")],
    binaries=[], hiddenimports=["PySide6.QtQuick", "PySide6.QtQuickControls2"], hookspath=[], runtime_hooks=[], excludes=[],
)
# Qt uses the Windows ICU API; exclude unrelated ICU builds found on the build host's PATH.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FolderConformer",
          console=True, hide_console="hide-early", version=version_info)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FolderConformer")
