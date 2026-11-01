"""Her messenger between sessions (the `messages` setting): one session's
model messages another (the SendMessage tool), and the receiving mascot's
messenger flies over from the sending mascot to her, then brings the
message in (`effects.delivered`).

The engine names neither session to the other (the sender's hook has the
receiver's ListAgents name, the receiver's the sender's, and no plugin
learns its own), so the mods write `sent` and `received` (epoch ms) into
their session files and the receiving overlay pairs its `received` with a
shown peer's `sent` within PAIR_MS (`sender_of`; seen live, 13 ms apart).
The sender's file may land a moment after the receiver's (its hook writes
once the send resolves), so a received message waits up to WAIT_S for its
sender. Nothing at all happens unless both mascots are shown.

The flight goes in a window of its own (layered.popup: clicks pass through
and it never takes the focus), effects.MAGIC_BOX square, moved with the
messenger at ANIMATE_FPS for its second or so; `landed` is called as it
reaches the spot `delivered` starts from.
"""

import ctypes
import ctypes.wintypes as wt
import time

from PIL import Image

import effects as fx
from layered import LayeredWindow, popup

PAIR_MS = 3000  # a `sent` and a `received` this close are one message
WAIT_S = 2.0  # a received message waits this long for its sender's `sent`
TICK_MS = round(1000 / fx.ANIMATE_FPS)

user32 = ctypes.windll.user32
user32.GetWindowRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
user32.IsWindowVisible.argtypes = (wt.HWND,)
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def sender_of(at_ms, peers):
    """Of `peers`, (pid, sent at) of shown mascots' overlays, the pid whose
    `sent` is nearest `at_ms` within PAIR_MS; None for none."""
    near = [(abs(sent - at_ms), pid) for pid, sent in peers if abs(sent - at_ms) <= PAIR_MS]
    return min(near)[1] if near else None


def window_of(pid):
    """(left, top, right, bottom) of process `pid`'s largest visible
    top-level window (desktop px), or None: a mascot's own window (her hover
    card is smaller, and hidden but while hovered)."""
    found = []

    def each(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            rect = wt.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                found.append((rect.left, rect.top, rect.right, rect.bottom))
        return True

    user32.EnumWindows(EnumWindowsProc(each), 0)
    return max(found, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), default=None)


def messenger_spot(rect, height):
    """Where a mascot's messenger stands (desktop px) in her window `rect`,
    at rest (no carry or beam margin): her art is `PAD_LEFT`/`PAD_TOP` in,
    `height` tall and as wide as the window less its pads."""
    left, top, right, _bottom = rect
    width = right - left - fx.PAD_LEFT - fx.PAD_RIGHT
    return left + fx.PAD_LEFT + fx.CALL_AT[0] * width, top + fx.PAD_TOP + fx.CALL_AT[1] * height


class Courier:
    """The window her messenger flies in between mascots, and its flight."""

    def __init__(self, root):
        self.root = root
        self.window = None  # made at the first flight
        self.flight = None
        self.job = None

    def flying(self):
        return self.flight is not None

    def send(self, start, target, height, sprites, landed, calm=False):
        """Flies her messenger from `start` to `target` (desktop px), drawn
        with `sprites` at her `height`; calls `landed` as it gets there."""
        self.stop()
        if self.window is None:
            self.window = LayeredWindow(hwnd=popup())
        self.flight = {"start": start, "target": target, "length": fx.courier_flight(start, target),
                       "since": time.monotonic(), "height": height, "sprites": dict(sprites),
                       "landed": landed, "calm": calm, "shown": False, "handed": False}
        self._tick()

    def _tick(self):
        self.job = None
        flight = self.flight
        t = time.monotonic()
        age = t - flight["since"]
        if not flight["handed"] and age >= flight["length"] - fx.COURIER_HANDOFF_S:
            flight["handed"] = True
            flight["landed"]()  # her own window takes over, crossfading
        if age >= flight["length"]:
            self.stop()
            return
        box = fx.MAGIC_BOX
        image = Image.new("RGBA", (box, box), (0, 0, 0, 0))
        try:
            draws = fx.courier(flight["start"], flight["target"], flight["length"], age, t, flight["height"],
                               flight["calm"])
            fx.paint(image, draws, flight["sprites"], (box / 2, box / 2))
        except KeyError:
            self.stop()  # her look changed under it: a sprite it names is not among its own
            return
        x, y = fx.courier_head(flight["start"], flight["target"], flight["length"], age)
        self.window.show(image, round(x - box / 2), round(y - box / 2))
        if not flight["shown"]:
            flight["shown"] = True
            self.window.reveal()
        self.job = self.root.after(TICK_MS, self._tick)

    def stop(self):
        """Ends the flight at once (its `landed` not called if not yet)."""
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        self.flight = None
        if self.window:
            self.window.conceal()
            self.window.close()  # its bitmap; the window waits for the next flight
