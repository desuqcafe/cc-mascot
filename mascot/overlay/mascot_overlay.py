"""Mascot overlay: a borderless, always-on-top, transparent window showing one
Claude Code session's mascot at full resolution. The mascot mod starts one per
session and writes that session's mood to a small JSON file; this window
watches it. Nothing else connects the two: no network, no API.

    pythonw mascot_overlay.py <frames dir> <session file>

Drag with the left mouse button to move it (the spot is remembered; she
swings as she is carried, effects.Carry, in her held pose when there is art
for it),
double-click to send it back to its spot, right-click to hide it. A tag under
her feet names the session's project; hovering shows a card about the session
(context, usage limits, what Claude is doing), from figures the mod writes.

The session file lives in the mascot folder, beside what every session's
overlay shares:

    sessions/<key>.json   a session's frame, card figures and visibility
                          (MascotSessionFile, written by the mod)
    all.json              a show or hide for every session (/mascot show all)
    settings.json         her size, calm mode, the aura's thresholds...
                          (settings.py; followed live)
    slots/<n>.lock        which overlay stands in spot n: {pid, parent, key}
    slots/<n>.pos.json    where spot n's mascot was dragged to

Each shown mascot takes the lowest free spot, so several never overlap. Spot 0
is the primary display's bottom-right corner; each next spot stands to the left
of the one before, wherever that one was dragged, a row up when its display
runs out of room, then on the next display. A dragged spot keeps its place
while its display is connected.

She is drawn into a layered window (layered.py): soft edges and glows blend
over the desktop. A mood's symbol (effects.py: the thought bubble, notes, the
"?"...) and her glitch are drawn over her frames, and her status around
them (effects.dress: an aura as the context grows, a failing stage light or
a hologram fade as a usage limit runs out); the window itself never moves on
its own. She comes and goes as a hologram (effects.projection): the intro
when shown, the outro when hidden or when the session ends, a channel change
when the conversation is cleared; an overlay taking over its reloaded
predecessor's spot skips the intro. A new character in the session file
(/mascot character) plays the outro, takes on that character's art and look
in this same process and spot, and plays the intro. Her big finish, the beam mood, bursts
past her window's usual edges (effects.beamed), so for its first seconds
the window is effects.BEAM_PAD larger on every side. So is it while a new
version's banner plays (effects.updated): once, when the mod says a newer
version than the last one run has loaded (the session file's `update`).
When a round of work ends while you are elsewhere, she sends magic to your
pointer, on any display (the session file's `call`, magic.py), in a window
of its own that clicks pass through; hidden, she sends it all the same.

The overlay runs while its session does, shown or hidden, and says on stdout
what was chosen in its window (`hidden`). Its art is loaded only while it is
shown. It cleans up and exits when the mod writes `ended` or when its Claude
Code is gone, and quits when the mod that started it is unloaded (a reload
starts the next one); any overlay sweeps up after crashed ones. Claude Code,
exiting, kills the process tree it started, so the overlay runs apart from it
(`stand_apart`): that way she still plays the outro when its terminal is
closed.
"""

import ctypes
import ctypes.wintypes as wintypes
import datetime
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageChops, ImageDraw, ImageFont

import effects as fx
import magic
import settings as cfg
from layered import LayeredWindow

MOODS = ("idle", "thinking", "working", "happy", "error", "waiting", "worried", "sleepy", "beam")
# Art the overlay plays on its own, not a mood the mod writes: "held" while
# she is carried.
POSES = ("held",)
FLIPBOOK_FPS = 6  # unless the frames folder's moods.json says otherwise
# The character's colors and names, beside her frames: her effects' look
# (effects.look_of) and the settings window's palette.
THEME_FILE = "theme.json"
HEIGHT = cfg.DEFAULTS.size  # the mascot's height in pixels: the size setting

# Set by configure(): this overlay's art and session, and the shared folders.
FRAMES_DIR = ""
SESSION_PATH = ""
SESSION_KEY = ""
STATE_DIR = ""
SESSIONS_DIR = ""
SLOTS_DIR = ""
ALL_PATH = ""
SETTINGS_PATH = ""

# Spots are this far apart; a slot taken by our own Claude Code's previous
# overlay (a reload, a new character) is waited on this long, then taken.
SLOT_GAP = 16
# Spot 0's distance from the right and bottom of its display's work area.
CORNER_X = 40
CORNER_Y = 80
MAX_SLOTS = 64
PREDECESSOR_WAIT_S = 3.0
# Set for an overlay started apart from Claude Code's process tree
# (stand_apart): the pid of the spawn's cmd.exe, which its stand-in was
# started by; and for the go-between that starts her.
STARTER_ENV = "MASCOT_STARTER"
GO_BETWEEN_ENV = "MASCOT_GO_BETWEEN"
# A session file nobody wrote for this long belongs to a session that is gone
# (a live mod rewrites it at least every 30 s); an unreadable lock this old is
# not one being written.
STALE_S = 10 * 60
UNREADABLE_LOCK_S = 5
SWEEP_EVERY_MS = 60_000
TAG_EVERY_MS = 2000
STATUS_EVERY_MS = 2000
SCREENS_EVERY_MS = 2000
# How often a shown mascot makes sure no ordinary window has got above her
# (LayeredWindow.keep_on_top): a walk up the windows above hers.
ON_TOP_EVERY_MS = 1000
# settings.json is checked with the session file (every POLL_MS): a size
# picked in the settings window shows at once. A stat costs microseconds.
POLL_MS = 100
# While a new size is built in the background, whether it is ready.
RESIZE_CHECK_MS = 16
BUILD_THREADS = 4  # frames prepared at once (prepare_all)
# After a resize, spots are laid out again this much later, once every
# mascot has resized (each spot stands beside the one before).
RELAYOUT_MS = 1500
TAG_CHARS = 24
DRAG_SLOP = 4  # px the pointer moves before a press on her is a drag
# The pointer's velocity while she is carried: from its moves this recent; a
# pointer still for STILL_S has stopped.
VELOCITY_S = 0.1
STILL_S = 0.06
KEEP_MOODS = 3  # moods besides idle whose frames stay built (thinking and working take turns, and held)

# The hover card's and the tag's colors.
CARD_BG = "#1f1f28"
CARD_FG = "#e6e6ef"
CARD_DIM = "#8a8aa0"
CARD_EDGE = "#4a4a5e"
CARD_BAR_EMPTY = "#3a3a4c"
# A bar's color by how full it is: fine, getting there, nearly out.
CARD_BAR_COLORS = ((60, "#4caf7a"), (85, "#e0a33a"), (101, "#e05a4f"))
CARD_FONT = ("Consolas", 10)
CARD_LABEL_CHARS = 10  # the column where bars start
CARD_BAR_CHARS = 10  # a bar's length, in character widths

# The name tag: its text size in points, and its room around the text.
TAG_POINTS = 9
TAG_PAD = (8, 1)

# Art saved without transparency: its backdrop is filled with this color,
# then cut out.
KEY = (1, 2, 3)


def configure(frames_dir, session_path):
    """Points the overlay at its art (and her effects at her look) and its
    session's file."""
    global SESSION_PATH, SESSION_KEY, STATE_DIR, SESSIONS_DIR, SLOTS_DIR, ALL_PATH, SETTINGS_PATH
    use_frames(frames_dir)
    SESSION_PATH = os.path.normpath(session_path)
    SESSION_KEY = os.path.splitext(os.path.basename(SESSION_PATH))[0]
    SESSIONS_DIR = os.path.dirname(SESSION_PATH)
    STATE_DIR = os.path.dirname(SESSIONS_DIR)
    SLOTS_DIR = os.path.join(STATE_DIR, "slots")
    ALL_PATH = os.path.join(STATE_DIR, "all.json")
    SETTINGS_PATH = os.path.join(STATE_DIR, cfg.FILE)


def use_frames(frames_dir):
    """Her art's folder, and her effects drawn in its character's look."""
    global FRAMES_DIR
    FRAMES_DIR = frames_dir
    fx.use(fx.look_of(read_json(os.path.join(frames_dir, THEME_FILE)) if frames_dir else None))


