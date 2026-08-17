"""Извлекает полноразмерную иконку (все размеры, включая 256px) из MicroSIP.exe в icon.ico.

Запуск: python extract_icon.py [путь к microsip.exe] [выходной .ico]
По умолчанию читает installer/bundled/MicroSIP.exe и пишет icon.ico в корень проекта.
"""
import ctypes
import struct
import sys
from ctypes import wintypes

RT_ICON = 3
RT_GROUP_ICON = 14
LOAD_LIBRARY_AS_DATAFILE = 0x00000002

kernel32 = ctypes.windll.kernel32

LPCWSTR = ctypes.c_wchar_p
HMODULE = ctypes.c_void_p
HRSRC = ctypes.c_void_p
HGLOBAL = ctypes.c_void_p
LONG_PTR = ctypes.c_ssize_t

kernel32.LoadLibraryExW.argtypes = [LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
kernel32.LoadLibraryExW.restype = HMODULE
kernel32.FindResourceW.argtypes = [HMODULE, LPCWSTR, LPCWSTR]
kernel32.FindResourceW.restype = HRSRC
kernel32.SizeofResource.argtypes = [HMODULE, HRSRC]
kernel32.SizeofResource.restype = wintypes.DWORD
kernel32.LoadResource.argtypes = [HMODULE, HRSRC]
kernel32.LoadResource.restype = HGLOBAL
kernel32.LockResource.argtypes = [HGLOBAL]
kernel32.LockResource.restype = ctypes.c_void_p
kernel32.FreeLibrary.argtypes = [HMODULE]
kernel32.FreeLibrary.restype = ctypes.c_bool

ENUMRESNAMEPROCW = ctypes.WINFUNCTYPE(
    ctypes.c_bool, HMODULE, LPCWSTR, LPCWSTR, LONG_PTR
)


def _makeintresource(value):
    return ctypes.cast(ctypes.c_void_p(value), LPCWSTR)


def _load_resource(hmod, res_type, res_name):
    hres = kernel32.FindResourceW(hmod, _makeintresource(res_name), _makeintresource(res_type))
    if not hres:
        return None
    size = kernel32.SizeofResource(hmod, hres)
    hglob = kernel32.LoadResource(hmod, hres)
    if not hglob:
        return None
    ptr = kernel32.LockResource(hglob)
    if not ptr:
        return None
    return ctypes.string_at(ptr, size)


def extract(exe_path, out_path):
    hmod = kernel32.LoadLibraryExW(exe_path, None, LOAD_LIBRARY_AS_DATAFILE)
    if not hmod:
        raise OSError("LoadLibraryExW failed")

    try:
        groups = [
            gid for gid in range(1, 256)
            if kernel32.FindResourceW(hmod, _makeintresource(gid), _makeintresource(RT_GROUP_ICON))
        ]

        best = None
        for gid in groups:
            data = _load_resource(hmod, RT_GROUP_ICON, gid)
            if not data:
                continue
            count = struct.unpack("<HHH", data[:6])[2]
            if best is None or count > best[0]:
                best = (count, data)

        if best is None:
            raise OSError("icon group resource not found")
        data = best[1]

        count = struct.unpack("<HHH", data[:6])[2]
        entries = []
        for i in range(count):
            entries.append(struct.unpack(
                "<BBBBHHIH", data[6 + i * 14: 6 + (i + 1) * 14]
            ))

        out = bytearray()
        out += struct.pack("<HHH", 0, 1, count)
        images = []
        offset = 6 + 16 * count
        for width, height, colorcount, reserved, planes, bitcount, size, nid in entries:
            img = _load_resource(hmod, RT_ICON, nid)
            if img is None:
                raise OSError(f"RT_ICON #{nid} not found")
            out += struct.pack("<BBBBHHII", width, height, colorcount, reserved, planes, bitcount, len(img), offset)
            images.append(img)
            offset += len(img)
        for img in images:
            out += img
    finally:
        kernel32.FreeLibrary(hmod)

    with open(out_path, "wb") as f:
        f.write(out)


if __name__ == "__main__":
    import os
    root = os.path.dirname(os.path.abspath(__file__))
    exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "installer", "bundled", "MicroSIP.exe")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "icon.ico")
    extract(exe, out)
    with open(out, "rb") as f:
        raw = f.read()
    count = struct.unpack("<HHH", raw[:6])[2]
    sizes = []
    for i in range(count):
        w, h = raw[6 + i * 16], raw[7 + i * 16]
        sizes.append(f"{256 if w == 0 else w}x{256 if h == 0 else h}")
    print(f"extracted {count} icons ({', '.join(sizes)}) -> {out}")
