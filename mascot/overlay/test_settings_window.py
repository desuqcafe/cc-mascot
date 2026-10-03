"""The settings window: its theme, what each control does to the settings
file, and one window at a time. Built off screen (`show=False`).

    python -m unittest discover -s overlay -p "test_*.py"
"""

import colorsys
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as cfg  # noqa: E402
import settings_window as sw  # noqa: E402

MIKU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frames", "miku")


def saved(app):
    app.flush()
    with open(app.path, encoding="utf-8") as f:
        return json.load(f)


def center(widget):
    x, y, w, h = widget.box
    return x + w / 2, y + h / 2


def click(app, widget, x=None, y=None):
    cx, cy = center(widget)
    x, y = (cx if x is None else x), (cy if y is None else y)
    app.grabbed = widget
    widget.press(x, y)
    app.grabbed = None
    widget.release(x, y)


class Theme(unittest.TestCase):
    def test_mikus_colors(self):
        theme = sw.load_theme(MIKU)
        self.assertEqual((theme.name, theme.primary, theme.accent), ("Miku", (57, 197, 187), (246, 130, 154)))
        self.assertEqual(theme.subtitle, "ミクの設定")

    def test_a_character_without_one_gets_the_fallback(self):
        folder = os.path.join(tempfile.mkdtemp(), "teto")
        os.makedirs(folder)
        with open(os.path.join(folder, sw.THEME_FILE), "w", encoding="utf-8") as f:
            json.dump({"colors": {"primary": "#FF0000", "accent": "pink"}, "name": 3}, f)
        theme = sw.load_theme(folder)
        self.assertEqual(theme.name, "Teto")
        self.assertEqual(theme.primary, (255, 0, 0))
        self.assertEqual(theme.accent, sw.rgb(sw.FALLBACK["accent"]))  # not a color: the fallback's

    def test_teal_and_pink_meet_in_a_pastel_not_gray(self):
        middle = sw.blend((57, 197, 187), (246, 130, 154), 0.5)
        hue, saturation, value = colorsys.rgb_to_hsv(*(c / 255 for c in middle))
        self.assertGreater(saturation, 0.2)
        self.assertGreater(value, 0.85)
        self.assertTrue(0.6 < hue < 0.85, hue)  # lavender
        self.assertEqual(sw.blend((57, 197, 187), (246, 130, 154), 0.0), (57, 197, 187))
        self.assertEqual(sw.blend((57, 197, 187), (246, 130, 154), 1.0), (246, 130, 154))


