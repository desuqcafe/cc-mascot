"""The mood symbols, her glitch and her status: what each draws, and when.

    python -m unittest discover -s overlay -p "test_*.py"
"""

import gc
import json
import os
import sys
import unittest

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effects as fx  # noqa: E402

W, H = 280, 420  # a frame at the overlay's height
SPRITES = fx.build_sprites(H)
MOODS = ("idle", "thinking", "working", "happy", "error", "waiting", "worried", "sleepy", "beam")


def frame():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste((0, 200, 200, 255), (60, 40, 220, 410))
    return img


def visible(draws):
    return [d for d in draws if d.scale > 0.01 and d.alpha > 0.01]


class Symbols(unittest.TestCase):
    def test_every_mood_but_idle_has_one(self):
        for mood in MOODS:
            with self.subTest(mood=mood):
                draws = visible(fx.placements(mood, W, H, 10.0, 3.0))
                self.assertEqual(bool(draws), mood != "idle")

    def test_they_pop_in_from_nothing(self):
        for mood in fx.PLACEMENTS:
            with self.subTest(mood=mood):
                self.assertEqual(visible(fx.placements(mood, W, H, 10.0, 0.0)), [])

    def test_a_moment_always_looks_the_same(self):
        for mood in fx.PLACEMENTS:
            with self.subTest(mood=mood):
                self.assertEqual(fx.placements(mood, W, H, 7.3, 2.1), fx.placements(mood, W, H, 7.3, 2.1))

    def test_every_sprite_they_use_is_drawn(self):
        for mood in fx.PLACEMENTS:
            for i in range(200):
                for d in fx.placements(mood, W, H, 3 + i / 30, i / 30):
                    self.assertIn(d.sprite, SPRITES, mood)

    def test_they_stay_on_the_window(self):
        # The window is the frame plus PAD_TOP above and PAD_RIGHT beside
        # (and BEAM_PAD more all round while the beam is wide): a symbol cut
        # off at its edge would show a hard line. A glow's faint rim may
        # cross it.
        for mood in fx.PLACEMENTS:
            for i in range(300):
                age = i / 30
                pad = fx.BEAM_PAD if mood == "beam" and fx.beam_wide(age) else 0
                for d in fx.placements(mood, W, H, 3 + age, age):
                    if d.alpha < 0.15 or d.scale < 0.05:
                        continue
                    img = SPRITES[d.sprite]
                    half_w, half_h = img.width * d.scale / 2 * 0.7, img.height * d.scale / 2 * 0.7
                    with self.subTest(mood=mood, sprite=d.sprite):
                        self.assertTrue(half_w - pad <= d.x <= W + fx.PAD_RIGHT + pad - half_w, d)
                        self.assertTrue(-fx.PAD_TOP - pad + half_h <= d.y <= H + pad - half_h, d)

    def test_the_sprites_are_small(self):
        # The beam's are most of it (its hollow heart is drawn large, to
        # stay crisp as it grows); all of them weigh less than one frame.
        size = sum(len(img.tobytes()) for img in SPRITES.values())
        self.assertLess(size, 450_000)

    def test_sprites_scale_with_her(self):
        bigger = fx.build_sprites(2 * H)
        self.assertAlmostEqual(bigger["speech"].width / SPRITES["speech"].width, 2, delta=0.15)


