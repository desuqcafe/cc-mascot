"""Which art import_frames.py picks up for a character, and what it makes of it.

    python -m unittest discover -s scripts -p "test_*.py"
"""

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_frames  # noqa: E402


def touch(folder, *names):
    for name in names:
        open(os.path.join(folder, name), "wb").close()


def write_figure(folder, name, left, bottom):
    """A 40x60 canvas with a 10x20 figure whose feet end at (left..left+10, bottom)."""
    img = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    img.paste((200, 0, 0, 255), (left, bottom - 20, left + 10, bottom))
    img.save(os.path.join(folder, name))


class BodyOnly(unittest.TestCase):
    def test_a_symbol_floating_apart_is_dropped(self):
        img = Image.new("RGBA", (60, 80), (0, 0, 0, 0))
        img.paste((0, 200, 200, 255), (10, 10, 40, 75))  # her
        img.paste((0, 200, 200, 255), (10, 40, 45, 45))  # an arm: part of her
        img.paste((255, 255, 255, 255), (48, 2, 56, 8))  # a bubble beside her head
        out = import_frames.body_only(img)
        self.assertEqual(out.getpixel((52, 5))[3], 0)
        self.assertEqual(out.getpixel((25, 50)), (0, 200, 200, 255))
        self.assertEqual(out.getpixel((43, 42)), (0, 200, 200, 255))

    def test_a_big_piece_of_her_stays(self):
        img = Image.new("RGBA", (60, 80), (0, 0, 0, 0))
        img.paste((0, 200, 200, 255), (10, 10, 40, 60))
        img.paste((50, 50, 50, 255), (12, 66, 38, 78))  # boots drawn apart from her legs
        out = import_frames.body_only(img)
        self.assertEqual(out.getpixel((20, 70))[3], 255)

    def test_faint_specks_do_not_join_pieces(self):
        img = Image.new("RGBA", (60, 80), (0, 0, 0, 0))
        img.paste((0, 200, 200, 255), (10, 10, 40, 75))
        img.paste((0, 0, 0, 8), (40, 20, 50, 21))  # a near-invisible smudge from her...
        img.paste((255, 255, 255, 255), (50, 15, 56, 25))  # ...to a symbol
        self.assertEqual(import_frames.body_only(img).getpixel((53, 20))[3], 0)


class ParseArgs(unittest.TestCase):
    def test_defaults_to_miku_and_the_art_folder(self):
        self.assertEqual(import_frames.parse_args([]), ("miku", import_frames.DEFAULT_ART))
        self.assertEqual(import_frames.parse_args(["mine"]), ("miku", "mine"))

    def test_a_character_by_name(self):
        self.assertEqual(import_frames.parse_args(["--character", "Teto"]), ("teto", import_frames.DEFAULT_ART))
        self.assertEqual(import_frames.parse_args(["--character", "teto", "mine"]), ("teto", "mine"))

    def test_what_makes_no_sense(self):
        for argv in (
            ["--character"],
            ["--character", "../frames"],  # a name, never a path
            ["--character", ""],
            ["one", "two"],
            ["mine", "--character", "teto"],  # the option comes first
            ["--character", "teto", "one", "two"],
        ):
            with self.subTest(argv=argv):
                self.assertIsNone(import_frames.parse_args(argv))


class IsFor(unittest.TestCase):
    def test_named_for_the_character(self):
        for name in ("Miku_Idle.png", "miku-happy.png", "MIKU WORKING 1.png"):
            with self.subTest(name=name):
                self.assertTrue(import_frames.is_for(name, "miku"))

    def test_named_for_a_mood_alone_is_anyones(self):
        self.assertTrue(import_frames.is_for("happy.png", "miku"))
        self.assertTrue(import_frames.is_for("Working-2.png", "teto"))

    def test_another_characters_art_is_not(self):
        for name in ("Teto_Idle.png", "Mikuidle.png", "Mikumiku_Idle.png", "first-test.jpg"):
            with self.subTest(name=name):
                self.assertFalse(import_frames.is_for(name, "miku"))
        self.assertFalse(import_frames.is_for("Miku_Idle.png", "mi"))


