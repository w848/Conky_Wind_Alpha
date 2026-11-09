"""Borderless, per-pixel-alpha window for the desktop monitor."""

from __future__ import annotations

import ctypes
import traceback
from ctypes import wintypes

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
SW_SHOWNOACTIVATE = 4
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_APP = 0x8000
WM_TRAY = WM_APP + 20
WM_NULL = 0
MF_STRING = 0
MF_SEPARATOR = 0x800
MF_CHECKED = 0x8
MF_POPUP = 0x10
TPM_RETURNCMD = 0x100
TPM_NONOTIFY = 0x80
TPM_RIGHTBUTTON = 0x2
NIF_MESSAGE = 0x1
NIF_ICON = 0x2
NIF_TIP = 0x4
NIF_INFO = 0x10
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIIF_INFO = 0x1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512
IDC_ARROW = 32512
LOGPIXELSX = 88

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", wintypes.BYTE),
        ("BlendFlags", wintypes.BYTE),
        ("SourceConstantAlpha", wintypes.BYTE),
        ("AlphaFormat", wintypes.BYTE),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


def _bind() -> None:
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
        ctypes.POINTER(POINT),
        ctypes.POINTER(SIZE),
        wintypes.HDC,
        ctypes.POINTER(POINT),
        wintypes.DWORD,
        ctypes.POINTER(BLENDFUNCTION),
        wintypes.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.restype = LRESULT
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_ulonglong, wintypes.UINT, ctypes.c_void_p]
    user32.SetTimer.restype = ctypes.c_ulonglong
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_ulonglong]
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadCursorW.restype = wintypes.HCURSOR
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wintypes.HICON
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.ReleaseCapture.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    user32.MessageBoxW.restype = ctypes.c_int
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowExW.restype = wintypes.HWND
    user32.SendMessageTimeoutW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    user32.SendMessageTimeoutW.restype = LRESULT
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
    ]
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(BITMAPINFOHEADER),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.GetDeviceCaps.restype = ctypes.c_int
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL


_bind()

_WINDOWS: dict[int, "LayeredWindow"] = {}
_CLASS_READY = False
_WNDPROC_REF: WNDPROC | None = None
_CLASS_NAME = "ConkyWindowsWidget"
_DPI_READY = False


def message_box(text: str, title: str = "Conky Windows", error: bool = False) -> None:
    flags = 0x10 if error else 0x40
    user32.MessageBoxW(None, text, title, flags)


def enable_dpi() -> None:
    global _DPI_READY
    if _DPI_READY:
        return
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
        try:
            shcore = ctypes.WinDLL("shcore", use_last_error=True)
            shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
            shcore.SetProcessDpiAwareness(2)
        except OSError:
            user32.SetProcessDPIAware()
    _DPI_READY = True


def dpi_scale() -> float:
    enable_dpi()
    try:
        user32.GetDpiForSystem.restype = wintypes.UINT
        dpi = int(user32.GetDpiForSystem())
        if dpi >= 96:
            return dpi / 96.0
    except (AttributeError, OSError):
        pass
    hdc = user32.GetDC(None)
    dpi = gdi32.GetDeviceCaps(hdc, LOGPIXELSX) or 96
    user32.ReleaseDC(None, hdc)
    return max(96, dpi) / 96.0


