import sys
from pathlib import Path

from folderconformer.updates import APP_NAME


CONTEXTS = (
    (r"Software\Classes\Directory\shell", "%1"),
    (r"Software\Classes\Directory\Background\shell", "%V"),
    (r"Software\Classes\Drive\shell", "%1"),
)


def install():
    import winreg

    executable = str(Path(sys.executable).with_name("pythonw.exe").resolve())
    icon = f'"{Path(__file__).resolve().parent / "FolderConformer.ico"}"'
    for root, target in CONTEXTS:
        menu_key = rf"{root}\{APP_NAME}"
        command = " ".join(f'"{part}"' for part in (executable, "-I", "-m", "folderconformer", target))
        print(f"File Explorer command ({root}): {command}")
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, menu_key, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"Open in {APP_NAME}")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, menu_key + r"\command", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
    print(f"[OK] Installed {len(CONTEXTS)} File Explorer context menu entries.")
    return 0
