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


if __name__ == "__main__":
    unittest.main()