def work_area(index: int = 0) -> tuple[int, int, int, int]:
    enable_dpi()
    monitors: list[tuple[int, tuple[int, int, int, int]]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
    def callback(monitor, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            rect = info.rcWork
            primary = 0 if info.dwFlags & 1 else 1
            monitors.append((primary, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    user32.EnumDisplayMonitors(None, None, callback, 0)
    if not monitors:
        return (0, 0, 1280, 720)
    monitors.sort(key=lambda item: item[0])
    chosen = monitors[min(max(index, 0), len(monitors) - 1)][1]
    return chosen


def find_workerw() -> int | None:
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        return None
    result = ctypes.c_size_t()
    user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(result))
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        shell_view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if shell_view:
            worker = user32.FindWindowExW(None, hwnd, "WorkerW", None)
            if worker:
                found.append(int(worker))
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _window_long(hwnd, index: int) -> int:
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        return int(user32.GetWindowLongPtrW(hwnd, index))
    return int(user32.GetWindowLongW(hwnd, index))


def _set_window_long(hwnd, index: int, value: int) -> None:
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.SetWindowLongPtrW(hwnd, index, value)
    else:
        user32.SetWindowLongW(hwnd, index, value)


def _cursor() -> tuple[int, int]:
    point = POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def _premultiply(image: Image.Image) -> bytes:
    raw = image.tobytes("raw", "BGRA")
    buf = bytearray(raw)
    for index in range(0, len(buf), 4):
        alpha = buf[index + 3]
        if alpha == 0:
            buf[index] = buf[index + 1] = buf[index + 2] = 0
        elif alpha < 255:
            buf[index] = buf[index] * alpha // 255
            buf[index + 1] = buf[index + 1] * alpha // 255
            buf[index + 2] = buf[index + 2] * alpha // 255
    return bytes(buf)


def _wndproc(hwnd, message, wparam, lparam):
    window = _WINDOWS.get(int(hwnd))
    if window is None:
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)
    try:
        return window.handle(message, wparam, lparam)
    except Exception:
        traceback.print_exc()
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)


def _ensure_class() -> None:
    global _CLASS_READY, _WNDPROC_REF
    if _CLASS_READY:
        return
    _WNDPROC_REF = WNDPROC(_wndproc)
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = _WNDPROC_REF
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)
    wc.lpszClassName = _CLASS_NAME
    atom = user32.RegisterClassExW(ctypes.byref(wc))
    if not atom and ctypes.get_last_error() not in (0, 1410):
        raise ctypes.WinError(ctypes.get_last_error())
    _CLASS_READY = True
    _ensure_class.wc = wc  # type: ignore[attr-defined]


