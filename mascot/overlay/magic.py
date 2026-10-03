"""Her call: a round of work over while you are elsewhere, she sends magic
to your pointer, whichever display it is on (effects.magic draws it). The
mod writes the call into the session file (`call`: {at, test?}) when a
round lasted the `magicAfter` setting's minutes; the overlay hands it here.

A call waits for you (`verdict`): while you are away (no input for AWAY_S),
while Windows holds notifications back (a fullscreen game or video, a
presentation) and while the pointer is hidden. It is dropped when you are
already looking: her session's terminal is the window in front, and when
that terminal holds other sessions too, her tab is the one in front (its
title, `is_watching`). A test call (/mascot magic, the settings window's button)
waits only for the pointer.

It flies in a window of its own (layered.popup: clicks pass through it and
it never takes the focus), MAGIC_BOX square, moved with the comet and then
the pointer at ANIMATE_FPS for the few seconds it plays, hidden after.
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

from PIL import Image

import effects as fx
from layered import LayeredWindow, popup

AWAY_S = 20  # no mouse or key for this long: you are away, and she waits for you
# SHQueryUserNotificationState: a fullscreen app, a Direct3D one, presentation mode.
HELD_STATES = (2, 3, 4)
CURSOR_SHOWING = 0x1
BUTTONS = (0x01, 0x02, 0x04)  # VK_LBUTTON, VK_RBUTTON, VK_MBUTTON
TICK_MS = round(1000 / fx.ANIMATE_FPS)
TITLES_TIMEOUT_S = 3
CREATE_NO_WINDOW = 0x08000000


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hCursor", wt.HANDLE), ("ptScreenPos", wt.POINT)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


user32 = ctypes.windll.user32
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
kernel32 = ctypes.windll.kernel32
kernel32.GetTickCount.restype = wt.DWORD
kernel32.AttachConsole.argtypes = [wt.DWORD]
kernel32.GetConsoleTitleW.argtypes = [wt.LPWSTR, wt.DWORD]


def idle_s():
    """Seconds since the last mouse or key input, anywhere."""
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000


def notifications_held():
    """Whether Windows holds notifications back now: a fullscreen app, a
    game, a presentation."""
    state = ctypes.c_int()
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    return state.value in HELD_STATES


def pointer():
    """The pointer's tip (desktop px), or None while it is hidden (a game,
    typing with a pen or touch)."""
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(info)) or not info.flags & CURSOR_SHOWING:
        return None
    return info.ptScreenPos.x, info.ptScreenPos.y


def pressed():
    """Whether a mouse button is down now."""
    return any(user32.GetAsyncKeyState(button) & 0x8000 for button in BUTTONS)


def foreground_pid():
    """The process of the window in front; 0 for none."""
    pid = wt.DWORD()
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def lineage(pid, table):
    """`pid` and every process above it (`table`: mascot_overlay.process_table)."""
    found = []
    while pid in table and pid not in found:
        found.append(pid)
        pid = table[pid][0]
    return found


def foreground_title():
    """The title of the window in front: a terminal's is its active tab's."""
    hwnd = user32.GetForegroundWindow()
    text = ctypes.create_unicode_buffer(512)
    if hwnd:
        user32.GetWindowTextW(hwnd, text, 512)
    return text.value


def console_titles(pids):
    """{pid: its console's title} (a terminal tab's title is its console's).
    Read by a helper process (this file, run): attaching to another
    process's console from the overlay itself could disturb the handles
    its word to the mod goes out on. {} when it cannot be read."""
    try:
        done = subprocess.run([sys.executable, os.path.abspath(__file__), "titles", *map(str, pids)],
                              capture_output=True, timeout=TITLES_TIMEOUT_S, creationflags=CREATE_NO_WINDOW)
        titles = json.loads(done.stdout.decode("utf-8") or "{}")
        return {int(pid): title for pid, title in titles.items()}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def is_watching(front, claude, table, title="", titles_of=console_titles):
    """Whether the window in front (its process `front`, its `title`) shows
    Claude Code `claude`'s session: it is one of the processes Claude Code
    runs under (its terminal, an editor), and no other Claude Code runs
    under it; or, when others do (a terminal's other tabs and windows), the
    window's title is her session's tab's alone (`titles_of`: console_titles).
    When that cannot be told, you may be looking elsewhere: she calls."""
    if not front or front not in lineage(claude, table):
        return False
    name = table[claude][1].lower()
    sessions = [pid for pid, (parent, exe) in table.items()
                if exe.lower() == name and table.get(parent, (0, ""))[1].lower() != name and front in lineage(pid, table)]
    if len(sessions) <= 1:
        return True
    titles = {pid: _named(t) for pid, t in titles_of(sessions).items()}
    title = _named(title)
    return bool(title) and titles.get(claude) == title and sum(t == title for t in titles.values()) == 1


def _named(title):
    """A tab's title without what leads it: Claude Code's spinner turns as it works."""
    return re.sub(r"^[\W_]+", "", title or "").strip()


def _print_titles(pids):
    """`console_titles`'s helper: each console's title as JSON on stdout."""
    kernel32.FreeConsole()
    titles = {}
    for pid in pids:
        if kernel32.AttachConsole(pid):
            text = ctypes.create_unicode_buffer(512)
            kernel32.GetConsoleTitleW(text, 512)
            titles[pid] = text.value
            kernel32.FreeConsole()
    sys.stdout.buffer.write(json.dumps(titles).encode("utf-8"))


def verdict(test, away, held, at, looking):
    """What to do with a call now: "go", "wait" or "drop". `away` (no input
    for AWAY_S), `held` (notifications_held), `at` (the pointer, None while
    hidden), `looking` (a function: is_watching, asked only when needed)."""
    if at is None:
        return "wait"
    if test:
        return "go"
    if away:
        return "wait"  # back at the terminal by then, you see for yourself
    if looking():
        return "drop"
    return "wait" if held else "go"


class Magic:
    """Her call's window, and the call flying in it."""

    def __init__(self, root):
        self.root = root
        self.window = None  # made at the first call
        self.call = None  # the call playing
        self.job = None

    def playing(self):
        return self.call is not None

    def send(self, start, sprites, calm=False):
        """Sends her call to the pointer from `start` (desktop px; None:
        from nowhere, she is hidden), drawn with `sprites` (kept: hers may
        go with a hide meanwhile). False when the pointer is hidden."""
        target = pointer()
        if target is None:
            return False
        self.stop()
        if self.window is None:
            self.window = LayeredWindow(hwnd=popup())
        self.call = {"start": start, "target": target, "flight": fx.magic_flight(start, target),
                     "since": time.monotonic(), "ended": None, "sprites": dict(sprites), "calm": calm,
                     "pressed": pressed(), "shown": False}
        self._tick()
        return True

    def _tick(self):
        self.job = None
        call = self.call
        t = time.monotonic()
        age = t - call["since"]
        call["target"] = pointer() or call["target"]
        # Landed, it circles the pointer until a click (a new one: a button
        # held as it came does not count) or until it has circled long enough.
        down = pressed()
        if call["ended"] is None and age >= call["flight"]:
            if (down and not call["pressed"]) or age >= call["flight"] + fx.MAGIC_LINGER_S:
                call["ended"] = age
        call["pressed"] = down
        if fx.magic_over(age, call["ended"]):
            self.stop()
            return
        box = fx.MAGIC_BOX
        image = Image.new("RGBA", (box, box), (0, 0, 0, 0))
        try:
            draws = fx.magic(call["start"], call["target"], call["flight"], age, t, call["ended"], call["calm"])
            fx.paint(image, draws, call["sprites"], (box / 2, box / 2))
        except KeyError:
            self.stop()  # her look changed under it: a sprite it names is not among its own
            return
        x, y = fx.magic_head(call["start"], call["target"], call["flight"], age)
        self.window.show(image, round(x - box / 2), round(y - box / 2))
        if not call["shown"]:
            call["shown"] = True
            self.window.reveal()
        self.job = self.root.after(TICK_MS, self._tick)

    def stop(self):
        """Ends the call at once."""
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        self.call = None
        if self.window:
            self.window.conceal()
            self.window.close()


if __name__ == "__main__" and sys.argv[1:2] == ["titles"]:
    _print_titles([int(pid) for pid in sys.argv[2:] if pid.isdigit()])
