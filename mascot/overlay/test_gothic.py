"""The gothic style (Yunseul's effects): everything effects.py promises,
drawn her way, and Miku's back as she was once it is put away.

    python -m unittest discover -s overlay -p "test_*.py"
"""

import json
import os
import sys
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects as fx  # noqa: E402
import gothic  # noqa: E402

W, H = 280, 420
TALL = fx.PAD_TOP + H + 20
THEME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frames", "yunseul", "theme.json")


def frame():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste((40, 30, 40, 255), (60, 40, 220, 410))
    return img


def visible(draws):
    return [d for d in draws if d.scale > 0.01 and d.alpha > 0.01]


def setUpModule():
    global SPRITES
    with open(THEME, encoding="utf-8") as f:
        fx.use(fx.look_of(json.load(f)))
    SPRITES = fx.build_sprites(H)


def tearDownModule():
    fx.use(fx.MIKU)


class Style(unittest.TestCase):
    def test_her_theme_picks_it(self):
        self.assertIs(fx.STYLE, gothic)

    def test_every_sprite_miku_names_is_drawn_her_way(self):
        fx.use(fx.MIKU)
        miku = fx.build_sprites(H)
        with open(THEME, encoding="utf-8") as f:
            fx.use(fx.look_of(json.load(f)))
        self.assertLessEqual(set(miku), set(SPRITES))
        for name in miku:
            with self.subTest(sprite=name):
                self.assertNotEqual(miku[name].tobytes(), SPRITES[name].tobytes())

    def test_putting_it_away_brings_miku_back(self):
        fx.use(fx.MIKU)
        self.assertIsNone(fx.STYLE)
        self.assertIn("note_main", fx.build_sprites(H))
        self.assertEqual(fx.placements("working", W, H, 5.0, 2.0)[0].sprite.startswith("pip_"), True)
        with open(THEME, encoding="utf-8") as f:
            fx.use(fx.look_of(json.load(f)))

    def test_the_sprites_are_small(self):
        # More than Miku's (bat frames, the banner's wings, mist), still
        # far less than one of her frames.
        self.assertLess(sum(len(img.tobytes()) for img in SPRITES.values()), 700_000)

    def test_ornaments(self):
        for kind in ("note", "notes", "star", "heart"):
            img = fx.ornament(kind, 22, (202, 39, 57), glow=(255, 255, 255), style="gothic")
            self.assertIsNotNone(img.getbbox(), kind)


class Symbols(unittest.TestCase):
    def test_every_mood_but_idle_has_one(self):
        for mood in ("idle", "thinking", "working", "happy", "error", "waiting", "worried", "sleepy", "beam"):
            self.assertEqual(bool(visible(fx.placements(mood, W, H, 10.0, 3.0))), mood != "idle", mood)

    def test_they_pop_in_from_nothing(self):
        for mood in gothic.PLACEMENTS:
            self.assertEqual(visible(fx.placements(mood, W, H, 10.0, 0.0)), [], mood)

    def test_a_moment_always_looks_the_same(self):
        for mood in gothic.PLACEMENTS:
            self.assertEqual(fx.placements(mood, W, H, 7.3, 2.1), fx.placements(mood, W, H, 7.3, 2.1))

    def test_every_sprite_they_use_is_drawn(self):
        for mood in gothic.PLACEMENTS:
            for i in range(200):
                for d in fx.placements(mood, W, H, 3 + i / 30, i / 30):
                    self.assertIn(d.sprite, SPRITES, mood)

    def test_bats_flap(self):
        self.assertEqual({gothic._bat(i / 40, 0) for i in range(40)}, {"bat_main_up", "bat_main_mid", "bat_main_down"})

    def test_they_stay_on_the_window(self):
        for mood in gothic.PLACEMENTS:
            for i in range(300):
                age = i / 30
                pad = fx.BEAM_PAD if mood == "beam" and fx.beam_wide(age) else 0
                for d in fx.placements(mood, W, H, 3 + age, age):
                    if d.alpha < 0.15 or d.scale < 0.05:
                        continue
                    img = SPRITES[d.sprite]
                    half_w, half_h = img.width * d.scale / 2 * 0.7, img.height * d.scale / 2 * 0.7
                    with self.subTest(mood=mood, sprite=d.sprite):
                        self.assertTrue(half_w - fx.PAD_LEFT - pad <= d.x <= W + fx.PAD_RIGHT + pad - half_w, d)
                        self.assertTrue(-fx.PAD_TOP - pad + half_h <= d.y <= H + pad - half_h, d)


class Haunt(unittest.TestCase):
    def test_her_glitch_doubles_and_ripples_her(self):
        out = fx.glitch(frame(), 0.8, 1.0)
        self.assertEqual(out.size, (W, H))
        self.assertNotEqual(out.tobytes(), frame().tobytes())

    def test_a_still_moment_is_left_alone(self):
        f = frame()
        self.assertIs(fx.glitch(f, 0.01, 1.0), f)


