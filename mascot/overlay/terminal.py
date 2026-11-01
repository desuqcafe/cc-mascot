"""Her terminal's window: a click on her brings it forward, and with the
`nudge` setting its taskbar button flashes once she has waited on you long
enough.

A console program does not own the window it shows in. Windows Terminal
hosts its sessions: each console has a hidden PseudoConsoleWindow whose
root owner is the terminal's own window (CASCADIA_HOSTING_WINDOW_CLASS;
checked live, three sessions in tabs of one window all lead to it). The
old console host draws the console's window itself. Either way, the console
is found by attaching to it, which a process can do for one console at a
time and which must not touch the overlay's own stdout (the mod reads it),
so a helper process does it (`find`, about 100 ms, on a thread).

Tabs share their window (seen live: every session in tabs of one window,
so bringing the window forward changed nothing). So a click also selects
her tab (`select_tab`, on a thread after the window came forward): a tab's
name is its console's title (checked live, three tabs each matching their
session's `GetConsoleTitleW` exactly), read by the same helper at that
moment (Claude Code leads it with a spinner glyph that turns, so both sides
drop a leading symbol and space), and UI Automation selects the one tab of
that name (Windows PowerShell, always there; about 0.5 s with its start).
None or two of that name (a tab renamed by hand, two sessions on the same
topic): the window alone comes forward, as before.
"""

import ctypes
import ctypes.wintypes as wintypes
import os
import re
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
SELECT_TIMEOUT_S = 10

# Run by the helper: the console's window, then its root owner (the
# terminal's window, under Windows Terminal), 0 when there is none; on the
# next line the console's title (UTF-8).
HELPER = """
import ctypes, sys
k, u = ctypes.windll.kernel32, ctypes.windll.user32
k.GetConsoleWindow.restype = ctypes.c_void_p
u.GetAncestor.restype = ctypes.c_void_p
u.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
k.FreeConsole()
h = k.GetConsoleWindow() if k.AttachConsole(int(sys.argv[1])) else None
title = ctypes.create_unicode_buffer(1024)
if h:
    k.GetConsoleTitleW(title, 1024)
line = str((u.GetAncestor(h, 3) or h) if h else 0) + "\\n" + title.value.replace("\\n", " ") + "\\n"
sys.stdout.buffer.write(line.encode("utf-8"))
"""

# Selects the tab of window MASCOT_HWND whose name, bare, is MASCOT_TAB:
# only when exactly one is; prints how many matched.
SELECT = r"""
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$A = [Windows.Automation.AutomationElement]
$win = $A::FromHandle([IntPtr][long]$env:MASCOT_HWND)
$tab = New-Object Windows.Automation.PropertyCondition($A::ControlTypeProperty, [Windows.Automation.ControlType]::TabItem)
$hits = @($win.FindAll([Windows.Automation.TreeScope]::Descendants, $tab) | Where-Object { ($_.Current.Name -replace '^[^\w\s]\s', '') -ceq $env:MASCOT_TAB })
if ($hits.Count -eq 1) { $hits[0].GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern).Select() }
$hits.Count
"""


class FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def console(pid):
    """(window, title) of the console `pid` runs in: its top-level window or
    None, and its title or ""."""
    try:
        done = subprocess.run([sys.executable, "-c", HELPER, str(pid)], capture_output=True,
                              timeout=FIND_TIMEOUT_S, creationflags=CREATE_NO_WINDOW)
        hwnd, _, title = done.stdout.decode("utf-8", "replace").partition("\n")
        hwnd = int(hwnd.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, ""
    return (hwnd if hwnd and user32.IsWindow(hwnd) else None), title.rstrip("\r\n")


def find(pid):
    """The top-level window of the console `pid` runs in, or None."""
    return console(pid)[0]


def bare(title):
    """A tab's title without the symbol Claude Code leads it with (a
    spinner that turns, so it is not the same from one moment to the next)."""
    return re.sub(r"^[^\w\s]\s", "", title)


def select_tab(pid, hwnd):
    """Selects, in terminal window `hwnd`, the tab of the console `pid` runs
    in, by its title; whether one tab had it."""
    title = bare(console(pid)[1])
    if not title:
        return False
    env = dict(os.environ, MASCOT_HWND=str(hwnd), MASCOT_TAB=title)
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SELECT],
                              capture_output=True, text=True, env=env, timeout=SELECT_TIMEOUT_S,
                              creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.stdout.strip().splitlines()[-1:] == ["1"]


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

    def __init__(self, pid, finder=find, tabs=select_tab):
        self.pid, self.finder, self.tabs = pid, finder, tabs
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
        """Brings it forward, then her tab in it (on a thread); whether the
        window came. Not known yet, it is looked for now (tens of ms: a click
        waits for it)."""
        hwnd = self.window()
        if not hwnd and self.pid:
            self.hwnd = hwnd = self.finder(self.pid)
        if not hwnd:
            return False
        self.flashing = False
        came = bring_forward(hwnd)
        threading.Thread(target=self.tabs, args=(self.pid, hwnd), daemon=True).start()
        return came