class LayeredWindow:
    def __init__(self, host) -> None:
        self.host = host
        self.hwnd: int | None = None
        self._image_id: int | None = None
        self._bits: bytes = b""
        self._width = 0
        self._height = 0
        self._dragging = False
        self._tray = False
        self._icon = None
        self._blit_error = False
        self._busy = False
        self.blit_ok = False

    def create(self) -> None:
        enable_dpi()
        _ensure_class()
        hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            _CLASS_NAME,
            "Conky Windows",
            WS_POPUP,
            0,
            0,
            100,
            100,
            None,
            None,
            kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = hwnd
        _WINDOWS[int(hwnd)] = self

    def show(self) -> None:
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)

    def present(self, image: Image.Image, x: int, y: int) -> None:
        if self.hwnd is None:
            return
        if id(image) != self._image_id:
            self._image_id = id(image)
            self._bits = _premultiply(image)
            self._width, self._height = image.size
        self._blit(x, y)

    def _blit(self, x: int, y: int) -> None:
        if not self._bits or self.hwnd is None:
            return
        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = self._width
        header.biHeight = -self._height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0
        screen = user32.GetDC(None)
        memory = gdi32.CreateCompatibleDC(screen)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(memory, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits:
            gdi32.DeleteDC(memory)
            user32.ReleaseDC(None, screen)
            return
        ctypes.memmove(bits, self._bits, len(self._bits))
        old = gdi32.SelectObject(memory, bitmap)
        destination = POINT(int(x), int(y))
        source = POINT(0, 0)
        size = SIZE(self._width, self._height)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        self.blit_ok = bool(
            user32.UpdateLayeredWindow(
                self.hwnd,
                screen,
                ctypes.byref(destination),
                ctypes.byref(size),
                memory,
                ctypes.byref(source),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )
        )
        if not self.blit_ok and not self._blit_error:
            self._blit_error = True
            self.host.on_blit_error(ctypes.get_last_error())
        gdi32.SelectObject(memory, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)

    def set_click_through(self, enabled: bool) -> None:
        self._restyle(click_through=enabled)

    def set_z_order(self, mode: str) -> None:
        if self.hwnd is None:
            return
        if mode == "desktop":
            worker = find_workerw()
            if worker:
                user32.SetParent(self.hwnd, worker)
            user32.SetWindowPos(self.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            return
        user32.SetParent(self.hwnd, None)
        insert = HWND_TOPMOST if mode == "dock" else HWND_NOTOPMOST
        user32.SetWindowPos(
            self.hwnd,
            insert,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )

    def _restyle(self, click_through: bool) -> None:
        if self.hwnd is None:
            return
        style = _window_long(self.hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if click_through:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        _set_window_long(self.hwnd, GWL_EXSTYLE, style)
        user32.SetWindowPos(
            self.hwnd,
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )

    def set_timer(self, seconds: float) -> None:
        if self.hwnd:
            user32.SetTimer(self.hwnd, 1, max(200, int(seconds * 1000)), None)

    def load_icon(self, path: str):
        icon = user32.LoadImageW(None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not icon:
            icon = user32.LoadIconW(None, IDI_APPLICATION)
        self._icon = icon
        return icon

    def add_tray(self, tip: str) -> bool:
        if self.hwnd is None:
            return False
        ok = self._notify(NIM_ADD, tip)
        self._tray = bool(ok)
        return bool(ok)

    def balloon(self, title: str, text: str) -> None:
        if self._tray:
            self._notify(NIM_MODIFY, "Conky Windows", title, text)

    def remove_tray(self) -> None:
        if self._tray and self.hwnd:
            self._notify(NIM_DELETE, "")
        self._tray = False

    def _notify(self, message: int, tip: str, title: str = "", info: str = "") -> bool:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._icon
        nid.szTip = tip[:127]
        if info:
            nid.uFlags |= NIF_INFO
            nid.szInfo = info[:255]
            nid.szInfoTitle = title[:63]
            nid.dwInfoFlags = NIIF_INFO
        return bool(shell32.Shell_NotifyIconW(message, ctypes.byref(nid)))

    def popup(self, items: list[dict]) -> int:
        if self.hwnd is None:
            return 0
        menu = self._build_menu(items)
        x, y = _cursor()
        user32.SetForegroundWindow(self.hwnd)
        command = user32.TrackPopupMenu(
            menu,
            TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
            x,
            y,
            0,
            self.hwnd,
            None,
        )
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        return int(command)

    def _build_menu(self, items: list[dict]):
        menu = user32.CreatePopupMenu()
        for item in items:
            if item.get("separator"):
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                continue
            if item.get("children"):
                child = self._build_menu(item["children"])
                user32.AppendMenuW(menu, MF_POPUP | MF_STRING, int(child), item.get("label", ""))
                continue
            flags = MF_STRING
            if item.get("checked"):
                flags |= MF_CHECKED
            user32.AppendMenuW(menu, flags, int(item.get("id", 0)), item.get("label", ""))
        return menu

    def loop(self) -> None:
        handler_ref = None
        try:
            HANDLER = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

            def _on_ctrl(_ctrl_type):
                user32.PostQuitMessage(0)
                return True

            handler_ref = HANDLER(_on_ctrl)
            kernel32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, wintypes.BOOL]
            kernel32.SetConsoleCtrlHandler(handler_ref, True)
        except (OSError, AttributeError):
            handler_ref = None
        message = MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        self.remove_tray()
        _ = handler_ref

    def close(self) -> None:
        self.remove_tray()
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)

    def handle(self, message: int, wparam, lparam) -> int:
        if message == WM_TIMER:
            if not self._busy:
                self._busy = True
                try:
                    self.host.on_timer()
                finally:
                    self._busy = False
            return 0
        if message == WM_LBUTTONDOWN:
            self._dragging = True
            user32.SetCapture(self.hwnd)
            x, y = _cursor()
            self.host.on_drag_start(x, y)
            return 0
        if message == WM_MOUSEMOVE and self._dragging:
            x, y = _cursor()
            self.host.on_drag(x, y)
            return 0
        if message == WM_LBUTTONUP and self._dragging:
            self._dragging = False
            user32.ReleaseCapture()
            self.host.on_drag_end()
            return 0
        if message == WM_RBUTTONUP:
            if self._dragging:
                self._dragging = False
                user32.ReleaseCapture()
            self.host.on_context_menu()
            return 0
        if message == WM_TRAY:
            event = int(lparam) & 0xFFFF
            if event == WM_RBUTTONUP:
                self.host.on_context_menu()
            elif event == WM_LBUTTONDBLCLK:
                self.host.on_edit()
            elif event == WM_LBUTTONUP:
                self.host.on_context_menu()
            return 0
        if message == WM_DESTROY:
            self.remove_tray()
            if self.hwnd is not None:
                _WINDOWS.pop(int(self.hwnd), None)
            user32.PostQuitMessage(0)
            return 0
        return int(user32.DefWindowProcW(self.hwnd, message, wparam, lparam))
