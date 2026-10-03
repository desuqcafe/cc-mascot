"""Her call to the pointer: when it waits, and how it flies (effects.magic).

    python -m unittest discover -s overlay -p "test_*.py"
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects as fx  # noqa: E402
import magic  # noqa: E402

class Calling(unittest.TestCase):
    def test_it_waits_only_for_a_game_or_a_presentation(self):
        self.assertEqual(magic.HELD_STATES, (3, 4))  # not QUNS_BUSY: a fullscreen video shows her

    def test_the_pointer_is_read_shown_or_hidden(self):
        at = magic.pointer()
        self.assertEqual(len(at), 2)
        self.assertTrue(all(isinstance(v, int) for v in at))


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
