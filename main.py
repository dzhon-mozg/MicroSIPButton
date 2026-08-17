import ctypes
import ctypes.wintypes
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from ctypes.wintypes import RECT
import wx
import wx.adv
from microsip import find_microsip, find_microsip_exe, find_dial_edit, paste_to_microsip

GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SW_SHOWNA = 8
SW_HIDE = 0
BUTTON_SIZE_PX = 40
DOCK_GAP_PX = 4
ZONE_INSIDE_PX = BUTTON_SIZE_PX * 3 // 2
ZONE_OUTSIDE_PX = BUTTON_SIZE_PX * 3
OVERLAY_FILL = (0, 200, 80, 60)
OVERLAY_BORDER = (90, 255, 160, 235)
OVERLAY_GRADIENT_PX = 10
OVERLAY_BORDER_PX = 2
BTN_FONT_PT = 18
ZONES = ("left", "right")
SAFETY_CHECK_MS = 2000
CLIPBOARD_RETRIES = 3
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
EVENT_SYSTEM_MINIMIZESTART = 0x0016
EVENT_SYSTEM_MINIMIZEEND = 0x0017
WINEVENT_OUTOFCONTEXT = 0x0000
OBJID_WINDOW = 0
LOCATION_EVENTS = {EVENT_OBJECT_LOCATIONCHANGE}
VISIBILITY_EVENTS = {
    EVENT_OBJECT_SHOW,
    EVENT_OBJECT_HIDE,
    EVENT_SYSTEM_MINIMIZESTART,
    EVENT_SYSTEM_MINIMIZEEND,
}
MICROSIP_WAIT_SECONDS = 20


def snap_ranges(rect, size=BUTTON_SIZE_PX, inside=ZONE_INSIDE_PX, outside=ZONE_OUTSIDE_PX):
    s = size
    return [
        (rect.left - outside, rect.left + inside),
        (rect.right - inside, rect.right + outside),
    ]


def zone_rects(rect, size=BUTTON_SIZE_PX, inside=ZONE_INSIDE_PX, outside=ZONE_OUTSIDE_PX):
    s = size
    return [
        (rect.left - outside, rect.top, rect.left + inside + s, rect.bottom),
        (rect.right - inside, rect.top, rect.right + outside + s, rect.bottom),
    ]


def snap_x(x, ranges):
    best, best_d = None, float("inf")
    for lo, hi in ranges:
        if lo <= x <= hi:
            return x
        for edge in (lo, hi):
            d = abs(x - edge)
            if d < best_d:
                best_d, best = d, edge
    return best


def _virtual_screen():
    user32 = ctypes.windll.user32
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))


def placement_coords(zone, offset, y_offset, rect, vx, vy, vw, vh, size=BUTTON_SIZE_PX):
    s = size
    o = int(offset)
    if zone == "left":
        o = max(-ZONE_OUTSIDE_PX, min(o, ZONE_INSIDE_PX))
        x = rect.left + o
    else:
        o = max(-ZONE_INSIDE_PX, min(o, ZONE_OUTSIDE_PX))
        x = rect.right + o
    y = rect.top + int(y_offset)
    x = max(vx, min(x, vx + vw - s))
    y = max(vy, min(y, vy + vh - s))
    return x, y


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte),
    ]