def frames_of(character):
    """The frames folder of `character` beside this one's, when it has idle
    art; else None."""
    if not character or not FRAMES_DIR:
        return None
    folder = os.path.join(os.path.dirname(os.path.normpath(FRAMES_DIR)), character)
    return folder if frame_paths("idle", folder) else None


def set_height(height):
    """Her size: frames are prepared at it, and the effects' pads fit it."""
    global HEIGHT
    HEIGHT = height
    fx.scale_to(height)


# ---------------------------------------------------------------- frames


def frame_paths(mood, folder=None):
    """frames/<mood>.png, or its flipbook frames <mood>-1.png, <mood>-2.png...
    (in `folder`, FRAMES_DIR by default)"""
    folder = folder or FRAMES_DIR
    numbered = []
    pattern = re.compile(rf"^{mood}-(\d+)\.png$", re.IGNORECASE)
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        match = pattern.match(name)
        if match:
            numbered.append((int(match.group(1)), os.path.join(folder, name)))
    if numbered:
        return [path for _, path in sorted(numbered)]
    single = os.path.join(folder, f"{mood}.png")
    return [single] if os.path.exists(single) else []


def cut_background(img):
    """Makes a flat backdrop transparent, for art saved without transparency."""
    if img.getextrema()[3][0] < 255:
        return img  # already has transparency
    rgb = img.convert("RGB")
    w, h = rgb.size
    backdrop = rgb.getpixel((0, 0))
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if rgb.getpixel(corner) != KEY:
            ImageDraw.floodfill(rgb, corner, KEY, thresh=40)

    # Gaps the corners cannot reach (between an arm and the hair): any region
    # of the backdrop's own color big enough not to be a highlight in the art.
    rejected = (4, 5, 6)
    min_area = (w * h) // 400
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            px = rgb.getpixel((x, y))
            if px in (KEY, rejected) or sum(abs(a - b) for a, b in zip(px, backdrop)) > 6:
                continue
            probe = rgb.copy()
            ImageDraw.floodfill(probe, (x, y), (7, 8, 9), thresh=24)
            area = ImageChops.difference(probe, rgb).convert("L").point(lambda v: 255 if v else 0).histogram()[255]
            ImageDraw.floodfill(rgb, (x, y), KEY if area >= min_area else rejected, thresh=24)

    # Opaque wherever the fill did not reach.
    diff = ImageChops.difference(rgb, Image.new("RGB", (w, h), KEY))
    out = img.copy()
    out.putalpha(diff.convert("L").point(lambda v: 255 if v else 0))
    return out


def prepare(path, height):
    """One frame, background cut and scaled to `height`."""
    img = cut_background(Image.open(path).convert("RGBA"))
    scale = height / img.height
    return img.resize((max(1, round(img.width * scale)), height), Image.LANCZOS)


def prepare_all(paths, height):
    """Frames, prepared BUILD_THREADS at a time: Pillow lets go of the GIL
    while it decodes and scales, so idle's 36 take 75 ms instead of 270."""
    with ThreadPoolExecutor(BUILD_THREADS) as pool:
        return list(pool.map(lambda path: prepare(path, height), paths))


# Art built at a height, ready to be taken on (`Art.adopt`): every mood's
# frame files, {mood: [frames]} (idle's and maybe others'), {mood: fps}.
Built = namedtuple("Built", "height paths frames rates")


def build_art(height, moods=()):
    """Idle's frames at `height`, and those of `moods` that have art of their
    own; None when there is no idle art at all. Touches nothing shared, so it
    may run on any thread."""
    paths = {mood: frame_paths(mood) for mood in MOODS + POSES}
    if not paths["idle"]:
        return None
    frames = {mood: prepare_all(paths[mood], height) for mood in dict.fromkeys(("idle", *moods)) if paths.get(mood)}
    return Built(height, paths, frames, frame_rates())


class Art:
    """A shown mascot's frames. Idle's are built on show: her size, and what
    a mood without art of its own plays. Another mood's are built in the
    background the first time she takes it on (a rigged loop is 10-20 MB and
    a quarter second to build), and until they are ready it plays idle's
    under its symbol. Idle and the KEEP_MOODS other moods used last stay
    built; `clear` drops everything (a hidden overlay holds no art). A new
    size is built apart (`build_art`) and taken on whole (`adopt`)."""

    def __init__(self, keep=KEEP_MOODS):
        self.keep = keep
        self.lock = threading.Lock()  # builds finish on their own threads
        self.height = HEIGHT  # what its frames are built at
        self.paths = {}  # {mood: its frame files}, read once per show
        self.frames = {}  # {mood: [frames]}, idle's included
        self.rates = {}  # {mood: fps}
        self.recent = []  # moods other than idle built or building, last used last
        self.generation = 0  # a build finishing after a clear is dropped

    def load(self):
        """Builds idle's frames at HEIGHT; False when there is no idle art at all."""
        built = build_art(HEIGHT)
        if built is None:
            self.clear()
            return False
        self.adopt(built)
        return True

    def adopt(self, built):
        """Takes on art from `build_art`, dropping what it had (and any build
        of it still running)."""
        self.clear()
        with self.lock:
            self.height, self.paths, self.rates = built.height, built.paths, built.rates
            self.frames.update(built.frames)
            self.recent.extend(mood for mood in built.frames if mood != "idle")

    def clear(self):
        with self.lock:
            self.generation += 1
            self.paths, self.rates = {}, {}
            self.frames.clear()
            self.recent.clear()

    def size(self):
        frame = self.frames["idle"][0]
        return frame.width, frame.height

    def has(self, mood):
        return bool(self.paths.get(mood))

    def get(self, mood, instead=None):
        """(frames, fps) to play for `mood` now: its own once built; until
        then, or when it has none, `instead` (idle's by default)."""
        idle = instead or (self.frames.get("idle"), self.rates.get("idle", FLIPBOOK_FPS))
        if mood == "idle" or not self.paths.get(mood):
            return idle
        with self.lock:
            if mood in self.recent:
                self.recent.remove(mood)
            else:
                threading.Thread(target=self._build, args=(mood, self.height, self.generation), daemon=True).start()
            self.recent.append(mood)
            for old in self.recent[: -self.keep]:
                self.recent.remove(old)
                self.frames.pop(old, None)
            frames = self.frames.get(mood)
        return (frames, self.rates.get(mood, FLIPBOOK_FPS)) if frames else idle

    def _build(self, mood, height, generation):
        try:
            frames = prepare_all(self.paths.get(mood, []), height)
        except (OSError, ValueError):
            return  # unreadable art: the mood keeps playing idle's
        with self.lock:
            if generation == self.generation and mood in self.recent and frames:
                self.frames[mood] = frames


def frame_rates():
    """{mood: fps} for every mood: how fast its frames play, set in the frames
    folder's moods.json ({"idle": {"fps": 12}}); a mood without art plays
    idle's frames at idle's rate."""
    data = read_json(os.path.join(FRAMES_DIR, "moods.json")) or {}

    def rate(mood):
        entry = data.get(mood) if isinstance(data.get(mood), dict) else {}
        fps = entry.get("fps")
        return fps if isinstance(fps, (int, float)) and not isinstance(fps, bool) and 0 < fps <= 60 else FLIPBOOK_FPS

    return {mood: rate(mood if mood == "idle" or frame_paths(mood) else "idle") for mood in MOODS + POSES}


def tag_image(text, size):
    """The name tag under her feet: `text` in Segoe UI `size` px on the hover
    card's colors, in a 1 px edge."""
    try:
        font = ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    ascent, descent = font.getmetrics()
    w = round(font.getlength(text)) + 2 * TAG_PAD[0] + 2
    h = ascent + descent + 2 * TAG_PAD[1] + 2
    img = Image.new("RGBA", (w, h), CARD_EDGE)
    draw = ImageDraw.Draw(img)
    draw.rectangle((1, 1, w - 2, h - 2), fill=CARD_BG)
    draw.text((1 + TAG_PAD[0], 1 + TAG_PAD[1]), text, font=font, fill=CARD_FG)
    return img


# ---------------------------------------------------------- files
#
# A choice to show or hide is (visible, at), `at` in epoch ms; the newest of
# the session's own, everyone's (all.json) and this window's wins.