class Compose(unittest.TestCase):
    def test_she_stands_below_the_pad_with_the_tag_under_her_feet(self):
        tag = Image.new("RGBA", (40, 10), (255, 0, 0, 255))
        out = fx.compose(frame(), [], SPRITES, tag)
        self.assertEqual(out.size, (fx.PAD_LEFT + W + fx.PAD_RIGHT, fx.PAD_TOP + H + fx.UNDER_GAP + 10))
        self.assertEqual(out.getpixel((fx.PAD_LEFT + 100, fx.PAD_TOP + 100)), (0, 200, 200, 255))
        self.assertEqual(out.getpixel((fx.PAD_LEFT + W // 2, fx.PAD_TOP + H + fx.UNDER_GAP + 5)), (255, 0, 0, 255))
        self.assertEqual(out.getpixel((fx.PAD_LEFT + W + 5, 5))[3], 0)
        self.assertEqual(out.getpixel((2, fx.PAD_TOP + 100))[3], 0)  # the aura's room, empty

    def test_a_symbol_is_drawn_over_her(self):
        bare = fx.compose(frame(), [], SPRITES)
        drawn = fx.compose(frame(), fx.placements("waiting", W, H, 5.0, 5.0), SPRITES)
        self.assertNotEqual(bare.tobytes(), drawn.tobytes())

    def test_a_sprite_off_the_canvas_is_skipped(self):
        out = fx.compose(frame(), [fx.Draw("heart", -500, -500), fx.Draw("heart", W + 500, 10)], SPRITES)
        self.assertEqual(out.tobytes(), fx.compose(frame(), [], SPRITES).tobytes())


class Glitch(unittest.TestCase):
    def test_every_mood_change_glitches_for_a_moment(self):
        for mood in MOODS:
            self.assertGreater(fx.glitch_amount(mood, 0.0), 0)
            self.assertEqual(fx.glitch_amount("idle", fx.SWITCH_GLITCH_S), 0)

    def test_error_glitches_hard_then_in_bursts(self):
        self.assertEqual(fx.glitch_amount("error", 0.0), 1)
        self.assertEqual(fx.glitch_amount("error", fx.ERROR_GLITCH_S + 0.5), 0)
        burst = fx.ERROR_GLITCH_S + fx.ERROR_BURST_EVERY - fx.ERROR_BURST_S / 2
        self.assertGreater(fx.glitch_amount("error", burst), 0)
        self.assertGreater(fx.glitch_amount("error", burst + fx.ERROR_BURST_EVERY), 0)
        self.assertEqual(fx.glitch_amount("working", burst), 0)

    def test_no_glitch_leaves_her_be(self):
        img = frame()
        self.assertIs(fx.glitch(img, 0, 1.0), img)

    def test_a_glitch_splits_her_into_teal_and_pink(self):
        out = fx.glitch(frame(), 1.0, 1.0)
        self.assertEqual(out.size, (W, H))
        colors = {out.getpixel((x, y))[:3] for x in range(0, W, 2) for y in range(0, H, 7) if out.getpixel((x, y))[3]}
        self.assertNotEqual(colors, {(0, 200, 200)})
        self.assertEqual(fx.glitch(frame(), 1.0, 1.0).tobytes(), out.tobytes())  # the same moment, the same glitch

    def test_moving(self):
        self.assertTrue(fx.moving("idle", 0.0))  # the switch glitch
        self.assertFalse(fx.moving("idle", 5.0))
        self.assertTrue(fx.moving("sleepy", 5.0))


def tails():
    """Her body and a twin tail beside it with a narrow gap between them."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste((0, 200, 200, 255), (60, 40, 150, 410))
    img.paste((0, 200, 200, 255), (162, 40, 200, 380))
    return img


TALL = fx.PAD_TOP + H + fx.UNDER_GAP + 12  # the window, with a tag 12 px tall


class Status(unittest.TestCase):
    def test_context_tiers(self):
        for tokens, level in ((None, 0), (True, 0), (299_999, 0), (300_000, 1), (450_000, 2), (500_000, 3), (950_000, 3)):
            self.assertEqual(fx.context_level(tokens), level, tokens)

    def test_calm_leaves_her_be(self):
        img = frame()
        look = fx.dress(img, fx.CALM, fx.CALM, 99, 5.0, TALL, SPRITES)
        self.assertIs(look.frame, img)
        self.assertIsNone(look.behind)
        self.assertIsNone(look.over)
        self.assertEqual((look.draws, look.glitch), ([], 0.0))

    def test_the_aura_glows_around_her_not_in_her_gaps(self):
        look = fx.dress(tails(), fx.Status(1), fx.Status(1), 99, 5.0, TALL, SPRITES)
        self.assertEqual(look.behind.size, (fx.PAD_LEFT + W + fx.PAD_RIGHT, TALL))
        beside = look.behind.getpixel((fx.PAD_LEFT + 60 - 4, fx.PAD_TOP + 200))
        gap = look.behind.getpixel((fx.PAD_LEFT + 156, fx.PAD_TOP + 200))
        self.assertGreater(beside[3], 40)
        self.assertEqual(beside[:3], fx.AURA[0][0])
        self.assertLess(gap[3], 10)

    def test_the_aura_warms_up_tier_by_tier(self):
        colors = [fx.dress(frame(), fx.Status(n), fx.Status(n), 99, 5.0, TALL, SPRITES).behind.getpixel((fx.PAD_LEFT + 55, fx.PAD_TOP + 200))[:3]
                  for n in (1, 2, 3)]
        self.assertEqual(colors, [fx.MAIN_LIGHT, fx.ACCENT_LIGHT, fx.HOT])
        self.assertEqual(fx.dress(frame(), fx.Status(1), fx.Status(1), 99, 5.0, TALL, SPRITES).draws, [])
        self.assertTrue(visible(fx.dress(frame(), fx.Status(2), fx.Status(2), 99, 5.0, TALL, SPRITES).draws))
        crackle = fx.dress(frame(), fx.Status(3), fx.Status(3), 99, 5.0, TALL, SPRITES).draws
        self.assertTrue(any(d.sprite.startswith("pixel_") for d in crackle))

    def test_a_change_crossfades(self):
        calm, glowing = fx.CALM, fx.Status(1)
        start = fx.dress(frame(), glowing, calm, 0.0, 5.0, TALL, SPRITES)
        self.assertIsNone(start.behind)  # nothing yet
        mid = fx.dress(frame(), glowing, calm, fx.STATUS_FADE_S / 2, 5.0, TALL, SPRITES).behind.getpixel((fx.PAD_LEFT + 55, fx.PAD_TOP + 200))[3]
        end = fx.dress(frame(), glowing, calm, fx.STATUS_FADE_S, 5.0, TALL, SPRITES).behind.getpixel((fx.PAD_LEFT + 55, fx.PAD_TOP + 200))[3]
        self.assertTrue(0 < mid < end, (mid, end))
        self.assertTrue(fx.status_moving(glowing, calm, 0.5))
        self.assertFalse(fx.status_moving(glowing, calm, fx.STATUS_FADE_S + 1))
        self.assertTrue(fx.status_moving(fx.Status(0, True), fx.Status(0, True), 99))

    def test_the_five_hour_light_is_on_the_floor_and_flickers(self):
        looks = [fx.dress(frame(), fx.Status(0, True), fx.Status(0, True), 99, k / 17, TALL, SPRITES).behind for k in range(170)]
        feet = (fx.PAD_LEFT + 140, fx.PAD_TOP + 410)
        ring = (fx.PAD_LEFT + 140 - round(W * 0.36), fx.PAD_TOP + 410 - round(H * 0.012))
        brightness = [img.getpixel(ring)[3] for img in looks]
        self.assertGreater(max(brightness), 100)
        self.assertLess(min(brightness), max(brightness) * 0.5)  # it sputters
        self.assertEqual(looks[0].getpixel((feet[0], fx.PAD_TOP + 100))[3], 0)  # only on the floor

    def test_the_weekly_fade_makes_her_a_hologram(self):
        look = fx.dress(frame(), fx.Status(0, False, True), fx.Status(0, False, True), 99, 5.0, TALL, SPRITES)
        alphas = {look.frame.getpixel((100, y))[3] for y in range(50, 100)}
        self.assertTrue(max(alphas) < 255 and min(alphas) < max(alphas), alphas)  # see-through, in lines
        self.assertTrue(visible(look.draws))  # bits of her flaking off
        self.assertTrue(look.over.getbbox())  # painted over her

    def test_particles_stay_on_the_window(self):
        for status in (fx.Status(2), fx.Status(3), fx.Status(0, False, True)):
            for k in range(120):
                for d in fx.dress(frame(), status, status, 99, k / 10, TALL, SPRITES).draws:
                    with self.subTest(status=status, sprite=d.sprite):
                        self.assertIn(d.sprite, SPRITES)
                        self.assertTrue(-fx.PAD_LEFT <= d.x <= W + fx.PAD_RIGHT, d)
                        self.assertTrue(-fx.PAD_TOP <= d.y <= H, d)

    def test_her_shape_is_worked_out_once_and_goes_with_her_frame(self):
        img = frame()
        before = len(fx._masks)
        fx.dress(img, fx.Status(3), fx.Status(3), 99, 5.0, TALL, SPRITES)
        fx.dress(img, fx.Status(3), fx.Status(3), 99, 6.0, TALL, SPRITES)
        self.assertEqual(len(fx._masks), before + 1)
        del img
        gc.collect()
        self.assertEqual(len(fx._masks), before)


class Projection(unittest.TestCase):
    """How she comes and goes: the intro, the outro and the channel change."""

    def her_alpha(self, kind, age):
        return fx.projection(kind, frame(), age, 5.0, TALL).frame.getchannel("A").getextrema()[1]

    def test_the_intro_builds_her_from_her_feet_up(self):
        self.assertEqual(self.her_alpha("intro", 0.0), 0)
        mid = fx.projection("intro", frame(), sum(fx.BUILD) / 2, 5.0, TALL).frame
        feet, head = mid.getpixel((100, 400))[3], mid.getpixel((100, 60))[3]
        self.assertGreater(feet, 150)  # there, in a hologram's scanlines
        self.assertLess(head, 60)  # at most the faint ghost of her
        img = frame()
        self.assertIs(fx.projection("intro", img, fx.INTRO_S - 0.01, 5.0, TALL).frame, img)

    def test_the_intro_locks_in_with_a_glitch_and_a_sparkle(self):
        act = fx.projection("intro", frame(), fx.INTRO_LOCK_S + 0.05, 5.0, TALL)
        self.assertGreater(act.glitch, 0.3)
        self.assertTrue(any(d.sprite.startswith("star_") for d in visible(act.draws)))
        self.assertEqual(fx.projection("intro", frame(), 1.0, 5.0, TALL).glitch, 0)

    def test_the_tag_fades_in_and_out(self):
        self.assertEqual(fx.projection("intro", frame(), 0.5, 5.0, TALL).tag, 0)
        self.assertEqual(fx.projection("intro", frame(), fx.INTRO_S, 5.0, TALL).tag, 1)
        self.assertEqual(fx.projection("outro", frame(), 0.0, 5.0, TALL).tag, 1)
        self.assertEqual(fx.projection("outro", frame(), 0.5, 5.0, TALL).tag, 0)

    def test_the_outro_takes_her_away(self):
        self.assertEqual(self.her_alpha("outro", 0.0), 255)
        self.assertEqual(self.her_alpha("outro", fx.DISSOLVE[1] + 0.05), 0)
        self.assertGreater(fx.projection("outro", frame(), 0.05, 5.0, TALL).glitch, 0.5)
        late = fx.projection("outro", frame(), fx.OUTRO_S - 0.01, 5.0, TALL)
        self.assertLess(late.behind.getchannel("A").getextrema()[1], 40)  # the ring has winked out

    def test_the_stage_stands_at_her_feet(self):
        behind = fx.projection("intro", frame(), 1.0, 5.0, TALL).behind
        self.assertEqual(behind.size, (fx.PAD_LEFT + W + fx.PAD_RIGHT, TALL))
        self.assertGreater(behind.getpixel((fx.PAD_LEFT + 140 - round(W * 0.36), fx.PAD_TOP + 405))[3], 100)  # the ring
        beam = max(behind.getpixel((fx.PAD_LEFT + 140 - round(W * 0.34), fx.PAD_TOP + y))[3] for y in range(195, 210))
        self.assertGreater(beam, 20)

    def test_the_channel_changes_quickly(self):
        img = frame()
        self.assertGreater(fx.projection("channel", img, 0.0, 5.0, TALL).glitch, 0.8)
        act = fx.projection("channel", img, fx.CHANNEL_S, 5.0, TALL)
        self.assertIs(act.frame, img)
        self.assertEqual((act.glitch, act.tag, act.draws), (0, 1.0, []))

    def test_a_moment_always_looks_the_same(self):
        for kind in fx.ACT_S:
            a, b = (fx.projection(kind, frame(), 0.9, 3.3, TALL) for _ in range(2))
            self.assertEqual(a.frame.tobytes(), b.frame.tobytes())
            self.assertEqual(a.draws, b.draws)

    def test_bits_stay_on_the_window_and_are_drawn(self):
        for kind in fx.ACT_S:
            for k in range(round(fx.ACT_S[kind] * 30)):
                for d in fx.projection(kind, frame(), k / 30, 3 + k / 30, TALL).draws:
                    with self.subTest(kind=kind, sprite=d.sprite):
                        self.assertIn(d.sprite, SPRITES)
                        self.assertTrue(-fx.PAD_LEFT <= d.x <= W + fx.PAD_RIGHT, d)
                        self.assertTrue(-fx.PAD_TOP <= d.y <= H, d)

    def test_a_faded_tag_keeps_its_size(self):
        tag = Image.new("RGBA", (40, 10), (255, 0, 0, 255))
        self.assertIs(fx.faded(tag, 1.0), tag)
        gone = fx.faded(tag, 0.0)
        self.assertEqual((gone.size, gone.getchannel("A").getextrema()), ((40, 10), (0, 0)))


def carried(path, grip=(140, 100)):
    """A Carry stepped at 30 fps through `path`: [(vx, vy) per tick], then
    dropped and stepped still until it is over (or 5 s)."""
    img = frame()
    carry = fx.Carry(grip, 0.0)
    t = 0.0
    for vx, vy in path:
        t += 1 / 30
        carry.step(t, vx, vy, img)
    carry.drop(t)
    while not carry.over(t) and t < 10:
        t += 1 / 30
        carry.step(t, 0, 0, img)
    return carry, t


class Carry(unittest.TestCase):
    """Picked up, carried and set down."""

    def test_she_leans_back_against_the_motion(self):
        sway = fx.Sway()
        for _ in range(30):
            sway.step(1 / 30, 600)  # carried right, held by her head
        self.assertLess(sway.angle, -5)  # her feet trail left: clockwise
        held_low = fx.Sway()
        for _ in range(30):
            held_low.step(1 / 30, 600, lever=-1)
        self.assertGreater(held_low.angle, 5)
        fast = fx.Sway()
        for _ in range(30):
            fast.step(1 / 30, 50_000)
        self.assertLessEqual(abs(fast.angle), fx.TILT_MAX * 1.3)  # a spring may overshoot a little

    def test_she_sways_back_when_the_motion_stops(self):
        sway = fx.Sway()
        for _ in range(20):
            sway.step(1 / 30, 900)
        angles = [sway.step(1 / 30, 0) for _ in range(60)]
        self.assertGreater(max(angles), 0.5)  # past upright, the other way
        for _ in range(90):
            sway.step(1 / 30, 0)
        self.assertTrue(sway.settled())

    def test_the_lever_follows_the_grip(self):
        self.assertEqual(fx.lever(frame(), (140, 40)), 1)
        self.assertEqual(fx.lever(frame(), (140, 410)), -1)

    def test_a_carry_ends_once_she_has_landed_and_settled(self):
        carry, t = carried([(900, 0)] * 20)
        self.assertTrue(carry.over(t))
        self.assertLess(t - carry.landed, 3)
        self.assertFalse(fx.Carry((1, 1), 0.0).over(99))  # not while held

    def test_only_a_fast_carry_shakes_bits_loose(self):
        img = frame()
        slow, fast = fx.Shaken(), fx.Shaken()
        for k in range(15):
            slow.step(1 / 30, k / 30, 200, 0, img)
            fast.step(1 / 30, k / 30, 1500, 0, img)
        self.assertEqual(slow.bits, [])
        draws = fast.draws(15 / 30)
        self.assertTrue(draws)
        self.assertTrue(all(d.sprite in SPRITES for d in draws))
        self.assertTrue(all(d.x < 230 for d in draws))  # left behind: carried right, they trail left
        for k in range(15, 40):
            fast.step(1 / 30, k / 30, 0, 0, img)
        self.assertEqual(fast.bits, [])  # gone by now

    def test_ghosts_trail_only_a_quick_move(self):
        self.assertIsNone(fx.trail(None, frame(), 100, 0, TALL))
        behind = fx.trail(None, frame(), -1200, 0, TALL)  # moving left: ghosts to her right
        self.assertGreater(behind.getpixel((fx.PAD_LEFT + 220 + 6, fx.PAD_TOP + 200))[3], 0)
        self.assertEqual(behind.getpixel((fx.PAD_LEFT + 60 - 6, fx.PAD_TOP + 200))[3], 0)

    def test_she_lands_with_a_squash_on_her_feet(self):
        img = frame()
        squashed = fx.squash(img, 0.0)
        self.assertEqual(squashed.size, img.size)
        self.assertLess(squashed.getbbox()[1], img.getbbox()[1] + 30)
        self.assertGreater(squashed.getbbox()[1], img.getbbox()[1])  # lower: squashed
        self.assertAlmostEqual(squashed.getbbox()[3], img.getbbox()[3], delta=1)  # feet where they were
        self.assertIs(fx.squash(img, 2.0), img)

    def test_the_canvas_has_room_to_swing_in(self):
        carry = fx.Carry((140, 100), 0.0)
        img = frame()
        carry.step(0.1, 800, 0, img)
        out = carry.draw(img, None, None, [], SPRITES, None, fx.PAD_TOP + H, 0.1)
        self.assertEqual(out.size, (fx.PAD_LEFT + W + fx.PAD_RIGHT + 2 * fx.DRAG_PAD, fx.PAD_TOP + H + 2 * fx.DRAG_PAD))
        self.assertIn("exclaim", [d.sprite for d in fx.held_draws(W, H, 0.5, None)])

    def test_her_symbol_comes_back_as_she_lands(self):
        symbol = [fx.Draw("heart", 100, 100)]
        carry = fx.Carry((140, 100), 0.0)
        carry.drop(1.0)
        bare = carry.draw(frame(), None, None, [], SPRITES, None, fx.PAD_TOP + H, 2.0)
        drawn = carry.draw(frame(), None, None, symbol, SPRITES, None, fx.PAD_TOP + H, 2.0)
        self.assertNotEqual(bare.tobytes(), drawn.tobytes())
        early = carry.draw(frame(), None, None, symbol, SPRITES, None, fx.PAD_TOP + H, 1.1)
        self.assertEqual(early.tobytes(), carry.draw(frame(), None, None, [], SPRITES, None, fx.PAD_TOP + H, 1.1).tobytes())


    def test_a_landing_glitches_like_a_pick_up(self):
        carry = fx.Carry((140, 100), 0.0)
        self.assertGreater(carry.glitch(0.0), 0)
        self.assertEqual(carry.glitch(1.0), 0)
        carry.drop(2.0)
        self.assertGreater(carry.glitch(2.0), 0)  # her held pose swaps out behind it
        self.assertEqual(carry.glitch(2.5), 0)


class Beam(unittest.TestCase):
    """Her big finish: charge, fire, afterglow."""

    def test_it_charges_then_fires(self):
        charging = {d.sprite for d in fx.placements("beam", W, H, 5.0, 0.4)}
        fired = {d.sprite for d in fx.placements("beam", W, H, 5.0, fx.CHARGE_S + 0.3)}
        self.assertIn("core_heart", charging)
        self.assertNotIn("love_heart", charging)
        self.assertTrue({"love_heart", "heart", "banner"} <= fired)
        self.assertNotIn("love_heart", {d.sprite for d in fx.placements("beam", W, H, 5.0, 3.0)})

    def test_she_recoils_only_as_she_fires(self):
        img = frame()
        self.assertIs(fx.recoil(img, 0.3), img)
        self.assertNotEqual(fx.recoil(img, fx.CHARGE_S).tobytes(), img.tobytes())
        self.assertIs(fx.recoil(img, fx.CHARGE_S + 3), img)

    def test_the_burst_has_room_then_the_window_shrinks_back(self):
        image = fx.compose(frame(), [], SPRITES)
        draws = fx.placements("beam", W, H, 5.0, 1.0)
        out = fx.beamed(image, W, H, 1.0, 5.0, draws, SPRITES)
        self.assertEqual(out.size, (image.width + 2 * fx.BEAM_PAD, image.height + 2 * fx.BEAM_PAD))
        self.assertTrue(fx.beam_wide(1.0))
        self.assertFalse(fx.beam_wide(3.0))

    def test_speed_lines_fade_before_the_edge(self):
        lines = fx._speed_lines((400, 500), (200, 220), 60, 1.0, 5.0)
        alpha = lines.getchannel("A")
        self.assertGreater(alpha.getextrema()[1], 0)
        edge = [alpha.getpixel((x, y)) for x in range(400) for y in (0, 499)] +                [alpha.getpixel((x, y)) for y in range(500) for x in (0, 399)]
        self.assertEqual(max(edge), 0)  # no hard line where the window ends
        self.assertEqual(fx._speed_lines((400, 500), (200, 220), 60, 0.0, 5.0).getbbox(), None)


class NewVersion(unittest.TestCase):
    """A new version: her banner over her head, a fountain of stars and notes."""

    def test_the_banner_pops_up_then_goes(self):
        def banner(age):
            return [d for d in visible(fx.updated(W, H, 5.0, age)) if d.sprite == "version"]

        self.assertEqual(banner(0.0), [])
        shown = banner(1.0)
        self.assertEqual(len(shown), 1)
        self.assertLess(shown[0].y, 0)  # above her head
        self.assertEqual(banner(fx.UPDATE_S), [])

    def test_stars_and_notes_rise_around_her(self):
        early = [d for d in visible(fx.updated(W, H, 5.0, 0.3)) if d.sprite != "version"]
        later = [d for d in visible(fx.updated(W, H, 5.0, 1.0)) if d.sprite != "version"]
        self.assertTrue(early and later)
        self.assertLess(min(d.y for d in later), min(d.y for d in early))
        self.assertTrue({d.sprite for d in later} <= set(SPRITES))

    def test_calm_keeps_the_banner_alone(self):
        self.assertEqual({d.sprite for d in visible(fx.updated(W, H, 5.0, 1.0, calm=True))}, {"version"})

    def test_it_draws_with_room_around_her(self):
        sprites = {**SPRITES, "version": fx.version_banner("0.15.0", H)}
        image = fx.compose(frame(), [], sprites)
        out = fx.celebrated(image, fx.updated(W, H, 5.0, 1.0), sprites)
        self.assertEqual(out.size, (image.width + 2 * fx.BEAM_PAD, image.height + 2 * fx.BEAM_PAD))
        top = out.crop((0, 0, out.width, fx.BEAM_PAD + fx.PAD_TOP)).getchannel("A").getbbox()
        self.assertIsNotNone(top)  # the banner, above her

    def test_the_banner_is_in_her_main_color(self):
        banner = fx.version_banner("0.15.0", H)
        self.assertGreater(banner.width, banner.height * 2)
        middle = banner.convert("RGB").getpixel((banner.width // 6, banner.height // 2))
        self.assertLess(sum(abs(a - b) for a, b in zip(middle, fx.MAIN)), 200)


class Messenger(unittest.TestCase):
    """What she tells you besides her mood: her messenger calling, bringing a
    prompt in, her away note."""

    def every(self, fn, ages=(0.0, 0.2, 0.5, 0.8, 1.2, 1.7, 2.3), calm=False):
        return [d for age in ages for d in visible(fn(W, H, 5.0 + age, age, calm))]

    def test_every_sprite_they_use_is_drawn(self):
        for fn in (fx.calling, fx.delivered, fx.noted):
            for calm in (False, True):
                draws = self.every(fn, calm=calm)
                self.assertTrue(draws, fn.__name__)
                self.assertTrue({d.sprite for d in draws} <= set(SPRITES), (fn.__name__, {d.sprite for d in draws} - set(SPRITES)))

    def test_it_calls_in_bursts(self):
        def busy(age):
            return len(visible(fx.calling(W, H, 5.0, age)))

        self.assertGreater(busy(0.5), busy(fx.CALL_RING_S + 0.2))  # ringing, then quiet till the next

    def test_a_delivery_comes_and_goes(self):
        self.assertTrue(visible(fx.delivered(W, H, 5.0, 1.0)))
        self.assertEqual(fx.delivered(W, H, 5.0, fx.DELIVER_S), [])
        self.assertEqual(fx.delivered(W, H, 5.0, -0.1), [])


class Calm(unittest.TestCase):
    """Calm mode: what tells something stays, what flashes or jitters goes."""

    def test_the_status_holds_still_without_particles(self):
        for status in (fx.Status(2), fx.Status(3), fx.Status(0, True), fx.Status(0, False, True), fx.Status(3, True, True)):
            looks = [fx.dress(frame(), status, status, 99, k / 7, TALL, SPRITES, calm=True) for k in range(40)]
            with self.subTest(status=status):
                self.assertEqual({(len(look.draws), look.glitch) for look in looks}, {(0, 0.0)})
                self.assertIsNone(looks[0].over)
                self.assertEqual(len({look.behind.tobytes() for look in looks}), 1)  # no breath, beat or flicker
                self.assertEqual(len({look.frame.tobytes() for look in looks}), 1)  # no band rolling down her
                self.assertFalse(fx.status_moving(status, status, 99, calm=True))
        self.assertTrue(fx.status_moving(fx.Status(1), fx.CALM, 0.5, calm=True))  # a change still crossfades

    def test_the_aura_keeps_its_color_and_the_light_stays_lit(self):
        look = fx.dress(frame(), fx.Status(3, True), fx.Status(3, True), 99, 5.0, TALL, SPRITES, calm=True)
        self.assertEqual(look.behind.getpixel((fx.PAD_LEFT + 55, fx.PAD_TOP + 200))[:3], fx.HOT)
        ring = (fx.PAD_LEFT + 140 - round(W * 0.36), fx.PAD_TOP + 410 - round(H * 0.012))
        self.assertGreater(look.behind.getpixel(ring)[3], 50)

    def test_she_comes_and_goes_in_a_plain_fade(self):
        self.assertEqual(fx.act_length("intro", calm=True), fx.CALM_FADE_S)
        self.assertEqual(fx.lock_in(calm=True), fx.CALM_FADE_S)
        self.assertEqual((fx.act_length("intro"), fx.lock_in()), (fx.INTRO_S, fx.INTRO_LOCK_S))
        for kind in fx.ACT_S:
            for k in range(13):
                act = fx.projection(kind, frame(), k / 30, 5.0, TALL, calm=True)
                with self.subTest(kind=kind, k=k):
                    self.assertEqual((act.behind, act.draws, act.glitch), (None, [], 0.0))
        alpha = lambda kind, age: fx.projection(kind, frame(), age, 5.0, TALL, calm=True).frame.getpixel((100, 100))[3]  # noqa: E731
        self.assertEqual((alpha("intro", 0.0), alpha("intro", fx.CALM_FADE_S)), (0, 255))
        self.assertEqual((alpha("outro", 0.0), alpha("outro", fx.CALM_FADE_S)), (255, 0))
        self.assertTrue(0 < alpha("channel", fx.CALM_FADE_S / 2) < 255)

    def test_the_beam_has_no_flash_or_speed_lines(self):
        image = fx.compose(frame(), [], SPRITES)
        bare = fx.beamed(image, W, H, fx.CHARGE_S + 0.2, 5.0, [], SPRITES, calm=True)
        backdrop = Image.new("RGBA", bare.size, (0, 0, 0, 0))
        backdrop.alpha_composite(image, (fx.BEAM_PAD, fx.BEAM_PAD))
        self.assertEqual(bare.tobytes(), backdrop.tobytes())
        self.assertNotEqual(fx.beamed(image, W, H, fx.CHARGE_S + 0.2, 5.0, [], SPRITES).tobytes(), backdrop.tobytes())

    def test_a_carry_leaves_no_ghosts_or_bits(self):
        img = frame()
        carry = fx.Carry((140, 100), 0.0, calm=True)
        for k in range(1, 30):
            carry.step(k / 30, 2500.0, 0.0, img)
        self.assertEqual(carry.shaken.bits, [])
        drawn = carry.draw(img, None, None, [], SPRITES, None, fx.PAD_TOP + H, 1.0)
        self.assertEqual(drawn.size, (fx.PAD_LEFT + W + fx.PAD_RIGHT + 2 * fx.DRAG_PAD, fx.PAD_TOP + H + 2 * fx.DRAG_PAD))
        self.assertNotEqual(carry.sway.angle, 0)  # she still swings


class Size(unittest.TestCase):
    """At another size the pads grow and shrink with her."""

    def tearDown(self):
        fx.scale_to(fx.BASE_HEIGHT)

    def test_the_pads_follow_her_height(self):
        self.assertEqual((fx.PAD_TOP, fx.PAD_RIGHT, fx.PAD_LEFT, fx.BEAM_PAD, fx.DRAG_PAD), (40, 40, 16, 90, 90))
        fx.scale_to(fx.BASE_HEIGHT * 1.5)
        self.assertEqual((fx.PAD_TOP, fx.PAD_RIGHT, fx.PAD_LEFT, fx.BEAM_PAD, fx.DRAG_PAD, fx.AURA_RADIUS), (60, 60, 24, 135, 135, 14))
        fx.scale_to(fx.BASE_HEIGHT)
        self.assertEqual((fx.PAD_TOP, fx.BEAM_PAD, fx.AURA_RADIUS), (40, 90, 9))

    def test_symbols_keep_their_room_at_any_size(self):
        for height in (240, 640):
            fx.scale_to(height)
            w, h = round(W * height / H), height
            sprites = fx.build_sprites(height)
            for mood in fx.PLACEMENTS:
                for i in range(0, 300, 3):
                    age = i / 30
                    pad = fx.BEAM_PAD if mood == "beam" and fx.beam_wide(age) else 0
                    for d in fx.placements(mood, w, h, 3 + age, age):
                        if d.alpha < 0.15 or d.scale < 0.05:
                            continue
                        img = sprites[d.sprite]
                        half_w, half_h = img.width * d.scale / 2 * 0.7, img.height * d.scale / 2 * 0.7
                        with self.subTest(height=height, mood=mood, sprite=d.sprite):
                            self.assertTrue(half_w - pad <= d.x <= w + fx.PAD_RIGHT + pad - half_w, d)
                            self.assertTrue(-fx.PAD_TOP - pad + half_h <= d.y <= h + pad - half_h, d)

    def test_a_shapes_edge_grows_and_shrinks_as_a_rank_filter_would(self):
        # _shrink and _grow stand in for MinFilter and MaxFilter, which are
        # too slow at a large size: the same pixels, shapes cut off at the
        # canvas's edge and squares wider than the canvas included.
        img = Image.new("L", (37, 23), 40)
        draw = ImageDraw.Draw(img)
        draw.ellipse((-8, 3, 20, 30), fill=255)
        draw.rectangle((24, -2, 33, 9), fill=170)
        img = img.filter(ImageFilter.GaussianBlur(1.3))
        for size in (1, 3, 9, 43):
            with self.subTest(size=size):
                self.assertEqual(fx._shrink(img, size).tobytes(), img.filter(ImageFilter.MinFilter(size)).tobytes())
                self.assertEqual(fx._grow(img, size).tobytes(), img.filter(ImageFilter.MaxFilter(size)).tobytes())

    def test_a_canvas_is_padded_at_her_size(self):
        fx.scale_to(300)
        img = Image.new("RGBA", (200, 300), (0, 200, 200, 255))
        out = fx.compose(img, [], {})
        self.assertEqual(out.size, (fx.PAD_LEFT + 200 + fx.PAD_RIGHT, fx.PAD_TOP + 300))
        self.assertEqual(out.getpixel((fx.PAD_LEFT, fx.PAD_TOP)), (0, 200, 200, 255))


class Look(unittest.TestCase):
    """A character's look: her effects' colors and her beam's call, from her theme.json."""

    def tearDown(self):
        fx.use(fx.MIKU)

    def test_mikus_is_the_default(self):
        for theme in (None, {}, {"effects": "teal"}, {"effects": {"colors": []}}):
            self.assertEqual(fx.look_of(theme), fx.MIKU, theme)
        self.assertEqual((fx.MIKU.colors["MAIN"], fx.MIKU.colors["MAIN_LIGHT"]), ((57, 197, 187), (57, 197, 187)))
        self.assertEqual(fx.MIKU.call, "ミクミクビーム!")

    def test_a_theme_gives_its_own_colors(self):
        look = fx.look_of({"effects": {"colors": {"main": "#102030", "accentLight": "#AABBCC", "pale": "mint", "glitter": "#000000"}}})
        self.assertEqual(look.colors["MAIN"], (16, 32, 48))
        self.assertEqual(look.colors["MAIN_LIGHT"], (16, 32, 48))  # a light left out is its ink
        self.assertEqual(look.colors["ACCENT"], fx.MIKU.colors["ACCENT"])
        self.assertEqual(look.colors["ACCENT_LIGHT"], (170, 187, 204))
        self.assertEqual(look.colors["PALE"], fx.MIKU.colors["PALE"])  # not a color: Miku's
        self.assertEqual(set(look.colors), set(fx.COLORS))

    def test_the_aura_tiers(self):
        look = fx.look_of({"effects": {"colors": {"mainLight": "#010203"}}})
        self.assertEqual(look.aura[0], ((1, 2, 3), fx.MIKU.colors["PALE"]))  # by role, in her colors
        look = fx.look_of({"effects": {"aura": [["#FF0000", "pale"], ["accent", "#00FF00"], ["hot", "blood"]]}})
        self.assertEqual(look.aura, (((255, 0, 0), fx.MIKU.colors["PALE"]), (fx.MIKU.colors["ACCENT"], (0, 255, 0)), fx.MIKU.aura[2]))

    def test_the_call(self):
        look = fx.look_of({"effects": {"call": " ビーム! ", "callPlain": "  "}})
        self.assertEqual((look.call, look.call_plain), ("ビーム!", "MIKU MIKU BEAM!"))
        self.assertTrue(fx.hangul("윤슬"))  # her banner then takes a Korean face
        self.assertFalse(fx.hangul("ミクミクビーム!"))

    def test_she_is_drawn_in_her_look(self):
        red = (200, 30, 50)
        fx.use(fx.look_of({"effects": {"colors": {"main": "#C81E32"}, "aura": [["main", "pale"]]}}))
        dot = fx.build_sprites(H)["dot_main"]
        self.assertEqual(dot.getpixel((dot.width // 2, dot.height // 2))[:3], red)
        aura = fx.dress(frame(), fx.Status(1), fx.Status(1), 99, 5.0, TALL, SPRITES).behind
        self.assertEqual(aura.getpixel((fx.PAD_LEFT + 55, fx.PAD_TOP + 200))[:3], red)
        fx.use(fx.MIKU)
        again = fx.build_sprites(H)
        self.assertEqual([again[k].tobytes() for k in sorted(again)], [SPRITES[k].tobytes() for k in sorted(SPRITES)])

    def test_every_characters_theme_is_read_whole(self):
        frames = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frames")
        for name in os.listdir(frames):
            path = os.path.join(frames, name, "theme.json")
            if not os.path.isfile(path):
                continue
            with self.subTest(character=name), open(path, encoding="utf-8") as f:
                effects = json.load(f).get("effects", {})
                for key, value in effects.get("colors", {}).items():
                    self.assertIn(fx._role(key), fx.COLORS, key)
                    self.assertIsNotNone(fx._hex(value), key)
                for pair in effects.get("aura", []):
                    self.assertTrue(all(fx._hex(c) or fx._role(c) in fx.COLORS for c in pair), pair)
                self.assertEqual(set(effects) - {"colors", "aura", "call", "callPlain", "style"}, set())
                self.assertIn(effects.get("style"), [None, *fx.STYLES])

    def test_a_style_is_read_by_name(self):
        self.assertEqual(fx.look_of({"effects": {"style": "gothic"}}).style, "gothic")
        for style in ("baroque", 3, None):
            self.assertIsNone(fx.look_of({"effects": {"style": style}}).style)
        self.assertIsNone(fx.MIKU.style)


if __name__ == "__main__":
    unittest.main()
