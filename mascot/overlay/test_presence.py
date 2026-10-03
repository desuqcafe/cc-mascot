import ctypes
import unittest

import presence


def setting(state, which=presence.DISPLAY_STATE):
    """A POWERBROADCAST_SETTING as Windows hands it over, kept alive."""
    s = presence.SETTING(presence.guid(which), 4, state)
    return s, ctypes.addressof(s)


class Displays(unittest.TestCase):
    def setUp(self):
        self.p = presence.Presence(register=False)
        self.locked, presence.is_locked = presence.is_locked, lambda: False

    def tearDown(self):
        presence.is_locked = self.locked

    def tell(self, state, which=presence.DISPLAY_STATE, kind=presence.PBT_POWERSETTINGCHANGE):
        s, at = setting(state, which)
        self.p._changed(None, kind, at)
        return s

    def test_dark_while_the_displays_are_off(self):
        self.assertFalse(self.p.dark())  # never told: taken as on
        self.tell(0)
        self.assertTrue(self.p.dark())
        self.tell(2)  # dimmed: still seen
        self.assertFalse(self.p.dark())
        self.tell(0)
        self.tell(1)
        self.assertFalse(self.p.dark())

    def test_other_settings_and_messages_say_nothing(self):
        self.tell(0, which=(0x12345678, 1, 2, (0,) * 8))
        self.assertFalse(self.p.dark())
        self.tell(0, kind=0x0007)  # PBT_APMRESUMESUSPEND
        self.assertFalse(self.p.dark())

    def test_dark_while_locked_asked_at_most_every_second(self):
        asked = []
        presence.is_locked = lambda: asked.append(1) or True
        self.assertTrue(self.p.dark(now=100.0))
        self.assertTrue(self.p.dark(now=100.5))
        self.assertEqual(len(asked), 1)
        presence.is_locked = lambda: asked.append(1) or False
        self.assertFalse(self.p.dark(now=100.0 + presence.LOCK_CHECK_S))
        self.assertEqual(len(asked), 2)

    def test_this_desktop_is_not_locked(self):
        self.assertFalse(self.locked())  # the tests run unlocked

    def test_it_registers_with_windows(self):
        live = presence.Presence()
        self.assertTrue(live._handle.value)
        self.assertFalse(live.display_off)  # the screen running the tests is on


if __name__ == "__main__":
    unittest.main()
