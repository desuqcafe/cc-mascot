import math
import os
import unittest

import courier
import effects as fx


class Pairing(unittest.TestCase):
    def test_the_nearest_sent_within_the_pair_window_is_the_sender(self):
        at = 10_000
        self.assertIsNone(courier.sender_of(at, []))
        self.assertEqual(courier.sender_of(at, [(1, at - 13)]), 1)
        self.assertEqual(courier.sender_of(at, [(1, at - 900), (2, at + 20), (3, at - 50)]), 2)
        self.assertIsNone(courier.sender_of(at, [(1, at - courier.PAIR_MS - 1), (2, at + courier.PAIR_MS + 1)]))


class Windows(unittest.TestCase):
    def test_a_process_without_windows_has_none(self):
        self.assertIsNone(courier.window_of(999_999_99))

    def test_a_tk_window_of_this_process_is_found(self):
        import tkinter as tk

        root = tk.Tk()
        try:
            root.geometry("300x200+50+60")
            root.update()
            rect = courier.window_of(os.getpid())
            self.assertIsNotNone(rect)
            self.assertGreaterEqual(rect[2] - rect[0], 300)
        finally:
            root.destroy()

    def test_her_messenger_stands_where_she_calls_from(self):
        h = fx.HEIGHT if hasattr(fx, "HEIGHT") else 420
        w = 280
        rect = (100, 200, 100 + fx.PAD_LEFT + w + fx.PAD_RIGHT, 200 + fx.PAD_TOP + h + 30)
        x, y = courier.messenger_spot(rect, h)
        self.assertAlmostEqual(x, 100 + fx.PAD_LEFT + fx.CALL_AT[0] * w)
        self.assertAlmostEqual(y, 200 + fx.PAD_TOP + fx.CALL_AT[1] * h)


class Flight(unittest.TestCase):
    def setUp(self):
        fx.use(fx.MIKU)

    def tearDown(self):
        fx.use(fx.MIKU)

    def test_it_goes_from_one_to_the_other_and_is_gone_at_the_end(self):
        start, target = (100.0, 500.0), (900.0, 300.0)
        length = fx.courier_flight(start, target)
        low, high = fx.COURIER_FLIGHT_S
        self.assertTrue(low <= length <= high)
        self.assertEqual(fx.courier_head(start, target, length, 0), start)
        end = fx.courier_head(start, target, length, length)
        self.assertTrue(math.isclose(end[0], target[0]) and math.isclose(end[1], target[1]))
        mid = fx.courier_head(start, target, length, length / 2)
        self.assertLess(mid[1], (start[1] + target[1]) / 2 - 50)  # it arcs up over the straight way
        self.assertEqual(fx.courier(start, target, length, length, 1.0, 420), [])

    def test_her_messenger_is_drawn_in_flight_and_fades_as_it_hands_over(self):
        start, target = (0.0, 0.0), (600.0, 0.0)
        length = fx.courier_flight(start, target)
        mid = fx.courier(start, target, length, length / 2, 1.0, 420)
        self.assertIn("messenger", [d.sprite for d in mid])
        self.assertTrue(any(d.sprite.startswith("spark_") for d in mid))  # its trail
        calm = fx.courier(start, target, length, length / 2, 1.0, 420, calm=True)
        self.assertEqual([d.sprite for d in calm], ["messenger"])
        late = fx.courier(start, target, length, length - fx.COURIER_HANDOFF_S / 2, 1.0, 420, calm=True)
        self.assertLess(late[-1].alpha, 1.0)

    def test_yunseul_sends_her_bat_with_its_letter(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "frames", "yunseul", "theme.json"), encoding="utf-8") as f:
            import json

            fx.use(fx.look_of(json.load(f)))
        draws = fx.courier((0.0, 0.0), (600.0, 0.0), 1.0, 0.5, 1.0, 420, calm=True)
        self.assertIn("letter", [d.sprite for d in draws])
        self.assertTrue(any(d.sprite.startswith("bat_") for d in draws))
        sprites = fx.build_sprites(420)
        for d in draws:
            self.assertIn(d.sprite, sprites)


if __name__ == "__main__":
    unittest.main()