# A projection playing in her window: "intro", "outro" or "channel", since
# when (monotonic seconds), what to do once it is over, and whether it plays
# calm (a plain fade; chosen as it starts).
Playing = namedtuple("Playing", "kind since then calm")
Playing.__new__.__defaults__ = (False,)

SessionState = namedtuple("SessionState", "mood info choice ended cleared character celebrate call")
SessionState.__new__.__defaults__ = (0, None, None, None)

# A new version's banner is played when the mod's word of it (`celebrate`,
# epoch ms) is this fresh; an overlay started later, by a reload, lets it be.
CELEBRATE_FRESH_MS = 60_000


def celebrate_of(data):
    """(when, version) of the newer version the session file's `update` says
    has loaded; None for none."""
    update = data.get("update") if isinstance(data.get("update"), dict) else {}
    at, version = update.get("celebrate"), update.get("version")
    if isinstance(at, (int, float)) and not isinstance(at, bool) and isinstance(version, str) \
            and re.fullmatch(r"\d+(\.\d+){1,3}", version):
        return at, version
    return None


def call_of(data):
    """(when, whether a test) of the last call to the pointer the session
    file's `call` asks for (magic.py); None for none."""
    call = data.get("call") if isinstance(data.get("call"), dict) else {}
    at = call.get("at")
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        return at, call.get("test") is True
    return None


def read_json(path):
    """A file's JSON object, or None when it is missing, unreadable or not an object."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def choice_of(data, visible_key, at_key):
    if not data or not isinstance(data.get(visible_key), bool):
        return None
    at = data.get(at_key)
    return data[visible_key], (at if isinstance(at, (int, float)) else 0)


def read_state(path=None):
    """The session's SessionState; None when its file cannot be read just now."""
    data = read_json(path or SESSION_PATH)
    if data is None:
        return None
    mood = data.get("frame")
    info = data.get("info")
    return SessionState(
        mood if mood in MOODS else "idle",
        info if isinstance(info, dict) else {},
        choice_of(data, "visible", "visibleAt"),
        data.get("ended") is True,
        data["cleared"] if isinstance(data.get("cleared"), (int, float)) and not isinstance(data.get("cleared"), bool) else 0,
        data["character"] if isinstance(data.get("character"), str) and re.fullmatch(r"[A-Za-z0-9_-]+", data["character"]) else None,
        celebrate_of(data),
        call_of(data),
    )


def read_all_choice():
    return choice_of(read_json(ALL_PATH), "visible", "at")


def is_visible(*choices):
    """The newest choice's answer; shown when nothing was chosen."""
    made = [c for c in choices if c is not None]
    return max(made, key=lambda c: c[1])[0] if made else True


# ------------------------------------------------------------ hover card

LIMIT_NAMES = {"five_hour": "5h limit", "seven_day": "Weekly", "spend_limit": "Spend"}
CARD_SUBAGENTS = 5  # rows before "+N more"


def fmt_tokens(n):
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{round(n / 1000)}k"
    return str(n)


def bar_color(percent):
    return next(color for limit, color in CARD_BAR_COLORS if percent < limit or limit == 101)


