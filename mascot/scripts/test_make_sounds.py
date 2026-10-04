"""Her own sounds: every character has one per moment, short, in the format
the overlay plays, and the files are what make_sounds.py makes.

    python -m unittest discover -s scripts -p "test_*.py"
"""

import array
import os
import sys
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_sounds  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "overlay"))
import settings as cfg  # noqa: E402
import sound  # noqa: E402

CHARACTERS = sorted(name for name in os.listdir(make_sounds.FRAMES)
                    if os.path.isfile(os.path.join(make_sounds.FRAMES, name, "idle-1.png")))


def samples(path):
    with wave.open(path) as w:
        info = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        data = array.array("h", w.readframes(w.getnframes()))
    return info, data


class Sounds(unittest.TestCase):
    def test_every_character_has_every_moment(self):
        self.assertEqual(make_sounds.MOMENTS, cfg.MOMENTS)
        self.assertEqual(sorted(make_sounds.SOUNDS), CHARACTERS)
        for character in CHARACTERS:
            for moment in cfg.MOMENTS:
                path = os.path.join(make_sounds.FRAMES, character, "sounds", f"{moment}.wav")
                info, data = samples(path)
                self.assertEqual(info, (1, 2, make_sounds.RATE), path)
                self.assertLess(len(data) / make_sounds.RATE, sound.MAX_S, path)
                self.assertLess(max(abs(v) for v in data), 32767 * 0.9, path)  # no clipping

    def test_the_beam_fires_with_the_picture(self):
        for character in CHARACTERS:
            _, data = samples(os.path.join(make_sounds.FRAMES, character, "sounds", "beam.wav"))
            loudest = max(range(len(data)), key=lambda i: abs(data[i])) / make_sounds.RATE
            self.assertGreaterEqual(loudest, make_sounds.CHARGE_S - 0.03, character)
            self.assertLess(loudest, make_sounds.CHARGE_S + 0.4, character)

    def test_the_files_are_what_the_script_makes(self):
        # One moment each (the whole set: make_sounds.py --check).
        for character in CHARACTERS:
            with open(os.path.join(make_sounds.FRAMES, character, "sounds", "waiting.wav"), "rb") as f:
                self.assertEqual(f.read(), make_sounds.make(character, "waiting"), character)

    def test_timings_follow_her_effects(self):
        import effects as fx
        self.assertEqual(make_sounds.CHARGE_S, fx.CHARGE_S)
        self.assertEqual(make_sounds.LOCK_S, fx.INTRO_LOCK_S)

    def test_notes(self):
        self.assertAlmostEqual(make_sounds.note("A4"), 440.0)
        self.assertAlmostEqual(make_sounds.note("A5"), 880.0)
        self.assertAlmostEqual(make_sounds.note("C#5"), make_sounds.note("Db5"))


if __name__ == "__main__":
    unittest.main()
