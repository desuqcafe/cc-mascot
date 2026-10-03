"""The layered window staying on top: an ordinary window that got above her
is noticed, and she goes back on top without taking the focus.

    python -m unittest discover -s overlay -p "test_*.py"
"""

import os
import sys
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layered  # noqa: E402

user32 = layered.user32


def above(hwnd):
    """The visible windows above `hwnd`, nearest first."""
    out, h = [], user32.GetWindow(hwnd, layered.GW_HWNDPREV)
    while h:
        if user32.IsWindowVisible(h):
            out.append(h)
        h = user32.GetWindow(h, layered.GW_HWNDPREV)
    return out


def frame_of(widget):
    widget.update_idletasks()
    return user32.GetParent(widget.winfo_id()) or widget.winfo_id()


class KeepOnTop(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry("40x40+10+10")
        self.window = layered.LayeredWindow(self.root)
        self.other = tk.Toplevel(self.root)
        self.other.geometry("40x40+20+20")
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_an_ordinary_window_above_her_is_put_back_under(self):
        other = frame_of(self.other)
        self.other.lift()
        self.root.update()
        self.assertIn(other, above(self.window.hwnd))  # as Windows once left a terminal
        self.assertTrue(self.window.keep_on_top())
        self.assertNotIn(other, above(self.window.hwnd))
        ex = user32.GetWindowLongPtrW(self.window.hwnd, layered.GWL_EXSTYLE)
        self.assertTrue(ex & layered.WS_EX_TOPMOST)
        self.assertFalse(self.window.keep_on_top())  # on top already: nothing to do


def size_of(hwnd):
    r = layered.wt.RECT()
    user32.GetWindowRect(hwnd, layered.ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


class TkSize(unittest.TestCase):
    """Tk is never told her window's size (UpdateLayeredWindow sets it), so
    its own window inside stayed as it was, 200 x 200 seen live: the pointer
    past it was outside her to Tk, which sent <Leave> and hid the hover card,
    and showed it again at once, every half second."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.window = layered.LayeredWindow(self.root)
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_tk_window_inside_follows_each_size(self):
        for size in ((300, 420), (520, 640), (300, 420)):
            self.assertTrue(self.window.show(layered.Image.new("RGBA", size, (0, 0, 0, 255)), 10, 10))
            self.root.update()
            self.assertEqual(size_of(self.window.hwnd), size)
            self.assertEqual(size_of(self.root.winfo_id()), size)


if __name__ == "__main__":
    unittest.main()
