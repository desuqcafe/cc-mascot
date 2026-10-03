"""Mood symbols, drawn and animated in code over the mascot's frames: the
thought bubble, notes, the "?", zZ, a sweat drop, sparkles, a storm cloud;
and her glitch. Anime-sticker style in the character's colors (her look,
section below): white borders, soft glows. Descriptions name Miku's (teal,
pink, mint); another character's look puts her own in their roles.

Sprites are drawn once per show (`build_sprites`), a few tens of KB, and
dropped with the frames on hide. Where they go is worked out from the mood
and the time alone (`placements`): no particle keeps state, so nothing
drifts, and a frame can be computed for any moment.

Coordinates are in pixels of a mascot frame HEIGHT tall; the window has
PAD_TOP and PAD_RIGHT of room above and right of her for symbols that rise
past her edge, and PAD_LEFT for her aura. Sprites and pads are drawn for her
at BASE_HEIGHT and scaled to her size (`build_sprites`, `scale_to`).

Calm mode (the `calm` setting) keeps what tells something (the symbols, the
aura's color, the hologram's scanlines) and drops what flashes or jitters:
her glitch, particles, flicker, the beam's flash and speed lines; she comes
and goes in a plain fade (`projection(..., calm=True)`).

Besides the mood, a long session and a usage limit running out show on her
(`dress`, the status section); she comes and goes as a hologram
(`projection`), and swings when carried (`Sway`, the handling section).
"""

import importlib
import math
import re
import weakref
from collections import namedtuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------- look
#
# A character's look (`Look`): the colors her effects are drawn in, her
# aura's colors for each tier, and her beam's call. Miku's is the default
# (`MIKU`, below); another character's comes from the "effects" of her
# theme.json (`look_of`), and `use` puts it in place, one mascot per
# process as with her size (`scale_to`).
#
# Each color is a role. A tint has an ink, which fills a symbol (a note, a
# dot, a pip, a "z"), and a light, which glows: the halos, the projector's
# ring and beam, the hologram, her glitch's ghosts. Miku's ink and light are
# the same teal (and the same pink); a dark ink, a black note, wants a light
# that still shows on a dark desktop. The sticker border and shine stay
# white for everyone: that is the style.
#
# Sprites are named for their part, by role ("note_main", "spark_accent"),
# not by color, so a character's own shapes (bats where Miku has notes)
# are drawn under the same names and every placement keeps working.
#
# A character's own shapes and motion are her style ("style" in her theme's
# effects; STYLES names its module). Left out, she draws Miku's concert in
# her colors. A style module draws its sprites (`build_sprites`), places
# its symbols (`PLACEMENTS`) and has its own glitch, status (`dress`),
# projection, beam and carry ring; the entry points below hand over to it
# (`STYLE`), and Miku's path stays as it was.

# Miku's colors, sampled from the art: hair, its shade, the hair ties.
MAIN = (57, 197, 187)  # a stage teal: lit dots, notes, the equalizer
MAIN_LIGHT = MAIN  # its glow: halos, the projector, the hologram
MAIN_SHADE = (96, 150, 168)  # the bubbles' rim
ACCENT = (246, 130, 154)  # pink: hearts, "!" and "?", the beam's banner
ACCENT_LIGHT = ACCENT
ACCENT_SHADE = (168, 92, 110)
ACCENT_SOFT = (255, 160, 185)  # the banner's top
PALE = (214, 242, 238)  # mint: the bubbles' fill, light along her edge
HOT = (240, 84, 168)  # an overloaded aura: her pink, pushed hot
GOLD = (250, 210, 100)  # a rare stage-light accent
STORM = (222, 219, 236)  # error's cloud: grumpy, still pastel
STORM_DEEP = (182, 177, 206)
STORM_SHADE = (118, 111, 150)
SKY = (196, 238, 250)  # the sweat drop, a cool cousin of her teal
SKY_DEEP = (122, 200, 232)
SKY_SHADE = (70, 150, 196)
DIM = (128, 172, 180)  # an unlit dot: teal gone gray
WHITE = (255, 255, 255)  # not a role: every sticker's border and shine

COLORS = ("MAIN", "MAIN_LIGHT", "MAIN_SHADE", "ACCENT", "ACCENT_LIGHT", "ACCENT_SHADE", "ACCENT_SOFT", "PALE", "HOT",
          "GOLD", "STORM", "STORM_DEEP", "STORM_SHADE", "SKY", "SKY_DEEP", "SKY_SHADE", "DIM")
# Her aura at each tier: the glow around her, the light along her edge.
AURA_ROLES = (("MAIN_LIGHT", "PALE"), ("ACCENT_LIGHT", "MAIN_LIGHT"), ("HOT", "ACCENT_LIGHT"))
AURA = tuple((globals()[glow], globals()[edge]) for glow, edge in AURA_ROLES)
# The beam's call on its banner, and its words where Windows has no face for it.
CALL = "ミクミクビーム!"
CALL_PLAIN = "MIKU MIKU BEAM!"

Look = namedtuple("Look", "colors aura call call_plain style")
Look.__new__.__defaults__ = (None,)
MIKU = Look({name: globals()[name] for name in COLORS}, AURA, CALL, CALL_PLAIN)

# A style's name in a theme, and its module beside this one.
STYLES = {"gothic": "gothic"}
STYLE = None  # the style module in use; None is Miku's


def _role(key):
    """A theme's camelCase role ("accentShade") as its constant's name."""
    return re.sub(r"([A-Z])", r"_\1", key).upper() if isinstance(key, str) else None


def _hex(value):
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return None


def look_of(theme):
    """The Look a character's theme.json (parsed; None for none) asks for in
    its "effects": "colors" by role ("main", "mainLight", "accentShade"...,
    as "#rrggbb"), "aura" (three [glow, edge] pairs, each a color or a role),
    "call", "callPlain" and "style" (a name in STYLES). What it leaves out
    or gets wrong is Miku's, but a light left out is its own ink."""
    effects = theme.get("effects") if isinstance(theme, dict) else None
    effects = effects if isinstance(effects, dict) else {}
    given = effects.get("colors") if isinstance(effects.get("colors"), dict) else {}
    given = {_role(k): _hex(v) for k, v in given.items() if _role(k) in COLORS and _hex(v)}
    colors = {}
    for name in COLORS:
        ink = name[:-len("_LIGHT")] if name.endswith("_LIGHT") else None
        colors[name] = given.get(name) or (ink in given and colors[ink]) or MIKU.colors[name]

    def tier(entry, roles):
        if isinstance(entry, list) and len(entry) == 2:
            pair = tuple(_hex(c) or colors.get(_role(c)) for c in entry)
            if all(pair):
                return pair
        return tuple(colors[role] for role in roles)

    aura = effects.get("aura") if isinstance(effects.get("aura"), list) else []
    aura = tuple(tier(aura[i] if i < len(aura) else None, roles) for i, roles in enumerate(AURA_ROLES))

    def text(key, default):
        value = effects.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else default

    style = effects.get("style") if effects.get("style") in STYLES else None
    return Look(colors, aura, text("call", MIKU.call), text("callPlain", MIKU.call_plain), style)


def use(look):
    """Draws in `look` from now on: every effect, and the sprites built after."""
    style = importlib.import_module(STYLES[look.style]) if look.style else None
    globals().update(look.colors, AURA=look.aura, CALL=look.call, CALL_PLAIN=look.call_plain, STYLE=style)

# What the pads and sprites below are drawn for; scale_to() fits the pads to
# her size, build_sprites() the sprites.
BASE_HEIGHT = 420
PAD_TOP = 40
PAD_RIGHT = 40
PAD_LEFT = 16  # room for her aura's glow left of her
# Between her feet and what is drawn under them (the name tag).
UNDER_GAP = 2
# Drawn this many times larger, then scaled down: smooth edges.
SUPER = 4

# Where a mood's symbol stands, as a share of the frame: upper right of her
# head, clear of the twin tail (past the frame's right edge, into the pad).
SYMBOL_AT = (0.95, 0.11)
# The thought bubble's puffs, from beside her head toward the bubble.
PUFFS_AT = ((0.84, 0.215), (0.875, 0.175))

# Worried's sweat drop, on her hair beside the temple; the flustered lines
# fan out from above her other temple.
DROP_AT = (0.75, 0.16)
LINES_AT = (0.25, 0.13)

# Happy: the burst comes from her head; stars keep twinkling at these spots
# around her raised arms.
HEAD_AT = (0.52, 0.2)
SHINE_AT = ((0.12, 0.13), (0.07, 0.3), (0.9, 0.06), (0.95, 0.24), (0.5, 0.0))

# Error's cloud, above her head where the art had it; its broken notes fall
# from its right side.
CLOUD_AT = (0.68, 0.06)

# Sleepy's z's rise from beside her head, up and right.
DOZE_AT = (0.78, 0.17)

# Working's equalizer: where its bars stand on the frame (their bottom middle).
EQ_AT = (0.93, 0.215)

# A sprite drawn centered at (x, y), scaled, faded and turned (degrees,
# counterclockwise).
Draw = namedtuple("Draw", "sprite x y scale alpha angle")
Draw.__new__.__defaults__ = (1.0, 1.0, 0.0)

# Moods whose symbol moves all the time: the window redraws at ANIMATE_FPS.
ANIMATE_FPS = 30


def _canvas(w, h):
    return Image.new("RGBA", (w * SUPER, h * SUPER), (0, 0, 0, 0))


