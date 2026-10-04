"""The settings window: every mascot's settings (settings.py) in one window,
in the character's own colors (`frames/<name>/theme.json`). The mod opens
it (/mascot settings); a change is saved at once and every overlay follows
it live; a change made elsewhere (/mascot size, the file by hand) shows
here within a second. One window at a time: opening it again from the same
session brings the open one forward; from another session, the open one
hands over to the new one (`claim`), on the same spot.

    pythonw settings_window.py <mascot folder> <frames dir> [<session key> <project>]

It also picks the opening session's character: a tile per character (each
folder beside the frames dir with idle art), in that character's colors.
A pick says `character NAME remember|session` on stdout, which the mod
reads (remembered for the project, or for this session alone), and the
window takes on her colors at once; it follows the session file's
`character` too (/mascot character), every `POLL_MS`.

Its Updates card shows her version and what is new since the version
before (whatsnew.json; `from` in the session file's `update`), with a link
to a page of every version's news (`page` "news", the `Changelog`), turns the daily check for a newer one on and off (`checkUpdates`; turning
it on says `check`, so the mod looks at once), and, when the mod has found
one (the session file's `update`), offers it: a press says `update`, and
the mod's progress shows as it writes it. Its cursor magic card's button
says `magic`: the mod sends her call to the pointer at once, to try it.

Its Sound card turns her sounds on and sets their volume; "Choose sounds"
opens a page of its own (`page` "sounds"): how long she waits on you
before her waiting sound, and a row per moment with its own toggle, the
sound it plays, "Try" (played here through sound.py, at the volume set,
even with sound off), "Choose…" (a file dialog; the file is copied into
the mascot folder's sounds/, `adopt_sound`) and "Default" (hers again).

Everything in it is drawn with Pillow onto one Tk canvas, anime-sticker
style like her symbols (soft edges, white borders, glows): a header with
her portrait, the character card, then a card each for her size, her
effects (calm mode, smooth sparkles), the aura, the beam, cursor magic, sound and updates,
with widgets of its own (`Slider`, `Tiers`, `Toggle`...). Layout is in logical px (`WIDTH` wide), times the
display's scale.
"""

import colorsys
import json
import ctypes
import ctypes.wintypes
import math
import os
import re
import shutil
import sys
import time
import tkinter as tk
from collections import namedtuple
from tkinter import filedialog

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

import effects as fx
import settings as cfg
import sound
from mascot_overlay import THEME_FILE, fmt_tokens, is_alive, mtime_of, read_json, remove, write_json

LOCK_FILE = "settings-window.lock"  # {pid, session} of the open window
RAISE_FILE = "settings-window.raise"  # {at, handover?}: come forward, or close for pid `handover`
POS_FILE = "settings-window.pos.json"  # {x, y}: where it was last closed, opened there again
HANDOVER_S = 3.0  # how long a new window waits for the old one to close

WIDTH = 760
SS = 3  # shapes are drawn this many times larger, then scaled down: smooth edges
# A wheel's notches are gathered this long before saving; a click or a
# drag is one change, saved as the button comes up.
SAVE_DELAY_MS = 150
POLL_MS = 1000
RAISE_POLL_MS = 300
FRAME_MS = 16  # while something animates
TOGGLE_S = 0.16  # a toggle's knob slides over
DISABLED = 0.4  # a widget that does nothing now is drawn this faint

# The ranges the sliders show; the settings take more (by hand or /mascot),
# shown at the slider's end.
UPDATES = 100  # the updates card's height
SCROLL_STEP = 54  # px a wheel notch scrolls the news
MAGIC = 96  # the cursor magic card's height
SOUND = 96  # the sound card's height
SOUND_ROW = 60  # a moment's row on the sounds page
NOTIFY_ROW = 92  # a row on the notifications page
VOLUME_STEP = 5
WAITING_SHOWN = (10, 120, 5)
AURA_SHOWN = (0, 1_000_000, 10_000)  # low, high, step (and the least gap)
BEAM_SHOWN = (1, 30, 1)
MAGIC_SHOWN = (0, 30, 1)
MAGIC_ON = 1  # minutes, the first time cursor magic is turned on
SIZE_STEP = 10

# ---------------------------------------------------------------- theme

# `style`: her effects' style (theme.json's effects.style), whose ornaments decorate the stage.
Theme = namedtuple("Theme", "name subtitle beam primary primaryDeep accent accentDeep hot paper card ink muted track style")

# A character without a theme of its own: soft slate and lilac.
FALLBACK = {
    "primary": "#7C8DB5", "primaryDeep": "#56668F", "accent": "#C79BD8", "accentDeep": "#9A6FAD", "hot": "#B061C9",
    "paper": "#F0F1F7", "card": "#FFFFFF", "ink": "#2A2F45", "muted": "#7A8099", "track": "#E0E3EE",
}


def rgb(text):
    return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))


def load_theme(frames_dir):
    """The character's Theme from its theme.json; what it leaves out (or
    gets wrong) from FALLBACK."""
    data = read_json(os.path.join(frames_dir, THEME_FILE)) or {}
    colors = data.get("colors") if isinstance(data.get("colors"), dict) else {}

    def color(key):
        value = colors.get(key)
        return rgb(value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else FALLBACK[key])

    def text(key, default):
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else default

    name = text("name", os.path.basename(os.path.normpath(frames_dir)).title() or "Mascot")
    effects = data.get("effects") if isinstance(data.get("effects"), dict) else {}
    style = effects.get("style") if effects.get("style") in fx.STYLES else None
    return Theme(name, text("subtitle", "設定"), text("beam", "Beam"), *(color(k) for k in FALLBACK), style)


# ---------------------------------------------------------------- drawing

FONT_FILES = {
    "regular": ("segoeui.ttf", "arial.ttf"),
    "semibold": ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"),
    "bold": ("segoeuib.ttf", "arialbd.ttf"),
    "black": ("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf"),
    "jp": ("YuGothB.ttc", "meiryob.ttc", "msgothic.ttc"),
    "kr": ("malgunbd.ttf", "malgun.ttf"),
}
_fonts = {}


def font(kind, px, text=""):
    """A font `px` tall; Yu Gothic for text that is not plain ASCII (an
    ellipsis aside: Yu Gothic's sits mid-line), Malgun Gothic for Hangul
    (Yu Gothic has none)."""
    if fx.hangul(text):
        kind = "kr"
    elif any(ord(c) > 127 and c != "…" for c in text):
        kind = "jp"
    key = (kind, round(px))
    if key not in _fonts:
        for name in FONT_FILES[kind]:
            try:
                _fonts[key] = ImageFont.truetype(name, max(1, round(px)))
                break
            except OSError:
                continue
        else:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def faded(img, amount):
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda a: a * amount))
    return out


PASTEL = 0.5  # how much softer and lighter a blend is halfway


def blend(a, b, t):
    """`a` to `b`, `t` of the way, around the color wheel (the short way)
    and softer and lighter halfway: teal and pink meet in a pastel
    lavender, where a plain mix goes gray."""
    (h1, s1, v1), (h2, s2, v2) = (colorsys.rgb_to_hsv(*(c / 255 for c in color)) for color in (a, b))
    if s1 < 0.05 or s2 < 0.05:  # a gray has no hue to turn from
        return mix(a, b, t)
    dh = (h2 - h1 + 0.5) % 1.0 - 0.5
    soft = PASTEL * 4 * t * (1 - t)
    s = (s1 + (s2 - s1) * t) * (1 - soft)
    v = v1 + (v2 - v1) * t
    v += (1 - v) * soft
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb((h1 + dh * t) % 1.0, s, v))


def gradient(w, h, left, right):
    """A left-to-right gradient, RGBA, around the color wheel (`blend`)."""
    w, h = max(1, w), max(1, h)

    def at(x):
        return blend(left, right, x / max(1, w - 1)) + (255,)

    strip = Image.new("RGBA", (w, 1))
    strip.putdata([at(x) for x in range(w)])
    return strip.resize((w, h))


def pill_mask(w, h, radius=None):
    """An "L" rounded rectangle w by h (a pill by default), smooth-edged."""
    big = Image.new("L", (w * SS, h * SS), 0)
    r = (min(w, h) / 2 if radius is None else radius) * SS
    ImageDraw.Draw(big).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def disc_mask(d):
    big = Image.new("L", (d * SS, d * SS), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * SS - 1, d * SS - 1), fill=255)
    return big.resize((d, d), Image.LANCZOS)


def filled(mask, fill):
    """`fill` (a color, or an image of the mask's size) cut to `mask`."""
    out = fill.copy() if isinstance(fill, Image.Image) else Image.new("RGBA", mask.size, fill + (255,))
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask))
    return out


def shadow(mask, blur, color, strength):
    """A soft shadow of `mask`, on a canvas `blur`*2 larger each way."""
    pad = blur * 2
    shape = Image.new("L", (mask.width + 2 * pad, mask.height + 2 * pad), 0)
    shape.paste(mask, (pad, pad))
    out = Image.new("RGBA", shape.size, color + (0,))
    out.putalpha(shape.filter(ImageFilter.GaussianBlur(blur)).point(lambda a: a * strength))
    return out


def drop(out, mask, x, y, blur, color, strength, dy=0):
    """A soft shadow of `mask` onto `out`, under where `mask` goes at (x, y),
    `dy` lower."""
    put(out, shadow(mask, blur, color, strength), x - 2 * blur, y - 2 * blur + dy)


