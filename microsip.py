import ctypes
import ctypes.wintypes
import os
import sys
import time
import winreg

SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9


def find_microsip() -> int | None:
    hwnd = ctypes.windll.user32.FindWindowW("MicroSIP", None)
    return hwnd if hwnd else None


def _registry_microsip_dir() -> str | None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MicroSIP",
        ) as key:
            try:
                loc = winreg.QueryValueEx(key, "InstallLocation")[0]
            except OSError:
                loc = ""
            try:
                un = winreg.QueryValueEx(key, "UninstallString")[0].strip('"')
            except OSError:
                un = ""
    except OSError:
        return None
    for base in (loc, os.path.dirname(un)):
        if base and os.path.isfile(os.path.join(base, "MicroSIP.exe")):
            return base
    return None


def find_microsip_exe(explicit: str | None = None) -> str | None:
    local = os.environ.get("LOCALAPPDATA", "")
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates = [
        explicit,
        os.path.join(_registry_microsip_dir() or "", "MicroSIP.exe"),
        os.path.join(local, "MicroSIP", "MicroSIP.exe"),
        os.path.join(exe_dir, "MicroSIP.exe"),
        os.path.join(exe_dir, "MicroSIP", "MicroSIP.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "MicroSIP", "MicroSIP.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "MicroSIP", "MicroSIP.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def find_dial_edit(hwnd: int) -> int | None:
    user32 = ctypes.windll.user32
    found: list[int] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(child, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child, cls, 256)
        if cls.value == "Edit" and user32.IsWindowVisible(child) and user32.IsWindowEnabled(child):
            found.append(child)
        return True

    user32.EnumChildWindows(hwnd, WNDENUMPROC(callback), 0)
    return found[0] if found else None


def toggle_microsip(hwnd: int) -> bool:
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    elif user32.IsWindowVisible(hwnd):
        user32.ShowWindow(hwnd, SW_HIDE)
    else:
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetForegroundWindow(hwnd)
    return True


def paste_to_microsip(text: str) -> bool:
    user32 = ctypes.windll.user32
    hwnd = find_microsip()
    if not hwnd:
        return False
    edit = find_dial_edit(hwnd)
    if not edit:
        return False
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    for _ in range(2):
        user32.SendMessageW(edit, 0x00B1, 0, -1)  # EM_SETSEL select all
        user32.SendMessageW(edit, 0x0302, 0, 0)   # WM_PASTE
        time.sleep(0.1)
        buf = ctypes.create_unicode_buffer(256)
        user32.SendMessageW(edit, 0x000D, 256, buf)  # WM_GETTEXT
        if buf.value == text:
            return True
    user32.SendMessageW(edit, 0x00B1, 0, -1)
    user32.SendMessageW(edit, 0x000C, 0, text)  # WM_SETTEXT fallback
    return True
