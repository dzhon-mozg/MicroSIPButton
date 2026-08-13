import ctypes
import ctypes.wintypes
import time


def find_microsip() -> int | None:
    hwnd = ctypes.windll.user32.FindWindowW("MicroSIP", None)
    return hwnd if hwnd else None


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