def fmt_elapsed(ms):
    """A running turn: 45s, 2m 14s, 1h 05m."""
    secs = max(0, int(ms // 1000))
    if secs < 60:
        return f"{secs}s"
    mins, secs = divmod(secs, 60)
    if mins < 60:
        return f"{mins}m {secs:02d}s"
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins:02d}m"


def fmt_age(ms):
    """The session's length: 42 min, 3h 05m."""
    mins = max(0, int(ms // 60_000))
    if mins < 60:
        return f"{mins} min"
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins:02d}m"


def fmt_reset(iso, now):
    """When a usage limit resets, in local time: 21:40 today, else Mon 09:00."""
    try:
        when = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except (AttributeError, ValueError):
        return ""
    if when - now < datetime.timedelta(hours=20):
        return f"resets {when:%H:%M}"
    return f"resets {when:%a %H:%M}"


def reset_minute(limit):
    """When a limit's window resets, to the minute; 0 when unknown."""
    try:
        when = datetime.datetime.fromisoformat(limit["resetsAt"].replace("Z", "+00:00"))
        return int(when.timestamp() // 60)
    except (KeyError, AttributeError, ValueError):
        return 0


def freshest_limits(readings):
    """The usage limits, from every session's last reading (`readings`: a list
    per session, this one's first). The limits are the account's, and within a
    window usage only grows: the window that resets last wins, then the
    highest figure in it."""
    best = {}
    for reading in readings:
        for limit in reading or []:
            if not isinstance(limit, dict) or not isinstance(limit.get("percent"), (int, float)):
                continue
            kind = limit.get("kind")
            key = (reset_minute(limit), limit["percent"])
            if kind not in best or key > best[kind][0]:
                best[kind] = (key, limit)
    return [limit for _, limit in best.values()]


def status_of(info, readings, now_ms, tiers=fx.CONTEXT_TIERS):
    """Her status (effects.Status) from the session's figures: how far its
    context has grown past `tiers` (the aura setting), and whether the
    5-hour or weekly limit is nearly used (LIMIT_NEAR percent, freshest of
    every session's `readings`; a window that has already reset counts for
    nothing)."""
    ctx = info.get("context") if isinstance(info.get("context"), dict) else {}
    near = set()
    for limit in freshest_limits([info.get("limits")] + list(readings)):
        if limit["percent"] >= fx.LIMIT_NEAR and reset_minute(limit) * 60_000 > now_ms - 60_000:
            near.add(limit.get("kind"))
    return fx.Status(fx.context_level(ctx.get("tokens"), tiers), "five_hour" in near, "seven_day" in near)


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def card_lines(mood, info, now_ms):
    """The card as (title, rows), from what the mod wrote and the time now.

    A row is a line of text, ("bar", name, percent, text) for a bar, or
    ("dim", text) for a quiet one.
    """
    now = datetime.datetime.fromtimestamp(now_ms / 1000).astimezone()
    title = " \u00b7 ".join(p for p in (info.get("project"), info.get("branch")) if p) or "Claude Code"
    lines = []

    ctx = info.get("context")
    if ctx:
        if ctx.get("tokens") is None:
            lines.append(("bar", "Context", 0, "no reply yet"))
        else:
            pct = ctx.get("percent") or 0
            lines.append(("bar", "Context", pct, f"{pct:>3}%  {fmt_tokens(ctx['tokens'])}/{fmt_tokens(ctx.get('window'))}"))
        if ctx.get("perTurn"):
            growth = f"+{fmt_tokens(ctx['perTurn'])}/turn"
            if ctx.get("turnsToCompact") is not None:
                growth += f" \u00b7 ~{ctx['turnsToCompact']} turns to compact"
            lines.append(" " * CARD_LABEL_CHARS + growth)

    for limit in info.get("limits") or []:
        name = LIMIT_NAMES.get(limit.get("kind"), str(limit.get("kind")))
        pct = limit.get("percent") or 0
        reset = fmt_reset(limit.get("resetsAt"), now) if limit.get("resetsAt") else ""
        lines.append(("bar", name, pct, f"{round(pct):>3}%  {reset}".rstrip()))

    about = []
    if info.get("model"):
        about.append(info["model"])
    if info.get("startedAt"):
        about.append(fmt_age(now_ms - info["startedAt"]))
    if info.get("prompts") is not None:
        about.append(plural(info["prompts"], "prompt"))
    if about:
        lines.append(" \u00b7 ".join(about))

    doing = mood
    if info.get("tool") and mood in ("working", "waiting", "worried"):
        doing += f" ({info['tool']})"
    if info.get("turnSince"):
        doing += f" \u00b7 {fmt_elapsed(now_ms - info['turnSince'])}"
    lines.append(f"Now: {doing}")

    agents = info.get("subagents") or []
    if agents:
        lines.append("Subagents:")
        for agent in agents[:CARD_SUBAGENTS]:
            size = fmt_tokens(agent.get("tokens")) if agent.get("tokens") is not None else "starting"
            if agent.get("percent") is not None:
                size += f" ({agent['percent']}%)"
            lines.append(f"  {agent.get('type', '?'):<16} {size}")
        if len(agents) > CARD_SUBAGENTS:
            lines.append(f"  +{len(agents) - CARD_SUBAGENTS} more")

    background = info.get("background") or {}
    if background:
        parts = [plural(n, kind.replace("_", " ")) for kind, n in sorted(background.items())]
        lines.append("Background: " + ", ".join(parts))

    new = info.get("newVersion")
    if isinstance(new, str) and re.fullmatch(r"\d+(\.\d+){1,3}", new):
        lines.append(f"v{new} is out \u00b7 /mascot update")

    if info.get("sessionId"):
        lines.append(("dim", f"Session {info['sessionId'][:8]}"))

    return title, lines


def tag_text(project, slot, peers):
    """The name tag under her feet: the project, numbered when other shown
    mascots belong to sessions of the same project (`peers`: (slot, project)
    of every shown mascot, this one included)."""
    name = project or "Claude Code"
    same = sorted(s for s, p in peers if (p or "Claude Code") == name)
    if len(same) > 1 and slot in same:
        suffix = f" ·{same.index(slot) + 1}"
    else:
        suffix = ""
    room = TAG_CHARS - len(suffix)
    if len(name) > room:
        name = name[: room - 1] + "…"
    return name + suffix


# ------------------------------------------------ processes and slots


def is_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: still running
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_table():
    """{pid: (parent pid, executable name)} of every process; {} off Windows."""
    if os.name != "nt":
        return {}
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, wintypes.HANDLE(-1).value):
        return {}
    table = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            table[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return table


def is_go_between(name):
    """A process a spawn passes through on its way to Python: the shell, the launchers."""
    return re.fullmatch(r"cmd|conhost|pyw?|pythonw?[\d.]*", os.path.splitext(name.lower())[0]) is not None


def claude_code_of(pid, table):
    """The process that really started the one `pid` names: past the shell and
    launchers in between (the mod's spawn goes through cmd.exe)."""
    seen = set()
    while pid in table and pid not in seen and is_go_between(table[pid][1]):
        seen.add(pid)
        pid = table[pid][0]
    return pid


def start_again(env):
    """Starts this overlay again with `env` and this process's output, out of
    Claude Code's job if it lets it go; None if it cannot start."""
    out = sys.stdout if sys.stdout else subprocess.DEVNULL
    err = sys.stderr if sys.stderr else subprocess.DEVNULL
    for flags in (0x01000000, 0):  # CREATE_BREAKAWAY_FROM_JOB, then without
        try:
            return subprocess.Popen(
                [sys.executable, *sys.argv], env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                creationflags=flags,
            )
        except (OSError, ValueError):
            pass
    return None


def wait_for(pid):
    """Waits for a process that is not our child; its exit code (0 when it is
    already gone)."""
    kernel = ctypes.WinDLL("kernel32")
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED
    if not handle:
        return 0
    try:
        kernel.WaitForSingleObject(wintypes.HANDLE(handle), 0xFFFFFFFF)  # INFINITE
        code = wintypes.DWORD()
        kernel.GetExitCodeProcess(wintypes.HANDLE(handle), ctypes.byref(code))
        return code.value
    finally:
        kernel.CloseHandle(wintypes.HANDLE(handle))


def stand_apart():
    """Claude Code, exiting, kills its spawn's whole process tree while it
    still runs (measured: 33 ms after the mod wrote `ended`), which would cut
    her off mid-frame, before the outro. So on Windows the spawned overlay
    starts a go-between that starts her and exits at once: her parent is gone,
    so no walk down the tree reaches her. The spawned one stays as her
    stand-in, waiting on her, which holds the mod's spawn open for as long as
    she runs: her stdout still reaches the mod, and a reload still ends her
    through the spawn's cmd (`STARTER_ENV` names it to her).

    Returns the exit code to leave with (her own, or the go-between's: her
    pid), or None to run her here."""
    if GO_BETWEEN_ENV in os.environ:
        her = start_again({k: v for k, v in os.environ.items() if k != GO_BETWEEN_ENV})
        return her.pid if her else 0
    if os.name != "nt" or STARTER_ENV in os.environ:
        return None
    env = dict(os.environ, **{STARTER_ENV: str(os.getppid()), GO_BETWEEN_ENV: "1"})
    go_between = start_again(env)  # it hands this output on to her
    if go_between is None:
        return None
    her = go_between.wait()
    if her == 0 or her % 4:  # Windows pids are multiples of 4; a crash's 1 is none
        return None
    return wait_for(her)


def starter_pid():
    """The process the mod's spawn started (its cmd.exe): gone when the mod is
    unloaded."""
    try:
        return int(os.environ[STARTER_ENV])
    except (KeyError, ValueError):
        return os.getppid()


def slot_path(n):
    return os.path.join(SLOTS_DIR, f"{n}.lock")


def pos_path(n):
    return os.path.join(SLOTS_DIR, f"{n}.pos.json")


def mtime_of(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def age_s(path):
    mtime = mtime_of(path)
    return None if mtime is None else time.time() - mtime


def is_stale_lock(path):
    """A lock whose overlay is gone; an unreadable one only once it has aged
    (another overlay may be writing it this moment)."""
    holder = read_json(path)
    if holder is None:
        age = age_s(path)
        return age is not None and age > UNREADABLE_LOCK_S
    return not is_alive(holder.get("pid"))


def claim_slot(parent):
    """Takes the lowest free spot: (its number, whether it was taken over),
    or (None, False) when all are taken. A spot held by our own Claude Code's
    previous overlay (a reload: it is being stopped, or has left its lock
    behind for us) is ours, taken over."""
    os.makedirs(SLOTS_DIR, exist_ok=True)
    me = {"pid": os.getpid(), "parent": parent, "key": SESSION_KEY}
    for n in range(MAX_SLOTS):
        path = slot_path(n)
        holder = read_json(path)
        if holder and holder.get("pid") == os.getpid():
            return n, False
        if holder and holder.get("parent") == parent:
            deadline = time.monotonic() + PREDECESSOR_WAIT_S
            while is_alive(holder.get("pid")) and time.monotonic() < deadline:
                time.sleep(0.1)
            write_json(path, me)
            return n, True
        if holder and is_alive(holder.get("pid")):
            continue
        if os.path.exists(path):
            if not is_stale_lock(path):
                continue
            remove(path)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            continue  # another overlay took it this moment
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(me, f)
        return n, False
    return None, False


def release_slot(n):
    if n is not None and (read_json(slot_path(n)) or {}).get("pid") == os.getpid():
        remove(slot_path(n))


# A display's work area (the screen less the taskbar), in desktop pixels: a
# display left of or above the primary has negative ones.
Screen = namedtuple("Screen", "left top right bottom")


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


def list_screens():
    """Every connected display, the primary first; [] when they cannot be listed."""
    if os.name != "nt":
        return []
    user32 = ctypes.WinDLL("user32")
    user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
    found = []

    def each(handle, _dc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            work = info.rcWork
            is_primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY
            found.append((not is_primary, Screen(work.left, work.top, work.right, work.bottom)))
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors(None, None, callback(each), 0)
    return [screen for _, screen in sorted(found)]


def screen_at(x, y, screens):
    """The display the point is on, or None."""
    return next((s for s in screens if s.left <= x < s.right and s.top <= y < s.bottom), None)


def nearest_screen(x, y, screens):
    """The display the point is on, or the closest one."""
    return screen_at(x, y, screens) or min(
        screens, key=lambda s: max(s.left - x, 0, x - s.right + 1) ** 2 + max(s.top - y, 0, y - s.bottom + 1) ** 2
    )


def middle_of(pos, width, height):
    return pos["x"] + width // 2, pos["y"] + height // 2


def corner(screen, width, height):
    """Spot 0 of a display: its bottom-right corner."""
    return {"x": screen.right - width - CORNER_X, "y": screen.bottom - height - CORNER_Y}


def beside(pos, width, height, screens):
    """The spot after the one standing at `pos`: to its left; when its display
    has no room there, a row up from the right; when the display is full, the
    next display's corner."""
    here = nearest_screen(*middle_of(pos, width, height), screens)
    if pos["x"] - width - SLOT_GAP >= here.left:
        return {"x": pos["x"] - width - SLOT_GAP, "y": pos["y"]}
    if pos["y"] - height - SLOT_GAP >= here.top:
        return {"x": here.right - width - CORNER_X, "y": pos["y"] - height - SLOT_GAP}
    return corner(screens[(screens.index(here) + 1) % len(screens)], width, height)


def slot_spot(n, width, height, screens, saved=lambda n: None):
    """Where spot n's mascot stands: where it was dragged to (`saved(n)`) while
    that is on a connected display; else beside spot n-1, spot 0 in the
    primary display's corner."""
    pos = None
    for i in range(n + 1):
        kept = saved(i)
        if kept and screen_at(*middle_of(kept, width, height), screens):
            pos = kept
        else:
            pos = corner(screens[0], width, height) if i == 0 else beside(pos, width, height, screens)
    return pos


def resized_pos(pos, old, new):
    """Her top left `pos` once her size goes from `old` to `new` (w, h):
    her feet stay where they stood."""
    return {"x": round(pos["x"] + (old[0] - new[0]) / 2), "y": pos["y"] + old[1] - new[1]}


def card_spot(pos, size, card_size, screens):
    """Where the hover card goes: left of her, right when there is no room,
    always on her display."""
    (width, height), (card_w, card_h) = size, card_size
    screen = nearest_screen(*middle_of(pos, width, height), screens)
    x = pos["x"] - card_w - 12
    if x < screen.left:
        x = min(pos["x"] + width + 12, screen.right - card_w)
    y = max(screen.top, min(pos["y"] + height // 4, screen.bottom - card_h))
    return x, y


def load_pos(n):
    saved = read_json(pos_path(n))
    try:
        return {"x": int(saved["x"]), "y": int(saved["y"])}
    except (TypeError, KeyError, ValueError):
        return None


def shown_peers():
    """(slot, project) of every shown mascot: the live slot locks and their
    sessions' files."""
    peers = []
    try:
        names = os.listdir(SLOTS_DIR)
    except OSError:
        return peers
    for name in names:
        match = re.fullmatch(r"(\d+)\.lock", name)
        if not match:
            continue
        holder = read_json(os.path.join(SLOTS_DIR, name))
        if not holder or not is_alive(holder.get("pid")) or not isinstance(holder.get("key"), str):
            continue
        state = read_state(os.path.join(SESSIONS_DIR, f"{holder['key']}.json"))
        peers.append((int(match.group(1)), state.info.get("project") if state else None))
    return peers


def others_limits():
    """The usage limits every other session's file holds."""
    try:
        names = os.listdir(SESSIONS_DIR)
    except OSError:
        return []
    readings = []
    for name in names:
        path = os.path.join(SESSIONS_DIR, name)
        if name.endswith(".json") and path != SESSION_PATH:
            state = read_state(path)
            if state and isinstance(state.info.get("limits"), list):
                readings.append(state.info["limits"])
    return readings


def sweep(parent=None):
    """Clears what crashed or ended sessions left: session files nobody writes
    any more, locks of overlays that are gone, and the files of the single
    overlay that came before (its spot becomes spot 0's). A lock our own
    Claude Code's (`parent`) overlay left behind when its mod was reloaded
    stays, for this one to take over."""

    def is_leftover_lock(p):
        return p.endswith(".lock") and is_stale_lock(p) and (parent is None or (read_json(p) or {}).get("parent") != parent)

    for folder, is_leftover in (
        (SESSIONS_DIR, lambda p: p != SESSION_PATH and (age_s(p) or 0) > STALE_S),
        (SLOTS_DIR, is_leftover_lock),
    ):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            path = os.path.join(folder, name)
            if is_leftover(path):
                remove(path)

    old_pos = os.path.join(STATE_DIR, "overlay-pos.json")
    if os.path.exists(old_pos):
        if load_pos(0) is None and read_json(old_pos) is not None:
            os.makedirs(SLOTS_DIR, exist_ok=True)
            write_json(pos_path(0), read_json(old_pos))
        remove(old_pos)
    for old in ("mood.json", "overlay.lock"):
        remove(os.path.join(STATE_DIR, old))


def report(line):
    """Tells the mod something chosen in this window."""
    try:
        if sys.stdout:
            print(line, flush=True)
    except (OSError, ValueError):
        pass


# --------------------------------------------------------------- window


TICK_MS = round(1000 / fx.ANIMATE_FPS)  # while a symbol or her glitch moves
STILL_TICK_MS = 1000  # nothing moving: a new mood or tag redraws her at once
# Only her status moving (sparkles, a flickering light): it moves at 12 fps,
# on twos like anime itself, in step with her rigged frames, so it adds no
# redraws of the window (each costs 3-4 ms, the drawing itself 1-2).
STATUS_TICK_MS = 83


def next_tick_ms(age, fps, frame_count, cap):
    """When to draw next: when the next frame is due, so every frame of a
    loop shows equally long (fixed 33 ms ticks would hold 12 fps frames for
    67 and 100 ms by turns), and no later than `cap` ms (TICK_MS while a
    symbol moves, STATUS_TICK_MS while only her status does)."""
    if frame_count < 2:
        return cap
    due = (math.floor(age * fps) + 1) / fps - age
    return max(1, min(cap, math.ceil(due * 1000)))


def draw_rows(canvas, font, rows):
    """The card's rows onto `canvas`, sized to fit them."""
    canvas.delete("all")
    char = font.measure("0")
    line = font.metrics("linespace") + 2
    bar_x, bar_w = char * CARD_LABEL_CHARS, char * CARD_BAR_CHARS
    width = 0
    for i, row in enumerate(rows):
        y = i * line
        if isinstance(row, tuple) and row[0] == "dim":
            canvas.create_text(0, y, text=row[1], anchor="nw", font=font, fill=CARD_DIM)
            width = max(width, font.measure(row[1]))
        elif isinstance(row, tuple):
            _, name, percent, text = row
            canvas.create_text(0, y, text=name, anchor="nw", font=font, fill=CARD_FG)
            top, bottom = y + line * 0.28, y + line * 0.72
            canvas.create_rectangle(bar_x, top, bar_x + bar_w, bottom, fill=CARD_BAR_EMPTY, width=0)
            filled = bar_w * max(0, min(100, percent)) / 100
            if filled:
                canvas.create_rectangle(bar_x, top, bar_x + filled, bottom, fill=bar_color(percent), width=0)
            canvas.create_text(bar_x + bar_w + char, y, text=text, anchor="nw", font=font, fill=CARD_FG)
            width = max(width, bar_x + bar_w + char + font.measure(text))
        else:
            canvas.create_text(0, y, text=row, anchor="nw", font=font, fill=CARD_FG)
            width = max(width, font.measure(row))
    canvas.config(width=width, height=len(rows) * line)


def run_window(parent, starter):
    """The mascot's window, for the Claude Code `parent`; `starter` is the
    process that started this one (the mod's spawn), gone once the mod is."""
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    window = LayeredWindow(root)
    tag_px = round(TAG_POINTS * root.winfo_fpixels("1i") / 72)

    # Only while she is shown (a hidden overlay holds no art): her frames and
    # the symbols' sprites.
    art = Art()
    sprites = {}
    dressed = {"step": None, "look": None}  # her status's last look, and for which moment
    # A new size being built (resize): the height wanted (None: none), and
    # each finished build by its height, (Built, sprites).
    resizing = {"height": None, "done": {}}
    first = read_state() or SessionState("idle", {}, None, False)

    prefs = cfg.load(SETTINGS_PATH)
    set_height(prefs.size)

    state = {
        # The settings (settings.py) and their file's mtime when read.
        "prefs": prefs,
        "prefs_mtime": mtime_of(SETTINGS_PATH),
        "mood": None,
        "since": time.monotonic(),
        "frame": -1,
        "dirty": True,  # drawn anew at the next tick, frame due or not
        "tick": None,  # the next tick's after() id
        "mtimes": None,
        "drag": None,
        # Her status (context aura, failing stage light, hologram fade), the
        # one it crossfades from, and since when.
        "status": fx.CALM,
        "status_was": fx.CALM,
        "status_since": time.monotonic(),
        "info": first.info,
        "choice": first.choice,  # the session's own show or hide
        "local": None,  # one made in this window, until the mod echoes it
        "shown": False,
        "slot": None,
        "pos": {"x": 0, "y": 0},  # her top left: the window's is PAD_TOP above
        "screens": None,
        # The name tag under her feet: which session she belongs to.
        "tag_text": "Claude Code",
        "tag": tag_image("Claude Code", tag_px),
        # Her projection playing (Playing: intro, outro or channel change),
        # and the last /clear seen (a new one changes the channel).
        "act": None,
        "cleared": first.cleared,
        "character": first.character,  # the one the mod wants shown
        "ending": False,  # the session is over: she goes, then the overlay
        "closed": False,  # and the window is gone
        "handover": False,  # the mod was reloaded: the next overlay takes her spot
        # Carried by a drag (effects.Carry), until she has landed and stopped
        # swinging; meanwhile the window has DRAG_PAD more room on every side.
        "carry": None,
        "margin": 0,
        # A new version: the last word of one seen (epoch ms), one waiting
        # to play (its version, while she cannot: hidden, coming in, carried)
        # and since when it plays (monotonic s).
        "celebrated": 0,
        "celebrate": None,
        "celebration": None,
        # Her call to the pointer (magic.py): the last word of one seen
        # (epoch ms; one already in the file at the start is old), and one
        # waiting for you, {test, seen (monotonic s)}.
        "called": first.call[0] if first.call else 0,
        "call": None,
    }
    calls = magic.Magic(root)

    def calm():
        return state["prefs"].calm

    def play(kind, then=None):
        """Starts a projection; `then` runs once it is over."""
        now = time.monotonic()
        state["act"] = Playing(kind, now, then, calm())
        state["carry"] = None
        if kind == "intro":
            # Her symbol and the status come once she is whole.
            state["since"] = now + fx.lock_in(calm())
            state["status_was"], state["status_since"] = fx.CALM, now + fx.act_length("intro", calm())
        redraw()

    def playing(kind):
        return state["act"] is not None and state["act"].kind == kind

    def place():
        """Puts the window where she stands now."""
        window.show(None, *corner_at())

    def corner_at():
        """The window's top left: PAD_LEFT and PAD_TOP beside hers, and the
        room she swings in while carried."""
        return state["pos"]["x"] - fx.PAD_LEFT - state["margin"], state["pos"]["y"] - fx.PAD_TOP - state["margin"]

    def size():
        """Her size with the name tag: what spots are laid out by. Symbols
        stand in the window's pad above and right of it."""
        width, height = art.size()
        return width, height + fx.UNDER_GAP + state["tag"].height

    def screens():
        found = list_screens()
        return found or [Screen(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]

    def spot():
        """Where she stands now: her spot's dragged place, or its place in the line."""
        width, height = size()
        state["screens"] = screens()
        return slot_spot(state["slot"] or 0, width, height, state["screens"], load_pos)

    def load_art():
        if not art.load():
            sys.exit(f"No frames found in {FRAMES_DIR}")
        sprites.update(fx.build_sprites(HEIGHT))
        state["frame"] = -1

    def draw(frame, mood, t, age):
        height = fx.PAD_TOP + frame.height + fx.UNDER_GAP + state["tag"].height
        act = state["act"]
        if act and act.kind != "channel":
            # Coming or going: the projection instead of her status.
            shown = fx.projection(act.kind, frame, t - act.since, t, height, act.calm)
            glitch = 0.0 if calm() else max(shown.glitch, fx.glitch_amount(mood, age) if age >= 0 else 0.0)
            draws = list(shown.draws)
            if act.kind == "intro" and age >= 0:
                draws += fx.placements(mood, frame.width, frame.height, t, age)
            image = fx.compose(fx.glitch(shown.frame, glitch, t), draws, sprites, fx.faded(state["tag"], shown.tag), shown.behind)
            state["margin"] = 0
            window.show(image, *corner_at())
            return
        # Her status moves at 12 fps (STATUS_TICK_MS): while a symbol redraws
        # her at 30, the same look is drawn again rather than worked out anew.
        step = (id(frame), math.floor(t * 1000 / STATUS_TICK_MS), state["status"], state["status_was"], height, calm())
        if dressed["step"] != step:
            dressed["step"] = step
            dressed["look"] = fx.dress(frame, state["status"], state["status_was"], t - state["status_since"], t, height,
                                       sprites, calm())
        look = dressed["look"]
        her, glitch = look.frame, max(fx.glitch_amount(mood, age), look.glitch)
        if mood == "beam" and not state["carry"]:
            her = fx.recoil(her, age)
        if act:  # the channel changing
            shown = fx.projection(act.kind, her, t - act.since, t, height, act.calm)
            her, glitch = shown.frame, max(glitch, shown.glitch)
        carry = state["carry"]
        if carry:
            glitch = max(glitch, carry.glitch(t))
        frame = her if calm() else fx.glitch(her, glitch, t)
        draws = [] if act else fx.placements(mood, frame.width, frame.height, t, age)
        if carry:
            image = carry.draw(frame, look.behind, look.over, draws, sprites, state["tag"], height, t)
            state["margin"] = fx.DRAG_PAD
            window.show(image, *corner_at())
            return
        celebration = state["celebration"]
        if celebration is not None and not act and not (mood == "beam" and fx.beam_wide(age)) and "version" in sprites:
            # A new version: the banner and its fountain need room too.
            image = fx.compose(frame, draws, sprites, state["tag"], look.behind, look.over)
            image = fx.celebrated(image, fx.updated(frame.width, frame.height, t, t - celebration, calm()), sprites)
            state["margin"] = fx.BEAM_PAD
            window.show(image, *corner_at())
            return
        if mood == "beam" and not act and fx.beam_wide(age):
            # The burst needs room past her usual edges.
            image = fx.compose(frame, [], sprites, state["tag"], look.behind, look.over)
            image = fx.beamed(image, frame.width, frame.height, age, t, draws, sprites, calm())
            state["margin"] = fx.BEAM_PAD
            window.show(image, *corner_at())
            return
        image = fx.compose(frame, draws, sprites, state["tag"], look.behind, look.over)
        state["margin"] = 0
        window.show(image, *corner_at())

    def animate():
        state["tick"] = None
        t = time.monotonic()
        act = state["act"]
        if act and t - act.since >= fx.act_length(act.kind, act.calm):
            state["act"], state["dirty"] = None, True
            if act.then:
                act.then()
                if state["closed"]:
                    return  # the window is gone
        age = t - state["since"]
        mood = state["mood"] or "idle"
        frames, fps = art.get(mood)
        carry = state["carry"]
        clock = age  # where in its loop the art plays
        if carry and carry.landed is None and art.has("held"):
            # Carried: her held pose, from when she was picked up (her
            # mood's loop until it is built).
            frames, fps = art.get("held", instead=(frames, fps))
            clock = t - carry.since
        if carry and frames:
            carry.step(t, *velocity(t), frames[int(clock * fps) % len(frames)])
            if carry.over(t):
                state["carry"], state["dirty"] = None, True
        celebrate(t)
        status_moving = fx.status_moving(state["status"], state["status_was"], t - state["status_since"], calm())
        busy = (state["act"] is not None or state["carry"] is not None or state["celebration"] is not None
                or fx.moving(mood, age))
        moving = busy or status_moving
        cap = TICK_MS if busy else STATUS_TICK_MS if status_moving else STILL_TICK_MS
        if frames and state["shown"]:
            index = int(clock * fps) % len(frames)
            if moving or index != state["frame"] or state["dirty"]:
                state["frame"], state["dirty"] = index, False
                draw(frames[index], mood, t, age)
        state["tick"] = root.after(next_tick_ms(age, fps, len(frames) if frames else 0, cap), animate)

    def celebrate(t):
        """Starts a new version's banner once she can show it (shown, not
        coming, going or carried), while the word of it is fresh; ends it."""
        due = state["celebrate"]
        if due and state["shown"] and state["act"] is None and state["carry"] is None and sprites:
            state["celebrate"] = None
            if time.time() * 1000 - due[0] < CELEBRATE_FRESH_MS:
                sprites["version"] = fx.version_banner(due[1], HEIGHT)
                state["celebration"] = t
        if state["celebration"] is not None and t - state["celebration"] >= fx.UPDATE_S:
            state["celebration"], state["dirty"] = None, True

    def redraw():
        """Draws her now (a new mood, a new tag) instead of at the next tick."""
        state["dirty"] = True
        if state["tick"]:
            root.after_cancel(state["tick"])
        animate()

    # The hover card: a window of its own beside the mascot, shown while the
    # pointer is over her.
    card = tk.Toplevel(root)
    card.overrideredirect(True)
    card.attributes("-topmost", True)
    card.config(bg=CARD_EDGE)
    card.withdraw()
    inner = tk.Frame(card, bg=CARD_BG, padx=12, pady=8)
    inner.pack(padx=1, pady=1)
    card_title = tk.Label(inner, bg=CARD_BG, fg=CARD_FG, font=("Segoe UI", 10, "bold"), anchor="w", justify="left")
    card_title.pack(fill="x")
    card_body = tk.Canvas(inner, bg=CARD_BG, highlightthickness=0, borderwidth=0)
    card_body.pack(anchor="w", pady=(4, 0))
    font = tkfont.Font(family=CARD_FONT[0], size=CARD_FONT[1])
    hover = {"shown": False, "hide": None}

    def save_pos():
        if state["slot"] is not None:
            os.makedirs(SLOTS_DIR, exist_ok=True)
            write_json(pos_path(state["slot"]), state["pos"])

    def set_mood(mood):
        if mood != state["mood"]:
            state["mood"] = mood
            state["since"] = time.monotonic()
            if playing("intro"):  # her symbol waits until she is whole
                state["since"] = max(state["since"], state["act"].since + fx.lock_in(state["act"].calm))
            redraw()

    def update_status():
        """Her status from the session's figures (the limits are the
        account's: any session may have read them last)."""
        status = status_of(state["info"], others_limits(), time.time() * 1000, state["prefs"].aura or ())
        if status != state["status"]:
            state["status_was"], state["status"] = state["status"], status
            state["status_since"] = time.monotonic()
            if state["shown"]:
                redraw()

    def update_tag():
        peers = shown_peers() if state["shown"] else []
        text = tag_text(state["info"].get("project"), state["slot"], peers)
        if text != state["tag_text"]:
            state["tag_text"], state["tag"] = text, tag_image(text, tag_px)
            redraw()

    def show():
        if state["ending"]:
            return
        if state["shown"]:
            if playing("outro"):  # shown again while going: she comes back
                play("intro")
            return
        state["shown"] = True
        load_art()
        state["slot"], took_over = claim_slot(parent)
        update_tag()
        state["pos"] = spot()
        root.deiconify()
        root.attributes("-topmost", True)
        if took_over:
            redraw()  # a reload: she was standing here already
        else:
            play("intro")

    def leave(then):
        """She goes (the outro), then `then` runs; at once when hidden."""
        if not state["shown"]:
            then()
        elif not playing("outro"):
            hide_card()
            play("outro", then)

    def hide():
        state["act"] = None
        state["carry"] = None
        state["celebration"] = None
        state["shown"] = False
        hide_card()
        root.withdraw()
        release_slot(state["slot"])
        state["slot"] = None
        art.clear()  # the art goes with the last reference to it
        sprites.clear()
        dressed.update(step=None, look=None)
        window.close()

    def end():
        """The session is over: she goes, and nothing of this mascot stays behind."""
        if state["ending"]:
            return
        state["ending"] = True

        def gone():
            state["closed"] = True
            release_slot(state["slot"])
            state["slot"] = None
            remove(SESSION_PATH)
            root.destroy()

        if playing("outro"):
            state["act"] = state["act"]._replace(then=gone)
        else:
            leave(gone)

    def follow_character():
        """A new character picked (/mascot character): she goes, the new
        one's art and look come in, and she comes back on the same spot.
        Shown again in the middle (the outro cut short), she goes again.
        Who comes back is settled as the outro ends: picked back while she
        went, she comes back as she was (no second outro)."""
        folder = frames_of(state["character"])
        if not folder or os.path.normcase(folder) == os.path.normcase(os.path.normpath(FRAMES_DIR)):
            return
        if state["ending"] or playing("outro"):
            return

        def take_on():
            folder = frames_of(state["character"]) or os.path.normpath(FRAMES_DIR)
            if os.path.normcase(folder) == os.path.normcase(os.path.normpath(FRAMES_DIR)):
                if state["shown"]:
                    play("intro")  # her art is still built
                return
            calls.stop()  # drawn in her old look
            if resizing["height"] is not None:  # a size being built: build the new art at it
                set_height(resizing["height"])
                resizing.update(height=None, done={})
            use_frames(folder)
            if not state["shown"]:
                return  # built at the next show
            art.clear()
            sprites.clear()
            dressed.update(step=None, look=None)
            load_art()
            state["pos"] = spot()
            play("intro")

        leave(take_on)

    def poll():
        watch_settings()
        mtimes = (mtime_of(SESSION_PATH), mtime_of(ALL_PATH))
        if mtimes != state["mtimes"]:
            state["mtimes"] = mtimes
            current = read_state()
            if current is not None:  # missing or half-written: keep what we have
                if current.ended:
                    end()
                    return
                set_mood(current.mood)
                if current.cleared != state["cleared"]:
                    # A /clear: the same session on a fresh conversation.
                    state["cleared"] = current.cleared
                    state["call"] = None  # you are at her terminal
                    if state["shown"] and state["act"] is None:
                        play("channel")
                if current.call and current.call[0] != state["called"]:
                    # A round is over: her call, once you are around.
                    state["called"] = current.call[0]
                    state["call"] = {"test": current.call[1], "seen": time.monotonic()}
                if current.celebrate and current.celebrate[0] != state["celebrated"]:
                    # A newer version has loaded: her banner, once.
                    state["celebrated"] = current.celebrate[0]
                    state["celebrate"] = current.celebrate
                state["info"], state["choice"], state["character"] = current.info, current.choice, current.character
                # The mod has caught up with a choice made in this window.
                if state["local"] and current.choice and current.choice[1] >= state["local"][1]:
                    state["local"] = None
            if state["ending"]:
                return
            want = is_visible(state["choice"], read_all_choice(), state["local"])
            if want and (not state["shown"] or playing("outro")):
                show()
            elif not want and state["shown"]:
                leave(hide)
        follow_character()
        answer_call()
        if not state["ending"]:
            root.after(POLL_MS, poll)

    def answer_call():
        """Sends a waiting call once you are around and not already looking
        at her session (magic.verdict); a new round of work, or her being
        in your hand, drops it. It leaves her as she fires her finish."""
        call = state["call"]
        if call is None:
            return
        if state["ending"] or (not call["test"] and (state["mood"] in ("thinking", "working") or state["drag"])):
            state["call"] = None
            return
        if time.monotonic() - call["seen"] < fx.CHARGE_S:
            return
        answer = magic.verdict(call["test"], magic.idle_s() >= magic.AWAY_S, magic.notifications_held(),
                               magic.pointer(), lambda: magic.is_watching(magic.foreground_pid(), parent, process_table(),
                                                                          magic.foreground_title()))
        if answer == "wait":
            return
        state["call"] = None
        if answer == "go":
            start = None
            if state["shown"] and art.frames.get("idle"):
                width, height = art.size()
                x, y = fx.magic_from(width, height)
                start = (state["pos"]["x"] + x, state["pos"]["y"] + y)
            calls.send(start, sprites or fx.build_sprites(HEIGHT), calm())

    def draw_card():
        if not hover["shown"]:
            return
        # The limits are the account's: another session may have read them since.
        limits = freshest_limits([state["info"].get("limits")] + others_limits())
        info = {**state["info"], "limits": limits}
        title, lines = card_lines(state["mood"] or "idle", info, time.time() * 1000)
        card_title.config(text=title)
        draw_rows(card_body, font, lines)
        card.update_idletasks()
        card_size = card.winfo_reqwidth(), card.winfo_reqheight()
        x, y = card_spot(state["pos"], size(), card_size, state["screens"] or screens())
        card.geometry(f"+{x}+{y}")
        root.after(500, draw_card)  # the turn's clock keeps running

    def hover_start(_e):
        if hover["hide"]:
            root.after_cancel(hover["hide"])
            hover["hide"] = None
        if state["drag"] is None and state["shown"] and not hover["shown"] and not playing("outro"):
            hover["shown"] = True
            draw_card()
            card.deiconify()

    def hide_card():
        if hover["hide"]:
            root.after_cancel(hover["hide"])
            hover["hide"] = None
        hover["shown"] = False
        card.withdraw()

    def hover_end(_e):
        # A gap between her and a symbol can slip the pointer off for a moment.
        if hover["hide"] is None:
            hover["hide"] = root.after(250, hide_card)

    def watch_parent():
        if state["ending"]:
            return
        if not is_alive(parent):
            end()  # Claude Code is gone (a crash): so is its session
            return
        if not is_alive(starter):
            current = read_state()
            if current is not None and current.ended:
                end()  # the session ended, then its mod went before poll saw it
                return
            # The mod was unloaded: its next overlay takes over this spot
            # (the lock stays for it) without an intro.
            state["handover"] = True
            root.destroy()
            return
        root.after(2000, watch_parent)

    def stay_on_top():
        if state["shown"] and not state["closed"]:
            window.keep_on_top()

    def watch_settings():
        """Follows settings.json: calm and the aura at once; her size as soon
        as it is built (`resize`)."""
        mtime = mtime_of(SETTINGS_PATH)
        if mtime != state["prefs_mtime"]:
            state["prefs_mtime"] = mtime
            was, state["prefs"] = state["prefs"], cfg.load(SETTINGS_PATH)
            if state["prefs"].aura != was.aura:
                update_status()
            if state["prefs"].calm != was.calm and state["shown"]:
                redraw()
        size = state["prefs"].size
        if not state["shown"]:
            resizing["height"] = None
            if size != HEIGHT:
                set_height(size)  # built at it when next shown
        elif size == HEIGHT:
            resizing["height"] = None  # back to the size she has: a build under way is dropped
        elif size != resizing["height"]:
            resize(size)

    def resize(height):
        """Builds her at a new size on a thread (idle's frames, her mood's,
        the sprites) while she plays on at the old one; `take_size` swaps it
        in. A new size picked meanwhile leaves this one's build unused."""
        resizing["height"] = height
        moods = [state["mood"]] if state["mood"] and art.has(state["mood"]) else []

        def build():
            try:
                done = build_art(height, moods), fx.build_sprites(height)
            except (OSError, ValueError):
                done = None, None  # unreadable art: she keeps her size
            resizing["done"][height] = done

        threading.Thread(target=build, daemon=True).start()
        root.after(RESIZE_CHECK_MS, take_size)

    def take_size():
        """Her new size, once built and once she is not being carried or
        coming or going: she stands on the same spot, and a dragged place
        keeps her feet where they were."""
        height = resizing["height"]
        if height is None or not state["shown"]:
            resizing.update(height=None, done={})
            return  # dropped: hidden, or the old size is back
        if height not in resizing["done"] or state["drag"] or state["carry"] or state["act"]:
            root.after(RESIZE_CHECK_MS, take_size)
            return
        built, new_sprites = resizing["done"][height]
        resizing.update(height=None, done={})
        if built is None:
            return
        old_w, old_h = art.size()
        set_height(height)
        art.adopt(built)
        sprites.clear()
        sprites.update(new_sprites)
        state["frame"] = -1
        dressed.update(step=None, look=None)
        new_w, new_h = art.size()
        kept = load_pos(state["slot"]) if state["slot"] is not None else None
        if kept:
            write_json(pos_path(state["slot"]), resized_pos(kept, (old_w, old_h), (new_w, new_h)))
        state["pos"] = spot()
        place()
        redraw()
        # Spots beside this one stand where it stands: once every mascot has
        # resized, each lines up again.
        root.after(RELAYOUT_MS, relayout)

    def relayout():
        if state["shown"] and state["drag"] is None:
            state["pos"] = spot()
            place()

    def watch_screens():
        """A display plugged in or out: she moves to where she now belongs (back
        to a dragged place whose display is back)."""
        if state["shown"] and state["drag"] is None and screens() != state["screens"]:
            state["pos"] = spot()
            place()

    def every(ms, fn):
        def tick():
            fn()
            root.after(ms, tick)

        root.after(ms, tick)

    def drag_start(e):
        state["drag"] = {"grip": (e.x_root - state["pos"]["x"], e.y_root - state["pos"]["y"]),
                         "from": (e.x_root, e.y_root), "moved": False, "moves": []}
        hide_card()
        if state["shown"] and art.has("held"):
            art.get("held")  # a head start on building it, in case this press becomes a carry

    def velocity(t):
        """The pointer's velocity (px/s) while she is carried; 0 once it stops."""
        moves = state["drag"]["moves"] if state["drag"] else []
        if not moves or t - moves[-1][0] > STILL_S:
            return 0.0, 0.0
        recent = [m for m in moves if t - m[0] <= VELOCITY_S] or moves[-1:]
        (t0, x0, y0), (t1, x1, y1) = recent[0], moves[-1]
        if t1 - t0 < 0.015:
            return 0.0, 0.0
        return (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)

    def drag_move(e):
        drag = state["drag"]
        if not drag:
            return
        # A click's hand tremor is not a drag: only one that leaves DRAG_SLOP.
        if not drag["moved"] and max(abs(e.x_root - drag["from"][0]), abs(e.y_root - drag["from"][1])) < DRAG_SLOP:
            return
        now = time.monotonic()
        if not drag["moved"] and state["shown"] and state["act"] is None:
            state["carry"] = fx.Carry(drag["grip"], now, calm())  # picked up
            redraw()
        drag["moved"] = True
        drag["moves"] = [m for m in drag["moves"] if now - m[0] <= VELOCITY_S] + [(now, e.x_root, e.y_root)]
        state["pos"] = {"x": e.x_root - drag["grip"][0], "y": e.y_root - drag["grip"][1]}
        place()

    def drag_end(_e):
        # Only a real drag pins her place: a click, or a double-click's
        # second release right after it sent her back, leaves it alone.
        if state["drag"] and state["drag"]["moved"]:
            save_pos()
        if state["carry"]:
            state["carry"].drop(time.monotonic())  # set down
        state["drag"] = None

    def reset_pos(_e):
        if state["slot"] is not None:
            remove(pos_path(state["slot"]))
        state["pos"] = spot()
        place()

    def hide_here(_e):
        state["local"] = (False, time.time() * 1000)
        leave(hide)
        report("hidden")

    root.bind("<ButtonPress-1>", drag_start)
    root.bind("<B1-Motion>", drag_move)
    root.bind("<ButtonRelease-1>", drag_end)
    root.bind("<Double-Button-1>", reset_pos)
    root.bind("<Button-3>", hide_here)
    root.bind("<Enter>", hover_start)
    root.bind("<Leave>", hover_end)

    root.withdraw()  # until poll() decides
    set_mood(first.mood)
    poll()
    watch_parent()
    every(TAG_EVERY_MS, update_tag)
    update_status()
    every(STATUS_EVERY_MS, update_status)
    every(SWEEP_EVERY_MS, sweep)
    every(SCREENS_EVERY_MS, watch_screens)
    every(ON_TOP_EVERY_MS, stay_on_top)
    try:
        root.mainloop()
    finally:
        if not state["handover"]:
            release_slot(state["slot"])


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    code = stand_apart()
    if code is not None:
        sys.exit(code)
    configure(sys.argv[1], sys.argv[2])
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp on scaled displays
    except Exception:
        pass

    if not frame_paths("idle"):
        sys.exit(f"No frames found in {FRAMES_DIR}")
    starter = starter_pid()
    parent = claude_code_of(starter, process_table())
    sweep(parent)
    run_window(parent, starter)


if __name__ == "__main__":
    main()