def _down(img):
    return img.resize((img.width // SUPER, img.height // SUPER), Image.LANCZOS)


def _edged(mask, n):
    """`mask` with `n` px more on every side, its edge pixels repeated there
    (as PIL's rank filters see past an edge)."""
    w, h = mask.size
    out = Image.new(mask.mode, (w + 2 * n, h + 2 * n))
    out.paste(mask, (n, n))
    out.paste(mask.crop((0, 0, 1, h)).resize((n, h)), (0, n))
    out.paste(mask.crop((w - 1, 0, w, h)).resize((n, h)), (n + w, n))
    out.paste(out.crop((0, n, w + 2 * n, n + 1)).resize((w + 2 * n, n)), (0, 0))
    out.paste(out.crop((0, n + h - 1, w + 2 * n, n + h)).resize((w + 2 * n, n)), (0, n + h))
    return out


def _square(mask, size, pick):
    """`pick` (darker or lighter) over a `size` px square (odd) around each
    pixel: along the rows, then down the columns."""
    n = size // 2
    if n < 1:
        return mask
    w, h = mask.size
    edged = _edged(mask, n)
    rows = edged.crop((0, 0, w, h + 2 * n))
    for dx in range(1, size):
        rows = pick(rows, edged.crop((dx, 0, dx + w, h + 2 * n)))
    out = rows.crop((0, 0, w, h))
    for dy in range(1, size):
        out = pick(out, rows.crop((0, dy, w, dy + h)))
    return out


def _shrink(mask, size):
    """`mask` eroded by a `size` px square: MinFilter(size)'s pixels exactly.
    PIL's rank filter sorts every square, size squared per pixel: the beam
    heart's 43 px one took 2.4 s of a 640 px mascot's sprites."""
    return _square(mask, size, ImageChops.darker)


def _grow(mask, size):
    """`mask` dilated by a `size` px square: MaxFilter(size)'s pixels, as `_shrink`."""
    return _square(mask, size, ImageChops.lighter)


def _glow(img, color, radius, strength):
    """`img` over a soft halo of `color` in its own shape."""
    pad = radius * 3
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    halo = Image.new("RGBA", out.size, color + (0,))
    shape = Image.new("L", out.size, 0)
    shape.paste(img.getchannel("A"), (pad, pad))
    halo.putalpha(shape.filter(ImageFilter.GaussianBlur(radius)).point(lambda a: min(255, round(a * strength))))
    out.alpha_composite(halo)
    out.alpha_composite(img, (pad, pad))
    return out


def _gradient(size, top, bottom):
    """An RGBA image fading from `top` to `bottom` down its height."""
    v = Image.linear_gradient("L").resize(size)
    return Image.merge("RGB", [v.point(lambda x, a=a, b=b: round(a + (b - a) * x / 255)) for a, b in zip(top, bottom)]).convert("RGBA")


def _filled(shape, top, bottom, rim, line):
    """A shape (an "L" mask drawn SUPER times larger) filled with a gradient
    from `top` to `bottom` inside a `rim` `line` px wide, still SUPER large."""
    out = Image.new("RGBA", shape.size, rim + (255,))
    out.putalpha(shape)
    fill = _gradient(shape.size, top, bottom)
    fill.putalpha(_shrink(shape, 2 * round(line * SUPER) + 1))
    out.alpha_composite(fill)
    return out


def _mask(w, h):
    """A blank shape mask for a sprite w by h (plus a pixel of room around),
    drawn SUPER times larger, and a pen for it."""
    shape = Image.new("L", (round((w + 2) * SUPER), round((h + 2) * SUPER)), 0)
    return shape, ImageDraw.Draw(shape)


def _ellipse(w, h, fill, outline=None, line=0):
    img = _canvas(w + 2, h + 2)
    s = SUPER
    ImageDraw.Draw(img).ellipse((s, s, (w + 1) * s, (h + 1) * s), fill=fill, outline=outline, width=line * s)
    return _down(img)


def _star(size, color, waist=0.11):
    """A four-point twinkle; a bigger `waist` makes it plumper."""
    img = _canvas(size, size)
    c, r, k = size * SUPER / 2, size * SUPER / 2, size * SUPER * waist
    points = [(c, c - r), (c + k, c - k), (c + r, c), (c + k, c + k), (c, c + r), (c - k, c + k), (c - r, c), (c - k, c - k)]
    ImageDraw.Draw(img).polygon(points, fill=color)
    return _down(img)


def _note(h, color, beamed):
    """♪, or ♫ when `beamed`: tilted heads, stems, a flag or a beam, with a
    small shine on each head."""
    S = SUPER
    w = h * (1.05 if beamed else 0.75)
    img = _canvas(round(w), h)
    d = ImageDraw.Draw(img)
    head_w, head_h, stem = 0.44 * h * S, 0.32 * h * S, max(S, round(0.1 * h * S))
    heads = [(head_w / 2, h * S - head_h / 2)]
    if beamed:
        heads.append((w * S - head_w / 2 - S, h * S - head_h / 2 - 0.12 * h * S))
    tops = []
    for cx, cy in heads:
        head = Image.new("RGBA", (round(head_w * 1.2), round(head_w * 1.2)), (0, 0, 0, 0))
        hc = head.width / 2
        ImageDraw.Draw(head).ellipse((hc - head_w / 2, hc - head_h / 2, hc + head_w / 2, hc + head_h / 2), fill=color)
        head = head.rotate(22, Image.BICUBIC)
        img.alpha_composite(head, (round(cx - hc), round(cy - hc)))
        sx = cx + head_w * 0.42
        top = cy - 0.78 * h * S
        d.rectangle((sx - stem, top, sx, cy - head_h * 0.1), fill=color)
        shine = head_h * 0.16
        d.ellipse((cx - head_w * 0.22 - shine, cy - head_h * 0.12 - shine, cx - head_w * 0.22 + shine, cy - head_h * 0.12 + shine), fill=WHITE)
        tops.append((sx, top))
    if beamed:
        (x1, y1), (x2, y2) = tops
        beam = 0.17 * h * S
        d.polygon([(x1 - stem, y1), (x2, y2), (x2, y2 + beam), (x1 - stem, y1 + beam)], fill=color)
    else:
        x, y = tops[0]
        d.polygon([(x - stem / 2, y), (x + 0.3 * h * S, y + 0.28 * h * S), (x + 0.24 * h * S, y + 0.5 * h * S),
                   (x + 0.12 * h * S, y + 0.34 * h * S), (x - stem / 2, y + 0.24 * h * S)], fill=color)
    return _down(img)


def _sticker(img, width, color=WHITE):
    """`img` with a border of `color` around its shape, like an anime sticker
    or emote: it reads on any desktop."""
    size = 2 * width + 1
    out = Image.new("RGBA", (img.width + 2 * width, img.height + 2 * width), (0, 0, 0, 0))
    shape = Image.new("L", out.size, 0)
    shape.paste(img.getchannel("A"), (width, width))
    border = Image.new("RGBA", out.size, color + (255,))
    border.putalpha(_grow(shape, size).filter(ImageFilter.GaussianBlur(0.6)))
    out.alpha_composite(border)
    out.alpha_composite(img, (width, width))
    return out


def _speech(w, h, line):
    """A plump speech bubble, white fading to mint, with a teal rim, a shine
    and its tail at the lower left, toward her."""
    S = SUPER
    shape, d = _mask(w, h)
    d.rounded_rectangle((S, S, (w + 1) * S, (h * 0.8 + 1) * S), radius=h * 0.36 * S, fill=255)
    d.polygon([(w * 0.2 * S, h * 0.7 * S), (w * 0.06 * S, (h + 0.6) * S), (w * 0.46 * S, h * 0.74 * S)], fill=255)
    out = _filled(shape, WHITE, PALE, MAIN_SHADE, line)
    ImageDraw.Draw(out).ellipse((w * 0.2 * S, h * 0.19 * S, w * 0.32 * S, h * 0.27 * S), fill=WHITE + (255,))
    return _down(out)


def _thought(w, h, line):
    """A plump oval thought bubble in the speech bubble's colors, with a shine."""
    S = SUPER
    shape, d = _mask(w, h)
    d.ellipse((S, S, (w + 1) * S, (h + 1) * S), fill=255)
    out = _filled(shape, WHITE, PALE, MAIN_SHADE, line)
    if w > 20:  # a puff is too small for one
        ImageDraw.Draw(out).ellipse((w * 0.22 * S, h * 0.2 * S, w * 0.34 * S, h * 0.32 * S), fill=WHITE + (255,))
    return _down(out)


def _glyph(text, size, color, outline):
    """`text` in a heavy face with a darker rim, trimmed to its ink."""
    for name in ("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf"):
        try:
            font = ImageFont.truetype(name, size * SUPER)
            break
        except OSError:
            font = None
    font = font or ImageFont.load_default()
    img = _canvas(size * 2, size * 2)
    ImageDraw.Draw(img).text((size * SUPER // 2, SUPER * 2), text, font=font, fill=color,
                             stroke_width=SUPER, stroke_fill=outline)
    return _down(img.crop(img.getbbox()))


def _drop(w, h, line):
    """An anime sweat drop: a round bottom drawn up to a point, pale sky
    fading deeper, a darker rim and a white shine streak."""
    S = SUPER
    shape, d = _mask(w, h)
    r = w / 2
    cx, cy = (r + 1) * S, (h - r + 1) * S
    d.ellipse((cx - r * S, cy - r * S, cx + r * S, cy + r * S), fill=255)
    d.polygon([(cx, S), (cx + r * S * 0.97, cy - r * S * 0.25), (cx - r * S * 0.97, cy - r * S * 0.25)], fill=255)
    out = _filled(shape, SKY, SKY_DEEP, SKY_SHADE, line)
    pen = ImageDraw.Draw(out)
    pen.line([(cx - r * S * 0.42, cy - r * S * 0.05), (cx - r * S * 0.2, cy - r * S * 0.75)], fill=WHITE + (255,),
             width=max(S, round(r * S * 0.28)))
    pen.ellipse((cx - r * S * 0.55, cy + r * S * 0.1, cx - r * S * 0.3, cy + r * S * 0.35), fill=WHITE + (255,))
    return _down(out)


def _dash(length, thick, color):
    """A short rounded stroke, pointing up."""
    img = _canvas(thick, length)
    ImageDraw.Draw(img).rounded_rectangle((0, 0, thick * SUPER - 1, length * SUPER - 1), radius=thick * SUPER / 2, fill=color)
    return _down(img)


def _zee(size, color, rim, line):
    """A hand-drawn Z: one rounded stroke with a darker rim, the top bar
    tipped up a little."""
    S = SUPER
    img = _canvas(size, size)
    d = ImageDraw.Draw(img)
    m = line * 1.6 * S
    a = size * S - m
    points = [(m, m + 0.08 * a), (a, m), (m + 0.04 * a, a), (a, a - 0.04 * a)]
    for color_, width in ((rim, line * 2.2 * S), (color, line * 1.2 * S)):
        d.line(points, fill=color_, width=round(width), joint="curve")
        r = width / 2
        for x, y in (points[0], points[-1]):
            d.ellipse((x - r, y - r, x + r, y + r), fill=color_)
    return _down(img)


def _heart_shape(size):
    """A plump heart's mask, `size` px square (plus _mask's room), SUPER large."""
    shape, d = _mask(size, size)
    n = size * SUPER
    r = n * 0.27
    d.ellipse((n * 0.04, n * 0.08, n * 0.04 + 2 * r, n * 0.08 + 2 * r), fill=255)
    d.ellipse((n * 0.96 - 2 * r, n * 0.08, n * 0.96, n * 0.08 + 2 * r), fill=255)
    d.polygon([(n * 0.06, n * 0.42), (n * 0.94, n * 0.42), (n * 0.5, n * 0.94)], fill=255)
    return shape


def _heart(size, color, rim, line):
    """A plump heart with a darker rim and a shine."""
    n = size * SUPER
    out = _filled(_heart_shape(size), color, color, rim, line)
    ImageDraw.Draw(out).ellipse((n * 0.2, n * 0.2, n * 0.32, n * 0.32), fill=WHITE + (255,))
    return _down(out)


def _gem_star(size, color):
    """A four-point star in `color` with a white heart: a stage sparkle."""
    out = _star(size, color, 0.17)
    core = _star(max(1, size // 2), WHITE, 0.17)
    out.alpha_composite(core, ((out.width - core.width) // 2, (out.height - core.height) // 2))
    return out


def _cloud(w, h, line):
    """A puffy little storm cloud, pale violet-gray deepening downward, with
    a darker rim and a shine."""
    S = SUPER
    shape, d = _mask(w, h)
    for cx, cy, r in ((0.22, 0.62, 0.2), (0.42, 0.4, 0.28), (0.66, 0.42, 0.24), (0.8, 0.64, 0.18), (0.5, 0.7, 0.24)):
        d.ellipse(((cx - r * h / w) * w * S + S, (cy - r) * h * S + S, (cx + r * h / w) * w * S + S, (cy + r) * h * S + S), fill=255)
    out = _filled(shape, STORM, STORM_DEEP, STORM_SHADE, line)
    ImageDraw.Draw(out).ellipse((w * 0.3 * S, h * 0.24 * S, w * 0.42 * S, h * 0.36 * S), fill=WHITE + (200,))
    return _down(out)


def _scribble(w, h, color, line):
    """A loopy coil drawn left to right, the way a manga draws a bad mood."""
    S = SUPER
    img = _canvas(w, h)
    n = 60
    points = [((0.12 + 0.76 * i / n + 0.1 * math.cos(i * 0.42)) * w * S, (0.5 + 0.34 * math.sin(i * 0.42)) * h * S)
              for i in range(n + 1)]
    ImageDraw.Draw(img).line(points, fill=color, width=round(line * S), joint="curve")
    return _down(img)


def _broken_note(h, color):
    """A note with a white crack through its head."""
    img = _note(h, color, False)
    w_, h_ = img.size
    ImageDraw.Draw(img).line([(w_ * 0.05, h_ * 0.72), (w_ * 0.28, h_ * 0.8), (w_ * 0.2, h_ * 0.9), (w_ * 0.45, h_)],
                             fill=WHITE + (255,), width=max(1, round(h / 10)))
    return img


def _bang(w, h, line):
    """A plump "!": a rounded bar tapering down, a round dot, pink with a
    darker rim and a shine."""
    S = SUPER
    shape, d = _mask(w, h)
    bar = h * 0.66
    d.polygon([(S, S + w * 0.2 * S), ((w + 1) * S, S + w * 0.2 * S), ((w * 0.68 + 1) * S, (bar + 1) * S), ((w * 0.32 + 1) * S, (bar + 1) * S)], fill=255)
    d.ellipse((S, S, (w + 1) * S, (w * 0.5 + 1) * S + w * 0.2 * S), fill=255)
    r = w * 0.36
    d.ellipse(((w / 2 - r + 1) * S, (h - 2 * r + 1) * S, (w / 2 + r + 1) * S, (h + 1) * S), fill=255)
    out = _filled(shape, ACCENT, ACCENT, ACCENT_SHADE, line)
    ImageDraw.Draw(out).ellipse((w * 0.3 * S, w * 0.3 * S, w * 0.5 * S, w * 0.62 * S), fill=WHITE + (255,))
    return _down(out)


def _pip(w, h, color):
    img = _canvas(w, h)
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * SUPER - 1, h * SUPER - 1), radius=h * SUPER * 0.45, fill=color)
    return _down(img)


def _love_heart(size, band):
    """The beam's heart: a hollow heart `band` px thick, teal fading to mint
    inside a pink rim, a shine on its shoulder."""
    shape = _heart_shape(size)
    hollow = ImageChops.subtract(shape, _shrink(shape, 2 * round(band * SUPER / 2) + 1))
    out = _filled(hollow, PALE, MAIN_LIGHT, ACCENT, max(1, band / 4))
    n = size * SUPER
    ImageDraw.Draw(out).ellipse((n * 0.14, n * 0.17, n * 0.2, n * 0.23), fill=WHITE + (255,))
    return _down(out)


# Image.radial_gradient's value at its circle's edge (255 is its corners).
RADIAL_EDGE = 181


def _flash(size, color):
    """A soft round glow, brightest in the middle, nothing at its edge."""
    v = Image.radial_gradient("L").resize((size, size), Image.BILINEAR)
    out = Image.new("RGBA", (size, size), color + (0,))
    out.putalpha(v.point(lambda a: round(255 * max(0.0, 1 - a / RADIAL_EDGE) ** 2)))
    return out


def hangul(text):
    """Whether `text` has Korean letters, which the Japanese faces lack."""
    return any("\uac00" <= c <= "\ud7a3" or "\u1100" <= c <= "\u11ff" or "\u3130" <= c <= "\u318f" for c in text)


def _banner(text, size, line, tint=None, plain=None):
    """`text` on a sticker pill in her accent (or `tint`: soft top, fill,
    shade), white letters with a darker rim: the beam's call. A Japanese
    face when Windows has one (a Korean one for Hangul), else `plain`
    (CALL_PLAIN)."""
    soft, fill, shade = tint or (ACCENT_SOFT, ACCENT, ACCENT_SHADE)
    font = None
    for name in ("malgunbd.ttf", "malgun.ttf") if hangul(text) else ("YuGothB.ttc", "meiryob.ttc", "msgothic.ttc"):
        try:
            font = ImageFont.truetype(name, size * SUPER)
            break
        except OSError:
            continue
    if font is None:
        text, font = plain or CALL_PLAIN, ImageFont.load_default()
    S = SUPER
    left, top, right, bottom = font.getbbox(text, stroke_width=S * 2)
    tw, th = right - left, bottom - top
    w, h = tw / S + size * 1.1, th / S + size * 0.6
    shape, d = _mask(w, h)
    d.rounded_rectangle((S, S, (w + 1) * S, (h + 1) * S), radius=h * S / 2, fill=255)
    out = _filled(shape, soft, fill, shade, line)
    ImageDraw.Draw(out).text(((w + 2) * S / 2 - tw / 2 - left, (h + 2) * S / 2 - th / 2 - top), text, font=font,
                             fill=WHITE, stroke_width=S * 2, stroke_fill=shade)
    return _down(out)


def _pixel(size, color):
    """A square bit of her with a white core: a pixel flaking off."""
    img = Image.new("RGBA", (size + 2, size + 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((1, 1, size, size), fill=color + (255,))
    if size >= 3:
        d.rectangle((1 + size // 3, 1 + size // 3, size - size // 3, size - size // 3), fill=WHITE + (255,))
    return img


def build_sprites(height):
    """{name: RGBA image} for every symbol, at a mascot `height` px tall."""
    if STYLE:
        return STYLE.build_sprites(height)
    k = height / BASE_HEIGHT

    def px(v):
        return max(1, round(v * k))

    line = px(2)
    sprites = {
        "bubble": _glow(_sticker(_thought(px(50), px(36), line), px(2)), MAIN_LIGHT, px(5), 0.5),
        "puff_s": _glow(_sticker(_thought(px(8), px(7), px(1)), px(1.5)), MAIN_LIGHT, px(3), 0.45),
        "puff_m": _glow(_sticker(_thought(px(13), px(11), px(1)), px(1.5)), MAIN_LIGHT, px(3), 0.45),
        "dot_dim": _ellipse(px(7), px(7), DIM),
        "twinkle": _glow(_star(px(14), WHITE), ACCENT_LIGHT, px(3), 0.9),
        "speech": _glow(_sticker(_speech(px(42), px(40), line), px(2)), MAIN_LIGHT, px(5), 0.5),
        "question": _sticker(_glyph("?", px(22), ACCENT, ACCENT_SHADE), px(1)),
        "exclaim": _glow(_sticker(_bang(px(12), px(30), line), px(2)), ACCENT_LIGHT, px(3), 0.5),
        "drop": _glow(_sticker(_drop(px(15), px(22), line), px(2)), SKY_DEEP, px(4), 0.45),
        "dash": _sticker(_dash(px(9), px(3), ACCENT), px(1)),
        "heart": _glow(_sticker(_heart(px(17), ACCENT, ACCENT_SHADE, px(1.5)), px(2)), ACCENT_LIGHT, px(3), 0.5),
        "cloud": _glow(_sticker(_cloud(px(58), px(36), line), px(2)), STORM_SHADE, px(4), 0.35),
        "scribble": _scribble(px(34), px(16), ACCENT, px(2.2)),
        "broken_note": _glow(_sticker(_broken_note(px(22), STORM_SHADE), px(2)), STORM_SHADE, px(3), 0.3),
        "z_main": _glow(_sticker(_zee(px(18), MAIN, MAIN_SHADE, px(2.5)), px(2)), MAIN_LIGHT, px(3), 0.5),
        "z_accent": _glow(_sticker(_zee(px(18), ACCENT, ACCENT_SHADE, px(2.5)), px(2)), ACCENT_LIGHT, px(3), 0.5),
        "love_heart": _glow(_sticker(_love_heart(px(110), px(14)), px(3)), ACCENT_LIGHT, px(6), 0.6),
        "core_heart": _glow(_sticker(_heart(px(30), ACCENT, ACCENT_SHADE, px(2)), px(2)), ACCENT_LIGHT, px(7), 0.9),
        "flash_accent": _flash(px(64), ACCENT_LIGHT),  # smooth: drawn scaled up
        "flash_main": _flash(px(64), MAIN_LIGHT),
        "banner": _glow(_sticker(_banner(CALL, px(21), px(2)), px(2)), ACCENT_LIGHT, px(4), 0.6),
    }
    for name, ink, light in (("main", MAIN, MAIN_LIGHT), ("accent", ACCENT, ACCENT_LIGHT)):
        sprites[f"dot_{name}"] = _glow(_ellipse(px(7), px(7), ink), light, px(3), 0.9)
        sprites[f"note_{name}"] = _glow(_note(px(22), ink, False), light, px(3), 0.6)
        sprites[f"notes_{name}"] = _glow(_note(px(22), ink, True), light, px(3), 0.6)
        sprites[f"pip_{name}"] = _glow(_pip(px(6), px(4), ink), light, px(2), 0.7)
        sprites[f"spark_{name}"] = _glow(_star(px(7), WHITE), light, px(2), 0.9)
    for name, ink, light in (("main", MAIN, MAIN_LIGHT), ("accent", ACCENT, ACCENT_LIGHT), ("gold", GOLD, GOLD)):
        sprites[f"star_{name}"] = _glow(_gem_star(px(20), ink), light, px(4), 0.8)
    for name, ink, light in (("main", MAIN, MAIN_LIGHT), ("accent", ACCENT, ACCENT_LIGHT), ("hot", HOT, HOT)):
        sprites[f"pixel_{name}"] = _glow(_pixel(px(3.5), ink), light, px(2), 0.9)
    return sprites


def ornament(kind, size, color, glow=None, style=None):
    """A sticker ornament `size` px for another window (the settings
    window's decoration) in `color`, with a soft `glow` of that color:
    "note" (a quaver), "notes" (two beamed), "star" (a twinkle), "heart";
    `style` (a name in STYLES) draws that style's own."""
    if style in STYLES:
        return importlib.import_module(STYLES[style]).ornament(kind, size, color, glow)
    line = max(1, round(size / 12))
    if kind in ("note", "notes"):
        img = _sticker(_note(size, color, kind == "notes"), line)
    elif kind == "star":
        img = _star(size, color)
    elif kind == "heart":
        rim = tuple(round(c * 0.7) for c in color)
        img = _sticker(_heart(size, color, rim, line), line)
    else:
        raise ValueError(kind)
    return _glow(img, glow, max(1, round(size / 6)), 0.6) if glow else img


# ---------------------------------------------------------- motion


def ease_back(p):
    """0 to 1, a little past 1 and back: a pop."""
    p = min(1.0, max(0.0, p))
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def pop(age, delay=0.0, duration=0.35):
    return ease_back((age - delay) / duration) if age > delay else 0.0


def pulse(x):
    """A smooth bump over 0..1, zero outside it."""
    return math.sin(math.pi * x) ** 2 if 0 < x < 1 else 0.0


def thinking(w, h, t, age):
    """A plump mint thought bubble at the upper right whose three dots light
    up in turn, teal to pink, trailing two puffs back to her head; it bobs
    slowly."""
    sx, sy = SYMBOL_AT[0] * w, SYMBOL_AT[1] * h
    bob = 2 * math.sin(t * 2.0)
    draws = []
    for i, (name, (x, y)) in enumerate(zip(("puff_s", "puff_m"), PUFFS_AT)):
        draws.append(Draw(name, x * w, y * h + bob * (i + 1) / 3, pop(age, 0.08 * i)))
    grow = pop(age, 0.16)
    draws.append(Draw("bubble", sx, sy + bob, grow))
    gap = w * 0.045
    beat = (t * 0.9) % 1.0  # one sweep of the dots, then a rest
    for i in range(3):
        x, y = sx + (i - 1) * gap * grow, sy + bob
        lit = pulse((beat - i * 0.18) / 0.36)
        draws.append(Draw("dot_dim", x, y, grow * (1 - lit)))
        if lit:
            draws.append(Draw("dot_accent" if i == 2 else "dot_main", x, y - 2 * lit, grow * (0.8 + 0.45 * lit), lit))
    if 0.2 < age < 0.8:  # one twinkle as it lands
        p = (age - 0.2) / 0.6
        draws.append(Draw("twinkle", sx + w * 0.08, sy - h * 0.045, pulse(p) * 1.1, pulse(p)))
    return draws


NOTE_EVERY = 0.6  # a new note this often
NOTE_LIFE = 2.2  # seconds from the bars to gone


def _note_at(k, p, w, h):
    """Where note k is, `p` (0..1) into its life: up and a little right from
    the bars on a wave, tilting with it."""
    x0, y0 = EQ_AT[0] * w, EQ_AT[1] * h - 0.035 * h
    side = (-1, 1, 0.3)[k % 3]
    rise = 1 - (1 - p) ** 2
    x = x0 + side * 0.03 * w + 0.05 * w * p + 0.03 * w * math.sin(p * 2 * math.pi + k)
    y = y0 - rise * 0.24 * h  # gone before the top of the window
    return x, y, 14 * math.cos(p * 2 * math.pi + k)


def working(w, h, t, age):
    """An equalizer at the upper right, its bars bouncing to a beat, and
    notes (♪ and ♫, teal and pink by turns) rising from it on a wave with a
    sparkle trail, fading as they go."""
    draws = []
    bx, by = EQ_AT[0] * w, EQ_AT[1] * h
    grow = pop(age)
    pip_w, pip_h = 0.026 * w, 0.0125 * h
    for i in range(4):
        level = 0.5 + 0.5 * math.sin(t * (7.1 + 1.7 * i) + i * 1.3) * math.sin(t * (2.3 + 0.6 * i) + i)
        lit = 1 + round(3 * abs(level) * grow)
        x = bx + (i - 1.5) * pip_w * 1.35 * grow
        for j in range(lit):
            y = by - j * pip_h * 1.45 * grow
            draws.append(Draw("pip_accent" if j == 3 else "pip_main", x, y, grow))
    first = max(0, math.floor((age - NOTE_LIFE) / NOTE_EVERY) + 1)
    for k in range(first, math.floor(age / NOTE_EVERY) + 1):
        p = (age - k * NOTE_EVERY) / NOTE_LIFE
        color = "accent" if k % 2 else "main"
        fade = min(1.0, (1 - p) / 0.35)
        x, y, angle = _note_at(k, p, w, h)
        draws.append(Draw(("notes_" if k % 3 == 2 else "note_") + color, x, y, pop(p * NOTE_LIFE, 0, 0.25), fade, angle))
        for n in range(1, 3):
            q = p - 0.05 * n
            if q > 0:
                tx, ty, _ = _note_at(k, q, w, h)
                draws.append(Draw("spark_" + color, tx, ty + 0.02 * h, 0.9 - 0.25 * n, fade * (0.8 - 0.25 * n), 30 * n))
    return draws


ASK_EVERY = 1.5  # the "?" hops and the stars burst this often


def waiting(w, h, t, age):
    """A plump mint speech bubble with a pink "?" that hops now and then; on
    each hop a ring of little teal and pink stars bursts from it, and a small
    note peeks at its corner: she needs you, so this one calls the most."""
    sx, sy = SYMBOL_AT[0] * w, SYMBOL_AT[1] * h
    grow = pop(age)
    beat = (age % ASK_EVERY) / ASK_EVERY if age > 0.4 else 0
    hop = pulse(beat / 0.25)
    draws = []
    burst = beat / 0.55 if 0 < beat < 0.55 else 0
    if burst:
        reach = 1 - (1 - burst) ** 3
        for i in range(6):
            a = math.pi * 2 * i / 6 + 0.4
            r = w * (0.06 + 0.07 * reach)
            draws.append(Draw("spark_accent" if i % 2 else "spark_main", sx + r * math.cos(a), sy - 0.01 * h + r * math.sin(a) * 0.85,
                              1.5 - 0.6 * burst, 1 - burst ** 2, 90 * burst))
    squash = 1 + 0.06 * hop
    draws.append(Draw("speech", sx, sy, grow * squash))
    draws.append(Draw("question", sx + 0.004 * w, sy - 0.016 * h - 3 * hop, grow * (1 + 0.1 * hop), 1.0, -10 * hop))
    draws.append(Draw("note_main", sx + 0.075 * w, sy + 0.035 * h, grow * 0.6, 1.0, 12 * math.sin(t * 3)))
    return draws


SWEAT_EVERY = 2.2  # a new drop this often


def worried(w, h, t, age):
    """A sweat drop on her hair that slides down a little, glints and fades
    as the next one appears, and three little pink lines flickering out
    from her other temple: flustered, not upset."""
    draws = []
    lx, ly = LINES_AT[0] * w, LINES_AT[1] * h
    for i, a in enumerate((-195, -160, -125)):
        flick = 0.5 + 0.5 * math.sin(t * 9 + i * 2.1)
        out = 0.045 * w + 0.01 * w * flick
        rad = math.radians(a)
        draws.append(Draw("dash", lx + out * math.cos(rad), ly + out * math.sin(rad), pop(age, 0.05 * i) * (0.85 + 0.2 * flick),
                          0.55 + 0.45 * flick, -90 - a))
    beat = (age % SWEAT_EVERY) / SWEAT_EVERY
    first = age < SWEAT_EVERY
    grow = pop(age) if first else pop(beat * SWEAT_EVERY, 0, 0.3)
    slide = 0.025 * h * (1 - (1 - beat) ** 2)
    fade = min(1.0, (1 - beat) / 0.2)
    x, y = DROP_AT[0] * w, DROP_AT[1] * h + slide
    draws.append(Draw("drop", x, y, grow, fade))
    glint = pulse((beat - 0.25) / 0.3)
    if glint:
        draws.append(Draw("twinkle", x + 0.025 * w, y - 0.02 * h, 0.3 + 0.6 * glint, glint, 60 * beat))
    return draws


DOZE_EVERY = 1.1  # a new z this often
DOZE_LIFE = 3.3


def sleepy(w, h, t, age):
    """Soft z's (teal, every third pink) drifting up and right from beside
    her head, growing, swaying and tilting as they go, fading in and out,
    with a sleepy twinkle now and then."""
    draws = []
    x0, y0 = DOZE_AT[0] * w, DOZE_AT[1] * h
    first = max(0, math.floor((age - DOZE_LIFE) / DOZE_EVERY) + 1)
    for k in range(first, math.floor(age / DOZE_EVERY) + 1):
        p = (age - k * DOZE_EVERY) / DOZE_LIFE
        drift = 1 - (1 - p) ** 1.6
        x = x0 + 0.2 * w * drift + 0.025 * w * math.sin(p * 5 + k)
        y = y0 - 0.2 * h * drift
        alpha = min(1.0, p / 0.15, (1 - p) / 0.3)
        draws.append(Draw("z_accent" if k % 3 == 2 else "z_main", x, y, 0.55 + 0.7 * p, alpha, 15 * math.sin(p * 4 + k)))
    twinkle = pulse(((age + 0.6) % 2.7) / 0.8)
    if twinkle and age > 0.6:
        n = math.floor((age + 0.6) / 2.7)
        draws.append(Draw("spark_main" if n % 2 else "spark_accent", x0 + (0.1 + 0.05 * (n % 3)) * w, y0 - (0.06 + 0.04 * (n % 2)) * h,
                          0.6 + 0.6 * twinkle, twinkle, 40 * twinkle))
    return draws


BURST_S = 1.0  # how long the opening burst flies
HEART_EVERY = 1.3


def happy(w, h, t, age):
    """Idol-stage sparkle: a ring of stars (teal, pink, now and then gold)
    bursts out from her head as the mood starts, then stars keep twinkling
    around her raised arms and little pink hearts float up."""
    draws = []
    hx, hy = HEAD_AT[0] * w, HEAD_AT[1] * h
    if age < BURST_S:
        p = age / BURST_S
        reach = 1 - (1 - p) ** 3
        for i in range(9):
            a = math.radians(-195 + 210 * i / 8)  # fanned up and out, clear of her face
            r = w * (0.16 + 0.32 * reach) * (1.0 if i % 2 else 0.8)
            color = ("main", "accent", "main", "gold", "accent")[i % 5]
            draws.append(Draw("star_" + color, hx + r * math.cos(a), hy + r * math.sin(a) * 0.8,
                              (1.2 - 0.7 * p) * pop(age, 0, 0.15), 1 - p ** 3, 180 * p))
    for i, (x, y) in enumerate(SHINE_AT):
        cycle = 1.6 + 0.3 * i
        q = ((age - 0.3 - 0.37 * i) % cycle) / cycle if age > 0.3 + 0.37 * i else 0
        twinkle = pulse(q / 0.6)
        if twinkle:
            n = math.floor((age - 0.3 - 0.37 * i) / cycle)
            color = ("accent", "main", "accent", "main", "gold")[(i + n) % 5]
            draws.append(Draw("star_" + color, x * w, y * h, 0.3 + 0.7 * twinkle, twinkle, 45 * q))
    first = max(0, math.floor((age - 0.6 - 1.8) / HEART_EVERY) + 1)
    for k in range(first, math.floor(max(0, age - 0.6) / HEART_EVERY) + 1 if age > 0.6 else 0):
        p = (age - 0.6 - k * HEART_EVERY) / 1.8
        side = -1 if k % 2 else 1
        x = hx + side * w * (0.3 + 0.04 * math.sin(p * 6 + k))
        y = hy - 0.02 * h - 0.14 * h * (1 - (1 - p) ** 2)
        draws.append(Draw("heart", x, y, pop(p * 1.8, 0, 0.3) * 0.9, min(1.0, (1 - p) / 0.3), 12 * math.sin(p * 5 + k)))
    return draws


FALL_EVERY = 2.4  # a broken note drops this often
FALL_LIFE = 1.4


def error(w, h, t, age):
    """A grumpy little cloud above her head with a pink scribble tangling in
    it; the cloud shudders as it arrives, then huffs, and now and then a
    broken note tumbles out of it: upset, but cute."""
    cx, cy = CLOUD_AT[0] * w, CLOUD_AT[1] * h
    shudder = 3 * math.sin(age * 45) * max(0.0, 1 - age / 0.7)
    huff = 1 + 0.04 * math.sin(t * 3.2)
    grow = pop(age)
    draws = []
    k = math.floor((age - 0.8) / FALL_EVERY) if age > 0.8 else -1
    if k >= 0:
        p = (age - 0.8 - k * FALL_EVERY) / FALL_LIFE
        if p < 1:
            x = cx + 0.13 * w + 0.03 * w * p
            y = cy + 0.03 * h + 0.14 * h * p * p
            draws.append(Draw("broken_note", x, y, pop(p * FALL_LIFE, 0, 0.2), min(1.0, (1 - p) / 0.35), -8 - 30 * p))
    draws.append(Draw("cloud", cx + shudder, cy, grow * huff))
    jitter = math.floor(t * 7)  # the scribble redraws itself, a little cross
    draws.append(Draw("scribble", cx + shudder + 0.004 * w * (jitter % 3 - 1), cy + 0.01 * h, grow * (0.95 + 0.05 * (jitter % 2)), 1.0,
                      (jitter * 7) % 13 - 6))
    return draws


# "Miku Miku Beam!": a big finish. Heart hands held out at the viewer, she
# fires love at you:
#   charge: sparkles and notes spiral into her hands, a heart swells there.
#   fire: a flash, a recoil (`squash`), the call on a sticker banner, hollow
#     hearts bursting out of her hands toward the viewer, speed lines
#     radiating behind her (manga style), little hearts flying off.
#   afterglow: hearts floating up and popping, stars twinkling.
# The burst needs more room than the window has: until BEAM_WIDE_S the
# overlay draws her on a canvas BEAM_PAD larger on every side (`beamed`).

HANDS_AT = (0.56, 0.37)  # her heart hands, on the beam pose's frame
CHARGE_S = 0.7  # the charge; then she fires
RING_EVERY = 0.16
RING_LIFE = 0.9
BANNER_S = (0.75, 2.2)  # the banner pops in and is gone by then
BEAM_WIDE_S = 2.3
BEAM_PAD = 90
AFTERGLOW_S = 1.9


def beam_wide(age):
    """Whether the beam, `age` s in, is drawn on its larger canvas."""
    return age < (STYLE.BEAM_WIDE_S if STYLE else BEAM_WIDE_S)


def beam(w, h, t, age):
    """The beam's sprites over her (frame coordinates; the burst reaches
    well past the frame)."""
    hx, hy = HANDS_AT[0] * w, HANDS_AT[1] * h
    draws = []
    fired = age - CHARGE_S
    if fired < 0:
        p = age / CHARGE_S
        for i in range(10):
            q = min(1.0, max(0.0, (p - 0.04 * i) / 0.6))  # each arrives a little after the last
            if q <= 0 or q >= 1:
                continue
            a = i * math.tau / 10 + 5 * q
            r = w * 0.5 * (1 - q) ** 1.2
            sprite = ("note_main", "spark_accent", "spark_main", "note_accent", "spark_accent")[i % 5]
            draws.append(Draw(sprite, hx + r * math.cos(a), hy + 0.8 * r * math.sin(a), 0.6 + 0.6 * (1 - q), min(1.0, q * 4), 90 * q))
        swell = 0.35 + 0.75 * p ** 1.5 + 0.08 * math.sin(age * 30) * p
        draws.append(Draw("core_heart", hx, hy, swell, min(1.0, p * 3)))
        return draws
    # Little hearts flying off, in a ring that leans upward (clear of the floor).
    if fired < 1.2:
        p = fired / 1.2
        reach = 1 - (1 - p) ** 2.5
        for i in range(10):
            a = math.radians(-90 + 36 * i + 9 * math.sin(i * 2.3))
            r = w * (0.2 + 0.45 * reach) * (0.85 + 0.15 * (i % 3))
            draws.append(Draw("heart", hx + r * math.cos(a), hy + 0.85 * r * math.sin(a), 0.7 + 0.5 * (1 - p),
                              min(1.0, (1 - p) / 0.3), 25 * math.sin(p * 6 + i)))
    # Hollow hearts bursting toward the viewer: growing, thinning out.
    for k in range(3):
        p = (fired - k * RING_EVERY) / RING_LIFE
        if 0 <= p < 1:
            grow = 1 - (1 - p) ** 2
            draws.append(Draw("love_heart", hx, hy + 0.04 * h * grow, 0.25 + 2.4 * grow, (1 - p) ** 2.2, 6 * math.sin(k + p * 3)))
    # The heart in her hands: a flash as she fires, then it fades out.
    if fired < 0.9:
        draws.append(Draw("core_heart", hx, hy, 1.1 + 0.9 * pulse(fired / 0.5), max(0.0, 1 - fired / 0.9)))
    # The call.
    if BANNER_S[0] <= age < BANNER_S[1]:
        b = age - BANNER_S[0]
        fade = min(1.0, (BANNER_S[1] - age) / 0.3)
        draws.append(Draw("banner", 0.5 * w, -0.06 * h - 4 * pulse(b / 0.5), pop(b, 0, 0.3), fade, 6 * math.exp(-4 * b) * math.sin(b * 14) - 3))
    # Afterglow: hearts drifting up and popping into sparkles, stars twinkling.
    if age > AFTERGLOW_S:
        g = age - AFTERGLOW_S
        for i in range(5):
            p = (g - 0.22 * i) / 1.3
            if not 0 <= p < 1:
                continue
            side = -1 if i % 2 else 1
            x = hx + side * w * (0.18 + 0.08 * i) + 6 * math.sin(p * 7 + i)
            y = hy - h * (0.05 + 0.25 * p)
            if p < 0.8:
                draws.append(Draw("heart", x, y, 0.8 * pop(p * 1.3, 0, 0.25), 1.0, 12 * math.sin(p * 5 + i)))
            else:
                q = (p - 0.8) / 0.2
                draws.append(Draw("spark_" + ("accent" if i % 2 else "main"), x, y, 1.4 * pulse(q), pulse(q), 90 * q))
        for i, (x, y) in enumerate(SHINE_AT[:3]):
            q = ((g - 0.3 * i) % 1.2) / 1.2 if g > 0.3 * i else 0
            if pulse(q / 0.6):
                draws.append(Draw("star_" + ("accent", "main", "gold")[i], x * w, y * h, 0.3 + 0.6 * pulse(q / 0.6), pulse(q / 0.6), 45 * q))
    return draws


# A new version: the first time a newer one runs (the mod says so in the
# session file's `update`), her version on a sticker banner over her head in
# her main color, stars and notes fountaining up around her and sparkles by
# the banner, over whatever she is doing. Calm keeps the banner alone. The
# window is BEAM_PAD larger meanwhile (`celebrated`), as for the beam.
UPDATE_S = 3.4
UPDATE_BANNER_S = (0.15, 3.1)
UPDATE_AT = -0.04  # the banner's middle, a share of her height above her head


def version_banner(version, height):
    """The banner's sprite, "NEW! v0.15.0", for a mascot `height` px tall."""
    if STYLE:
        return STYLE.version_banner(version, height)
    k = height / BASE_HEIGHT

    def px(v):
        return max(1, round(v * k))

    words = version_words(version)
    pill = _banner(words, px(18), px(2), version_tint(), words)
    return _glow(_sticker(pill, px(2)), MAIN_LIGHT, px(4), 0.6)


def version_words(version):
    return f"NEW! v{version}"


def version_tint():
    """The version banner's colors: her main ink, lightened at the top."""
    return tuple(round(c + (255 - c) * 0.45) for c in MAIN), MAIN, MAIN_SHADE


def updated(w, h, t, age, calm=False):
    """The new version's sprites over her, `age` s in (frame coordinates;
    the banner stands above the frame)."""
    if STYLE:
        return STYLE.updated(w, h, t, age, calm)
    return _updated(w, h, t, age, calm)


def _updated(w, h, t, age, calm):
    """Miku's new-version motion: a style with the same sprite names may
    use it too."""
    draws = []
    start, end = UPDATE_BANNER_S
    if start <= age < end:
        b = age - start
        sway = 0.0 if calm else 5 * math.exp(-4 * b) * math.sin(b * 14) - 2
        draws.append(Draw("version", 0.5 * w, UPDATE_AT * h - 3 * pulse(b / 0.5), pop(b, 0, 0.3),
                          min(1.0, (end - age) / 0.3), sway))
    if calm:
        return draws
    # Stars and notes rising from her feet on both sides, slowing as they go.
    for i in range(12):
        p = (age - 0.08 * i) / 1.7
        if not 0 <= p < 1:
            continue
        side = -1 if i % 2 else 1
        x = 0.5 * w + side * w * (0.3 + 0.1 * math.sin(i * 1.7)) * (0.7 + 0.3 * p) + 0.03 * w * math.sin(p * 9 + i)
        y = h * (0.95 - 0.95 * (1 - (1 - p) ** 2))
        sprite = ("star_main", "note_accent", "star_accent", "note_main", "star_gold", "spark_main")[i % 6]
        draws.append(Draw(sprite, x, y, 0.5 + 0.5 * pop(p * 1.7, 0, 0.2), min(1.0, (1 - p) / 0.3), 30 * math.sin(p * 4 + i)))
    # Sparkles twinkling around the banner.
    if age > 0.4:
        for i in range(4):
            q = ((age - 0.4 - 0.25 * i) % 0.9) / 0.9
            y = (UPDATE_AT + (0.06 if i % 2 else -0.06)) * h
            draws.append(Draw("spark_" + ("accent" if i % 2 else "main"), (0.5 + (i - 1.5) * 0.28) * w, y,
                              1.3 * pulse(q), pulse(q), 90 * q))
    return draws


def celebrated(image, draws, sprites):
    """The window's `image` (as compose() makes it) on a canvas BEAM_PAD
    larger on every side, `draws` (the new version's) over her."""
    out = Image.new("RGBA", (image.width + 2 * BEAM_PAD, image.height + 2 * BEAM_PAD), (0, 0, 0, 0))
    out.alpha_composite(image, (BEAM_PAD, BEAM_PAD))
    return paint(out, draws, sprites, (PAD_LEFT + BEAM_PAD, PAD_TOP + BEAM_PAD))


_line_fades = {}


def _fade_mask(size, center, reach):
    """An "L" mask on a canvas `size`: full out to half of `reach` from
    `center`, fading to nothing at `reach`, so lines end softly, never at
    the window's edge. One kept: the beam pose's frames share a size."""
    key = (size, round(center[0]), round(center[1]), round(reach))
    if key not in _line_fades:
        _line_fades.clear()
        r = round(reach)
        disc = Image.radial_gradient("L").resize((2 * r, 2 * r), Image.BILINEAR)
        disc = disc.point(lambda v: round(255 * min(1.0, max(0.0, 2 * (1 - v / RADIAL_EDGE)))))
        mask = Image.new("L", size, 0)
        mask.paste(disc, (round(center[0]) - r, round(center[1]) - r))
        _line_fades[key] = mask
    return _line_fades[key]


def _speed_lines(size, center, inner, strength, t):
    """Manga speed lines radiating from `center` on a canvas `size`: thin
    wedges, wide outside and sharp toward the middle, teal, pink and white,
    starting `inner` px out and fading before the canvas's edge; they redraw
    a little differently every GLITCH_STEP, flickering like a drawn effect."""
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if strength <= 0.01:
        return out
    d = ImageDraw.Draw(out)
    cx, cy = center
    reach = min(cx, cy, size[0] - cx, size[1] - cy) - 4  # clear of the edge, resampling included
    step = math.floor(t / GLITCH_STEP)
    n = 26
    for i in range(n):
        a = math.tau * (i + 0.6 * _rand(step, i, 90)) / n
        r0 = inner * (0.85 + 0.45 * _rand(step, i, 91))
        half = 0.01 + 0.014 * _rand(step, i, 92)
        color = (MAIN_LIGHT, ACCENT_LIGHT, WHITE)[i % 3]
        alpha = round(255 * strength * (0.35 + 0.3 * _rand(step, i, 93)))
        tip = (cx + r0 * math.cos(a), cy + r0 * math.sin(a))
        d.polygon([tip, (cx + reach * math.cos(a - half), cy + reach * math.sin(a - half)),
                   (cx + reach * math.cos(a + half), cy + reach * math.sin(a + half))], fill=color + (alpha,))
    out.putalpha(ImageChops.multiply(out.getchannel("A"), _fade_mask(size, center, reach)))
    return out


def beamed(image, w, h, age, t, draws, sprites, calm=False):
    """The window's `image` (as compose() makes it, for a frame w by h,
    without its symbols) on a canvas BEAM_PAD larger on every side, with the
    beam's speed lines and flash behind her (not when `calm`) and `draws`
    over her."""
    if STYLE:
        return STYLE.beamed(image, w, h, age, t, draws, sprites, calm)
    out = Image.new("RGBA", (image.width + 2 * BEAM_PAD, image.height + 2 * BEAM_PAD), (0, 0, 0, 0))
    at = (PAD_LEFT + BEAM_PAD, PAD_TOP + BEAM_PAD)
    hx, hy = at[0] + HANDS_AT[0] * w, at[1] + HANDS_AT[1] * h
    fired = age - CHARGE_S
    if fired >= 0 and not calm:
        strength = pop(fired, 0, 0.12) * (1 - _span(fired, 0.8, 1.4))
        out.alpha_composite(_speed_lines(out.size, (hx, hy), w * (0.3 + 0.25 * min(1.0, fired / 0.8)), strength, t))
        flash = pulse(min(1.0, fired / 0.7) * 0.5 + 0.5) if fired < 0.7 else 0.0
        paint(out, [Draw("flash_accent", HANDS_AT[0] * w, HANDS_AT[1] * h, 5.0, 0.8 * flash),
                    Draw("flash_main", HANDS_AT[0] * w, HANDS_AT[1] * h, 2.8, 0.7 * flash)], sprites, at)
    out.alpha_composite(image, (BEAM_PAD, BEAM_PAD))
    return paint(out, draws, sprites, at)


def recoil(frame, age):
    """The beam pose's `frame` kicked back onto her feet as she fires."""
    fire = STYLE.CHARGE_S if STYLE else CHARGE_S
    return squash(frame, age - fire) if age >= fire else frame


# Her call (the `magicAfter` setting): a long enough round of work over,
# she sends magic to your pointer, whichever display it is on. A
# comet leaves her heart hands trailing sparkles and notes, and flies on an
# arc to the pointer, homing in as it moves; it bursts there (a flash, a
# ring of stars), then two notes and a heart circle the pointer, following
# it, until you click or MAGIC_LINGER_S has passed, and fly apart. Hidden,
# she sends it all the same: sparkles gather at the pointer instead. Calm:
# a short trail, no flash or burst, the circling alone.
#
# It is drawn in a window of its own (magic.py), MAGIC_BOX square, centered
# on the comet as it flies (`magic_head`), then on the pointer; what is in
# it (`magic`) is worked out from the time alone, given where the comet
# left and where the pointer is, around the middle of that window.

MAGIC_BOX = 240  # px, the window's side
MAGIC_SPEED = 2600  # px/s the comet adds to its shortest flight
MAGIC_FLIGHT_S = (0.55, 1.1)  # its shortest and longest flight
MAGIC_GATHER_S = 0.55  # hidden, the sparkles gather this long
MAGIC_ARC = 0.22  # how far the arc bows, a share of the way
MAGIC_TRAIL = 12  # sparkles in the trail, MAGIC_TRAIL_S apart on the way
MAGIC_TRAIL_S = 0.022
MAGIC_BURST_S = 0.7
MAGIC_LINGER_S = 6.0  # circling the pointer at most this long after it lands
MAGIC_LEAVE_S = 0.45


def magic_from(w, h):
    """Where her call leaves her frame, w by h: her heart hands."""
    x, y = STYLE.HANDS_AT if STYLE else HANDS_AT
    return x * w, y * h


def magic_flight(start, target):
    """How long the call takes to land, set as it leaves: flying from
    `start` to `target` (desktop px), longer the farther; gathering when it
    leaves from nowhere (`start` None: she is hidden)."""
    if start is None:
        return MAGIC_GATHER_S
    low, high = MAGIC_FLIGHT_S
    return min(high, low + math.dist(start, target) / MAGIC_SPEED)


def _arc(start, target, e):
    """A point `e` (0..1) of the way along the arc from `start` to `target`,
    bowed upward."""
    (x0, y0), (x2, y2) = start, target
    dx, dy = x2 - x0, y2 - y0
    d = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / d, dx / d
    if ny > 0:
        nx, ny = -nx, -ny
    cx, cy = (x0 + x2) / 2 + nx * MAGIC_ARC * d, (y0 + y2) / 2 + ny * MAGIC_ARC * d
    u = 1 - e
    return u * u * x0 + 2 * u * e * cx + e * e * x2, u * u * y0 + 2 * u * e * cy + e * e * y2


def magic_head(start, target, flight, age):
    """Where the comet is (desktop px), `age` s after it left `start` for
    the pointer at `target`; the pointer itself once it has landed."""
    if start is None or age >= flight:
        return target
    p = max(0.0, age / flight)
    return _arc(start, target, p * p * (3 - 2 * p))


def magic_over(age, ended):
    """Whether the call, `age` s in and ended at `ended` (None: not yet), is gone."""
    return ended is not None and age - ended >= MAGIC_LEAVE_S


def magic(start, target, flight, age, t, ended=None, calm=False):
    """The call's sprites `age` s in, around the middle of its window (the
    comet's head, then the pointer): `start` and `target` as for
    `magic_head`, `flight` from `magic_flight`, `ended` the age at which
    it was dismissed (None: not yet)."""
    if STYLE:
        return STYLE.magic(start, target, flight, age, t, ended, calm)
    return _magic(start, target, flight, age, t, ended, calm)


def _magic(start, target, flight, age, t, ended, calm, note=lambda k, tint: f"note_{tint}"):
    """Miku's call; a style with the same sprite names may use it too,
    `note(k, tint)` naming the sprite of its note k."""
    box = MAGIC_BOX
    reach = 0.45 * box  # nothing is drawn farther from the middle
    draws = []
    if age < flight and start is None:
        # Gathering at the pointer: sparkles spiral in.
        p = age / flight
        for i in range(4 if calm else 8):
            q = min(1.0, max(0.0, (p - 0.05 * i) / 0.6))
            if 0 < q < 1:
                a = i * math.tau / 8 + 4 * q
                r = reach * (1 - q) ** 1.2
                sprite = ("spark_main", "spark_accent", "star_main", "spark_accent")[i % 4]
                draws.append(Draw(sprite, r * math.cos(a), r * math.sin(a), 0.6 + 0.6 * (1 - q), min(1.0, q * 4), 90 * q))
        return draws
    if age < flight:
        # The trail: where the head was a moment ago, fading with distance.
        hx, hy = magic_head(start, target, flight, age)
        for i in range(1, (5 if calm else MAGIC_TRAIL) + 1):
            back = age - MAGIC_TRAIL_S * i
            if back < 0:
                break
            x, y = magic_head(start, target, flight, back)
            ox, oy = x - hx, y - hy
            dist = math.hypot(ox, oy)
            if dist >= reach:
                break
            fade = (1 - dist / reach) * (1 - i / (MAGIC_TRAIL + 1))
            wobble = 0.05 * box * math.sin(i * 1.9 + t * 9) * min(1.0, dist / (0.1 * box))
            if i % 4 == 0:
                draws.append(Draw(note(i // 4, "accent" if i % 8 else "main"), ox, oy + wobble, 1.0, fade, 15 * math.sin(t * 6 + i)))
            else:
                sprite = ("spark_main", "spark_accent", "pixel_main")[i % 3]
                draws.append(Draw(sprite, ox, oy - wobble, 2.0 - 0.08 * i, fade, 40 * i + 300 * t))
        if not calm:
            draws.append(Draw("flash_main", 0, 0, 1.3, 0.6))
        draws.append(Draw("star_main", 0, 0, 1.6, 1.0, -400 * age))
        return draws
    landed = age - flight
    if landed < MAGIC_BURST_S and not calm:
        # It bursts on the pointer: a flash, a ring of stars flying out.
        p = landed / MAGIC_BURST_S
        draws.append(Draw("flash_accent", 0, 0, 1.0 + 1.6 * p, 0.8 * (1 - p) ** 2))
        out = 1 - (1 - p) ** 3
        for i in range(8):
            a = math.tau * i / 8 + 0.3
            r = box * (0.08 + 0.3 * out)
            draws.append(Draw("star_" + ("main", "accent", "gold", "accent")[i % 4], r * math.cos(a), r * math.sin(a),
                              (1.1 - 0.6 * p) * pop(landed, 0, 0.12), 1 - p ** 3, 180 * p))
    # Circling the pointer (a little down and right of its tip, around the
    # arrow), then flying apart once dismissed.
    leave = 0.0 if ended is None else _span(age - ended, 0, MAGIC_LEAVE_S)
    grow = pop(landed, 0.12, 0.35)
    cx, cy = 0.03 * box, 0.04 * box
    if grow > 0 and leave < 1:
        for i, sprite in enumerate((note(0, "main"), "heart", note(1, "accent"))):
            a = 2.4 * landed + math.tau * i / 3
            r = box * (0.17 + 0.2 * leave)
            bob = 0.012 * box * math.sin(t * 5 + i * 2)
            draws.append(Draw(sprite, cx + r * math.cos(a), cy + 0.8 * r * math.sin(a) + bob, grow * (0.9 + 0.3 * leave),
                              1 - leave, 12 * math.sin(t * 3 + i)))
        if not calm and ended is None:
            q = (landed % 0.9) / 0.9
            n = math.floor(landed / 0.9)
            a = n * 2.4
            draws.append(Draw("spark_" + ("accent" if n % 2 else "main"), cx + 0.26 * box * math.cos(a),
                              cy + 0.22 * box * math.sin(a), 1.3 * pulse(q), pulse(q), 90 * q))
    if ended is not None and not calm:
        # A pop of sparkles as it goes.
        p = (age - ended) / MAGIC_LEAVE_S
        if 0 <= p < 1:
            for i in range(6):
                a = math.tau * i / 6
                r = box * (0.1 + 0.25 * p)
                draws.append(Draw("spark_" + ("accent" if i % 2 else "main"), cx + r * math.cos(a), cy + r * math.sin(a),
                                  1.2 * (1 - p), 1 - p, 120 * p))
    return draws


PLACEMENTS = {"thinking": thinking, "working": working, "waiting": waiting, "worried": worried, "sleepy": sleepy,
              "happy": happy, "error": error, "beam": beam}


def placements(mood, w, h, t, age):
    """[Draw] for `mood` at time `t`, `age` seconds into the mood, on a frame
    w by h; [] for a mood with no symbol."""
    fn = (STYLE.PLACEMENTS if STYLE else PLACEMENTS).get(mood)
    return fn(w, h, t, age) if fn else []


def moving(mood, age):
    """Whether anything moves, `age` seconds into `mood`: a mood's symbol
    always does; her glitch for a moment."""
    return mood in (STYLE.PLACEMENTS if STYLE else PLACEMENTS) or glitch_amount(mood, age) > 0


# ---------------------------------------------------------- glitch
#
# Her "digital diva" side: for a moment she splits into teal and pink ghosts
# and bands of her slide sideways. Every mood change does it briefly, like a
# hologram changing channel; error does it hard as it starts and in short
# bursts after.

SWITCH_GLITCH_S = 0.22
ERROR_GLITCH_S = 0.6
ERROR_BURST_EVERY = 3.4
ERROR_BURST_S = 0.28
GLITCH_STEP = 1 / 20  # the glitch picks new bands this often


def glitch_amount(mood, age):
    """How hard she glitches (0..1), `age` seconds into `mood`."""
    amount = max(0.0, 1 - age / SWITCH_GLITCH_S) * 0.6
    if mood == "error":
        if age < ERROR_GLITCH_S:
            amount = max(amount, 1 - (age / ERROR_GLITCH_S) ** 2)
        else:
            q = (age - ERROR_GLITCH_S) % ERROR_BURST_EVERY
            if q > ERROR_BURST_EVERY - ERROR_BURST_S:
                amount = max(amount, 0.7)
    return amount


def _rand(*keys):
    """A repeatable 0..1 from integers: the same moment glitches the same way."""
    n = 0x9E3779B1
    for k in keys:
        n = (n ^ (k & 0xFFFFFFFF)) * 0x85EBCA6B & 0xFFFFFFFF
        n ^= n >> 13
    return (n * 0xC2B2AE35 & 0xFFFFFFFF) / 0xFFFFFFFF


def _ghost(frame, color, alpha):
    ghost = Image.new("RGBA", frame.size, color + (0,))
    ghost.putalpha(frame.getchannel("A").point(lambda a: a * alpha))
    return ghost


def glitch(frame, amount, t):
    """`frame` glitched by `amount` (0..1) at time `t`: teal and pink ghosts
    split left and right, a few bands slid sideways, faint scanlines."""
    if amount <= 0.02:
        return frame
    if STYLE:
        return STYLE.glitch(frame, amount, t)
    w, h = frame.size
    step = math.floor(t / GLITCH_STEP)
    split = max(1, round(w * 0.025 * amount * (0.5 + _rand(step, 1))))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(_ghost(frame, MAIN_LIGHT, 0.75 * amount), (0, 0), (split, 0))
    out.alpha_composite(_ghost(frame, ACCENT_LIGHT, 0.75 * amount), (split, 0))
    out.alpha_composite(frame)
    for i in range(1 + round(5 * amount)):
        top = round(_rand(step, i, 2) * h * 0.9)
        band = round(h * (0.01 + 0.05 * _rand(step, i, 3)))
        shift = round((_rand(step, i, 4) - 0.5) * w * 0.12 * amount)
        if not shift or band < 1:
            continue
        piece = out.crop((0, top, w, min(h, top + band)))
        tint = _ghost(piece, MAIN_LIGHT if shift < 0 else ACCENT_LIGHT, 0.35)
        piece.alpha_composite(tint)
        out.paste((0, 0, 0, 0), (0, top, w, min(h, top + band)))
        out.alpha_composite(piece, (max(0, shift), top), (max(0, -shift), 0))
    if amount > 0.3:
        lines = Image.new("L", (1, h), 255)
        lines.putdata([255 if y % 3 else round(255 * (1 - 0.35 * amount)) for y in range(h)])
        out.putalpha(ImageChops.multiply(out.getchannel("A"), lines.resize((w, h))))
    return out


def paint(out, draws, sprites, at=None):
    """The sprites `draws` asks for onto `out`, a canvas as compose() makes
    (frame coordinates, offset by the pads), or one with the frame's top
    left `at` elsewhere."""
    at = at or (PAD_LEFT, PAD_TOP)
    for d in draws:
        if d.scale <= 0.01 or d.alpha <= 0.01:
            continue
        img = sprites[d.sprite]
        if abs(d.scale - 1) > 0.01:
            img = img.resize((max(1, round(img.width * d.scale)), max(1, round(img.height * d.scale))), Image.BILINEAR)
        if abs(d.angle) > 0.5:
            img = img.rotate(d.angle, Image.BICUBIC, expand=True)
        if d.alpha < 0.99:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda a: a * d.alpha))
        x, y = round(d.x + at[0] - img.width / 2), round(d.y + at[1] - img.height / 2)
        if x + img.width <= 0 or y + img.height <= 0 or x >= out.width or y >= out.height:
            continue
        out.alpha_composite(img, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    return out


def compose(frame, draws, sprites, under=None, behind=None, over=None):
    """The frame on a canvas padded above, left and right, with `behind`
    (her aura) under it and `over` (her status's sparkles) over it, both
    canvases from its top left; the symbols `draws` over all that, and
    `under` (the name tag) centered below her feet."""
    below = under.height + UNDER_GAP if under else 0
    out = Image.new("RGBA", (PAD_LEFT + frame.width + PAD_RIGHT, frame.height + PAD_TOP + below), (0, 0, 0, 0))
    if behind:
        out.alpha_composite(behind)
    out.alpha_composite(frame, (PAD_LEFT, PAD_TOP))
    if under:
        out.alpha_composite(under, (PAD_LEFT + (frame.width - under.width) // 2, PAD_TOP + frame.height + UNDER_GAP))
    if over:
        out.alpha_composite(over)
    return paint(out, draws, sprites)


# ---------------------------------------------------------- status
#
# What lasts beyond the mood, drawn around her (`dress`):
#   context past CONTEXT_TIERS tokens: an aura that builds up the longer she
#     sings, like stage lights warming on the diva. Teal; then pink with
#     sparkles and notes drifting up; then an overloaded magenta beating like
#     a heart, pixels crackling off her edges, a flicker of static.
#   5-hour limit LIMIT_NEAR% used: the stage light at her feet is failing, a
#     ring of light on the floor that hums, sputters and flickers.
#   weekly limit LIMIT_NEAR% used: she is a hologram fading from the stage,
#     scanlines, a bright band rolling down her, bits of her flaking away.
# The aura and the floor light go behind her, so the mood's symbol and
# glitch stay hers. A change crossfades over STATUS_FADE_S. What depends on
# her shape alone is worked out once per frame (`_masks`): her frames repeat.

Status = namedtuple("Status", "context five_hour weekly")
Status.__new__.__defaults__ = (0, False, False)
CALM = Status()

CONTEXT_TIERS = (300_000, 400_000, 500_000)
LIMIT_NEAR = 90  # percent of a usage limit used
STATUS_FADE_S = 1.5
AURA_RADIUS = 9  # px of glow past her edge
AURA_SCALE = 4  # the glow is worked out this many times smaller: cheap
SCAN_EVERY = 5  # px between hologram scanlines
SCAN_BAND_S = 2.4  # a bright band rolls down her this often

# Her figure's masks, by id of the frame they were made from (the frames are
# kept while she is shown; each entry goes when its frame does, so an id
# used again never finds another frame's masks). Images are not hashable.
_masks = {}
_outlines = {}


def context_level(tokens, tiers=CONTEXT_TIERS):
    """0 under the first of `tiers` tokens, then 1, 2, 3 as it passes each
    (the `aura` setting; none: always 0)."""
    if not isinstance(tokens, (int, float)) or isinstance(tokens, bool):
        return 0
    return sum(1 for tier in tiers if tokens >= tier)


def _fades(now, before, age):
    """{(effect, level): 0..1}: `before` crossfading into `now`, `age`
    seconds after the change."""
    f = min(1.0, max(0.0, age / STATUS_FADE_S))
    out = {}

    def add(key, amount):
        if amount > 0.01:
            out[key] = out.get(key, 0.0) + amount

    if now.context == before.context:
        add(("aura", now.context), 1.0 if now.context else 0.0)
    else:
        add(("aura", before.context), 1 - f if before.context else 0.0)
        add(("aura", now.context), f if now.context else 0.0)
    for name in ("five_hour", "weekly"):
        on, was = getattr(now, name), getattr(before, name)
        add((name, 0), 1.0 if on and was else f if on else 1 - f if was else 0.0)
    return out


def status_moving(now, before, age, calm=False):
    """Whether her status keeps something moving (then the window redraws at
    ANIMATE_FPS): sparkles, flicker, hologram, or a crossfade. Calm, it
    holds still but for the crossfade."""
    if now != before and age < STATUS_FADE_S:
        return True
    return not calm and (now.context >= 2 or now.five_hour or now.weekly)


def _outline(frame):
    """Where her edge is on each row (`rows`: (left, right) or None) and her
    bounding box (`feet`), once per frame."""
    cached = _outlines.get(id(frame))
    if cached is not None:
        return cached
    w, h = frame.size
    solid = frame.getchannel("A").point(lambda a: 255 if a > 100 else 0)
    rows = []
    for y in range(h):
        box = solid.crop((0, y, w, y + 1)).getbbox()
        rows.append((box[0], box[2]) if box else None)
    cached = {"rows": rows, "feet": solid.getbbox()}
    _outlines[id(frame)] = cached
    weakref.finalize(frame, _outlines.pop, id(frame), None)
    return cached


def _shape(frame):
    """What her outline gives once per frame: the aura's glow (two sizes),
    the light along her edge, where her edge is on each row, her feet."""
    cached = _masks.get(id(frame))
    if cached is not None:
        return cached
    w, h = frame.size
    k = AURA_SCALE
    cw, ch = PAD_LEFT + w + PAD_RIGHT, PAD_TOP + h
    alpha = frame.getchannel("A")
    solid = alpha.point(lambda a: 255 if a > 100 else 0)
    small = Image.new("L", (cw // k, ch // k), 0)
    small.paste(alpha.resize((w // k, h // k), Image.BILINEAR).point(lambda a: 255 if a > 100 else 0), (PAD_LEFT // k, PAD_TOP // k))
    # Her silhouette with its gaps closed, pulled in a little: the glow stays
    # outside it (in the gaps between tails and body it would read as a
    # sticker's backing) and starts under her edge (no dark seam).
    closed = _shrink(_grow(small, 9), 11)
    outside = ImageChops.invert(closed).filter(ImageFilter.GaussianBlur(0.6))
    glows = {}
    for big in (False, True):
        halo = small.filter(ImageFilter.GaussianBlur(AURA_RADIUS * (1.25 if big else 1.0) / k))
        glows[big] = ImageChops.multiply(halo, outside)  # scaled up as it is drawn
    edge = ImageChops.subtract(solid, _shrink(solid, 3)).filter(ImageFilter.GaussianBlur(0.8))
    edge = ImageChops.multiply(edge, alpha)
    cached = {"glow": glows, "edge": edge, **_outline(frame)}
    _masks[id(frame)] = cached
    weakref.finalize(frame, _masks.pop, id(frame), None)
    return cached


def _breath(t, period):
    return 0.5 - 0.5 * math.cos(2 * math.pi * t / period)


def _heartbeat(t, period=1.3):
    """Two quick beats then a rest, 0..1."""
    q = (t % period) / period
    return max(pulse(q / 0.14), 0.7 * pulse((q - 0.17) / 0.14))


# Calm, the aura holds still at about the middle of its breath.
CALM_AURA = {1: 0.52, 2: 0.67, 3: 0.85}


def aura_strength(level, t, calm=False):
    """How bright the aura is now (0..1): it breathes, and overload beats."""
    if level <= 0:
        return 0.0
    if calm:
        return CALM_AURA[min(level, 3)]
    if level == 1:
        return 0.4 + 0.25 * _breath(t, 3.2)
    if level == 2:
        return 0.55 + 0.25 * _breath(t, 2.4)
    return 0.7 + 0.3 * _heartbeat(t)


def _aura_colors(level):
    """(the glow around her, the light along her edge)."""
    return AURA[min(level, 3) - 1]


def _scaled(mask, amount):
    # A plain product: PIL then scales in C (clipped to 255) instead of
    # calling the lambda for each of the 256 levels, as round() or min() makes it.
    return mask.point(lambda a: a * amount)


def _aura(shape, level, strength, size):
    glow = _scaled(shape["glow"][level >= 3], 2.2 * strength).resize(size, Image.BILINEAR)
    out = Image.new("RGBA", size, _aura_colors(level)[0] + (0,))
    out.putalpha(glow)
    return out


def _rim(frame, shape, level, strength):
    """A thin light along her own edge, as a spotlight catches her outline."""
    light = Image.new("RGBA", frame.size, _aura_colors(level)[1] + (0,))
    light.putalpha(_scaled(shape["edge"], 0.7 * strength))
    out = frame.copy()
    out.alpha_composite(light)
    return out


def _flicker(t):
    """A failing stage light's brightness (0..1) at time `t`: mostly on with
    a little hum, now and then a sputter, sometimes a few in a row."""
    step = math.floor(t / 0.06)
    hum = 0.85 + 0.08 * math.sin(t * 7.3) + 0.04 * math.sin(t * 17.1)
    burst = math.floor(t / 2.9)
    in_burst = _rand(burst, 31) < 0.55 and 0 <= t - burst * 2.9 - 2.9 * _rand(burst, 32) * 0.6 < 0.45
    if in_burst and _rand(step, 33) < 0.55:
        return 0.12 + 0.2 * _rand(step, 34)
    if _rand(step, 35) < 0.025:
        return 0.35
    return hum


def _floor_ring(w, h):
    """The stage light's shape (an "L" pool with a bright rim, and its teal
    halo), for a frame w by h; drawn SUPER large and scaled down."""
    rx, ry = w * 0.36, h * 0.034
    k = SUPER
    size = (round(rx * 2 + 24) * k, round(ry * 2 + 24) * k)
    ox, oy = size[0] / 2, size[1] / 2
    box = (ox - rx * k, oy - ry * k, ox + rx * k, oy + ry * k)
    pool = Image.new("L", size, 0)
    ImageDraw.Draw(pool).ellipse(box, fill=70)
    ring = Image.new("L", size, 0)
    ImageDraw.Draw(ring).ellipse(box, outline=255, width=round(2.2 * k))
    glow = ring.filter(ImageFilter.GaussianBlur(4 * k))
    light = ImageChops.lighter(ImageChops.lighter(pool.filter(ImageFilter.GaussianBlur(3 * k)), ring), glow.point(lambda a: min(255, a * 2)))
    small = (size[0] // k, size[1] // k)
    return light.resize(small, Image.LANCZOS), glow.resize(small, Image.LANCZOS).point(lambda a: min(255, round(a * 1.6)))


_rings = {}


CALM_LIGHT = 0.55  # calm, the failing light is a steady dim one


def _floor_light(shape, frame, t, fade, calm=False):
    """The failing stage light under her boots, flickering (steady dim when
    `calm`), as (image, x, y) on the canvas."""
    b = (CALM_LIGHT if calm else _flicker(t)) * fade
    if b <= 0.01 or not shape["feet"]:
        return None
    w, h = frame.size
    if (w, h) not in _rings:
        _rings.clear()
        _rings[(w, h)] = _floor_ring(w, h)
    light, glow = _rings[(w, h)]
    out = Image.new("RGBA", light.size, MAIN_LIGHT + (0,))
    out.putalpha(_scaled(glow, b))
    top = Image.new("RGBA", light.size, PALE + (0,))
    top.putalpha(_scaled(light, b))
    out.alpha_composite(top)
    feet = shape["feet"]
    cx = PAD_LEFT + (feet[0] + feet[2]) / 2
    cy = PAD_TOP + feet[3] - h * 0.012
    return out, round(cx - out.width / 2), round(cy - out.height / 2)


_scans = {}  # the scanlines' mask, for a frame size


def _hologram(frame, shape, t, fade, calm=False):
    """`frame` as a fading hologram: a teal tint, fine scanlines, a little
    see-through, and a bright band rolling down her now and then (not when
    `calm`). Fully faded in (the usual case), the scanlines are worked out
    once."""
    w, h = frame.size
    alpha = frame.getchannel("A")
    tint = Image.new("RGBA", (w, h), MAIN_LIGHT + (0,))
    tint.putalpha(_scaled(alpha, 0.1 * fade))
    if fade >= 0.999 and _scans.get("size") == (w, h):
        scan = _scans["mask"]
    else:
        scan = Image.new("L", (1, h))
        scan.putdata([round(255 * (1 - fade * (1 - (0.8 if y % SCAN_EVERY == 0 else 0.96)))) for y in range(h)])
        scan = scan.resize((w, h))
        if fade >= 0.999:
            _scans.update(size=(w, h), mask=scan)
    out = frame.copy()
    out.alpha_composite(tint)
    # The bright band: only the rows it covers.
    band_y = ((t % SCAN_BAND_S) / SCAN_BAND_S) * (h * 1.3) - h * 0.15
    reach = h * 0.04
    top, bottom = max(0, int(band_y - reach)), min(h, int(band_y + reach) + 1)
    if bottom > top and not calm:
        bright = Image.new("L", (1, bottom - top))
        bright.putdata([round(255 * max(0.0, 1 - abs(y - band_y) / reach) * 0.45 * fade) for y in range(top, bottom)])
        shine = Image.new("RGBA", (w, bottom - top), PALE + (0,))
        shine.putalpha(ImageChops.multiply(bright.resize((w, bottom - top)), alpha.crop((0, top, w, bottom))))
        out.alpha_composite(shine, (0, top))
    out.putalpha(ImageChops.multiply(out.getchannel("A"), scan))
    return out


RISE_EVERY = 0.35  # level 2 up: a sparkle or note leaves her this often
RISE_LIFE = 2.6
CRACKLE_EVERY = 0.07  # level 3: a pixel flakes off her edge this often
CRACKLE_LIFE = 0.7
FLAKE_EVERY = 0.12  # the weekly fade: a bit of her floats away this often
FLAKE_LIFE = 1.8


def _edge_point(shape, h, u, side):
    """Where her outline is at height share `u`, on her left (-1) or right side."""
    row = shape["rows"][min(h - 1, max(0, round(u * h)))]
    if not row:
        return None
    return (row[0] if side < 0 else row[1]), round(u * h)


def _spawned(t, every, life):
    """(n, age, p) for each particle alive at `t`, one born every `every` s."""
    for n in range(math.floor((t - life) / every) + 1, math.floor(t / every) + 1):
        age = t - n * every
        if 0 <= age < life:
            yield n, age, age / life


def _aura_draws(shape, w, h, level, t, fade):
    draws = []
    # Sparkles and notes drift up off her shoulders and hair.
    for n, age, p in _spawned(t, RISE_EVERY, RISE_LIFE):
        x = w * (0.12 + 0.76 * _rand(n, 11)) + math.sin(age * 2.2 + n) * w * 0.025
        y = h * (0.25 + 0.35 * _rand(n, 12)) - p * h * 0.32
        kind = _rand(n, 13)
        if level >= 3:
            sprite = "spark_accent" if kind < 0.5 else "pixel_hot" if kind < 0.8 else "note_accent"
        else:
            sprite = "spark_main" if kind < 0.35 else "spark_accent" if kind < 0.7 else "note_main" if kind < 0.85 else "note_accent"
        scale = (0.55 + 0.35 * _rand(n, 14)) * (0.6 if sprite.startswith("note") else 1.0)
        alpha = min(1.0, p / 0.15) * min(1.0, (1 - p) / 0.35) * 0.85 * fade
        draws.append(Draw(sprite, x, y, scale, alpha, math.sin(age * 3 + n) * 12))
    if level >= 3:
        # Pixels crackle off her edges, flung out a little, fading.
        for n, age, p in _spawned(t, CRACKLE_EVERY, CRACKLE_LIFE):
            side = -1 if _rand(n, 21) < 0.5 else 1
            spot = _edge_point(shape, h, 0.08 + 0.8 * _rand(n, 22), side)
            if spot:
                x = spot[0] + side * (2 + p * w * 0.06)
                y = spot[1] - p * h * 0.03 + (_rand(n, 23) - 0.5) * 6
                sprite = ("pixel_main", "pixel_accent", "pixel_hot")[int(_rand(n, 24) * 3) % 3]
                draws.append(Draw(sprite, x, y, 1.0 - 0.4 * p, (1 - p) * fade, 0.0))
    return draws


def _flake_draws(shape, w, h, t, fade):
    """Bits of her flaking off her edges, floating up and away, dissolving."""
    draws = []
    for n, age, p in _spawned(t, FLAKE_EVERY, FLAKE_LIFE):
        side = -1 if _rand(n, 41) < 0.5 else 1
        spot = _edge_point(shape, h, 0.1 + 0.75 * _rand(n, 42), side)
        if spot:
            x = spot[0] + side * p * w * 0.05 + math.sin(age * 4 + n) * 2
            y = spot[1] - p * h * 0.12
            sprite = "pixel_main" if _rand(n, 43) < 0.7 else "pixel_accent"
            alpha = min(1.0, p / 0.1) * (1 - p) ** 1.5 * 0.9 * fade
            draws.append(Draw(sprite, x, y, 0.9 - 0.5 * p, alpha, 0.0))
    return draws


Dressed = namedtuple("Dressed", "frame behind over draws glitch")


def dress(frame, now, before, age, t, height, sprites, calm=False):
    """`frame` dressed for her status `now` (crossfading from `before`,
    `age` seconds after it changed) at time `t`: her frame; what goes behind
    her and over her (canvases `height` tall as compose() makes them, or
    None); the particles painted over her (`draws`, for a look at them); and
    extra glitch. `calm`: still, no particles, no static."""
    if STYLE:
        return STYLE.dress(frame, now, before, age, t, height, sprites, calm)
    fades = _fades(now, before, age)
    if not fades:
        return Dressed(frame, None, None, [], 0.0)
    shape = _shape(frame)
    w, h = frame.size
    out, draws, glitch = frame, [], 0.0
    behind = Image.new("RGBA", (PAD_LEFT + w + PAD_RIGHT, height), (0, 0, 0, 0))
    if ("five_hour", 0) in fades:
        light = _floor_light(shape, frame, t, fades[("five_hour", 0)], calm)
        if light:
            behind.alpha_composite(light[0], (max(0, light[1]), max(0, light[2])))
    for (effect, level), fade in sorted(fades.items()):
        if effect != "aura":
            continue
        strength = aura_strength(level, t, calm) * fade
        behind.alpha_composite(_aura(shape, level, strength, (behind.width, PAD_TOP + h)))
        out = _rim(out, shape, level, strength)
        if level >= 2 and not calm:
            draws += _aura_draws(shape, w, h, level, t, fade)
        if level >= 3 and not calm and t % 3.7 > 3.7 - 0.12:
            glitch = 0.25 * fade  # overload's static
    if ("weekly", 0) in fades:
        out = _hologram(out, shape, t, fades[("weekly", 0)], calm)
        if not calm:
            draws += _flake_draws(shape, w, h, t, fades[("weekly", 0)])
    over = paint(Image.new("RGBA", behind.size, (0, 0, 0, 0)), draws, sprites) if draws else None
    return Dressed(out, behind, over, draws, glitch)


# ---------------------------------------------------------- projection
#
# How she comes and goes, as a concert hologram (`projection`):
#   intro: a teal ring lights on the floor, a beam rises from it, and she is
#     projected from her feet up behind a bright edge while teal and pink
#     bits and notes stream into her; she locks in with one glitch and a
#     sparkle pop, the beam fades, the ring winks out, her tag fades in.
#   outro: a short glitch, the beam rises again and she dissolves upward
#     into bits and notes; the beam fades and the ring winks out.
#   channel: a /clear, the same session on a fresh conversation: a quick
#     hard glitch with a bright band rolling down her.
# Everything is worked out from the time alone, like the symbols.

INTRO_S = 2.6
INTRO_LOCK_S = 1.95  # she is whole: one glitch, a sparkle pop; her symbol comes
OUTRO_S = 1.8
CHANNEL_S = 0.5
ACT_S = {"intro": INTRO_S, "outro": OUTRO_S, "channel": CHANNEL_S}
BUILD = (0.55, 1.85)  # the intro builds her up over these seconds
DISSOLVE = (0.3, 1.35)  # the outro takes her away over these
BLOCK = 4  # px: the bits she is projected in
RAGGED = 26  # px: how far bits run ahead of her building edge
BIT_EVERY = 0.035  # a bit streams in, or flies off, this often
BIT_LIFE = 0.6

# What a projection draws: her frame as projected now, the beam and ring
# behind her (a canvas as compose() makes them), sprites over her, how much
# of her name tag shows, and her glitch.
Act = namedtuple("Act", "frame behind draws tag glitch")


def _span(age, start, end):
    """0 before `start`, 1 after `end`, eased in between."""
    p = min(1.0, max(0.0, (age - start) / (end - start)))
    return p * p * (3 - 2 * p)


_noises = {}


def _bits(size):
    """An "L" image of random blocks BLOCK px wide (1..254): where she
    builds up first, bit by bit."""
    if size not in _noises:
        w, h = size
        bw, bh = -(-w // BLOCK), -(-h // BLOCK)
        small = Image.new("L", (bw, bh))
        small.putdata([1 + round(253 * _rand(i, 51)) for i in range(bw * bh)])
        _noises.clear()
        _noises[size] = small.resize((bw * BLOCK, bh * BLOCK), Image.NEAREST).crop((0, 0, w, h))
    return _noises[size]


_SHOWN = [0] + [255] * 255


def _column(values, w):
    """An "L" image `w` wide with one value per row."""
    col = Image.new("L", (1, len(values)))
    col.putdata(values)
    return col.resize((w, len(values)), Image.NEAREST)


def _projected(frame, edge, building, glow):
    """`frame` cut at row `edge` in ragged blocks: shown below it while she
    builds up (`building`), above it as she goes; the bits by the edge lit
    up mint, and (`glow`, 0..1) the part not yet there a faint teal ghost."""
    w, h = frame.size
    if building:
        ramp = [min(255, max(0, round(255 * (y - edge + RAGGED) / RAGGED))) for y in range(h)]
    else:
        ramp = [min(255, max(0, round(255 * (edge + RAGGED - y) / RAGGED))) for y in range(h)]
    shown = ImageChops.subtract(_column(ramp, w), _bits((w, h))).point(_SHOWN)
    alpha = frame.getchannel("A")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow > 0.01:
        ghost = Image.new("RGBA", (w, h), MAIN_LIGHT + (0,))
        ghost.putalpha(_scaled(ImageChops.multiply(alpha, ImageChops.invert(shown)), 0.16 * glow))
        out.alpha_composite(ghost)
    her = frame.copy()
    her.putalpha(ImageChops.multiply(alpha, shown))
    out.alpha_composite(her)
    reach = RAGGED / 2 + 6
    middle = edge - RAGGED / 2 if building else edge + RAGGED / 2
    light = [round(255 * max(0.0, 1 - abs(y - middle) / reach)) for y in range(h)]
    lit = Image.new("RGBA", (w, h), PALE + (0,))
    lit.putalpha(ImageChops.multiply(ImageChops.multiply(_column(light, w), alpha), shown))
    out.alpha_composite(lit)
    return out


def _ring(w, h, brightness, spread):
    """The projector's ring for a frame w by h: brightness 0..1, drawn
    `spread` (0..1) of its width wide."""
    if STYLE:
        return STYLE.ring(w, h, brightness, spread)
    if (w, h) not in _rings:
        _rings.clear()
        _rings[(w, h)] = _floor_ring(w, h)
    light, glow = _rings[(w, h)]
    size = (max(1, round(light.width * spread)), max(1, round(light.height * spread ** 0.5)))
    if size != light.size:
        light, glow = light.resize(size, Image.BILINEAR), glow.resize(size, Image.BILINEAR)
    out = Image.new("RGBA", size, MAIN_LIGHT + (0,))
    out.putalpha(_scaled(glow, brightness))
    top = Image.new("RGBA", size, PALE + (0,))
    top.putalpha(_scaled(light, brightness))
    out.alpha_composite(top)
    return out


_beams = {}


def _beam_profile(bw, bh):
    """The beam across its width: brighter at its sides, like a cylinder of
    light, with a few faint streaks in it."""
    key = (bw, bh)
    if key not in _beams:
        values = []
        for x in range(bw):
            u = abs(2 * x / max(1, bw - 1) - 1)
            side = math.exp(-(((u - 0.9) / 0.08) ** 2))
            streak = 0.25 if round(x / bw * 23) % 5 == 2 else 0.0
            values.append(round(255 * min(1.0, (0.35 + 0.65 * side + streak) * max(0.0, 1 - u ** 8))))
        row = Image.new("L", (bw, 1))
        row.putdata(values)
        _beams.clear()
        _beams[key] = row.resize((bw, bh), Image.NEAREST)
    return _beams[key]


def _beam(bw, bottom, top, brightness, t, edge=None):
    """The beam as an RGBA image `bw` wide and `bottom` tall: from the floor
    (its bottom) up to row `top`, fading upward, scanlines rising through it,
    and a bright line across it at row `edge`."""
    values = []
    for y in range(bottom):
        if y < top:
            values.append(0)
            continue
        rise = 0.3 + 0.7 * (y / bottom) ** 1.4
        head = min(1.0, (y - top) / 24)
        scan = 1.0 if (y + t * 46) % 7 >= 2 else 0.55
        v = 0.42 * rise * head * scan
        if edge is not None:
            v = max(v, 0.9 * max(0.0, 1 - abs(y - edge) / 3))
        values.append(round(255 * min(1.0, v * brightness)))
    out = Image.new("RGBA", (bw, bottom), MAIN_LIGHT + (0,))
    out.putalpha(ImageChops.multiply(_column(values, bw), _beam_profile(bw, bottom)))
    return out


def _stage(frame, height, ring, spread, beam, beam_top, edge, t):
    """The canvas behind her: the ring at her feet, the beam rising from it
    to `beam_top` (0..1 of the way to the window's top), its line at `edge`
    (a frame row)."""
    w, h = frame.size
    feet = _outline(frame)["feet"] or (0, 0, w, h)
    cx = PAD_LEFT + (feet[0] + feet[2]) / 2
    cy = PAD_TOP + feet[3] - h * 0.012
    canvas = Image.new("RGBA", (PAD_LEFT + w + PAD_RIGHT, height), (0, 0, 0, 0))
    if beam > 0.01:
        bw = round(w * 0.72)
        bottom = round(cy)
        img = _beam(bw, bottom, round(bottom * (1 - beam_top)), beam, t, None if edge is None else edge + PAD_TOP)
        canvas.alpha_composite(img, (round(cx - bw / 2), 0))
    if ring > 0.01 and spread > 0.01:
        img = _ring(w, h, ring, spread)
        canvas.alpha_composite(img, (round(cx - img.width / 2), max(0, round(cy - img.height / 2))))
    return canvas


def _row_point(rows, y, u):
    """A point `u` (0..1) across her at row `y`; None where she is not."""
    row = rows[min(len(rows) - 1, max(0, round(y)))]
    return None if not row else (row[0] + (row[1] - row[0]) * u, y)


def _bit_sprite(n):
    kind = _rand(n, 63)
    if kind < 0.42:
        return "pixel_main", 1.0
    if kind < 0.68:
        return "pixel_accent", 1.0
    if kind < 0.86:
        return ("spark_main" if kind < 0.77 else "spark_accent"), 0.9
    return ("note_main" if kind < 0.93 else "note_accent"), 0.6


def _edge(feet, age, span):
    """The moving edge (a frame row) `age` seconds in, from below her feet
    to above her head over the seconds `span`."""
    p = _span(age, *span)
    return feet[3] + RAGGED - p * (feet[3] - feet[1] + 2 * RAGGED)


def _incoming(shape, w, h, age):
    """Bits and notes streaming into her from all around, each reaching her
    building edge where it will be when it arrives."""
    draws = []
    first = BUILD[0] - BIT_LIFE + 0.2
    last = BUILD[1] - BIT_LIFE - 0.05
    for n, since, p in _spawned(age - first, BIT_EVERY, BIT_LIFE):
        if n < 0 or n * BIT_EVERY > last - first:
            continue
        arrives = first + n * BIT_EVERY + BIT_LIFE
        target = _row_point(shape["rows"], _edge(shape["feet"], arrives, BUILD) - RAGGED / 2, _rand(n, 61))
        if not target:
            continue
        a = 2 * math.pi * _rand(n, 62)
        reach = w * (0.45 + 0.3 * _rand(n, 64))
        sx = min(w + PAD_RIGHT - 6, max(6 - PAD_LEFT, target[0] + reach * math.cos(a)))
        sy = min(h - 6, max(6 - PAD_TOP, target[1] + reach * 1.1 * math.sin(a)))
        q = p * p
        swirl = math.sin(math.pi * p) * w * 0.05 * (1 if n % 2 else -1)
        x = sx + (target[0] - sx) * q - swirl * math.sin(a)
        y = min(h - 4, sy + (target[1] - sy) * q + swirl * math.cos(a))
        sprite, size = _bit_sprite(n)
        draws.append(Draw(sprite, x, y, size * (1.1 - 0.5 * q), min(1.0, p / 0.25), 90 * p if sprite.startswith("spark") else 0.0))
    return draws


def _outgoing(shape, w, h, age):
    """Bits and notes coming off her dissolving edge and floating up."""
    draws = []
    every, life = BIT_EVERY * 0.8, 0.9
    for n, since, p in _spawned(age - DISSOLVE[0], every, life):
        if n < 0 or n * every > DISSOLVE[1] - DISSOLVE[0]:
            continue
        start = _row_point(shape["rows"], _edge(shape["feet"], DISSOLVE[0] + n * every, DISSOLVE) + RAGGED / 2, _rand(n, 71))
        if not start:
            continue
        rise = 1 - (1 - p) ** 2
        x = start[0] + (_rand(n, 72) - 0.5) * w * 0.12 * rise + math.sin(p * 5 + n) * 3
        y = max(6 - PAD_TOP, start[1] - h * (0.16 + 0.12 * _rand(n, 73)) * rise)
        sprite, size = _bit_sprite(n + 7)
        draws.append(Draw(sprite, x, y, size * (1.0 - 0.35 * p), (1 - p) ** 1.3, 70 * p if sprite.startswith("spark") else 0.0))
    return draws


def _lock_pop(w, h, age):
    """She locks in: a ring of stage stars bursts from her head, a big
    twinkle, two notes hop off beside her."""
    draws = []
    p = (age - INTRO_LOCK_S) / 0.7
    if not 0 <= p < 1:
        return draws
    hx, hy = HEAD_AT[0] * w, HEAD_AT[1] * h
    reach = 1 - (1 - p) ** 3
    for i in range(8):
        a = math.radians(-90 + 45 * i + 20)
        r = w * (0.14 + 0.2 * reach)
        color = ("main", "accent", "gold", "accent")[i % 4]
        draws.append(Draw("star_" + color, hx + r * math.cos(a), hy + r * math.sin(a) * 0.85,
                          (0.9 - 0.5 * p) * pop(age, INTRO_LOCK_S, 0.15), 1 - p ** 3, 160 * p))
    draws.append(Draw("twinkle", hx + 0.13 * w, hy - 0.09 * h, 2.2 * pulse(p / 0.6), pulse(p / 0.6), 45 * p))
    for side, name in ((-1, "note_main"), (1, "notes_accent")):
        draws.append(Draw(name, hx + side * 0.3 * w, hy - 0.02 * h - 0.08 * h * reach, pop(age, INTRO_LOCK_S + 0.05, 0.25),
                          min(1.0, (1 - p) / 0.4), side * -14))
    return draws


def _wink(shape, h, age, start):
    """The ring winking out at `start`: one twinkle where it was."""
    p = (age - start) / 0.45
    if not 0 <= p < 1 or not shape["feet"]:
        return []
    feet = shape["feet"]
    return [Draw("twinkle", (feet[0] + feet[2]) / 2, feet[3] - h * 0.012, 1.6 * pulse(p), pulse(p), 90 * p)]


def _band(frame, y, reach, strength):
    """A bright mint band across `frame` at row `y`, on her alone."""
    w, h = frame.size
    top, bottom = max(0, int(y - reach)), min(h, int(y + reach) + 1)
    if bottom <= top or strength <= 0.01:
        return frame
    values = [round(255 * max(0.0, 1 - abs(r - y) / reach) * strength) for r in range(top, bottom)]
    shine = Image.new("RGBA", (w, bottom - top), PALE + (0,))
    shine.putalpha(ImageChops.multiply(_column(values, w), frame.getchannel("A").crop((0, top, w, bottom))))
    out = frame.copy()
    out.alpha_composite(shine, (0, top))
    return out


def _intro(frame, age, t, height):
    w, h = frame.size
    shape = _outline(frame)
    feet = shape["feet"] or (0, 0, w, h)
    ring = pop(age, 0.0, 0.4)
    beam = 1 - _span(age, 1.9, 2.35)
    edge = _edge(feet, age, BUILD)
    building = age < BUILD[1]
    her = _projected(frame, edge, True, beam * _span(age, 0.4, 0.8)) if building else frame
    # Freshly projected, she is a hologram (a teal tint, scanlines) that
    # settles into herself as she locks in.
    holo = 1 - _span(age, INTRO_LOCK_S - 0.3, INTRO_LOCK_S + 0.15)
    if holo > 0.01:
        her = _hologram(her, shape, t, holo)
    spread = 1 - _span(age, 2.05, 2.4) if age > 2.05 else min(1.0, ring)
    behind = _stage(frame, height, min(1.0, ring) * (1 + 0.6 * pulse((age - 2.0) / 0.3)), spread,
                    beam, _span(age, 0.2, 0.65), edge if BUILD[0] < age < BUILD[1] else None, t)
    draws = _incoming(shape, w, h, age) + _lock_pop(w, h, age) + _wink(shape, h, age, 2.3)
    glitch = 0.7 * max(0.0, 1 - (age - INTRO_LOCK_S) / 0.25) if age >= INTRO_LOCK_S else 0.0
    return Act(her, behind, draws, _span(age, 2.1, 2.5), glitch)


def _outro(frame, age, t, height):
    w, h = frame.size
    shape = _outline(frame)
    feet = shape["feet"] or (0, 0, w, h)
    edge = _edge(feet, age, DISSOLVE)
    her = _projected(frame, edge, False, 0.0) if age > DISSOLVE[0] else frame
    holo = _span(age, 0.05, 0.4)
    if holo > 0.01:
        her = _hologram(her, shape, t, holo)
    ring = pop(age, 0.0, 0.3)
    beam = _span(age, 0.1, 0.3) * (1 - _span(age, 1.3, 1.6))
    spread = 1 - _span(age, 1.45, 1.75) if age > 1.45 else min(1.0, ring)
    behind = _stage(frame, height, min(1.0, ring) * (1 + 0.6 * pulse((age - 1.4) / 0.3)), spread,
                    beam, _span(age, 0.1, 0.45), edge if DISSOLVE[0] < age < DISSOLVE[1] else None, t)
    draws = _outgoing(shape, w, h, age) + _wink(shape, h, age, 1.65)
    glitch = 0.85 * max(0.0, 1 - age / 0.3)
    return Act(her, behind, draws, 1 - _span(age, 0.0, 0.35), glitch)


def _channel(frame, age, t, height):
    p = min(1.0, age / CHANNEL_S)
    h = frame.height
    her = _hologram(frame, None, t, 1 - p) if p < 1 else frame
    her = _band(her, -0.1 * h + 1.2 * h * p, h * 0.06, 0.8 * (1 - p * p))
    return Act(her, None, [], 1.0, 0.95 * (1 - p) ** 1.5)


# Calm, every projection is a plain fade this long: in, out, or a dip.
CALM_FADE_S = 0.4


def _calm(kind, frame, age):
    p = min(1.0, max(0.0, age / CALM_FADE_S))
    if kind == "channel":
        return Act(faded(frame, 1 - 0.6 * pulse(p)), None, [], 1.0, 0.0)
    shown = p if kind == "intro" else 1 - p
    return Act(faded(frame, shown), None, [], shown, 0.0)


def projection(kind, frame, age, t, height, calm=False):
    """Act for the `kind` of projection ("intro", "outro", "channel"),
    `age` seconds in, at time `t`, over canvases `height` tall; a plain
    fade when `calm`."""
    if calm:
        return _calm(kind, frame, age)
    if STYLE:
        return STYLE.projection(kind, frame, age, t, height)
    return {"intro": _intro, "outro": _outro, "channel": _channel}[kind](frame, age, t, height)


def act_length(kind, calm=False):
    """How long a projection of `kind` plays."""
    return CALM_FADE_S if calm else (STYLE.ACT_S if STYLE else ACT_S)[kind]


def lock_in(calm=False):
    """How far into the intro she is whole: her symbol and status wait for it."""
    return CALM_FADE_S if calm else STYLE.INTRO_LOCK_S if STYLE else INTRO_LOCK_S


def faded(img, amount):
    """`img` at `amount` (0..1) of its opacity, its size kept (the window
    keeps its size as the tag fades)."""
    if img is None or amount >= 0.99:
        return img
    out = img.copy()
    out.putalpha(_scaled(img.getchannel("A"), amount))
    return out


# ---------------------------------------------------------- handling
#
# Picked up and carried (a drag), then set down:
#   pick up: a pink "!" pops, a little glitch, and a small projector ring
#     under her boots comes along with her.
#   carry: she swings from where she was grabbed, like a plush held up:
#     leaning back against the motion (`Sway`), swaying back when it stops;
#     fast, she smears into teal and pink ghosts behind her (`trail`) and
#     bits and notes shake loose (`Shaken`).
#   set down: a squash and bounce onto the ring (`squash`), the ring flashes
#     and ripples out, a few sparkles; then the ring goes and her symbol
#     comes back.
# Unlike the rest, a carry has state (how she swings depends on how she was
# moved), kept in Sway and Shaken.

DRAG_PAD = 90  # px of room around the window while she swings
TILT_MAX = 16  # degrees
TILT_PER_SPEED = 0.02  # degrees per px/s
GRAB_GLITCH_S = 0.15
LAND_S = 0.6
TRAIL_FROM = 150  # px/s: slower than this leaves no ghosts
SHAKE_FROM = 400  # px/s: faster than this shakes bits loose
SHAKE_LIFE = 0.55


class Sway:
    """Her tilt while carried (degrees, counterclockwise): a damped spring
    pulled toward leaning back against the motion, so a flick swings her
    and she sways back when it stops. `lever` is 1 when she hangs below the
    grip, -1 when held up from below it."""

    def __init__(self):
        self.angle = 0.0
        self.spin = 0.0
        self.vx = 0.0

    def step(self, dt, vx, lever=1.0):
        dt = min(dt, 0.1)
        while dt > 0:
            h = min(dt, 1 / 120)
            dt -= h
            self.vx += (vx - self.vx) * min(1.0, h * 12)
            target = max(-TILT_MAX, min(TILT_MAX, -self.vx * TILT_PER_SPEED * lever))
            self.spin += (60 * (target - self.angle) - 4.5 * self.spin) * h
            self.angle += self.spin * h
        return self.angle

    def settled(self):
        return abs(self.angle) < 0.3 and abs(self.spin) < 3 and abs(self.vx) < 20


def lever(frame, grip):
    """How she hangs from `grip` (a point on her frame): 1 held by her head
    or body, easing to -1 held up by her boots."""
    return max(-1.0, min(1.0, (frame.height * 0.6 - grip[1]) / (frame.height * 0.2)))


class Shaken:
    """Bits and notes shaken loose from her edges by a fast carry: left
    behind (they move against her motion), falling, fading."""

    def __init__(self):
        self.bits = []  # [born, x, y, vx, vy, sprite, size, n]
        self.debt = 0.0
        self.count = 0

    def step(self, dt, t, vx, vy, frame):
        dt = min(dt, 0.1)
        for b in self.bits:
            b[4] += 500 * dt  # they fall
            b[1] += b[3] * dt
            b[2] += b[4] * dt
        self.bits = [b for b in self.bits if t - b[0] < SHAKE_LIFE]
        speed = math.hypot(vx, vy)
        if speed < SHAKE_FROM:
            self.debt = 0.0
            return
        self.debt += (speed - SHAKE_FROM) * dt / 25
        rows = _outline(frame)["rows"]
        while self.debt >= 1:
            self.debt -= 1
            n = self.count = self.count + 1
            side = -1 if vx > 0 else 1  # the side she trails
            row = rows[min(len(rows) - 1, round(frame.height * (0.1 + 0.75 * _rand(n, 81))))]
            if not row:
                continue
            x = row[0] if side < 0 else row[1]
            sprite, size = _bit_sprite(n + 3)
            self.bits.append([t, x, frame.height * (0.1 + 0.75 * _rand(n, 81)), -0.35 * vx + (_rand(n, 82) - 0.5) * 80,
                              -0.35 * vy - 60 - 60 * _rand(n, 83), sprite, size, n])

    def draws(self, t):
        out = []
        for born, x, y, _, _, sprite, size, n in self.bits:
            p = (t - born) / SHAKE_LIFE
            out.append(Draw(sprite, x, y, size * (1 - 0.3 * p), (1 - p) ** 1.2, 200 * p if sprite.startswith("spark") else 0.0))
        return out


def _put(out, img, x, y):
    """`img` onto `out` with its top left at (x, y), clipped to `out`."""
    x, y = round(x), round(y)
    if x + img.width <= 0 or y + img.height <= 0 or x >= out.width or y >= out.height:
        return
    out.alpha_composite(img, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


def trail(behind, frame, vx, vy, height):
    """`behind` (a canvas, or None) with her ghosts trailing her motion: a
    teal one, a fainter pink one further back."""
    speed = math.hypot(vx, vy)
    if speed < TRAIL_FROM:
        return behind
    out = behind.copy() if behind else Image.new("RGBA", (PAD_LEFT + frame.width + PAD_RIGHT, height), (0, 0, 0, 0))
    reach = min(18.0, speed * 0.012)
    dx, dy = -vx / speed * reach, -vy / speed * reach
    strength = min(0.5, (speed - TRAIL_FROM) / 1500)
    _put(out, _ghost(frame, ACCENT_LIGHT, strength * 0.6), PAD_LEFT + 2 * dx, PAD_TOP + 2 * dy)
    _put(out, _ghost(frame, MAIN_LIGHT, strength), PAD_LEFT + dx, PAD_TOP + dy)
    return out


def carried_ring(behind, frame, height, held, landed):
    """`behind` (a canvas, or None) with the small ring under her boots that
    she is carried on: lit as she is picked up (`held` s ago), flashing and
    rippling out as she lands (`landed` s ago, or None), then gone."""
    w, h = frame.size
    feet = _outline(frame)["feet"]
    if not feet:
        return behind
    if landed is None:
        bright = pop(held, 0.0, 0.25) * (0.75 + 0.1 * math.sin(held * 9))
        rings = [(bright, 0.7)]
    else:
        p = landed / LAND_S
        flash = 0.85 + 0.6 * pulse(p / 0.4)
        rings = [(flash * (1 - _span(landed, LAND_S * 0.55, LAND_S)), 0.7)]
        if p < 1:
            rings.append(((1 - p) ** 2 * 0.9, 0.7 + 0.75 * (1 - (1 - p) ** 2)))
    out = behind.copy() if behind else Image.new("RGBA", (PAD_LEFT + w + PAD_RIGHT, height), (0, 0, 0, 0))
    cx = PAD_LEFT + (feet[0] + feet[2]) / 2
    cy = PAD_TOP + feet[3] - h * 0.012
    for bright, spread in rings:
        if bright > 0.01:
            img = _ring(w, h, min(1.0, bright), spread)
            _put(out, img, cx - img.width / 2, cy - img.height / 2)
    return out


def squash(frame, landed):
    """`frame` squashed onto her feet as she lands (`landed` s ago), then
    bouncing back: same size, feet kept where they are."""
    k = 0.065 * math.exp(-6 * landed) * math.cos(18 * landed)
    if abs(k) < 0.004:
        return frame
    w, h = frame.size
    feet = _outline(frame)["feet"] or (0, 0, w, h)
    sx, sy = 1 + k * 0.6, 1 - k
    small = frame.resize((max(1, round(w * sx)), max(1, round(h * sy))), Image.BILINEAR)
    cx = (feet[0] + feet[2]) / 2
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    _put(out, small, cx - cx * sx, feet[3] - feet[3] * sy)
    return out


def held_draws(w, h, held, landed):
    """The "!" popping as she is picked up (going as she lands), and the
    sparkles of her landing."""
    draws = []
    sx, sy = SYMBOL_AT[0] * w, SYMBOL_AT[1] * h
    fade = 1.0 if landed is None else max(0.0, 1 - landed / 0.2)
    if fade > 0:
        wobble = 14 * math.sin(held * 10) * math.exp(-held * 3)
        draws.append(Draw("exclaim", sx, sy - 3 * pulse(held / 0.3), pop(held, 0.0, 0.25), fade, wobble))
    if landed is not None and landed < LAND_S:
        p = landed / LAND_S
        for i, (u, color) in enumerate(((-0.33, "main"), (-0.2, "accent"), (0.2, "main"), (0.33, "accent"))):
            x = w * (0.5 + u * (1 + 0.5 * p))
            y = h * (0.965 - 0.07 * (1 - (1 - p) ** 2)) - 6 * (i % 2)
            draws.append(Draw("spark_" + color, x, y, 1.2 * pulse(p / 0.8), pulse(p / 0.8), 120 * p))
    return draws


def tilt(image, pivot, angle):
    """`image` (a canvas as compose() makes) in DRAG_PAD more room on every
    side, turned `angle` degrees about `pivot` (a point on it)."""
    out = Image.new("RGBA", (image.width + 2 * DRAG_PAD, image.height + 2 * DRAG_PAD), (0, 0, 0, 0))
    out.alpha_composite(image, (DRAG_PAD, DRAG_PAD))
    if abs(angle) < 0.15:
        return out
    return out.rotate(angle, Image.BILINEAR, center=(pivot[0] + DRAG_PAD, pivot[1] + DRAG_PAD))


class Carry:
    """One carry, from the moment a drag picks her up (`grip`: where, on her
    frame) until she has landed and stopped swaying. `step` it each tick
    with the pointer's velocity, `drop` it on release, and `draw` her."""

    def __init__(self, grip, t, calm=False):
        self.calm = calm  # no ghosts trailing her, no bits shaken loose
        self.grip = grip
        self.since = t
        self.landed = None
        self.last = t
        self.vx = self.vy = 0.0
        self.sway = Sway()
        self.shaken = Shaken()

    def drop(self, t):
        if self.landed is None:
            self.landed = t

    def step(self, t, vx, vy, frame):
        dt, self.last = t - self.last, t
        if self.landed is not None:
            vx = vy = 0.0
        self.vx, self.vy = vx, vy
        self.sway.step(dt, vx, lever(frame, self.grip))
        if not self.calm:
            self.shaken.step(dt, t, vx, vy, frame)

    def over(self, t):
        """Landed, still, and nothing left in the air."""
        return self.landed is not None and t - self.landed >= LAND_S and self.sway.settled() and not self.shaken.bits

    def glitch(self, t):
        """A blink of glitch as she is picked up and as she lands: where the
        overlay swaps her held pose in and out."""
        landed = 0.0 if self.landed is None else max(0.0, 1 - (t - self.landed) / GRAB_GLITCH_S)
        return 0.5 * max(0.0, 1 - (t - self.since) / GRAB_GLITCH_S, landed)

    def draw(self, frame, behind, over, symbol, sprites, tag, height, t):
        """Her canvas, DRAG_PAD larger on every side than compose() makes it:
        `frame` (dressed, glitched) on the little ring with her ghosts,
        `behind` and `over` from her status, the "!" (or, landing, her mood's
        `symbol` draws coming back), turned as she swings, and the bits
        shaken loose."""
        held = t - self.since
        landed = None if self.landed is None else t - self.landed
        w, h = frame.size
        if not self.calm:
            behind = trail(behind, frame, self.vx, self.vy, height)
        behind = carried_ring(behind, frame, height, held, landed)
        draws = held_draws(w, h, held, landed)
        if landed is not None:
            frame = squash(frame, landed)
            k = pop(landed, 0.25, 0.35)
            draws += [d._replace(scale=d.scale * k) for d in symbol] if k > 0.01 else []
        image = compose(frame, draws, sprites, tag, behind, over)
        image = tilt(image, (self.grip[0] + PAD_LEFT, self.grip[1] + PAD_TOP), self.sway.angle)
        return paint(image, self.shaken.draws(t), sprites, (PAD_LEFT + DRAG_PAD, PAD_TOP + DRAG_PAD))


# ---------------------------------------------------------- size
#
# The pads are drawn for her at BASE_HEIGHT; at another size they grow or
# shrink with her, so symbols, aura and beam keep their room. One mascot per
# process: the overlay sets her size here.

_BASE_PADS = {name: globals()[name] for name in ("PAD_TOP", "PAD_RIGHT", "PAD_LEFT", "BEAM_PAD", "DRAG_PAD", "AURA_RADIUS",
                                                     "MAGIC_BOX")}


def scale_to(height):
    """Fits the pads to her at `height` px."""
    k = height / BASE_HEIGHT
    globals().update({name: max(1, round(v * k)) for name, v in _BASE_PADS.items()})
