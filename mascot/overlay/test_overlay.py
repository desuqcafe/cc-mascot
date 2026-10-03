"""The overlay's frames, its hover card, its session file and the spots
several overlays share.

    python -m unittest discover -s overlay -p "test_*.py"
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mascot_overlay as overlay  # noqa: E402


def use_state_dir(key="me"):
    """A fresh mascot folder, with this test as session `key`'s overlay."""
    state = tempfile.mkdtemp()
    overlay.configure("", os.path.join(state, "sessions", f"{key}.json"))
    os.makedirs(overlay.SESSIONS_DIR)
    return state


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))


def make_old(path, seconds):
    then = time.time() - seconds
    os.utime(path, (then, then))


def gone_pid():
    """The pid of a process that has exited."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def write_png(folder, name, color):
    """A figure of `color` on a transparent canvas, as the real frames are."""
    img = Image.new("RGBA", (20, 30), (0, 0, 0, 0))
    img.paste(color, (5, 5, 15, 25))
    img.save(os.path.join(folder, f"{name}.png"))


def middle(img):
    return img.getpixel((img.width // 2, img.height // 2))


def built(art, mood):
    """The frames `mood` plays once its background build is done."""
    deadline = time.monotonic() + 5
    while True:
        frames, _ = art.get(mood)
        if mood == "idle" or frames is not art.frames["idle"] or not art.paths.get(mood) or time.monotonic() > deadline:
            return frames
        time.sleep(0.01)


class Frames(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        overlay.FRAMES_DIR = self.dir

    def art(self, keep=overlay.KEEP_MOODS):
        art = overlay.Art(keep)
        self.assertTrue(art.load())
        return art

    def test_a_mood_without_art_plays_idles_frames(self):
        write_png(self.dir, "idle-1", (0, 200, 200, 255))
        write_png(self.dir, "idle-2", (0, 100, 200, 255))
        write_png(self.dir, "happy", (255, 200, 0, 255))
        art = self.art()
        self.assertEqual([middle(f)[:3] for f in built(art, "happy")], [(255, 200, 0)])
        self.assertEqual([middle(f)[:3] for f in built(art, "idle")], [(0, 200, 200), (0, 100, 200)])
        for mood in ("thinking", "waiting", "sleepy"):
            self.assertIs(art.get(mood)[0], art.frames["idle"])  # the same frames, not copies

    def test_a_mood_plays_idles_frames_until_its_own_are_built(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        write_png(self.dir, "error", (200, 0, 0, 255))
        art = self.art()
        self.assertEqual(set(art.frames), {"idle"})  # only idle's are built on show
        gate = overlay.threading.Event()
        prepare = overlay.prepare
        overlay.prepare = lambda path, height: gate.wait(5) and prepare(path, height)
        try:
            self.assertIs(art.get("error")[0], art.frames["idle"])
        finally:
            gate.set()
            overlay.prepare = prepare
        self.assertEqual([middle(f)[:3] for f in built(art, "error")], [(200, 0, 0)])

    def test_only_the_moods_used_last_stay_built(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        for mood in ("thinking", "working", "happy"):
            write_png(self.dir, mood, (200, 0, 0, 255))
        art = self.art(keep=2)
        for mood in ("thinking", "working", "thinking", "happy"):
            built(art, mood)
        self.assertEqual(set(art.frames), {"idle", "thinking", "happy"})  # working was used longest ago

    def test_a_build_finishing_after_a_hide_is_dropped(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        write_png(self.dir, "happy", (255, 200, 0, 255))
        art = self.art()
        gate = overlay.threading.Event()
        prepare = overlay.prepare
        overlay.prepare = lambda path, height: gate.wait(5) and prepare(path, height)
        try:
            art.get("happy")
            art.clear()
        finally:
            gate.set()
            overlay.prepare = prepare
        time.sleep(0.2)
        self.assertEqual(art.frames, {})

    def test_the_held_pose_plays_her_moods_frames_until_built(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        write_png(self.dir, "working", (9, 9, 9, 255))
        art = self.art()
        working = built(art, "working")
        self.assertFalse(art.has("held"))
        self.assertIs(art.get("held", instead=(working, 12))[0], working)  # no held art: her mood's loop
        write_png(self.dir, "held", (200, 0, 200, 255))
        art = self.art()
        working = built(art, "working")
        gate = overlay.threading.Event()
        prepare = overlay.prepare
        overlay.prepare = lambda path, height: gate.wait(5) and prepare(path, height)
        try:
            self.assertIs(art.get("held", instead=(working, 12))[0], working)
        finally:
            gate.set()
            overlay.prepare = prepare
        deadline = time.monotonic() + 5
        while art.get("held", instead=(working, 12))[0] is working and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual([middle(f)[:3] for f in art.get("held")[0]], [(200, 0, 200)])

    def test_a_new_size_is_built_apart_and_taken_on_whole(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        write_png(self.dir, "working", (9, 9, 9, 255))
        art = self.art()
        playing = art.frames["idle"]
        built = overlay.build_art(300, ["working"])
        self.assertIs(art.frames["idle"], playing)  # she plays on at her old size meanwhile
        art.adopt(built)
        self.assertEqual((art.height, art.size()[1]), (300, 300))
        working, _ = art.get("working")
        self.assertIs(working, built.frames["working"])  # her mood came built with it
        self.assertEqual(working[0].height, 300)
        os.remove(os.path.join(self.dir, "idle.png"))
        self.assertIsNone(overlay.build_art(300))  # no idle art: nothing to take on

    def test_a_moods_build_at_the_old_size_is_dropped(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        write_png(self.dir, "happy", (255, 200, 0, 255))
        art = self.art()
        gate = overlay.threading.Event()
        prepare = overlay.prepare
        overlay.prepare = lambda path, height: gate.wait(5) and prepare(path, height)
        try:
            art.get("happy")  # building at the old size...
            art.adopt(overlay.build_art(300))  # ...as the new one is taken on
        finally:
            gate.set()
            overlay.prepare = prepare
        time.sleep(0.2)
        self.assertEqual(set(art.frames), {"idle"})
        self.assertEqual(built(art, "happy")[0].height, 300)  # built again, at the new size

    def test_numbered_frames_play_in_order(self):
        write_png(self.dir, "idle", (0, 200, 200, 255))
        write_png(self.dir, "working", (9, 9, 9, 255))  # ignored once numbered frames exist
        write_png(self.dir, "working-2", (0, 0, 200, 255))
        write_png(self.dir, "working-1", (200, 0, 0, 255))
        frames = built(self.art(), "working")
        self.assertEqual([middle(f)[:3] for f in frames], [(200, 0, 0), (0, 0, 200)])

    def test_soft_edges_stay_soft(self):
        img = Image.new("RGBA", (20, 30), (0, 0, 0, 0))
        img.paste((0, 200, 200, 255), (5, 5, 15, 25))
        img.paste((0, 200, 200, 100), (5, 25, 15, 30))  # a half-clear hem
        img.save(os.path.join(self.dir, "idle.png"))
        idle = self.art().frames["idle"][0]
        self.assertEqual(idle.mode, "RGBA")
        self.assertEqual(idle.getpixel((0, 0))[3], 0)
        hem = idle.getpixel((idle.width // 2, idle.height - 3))[3]
        self.assertTrue(0 < hem < 255, hem)

    def test_no_idle_art_builds_nothing(self):
        write_png(self.dir, "happy", (255, 200, 0, 255))
        art = overlay.Art()
        self.assertFalse(art.load())
        self.assertEqual(art.frames, {})


class FrameRates(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        overlay.FRAMES_DIR = self.dir
        for i in (1, 2, 3):
            write_png(self.dir, f"idle-{i}", (0, 200, 200, 255))
        write_png(self.dir, "happy", (255, 200, 0, 255))

    def test_moods_json_sets_a_moods_speed(self):
        write(os.path.join(self.dir, "moods.json"), {"idle": {"fps": 12, "rigged": True}, "happy": {"fps": 24}})
        rates = overlay.frame_rates()
        self.assertEqual(rates["idle"], 12)
        self.assertEqual(rates["happy"], 24)

    def test_a_mood_without_art_plays_at_idles_speed(self):
        write(os.path.join(self.dir, "moods.json"), {"idle": {"fps": 12}, "sleepy": {"fps": 2}})
        self.assertEqual(overlay.frame_rates()["sleepy"], 12)  # it plays idle's frames

    def test_without_moods_json_every_mood_plays_at_the_flipbook_speed(self):
        rates = overlay.frame_rates()
        self.assertEqual(set(rates), set(overlay.MOODS + overlay.POSES))
        self.assertTrue(all(fps == overlay.FLIPBOOK_FPS for fps in rates.values()))

    def test_nonsense_falls_back(self):
        write(os.path.join(self.dir, "moods.json"), {"idle": {"fps": 0}, "happy": [], "error": {"fps": True}})
        rates = overlay.frame_rates()
        self.assertEqual(rates["idle"], overlay.FLIPBOOK_FPS)
        self.assertEqual(rates["happy"], overlay.FLIPBOOK_FPS)
        write(os.path.join(self.dir, "moods.json"), "not json")
        self.assertEqual(overlay.frame_rates()["idle"], overlay.FLIPBOOK_FPS)


class NextTick(unittest.TestCase):
    def test_ticks_when_the_next_frame_is_due(self):
        self.assertEqual(overlay.next_tick_ms(0.0, 12, 36, overlay.TICK_MS), 33)  # due in 83 ms: capped while moving
        self.assertEqual(overlay.next_tick_ms(0.0, 12, 36, overlay.STILL_TICK_MS), 84)  # nothing else moves: wait for it
        self.assertEqual(overlay.next_tick_ms(0.070, 12, 36, overlay.TICK_MS), 14)  # frame 1 is due at 83.3 ms
        self.assertEqual(overlay.next_tick_ms(1.0, 60, 36, overlay.TICK_MS), 17)  # 60 fps: every 16.7 ms

    def test_every_frame_of_a_loop_shows_equally_long(self):
        for cap in (overlay.TICK_MS, overlay.STATUS_TICK_MS, overlay.STILL_TICK_MS):
            t, shown, last = 0.0, [], 0
            for _ in range(400):
                t += overlay.next_tick_ms(t, 12, 36, cap) / 1000
                index = int(t * 12)
                if index != last:
                    shown.append(t)
                    last = index
            lengths = [b - a for a, b in zip(shown, shown[1:])]
            self.assertLess(max(lengths) - min(lengths), 0.002, cap)

    def test_a_still_picture(self):
        self.assertEqual(overlay.next_tick_ms(5.0, 6, 1, overlay.TICK_MS), overlay.TICK_MS)  # its symbol moves
        self.assertEqual(overlay.next_tick_ms(5.0, 6, 1, overlay.STILL_TICK_MS), overlay.STILL_TICK_MS)


class Tag(unittest.TestCase):
    def test_the_tag_fits_its_text_in_the_cards_colors(self):
        short, long = overlay.tag_image("app", 12), overlay.tag_image("a much longer project", 12)
        self.assertEqual(short.height, long.height)
        self.assertLess(short.width, long.width)
        self.assertEqual(short.getpixel((0, 0))[:3], (0x4A, 0x4A, 0x5E))  # CARD_EDGE
        self.assertEqual(short.getpixel((2, 2))[:3], (0x1F, 0x1F, 0x28))  # CARD_BG


NOW_MS = 1_790_000_000_000


class Card(unittest.TestCase):
    def test_a_calm_session(self):
        resets = datetime.datetime.fromtimestamp(NOW_MS / 1000 + 2 * 3600, datetime.timezone.utc)
        info = {
            "project": "my-app",
            "branch": "main",
            "model": "Opus 5.5",
            "startedAt": NOW_MS - 42 * 60_000,
            "prompts": 12,
            "context": {"tokens": 164_000, "window": 1_000_000, "percent": 16, "perTurn": 9_000, "turnsToCompact": 70},
            "limits": [{"kind": "five_hour", "percent": 23, "resetsAt": resets.isoformat().replace("+00:00", "Z")}],
            "subagents": [],
            "background": {},
            "sessionId": "1f510c20-bd3b-4c7f-86c3-299d0d168c9c",
        }
        title, lines = overlay.card_lines("idle", info, NOW_MS)
        self.assertEqual(title, "my-app · main")
        self.assertEqual(
            lines,
            [
                ("bar", "Context", 16, " 16%  164k/1M"),
                "          +9k/turn · ~70 turns to compact",
                ("bar", "5h limit", 23, f" 23%  resets {resets.astimezone():%H:%M}"),
                "Opus 5.5 · 42 min · 12 prompts",
                "Now: idle",
                ("dim", "Session 1f510c20"),
            ],
        )

    def test_a_busy_turn(self):
        info = {
            "tool": "Bash",
            "turnSince": NOW_MS - 134_000,
            "subagents": [
                {"type": "Explore", "tokens": 45_000, "percent": 5},
                {"type": "general-purpose", "tokens": 120_000},
                {"type": "Plan"},
            ],
            "background": {"workflow": 1, "shell": 2},
        }
        _title, lines = overlay.card_lines("working", info, NOW_MS)
        self.assertEqual(
            lines,
            [
                "Now: working (Bash) · 2m 14s",
                "Subagents:",
                "  Explore          45k (5%)",
                "  general-purpose  120k",
                "  Plan             starting",
                "Background: 2 shells, 1 workflow",
            ],
        )

    def test_nothing_written_yet(self):
        title, lines = overlay.card_lines("idle", {}, NOW_MS)
        self.assertEqual((title, lines), ("Claude Code", ["Now: idle"]))

    def test_her_status_comes_from_the_figures(self):
        soon, gone = "2026-10-02T16:40:00.000Z", "2026-10-02T15:00:00.000Z"
        now = datetime.datetime(2026, 10, 2, 16, 10, tzinfo=datetime.timezone.utc).timestamp() * 1000
        five = lambda pct, at=soon: {"kind": "five_hour", "percent": pct, "resetsAt": at}
        week = lambda pct, at=soon: {"kind": "seven_day", "percent": pct, "resetsAt": at}
        status = overlay.status_of
        self.assertEqual(status({}, [], now), overlay.fx.CALM)
        self.assertEqual(status({"context": {"tokens": 410_000}}, [], now).context, 2)
        self.assertTrue(status({"limits": [five(91)]}, [], now).five_hour)
        self.assertFalse(status({"limits": [five(89)]}, [], now).five_hour)
        self.assertFalse(status({"limits": [five(99, gone)]}, [], now).five_hour)  # that window has reset
        self.assertTrue(status({"limits": [week(90)]}, [], now).weekly)
        self.assertTrue(status({"limits": [five(40)]}, [[five(93)]], now).five_hour)  # another session read it later
        # The aura setting's tiers; none: no aura.
        self.assertEqual(status({"context": {"tokens": 410_000}}, [], now, (100_000, 200_000, 400_000)).context, 3)
        self.assertEqual(status({"context": {"tokens": 910_000}}, [], now, ()).context, 0)

    def test_the_freshest_limits_win(self):
        five = lambda pct, at="2026-10-02T16:40:00.000Z": {"kind": "five_hour", "percent": pct, "resetsAt": at}  # noqa: E731
        week = {"kind": "seven_day", "percent": 79, "resetsAt": "2026-10-07T02:00:00.000Z"}
        newer_week = {**week, "percent": 80}
        # Another session read them later: higher in the same window.
        self.assertEqual(overlay.freshest_limits([[five(8), week], [five(9), newer_week]]), [five(9), newer_week])
        # A reset window beats a fuller old one; a reset time a few seconds off is the same window.
        self.assertEqual(overlay.freshest_limits([[five(95)], [five(2, "2026-10-02T21:40:00.000Z")]]), [five(2, "2026-10-02T21:40:00.000Z")])
        self.assertEqual(overlay.freshest_limits([[five(9, "2026-10-02T16:40:20Z")], [five(8)]]), [five(9, "2026-10-02T16:40:20Z")])
        # Nothing read, or junk, leaves the rest standing.
        self.assertEqual(overlay.freshest_limits([None, [], [{"kind": "five_hour"}, "x"], [week]]), [week])

    def test_tag_names_the_project(self):
        self.assertEqual(overlay.tag_text("my-app", 0, [(0, "my-app"), (1, "other")]), "my-app")
        self.assertEqual(overlay.tag_text(None, 0, []), "Claude Code")

    def test_tags_of_one_project_are_numbered_by_spot(self):
        peers = [(3, "app"), (0, "app"), (1, "web")]
        self.assertEqual(overlay.tag_text("app", 0, peers), "app ·1")
        self.assertEqual(overlay.tag_text("app", 3, peers), "app ·2")

    def test_a_long_tag_is_cut(self):
        tag = overlay.tag_text("a-very-long-project-folder-name", 0, [(0, "a-very-long-project-folder-name")] * 2)
        self.assertEqual(len(tag), overlay.TAG_CHARS)
        self.assertTrue(tag.endswith("… ·1"))


class NewVersionHint(unittest.TestCase):
    def test_the_card_says_a_newer_version_is_out(self):
        _, lines = overlay.card_lines("idle", {"newVersion": "0.16.0"}, NOW_MS)
        self.assertIn("v0.16.0 is out \u00b7 /mascot update", lines)
        _, lines = overlay.card_lines("idle", {"newVersion": "soon"}, NOW_MS)
        self.assertFalse(any("is out" in str(line) for line in lines))


class SessionFile(unittest.TestCase):
    def setUp(self):
        use_state_dir()

    def test_reads_frame_info_and_visibility(self):
        write(overlay.SESSION_PATH, {"frame": "waiting", "info": {"tool": "Bash"}, "visible": False, "visibleAt": 5})
        self.assertEqual(overlay.read_state(), ("waiting", {"tool": "Bash"}, (False, 5), False, 0, None, None))

    def test_an_unknown_frame_is_idle_and_no_choice_is_none(self):
        write(overlay.SESSION_PATH, {"frame": "dancing"})
        self.assertEqual(overlay.read_state(), ("idle", {}, None, False, 0, None, None))

    def test_a_new_version_to_celebrate(self):
        write(overlay.SESSION_PATH, {"frame": "idle", "update": {"version": "0.15.0", "route": "clone", "celebrate": 9, "from": "0.14.1"}})
        self.assertEqual(overlay.read_state().celebrate, (9, "0.15.0"))
        for update in ({"version": "0.15.0"}, {"version": "soon", "celebrate": 9}, {"version": "0.15.0", "celebrate": True}, "yes"):
            write(overlay.SESSION_PATH, {"frame": "idle", "update": update})
            self.assertIsNone(overlay.read_state().celebrate)

    def test_a_missing_or_half_written_file_is_none(self):
        self.assertIsNone(overlay.read_state())
        write(overlay.SESSION_PATH, '{"frame": "idl')
        self.assertIsNone(overlay.read_state())

    def test_others_limits_reads_every_other_session(self):
        mine = [{"kind": "five_hour", "percent": 8}]
        theirs = [{"kind": "five_hour", "percent": 9}]
        write(overlay.SESSION_PATH, {"frame": "idle", "info": {"limits": mine}})
        write(os.path.join(overlay.SESSIONS_DIR, "b.json"), {"frame": "idle", "info": {"limits": theirs}})
        write(os.path.join(overlay.SESSIONS_DIR, "c.json"), {"frame": "idle", "visible": False, "visibleAt": 1, "ended": True})
        self.assertEqual(overlay.others_limits(), [theirs])

    def test_a_clear_is_a_number(self):
        write(overlay.SESSION_PATH, {"frame": "idle", "cleared": 1234})
        self.assertEqual(overlay.read_state().cleared, 1234)
        write(overlay.SESSION_PATH, {"frame": "idle", "cleared": True})
        self.assertEqual(overlay.read_state().cleared, 0)

    def test_the_character_is_a_folder_name(self):
        write(overlay.SESSION_PATH, {"frame": "idle", "character": "yunseul"})
        self.assertEqual(overlay.read_state().character, "yunseul")
        for bad in ("../miku", "", 3, None):
            write(overlay.SESSION_PATH, {"frame": "idle", "character": bad})
            self.assertIsNone(overlay.read_state().character, bad)

    def test_another_character_is_beside_hers_with_idle_art(self):
        frames = tempfile.mkdtemp()
        for name in ("miku", "yunseul", "teto"):
            os.makedirs(os.path.join(frames, name))
        write_png(os.path.join(frames, "miku"), "idle-1", (0, 200, 200, 255))
        write_png(os.path.join(frames, "yunseul"), "idle", (200, 30, 50, 255))
        before = overlay.FRAMES_DIR
        try:
            overlay.FRAMES_DIR = os.path.join(frames, "miku")
            self.assertEqual(overlay.frames_of("yunseul"), os.path.join(frames, "yunseul"))
            self.assertIsNone(overlay.frames_of("teto"))  # no art
            self.assertIsNone(overlay.frames_of("neru"))  # no folder
            self.assertIsNone(overlay.frames_of(None))
        finally:
            overlay.FRAMES_DIR = before

    def test_ended(self):
        write(overlay.SESSION_PATH, {"frame": "idle", "visible": False, "visibleAt": 5, "ended": True})
        self.assertTrue(overlay.read_state().ended)

    def test_the_newest_choice_wins(self):
        self.assertTrue(overlay.is_visible(None, None, None))
        self.assertFalse(overlay.is_visible((False, 10), None))
        self.assertTrue(overlay.is_visible((False, 10), (True, 20)))  # /mascot show all, later
        self.assertFalse(overlay.is_visible((True, 30), (True, 20), (False, 40)))  # right-click, later still
        write(overlay.ALL_PATH, {"visible": False, "at": 7})
        self.assertEqual(overlay.read_all_choice(), (False, 7))


class Slots(unittest.TestCase):
    def setUp(self):
        use_state_dir("me")
        self.parent = os.getppid()

    def lock(self, n, pid, parent=1, key="other"):
        write(overlay.slot_path(n), {"pid": pid, "parent": parent, "key": key})

    def test_takes_the_lowest_free_spot(self):
        self.lock(0, self.parent)  # alive, someone else's
        self.assertEqual(overlay.claim_slot(self.parent), (1, False))
        self.assertEqual(overlay.read_json(overlay.slot_path(1)), {"pid": os.getpid(), "parent": self.parent, "key": "me"})
        self.assertEqual(overlay.claim_slot(self.parent), (1, False))  # already ours
        overlay.release_slot(1)
        self.assertFalse(os.path.exists(overlay.slot_path(1)))

    def test_takes_a_spot_whose_overlay_is_gone(self):
        self.lock(0, gone_pid())
        self.assertEqual(overlay.claim_slot(self.parent), (0, False))

    def test_takes_over_its_own_claude_codes_previous_overlay(self):
        # A reload: the old overlay of the same Claude Code still holds spot 0.
        overlay.PREDECESSOR_WAIT_S = 0.2
        self.lock(0, self.parent, parent=self.parent)
        self.assertEqual(overlay.claim_slot(self.parent), (0, True))  # taken over: no intro

    def test_takes_over_the_lock_its_reloaded_predecessor_left(self):
        # The old overlay quit when its mod was unloaded and left its lock.
        self.lock(1, gone_pid(), parent=self.parent)
        self.lock(0, self.parent)  # alive, someone else's
        self.assertEqual(overlay.claim_slot(self.parent), (1, True))

    def test_leaves_a_lock_being_written_alone(self):
        write(overlay.slot_path(0), "")
        self.assertEqual(overlay.claim_slot(self.parent), (1, False))
        make_old(overlay.slot_path(0), 60)
        overlay.release_slot(1)
        self.assertEqual(overlay.claim_slot(self.parent), (0, False))

    def test_release_leaves_another_overlays_spot(self):
        self.lock(0, self.parent)
        overlay.release_slot(0)
        self.assertTrue(os.path.exists(overlay.slot_path(0)))

    def test_shown_peers_reads_each_shown_sessions_project(self):
        self.lock(0, self.parent, key="a")
        self.lock(1, gone_pid(), key="b")  # gone: not shown
        write(os.path.join(overlay.SESSIONS_DIR, "a.json"), {"frame": "idle", "info": {"project": "web"}})
        self.assertEqual(overlay.shown_peers(), [(0, "web")])


PRIMARY = overlay.Screen(0, 0, 1000, 900)
# A second display to the right, its top above the primary's (negative y).
SECOND = overlay.Screen(1000, -200, 1800, 400)


def spots(count, screens, saved=None):
    places = saved or {}
    return [overlay.slot_spot(n, 200, 300, screens, places.get) for n in range(count)]


def xy(places):
    return [(p["x"], p["y"]) for p in places]


class Layout(unittest.TestCase):
    def test_spots_line_up_leftwards_then_wrap(self):
        # 1000 wide: spot 0 at x=760, then 544, 328, 112; a 5th starts a row up.
        self.assertEqual(
            xy(spots(6, [PRIMARY])),
            [(760, 520), (544, 520), (328, 520), (112, 520), (760, 204), (544, 204)],
        )

    def test_a_full_display_goes_on_on_the_next(self):
        places = xy(spots(10, [PRIMARY, SECOND]))
        self.assertEqual(places[7], (112, 204))  # the primary's last
        self.assertEqual(places[8:], [(1560, 20), (1344, 20)])  # the second's corner, then leftwards

    def test_new_spots_stand_beside_a_dragged_one(self):
        # Spot 0 was dragged onto the second display: spot 1 joins it there.
        self.assertEqual(xy(spots(3, [PRIMARY, SECOND], {0: {"x": 1500, "y": 50}})), [(1500, 50), (1284, 50), (1068, 50)])

    def test_a_place_on_a_display_that_is_gone_waits_for_it(self):
        saved = {0: {"x": 1500, "y": 50}}
        self.assertEqual(xy(spots(2, [PRIMARY], saved)), [(760, 520), (544, 520)])
        self.assertEqual(xy(spots(1, [PRIMARY, SECOND], saved)), [(1500, 50)])  # plugged back in

    def test_the_card_stays_on_her_display(self):
        size, card = (200, 300), (250, 150)
        self.assertEqual(overlay.card_spot({"x": 760, "y": 520}, size, card, [PRIMARY, SECOND]), (498, 595))
        # Too close to the second display's left edge: the card goes right of her,
        # and it is held below that display's top.
        self.assertEqual(overlay.card_spot({"x": 1010, "y": -250}, size, card, [PRIMARY, SECOND]), (1222, -175))
        self.assertEqual(overlay.card_spot({"x": 1600, "y": 300}, size, card, [PRIMARY, SECOND]), (1338, 250))

    def test_nearest_screen(self):
        self.assertEqual(overlay.nearest_screen(1200, 0, [PRIMARY, SECOND]), SECOND)
        self.assertEqual(overlay.nearest_screen(1300, 600, [PRIMARY, SECOND]), SECOND)  # just below it
        self.assertEqual(overlay.nearest_screen(-50, 950, [PRIMARY, SECOND]), PRIMARY)

    def test_lists_this_machines_displays(self):
        found = overlay.list_screens()
        if os.name == "nt":
            self.assertGreaterEqual(len(found), 1)
            self.assertTrue(all(s.right > s.left and s.bottom > s.top for s in found))
        else:
            self.assertEqual(found, [])


class Resize(unittest.TestCase):
    def test_her_feet_stay_where_they_stood(self):
        before = {"x": 1000, "y": 500}
        after = overlay.resized_pos(before, (280, 420), (373, 560))
        self.assertEqual(after, {"x": 954, "y": 360})
        self.assertLessEqual(abs(after["x"] + 373 / 2 - (1000 + 280 / 2)), 0.5)  # her middle, to the pixel
        self.assertEqual(after["y"] + 560, before["y"] + 420)  # her feet


class Sweep(unittest.TestCase):
    def setUp(self):
        self.state = use_state_dir("me")

    def test_clears_what_gone_sessions_left(self):
        old = os.path.join(overlay.SESSIONS_DIR, "old.json")
        fresh = os.path.join(overlay.SESSIONS_DIR, "fresh.json")
        for path in (old, fresh, overlay.SESSION_PATH):
            write(path, {"frame": "idle"})
        make_old(old, overlay.STALE_S + 1)
        make_old(overlay.SESSION_PATH, overlay.STALE_S + 1)  # our own stays, whatever its age
        write(overlay.slot_path(0), {"pid": gone_pid()})
        write(overlay.slot_path(1), {"pid": os.getppid()})
        write(overlay.pos_path(0), {"x": 1, "y": 2})

        overlay.sweep()
        self.assertEqual(sorted(os.listdir(overlay.SESSIONS_DIR)), ["fresh.json", "me.json"])
        self.assertEqual(sorted(os.listdir(overlay.SLOTS_DIR)), ["0.pos.json", "1.lock"])

    def test_the_start_keeps_the_lock_its_reloaded_predecessor_left(self):
        write(overlay.slot_path(0), {"pid": gone_pid(), "parent": 4242})
        write(overlay.slot_path(1), {"pid": gone_pid(), "parent": 77})
        overlay.sweep(4242)
        self.assertEqual(os.listdir(overlay.SLOTS_DIR), ["0.lock"])
        overlay.sweep()  # later sweeps clear it, if nobody took it
        self.assertEqual(os.listdir(overlay.SLOTS_DIR), [])

    def test_the_single_overlays_files_go_and_its_spot_becomes_spot_0s(self):
        write(os.path.join(self.state, "mood.json"), {"frame": "idle"})
        write(os.path.join(self.state, "overlay.lock"), "123")
        write(os.path.join(self.state, "overlay-pos.json"), {"x": 10, "y": 20})
        overlay.sweep()
        self.assertEqual(sorted(os.listdir(self.state)), ["sessions", "slots"])
        self.assertEqual(overlay.load_pos(0), {"x": 10, "y": 20})


class Processes(unittest.TestCase):
    def test_is_alive(self):
        self.assertTrue(overlay.is_alive(os.getpid()))
        self.assertFalse(overlay.is_alive(gone_pid()))
        self.assertFalse(overlay.is_alive(None))

    def test_claude_code_is_found_past_the_shell(self):
        # claude.exe started cmd.exe, which started the launcher, then Python.
        table = {
            10: (1, "WindowsTerminal.exe"),
            20: (10, "claude.exe"),
            30: (20, "cmd.exe"),
            40: (30, "pythonw.exe"),
            50: (40, "pythonw3.13.exe"),
        }
        self.assertEqual(overlay.claude_code_of(40, table), 20)
        self.assertEqual(overlay.claude_code_of(20, table), 20)  # started directly
        self.assertEqual(overlay.claude_code_of(99, table), 99)  # unknown: as is
        self.assertEqual(overlay.claude_code_of(30, {30: (30, "cmd.exe")}), 30)  # no endless loop

    def test_go_betweens(self):
        for name in ("cmd.exe", "CMD.EXE", "conhost.exe", "py.exe", "pyw.exe", "python.exe", "pythonw3.13.exe"):
            self.assertTrue(overlay.is_go_between(name), name)
        for name in ("claude.exe", "node.exe", "bun.exe", "powershell.exe", "pythonista.exe"):
            self.assertFalse(overlay.is_go_between(name), name)

    def test_the_process_table_knows_this_one(self):
        table = overlay.process_table()
        if os.name == "nt":
            self.assertEqual(table[os.getpid()][0], os.getppid())
            self.assertTrue(overlay.is_go_between(table[os.getpid()][1]))
        else:
            self.assertEqual(table, {})

    def test_the_starter_is_the_spawns_cmd(self):
        saved = os.environ.pop(overlay.STARTER_ENV, None)
        try:
            self.assertEqual(overlay.starter_pid(), os.getppid())
            os.environ[overlay.STARTER_ENV] = "1234"
            self.assertEqual(overlay.starter_pid(), 1234)
            self.assertIsNone(overlay.stand_apart())  # she is the one started apart: runs here
        finally:
            os.environ.pop(overlay.STARTER_ENV, None)
            if saved is not None:
                os.environ[overlay.STARTER_ENV] = saved

    @unittest.skipUnless(os.name == "nt", "process trees and jobs as Windows has them")
    def test_she_outlives_the_tree_that_started_her(self):
        """A stand-in started as the mod's spawn is, in a job that kills its
        processes when it closes; then its tree is killed and the job closed,
        as Claude Code does on its way out. She runs apart, says so on the
        stand-in's stdout, and is still running after both."""
        import ctypes
        import ctypes.wintypes as wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.OpenProcess.restype = wintypes.HANDLE
        info = (ctypes.c_byte * 144)()  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION on x64
        ctypes.c_uint32.from_buffer(info, 16).value = 0x2000 | 0x800  # KILL_ON_JOB_CLOSE | BREAKAWAY_OK
        job = kernel.CreateJobObjectW(None, None)
        self.assertTrue(job)
        self.assertTrue(kernel.SetInformationJobObject(wintypes.HANDLE(job), 9, info, ctypes.sizeof(info)))

        folder = tempfile.mkdtemp()
        marker = os.path.join(folder, "alive")
        helper = os.path.join(folder, "helper.py")
        with open(helper, "w") as f:
            f.write(
                "import os, sys, time\n"
                f"sys.path.insert(0, {os.path.dirname(os.path.abspath(overlay.__file__))!r})\n"
                "import mascot_overlay as overlay\n"
                "if overlay.STARTER_ENV not in os.environ:\n"
                "    sys.stdin.readline()  # in the job by now\n"
                "code = overlay.stand_apart()\n"
                "if code is not None:\n"
                "    sys.exit(code)\n"
                "print(os.getpid(), overlay.starter_pid(), flush=True)\n"
                "time.sleep(2)\n"
                f"open({marker!r}, 'w').close()\n"
            )
        stand_in = subprocess.Popen([sys.executable, helper], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        handle = kernel.OpenProcess(0x1F0FFF, False, stand_in.pid)
        try:
            self.assertTrue(kernel.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(handle)))
            stand_in.stdin.write("go\n")
            stand_in.stdin.flush()
            her, starter = map(int, stand_in.stdout.readline().split())
            self.assertEqual(starter, os.getpid())  # the stand-in's parent, as cmd is
            self.assertNotEqual(overlay.process_table()[her][0], stand_in.pid)
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(stand_in.pid)], capture_output=True)
            kernel.CloseHandle(wintypes.HANDLE(job))  # Claude Code exits
            stand_in.wait(5)
            self.assertTrue(overlay.is_alive(her), "she was killed with the stand-in")
            deadline = time.monotonic() + 5
            while not os.path.exists(marker) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(os.path.exists(marker), "she did not get to finish")
        finally:
            kernel.CloseHandle(wintypes.HANDLE(handle))
            stand_in.kill()
            stand_in.stdin.close()
            stand_in.stdout.close()


if __name__ == "__main__":
    unittest.main()
