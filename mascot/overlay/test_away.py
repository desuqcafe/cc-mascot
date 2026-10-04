import datetime
import unittest

import away
from away import AWAY_S, NOTE_KEEP_S, Away

T = datetime.datetime(2026, 10, 4, 14, 0).timestamp()  # 14:00 local


def at(minutes):
    return T + minutes * 60


class Away_(unittest.TestCase):
    def test_nothing_while_you_are_here(self):
        notes = Away()
        notes.saw("done", at(1))
        self.assertFalse(notes.step(at(2), idle=10, dark=False))
        self.assertIsNone(notes.note)

    def test_a_note_of_what_happened_while_you_were_idle(self):
        notes = Away()
        notes.saw("done", at(1))  # before you left: not on the note
        notes.step(at(20), idle=AWAY_S + 60, dark=False)  # away since 14:14
        notes.saw("done", at(21))
        notes.saw("error", at(25))
        notes.saw("done", at(30))
        notes.saw("visit", at(31), "Remote Control")
        self.assertTrue(notes.step(at(40), idle=1, dark=False))
        self.assertEqual(notes.lines(), [
            "While you were away (26 min):",
            "  2 rounds of work done, the last at 14:30",
            "  A turn failed at 14:25",
            "  A prompt from Remote Control, the last at 14:31",
        ])

    def test_what_happened_before_away_was_known_counts(self):
        notes = Away()
        notes.saw("waiting", at(16))  # idle since 14:14, known only at 14:20
        notes.step(at(20), idle=6 * 60, dark=False)
        self.assertTrue(notes.step(at(25), idle=0, dark=False))
        self.assertEqual(notes.lines()[1:], ["  Waited on you from 14:16"])

    def test_the_screen_dark_is_away_at_once(self):
        notes = Away()
        notes.step(at(10), idle=3, dark=True)
        notes.saw("beam", at(11))
        self.assertTrue(notes.step(at(12), idle=0, dark=False))
        self.assertEqual(notes.lines()[1:], ["  Work done at 14:11"])

    def test_nothing_happened_no_note(self):
        notes = Away()
        notes.step(at(10), idle=AWAY_S, dark=False)
        self.assertFalse(notes.step(at(30), idle=0, dark=False))
        self.assertIsNone(notes.note)

    def test_read_it_goes_and_it_does_not_wait_forever(self):
        notes = Away()
        notes.step(at(10), idle=0, dark=True)
        notes.saw("done", at(11))
        notes.step(at(12), idle=0, dark=False)
        self.assertTrue(notes.read())
        self.assertIsNone(notes.note)
        self.assertFalse(notes.read())
        notes.step(at(20), idle=0, dark=True)
        notes.saw("done", at(21))
        notes.step(at(22), idle=0, dark=False)
        self.assertTrue(notes.step(at(22) + NOTE_KEEP_S, idle=0, dark=False))
        self.assertIsNone(notes.note)

    def test_away_again_before_reading_one_note_for_both(self):
        notes = Away()
        notes.step(at(10), idle=0, dark=True)
        notes.saw("done", at(11))
        notes.step(at(12), idle=0, dark=False)
        notes.step(at(30), idle=0, dark=True)
        notes.saw("error", at(31))
        notes.step(at(32), idle=0, dark=False)
        self.assertEqual(notes.lines(), ["While you were away (22 min):", "  Work done at 14:11", "  A turn failed at 14:31"])

    def test_channels_by_name(self):
        lines = away.lines_of([away.Moment("visit", at(1), "telegram"), away.Moment("visit", at(2), "Remote Control")])
        self.assertEqual(lines, ["2 prompts from Remote Control, telegram, the last at 14:02"])

    def test_how_long(self):
        self.assertEqual([away.how_long(s) for s in (10, 300, 3600, 3 * 3600 + 5 * 60)], ["1 min", "5 min", "1h 00m", "3h 05m"])

    def test_idle_is_a_number(self):
        self.assertGreaterEqual(away.idle_s(), 0)


if __name__ == "__main__":
    unittest.main()