class Status(unittest.TestCase):
    def test_nothing_to_show_draws_nothing(self):
        dressed = fx.dress(frame(), fx.CALM, fx.CALM, 9, 5.0, TALL, SPRITES)
        self.assertIsNone(dressed.behind)

    def test_the_blood_moon_rises_behind_her_at_the_top_tier(self):
        size = (fx.PAD_LEFT + W + fx.PAD_RIGHT, TALL)
        two = fx.dress(frame(), fx.Status(2), fx.Status(2), 9, 5.0, TALL, SPRITES)
        three = fx.dress(frame(), fx.Status(3), fx.Status(3), 9, 5.0, TALL, SPRITES)
        self.assertEqual(three.behind.size, size)
        corner = (fx.PAD_LEFT + 40, fx.PAD_TOP + 60)  # beside her head: only the moon reaches it
        self.assertLess(two.behind.getpixel(corner)[3], 30)
        self.assertGreater(three.behind.getpixel(corner)[3], 120)

    def test_the_weekly_limit_fades_her_feet(self):
        dressed = fx.dress(frame(), fx.Status(0, False, True), fx.Status(0, False, True), 9, 5.0, TALL, SPRITES)
        self.assertLess(dressed.frame.getpixel((140, 400))[3], dressed.frame.getpixel((140, 100))[3])

    def test_the_five_hour_limit_lights_candles(self):
        dressed = fx.dress(frame(), fx.Status(0, True), fx.Status(0, True), 9, 5.0, TALL, SPRITES)
        self.assertIsNotNone(dressed.behind.crop((0, fx.PAD_TOP + 380, dressed.behind.width, TALL)).getbbox())

    def test_calm_holds_still(self):
        a = fx.dress(frame(), fx.Status(3, True, True), fx.CALM, 9, 5.0, TALL, SPRITES, calm=True)
        b = fx.dress(frame(), fx.Status(3, True, True), fx.CALM, 9, 5.9, TALL, SPRITES, calm=True)
        self.assertEqual(a.draws, [])
        self.assertEqual(a.behind.tobytes(), b.behind.tobytes())


class Projection(unittest.TestCase):
    def test_she_forms_then_is_whole(self):
        start = fx.projection("intro", frame(), 0.3, 1.0, TALL)
        self.assertIsNone(start.frame.getbbox())  # not there yet: the circle and candles first
        self.assertTrue(start.draws)
        whole = fx.projection("intro", frame(), fx.INTRO_S - 0.01, 9.0, TALL)
        self.assertEqual(whole.frame.tobytes(), frame().tobytes())
        self.assertAlmostEqual(whole.tag, 1.0, places=2)

    def test_she_leaves_in_bats(self):
        gone = fx.projection("outro", frame(), 1.4, 9.0, TALL)
        self.assertIsNone(gone.frame.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
        self.assertTrue(any(d.sprite.startswith("bat_") for d in fx.projection("outro", frame(), 0.9, 9.0, TALL).draws))

    def test_the_lengths_are_effects(self):
        self.assertEqual(fx.act_length("intro"), gothic.INTRO_S)
        self.assertEqual(fx.lock_in(), gothic.INTRO_LOCK_S)
        self.assertEqual(fx.act_length("intro", calm=True), fx.CALM_FADE_S)

    def test_a_channel_change_settles(self):
        self.assertEqual(fx.projection("channel", frame(), fx.CHANNEL_S, 9.0, TALL).frame.tobytes(), frame().tobytes())

    def test_the_carry_ring_is_her_circle(self):
        ring = fx._ring(W, H, 1.0, 0.7)
        self.assertIsNotNone(ring.getbbox())


class Finisher(unittest.TestCase):
    def test_it_fires_wide_then_settles(self):
        image = fx.compose(frame(), [], SPRITES)
        draws = fx.placements("beam", W, H, 5.0, 1.0)
        wide = fx.beamed(image, W, H, 1.0, 5.0, draws, SPRITES)
        self.assertEqual(wide.size, (image.width + 2 * fx.BEAM_PAD, image.height + 2 * fx.BEAM_PAD))
        self.assertTrue(any(d.sprite == "banner" for d in draws))
        self.assertFalse(fx.beam_wide(gothic.BEAM_WIDE_S))

    def test_calm_skips_the_rays(self):
        image = fx.compose(frame(), [], SPRITES)
        calm = fx.beamed(image, W, H, 1.0, 5.0, [], SPRITES, calm=True)
        self.assertEqual(calm.getpixel((5, 5))[3], 0)


if __name__ == "__main__":
    unittest.main()
