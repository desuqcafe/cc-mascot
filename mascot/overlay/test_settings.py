"""The settings file: defaults, what counts as a valid value, and writing it.

    python -m unittest discover -s overlay -p "test_*.py"
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as cfg  # noqa: E402


def a_file(data=None):
    path = os.path.join(tempfile.mkdtemp(), cfg.FILE)
    if data is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
    return path


def raw(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Load(unittest.TestCase):
    def test_no_file_is_todays_behaviour(self):
        self.assertEqual(cfg.load(a_file()), cfg.DEFAULTS)
        self.assertEqual(cfg.DEFAULTS, (420, False, False, (300_000, 400_000, 500_000), 2, True, False, False,
                                        False, 60, cfg.SOUNDS, 30, False, False, False))

    def test_it_reads_what_was_set(self):
        path = a_file({"size": 560, "calm": True, "smooth": True, "aura": [200_000, 250_000, 900_000], "beamAfter": 10,
                       "beamForAgents": False, "magicAfter": 3, "checkUpdates": True, "sound": True, "volume": 35,
                       "sounds": {"magic": True, "done": "ding.mp3"}, "waitingAfter": 90,
                       "nudge": True, "remote": True, "away": True})
        self.assertEqual(cfg.load(path), (560, True, True, (200_000, 250_000, 900_000), 10, False, 3, True, True, 35,
                                          {**cfg.SOUNDS, "magic": True, "done": "ding.mp3"}, 90, True, True, True))
        self.assertEqual(cfg.load(a_file({"nudge": 1, "remote": "on", "away": None}))[-3:], (False, False, False))
        self.assertEqual(cfg.load(a_file({"checkUpdates": "yes"})).checkUpdates, False)
        self.assertEqual(cfg.load(a_file({"aura": False, "beamAfter": False})).aura, False)
        self.assertEqual(cfg.load(a_file({"aura": False, "beamAfter": False})).beamAfter, False)

    def test_a_bad_value_is_its_default_and_leaves_the_rest(self):
        path = a_file({"size": 9000, "calm": "yes", "smooth": 1, "aura": [500_000, 400_000, 300_000], "beamAfter": 0, "beamForAgents": 1, "extra": 3})
        self.assertEqual(cfg.load(path), cfg.DEFAULTS)
        self.assertEqual(cfg.load(a_file({"size": True, "calm": True})), cfg.DEFAULTS._replace(calm=True))
        for aura in ([1, 2], [300_000, 300_000, 400_000], [5_000, 20_000, 30_000], "off", None):
            self.assertIsNone(cfg.check("aura", aura), aura)

    def test_cursor_magic_takes_minutes_from_zero(self):
        self.assertEqual(cfg.check("magicAfter", 0), 0)  # every round
        self.assertEqual(cfg.check("magicAfter", 4.6), 5)
        self.assertIs(cfg.check("magicAfter", False), False)
        for value in (-1, 121, True, "5", None):
            self.assertIsNone(cfg.check("magicAfter", value), value)
        self.assertEqual(cfg.load(a_file({"magicAfter": 0})).magicAfter, 0)

    def test_a_broken_file_is_no_file(self):
        self.assertEqual(cfg.load(a_file("{size: 3")), cfg.DEFAULTS)
        self.assertEqual(cfg.load(a_file("[1, 2]")), cfg.DEFAULTS)

    def test_numbers_are_whole(self):
        self.assertEqual(cfg.check("size", 333.6), 334)
        self.assertEqual(cfg.check("aura", [300_000.4, 400_000, 500_000]), (300_000, 400_000, 500_000))


class Sounds(unittest.TestCase):
    def test_each_moment_is_checked_on_its_own(self):
        sounds = cfg.check("sounds", {"waiting": False, "beam": "../evil.wav", "error": "C:\\x.wav", "magic": "a.ogg",
                                      "intro": "Bell Tower.MP3", "outro": 1, "nope": True})
        self.assertEqual(sounds, {**cfg.SOUNDS, "waiting": False, "intro": "Bell Tower.MP3"})
        for value in ([], "on", None, True):
            self.assertIsNone(cfg.check("sounds", value), value)
        self.assertEqual(cfg.load(a_file({"sounds": "loud"})).sounds, cfg.SOUNDS)

    def test_a_name_is_a_bare_wav_or_mp3(self):
        for name in ("chime.wav", "ベル.mp3", "my bell (2).WAV"):
            self.assertEqual(cfg.sound_choice(name), name)
        for name in ("a/b.wav", "a\\b.wav", "c:x.wav", ".wav", "x.wav ", " x.wav", "x.ogg", "x" * 121 + ".wav", "x\n.wav"):
            self.assertIsNone(cfg.sound_choice(name), name)

    def test_volume_and_waiting(self):
        self.assertEqual(cfg.check("volume", 0), 0)
        self.assertEqual(cfg.check("volume", 99.6), 100)
        self.assertEqual(cfg.check("waitingAfter", 10), 10)
        for key, value in (("volume", 101), ("volume", True), ("waitingAfter", 9), ("waitingAfter", 301)):
            self.assertIsNone(cfg.check(key, value), (key, value))

    def test_the_file_keeps_only_the_moments_changed(self):
        path = a_file()
        cfg.save(path, sound=True, sounds={**cfg.SOUNDS, "waiting": "me.wav", "magic": True})
        self.assertEqual(raw(path), {"sound": True, "sounds": {"waiting": "me.wav", "magic": True}})
        cfg.save(path, sounds={**cfg.SOUNDS, "magic": True})
        self.assertEqual(raw(path)["sounds"], {"magic": True})
        cfg.save(path, sounds=dict(cfg.SOUNDS))
        self.assertEqual(raw(path), {"sound": True})

    def test_a_loaded_default_is_its_own(self):
        prefs = cfg.load(a_file())
        prefs.sounds["done"] = False
        self.assertIs(cfg.DEFAULTS.sounds["done"], True)
        self.assertIs(cfg.SOUNDS["done"], True)


class Save(unittest.TestCase):
    def test_it_keeps_only_what_differs_from_the_defaults(self):
        path = a_file({"note": "mine"})
        cfg.save(path, size=300, calm=False)
        self.assertEqual(raw(path), {"note": "mine", "size": 300})
        cfg.save(path, aura=(100_000, 200_000, 300_000), beamAfter=False)
        self.assertEqual(raw(path)["aura"], [100_000, 200_000, 300_000])
        self.assertEqual(cfg.load(path).beamAfter, False)
        cfg.save(path, size=420, aura=None)
        self.assertEqual(raw(path), {"note": "mine", "beamAfter": False})

    def test_a_bad_value_is_not_written(self):
        path = a_file({"size": 300})
        cfg.save(path, size=10)
        self.assertEqual(raw(path), {})

    def test_reset_brings_back_every_default(self):
        path = a_file({"size": 300, "calm": True, "note": "mine"})
        cfg.reset(path)
        self.assertEqual(raw(path), {"note": "mine"})
        self.assertEqual(cfg.load(path), cfg.DEFAULTS)

    def test_it_makes_the_folder_and_leaves_no_temp_file(self):
        folder = os.path.join(tempfile.mkdtemp(), "mascot")
        cfg.save(os.path.join(folder, cfg.FILE), calm=True)
        self.assertEqual(os.listdir(folder), [cfg.FILE])


if __name__ == "__main__":
    unittest.main()