def put(out, img, x, y):
    """`img` onto `out` at (x, y), clipped."""
    x, y = round(x), round(y)
    if x + img.width <= 0 or y + img.height <= 0 or x >= out.width or y >= out.height:
        return
    out.alpha_composite(img, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


def text(out, xy, words, kind, px, fill, anchor="la", stroke=0, stroke_fill=None):
    ImageDraw.Draw(out).text(xy, words, font=font(kind, px, words), fill=fill + (255,) if len(fill) == 3 else fill,
                             anchor=anchor, stroke_width=round(stroke), stroke_fill=stroke_fill)


def fit(words, kind, px, width):
    """`words`, cut short with an ellipsis to fit `width` px."""
    if text_width(words, kind, px) <= width:
        return words
    while words and text_width(words + "…", kind, px) > width:
        words = words[:-1]
    return words.rstrip() + "…"


def wrap(words, kind, px, width, most):
    """`words` in lines that fit `width` px, at `most` lines (the last cut short)."""
    lines, line = [], ""
    for word in words.split():
        if line and text_width(f"{line} {word}", kind, px) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    if len(lines) > most:
        lines = lines[:most - 1] + [fit(" ".join(lines[most - 1:]) + " …", kind, px, width)]
    return [fit(line, kind, px, width) for line in lines]


def text_width(words, kind, px):
    return font(kind, px, words).getlength(words)


# ---------------------------------------------------------------- what's new

# whatsnew.json: { "0.17.0": ["a line", {"text": "a line", "kind": "fix"}] }.
# A line is news unless marked a fix. The mod reads it by the same rules
# (`notesBetween` in hooks/register.tsx): keep them in step.
News = namedtuple("News", "version text is_fix")
VERSION = re.compile(r"^\d+(\.\d+){1,3}$")


def version_key(v):
    parts = [int(p) for p in v.split(".")]
    return parts + [0] * (4 - len(parts))


def notes_between(data, since, to):
    """The lines of the versions after `since` (None: every one) up to `to`,
    newest first."""
    if not isinstance(data, dict):
        return []
    versions = [v for v in data if isinstance(v, str) and VERSION.match(v) and version_key(v) <= version_key(to)
                and (since is None or version_key(v) > version_key(since))]
    out = []
    for v in sorted(versions, key=version_key, reverse=True):
        lines = data[v] if isinstance(data[v], list) else []
        for line in lines:
            if isinstance(line, str) and line.strip():
                out.append(News(v, line, False))
            elif isinstance(line, dict) and isinstance(line.get("text"), str) and line["text"].strip():
                out.append(News(v, line["text"], line.get("kind") == "fix"))
    return out


def headline(news):
    """The line to lead with: the newest that is not a fix, else the newest."""
    return next((n for n in news if not n.is_fix), news[0] if news else None)


def knob(d, ring, theme, grow=0.0):
    """A slider's knob: a white disc with a colored ring and a soft shadow,
    `grow` (0..1) larger under the pointer."""
    d = round(d * (1 + 0.15 * grow))
    mask = disc_mask(d)
    out = shadow(mask, max(1, d // 6), theme.ink, 0.35)
    pad = max(1, d // 6) * 2
    put(out, filled(mask, ring), pad, pad + d * 0.05)
    inner = max(1, round(d * 0.62))
    put(out, filled(disc_mask(inner), theme.card), pad + (d - inner) / 2, pad + (d - inner) / 2 + d * 0.05)
    return out, pad


# ---------------------------------------------------------------- widgets


class Widget:
    """A part of the window at `box` (x, y, w, h in canvas px) that draws
    itself (`draw` onto a clear image its size) and may take the pointer."""

    interactive = True
    keys = None  # the settings its look depends on (App.add); None: any

    def __init__(self, app, box):
        self.app = app
        self.box = tuple(round(v) for v in box)
        self.hover = False
        self.spot = None  # which part is under the pointer, for a widget whose parts light up
        self.item = None
        self.photo = None

    @property
    def enabled(self):
        return True

    def contains(self, x, y):
        bx, by, bw, bh = self.box
        return bx <= x < bx + bw and by <= y < by + bh

    def draw(self, img):
        pass

    def spot_of(self, x, y):
        return None

    def animating(self, now):
        return False

    def press(self, x, y):
        pass

    def drag(self, x, y):
        pass

    def release(self, x, y):
        pass

    def wheel(self, steps):
        pass


class Label(Widget):
    """Text that changes with the settings: `words()`."""

    interactive = False

    def __init__(self, app, box, words, kind, px, color, anchor="la"):
        super().__init__(app, box)
        self.words, self.kind, self.px, self.color, self.anchor = words, kind, px, color, anchor

    def draw(self, img):
        x = {"l": 0, "m": img.width / 2, "r": img.width}[self.anchor[0]]
        text(img, (x, img.height / 2), self.words(), self.kind, self.px, self.color(), self.anchor[0] + "m")


class Note(Label):
    """Text that changes, wrapped onto as many lines as its box holds
    (`lead` px apart), the last cut short with an ellipsis."""

    def __init__(self, app, box, words, px, color, lead):
        super().__init__(app, box, words, "regular", px, color)
        self.lead = lead

    def draw(self, img):
        lines = wrap(self.words(), self.kind, self.px, img.width, max(1, int(img.height // self.lead)))
        for i, line in enumerate(lines):
            text(img, (0, self.lead * (i + 0.5)), line, self.kind, self.px, self.color(), "lm")


class Slider(Widget):
    """A value from `low` to `high` by `step`: `get()`, `set(value, final)`;
    `final` once the pointer lets go. A value past the range sits at its end."""

    def __init__(self, app, box, low, high, step, get, set, enabled=lambda: True):
        super().__init__(app, box)
        self.low, self.high, self.step = low, high, step
        self.get, self.set, self.is_enabled = get, set, enabled
        self.held = False

    @property
    def enabled(self):
        return self.is_enabled()

    def _span(self):
        r = self.app.u * 11
        return r, self.box[2] - 2 * r

    def value_at(self, x):
        r, span = self._span()
        p = min(1.0, max(0.0, (x - self.box[0] - r) / span))
        value = self.low + p * (self.high - self.low)
        return min(self.high, max(self.low, round(value / self.step) * self.step))

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        r, span = self._span()
        p = (min(self.high, max(self.low, self.get())) - self.low) / (self.high - self.low)
        th = max(2, round(7 * u))
        cy = img.height / 2
        put(img, filled(pill_mask(round(span + th), th), t.track), r - th / 2, cy - th / 2)
        done = round(p * span + th)
        if done > th:
            put(img, filled(pill_mask(done, th), gradient(done, th, t.primary, blend(t.primary, t.accent, p))), r - th / 2, cy - th / 2)
        k, pad = knob(round(2 * r * 0.95), blend(t.primary, t.accent, p), t, 1.0 if (self.hover or self.held) else 0.0)
        put(img, k, r + p * span - k.width / 2, cy - k.height / 2)

    def press(self, x, y):
        self.held = True
        self.set(self.value_at(x), False)

    def drag(self, x, y):
        self.set(self.value_at(x), False)

    def release(self, x, y):
        self.held = False
        self.set(self.value_at(x), True)

    def wheel(self, steps):
        value = min(self.high, max(self.low, self.get() + steps * self.step))
        self.set(value, True)


class Tiers(Widget):
    """The aura's three thresholds on one track of context, `AURA_SHOWN`:
    teal, pink and hot knobs that keep their order, a bubble over each with
    its figure. `get()` (a tuple, or False when the aura is off), `set(tiers, final)`."""

    def __init__(self, app, box, get, set):
        super().__init__(app, box)
        self.get, self.set = get, set
        self.grabbed = None

    @property
    def enabled(self):
        return self.get() is not False

    def _geometry(self):
        u = self.app.u
        r = u * 10
        return r, self.box[2] - 2 * r, self.box[3] * 0.58  # knob radius, track span, track y

    def _x(self, value):
        low, high, _ = AURA_SHOWN
        r, span, _ = self._geometry()
        return r + (min(high, max(low, value)) - low) / (high - low) * span

    def _value(self, x):
        low, high, step = AURA_SHOWN
        r, span, _ = self._geometry()
        p = min(1.0, max(0.0, (x - r) / span))
        return round((low + p * (high - low)) / step) * step

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        tiers = self.get() or cfg.DEFAULTS.aura
        colors = (t.primary, t.accent, t.hot)
        r, span, cy = self._geometry()
        th = max(2, round(7 * u))
        put(img, filled(pill_mask(round(span + th), th), t.track), r - th / 2, cy - th / 2)
        xs = [self._x(v) for v in tiers]
        ends = xs[1:] + [r + span + th / 2]
        for x0, x1, color in zip(xs, ends, colors):
            w = round(x1 - x0)
            if w > 0:
                put(img, filled(pill_mask(w, th, th / 2), color), x0, cy - th / 2)
        # The scale's ends, under the track.
        small = 10.5 * u
        text(img, (r, img.height), "0", "regular", small, t.muted, "ld")
        text(img, (r + span, img.height), fmt_tokens(AURA_SHOWN[1]), "regular", small, t.muted, "rd")
        # Bubbles over the knobs, pushed apart so they never overlap.
        bubbles = []
        for v, color in zip(tiers, colors):
            words = fmt_tokens(v) + ("+" if v > AURA_SHOWN[1] else "")
            bw = round(text_width(words, "semibold", 11 * u) + 14 * u)
            bubbles.append([words, bw, color])
        centers = list(xs)
        gap = 4 * u
        for i in range(1, 3):
            least = centers[i - 1] + (bubbles[i - 1][1] + bubbles[i][1]) / 2 + gap
            centers[i] = max(centers[i], least)
        overflow = centers[2] + bubbles[2][1] / 2 - img.width
        if overflow > 0:
            centers = [c - overflow for c in centers]
        for i in range(1, -1, -1):
            centers[i] = min(centers[i], centers[i + 1] - (bubbles[i][1] + bubbles[i + 1][1]) / 2 - gap)
        bh = round(19 * u)
        for (words, bw, color), cx in zip(bubbles, centers):
            bubble = filled(pill_mask(bw, bh), color)
            text(bubble, (bw / 2, bh / 2), words, "semibold", 11 * u, t.card, "mm")
            put(img, bubble, cx - bw / 2, 0)
        for i, (x, color) in enumerate(zip(xs, colors)):
            k, _ = knob(round(2 * r), color, t, 1.0 if self.grabbed == i or (self.hover and self.grabbed is None) else 0.0)
            put(img, k, x - k.width / 2, cy - k.height / 2)

    def press(self, x, y):
        tiers = self.get()
        if tiers is False:
            return
        local = x - self.box[0]
        xs = [self._x(v) for v in tiers]
        # The nearest knob; of knobs on one spot, the one that can move that way.
        self.grabbed = min(range(3), key=lambda i: (abs(xs[i] - local), -i if local > xs[i] else i))
        self.drag(x, y)

    def drag(self, x, y):
        if self.grabbed is None:
            return
        low, high, step = AURA_SHOWN
        tiers = list(self.get())
        i = self.grabbed
        least = (tiers[i - 1] + step) if i else max(cfg.AURA_RANGE[0], low + step)
        most = (tiers[i + 1] - step) if i < 2 else max(high, tiers[2])
        tiers[i] = min(most, max(least, self._value(x - self.box[0])))
        self.set(tuple(tiers), False)

    def release(self, x, y):
        if self.grabbed is not None:
            self.grabbed = None
            self.set(tuple(self.get()), True)


class Toggle(Widget):
    """A pill switch: `get()`, `set(on)`; its knob slides over. `words`, if
    any, stand to its right and take the click too."""

    def __init__(self, app, box, get, set, words=None, note=None, enabled=lambda: True):
        super().__init__(app, box)
        self.get, self.set, self.words, self.note, self.is_enabled = get, set, words, note, enabled
        self.since = 0.0
        self.was = get()

    @property
    def enabled(self):
        return self.is_enabled()

    def animating(self, now):
        return now - self.since < TOGGLE_S + 2 * FRAME_MS / 1000  # and its last frame

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        on = self.get()
        if on != self.was:
            self.was, self.since = on, time.monotonic()
        p = min(1.0, (time.monotonic() - self.since) / TOGGLE_S)
        p = 1 - (1 - p) ** 3
        at = p if on else 1 - p
        w, h = round(44 * u), round(24 * u)
        y = (img.height - h) / 2
        track = filled(pill_mask(w, h), t.track)
        lit = faded(filled(pill_mask(w, h), gradient(w, h, t.primary, t.accent)), at)
        track.alpha_composite(lit)
        if self.hover:
            track.alpha_composite(faded(filled(pill_mask(w, h), t.ink), 0.06))
        put(img, track, 0, y)
        d = h - round(6 * u)
        mask = disc_mask(d)
        kx = 3 * u + at * (w - d - 6 * u)
        drop(img, mask, kx, y + 3 * u, max(1, round(2 * u)), t.ink, 0.3, u)
        put(img, filled(mask, t.card), kx, y + 3 * u)
        if self.words:
            text(img, (w + 10 * u, img.height / 2), self.words, "semibold", 13 * u, t.ink, "lm")
            if self.note:
                x = w + 10 * u + text_width(self.words, "semibold", 13 * u) + 6 * u
                text(img, (x, img.height / 2), self.note, "regular", 11.5 * u, t.muted, "lm")

    def release(self, x, y):
        if self.contains(x, y):
            self.set(not self.get())


class Choice(Widget):
    """A row of options (`options`: [(words, value)]) with one picked:
    `get()`, `set(value)`. None of them is picked when `get()` is none of
    their values."""

    def __init__(self, app, box, options, get, set):
        super().__init__(app, box)
        self.options, self.get, self.set = options, get, set

    def spot_of(self, x, y):
        n = len(self.options)
        return min(n - 1, max(0, int((x - self.box[0]) / self.box[2] * n)))

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        w, h = img.size
        put(img, filled(pill_mask(w, h), t.track), 0, 0)
        n = len(self.options)
        cell = w / n
        for i, (words, value) in enumerate(self.options):
            picked = self.get() == value
            x0 = round(i * cell + 3 * u)
            cw, ch = round(cell - 6 * u), h - round(6 * u)
            if picked:
                mask = pill_mask(cw, ch)
                drop(img, mask, x0, 3 * u, max(1, round(2 * u)), t.primaryDeep, 0.35, u)
                put(img, filled(mask, gradient(cw, ch, t.primaryDeep, t.primary)), x0, 3 * u)
            elif self.hover and self.spot == i:
                put(img, filled(pill_mask(cw, ch), t.card), x0, 3 * u)
            text(img, (i * cell + cell / 2, h / 2), words, "semibold", 12.5 * u, t.card if picked else t.ink, "mm")

    def release(self, x, y):
        if self.contains(x, y):
            self.set(self.options[self.spot_of(x, y)][1])


class Button(Widget):
    """A pill button: outlined, filled under the pointer."""

    def __init__(self, app, box, words, action, enabled=lambda: True):
        super().__init__(app, box)
        self.words, self.action, self.is_enabled = words, action, enabled

    @property
    def enabled(self):
        return self.is_enabled()

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        w, h = img.size
        mask = pill_mask(w, h)
        put(img, filled(mask, t.accent), 0, 0)
        if not self.hover:
            line = max(1, round(1.6 * u))
            put(img, filled(pill_mask(w - 2 * line, h - 2 * line), t.card), line, line)
        text(img, (w / 2, h / 2), self.words, "semibold", 12.5 * u, t.card if self.hover else t.accentDeep, "mm")

    def release(self, x, y):
        if self.contains(x, y):
            self.action()


class Offer(Button):
    """A button there only while `words()` says something: the update's."""

    def __init__(self, app, box, words, action):
        super().__init__(app, box, None, action)
        self.offer = words

    @property
    def enabled(self):
        return bool(self.offer())

    def draw(self, img):
        self.words = self.offer()
        if self.words:
            super().draw(img)


class Link(Widget):
    def __init__(self, app, box, words, action):
        super().__init__(app, box)
        self.words, self.action = words, action

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        text(img, (img.width, img.height / 2), self.words, "semibold", 12 * u, t.primaryDeep, "rm")
        if self.hover:
            w = text_width(self.words, "semibold", 12 * u)
            y = img.height / 2 + 8 * u
            ImageDraw.Draw(img).line((img.width - w, y, img.width, y), fill=t.primaryDeep + (255,), width=max(1, round(u)))

    def release(self, x, y):
        if self.contains(x, y):
            self.action()


class Changelog(Widget):
    """Every version's news, newest first, scrolled by the wheel or a drag;
    the versions new since `since` are marked NEW."""

    def __init__(self, app, box, news, since):
        super().__init__(app, box)
        self.news, self.since = news, since
        self.offset = 0
        self.grip = None
        self.page = None

    def _page(self):
        """The whole list drawn once, as tall as it needs."""
        if self.page is not None:
            return self.page
        t, u = self.app.theme, self.app.u
        w = self.box[2]
        pad, gap = round(14 * u), round(4 * u)
        body, lead = 12.5 * u, round(19 * u)
        parts, y, version = [], 0, None
        for n in self.news:
            if n.version != version:
                version = n.version
                y += round(10 * u) if parts else 0
                parts.append(("version", y, n.version))
                y += round(28 * u)
            lines = wrap(n.text, "regular", body, w - 2 * pad - 18 * u, 99)
            parts.append(("line", y, (n, lines)))
            y += lead * len(lines) + gap
        img = Image.new("RGBA", (w, max(1, y + pad)), (0, 0, 0, 0))
        for kind, y, what in parts:
            if kind == "version":
                is_new = self.since is not None and version_key(what) > version_key(self.since)
                text(img, (pad, y + 12 * u), f"v{what}", "bold", 15 * u, t.primaryDeep, "lm")
                if is_new:
                    x = pad + text_width(f"v{what}", "bold", 15 * u) + 10 * u
                    tw = round(text_width("NEW", "bold", 10 * u) + 14 * u)
                    put(img, filled(pill_mask(tw, round(18 * u)), t.accent), x, y + 3 * u)
                    text(img, (x + tw / 2, y + 12 * u), "NEW", "bold", 10 * u, t.card, "mm")
            else:
                n, lines = what
                dot = round(6 * u)
                put(img, filled(disc_mask(dot), t.muted if n.is_fix else t.primary), pad + 2 * u, y + lead / 2 - dot / 2)
                for i, line in enumerate(lines):
                    text(img, (pad + 18 * u, y + lead * (i + 0.5)), line, "regular", body,
                         t.muted if n.is_fix else t.ink, "lm")
        self.page = img
        return img

    def most(self):
        return max(0, self._page().height - self.box[3])

    def scroll_to(self, offset):
        offset = max(0, min(self.most(), round(offset)))
        if offset != self.offset:
            self.offset = offset
            self.app.render(self)

    def draw(self, img):
        page = self._page()
        view = page.crop((0, self.offset, img.width, self.offset + img.height))
        if self.most():
            # Soft edges where there is more above or below.
            fade = round(22 * self.app.u)
            ramp = Image.linear_gradient("L").resize((1, fade))  # 0 at the top, 255 at the bottom
            mask = Image.new("L", view.size, 255)
            if self.offset > 0:
                mask.paste(ramp.resize((view.width, fade)), (0, 0))
            if self.offset < self.most():
                mask.paste(ramp.transpose(Image.FLIP_TOP_BOTTOM).resize((view.width, fade)), (0, view.height - fade))
            view.putalpha(ImageChops.multiply(view.getchannel("A"), mask))
        img.alpha_composite(view)
        if self.most():
            t, u = self.app.theme, self.app.u
            h = img.height
            bar = max(round(30 * u), round(h * h / page.height))
            top = round((h - bar) * self.offset / self.most())
            w = round(4 * u)
            put(img, filled(pill_mask(w, bar, w / 2), t.track), img.width - w - 2 * u, top)

    def press(self, x, y):
        self.grip = (y, self.offset)

    def drag(self, x, y):
        if self.grip:
            self.scroll_to(self.grip[1] - (y - self.grip[0]))

    def release(self, x, y):
        self.grip = None

    def wheel(self, steps):
        self.scroll_to(self.offset - steps * SCROLL_STEP * self.app.u)


class Characters(Widget):
    """A tile per character (`app.cast`: [(name, Theme, portrait)]), each in
    its own colors, the one shown filled; a click picks one (`app.pick`)."""

    def __init__(self, app, box):
        super().__init__(app, box)
        self.gap = 10 * app.u

    def _width(self):
        n = max(1, len(self.app.cast))
        return (self.box[2] - (n - 1) * self.gap) / n

    def spot_of(self, x, y):
        tile = self._width() + self.gap
        i = int((x - self.box[0]) / tile)
        inside = (x - self.box[0]) - i * tile < self._width()
        return i if inside and 0 <= i < len(self.app.cast) else None

    def draw(self, img):
        u = self.app.u
        w, h = round(self._width()), img.height
        for i, (name, theme, face) in enumerate(self.app.cast):
            x = round(i * (w + self.gap))
            picked = name == self.app.character
            mask = pill_mask(w, h, 14 * u)
            if picked:
                drop(img, mask, x, 0, max(1, round(3 * u)), theme.primaryDeep, 0.35, 2 * u)
                put(img, filled(mask, gradient(w, h, theme.primary, theme.accent)), x, 0)
            else:
                put(img, filled(mask, mix(theme.paper, theme.primary, 0.18 if self.hover and self.spot == i else 0.07)), x, 0)
            d = h - round(16 * u)
            ring = round(3 * u)
            put(img, filled(disc_mask(d + 2 * ring), (255, 255, 255) if picked else theme.primary), x + 8 * u - ring, 8 * u - ring)
            inner = gradient(d, d, mix(theme.paper, theme.primary, 0.15), mix(theme.paper, theme.accent, 0.2))
            if face is not None:
                inner.alpha_composite(face.resize((d, d), Image.LANCZOS))
            inner.putalpha(disc_mask(d))
            put(img, inner, x + 8 * u, 8 * u)
            tx = x + 8 * u + d + 12 * u
            ink = (255, 255, 255) if picked else theme.ink
            if picked:
                text(img, (tx, h / 2 - 1 * u), theme.name, "black", 17 * u, ink, "ls", 2 * u, theme.primaryDeep)
                text(img, (tx, h / 2 + 5 * u), "shown", "semibold", 11 * u, ink, "lt")
            else:
                text(img, (tx, h / 2), theme.name, "bold", 16 * u, ink, "lm")

    def release(self, x, y):
        i = self.spot_of(x, y)
        if i is not None:
            self.app.pick(self.app.cast[i][0])


class Preview(Widget):
    """Her at the chosen size on a little stage, next to a faint outline of
    her at the default size: how much bigger or smaller she will stand."""

    interactive = False

    def __init__(self, app, box, art):
        super().__init__(app, box)
        self.art = art  # her idle frame, or None
        self._cache = {}

    def figure(self, height, tint=None):
        key = (height, tint)
        if key not in self._cache:
            if len(self._cache) > 8:
                self._cache.clear()
            img = self.art.resize((max(1, round(self.art.width * height / self.art.height)), height), Image.LANCZOS)
            if tint:
                ghost = Image.new("RGBA", img.size, tint + (0,))
                ghost.putalpha(img.getchannel("A").point(lambda a: a * 0.22))
                img = ghost
            self._cache[key] = img
        return self._cache[key]

    def draw(self, img):
        t, u = self.app.theme, self.app.u
        w, h = img.size
        put(img, filled(pill_mask(w, h, 14 * u), gradient(w, h, mix(t.paper, t.primary, 0.08), mix(t.paper, t.accent, 0.1))), 0, 0)
        floor = h - 16 * u
        ring = Image.new("RGBA", (round(w * 0.8) * SS, round(12 * u) * SS), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, ring.width - 1, ring.height - 1), outline=t.primary + (150,), width=round(2 * u * SS))
        ring = ring.resize((round(w * 0.8), round(12 * u)), Image.LANCZOS)
        put(img, ring, w * 0.1, floor - ring.height / 2)
        if not self.art:
            return
        tall = h - 26 * u  # the largest size fills the stage
        per_px = tall / cfg.SIZE_RANGE[1]
        ghost = self.figure(round(cfg.DEFAULTS.size * per_px), t.primaryDeep)
        her = self.figure(max(1, round(self.app.prefs.size * per_px)))
        put(img, ghost, (w - ghost.width) / 2, floor - ghost.height)
        put(img, her, (w - her.width) / 2, floor - her.height)


# ---------------------------------------------------------------- window


class App:
    """The window: its settings (`prefs`, saved shortly after a change),
    its art, and its widgets. `show=False` builds it without putting it on
    screen (`image` then shows what it would draw); `scale` overrides the
    display's."""

    def __init__(self, state_dir, frames_dir, show=True, scale=None, session=None, project=""):
        self.state_dir = state_dir
        self.path = os.path.join(state_dir, cfg.FILE)
        self.frames_root = os.path.dirname(os.path.normpath(frames_dir))
        self.character = os.path.basename(os.path.normpath(frames_dir))
        self.session, self.project = session, project
        self.remember = True  # a pick is the project's (else this session's alone)
        self.cast = cast_of(self.frames_root)
        self.theme = load_theme(frames_dir)
        self.prefs = cfg.load(self.path)
        self.mtime = mtime_of(self.path)
        self.pending = {}
        self.save_job = None
        self.problem = ""
        # What the aura, the long-rounds beam and cursor magic were when last
        # on, for turning them on again.
        self.last_aura = self.prefs.aura or cfg.DEFAULTS.aura
        self.last_minutes = self.prefs.beamAfter or cfg.DEFAULTS.beamAfter
        self.last_magic = MAGIC_ON if self.prefs.magicAfter is False else self.prefs.magicAfter
        self.raise_mtime = mtime_of(os.path.join(state_dir, RAISE_FILE))
        # Her version and its updates (the session file's `update`), what is
        # new in it, and an update asked for here until the mod answers.
        plugin_root = os.path.dirname(self.frames_root)
        manifest = read_json(os.path.join(plugin_root, ".claude-plugin", "plugin.json")) or {}
        self.release = {"version": manifest.get("version") if isinstance(manifest.get("version"), str) else ""}
        self.notes = read_json(os.path.join(plugin_root, "whatsnew.json")) or {}
        self.asked = False
        self.read_release()
        # Or "news": every version's news; "sounds": a row per moment;
        # "notify": what else she tells you (nudge, remote, away).
        self.page = "settings"
        self.player = None  # plays a sound tried here (sound.Player), made at the first try
        # A moment's file of yours while its sound is off: turned on again, it comes back.
        self.last_sounds = {m: v for m, v in self.prefs.sounds.items() if isinstance(v, str)}

        self.root = tk.Tk()
        self.root.withdraw()
        self.u = scale or self.root.winfo_fpixels("1i") / 96
        self.art = idle_art(frames_dir)
        self.grabbed = None
        self.anim_job = None
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.build()
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda _e: self.on_motion(None))
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.root.bind("<Escape>", lambda _e: self.on_escape())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        if not show:
            return
        self.root.geometry("+%d+%d" % self.spot())
        self.root.deiconify()
        self.root.after(POLL_MS, self.poll)
        self.root.after(RAISE_POLL_MS, self.watch_raise)

    def build(self):
        """Lays out and draws the window in the character's colors: at the
        start, and again when she changes."""
        self.widgets = []
        self.layout()
        paper = "#%02x%02x%02x" % self.theme.paper
        self.root.title(f"{self.theme.name} · Mascot settings")
        self.root.configure(bg=paper)
        self.canvas.delete("all")
        self.canvas.config(width=self.bg.width, height=self.bg.height, bg=paper)
        self.bg_photo = ImageTk.PhotoImage(self.bg, master=self.root)
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
        for widget in self.widgets:
            self.render(widget)
        if self.portrait:
            self.icon = ImageTk.PhotoImage(self.portrait.resize((64, 64), Image.LANCZOS), master=self.root)
            self.root.iconphoto(True, self.icon)

    def spot(self):
        """Where it opens: where it was last closed, while that is on a
        display; else the middle of the main one."""
        pos = read_json(os.path.join(self.state_dir, POS_FILE)) or {}
        x, y = pos.get("x"), pos.get("y")
        if isinstance(x, int) and isinstance(y, int) and on_a_display(x + 40, y + 20):
            return x, y
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return max(0, (sw - self.bg.width) // 2), max(0, (sh - self.bg.height) // 2 - round(20 * self.u))

    # ---- her character

    def pick(self, name):
        """Picks `name` for the session that opened the window (the mod reads
        it on stdout), and takes on her colors."""
        if name == self.character:
            return
        say(f"character {name} {'remember' if self.remember else 'session'}")
        self.use(name)

    def use(self, name):
        self.flush()
        self.character = name
        frames_dir = os.path.join(self.frames_root, name)
        self.theme = load_theme(frames_dir)
        self.art = idle_art(frames_dir)
        self.grabbed = None
        self.build()

    def session_data(self):
        if not self.session:
            return {}
        return read_json(os.path.join(self.state_dir, "sessions", f"{self.session}.json")) or {}

    def follow_session(self):
        """The session's character changed elsewhere (/mascot character),
        or its update moved on."""
        data = self.session_data()
        name = data.get("character")
        if isinstance(name, str) and name != self.character and any(n == name for n, _, _ in self.cast):
            self.use(name)
        if self.read_release(data):
            self.refresh({"release"})

    # ---- her version and updates

    def read_release(self, data=None):
        """Takes on the session file's `update`; whether it changed."""
        update = (data if data is not None else self.session_data()).get("update")
        if not isinstance(update, dict) or not isinstance(update.get("version"), str):
            return False
        release = {k: update[k] for k in ("version", "latest", "state", "message", "from", "installed")
                   if isinstance(update.get(k), str)}
        if release.get("state") in ("updating", "updated", "failed"):
            self.asked = False  # the mod has answered
        changed = release != self.release
        self.release = release
        return changed

    def release_offer(self):
        """The update button's words, when there is an update to offer."""
        r = self.release
        if self.asked or r.get("state") in ("updating", "updated") or r.get("installed"):
            return ""
        if r.get("state") == "failed":
            return "Try again"
        return f"Update to v{r['latest']}" if r.get("latest") else ""

    def release_lines(self):
        """The updates card's headline and the line under it."""
        r, version = self.release, self.release.get("version", "")
        state = "updating" if self.asked else r.get("state")
        if state == "updating":
            return "Updating…", "She is fetching her new version."
        if state == "updated":
            return "Updated!", r.get("message", "")
        if state == "failed":
            return "The update failed", r.get("message", "")
        if r.get("installed"):
            return f"v{r['installed']} is installed", "Type /reload-plugins in her session to meet her."
        if r.get("latest"):
            return f"v{r['latest']} is out!", f"She is v{version} now."
        lead = headline(self.news())
        if lead:
            return (f"New since v{r['from']}" if r.get("from") else f"New in v{version}"), lead.text
        return (f"v{version}" if version else "Her version"), (
            "She is up to date." if self.prefs.checkUpdates and r.get("version") else "")

    def news(self):
        """What is new since the version before (else in this one)."""
        version, since = self.release.get("version", ""), self.release.get("from")
        if not VERSION.match(version):
            return []
        if since and VERSION.match(since):
            return notes_between(self.notes, since, version)
        return [n for n in notes_between(self.notes, None, version) if n.version == version]

    def show_page(self, page):
        """The settings, or every version's news, in the same window."""
        if page != self.page:
            self.flush()
            self.page = page
            self.grabbed = None
            self.build()

    def on_escape(self):
        """Esc: back from the news or the sounds, else closes."""
        if self.page != "settings":
            self.show_page("settings")
        else:
            self.close()

    def ask_update(self):
        say("update")
        self.asked = True
        self.refresh({"release"})

    def set_check_updates(self, on):
        self.change(checkUpdates=on)
        if on:
            self.flush()  # saved before the mod reads it
            say("check")

    # ---- settings

    def change(self, final=True, **values):
        """Settings changed here: drawn at once, saved once `final`."""
        self.prefs = self.prefs._replace(**values)
        if self.prefs.aura:
            self.last_aura = self.prefs.aura
        if self.prefs.beamAfter:
            self.last_minutes = self.prefs.beamAfter
        if self.prefs.magicAfter is not False:
            self.last_magic = self.prefs.magicAfter
        if final:
            self.pending.update(values)
            if self.save_job:
                self.root.after_cancel(self.save_job)
            self.save_job = self.root.after(SAVE_DELAY_MS, self.save)
        self.refresh(values)

    def save(self):
        self.save_job = None
        changes, self.pending = self.pending, {}
        try:
            cfg.save(self.path, **changes)
            self.problem = ""
        except OSError as err:
            self.problem = f"Could not save: {err.strerror or err}"
        self.mtime = mtime_of(self.path)
        self.refresh({"problem"})

    def poll(self):
        """A change made elsewhere (/mascot, the file by hand) shows here."""
        mtime = mtime_of(self.path)
        if mtime != self.mtime and self.grabbed is None and not self.pending:
            self.mtime = mtime
            self.prefs = cfg.load(self.path)
            self.last_aura = self.prefs.aura or self.last_aura
            self.last_minutes = self.prefs.beamAfter or self.last_minutes
            if self.prefs.magicAfter is not False:
                self.last_magic = self.prefs.magicAfter
            self.refresh()
        if self.grabbed is None:
            self.follow_session()
        self.root.after(POLL_MS, self.poll)

    def magic_minutes(self):
        """Cursor magic's minutes, or what they were when last on."""
        return self.last_magic if self.prefs.magicAfter is False else self.prefs.magicAfter

    # ---- sounds

    def frames_dir(self):
        return os.path.join(self.frames_root, self.character)

    def sounds_dir(self):
        return os.path.join(self.state_dir, sound.FOLDER)

    def set_sound(self, moment, choice):
        if isinstance(choice, str):
            self.last_sounds[moment] = choice
        elif choice is True:
            self.last_sounds.pop(moment, None)
        self.change(sounds={**self.prefs.sounds, moment: choice})

    def toggle_sound(self, moment, on):
        """A moment's sound off, or on again: the file of yours it had, else hers."""
        self.set_sound(moment, self.last_sounds.get(moment, True) if on else False)

    def sound_words(self, moment):
        """What a moment plays, in words, and the color to say it in."""
        t, choice = self.theme, self.prefs.sounds[moment]
        if choice is False:
            return "None", t.muted
        if isinstance(choice, str):
            if os.path.isfile(sound.own_path(choice, self.state_dir)):
                return choice, t.primaryDeep
            return f"{choice} is missing: hers plays", t.accentDeep
        return f"{t.name}'s own", t.ink

    def try_sound(self, moment):
        """Plays a moment's sound here, at the volume set, sound on or off."""
        choice = self.prefs.sounds[moment]
        path = sound.resolve(choice if choice is not False else True, moment, self.frames_dir(), self.state_dir)
        if path is None:
            self.problem = "She has no sound of her own for that one."
            self.refresh({"problem"})
            return
        if self.player is None:
            self.player = sound.Player(os.path.join(self.state_dir, sound.GATE_FILE))
        self.player.play(path, self.prefs.volume, sound.PRIORITY[moment], force=True)

    def choose_sound(self, moment):
        """A file dialog for a moment's sound; the file picked is adopted."""
        path = filedialog.askopenfilename(parent=self.root, title=f"A sound for: {MOMENT_NAMES[moment][0]}",
                                          filetypes=[("Sounds (.wav, .mp3)", "*.wav *.mp3")])
        if path:
            self.adopt_sound(moment, path)

    def adopt_sound(self, moment, path):
        """Makes the file at `path` the moment's sound: checked (a .wav or
        .mp3 that plays here, up to sound.MAX_S), copied into sounds/ and
        played once. Whether it was taken; why not in `problem`."""
        problem, name = "", None
        seconds = sound.length_of(path) if os.path.splitext(path)[1].lower() in (".wav", ".mp3") else None
        if seconds is None:
            problem = "That file does not play here: a .wav or .mp3, please."
        elif seconds > sound.MAX_S:
            problem = f"That one lasts {seconds:.0f} s: up to {sound.MAX_S:.0f} s, please."
        else:
            try:
                name = copy_in(path, self.sounds_dir())
            except OSError as err:
                problem = f"Could not copy it: {err.strerror or err}"
        self.problem = problem
        self.refresh({"problem"})
        if problem:
            return False
        self.set_sound(moment, name)
        self.flush()
        self.try_sound(moment)
        return True

    def open_sounds(self):
        try:
            os.makedirs(self.sounds_dir(), exist_ok=True)
            os.startfile(self.sounds_dir())  # noqa: S606 - the user's own sounds folder
        except OSError as err:
            self.problem = f"Could not open it: {err.strerror or err}"
            self.refresh({"problem"})

    def set_remember(self, on):
        self.remember = on
        self.refresh({"remember"})

    def reset(self):
        self.change(**cfg.DEFAULTS._asdict())

    def open_file(self):
        if not os.path.exists(self.path):
            cfg.save(self.path)
            self.mtime = mtime_of(self.path)
        try:
            os.startfile(self.path)  # noqa: S606 - the user's own settings file, in their editor
        except OSError as err:
            self.problem = f"Could not open it: {err.strerror or err}"
            self.refresh({"problem"})

    # ---- drawing

    def layout(self):
        """The window's background (header, cards, fixed words) and its widgets."""
        t, u = self.theme, self.u
        W, M = WIDTH, 18
        col = (W - 3 * M) / 2
        CAST = 100  # the character card's height
        H = 548 + CAST + 14 + MAGIC + 14 + SOUND + 14 + UPDATES + 14
        self.bg = Image.new("RGBA", (round(W * u), round(H * u)), t.paper + (255,))
        self.portrait = portrait(self.art)
        draw_header(self.bg, t, u, self.portrait)
        cast_top = 134
        top = cast_top + CAST + 14
        if self.page == "news":
            return self.layout_news(W, M, H, cast_top)
        if self.page == "sounds":
            return self.layout_sounds(W, M, H, cast_top)
        if self.page == "notify":
            return self.layout_notify(W, M, H, cast_top)

        def card(x, y, w, h, jp, en, lines, value=None):
            """A card, its chip and title, and its description; (x, y) of its inside."""
            draw_card(self.bg, t, u, x, y, w, h)
            chip_w = draw_chip(self.bg, t, u, x + 16, y + 15, jp)
            text(self.bg, ((x + 16) * u + chip_w + 8 * u, (y + 26) * u), en, "bold", 15.5 * u, t.ink, "lm")
            for i, line in enumerate(lines):
                text(self.bg, ((x + 16) * u, (y + 48 + 17 * i) * u), line, "regular", 12 * u, t.muted, "la")
            return x, y

        def box(x, y, w, h):
            return (x * u, y * u, w * u, h * u)

        sizes = [(words.title(), px) for words, px in cfg.SIZES.items()]

        # Size
        x, y = card(M, top, col, 196, "サイズ", "Size", ["How tall she stands."])
        self.add(Label(self, box(x + col - 16 - 120, y + 14, 120, 24), lambda: f"{self.prefs.size} px",
                       "bold", 15.5 * u, lambda: t.primaryDeep, "rm"), "size")
        self.add(Choice(self, box(x + 16, y + 78, 196, 32), sizes, lambda: self.prefs.size,
                        lambda v: self.change(size=v)), "size")
        self.add(Slider(self, box(x + 16, y + 122, 196, 30), *cfg.SIZE_RANGE, SIZE_STEP,
                        lambda: self.prefs.size, lambda v, final: self.change(final, size=v)), "size")
        text(self.bg, ((x + 16 + 11) * u, (y + 158) * u), f"{cfg.SIZE_RANGE[0]}", "regular", 10.5 * u, t.muted, "la")
        text(self.bg, ((x + 16 + 196 - 11) * u, (y + 158) * u), f"{cfg.SIZE_RANGE[1]} px", "regular", 10.5 * u, t.muted, "ra")
        self.add(Preview(self, box(x + col - 16 - 112, y + 50, 112, 132), self.art), "size")

        # Effects: calm mode and smooth sparkles, side by side (smooth has
        # nothing to do in calm mode, and says so)
        x, y = card(M, top + 196 + 14, col, 140, "エフェクト", "Effects", [])
        self.add(Toggle(self, box(x + 16, y + 42, col - 32, 26), lambda: self.prefs.calm,
                        lambda v: self.change(calm=v), "Calm mode"), "calm")
        text(self.bg, ((x + 70) * u, (y + 76) * u), "No glitch, particles, flicker or flashes.", "regular", 11.5 * u,
             t.muted, "lm")
        self.add(Toggle(self, box(x + 16, y + 88, col - 32, 26), lambda: self.prefs.smooth,
                        lambda v: self.change(smooth=v), "Smooth sparkles", "uses more CPU",
                        enabled=lambda: not self.prefs.calm), "smooth", "calm")
        self.add(Label(self, box(x + 70, y + 114, col - 86, 16), lambda: (
            "Off in calm mode: it has no sparkles." if self.prefs.calm
            else "Sparkles move as smoothly as her symbols."), "regular", 11.5 * u, lambda: t.muted), "smooth", "calm")

        # The aura
        x2 = M + col + M
        x, y = card(x2, top, col, 160, "オーラ", "Aura",
                    ["She glows as the context grows, brighter", "at each step, until she overloads."])
        self.add(Toggle(self, box(x + col - 16 - 44, y + 14, 44, 24), lambda: self.prefs.aura is not False,
                        lambda v: self.change(aura=self.last_aura if v else False)), "aura")
        self.add(Tiers(self, box(x + 16, y + 92, col - 32, 54), lambda: self.prefs.aura,
                       lambda v, final: self.change(final, aura=v)), "aura")

        # The beam
        x, y = card(x2, top + 160 + 14, col, 176, "ビーム", t.beam,
                    ["Her big finish when a round of work is done:", "after a long one, or one agents helped with."])
        self.add(Toggle(self, box(x + 16, y + 96, 150, 26), lambda: self.prefs.beamAfter is not False,
                        lambda v: self.change(beamAfter=self.last_minutes if v else False), "After rounds of"),
                 "beamAfter")
        self.add(Slider(self, box(x + 168, y + 94, col - 168 - 16 - 54, 30), *BEAM_SHOWN,
                        lambda: self.prefs.beamAfter or self.last_minutes,
                        lambda v, final: self.change(final, beamAfter=v),
                        enabled=lambda: self.prefs.beamAfter is not False), "beamAfter")
        self.add(Label(self, box(x + col - 16 - 54, y + 96, 54, 26),
                       lambda: f"{self.prefs.beamAfter or self.last_minutes} min", "bold", 13.5 * u,
                       lambda: t.primaryDeep if self.prefs.beamAfter else t.muted, "rm"), "beamAfter")
        self.add(Toggle(self, box(x + 16, y + 134, col - 32, 26), lambda: self.prefs.beamForAgents,
                        lambda v: self.change(beamForAgents=v), "When agents helped"), "beamForAgents")

        # Cursor magic
        my = top + 350 + 14
        x, y = card(M, my, W - 2 * M, MAGIC, "まほう", "Cursor magic",
                    ["When a round of work ends, she sends magic", "to your pointer, on any display."])
        panel = x + 380
        pw = W - 2 * M - 380 - 16

        def on():
            return self.prefs.magicAfter is not False

        self.add(Toggle(self, box(panel, y + 14, 150, 26), on,
                        lambda v: self.change(magicAfter=self.last_magic if v else False), "After rounds of"), "magicAfter")
        self.add(Slider(self, box(panel + 152, y + 12, pw - 152 - 58, 30), *MAGIC_SHOWN, self.magic_minutes,
                        lambda v, final: self.change(final, magicAfter=v), enabled=on), "magicAfter")
        self.add(Label(self, box(panel + pw - 54, y + 14, 54, 26), lambda: f"{self.magic_minutes()} min", "bold", 13.5 * u,
                       lambda: t.primaryDeep if on() else t.muted, "rm"), "magicAfter")
        self.add(Button(self, box(panel + pw - 130, y + 52, 130, 30), "Send one now", lambda: say("magic")))
        self.add(Button(self, box(panel + pw - 130 - 10 - 150, y + 52, 150, 30), "Notifications…",
                        lambda: self.show_page("notify")))

        # Sound
        sy = my + MAGIC + 14
        x, y = card(M, sy, W - 2 * M, SOUND, "サウンド", "Sound",
                    ["A chime when she waits on you, a cheer when", "work is done, and more. Quiet while hidden."])
        self.add(Toggle(self, box(panel, y + 14, 150, 26), lambda: self.prefs.sound,
                        lambda v: self.change(sound=v), "Sounds on"), "sound")
        self.volume_widgets(panel + 152, y + 12, pw - 152)
        self.add(Button(self, box(panel + pw - 150, y + 52, 150, 30), "Choose sounds…", lambda: self.show_page("sounds")))

        # Updates
        uy = sy + SOUND + 14
        x, y = card(M, uy, W - 2 * M, UPDATES, "アップデート", "Updates", [])
        self.add(Label(self, box(x + 16, y + 40, 330, 18), lambda: (
            "Once a day, a look at her newest version on GitHub." if self.prefs.checkUpdates
            else "Off: she never goes online. /mascot update works anyway."),
            "regular", 12 * u, lambda: t.muted), "checkUpdates")
        self.add(Toggle(self, box(x + 16, y + 64, 330, 26), lambda: self.prefs.checkUpdates, self.set_check_updates,
                        "Look for new versions"), "checkUpdates")
        panel = x + 380
        pw = W - 2 * M - 380 - 16
        self.add(Label(self, box(panel, y + 12, pw - 176, 30), lambda: self.release_lines()[0],
                       "bold", 15 * u, lambda: t.accentDeep if self.release_offer() else t.primaryDeep), "release",
                 "checkUpdates")
        self.add(Note(self, box(panel, y + 42, pw, 22), lambda: self.release_lines()[1],
                      12 * u, lambda: t.muted, 18 * u), "release", "checkUpdates")
        self.add(Link(self, box(panel + pw - 200, y + 66, 200, 24), "What's new in every version",
                      lambda: self.show_page("news")))
        self.add(Offer(self, box(panel + pw - 168, y + 12, 168, 32), self.release_offer, self.ask_update), "release")

        # Footer
        fy = uy + UPDATES + 14
        self.add(Label(self, box(M + 4, fy, 400, 32), lambda: self.problem or "Every mascot follows these at once.",
                       "regular", 12 * u, lambda: t.accentDeep if self.problem else t.muted), "problem")
        self.add(Button(self, box(W - M - 104, fy, 104, 32), "Reset all", self.reset))
        self.add(Link(self, box(W - M - 104 - 16 - 140, fy, 140, 32), "Open settings.json", self.open_file))

        # Her character (last, so the cards above keep their order among the widgets)
        tiles = min(len(self.cast), 3) * 150 + (min(len(self.cast), 3) - 1) * 10
        x, y = card(M, cast_top, W - 2 * M, CAST, "キャラクター", "Character", [])
        self.add(Label(self, box(x + 16, y + 40, W - 2 * M - 48 - tiles, 20),
                       lambda: ("For this project's sessions, now and when they start."
                                if self.remember else "For this session only."),
                       "regular", 12 * u, lambda: t.muted), "remember")
        where = f"Remember for {self.project}" if self.project else "Remember for this project"
        self.add(Toggle(self, box(x + 16, y + 64, W - 2 * M - 48 - tiles, 26), lambda: self.remember,
                        self.set_remember, where), "remember")
        self.add(Characters(self, box(x + W - 2 * M - 16 - tiles, y + 14, tiles, CAST - 28)), "character")

    def layout_news(self, W, M, H, top):
        """The news page: every version's news on one card, and the way back."""
        t, u = self.theme, self.u
        fy = H - 14 - 32
        h = fy - 14 - top
        draw_card(self.bg, t, u, M, top, W - 2 * M, h)
        chip_w = draw_chip(self.bg, t, u, M + 16, top + 15, "おしらせ")
        text(self.bg, ((M + 16) * u + chip_w + 8 * u, (top + 26) * u), "What's new", "bold", 15.5 * u, t.ink, "lm")
        since = self.release.get("from")
        sub = f"Newest first. Marked NEW: since v{since}, the version before." if since else "Newest first."
        text(self.bg, ((M + 16) * u, (top + 48) * u), sub, "regular", 12 * u, t.muted, "la")
        news = notes_between(self.notes, None, self.release.get("version") or "999")
        self.add(Changelog(self, (M * u, (top + 70) * u, (W - 2 * M - 8) * u, (h - 70 - 12) * u), news, since))
        self.add(Label(self, ((M + 4) * u, fy * u, 400 * u, 32 * u), lambda: "Scroll for older versions. Esc goes back.",
                       "regular", 12 * u, lambda: t.muted))
        self.add(Button(self, ((W - M - 104) * u, fy * u, 104 * u, 32 * u), "Back", lambda: self.show_page("settings")))

    def volume_widgets(self, x, y, w):
        """The volume's slider and its figure, `w` wide from (x, y)."""
        t, u = self.theme, self.u
        self.add(Slider(self, (x * u, y * u, (w - 58) * u, 30 * u), *cfg.VOLUME_RANGE, VOLUME_STEP,
                        lambda: self.prefs.volume, lambda v, final: self.change(final, volume=v),
                        enabled=lambda: self.prefs.sound), "volume", "sound")
        self.add(Label(self, ((x + w - 54) * u, (y + 2) * u, 54 * u, 26 * u), lambda: f"{self.prefs.volume}%",
                       "bold", 13.5 * u, lambda: t.primaryDeep if self.prefs.sound else t.muted, "rm"), "volume", "sound")

    def layout_sounds(self, W, M, H, top):
        """The sounds page: sound on, its volume, how long she waits on you
        first, a row per moment, and the way back."""
        t, u = self.theme, self.u
        fy = H - 14 - 32
        h = fy - 14 - top
        draw_card(self.bg, t, u, M, top, W - 2 * M, h)
        chip_w = draw_chip(self.bg, t, u, M + 16, top + 15, "サウンド")
        text(self.bg, ((M + 16) * u + chip_w + 8 * u, (top + 26) * u), "Sounds", "bold", 15.5 * u, t.ink, "lm")
        text(self.bg, ((M + 16) * u, (top + 48) * u), "Each moment plays her own sound, a file of yours, or nothing.",
             "regular", 12 * u, t.muted, "la")
        x0, cw = M + 16, W - 2 * M - 32

        def box(x, y, w, h):
            return (x * u, y * u, w * u, h * u)

        y = top + 76
        self.add(Toggle(self, box(x0, y + 2, 150, 26), lambda: self.prefs.sound,
                        lambda v: self.change(sound=v), "Sounds on"), "sound")
        text(self.bg, ((x0 + 290) * u, (y + 15) * u), "Volume", "semibold", 13 * u, t.ink, "lm")
        self.volume_widgets(x0 + 400, y, cw - 400)
        y += 40
        text(self.bg, ((x0 + 290) * u, (y + 15) * u), "Waiting after", "semibold", 13 * u, t.ink, "lm")
        self.add(Slider(self, box(x0 + 400, y, cw - 400 - 58, 30), *WAITING_SHOWN,
                        lambda: self.prefs.waitingAfter, lambda v, final: self.change(final, waitingAfter=v)),
                 "waitingAfter")
        self.add(Label(self, box(x0 + cw - 54, y + 2, 54, 26), lambda: f"{self.prefs.waitingAfter} s",
                       "bold", 13.5 * u, lambda: t.primaryDeep, "rm"), "waitingAfter")
        y += 48
        ImageDraw.Draw(self.bg).line((x0 * u, y * u, (x0 + cw) * u, y * u), fill=t.track + (255,), width=max(1, round(u)))
        y += 12
        for moment in cfg.MOMENTS:
            if moment == "intro":
                text(self.bg, (x0 * u, (y + 10) * u), "Coming and going", "bold", 12 * u, t.muted, "lm")
                y += 24
            self.sound_row(moment, x0, y, cw)
            y += SOUND_ROW
        where = f"Yours are copied into {self.sounds_dir()}. Up to {sound.MAX_S:.0f} s, .wav or .mp3."
        self.add(Note(self, box(x0, y + 8, cw, 36), lambda: where, 11.5 * u, lambda: t.muted, 18 * u))
        self.add(Label(self, box(M + 4, fy, 400, 32), lambda: self.problem or "Never two at once, and never while she is hidden.",
                       "regular", 12 * u, lambda: t.accentDeep if self.problem else t.muted), "problem")
        self.add(Button(self, box(W - M - 104, fy, 104, 32), "Back", lambda: self.show_page("settings")))
        self.add(Link(self, box(W - M - 104 - 16 - 150, fy, 150, 32), "Open sounds folder", self.open_sounds))

    def layout_notify(self, W, M, H, top):
        """The notifications page: her call when she waits on you, prompts
        from elsewhere, her away note; each a switch and what it does."""
        t, u = self.theme, self.u
        fy = H - 14 - 32
        h = fy - 14 - top
        draw_card(self.bg, t, u, M, top, W - 2 * M, h)
        chip_w = draw_chip(self.bg, t, u, M + 16, top + 15, "でんごん")
        text(self.bg, ((M + 16) * u + chip_w + 8 * u, (top + 26) * u), "Notifications", "bold", 15.5 * u, t.ink, "lm")
        text(self.bg, ((M + 16) * u, (top + 48) * u), f"More ways {t.name} tells you what is going on. Each is off until you turn it on.",
             "regular", 12 * u, t.muted, "la")
        x0, cw = M + 16, W - 2 * M - 32
        y = top + 84
        pictures = messenger_sprites(self.frames_dir(), round(420 * 1.5 * u))
        rows = (
            ("nudge", "Call me", lambda: (
                f"When she has waited on you {self.prefs.waitingAfter} s, her messenger calls and",
                "her terminal blinks in the taskbar. Click her to bring her terminal forward.")),
            ("remote", "Remote Control", lambda: (
                "A prompt you send from the Claude app on your phone, the web or a chat",
                "comes in with her messenger.")),
            ("away", "While you were away", lambda: (
                "Away 5 min or more, or the screen off: she keeps a note of what happened.",
                "When you are back, hover her to read it.")),
        )
        for (key, title, about), names in zip(rows, (("messenger",), ("messenger",), ("away_note",))):
            self.notify_row(key, title, about, x0, y, cw)
            # What it looks like, in her own style, at the row's right.
            right = (x0 + cw - 20) * u
            for name in reversed(names):
                img = pictures.get(name)
                if img:
                    put(self.bg, img, right - img.width, (y + 30) * u - img.height / 2)
                    right -= img.width + 4 * u
            y += NOTIFY_ROW
        self.add(Note(self, ((x0 * u), (y + 4) * u, cw * u, 40 * u), lambda: (
            "Windows Terminal shows several sessions in one window: it comes forward on the tab you left it at."),
            11.5 * u, lambda: t.muted, 18 * u))
        self.add(Label(self, ((M + 4) * u, fy * u, 400 * u, 32 * u), lambda: self.problem or "Quiet while she is hidden.",
                       "regular", 12 * u, lambda: t.accentDeep if self.problem else t.muted), "problem")
        self.add(Button(self, ((W - M - 104) * u, fy * u, 104 * u, 32 * u), "Back", lambda: self.show_page("settings")))

    def notify_row(self, key, title, about, x, y, w):
        """A row of the notifications page: its switch, name and what it does."""
        t, u = self.theme, self.u
        self.add(Toggle(self, (x * u, (y + 4) * u, 44 * u, 26 * u), lambda: getattr(self.prefs, key),
                        lambda v: self.change(**{key: v})), key)
        text(self.bg, ((x + 56) * u, (y + 17) * u), title, "semibold", 13.5 * u, t.ink, "lm")
        for i in range(2):
            self.add(Label(self, ((x + 56) * u, (y + 30 + 18 * i) * u, (w - 56) * u, 18 * u), lambda i=i: about()[i],
                           "regular", 12 * u, lambda: t.muted), key, "waitingAfter")

    def sound_row(self, moment, x, y, w):
        """A moment's row: its toggle, name, what it plays, Try, Choose…, Default."""
        t, u = self.theme, self.u
        title, about = MOMENT_NAMES[moment]

        def box(bx, by, bw, bh):
            return (bx * u, by * u, bw * u, bh * u)

        self.add(Toggle(self, box(x, y + 13, 44, 26), lambda: self.prefs.sounds[moment] is not False,
                        lambda v: self.toggle_sound(moment, v)), "sounds")
        text(self.bg, ((x + 56) * u, (y + 17) * u), title, "semibold", 13.5 * u, t.ink, "lm")
        text(self.bg, ((x + 56) * u, (y + 35) * u), about, "regular", 11.5 * u, t.muted, "lm")
        self.add(Label(self, box(x + 290, y + 13, 176, 26),
                       lambda: fit(self.sound_words(moment)[0], "semibold", 12.5 * u, 174 * u),
                       "semibold", 12.5 * u, lambda: self.sound_words(moment)[1]), "sounds")
        self.add(Button(self, box(x + w - 222, y + 12, 56, 28), "Try", lambda: self.try_sound(moment)))
        self.add(Button(self, box(x + w - 160, y + 12, 84, 28), "Choose…", lambda: self.choose_sound(moment)))
        self.add(Button(self, box(x + w - 70, y + 12, 70, 28), "Default", lambda: self.set_sound(moment, True),
                        enabled=lambda: isinstance(self.prefs.sounds[moment], str)), "sounds")

    def add(self, widget, *keys):
        """A widget whose look depends on the settings `keys` (and "problem",
        the footer's message): a change redraws only those that show it."""
        widget.keys = frozenset(keys)
        self.widgets.append(widget)

    def render(self, widget):
        """Draws `widget` over its piece of the background."""
        x, y, w, h = widget.box
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        widget.draw(img)
        if not widget.enabled:
            img = faded(img, DISABLED)
        piece = self.bg.crop((x, y, x + w, y + h))
        piece.alpha_composite(img)
        widget.drawn = piece.convert("RGB")
        widget.photo = ImageTk.PhotoImage(widget.drawn, master=self.root)
        if widget.item is None:
            widget.item = self.canvas.create_image(x, y, image=widget.photo, anchor="nw")
        else:
            self.canvas.itemconfig(widget.item, image=widget.photo)

    def image(self):
        """The window's inside as it is drawn now, RGB."""
        out = self.bg.convert("RGB")
        for widget in self.widgets:
            out.paste(widget.drawn, widget.box[:2])
        return out

    def refresh(self, keys=None):
        """Draws again the widgets that show any of `keys`; all of them
        without. A size slider's drag redraws four of fourteen."""
        for widget in self.widgets:
            if keys is None or widget.keys is None or widget.keys & set(keys):
                self.render(widget)
        self.animate()

    def animate(self):
        """Keeps drawing while a toggle slides."""
        now = time.monotonic()
        moving = [w for w in self.widgets if w.animating(now)]
        if moving and self.anim_job is None:
            def frame():
                self.anim_job = None
                for w in moving:
                    self.render(w)
                self.animate()

            self.anim_job = self.root.after(FRAME_MS, frame)

    # ---- the pointer

    def widget_at(self, x, y):
        for widget in self.widgets:
            if widget.interactive and widget.enabled and widget.contains(x, y):
                return widget
        return None

    def on_motion(self, e):
        over = self.widget_at(e.x, e.y) if e else None
        for widget in self.widgets:
            hover = widget is over or widget is self.grabbed
            spot = widget.spot_of(e.x, e.y) if hover and e else None
            if (hover, spot) != (widget.hover, widget.spot):
                widget.hover, widget.spot = hover, spot
                self.render(widget)
        self.canvas.config(cursor="hand2" if over else "")

    def on_press(self, e):
        self.grabbed = self.widget_at(e.x, e.y)
        if self.grabbed:
            self.grabbed.press(e.x, e.y)
            self.render(self.grabbed)

    def on_drag(self, e):
        if self.grabbed:
            self.grabbed.drag(e.x, e.y)

    def on_release(self, e):
        grabbed, self.grabbed = self.grabbed, None
        if grabbed:
            grabbed.release(e.x, e.y)
            self.flush()
            if grabbed in self.widgets:  # not after a pick drew the window anew
                self.render(grabbed)
        self.on_motion(e)

    def on_wheel(self, e):
        widget = self.widget_at(e.x, e.y)
        if widget:
            widget.wheel(1 if e.delta > 0 else -1)

    # ---- one window at a time

    def watch_raise(self):
        mtime = mtime_of(os.path.join(self.state_dir, RAISE_FILE))
        if mtime != self.raise_mtime:
            self.raise_mtime = mtime
            if (read_json(os.path.join(self.state_dir, RAISE_FILE)) or {}).get("handover"):
                self.close()  # another session's window takes this spot
                return
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(300, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        self.root.after(RAISE_POLL_MS, self.watch_raise)

    def flush(self):
        """Saves now what is waiting to be saved: as a click or a drag ends,
        and on closing."""
        if self.save_job:
            self.root.after_cancel(self.save_job)
            self.save()

    def close(self):
        self.flush()
        try:
            write_json(os.path.join(self.state_dir, POS_FILE), {"x": self.root.winfo_x(), "y": self.root.winfo_y()})
        except OSError:
            pass
        self.root.destroy()


# A moment's name and what it is, on the sounds page.
def messenger_sprites(frames_dir, height):
    """Her messenger and away note as the overlay draws them,
    in her look, for a mascot `height` px tall (the notifications page's
    pictures); {} when her look cannot be read."""
    try:
        with open(os.path.join(frames_dir, THEME_FILE), encoding="utf-8") as f:
            theme = json.load(f)
        fx.use(fx.look_of(theme))
        sprites = fx.build_sprites(height)
    except (OSError, ValueError):
        return {}
    return {name: sprites[name] for name in ("messenger", "away_note") if name in sprites}


MOMENT_NAMES = {
    "waiting": ("Waiting on you", "a question or a permission, once"),
    "done": ("Work done", "a round of work is over"),
    "beam": ("Her big finish", "a long round, or one agents helped"),
    "error": ("Something broke", "a turn died on an error"),
    "magic": ("Cursor magic", "as it flies to your pointer"),
    "intro": ("She appears", "every show"),
    "outro": ("She goes", "every hide, and as a session ends"),
}


def safe_name(path):
    """A file's name as `sounds` takes it (settings.SOUND_FILE): what a
    file name may not hold, out; a long one cut short."""
    stem, ext = os.path.splitext(os.path.basename(path))
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", stem).strip() or "sound"
    return stem[:100] + ext.lower()


def copy_in(path, folder):
    """Copies the sound file at `path` into `folder` (yours); its name
    there. The same file already there is taken as it is; another file of
    that name stays, and this one is numbered."""
    os.makedirs(folder, exist_ok=True)
    name = safe_name(path)
    stem, ext = os.path.splitext(name)
    n = 1
    while True:
        target = os.path.join(folder, name)
        if not os.path.exists(target):
            shutil.copyfile(path, target)
            return name
        if same_file(path, target):
            return name
        n += 1
        name = f"{stem}-{n}{ext}"


def same_file(a, b):
    try:
        if os.path.samefile(a, b):
            return True
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def say(line):
    """A line to the mod, on stdout (none under a bare pythonw)."""
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except (AttributeError, OSError, ValueError):
        pass


def cast_of(frames_root):
    """Every character with idle art: [(folder name, Theme, portrait)]."""
    cast = []
    try:
        names = sorted(os.listdir(frames_root))
    except OSError:
        return cast
    for name in names:
        folder = os.path.join(frames_root, name)
        art = idle_art(folder) if os.path.isdir(folder) else None
        if art is not None:
            cast.append((name, load_theme(folder), portrait(art)))
    return cast


def on_a_display(x, y):
    try:
        return bool(ctypes.windll.user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), 0))  # 0: none, if off every display
    except (AttributeError, OSError):
        return False


def idle_art(frames_dir):
    """Her first idle frame, or None."""
    for name in ("idle-1.png", "idle.png"):
        try:
            return Image.open(os.path.join(frames_dir, name)).convert("RGBA")
        except OSError:
            continue
    return None


def portrait(art):
    """Her head and shoulders, square, from her idle frame (None without one)."""
    if art is None:
        return None
    box = art.getchannel("A").point(lambda a: 255 if a > 100 else 0).getbbox() or (0, 0, art.width, art.height)
    side = round((box[3] - box[1]) * 0.44)
    cx = (box[0] + box[2]) / 2
    top = box[1] - round(side * 0.02)
    return art.crop((round(cx - side / 2), top, round(cx + side / 2), top + side))


def draw_header(bg, t, u, face):
    """The banner across the top: a teal-to-pink stage with a wavy edge,
    halftone dots like a manga screentone, her portrait, the title, notes
    and sparkles."""
    w = bg.width
    h = round(118 * u)
    band = gradient(w, h, t.primary, t.accent)
    # Screentone: dots growing toward the right.
    dots = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(dots)
    step = 9 * u
    for row in range(int(h / step) + 1):
        for column in range(int(w / step) + 1):
            x = column * step + (step / 2 if row % 2 else 0)
            r = max(0.0, (x / w - 0.45) * 2.6 * u)
            if r > 0.3:
                d.ellipse((x - r, row * step - r, x + r, row * step + r), fill=60)
    band.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (w, h), (255, 255, 255)).split(), dots)))
    # A wavy bottom edge.
    mask = Image.new("L", (w * SS, h * SS), 0)
    wave = [(x * SS, (h - 8 * u + 4 * u * math.sin(x / (34 * u))) * SS) for x in range(0, w + 1, 4)]
    ImageDraw.Draw(mask).polygon([(0, 0), (w * SS, 0)] + wave[::-1], fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    drop(bg, mask, 0, 0, round(4 * u), t.primaryDeep, 0.25, 3 * u)
    band.putalpha(mask)
    bg.alpha_composite(band)

    # Her portrait in a round frame.
    d = round(86 * u)
    x0, y0 = round(24 * u), round(14 * u)
    ring = round(4 * u)
    drop(bg, disc_mask(d + 2 * ring), x0 - ring, y0 - ring, round(5 * u), t.primaryDeep, 0.45, 3 * u)
    put(bg, filled(disc_mask(d + 2 * ring), (255, 255, 255)), x0 - ring, y0 - ring)
    inner = gradient(d, d, mix(t.paper, t.primary, 0.15), mix(t.paper, t.accent, 0.2))
    if face is not None:
        inner.alpha_composite(face.resize((d, d), Image.LANCZOS))
    inner.putalpha(disc_mask(d))
    put(bg, inner, x0, y0)

    # The title and its subtitle, white stickers.
    tx = x0 + d + ring + 18 * u
    text(bg, (tx, 50 * u), t.name, "black", 34 * u, (255, 255, 255), "ls", 3 * u, t.primaryDeep)
    text(bg, (tx + 2 * u, 76 * u), f"{t.subtitle} · Settings", "jp", 14 * u, (255, 255, 255), "ls", 2 * u, t.primaryDeep)

    # Notes and sparkles over the right of the stage (her style's own: bats, glints).
    for kind, x, y, size, color in (("notes", 0.66, 0.18, 30, (255, 255, 255)), ("star", 0.73, 0.52, 18, (255, 255, 255)),
                                    ("note", 0.79, 0.12, 26, t.accent), ("heart", 0.86, 0.44, 22, t.accent),
                                    ("star", 0.91, 0.14, 14, (255, 255, 255)), ("note", 0.955, 0.5, 22, (255, 255, 255)),
                                    ("star", 0.6, 0.58, 11, (255, 255, 255))):
        # White ones glow in her deep color, to read on the light middle of the stage.
        glow = t.accentDeep if color == (255, 255, 255) else (255, 255, 255)
        img = fx.ornament(kind, max(4, round(size * u)), color, glow=glow, style=t.style)
        put(bg, img, x * w - img.width / 2, y * h - img.height / 2 + 2 * u)


def draw_card(bg, t, u, x, y, w, h):
    """A white card with round corners on a soft, tinted shadow."""
    mask = pill_mask(round(w * u), round(h * u), 16 * u)
    drop(bg, mask, x * u, y * u, round(8 * u), t.primaryDeep, 0.18, 3 * u)
    put(bg, filled(mask, t.card), x * u, y * u)


def draw_chip(bg, t, u, x, y, words):
    """A card's sticker chip (its name in Japanese); its width."""
    px = 12 * u
    w = round(text_width(words, "jp", px) + 18 * u)
    h = round(22 * u)
    chip = filled(pill_mask(w, h), gradient(w, h, t.primary, t.accent))
    text(chip, (w / 2, h / 2 + 0.5 * u), words, "jp", px, (255, 255, 255), "mm")
    drop(bg, pill_mask(w, h), x * u, y * u, round(3 * u), t.primaryDeep, 0.3, 2 * u)
    put(bg, chip, x * u, y * u)
    return w


# ---------------------------------------------------------------- start


def claim(state_dir, session=None):
    """True when this is the only window. One open for the same session is
    asked to come forward (False); one open for another session is asked
    to close, and this one waits for it (up to HANDOVER_S), then opens
    where it stood: its picks would go to the wrong session."""
    lock = os.path.join(state_dir, LOCK_FILE)
    holder = read_json(lock) or {}
    os.makedirs(state_dir, exist_ok=True)
    if holder.get("pid") != os.getpid() and is_alive(holder.get("pid")):
        handover = holder.get("session") != session
        write_json(os.path.join(state_dir, RAISE_FILE),
                   {"at": time.time(), **({"handover": os.getpid()} if handover else {})})
        if not handover:
            return False
        end = time.monotonic() + HANDOVER_S
        while is_alive(holder.get("pid")) and time.monotonic() < end:
            time.sleep(0.05)
    write_json(lock, {"pid": os.getpid(), **({"session": session} if session else {})})
    return True


def main():
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__)
    state_dir, frames_dir = sys.argv[1], sys.argv[2]
    session, project = (sys.argv[3], sys.argv[4]) if len(sys.argv) == 5 else (None, "")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp on scaled displays
    except Exception:
        pass
    if not claim(state_dir, session):
        return
    try:
        App(state_dir, frames_dir, session=session, project=project).root.mainloop()
    finally:
        lock = os.path.join(state_dir, LOCK_FILE)
        if (read_json(lock) or {}).get("pid") == os.getpid():
            remove(lock)
            remove(os.path.join(state_dir, RAISE_FILE))


if __name__ == "__main__":
    main()