class Window(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.app = sw.App(self.state, MIKU, show=False, scale=1.0)

    def tearDown(self):
        self.app.root.destroy()

    def widget(self, kind, n=0):
        return [w for w in self.app.widgets if isinstance(w, kind)][n]

    def test_it_draws_at_the_displays_scale(self):
        self.assertEqual(self.app.image().size, (sw.WIDTH, 642))
        big = sw.App(self.state, MIKU, show=False, scale=1.5)
        try:
            self.assertEqual(big.image().size, (round(sw.WIDTH * 1.5), 963))
        finally:
            big.root.destroy()

    def test_a_size_preset_and_the_slider(self):
        choice, slider = self.widget(sw.Choice), self.widget(sw.Slider)
        x, y, w, h = choice.box
        click(self.app, choice, x + w * 0.9)
        self.assertEqual(saved(self.app), {"size": 560})
        # A drag shows at once and is saved when let go.
        sx, sy, sw_, sh = slider.box
        slider.press(sx + 11, sy + sh / 2)
        self.assertEqual(self.app.prefs.size, cfg.SIZE_RANGE[0])
        self.assertEqual(saved(self.app), {"size": 560})
        slider.release(sx + sw_ - 11, sy + sh / 2)
        self.assertEqual(saved(self.app), {"size": cfg.SIZE_RANGE[1]})
        slider.wheel(-1)
        self.assertEqual(saved(self.app), {"size": cfg.SIZE_RANGE[1] - sw.SIZE_STEP})

    def test_letting_go_saves_at_once(self):
        slider = self.widget(sw.Slider)
        x, y, w, h = slider.box
        Event = namedtuple("Event", "x y")
        self.app.on_press(Event(x + 11, y + h / 2))
        self.app.on_drag(Event(x + w / 2, y + h / 2))
        self.assertFalse(os.path.exists(self.app.path))  # not while dragging
        self.app.on_release(Event(x + w - 11, y + h / 2))
        self.assertIsNone(self.app.save_job)
        with open(self.app.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"size": cfg.SIZE_RANGE[1]})
        slider.wheel(-1)  # a wheel's notches are gathered first
        self.assertIsNotNone(self.app.save_job)

    def test_a_drag_redraws_only_what_shows_the_size(self):
        slider = self.widget(sw.Slider)
        x, y, w, h = slider.box
        slider.press(x + 11, y + h / 2)
        before = {id(widget): widget.drawn for widget in self.app.widgets}
        slider.drag(x + w / 2, y + h / 2)
        redrawn = {type(widget).__name__ for widget in self.app.widgets if widget.drawn is not before[id(widget)]}
        self.assertEqual(redrawn, {"Label", "Choice", "Slider", "Preview"})
        self.assertEqual(sum(widget.drawn is not before[id(widget)] for widget in self.app.widgets), 4)

    def test_calm_and_the_agents_toggle(self):
        calm = self.widget(sw.Toggle, 0)
        click(self.app, calm)
        self.assertEqual(saved(self.app), {"calm": True})
        agents = self.widget(sw.Toggle, 3)
        click(self.app, agents)
        self.assertEqual(saved(self.app), {"calm": True, "beamForAgents": False})

    def test_the_aura_off_and_back_on_keeps_its_tiers(self):
        aura, tiers = self.widget(sw.Toggle, 1), self.widget(sw.Tiers)
        x, y, w, h = tiers.box
        # The first knob, dragged far right, stops short of the second.
        first = x + tiers._x(300_000)
        tiers.press(first, y + h * 0.58)
        tiers.drag(x + w, y + h * 0.58)
        tiers.release(x + w, y + h * 0.58)
        self.assertEqual(saved(self.app), {"aura": [390_000, 400_000, 500_000]})
        click(self.app, aura)
        self.assertEqual(saved(self.app), {"aura": False})
        self.assertFalse(tiers.enabled)
        click(self.app, aura)
        self.assertEqual(saved(self.app), {"aura": [390_000, 400_000, 500_000]})

    def test_the_beam_after_long_rounds(self):
        toggle, minutes = self.widget(sw.Toggle, 2), self.widget(sw.Slider, 1)
        x, y, w, h = minutes.box
        minutes.press(x + w - 11, y + h / 2)
        minutes.release(x + w - 11, y + h / 2)
        self.assertEqual(saved(self.app), {"beamAfter": sw.BEAM_SHOWN[1]})
        click(self.app, toggle)
        self.assertEqual(saved(self.app), {"beamAfter": False})
        self.assertFalse(minutes.enabled)
        click(self.app, toggle)
        self.assertEqual(saved(self.app), {"beamAfter": sw.BEAM_SHOWN[1]})

    def test_reset_brings_back_the_defaults(self):
        cfg.save(self.app.path, size=300, calm=True)
        self.app.poll()
        self.assertEqual((self.app.prefs.size, self.app.prefs.calm), (300, True))
        click(self.app, self.widget(sw.Button))
        self.assertEqual(saved(self.app), {})

    def test_a_change_made_elsewhere_shows(self):
        before = self.app.image().tobytes()
        cfg.save(self.app.path, size=600)
        self.app.poll()
        self.assertEqual(self.app.prefs.size, 600)
        self.assertNotEqual(self.app.image().tobytes(), before)

    def test_a_value_past_the_sliders_end_is_kept(self):
        cfg.save(self.app.path, beamAfter=90, aura=(300_000, 400_000, 2_000_000))
        self.app.poll()
        self.app.refresh()
        self.assertEqual((self.app.prefs.beamAfter, self.app.prefs.aura[2]), (90, 2_000_000))
        click(self.app, self.widget(sw.Toggle, 0))  # something else changes
        self.assertEqual(saved(self.app)["beamAfter"], 90)


