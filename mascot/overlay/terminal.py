"""Her terminal's window, for the `nudge` setting: its taskbar button flashes
once she has waited on you long enough, and a click on her brings it forward.

A console program does not own the window it shows in. Windows Terminal
hosts its sessions: each console has a hidden PseudoConsoleWindow whose
root owner is the terminal's own window (CASCADIA_HOSTING_WINDOW_CLASS;
checked live, three sessions in tabs of one window all lead to it). The
old console host draws the console's window itself. Either way, the console
is found by attaching to it, which a process can do for one console at a
time and which must not touch the overlay's own stdout (the mod reads it),
so a helper process does it (`find`, about 100 ms, on a thread). Tabs share
their window: which tab shows is the terminal's to say, not hers.
"""

import ctypes
import ctypes.wintypes as wintypes
import subprocess
import sys
import threading
import time

user32 = ctypes.windll.user32
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.GetForegroundWindow.restype = wintypes.HWND

GA_ROOTOWNER = 3
FLASHW_STOP, FLASHW_TRAY, FLASHW_TIMERNOFG = 0, 2, 12
SW_RESTORE = 9
CREATE_NO_WINDOW = 0x08000000
FIND_TIMEOUT_S = 5
FIND_AGAIN_S = 30  # a window not found (or gone) is looked for again this often, at most

# Run by the helper: the console's window, then its root owner (the
# terminal's window, under Windows Terminal); 0 when there is none.
HELPER = """
import ctypes, sys
k, u = ctypes.windll.kernel32, ctypes.windll.user32
k.GetConsoleWindow.restype = ctypes.c_void_p
u.GetAncestor.restype = ctypes.c_void_p
u.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
k.FreeConsole()
h = k.GetConsoleWindow() if k.AttachConsole(int(sys.argv[1])) else None
print((u.GetAncestor(h, 3) or h) if h else 0)
"""


class FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def find(pid):
    """The top-level window of the console `pid` runs in, or None."""
    try:
        done = subprocess.run([sys.executable, "-c", HELPER, str(pid)], capture_output=True, text=True,
                              timeout=FIND_TIMEOUT_S, creationflags=CREATE_NO_WINDOW)
        hwnd = int(done.stdout.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return hwnd if hwnd and user32.IsWindow(hwnd) else None


def flash(hwnd, on=True):
    """Flashes `hwnd`'s taskbar button until it comes to the front (nothing
    when it is in front already); `on` False stops it."""
    info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_TRAY | FLASHW_TIMERNOFG if on else FLASHW_STOP, 0, 0)
    user32.FlashWindowEx(ctypes.byref(info))


def bring_forward(hwnd):
    """Puts `hwnd` in front, restored if minimized. Windows allows it from
    the process that took the last input: a click on her."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.SetForegroundWindow(hwnd))


class Terminal:
    """The window of Claude Code `pid`'s terminal, found once on a thread
    (`find`) and kept while it lasts; None until then, or when there is none."""

    def __init__(self, pid, finder=find):
        self.pid, self.finder = pid, finder
        self.hwnd = None
        self.looked = None  # when it was last looked for (monotonic s)
        self.flashing = False

    def window(self):
        """The window if known now; a look for it starts when it is not."""
        if self.hwnd and user32.IsWindow(self.hwnd):
            return self.hwnd
        self.hwnd = None
        now = time.monotonic()
        if self.pid and (self.looked is None or now - self.looked >= FIND_AGAIN_S):
            self.looked = now
            threading.Thread(target=self._find, daemon=True).start()
        return None

    def _find(self):
        self.hwnd = self.finder(self.pid)

    def call(self, on):
        """Flashes its taskbar button (`on`), or stops a flash started here."""
        hwnd = self.window()
        if hwnd and on != self.flashing:
            flash(hwnd, on)
            self.flashing = on
        elif not on:
            self.flashing = False

    def come(self):
        """Brings it forward; whether it came. Not known yet, it is looked
        for now (tens of ms: a click waits for it)."""
        hwnd = self.window()
        if not hwnd and self.pid:
            self.hwnd = hwnd = self.finder(self.pid)
        if not hwnd:
            return False
        self.flashing = False
        return bring_forward(hwnd)