class FindArt(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        touch(
            self.dir,
            "Miku_Idle.png",
            "Miku_Happy.png",
            "Miku_Working.png",
            "Miku_Error.jpg",  # not a PNG
            "Teto_Idle.png",
            "Teto_Working_2.png",
            "Teto_Working_1.png",
            "sleepy.png",  # a mood alone: either character's
            "notes.txt",
        )

    def found(self, character):
        return {mood: [(n, os.path.basename(p)) for n, p in items] for mood, items in import_frames.find_art(self.dir, character).items()}

    def test_each_character_gets_its_own_art(self):
        self.assertEqual(
            self.found("miku"),
            {
                "idle": [(None, "Miku_Idle.png")],
                "happy": [(None, "Miku_Happy.png")],
                "working": [(None, "Miku_Working.png")],
                "sleepy": [(None, "sleepy.png")],
            },
        )
        self.assertEqual(
            self.found("teto"),
            {
                "idle": [(None, "Teto_Idle.png")],
                "working": [(1, "Teto_Working_1.png"), (2, "Teto_Working_2.png")],
                "sleepy": [(None, "sleepy.png")],
            },
        )

    def test_flipbook_frames_replace_a_single_image(self):
        touch(self.dir, "Miku_Working_2.png", "Miku_Working_1.png")
        self.assertEqual(self.found("miku")["working"], [(1, "Miku_Working_1.png"), (2, "Miku_Working_2.png")])

    def test_a_character_without_art_finds_only_mood_files(self):
        self.assertEqual(self.found("rin"), {"sleepy": [(None, "sleepy.png")]})


class Import(unittest.TestCase):
    def setUp(self):
        self.art = tempfile.mkdtemp()
        self.frames = tempfile.mkdtemp()
        write_figure(self.art, "Teto_Idle.png", left=10, bottom=50)
        write_figure(self.art, "Teto_Happy.png", left=20, bottom=40)  # off to the side, and higher

    def run_main(self, *argv):
        with mock.patch.object(import_frames, "FRAMES_ROOT", self.frames), mock.patch.object(sys, "argv", ["import_frames.py", *argv]):
            with redirect_stdout(StringIO()):
                import_frames.main()
        return os.path.join(self.frames, "teto")

    def test_feet_land_where_idles_do(self):
        out = self.run_main("--character", "teto", self.art)
        self.assertEqual(sorted(os.listdir(out)), ["happy.png", "idle.png"])
        idle, happy = (Image.open(os.path.join(out, f"{m}.png")) for m in ("idle", "happy"))
        self.assertEqual(idle.size, import_frames.SIZE)
        self.assertEqual(import_frames.feet(happy), import_frames.feet(idle))

    def test_a_moods_old_frames_are_replaced(self):
        out = os.path.join(self.frames, "teto")
        os.makedirs(out)
        touch(out, "happy-1.png", "happy-2.png", "working.png")
        self.run_main("--character", "teto", self.art)
        self.assertEqual(sorted(os.listdir(out)), ["happy.png", "idle.png", "working.png"])

    def test_a_rigged_moods_frames_are_kept(self):
        out = os.path.join(self.frames, "teto")
        os.makedirs(out)
        touch(out, "idle-1.png", "idle-2.png")
        with open(os.path.join(out, "moods.json"), "w", encoding="utf-8") as f:
            f.write('{"idle": {"fps": 12, "rigged": true}}')
        self.run_main("--character", "teto", self.art)
        self.assertEqual(sorted(os.listdir(out)), ["happy.png", "idle-1.png", "idle-2.png", "moods.json"])

    def test_rigged_lines_up_with_the_idle_art_all_the_same(self):
        # The rig's frames are lined up with the idle art, so the other moods still are.
        out = os.path.join(self.frames, "teto")
        os.makedirs(out)
        with open(os.path.join(out, "moods.json"), "w", encoding="utf-8") as f:
            f.write('{"idle": {"rigged": true}}')
        self.run_main("--character", "teto", self.art)
        idle_art = Image.open(os.path.join(self.art, "Teto_Idle.png")).convert("RGBA").resize(import_frames.SIZE)
        happy = Image.open(os.path.join(out, "happy.png"))
        self.assertEqual(import_frames.feet(happy), import_frames.feet(idle_art))

    def test_no_idle_is_refused(self):
        os.remove(os.path.join(self.art, "Teto_Idle.png"))
        with self.assertRaises(SystemExit):
            self.run_main("--character", "teto", self.art)
        self.assertFalse(os.path.exists(os.path.join(self.frames, "teto")))


if __name__ == "__main__":
    unittest.main()