def overlay_rgba(w, h, fill=OVERLAY_FILL, border=OVERLAY_BORDER,
                 band=OVERLAY_GRADIENT_PX, line=OVERLAY_BORDER_PX):
    """Попиксельный BGRA-буфер (bottom-up, преумноженная альфа) для UpdateLayeredWindow."""
    w, h = max(1, int(w)), max(1, int(h))
    band, line = max(0, int(band)), max(0, int(line))
    fr, fg, fb, fa = (int(v) for v in fill)
    br, bg, bb, ba = (int(v) for v in border)
    fill_quad = bytes((fb * fa // 255, fg * fa // 255, fr * fa // 255, fa))
    buf = bytearray(fill_quad * (w * h))  # заливка одним срезом, C-скорость

    limit = line + band
    quads = []
    for d in range(limit):
        if d < line:
            quads.append(bytes((bb * ba // 255, bg * ba // 255, br * ba // 255, ba)))
        else:
            t = (d - line) / band
            a = int(ba + (fa - ba) * t)
            r = int(br + (fr - br) * t)
            g = int(bg + (fg - bg) * t)
            b = int(bb + (fb - bb) * t)
            quads.append(bytes((b * a // 255, g * a // 255, r * a // 255, a)))

    for y in range(h):  # только рамка + градиент, O(w + h)
        dy = min(y, h - 1 - y)
        row = (h - 1 - y) * w * 4
        if dy < limit:
            for x in range(w):
                d = min(x, w - 1 - x, dy)
                if d < limit:
                    buf[row + x * 4: row + x * 4 + 4] = quads[d]
        else:
            for x in range(min(limit, w)):
                buf[row + x * 4: row + x * 4 + 4] = quads[x]
                buf[row + (w - 1 - x) * 4: row + (w - 1 - x) * 4 + 4] = quads[x]
    return buf


def _selftest():
    class Rect:
        def __init__(self, l, t, r, b):
            self.left, self.top, self.right, self.bottom = l, t, r, b

    rect = Rect(100, 100, 500, 400)
    rng = snap_ranges(rect)
    assert rng == [(-20, 160), (440, 620)], rng
    assert snap_x(-100, rng) == -20
    assert snap_x(80, rng) == 80        # кнопка на границе — разрешено
    assert snap_x(200, rng) == 160      # середина окна → ближний край
    assert snap_x(350, rng) == 440
    assert snap_x(700, rng) == 620
    assert placement_coords("right", 4, 150, rect, 0, 0, 1920, 1080) == (504, 250)
    assert placement_coords("right", 120, 150, rect, 0, 0, 1920, 1080) == (620, 250)
    assert placement_coords("right", -60, 150, rect, 0, 0, 1920, 1080) == (440, 250)
    assert placement_coords("right", -999, 150, rect, 0, 0, 1920, 1080) == (440, 250)
    assert placement_coords("left", 60, 150, rect, 0, 0, 1920, 1080) == (160, 250)
    assert placement_coords("left", -120, 150, rect, 0, 0, 1920, 1080) == (0, 250)
    assert placement_coords("left", 999, 150, rect, 0, 0, 1920, 1080) == (160, 250)
    assert zone_rects(rect)[0] == (-20, 100, 200, 400)
    assert zone_rects(rect)[1] == (440, 100, 660, 400)

    # окно на вторичном мониторе слева от основного (виртуальный экран: x ∈ [−1920, 1920))
    rect2 = Rect(-1500, 100, -1100, 400)
    assert placement_coords("right", 4, 150, rect2, -1920, 0, 3840, 1080) == (-1096, 250)
    assert placement_coords("left", -120, 150, rect2, -1920, 0, 3840, 1080) == (-1620, 250)
    assert placement_coords("left", -120, 150, Rect(-1900, 100, -1500, 400), -1920, 0, 3840, 1080) == (-1920, 250)

    w, h = 40, 40
    buf = overlay_rgba(w, h)
    border_i = (h - 1) * w * 4
    assert buf[border_i + 3] == 235, buf[border_i + 3]          # альфа рамки
    assert buf[border_i] == 160 * 235 // 255                     # B преумножен
    inner_i = (h - 1 - h // 2) * w * 4 + (w // 2) * 4
    assert buf[inner_i + 3] == 60                               # альфа фона
    grad_i = (h - 1 - 3) * w * 4 + 3 * 4
    assert 60 < buf[grad_i + 3] < 235                           # градиент между
    print("selftest OK")


def _parse_prefix():
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--prefix" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--prefix="):
            return arg.split("=", 1)[1]
    return None


def _resolve_prefix():
    cli = _parse_prefix()
    if cli is not None:
        return cli
    cfg = _load_config()
    if cfg and isinstance(cfg.get("prefix"), str):
        return cfg["prefix"]
    return "98"


def _parse_microsip_path():
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--microsip" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--microsip="):
            return arg.split("=", 1)[1]
    return None


def _setup_logging():
    log_path = os.path.join(tempfile.gettempdir(), "MicroSIPButton.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _config_path():
    appdata = os.environ.get("APPDATA") or tempfile.gettempdir()
    return os.path.join(appdata, "MicroSIPButton", "config.json")


def _load_config():
    try:
        with open(_config_path(), encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else None
    except Exception:
        return None


def _save_config(**updates):
    try:
        path = _config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cfg = _load_config() or {}
        cfg.update(updates)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        logging.warning("config save failed", exc_info=True)


class ZoneOverlay(wx.Frame):
    def __init__(self, host_hwnd: int):
        super().__init__(None, style=wx.BORDER_NONE | wx.FRAME_NO_TASKBAR)
        hwnd = self.GetHandle()
        user32 = ctypes.windll.user32
        user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, host_hwnd)
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE,
                                 ex | WS_EX_LAYERED | WS_EX_NOACTIVATE
                                 | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)

    def set_rect(self, left, top, right, bottom):
        w = max(1, int(right - left))
        h = max(1, int(bottom - top))
        self._update_layer(int(left), int(top), w, h, overlay_rgba(w, h))
        ctypes.windll.user32.ShowWindow(self.GetHandle(), SW_SHOWNA)

    def hide(self):
        ctypes.windll.user32.ShowWindow(self.GetHandle(), SW_HIDE)

    def _update_layer(self, x, y, w, h, buf):
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hwnd = self.GetHandle()
        hdc = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(hdc)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        old = gdi32.SelectObject(mem, hbmp)
        ctypes.memmove(bits, (ctypes.c_ubyte * len(buf)).from_buffer(buf), len(buf))
        pt = ctypes.wintypes.POINT(x, y)
        sz = ctypes.wintypes.SIZE(w, h)
        src = ctypes.wintypes.POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)  # AC_SRC_OVER + AC_SRC_ALPHA
        user32.UpdateLayeredWindow(hwnd, hdc, ctypes.byref(pt), ctypes.byref(sz),
                                   mem, ctypes.byref(src), 0, ctypes.byref(blend), 2)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, hdc)


class ButtonFrame(wx.Frame):
    def __init__(self, host_hwnd: int, prefix: str):
        super().__init__(None, style=wx.BORDER_NONE | wx.FRAME_NO_TASKBAR)
        self._host_hwnd = host_hwnd
        self._prefix = prefix
        self._position_scheduled = False
        self._active = True
        self._win_event_hook = 0
        self._dragging = False
        self._drag_offset = wx.Point(0, 0)
        self._overlays = []

        cfg = _load_config()
        zone = cfg.get("zone") if cfg else None
        if zone in ZONES:
            self._zone = zone
            self._offset = int(cfg.get("offset", DOCK_GAP_PX))
        elif zone == "out_left":
            self._zone = "left"
            self._offset = -int(cfg.get("gap", 0)) - BUTTON_SIZE_PX
        elif zone == "in_left":
            self._zone = "left"
            self._offset = 0
        elif zone == "in_right":
            self._zone = "right"
            self._offset = -BUTTON_SIZE_PX
        elif zone == "out_right":
            self._zone = "right"
            self._offset = int(cfg.get("gap", DOCK_GAP_PX))
        else:
            self._zone = ZONES[1]
            self._offset = DOCK_GAP_PX
        self._y_offset = int(cfg["y_offset"]) if cfg and "y_offset" in cfg else None

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(64, 150, 255))
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._btn = wx.Button(panel, label="\U0001F4DE", size=(BUTTON_SIZE_PX, BUTTON_SIZE_PX))
        font = self._btn.GetFont()
        font.SetPointSize(BTN_FONT_PT)
        self._btn.SetFont(font)
        self._btn.SetToolTip("Форматировать телефон из буфера\nи вставить в MicroSIP\n\nПравая кнопка мыши — перетащить кнопку")
        self._btn.Bind(wx.EVT_BUTTON, self._on_click)
        self._btn.Bind(wx.EVT_RIGHT_DOWN, self._on_right_down)
        self.Bind(wx.EVT_RIGHT_DOWN, self._on_right_down)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_RIGHT_UP, self._on_right_up)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._on_capture_lost)
        sizer.Add(self._btn, 0)
        panel.SetSizer(sizer)
        sizer.Fit(self)

        hwnd = self.GetHandle()
        user32 = ctypes.windll.user32
        user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, host_hwnd)
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

        self._place_initial(user32)
        self.Show()

        self._setup_event_hook()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(SAFETY_CHECK_MS)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _place_initial(self, user32):
        host = self._host_hwnd
        rect = RECT()
        user32.GetWindowRect(host, ctypes.byref(rect))
        if self._y_offset is None:
            self._y_offset = (rect.bottom - rect.top) // 2 - BUTTON_SIZE_PX // 2
        self._do_position()

    def _do_position(self):
        user32 = ctypes.windll.user32
        rect = RECT()
        user32.GetWindowRect(self._host_hwnd, ctypes.byref(rect))
        x, y = placement_coords(self._zone, self._offset, self._y_offset, rect, *_virtual_screen())
        user32.MoveWindow(self.GetHandle(), x, y, BUTTON_SIZE_PX, BUTTON_SIZE_PX, True)

    def _setup_event_hook(self):
        WINEVENTPROC = ctypes.WINFUNCTYPE(
            None, ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD,
            ctypes.wintypes.HWND, ctypes.c_long, ctypes.c_long,
            ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
        )
        self._win_event_cb = WINEVENTPROC(self._on_win_event)
        user32 = ctypes.windll.user32
        self._win_event_hook = user32.SetWinEventHook(
            EVENT_SYSTEM_MINIMIZESTART,
            EVENT_OBJECT_LOCATIONCHANGE,
            0,
            self._win_event_cb,
            0, 0,
            WINEVENT_OUTOFCONTEXT,
        )

    def _on_win_event(self, hook, event, hwnd, idObject, idChild, thread, evt_time):
        if not self._active or self._dragging:
            return
        if hwnd != self._host_hwnd or idObject != OBJID_WINDOW:
            return
        if event in LOCATION_EVENTS:
            if not self._position_scheduled:
                self._position_scheduled = True
                wx.CallAfter(self._do_position_scheduled)
        elif event in VISIBILITY_EVENTS:
            wx.CallAfter(self._sync_visibility)

    def _do_position_scheduled(self):
        self._position_scheduled = False
        if self._active and not self._dragging:
            self._do_position()

    def _sync_visibility(self):
        user32 = ctypes.windll.user32
        hwnd = self.GetHandle()
        host_visible = not user32.IsIconic(self._host_hwnd) and user32.IsWindowVisible(self._host_hwnd)
        my_visible = user32.IsWindowVisible(hwnd)
        if host_visible != my_visible:
            user32.ShowWindow(hwnd, 5 if host_visible else 0)  # SW_SHOW / SW_HIDE
            if host_visible:
                self._do_position()

    def _on_timer(self, evt):
        if not ctypes.windll.user32.IsWindow(self._host_hwnd):
            self.Close()
            return
        if not self._dragging:
            self._sync_visibility()

    def _show_overlays(self):
        if not self._overlays:
            self._overlays = [ZoneOverlay(self._host_hwnd) for _ in ZONES]
        rect = RECT()
        ctypes.windll.user32.GetWindowRect(self._host_hwnd, ctypes.byref(rect))
        for ov, r in zip(self._overlays, zone_rects(rect)):
            ov.set_rect(*r)
            ov.Show()
        ctypes.windll.user32.SetWindowPos(
            self.GetHandle(), HWND_TOP, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _on_right_down(self, evt):
        if self._dragging:
            return
        user32 = ctypes.windll.user32
        own = RECT()
        user32.GetWindowRect(self.GetHandle(), ctypes.byref(own))
        cur = wx.GetMousePosition()
        self._drag_offset = wx.Point(own.left - cur.x, own.top - cur.y)
        self._dragging = True
        self.CaptureMouse()
        self._show_overlays()

    def _on_motion(self, evt):
        if not self._dragging:
            return
        user32 = ctypes.windll.user32
        rect = RECT()
        user32.GetWindowRect(self._host_hwnd, ctypes.byref(rect))
        vx, vy, vw, vh = _virtual_screen()
        pt = wx.GetMousePosition() + self._drag_offset
        x = snap_x(pt.x, snap_ranges(rect))
        x = max(vx, min(x, vx + vw - BUTTON_SIZE_PX))
        y = pt.y
        y = max(rect.top, min(y, rect.bottom - BUTTON_SIZE_PX))
        y = max(vy, min(y, vy + vh - BUTTON_SIZE_PX))
        user32.MoveWindow(self.GetHandle(), x, y, BUTTON_SIZE_PX, BUTTON_SIZE_PX, True)

    def _on_right_up(self, evt):
        if self._dragging:
            self._end_drag()
            self._store_placement()

    def _on_capture_lost(self, evt):
        if self._dragging:
            self._end_drag()
            self._store_placement()

    def _end_drag(self):
        self._dragging = False
        if self.HasCapture():
            self.ReleaseMouse()
        for ov in self._overlays:
            ov.hide()

    def _store_placement(self):
        user32 = ctypes.windll.user32
        rect = RECT()
        user32.GetWindowRect(self._host_hwnd, ctypes.byref(rect))
        own = RECT()
        user32.GetWindowRect(self.GetHandle(), ctypes.byref(own))
        x, y = own.left, own.top
        s = BUTTON_SIZE_PX
        if x + s // 2 < (rect.left + rect.right) // 2:
            zone, offset = ZONES[0], x - rect.left
        else:
            zone, offset = ZONES[1], x - rect.right
        self._zone = zone
        self._offset = int(offset)
        self._y_offset = y - rect.top
        _save_config(zone=self._zone, offset=self._offset, y_offset=self._y_offset)

    def _on_click(self, evt):
        formatted = self._format_phone()
        if not formatted:
            return
        ok = paste_to_microsip(formatted)
        if ok:
            self._btn.SetLabel("✓")
            wx.CallLater(1500, lambda: self._btn.SetLabel("\U0001F4DE"))
            logging.info("Paste OK: %s", formatted)
        else:
            logging.warning("Paste failed: %s", formatted)

    def _format_phone(self):
        for _ in range(CLIPBOARD_RETRIES):
            if wx.TheClipboard.IsOpened():
                wx.TheClipboard.Close()
            if not wx.TheClipboard.Open():
                time.sleep(0.05)
                continue
            data = wx.TextDataObject()
            got = wx.TheClipboard.GetData(data)
            wx.TheClipboard.Close()
            if got:
                break
            time.sleep(0.05)
        else:
            logging.warning("Clipboard read failed after %d retries", CLIPBOARD_RETRIES)
            return None

        raw = data.GetText()
        digits = [c for c in raw if c.isdigit()]
        if len(digits) < 10:
            return None
        formatted = self._prefix + "".join(digits[-10:])

        for _ in range(CLIPBOARD_RETRIES):
            if wx.TheClipboard.IsOpened():
                wx.TheClipboard.Close()
            if wx.TheClipboard.Open():
                out = wx.TextDataObject()
                out.SetText(formatted)
                wx.TheClipboard.SetData(out)
                wx.TheClipboard.Flush()
                wx.TheClipboard.Close()
                return formatted
            time.sleep(0.05)
        logging.error("Clipboard write failed after %d retries", CLIPBOARD_RETRIES)
        return None

    def _on_close(self, evt):
        self._active = False
        if self._win_event_hook:
            ctypes.windll.user32.UnhookWinEvent(self._win_event_hook)
        self._timer.Stop()
        for ov in self._overlays:
            ov.Destroy()
        self._overlays = []
        self.Destroy()
        wx.GetApp().ExitMainLoop()


def _drawn_tray_icon():
    bmp = wx.Bitmap(16, 16)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(64, 150, 255)))
    dc.Clear()
    dc.SetBrush(wx.WHITE_BRUSH)
    dc.SetPen(wx.TRANSPARENT_PEN)
    dc.DrawRoundedRectangle(3, 1, 10, 4, 2)
    dc.DrawRoundedRectangle(3, 11, 10, 4, 2)
    dc.DrawRectangle(6, 5, 4, 6)
    dc.SelectObject(wx.NullBitmap)
    icon = wx.Icon()
    icon.CopyFromBitmap(bmp)
    return icon


