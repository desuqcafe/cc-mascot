"""Her call: a round of work over, she sends magic to your pointer,
whichever display it is on (effects.magic draws it). The mod writes the
call into the session file (`call`: {at, test?}) when a round lasted the
`magicAfter` setting's minutes; the overlay hands it here.

It goes at once, whatever window is in front and however long since you
last touched the mouse: neither says where you are looking (a video on one
display, the terminal active on the other). It waits only while a game
runs in exclusive fullscreen or Windows is in presentation mode
(`notifications_held`), and a test call (/mascot magic, the settings
window's button) not even then.

It flies in a window of its own (layered.popup: clicks pass through it and
it never takes the focus), MAGIC_BOX square, moved with the comet and then
the pointer at ANIMATE_FPS for the few seconds it plays, hidden after.
"""

import ctypes
import ctypes.wintypes as wt
import time

from PIL import Image

import effects as fx
from layered import LayeredWindow, popup

# SHQueryUserNotificationState: a Direct3D game in exclusive fullscreen,
# presentation mode. Not QUNS_BUSY (2): a browser's fullscreen video is one,
# and she shows over it.
HELD_STATES = (3, 4)
BUTTONS = (0x01, 0x02, 0x04)  # VK_LBUTTON, VK_RBUTTON, VK_MBUTTON
TICK_MS = round(1000 / fx.ANIMATE_FPS)

user32 = ctypes.windll.user32
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


def notifications_held():
    """Whether Windows holds notifications back now for a fullscreen game
    or a presentation."""
    state = ctypes.c_int()
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    return state.value in HELD_STATES


def pointer():
    """The pointer's tip (desktop px), shown or not (a video hides it while
    it plays: that is where you are looking); None when it cannot be read."""
    at = wt.POINT()
    if not user32.GetCursorPos(ctypes.byref(at)):
        return None
    return at.x, at.y


def pressed():
    """Whether a mouse button is down now."""
    return any(user32.GetAsyncKeyState(button) & 0x8000 for button in BUTTONS)


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
        go with a hide meanwhile). False when the pointer cannot be read."""
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

