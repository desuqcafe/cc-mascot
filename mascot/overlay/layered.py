"""Per-pixel transparency for a Tk window on Windows: a layered window shows
an RGBA image as it is, soft edges and glows blended over the desktop, where
a color key only has fully shown and fully hidden pixels. Fully transparent
pixels let clicks through to what is behind.

Tk paints nothing in such a window: everything she shows is in the image.
"""

import ctypes
import ctypes.wintypes as wt

from PIL import Image, ImageChops

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TOPMOST = 0x8
GW_HWNDPREV = 3
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_NOOWNERZORDER = 0x1, 0x2, 0x10, 0x200
ULW_ALPHA = 2
AC_SRC_ALPHA = 1


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("op", ctypes.c_byte), ("flags", ctypes.c_byte), ("alpha", ctypes.c_ubyte), ("format", ctypes.c_byte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.GetParent.argtypes = [wt.HWND]
user32.GetParent.restype = wt.HWND
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), wt.HDC,
    ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.POINTER(BLENDFUNCTION), wt.DWORD,
]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]


def premultiplied_bgra(img):
    """What a layered window takes: each color already multiplied by alpha."""
    r, g, b, a = img.split()
    return Image.merge("RGBA", (ImageChops.multiply(b, a), ImageChops.multiply(g, a), ImageChops.multiply(r, a), a)).tobytes()


class LayeredWindow:
    """A Tk toplevel shown through UpdateLayeredWindow. `show(img, x, y)`
    puts an RGBA image at desktop pixels (x, y); `close()` frees the bitmap."""

    def __init__(self, tk_window):
        tk_window.update_idletasks()
        self.hwnd = user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()
        self._layer()
        self.dc = None
        self.bitmap = None
        self.old = None
        self.bits = ctypes.c_void_p()
        self.size = None
        self.image = None  # the last image shown, to move it without redrawing

    def _layer(self):
        """Makes the window layered anew: Tk's withdraw leaves it refusing
        UpdateLayeredWindow until its style is set again."""
        style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)

    def _bitmap_for(self, size):
        if size == self.size:
            return
        self.close()
        w, h = size
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        screen = user32.GetDC(None)
        self.dc = gdi32.CreateCompatibleDC(screen)
        user32.ReleaseDC(None, screen)
        self.bitmap = gdi32.CreateDIBSection(self.dc, ctypes.byref(header), 0, ctypes.byref(self.bits), None, 0)
        self.old = gdi32.SelectObject(self.dc, self.bitmap)
        self.size = size

    def show(self, img, x, y):
        """Shows `img` (None: the last one) at (x, y); False when Windows refused."""
        if img is not None and img is not self.image:
            self._bitmap_for(img.size)
            data = premultiplied_bgra(img)
            ctypes.memmove(self.bits, data, len(data))
            self.image = img
        if self.image is None:
            return False
        w, h = self.size
        blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)

        def update():
            return bool(user32.UpdateLayeredWindow(
                self.hwnd, None, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(w, h)), self.dc,
                ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA,
            ))

        if update():
            return True
        self._layer()
        return update()

    def keep_on_top(self):
        """Puts the window back on top when a window that is not topmost
        stands above it: Windows sometimes lets one (closing the Photos
        viewer, then clicking a terminal, did), the window still flagged
        topmost. Never takes the focus. Whether it had to."""
        above = user32.GetWindow(self.hwnd, GW_HWNDPREV)
        while above:
            if user32.IsWindowVisible(above) and not user32.GetWindowLongPtrW(above, GWL_EXSTYLE) & WS_EX_TOPMOST:
                user32.SetWindowPos(self.hwnd, wt.HWND(HWND_TOPMOST), 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER)
                return True
            above = user32.GetWindow(above, GW_HWNDPREV)
        return False

    def close(self):
        if self.dc:
            gdi32.SelectObject(self.dc, self.old)
            gdi32.DeleteObject(self.bitmap)
            gdi32.DeleteDC(self.dc)
        self.dc = self.bitmap = self.old = None
        self.size = self.image = None