def _microsip_icon(exe_path):
    if not exe_path:
        return None
    try:
        big = ctypes.c_void_p()
        small = ctypes.c_void_p()
        shell32 = ctypes.windll.shell32
        shell32.ExtractIconExW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_uint,
        ]
        shell32.ExtractIconExW.restype = ctypes.c_uint
        n = shell32.ExtractIconExW(exe_path, 0, ctypes.byref(big), ctypes.byref(small), 1)
        if n and small.value:
            icon = wx.Icon()
            ok = icon.CreateFromHICON(small.value)
            ctypes.windll.user32.DestroyIcon.argtypes = [ctypes.c_void_p]
            if big.value and big.value != small.value:
                ctypes.windll.user32.DestroyIcon(big.value)
            if ok and icon.IsOk():
                return icon
    except Exception:
        logging.warning("icon extraction failed", exc_info=True)
    return None


class TrayIcon(wx.adv.TaskBarIcon):
    def __init__(self, app, microsip_exe=None):
        super().__init__()
        self._app = app
        icon = _microsip_icon(microsip_exe) if microsip_exe else None
        if icon is None:
            icon = _drawn_tray_icon()
        self.SetIcon(icon, "MicroSIPButton")

    def CreatePopupMenu(self):
        menu = wx.Menu()
        item = menu.Append(wx.ID_ANY, "Префикс…")
        self.Bind(wx.EVT_MENU, self._on_prefix, item)
        menu.AppendSeparator()
        item = menu.Append(wx.ID_EXIT, "Выход")
        self.Bind(wx.EVT_MENU, self._on_exit, item)
        return menu

    def _on_prefix(self, evt):
        dlg = wx.TextEntryDialog(
            None, "Префикс, который добавляется к последним 10 цифрам номера "
                  "(пусто — без префикса):",
            "Префикс набора", self._app._prefix,
        )
        if dlg.ShowModal() == wx.ID_OK:
            self._app.set_prefix(dlg.GetValue().strip())
        dlg.Destroy()

    def _on_exit(self, evt):
        wx.GetApp().ExitMainLoop()


