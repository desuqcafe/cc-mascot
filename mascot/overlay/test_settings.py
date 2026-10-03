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
        self.assertEqual(cfg.DEFAULTS, (420, False, (300_000, 400_000, 500_000), 2, True, False))

    def test_it_reads_what_was_set(self):
        path = a_file({"size": 560, "calm": True, "aura": [200_000, 250_000, 900_000], "beamAfter": 10, "beamForAgents": False,
                       "checkUpdates": True})
        self.assertEqual(cfg.load(path), (560, True, (200_000, 250_000, 900_000), 10, False, True))
        self.assertEqual(cfg.load(a_file({"checkUpdates": "yes"})).checkUpdates, False)
        self.assertEqual(cfg.load(a_file({"aura": False, "beamAfter": False})).aura, False)
        self.assertEqual(cfg.load(a_file({"aura": False, "beamAfter": False})).beamAfter, False)

    def test_a_bad_value_is_its_default_and_leaves_the_rest(self):
        path = a_file({"size": 9000, "calm": "yes", "aura": [500_000, 400_000, 300_000], "beamAfter": 0, "beamForAgents": 1, "extra": 3})
        self.assertEqual(cfg.load(path), cfg.DEFAULTS)
        self.assertEqual(cfg.load(a_file({"size": True, "calm": True})), cfg.DEFAULTS._replace(calm=True))
        for aura in ([1, 2], [300_000, 300_000, 400_000], [5_000, 20_000, 30_000], "off", None):
            self.assertIsNone(cfg.check("aura", aura), aura)

    def test_a_broken_file_is_no_file(self):
        self.assertEqual(cfg.load(a_file("{size: 3")), cfg.DEFAULTS)
        self.assertEqual(cfg.load(a_file("[1, 2]")), cfg.DEFAULTS)

    def test_numbers_are_whole(self):
        self.assertEqual(cfg.check("size", 333.6), 334)
        self.assertEqual(cfg.check("aura", [300_000.4, 400_000, 500_000]), (300_000, 400_000, 500_000))


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
