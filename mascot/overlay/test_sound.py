"""Her sounds: which file a moment plays, one at a time, and the gate
between mascots. MCI is stood in for: nothing is heard.

    python -m unittest discover -s overlay -p "test_*.py"
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sound  # noqa: E402


class FakeMci:
    """Answers MCI's commands as for files `lengths` (path: ms); keeps what it was told."""

    def __init__(self, lengths):
        self.lengths = lengths
        self.said = []
        self.opened = {}
        self.lock = threading.Lock()

    def __call__(self, command, answer, size, _callback):
        with self.lock:
            self.said.append(command)
        words = command.split()
        if words[0] == "open":
            path = command.split('"')[1]
            if path not in self.lengths:
                return 275  # MCIERR_FILE_NOT_FOUND
            self.opened[words[-1]] = path
        elif words[0] == "status" and answer is not None:
            answer.value = str(self.lengths[self.opened[words[1]]])
        return 0

    def plays(self):
        with self.lock:
            return [c.split()[1] for c in self.said if c.startswith("play ")]

    def wait_for(self, count, timeout=2.0):
        end = time.monotonic() + timeout
        while len(self.plays()) < count and time.monotonic() < end:
            time.sleep(0.005)
        return self.plays()


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"RIFF")
    return path


class Resolve(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.frames = os.path.join(self.root, "frames")
        self.state = os.path.join(self.root, "state")
        self.miku_done = touch(os.path.join(self.frames, "miku", "sounds", "done.wav"))
        self.her_done = touch(os.path.join(self.frames, "yunseul", "sounds", "done.wav"))
        self.mine = touch(os.path.join(self.state, "sounds", "bell.mp3"))

    def test_hers_yours_or_none(self):
        yunseul = os.path.join(self.frames, "yunseul")
        self.assertEqual(sound.resolve(True, "done", yunseul, self.state), self.her_done)
        self.assertEqual(sound.resolve("bell.mp3", "done", yunseul, self.state), self.mine)
        self.assertIsNone(sound.resolve(False, "done", yunseul, self.state))

    def test_a_missing_file_of_yours_plays_hers(self):
        yunseul = os.path.join(self.frames, "yunseul")
        self.assertEqual(sound.resolve("gone.wav", "done", yunseul, self.state), self.her_done)

    def test_a_character_without_her_own_plays_mikus(self):
        other = os.path.join(self.frames, "someone")
        self.assertEqual(sound.resolve(True, "done", other, self.state), self.miku_done)
        self.assertIsNone(sound.resolve(True, "beam", other, self.state))


class Gate(unittest.TestCase):
    def test_another_mascots_sound_holds_it_until_it_ends(self):
        path = os.path.join(tempfile.mkdtemp(), sound.GATE_FILE)
        self.assertFalse(sound.gate_taken(path))
        with open(path, "w") as f:
            json.dump({"until": time.time() + 5, "pid": os.getpid() + 1}, f)
        self.assertTrue(sound.gate_taken(path))
        self.assertFalse(sound.gate_taken(path, now=time.time() + 6))

    def test_its_own_sound_does_not_hold_it_for_itself(self):
        path = os.path.join(tempfile.mkdtemp(), sound.GATE_FILE)
        sound.take_gate(path, 5)
        self.assertFalse(sound.gate_taken(path))
        self.assertEqual(os.listdir(os.path.dirname(path)), [sound.GATE_FILE])

    def test_a_broken_gate_is_open(self):
        path = os.path.join(tempfile.mkdtemp(), sound.GATE_FILE)
        with open(path, "w") as f:
            f.write("{until")
        self.assertFalse(sound.gate_taken(path))


class Playing(unittest.TestCase):
    def setUp(self):
        self.gate = os.path.join(tempfile.mkdtemp(), sound.GATE_FILE)

    def test_it_plays_at_the_volume_and_holds_the_gate_for_its_length(self):
        mci = FakeMci({"a.wav": 1200})
        player = sound.Player(self.gate, mci)
        self.assertTrue(player.play("a.wav", 35, sound.PRIORITY["done"]))
        mci.wait_for(1)
        self.assertIn("setaudio mascot1 volume to 350", mci.said)
        time.sleep(0.05)
        with open(self.gate) as f:
            gate = json.load(f)
        self.assertAlmostEqual(gate["until"] - time.time(), 1.2 + sound.GAP_S, delta=0.2)
        player.close()

    def test_a_sound_that_matters_more_cuts_one_that_matters_less(self):
        mci = FakeMci({"done.wav": 2000, "beam.wav": 3000})
        player = sound.Player(None, mci)
        self.assertTrue(player.play("done.wav", 60, sound.PRIORITY["done"]))
        self.assertFalse(player.play("done.wav", 60, sound.PRIORITY["done"]))  # as much: dropped
        self.assertFalse(player.play("done.wav", 60, sound.PRIORITY["magic"]))
        self.assertTrue(player.play("done.wav", 60, sound.PRIORITY["beam"]))
        mci.wait_for(2)
        self.assertIn("close mascot1", mci.said)
        self.assertEqual(player.playing(), sound.PRIORITY["beam"])
        self.assertTrue(player.play("done.wav", 60, 0, force=True))  # trying one out
        player.close()

    def test_another_mascots_sound_drops_this_one(self):
        with open(self.gate, "w") as f:
            json.dump({"until": time.time() + 5, "pid": os.getpid() + 1}, f)
        mci = FakeMci({"a.wav": 500})
        player = sound.Player(self.gate, mci)
        self.assertFalse(player.play("a.wav", 60, sound.PRIORITY["beam"]))
        self.assertTrue(player.play("a.wav", 60, 0, force=True))
        player.close()

    def test_it_closes_the_sound_once_played_out(self):
        mci = FakeMci({"a.wav": 50})
        player = sound.Player(None, mci)
        player.play("a.wav", 60, 1)
        mci.wait_for(1)
        end = time.monotonic() + 1
        while "close mascot1" not in mci.said and time.monotonic() < end:
            time.sleep(0.01)
        self.assertIn("close mascot1", mci.said)
        self.assertIsNone(player.playing())
        self.assertTrue(player.play("a.wav", 60, 1))
        player.close()

    def test_a_long_file_stops_at_the_cap(self):
        mci = FakeMci({"song.mp3": 240_000})
        player = sound.Player(self.gate, mci)
        player.play("song.mp3", 60, 1)
        mci.wait_for(1)
        time.sleep(0.05)
        with open(self.gate) as f:
            self.assertLessEqual(json.load(f)["until"] - time.time(), sound.MAX_S + sound.GAP_S)
        player.close()

    def test_an_unplayable_file_lets_go_at_once(self):
        mci = FakeMci({})
        player = sound.Player(self.gate, mci)
        self.assertTrue(player.play("broken.mp3", 60, 6))
        end = time.monotonic() + 1
        while player.playing() is not None and time.monotonic() < end:
            time.sleep(0.01)
        self.assertIsNone(player.playing())
        self.assertFalse(sound.gate_taken(self.gate))
        player.close()

    def test_length_of(self):
        self.assertEqual(sound.length_of("a.wav", FakeMci({"a.wav": 1500})), 1.5)
        self.assertIsNone(sound.length_of("a.wav", FakeMci({})))


if __name__ == "__main__":
    unittest.main()
