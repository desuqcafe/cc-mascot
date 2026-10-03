"""Her call to the pointer: when it goes, whether you are looking, and how
it flies (effects.magic).

    python -m unittest discover -s overlay -p "test_*.py"
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects as fx  # noqa: E402
import magic  # noqa: E402

# A terminal holding a shell holding Claude Code (with a tool it runs), and
# an editor elsewhere: {pid: (parent, exe)}.
TABLE = {
    10: (1, "WindowsTerminal.exe"),
    20: (10, "pwsh.exe"),
    30: (20, "claude.exe"),
    31: (30, "claude.exe"),  # one of its own helpers, not another session
    32: (30, "bash.exe"),
    50: (1, "Code.exe"),
}


class Verdict(unittest.TestCase):
    def verdict(self, test=False, away=False, held=False, at=(5, 5), looking=False):
        asked = []

        def look():
            asked.append(True)
            return looking

        return magic.verdict(test, away, held, at, look), bool(asked)

    def test_it_goes_when_you_are_elsewhere(self):
        self.assertEqual(self.verdict(), ("go", True))

    def test_it_waits_for_you_and_for_the_pointer(self):
        self.assertEqual(self.verdict(away=True), ("wait", False))
        self.assertEqual(self.verdict(at=None), ("wait", False))
        self.assertEqual(self.verdict(held=True), ("wait", True))  # a game: later, unless you are looking

    def test_looking_at_her_session_drops_it(self):
        self.assertEqual(self.verdict(looking=True), ("drop", True))
        self.assertEqual(self.verdict(looking=True, held=True), ("drop", True))

    def test_a_test_goes_as_soon_as_the_pointer_shows(self):
        self.assertEqual(self.verdict(test=True, away=True, held=True, looking=True), ("go", False))
        self.assertEqual(self.verdict(test=True, at=None), ("wait", False))


class Watching(unittest.TestCase):
    def test_her_terminal_in_front_is_looking(self):
        self.assertTrue(magic.is_watching(10, 30, TABLE))
        self.assertTrue(magic.is_watching(20, 30, TABLE))

    def test_another_window_in_front_is_not(self):
        self.assertFalse(magic.is_watching(50, 30, TABLE))
        self.assertFalse(magic.is_watching(0, 30, TABLE))
        self.assertFalse(magic.is_watching(32, 30, TABLE))  # under her, not above

    def test_a_terminal_with_other_sessions_goes_by_its_tabs_title(self):
        table = {**TABLE, 40: (10, "pwsh.exe"), 41: (40, "claude.exe")}
        tabs = {30: "◐ Fix the build", 41: "✳ Write the docs"}

        def titles_of(pids):
            self.assertEqual(sorted(pids), [30, 41])
            return tabs

        # The spinner leading a working session's title turns between reads.
        self.assertTrue(magic.is_watching(10, 30, table, "◑ Fix the build", titles_of))
        self.assertFalse(magic.is_watching(10, 30, table, "✳ Write the docs", titles_of))
        self.assertFalse(magic.is_watching(10, 30, table, "", titles_of))
        self.assertFalse(magic.is_watching(10, 30, table, "Fix the build", lambda pids: {}))  # unreadable: she calls
        tabs[41] = "✳ Fix the build"
        self.assertFalse(magic.is_watching(10, 30, table, "Fix the build", titles_of))  # two alike: no telling
        self.assertTrue(magic.is_watching(20, 30, table))  # her own shell's window is hers alone

    def test_console_titles_reads_a_real_console(self):
        self.assertEqual(magic.console_titles([]), {})
        self.assertEqual(magic.console_titles([4]), {})  # the System process has no console

    def test_lineage_stops_at_a_loop(self):
        self.assertEqual(magic.lineage(1, {1: (2, "a"), 2: (1, "b")}), [1, 2])


class Flight(unittest.TestCase):
    START, TARGET = (100.0, 900.0), (2900.0, 300.0)

    def setUp(self):
        fx.use(fx.MIKU)
        fx.scale_to(fx.BASE_HEIGHT)
        self.flight = fx.magic_flight(self.START, self.TARGET)

    def test_it_flies_longer_the_farther_within_bounds(self):
        low, high = fx.MAGIC_FLIGHT_S
        self.assertEqual(fx.magic_flight(self.START, self.START), low)
        self.assertEqual(self.flight, high)
        self.assertLess(low, fx.magic_flight(self.START, (600, 900)), high)
        self.assertEqual(fx.magic_flight(None, self.TARGET), fx.MAGIC_GATHER_S)

    def test_it_leaves_her_and_lands_on_the_pointer(self):
        self.assertEqual(fx.magic_head(self.START, self.TARGET, self.flight, 0), self.START)
        self.assertEqual(fx.magic_head(self.START, self.TARGET, self.flight, self.flight), self.TARGET)
        self.assertEqual(fx.magic_head(self.START, (5, 5), self.flight, self.flight + 3), (5, 5))  # following it
        self.assertEqual(fx.magic_head(None, self.TARGET, 0.5, 0.1), self.TARGET)  # hidden: it gathers there

    def test_its_arc_bows_upward(self):
        for start, target in ((self.START, self.TARGET), (self.TARGET, self.START), ((0, 0), (0, 800))):
            mx, my = fx.magic_head(start, target, 1.0, 0.5)
            straight = ((start[0] + target[0]) / 2, (start[1] + target[1]) / 2)
            self.assertLessEqual(my, straight[1] + 1e-6, (start, target))
            self.assertGreater(math.dist((mx, my), straight), 1)

    def test_it_stays_inside_its_window(self):
        sprites = fx.build_sprites(fx.BASE_HEIGHT)
        reach = fx.MAGIC_BOX / 2
        for start in (self.START, None):
            for age in [i * 0.05 for i in range(200)]:
                for d in fx.magic(start, self.TARGET, self.flight, age, age, None):
                    self.assertIn(d.sprite, sprites)
                    self.assertLess(math.hypot(d.x, d.y), reach, (start, age, d))

    def test_it_circles_until_dismissed_then_flies_apart(self):
        landed = self.flight + 1.0
        circling = fx.magic(self.START, self.TARGET, self.flight, landed, landed, None)
        self.assertEqual(sum(d.sprite.startswith("note_") for d in circling), 2)
        self.assertIn("heart", [d.sprite for d in circling])
        self.assertFalse(fx.magic_over(landed, None))
        self.assertFalse(fx.magic_over(landed + 0.2, landed))
        self.assertTrue(fx.magic_over(landed + fx.MAGIC_LEAVE_S, landed))

    def test_calm_drops_the_flash_and_burst(self):
        for age in (0.3, self.flight + 0.1):
            loud = fx.magic(self.START, self.TARGET, self.flight, age, age, None)
            calm = fx.magic(self.START, self.TARGET, self.flight, age, age, None, calm=True)
            self.assertLess(len(calm), len(loud))
            self.assertFalse(any(d.sprite.startswith(("flash", "star_gold")) for d in calm))

    def test_it_scales_with_her(self):
        fx.scale_to(fx.BASE_HEIGHT * 1.5)
        try:
            self.assertEqual(fx.MAGIC_BOX, 360)
        finally:
            fx.scale_to(fx.BASE_HEIGHT)

    def test_yunseuls_notes_are_flapping_bats(self):
        fx.use(fx.look_of({"effects": {"style": "gothic"}}))
        try:
            sprites = fx.build_sprites(fx.BASE_HEIGHT)
            landed = self.flight + 1.0
            names = [d.sprite for d in fx.magic(self.START, self.TARGET, self.flight, landed, landed, None)]
            self.assertEqual(sum(n.startswith("bat_") for n in names), 2)
            self.assertTrue(all(n in sprites for n in names))
            later = [d.sprite for d in fx.magic(self.START, self.TARGET, self.flight, landed + 0.1, landed + 0.1, None)]
            self.assertNotEqual(names, later)  # mid-flap
        finally:
            fx.use(fx.MIKU)


if __name__ == "__main__":
    unittest.main()