class ButtonApp(wx.App):
    def __init__(self, prefix: str, microsip_path: str | None = None):
        self._prefix = prefix
        self._microsip_path = microsip_path
        self._frame = None
        self._tray = None
        super().__init__()

    def OnInit(self):
        self._checker = wx.SingleInstanceChecker("MicroSIPButton")
        if self._checker.IsAnotherRunning():
            wx.MessageBox(
                "MicroSIPButton уже запущен.",
                "Кнопка", wx.OK | wx.ICON_INFORMATION,
            )
            return False
        hwnd = find_microsip()
        exe = find_microsip_exe(self._microsip_path)
        if not hwnd and exe:
            logging.info("Launching MicroSIP: %s", exe)
            subprocess.Popen([exe])
        elif not hwnd:
            logging.error("MicroSIP executable not found")
        if not hwnd:
            wait_ms = int(MICROSIP_WAIT_SECONDS * 1000 / 200)
            for _ in range(wait_ms):
                time.sleep(0.2)
                hwnd = find_microsip()
                if hwnd:
                    break
        if not hwnd:
            logging.error("MicroSIP window not found")
            wx.MessageBox(
                "MicroSIP не найден.\n\n"
                "Установите MicroSIP (microsip.org) или переустановите "
                "MicroSIPButton, отметив «Установить MicroSIP (из комплекта)».",
                "Кнопка", wx.OK | wx.ICON_INFORMATION,
            )
            return False
        logging.info("MicroSIP found (hwnd=%s), prefix=%s, starting", hwnd, self._prefix)
        self._frame = ButtonFrame(hwnd, self._prefix)
        self._tray = TrayIcon(self, exe)
        return True

    def set_prefix(self, prefix):
        self._prefix = prefix
        if self._frame is not None:
            self._frame._prefix = prefix
        _save_config(prefix=prefix)
        logging.info("prefix changed: %s", prefix)

    def OnExit(self):
        if self._tray is not None:
            self._tray.RemoveIcon()
            self._tray.Destroy()
            self._tray = None
        if self._frame is not None and self._frame._active:
            self._frame._on_close(None)
        return super().OnExit()


if __name__ == '__main__':
    _setup_logging()
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    prefix = _resolve_prefix()
    app = ButtonApp(prefix, _parse_microsip_path())
    app.MainLoop()