class Character(unittest.TestCase):
    """The character card: a tile per character, a pick for the session."""

    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.said = []
        self.say, sw.say = sw.say, self.said.append
        self.app = sw.App(self.state, MIKU, show=False, scale=1.0, session="s1", project="webapp")

    def tearDown(self):
        sw.say = self.say
        self.app.root.destroy()

    def tile(self, name):
        tiles = next(w for w in self.app.widgets if isinstance(w, sw.Characters))
        x, y, w, h = tiles.box
        i = [n for n, _, _ in self.app.cast].index(name)
        return tiles, x + (i + 0.5) * (tiles._width() + tiles.gap) - tiles.gap / 2, y + h / 2

    def test_every_character_with_idle_art_has_a_tile(self):
        self.assertEqual([n for n, _, _ in self.app.cast], ["miku", "yunseul"])
        self.assertEqual(self.app.cast[1][1].name, "Yunseul")

    def test_a_pick_tells_the_mod_and_takes_on_her_colors(self):
        before = self.app.image().tobytes()
        tiles, x, y = self.tile("yunseul")
        click(self.app, tiles, x, y)
        self.assertEqual(self.said, ["character yunseul remember"])
        self.assertEqual((self.app.character, self.app.theme.name), ("yunseul", "Yunseul"))
        self.assertNotEqual(self.app.image().tobytes(), before)
        tiles, x, y = self.tile("yunseul")  # the one shown: nothing to do
        click(self.app, tiles, x, y)
        self.assertEqual(len(self.said), 1)

    def test_remember_off_picks_for_this_session_alone(self):
        remember = [w for w in self.app.widgets if isinstance(w, sw.Toggle)][-1]
        click(self.app, remember)
        self.assertFalse(self.app.remember)
        click(self.app, *self.tile("yunseul"))
        self.assertEqual(self.said, ["character yunseul session"])

    def test_it_follows_the_sessions_character(self):
        os.makedirs(os.path.join(self.state, "sessions"))
        with open(os.path.join(self.state, "sessions", "s1.json"), "w", encoding="utf-8") as f:
            json.dump({"frame": "idle", "character": "yunseul"}, f)
        self.app.poll()
        self.assertEqual(self.app.character, "yunseul")
        self.assertEqual(self.said, [])  # the mod knows already


class OneWindow(unittest.TestCase):
    def test_a_second_window_brings_the_first_forward(self):
        state = tempfile.mkdtemp()
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            with open(os.path.join(state, sw.LOCK_FILE), "w", encoding="utf-8") as f:
                json.dump({"pid": holder.pid}, f)
            self.assertFalse(sw.claim(state))
            self.assertTrue(os.path.exists(os.path.join(state, sw.RAISE_FILE)))
        finally:
            holder.kill()
            holder.wait()
        self.assertTrue(sw.claim(state))  # its window is gone: this one is the window
        with open(os.path.join(state, sw.LOCK_FILE), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"pid": os.getpid()})

    def test_another_sessions_window_hands_over(self):
        state = tempfile.mkdtemp()
        # Stands in for the open window: closes once asked to hand over.
        watch = (
            "import json, os, sys, time\n"
            "path = os.path.join(sys.argv[1], 'settings-window.raise')\n"
            "for _ in range(200):\n"
            "    try:\n"
            "        if json.load(open(path)).get('handover'): break\n"
            "    except (OSError, ValueError): pass\n"
            "    time.sleep(0.02)\n"
        )
        holder = subprocess.Popen([sys.executable, "-c", watch, state])
        try:
            with open(os.path.join(state, sw.LOCK_FILE), "w", encoding="utf-8") as f:
                json.dump({"pid": holder.pid, "session": "a"}, f)
            self.assertFalse(sw.claim(state, "a"))  # the same session's: it comes forward
            self.assertTrue(sw.claim(state, "b"))  # another's: it closes for this one
            self.assertIsNotNone(holder.poll())
        finally:
            holder.kill()
            holder.wait()
        with open(os.path.join(state, sw.LOCK_FILE), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"pid": os.getpid(), "session": "b"})


if __name__ == "__main__":
    unittest.main()
