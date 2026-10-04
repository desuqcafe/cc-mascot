import ctypes
import time
import unittest
from unittest import mock

import terminal
from terminal import Terminal


def a_window():
    """A real top-level window of this process (Tk's), for IsWindow."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.update()
    return root, int(root.wm_frame(), 16)


class Find(unittest.TestCase):
    def test_a_process_without_a_console_has_no_window(self):
        self.assertIsNone(terminal.find(4))  # System: no console to attach to

    def test_a_dead_pid_has_no_window(self):
        self.assertIsNone(terminal.find(999_999_99))


class Terminal_(unittest.TestCase):
    def wait_found(self, term):
        for _ in range(100):
            if term.hwnd:
                return
            time.sleep(0.01)

    def test_it_is_looked_for_once_on_a_thread_then_kept(self):
        root, hwnd = a_window()
        try:
            looked = []
            term = Terminal(1234, finder=lambda pid: looked.append(pid) or hwnd)
            self.assertIsNone(term.window())  # being looked for
            self.wait_found(term)
            self.assertEqual(term.window(), hwnd)
            self.assertEqual(looked, [1234])
        finally:
            root.destroy()

    def test_not_found_is_looked_for_again_later_not_at_every_ask(self):
        looked = []
        term = Terminal(1234, finder=lambda pid: looked.append(pid))
        term.window()
        time.sleep(0.05)
        term.window()
        self.assertEqual(len(looked), 1)
        term.looked -= terminal.FIND_AGAIN_S
        term.window()
        time.sleep(0.05)
        self.assertEqual(len(looked), 2)

    def test_no_pid_no_look(self):
        term = Terminal(None, finder=lambda pid: self.fail("looked"))
        self.assertIsNone(term.window())

    def test_a_call_flashes_once_and_stops(self):
        root, hwnd = a_window()
        try:
            term = Terminal(1, finder=lambda pid: hwnd)
            term.window()
            self.wait_found(term)
            with mock.patch.object(terminal, "flash") as flash:
                term.call(True)
                term.call(True)
                term.call(False)
                term.call(False)
            self.assertEqual(flash.call_args_list, [mock.call(hwnd, True), mock.call(hwnd, False)])
        finally:
            root.destroy()

    def test_a_click_brings_it_forward(self):
        root, hwnd = a_window()
        try:
            term = Terminal(1, finder=lambda pid: hwnd)
            with mock.patch.object(terminal, "bring_forward", return_value=True) as come:
                self.assertTrue(term.come())  # not known yet: looked for at once
                self.assertTrue(term.come())
            self.assertEqual(come.call_args_list, [mock.call(hwnd)] * 2)
            self.assertFalse(Terminal(1, finder=lambda pid: None).come())
        finally:
            root.destroy()


class Flash(unittest.TestCase):
    def test_it_asks_windows_to_flash_until_in_front(self):
        calls = []

        def flash_window_ex(info):
            calls.append((info._obj.hwnd, info._obj.dwFlags))
            return 1

        with mock.patch.object(terminal.user32, "FlashWindowEx", flash_window_ex):
            terminal.flash(42)
            terminal.flash(42, on=False)
        self.assertEqual(calls, [(42, terminal.FLASHW_TRAY | terminal.FLASHW_TIMERNOFG), (42, terminal.FLASHW_STOP)])

    def test_flashinfo_has_windows_size(self):
        self.assertEqual(ctypes.sizeof(terminal.FLASHWINFO), 32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 20)


if __name__ == "__main__":
    unittest.main()
