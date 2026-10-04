"""The gothic style: a sleepy vampire doll's effects (Yunseul's), in place
of Miku's concert. Same roles, her own shapes and motion:

  shapes   notes are bats (flapping: `bat_<tint>_<up|mid|down>`), stars
           are roses, silver cross glints and gold crescents, hearts are
           stitched, bits are rose petals, bubbles are lace, the storm
           cloud pouts, a broken note is a cracked heart.
  moods    thinking: a lace bubble, gem dots lighting in turn. working: a
           needle sewing a cross-stitch seam, bats fluttering off it.
           waiting: a lace speech bubble, a hopping "?", a bat peeking.
           worried: a sweat drop and a trembling little ghost. sleepy: a
           crescent moon with a bat asleep under it, z's. happy: a burst
           of bats, roses, stitched hearts. error: the grumpy cloud
           dropping cracked hearts.
  status   context: moonlight, then crimson with petals and bats rising,
           then a blood moon behind her beating like a heart. The 5-hour
           limit: candles guttering at her feet. The weekly one: she
           fades into a ghost from her feet up, wisps rising.
  glitch   ghostly: silver and crimson afterimages, an ectoplasm ripple.
  coming   a summoning circle traces itself on the floor, candles light,
  going    mist rises, bats swirl in and she forms out of smoke; she
           leaves in a burst of bats. A /clear blows the candles out.
  finisher bats spiral into her heart hands, a stitched heart beats
           there; she fires hollow stitched hearts and a swarm of bats,
           crimson rays and a shockwave behind her, the call on a banner
           with bat wings; petals drift down after.
  call     a glint flies to the pointer trailing petals and bats, roses
           burst there, two bats and a stitched heart circle it.
  messages a bat carries a letter sealed in crimson wax: it flutters by
           her head, shaking the letter, while she has waited on you; it
           swoops in with a prompt sent from elsewhere and drops the letter,
           which flutters down and fades; a letter waits at her feet with
           what happened while you were away.

Everything takes its colors from the look (`fx.MAIN`...) when drawn, so a
character's theme recolors it; positions are shares of her frame, as in
effects.py.
"""

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import effects as fx

pop, pulse, Draw, _rand = fx.pop, fx.pulse, fx.Draw, fx._rand

# Where things stand on her frame (her art shares Miku's framing).
SYMBOL_AT = fx.SYMBOL_AT
HEAD_AT = fx.HEAD_AT
SHINE_AT = fx.SHINE_AT
DROP_AT = fx.DROP_AT
DOZE_AT = fx.DOZE_AT
GHOST_AT = (0.13, 0.21)  # worried's little ghost, by her other temple
MOON_AT = (0.17, 0.035)  # sleepy's moon, up left of her head (her z's rise right)
SEAM = ((0.79, 0.235), (1.05, 0.125))  # working's seam, from its first stitch to its last
HANDS_AT = (0.51, 0.345)  # her heart hands, on her beam pose's frame

FLAP_HZ = 6.0  # wing beats a second
WINGS = ("up", "mid", "down", "mid")


def _bat(t, k, tint="main", hz=FLAP_HZ):
    """The sprite of bat `k` at time `t`, mid-flap (each its own beat)."""
    return f"bat_{tint}_{WINGS[int((t * hz + 0.37 * k) * 4) % 4]}"


# ---------------------------------------------------------- shapes


def _px(height):
    k = height / fx.BASE_HEIGHT
    return lambda v: max(1, round(v * k))


def _scallop(d, points, r, fill=255):
    for x, y in points:
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _wing(sx, sy, n, angle, side):
    """A bat wing's polygon from the shoulder (sx, sy), `n` px a unit,
    lifted `angle` degrees, on `side` (1 right, -1 left): a curved top to
    the tip, a scalloped trailing edge back."""
    pts = [(0, -0.02), (0.09, -0.15), (0.24, -0.21), (0.42, -0.15), (0.38, -0.02), (0.32, -0.05), (0.27, 0.07),
           (0.2, 0.02), (0.13, 0.12), (0.06, 0.08), (0.0, 0.12)]
    a = math.radians(angle)
    out = []
    for x, y in pts:
        rx, ry = x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)
        out.append((sx + side * rx * n, sy + ry * n))
    return out


def _bat_shape(size, angle):
    """A bat's mask, `size` px square (SUPER large): round body and head,
    pointed ears, wings lifted `angle` degrees."""
    S = fx.SUPER
    n = size * S
    shape = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(shape)
    cx, cy = n * 0.5, n * 0.52
    d.ellipse((cx - n * 0.1, cy - n * 0.08, cx + n * 0.1, cy + n * 0.17), fill=255)  # body
    d.ellipse((cx - n * 0.09, cy - n * 0.17, cx + n * 0.09, cy + n * 0.01), fill=255)  # head
    for side in (-1, 1):
        d.polygon([(cx + side * n * 0.03, cy - n * 0.13), (cx + side * n * 0.085, cy - n * 0.25), (cx + side * n * 0.09, cy - n * 0.09)],
                  fill=255)
        d.polygon(_wing(cx + side * n * 0.07, cy - n * 0.02, n * 0.98, angle, side), fill=255)
    return shape


def _bat_img(size, ink, angle):
    """A bat in `ink` with two white eyes and a tiny fang."""
    S = fx.SUPER
    shape = _bat_shape(size, angle)
    out = Image.new("RGBA", shape.size, ink + (255,))
    out.putalpha(shape)
    n = size * S
    d = ImageDraw.Draw(out)
    cx, cy = n * 0.5, n * 0.52
    for side in (-1, 1):
        r = n * 0.022
        d.ellipse((cx + side * n * 0.04 - r, cy - n * 0.085 - r, cx + side * n * 0.04 + r, cy - n * 0.085 + r), fill=fx.WHITE + (255,))
    d.polygon([(cx + n * 0.012, cy - n * 0.03), (cx + n * 0.042, cy - n * 0.03), (cx + n * 0.027, cy + n * 0.0)], fill=fx.WHITE + (255,))
    return fx._down(out)


def _hanging_bat(size, ink):
    """A bat asleep upside down, wrapped in its wings: feet up top, ears
    down, a closed eye's curve."""
    S = fx.SUPER
    w, h = size * 0.62, size
    img = fx._canvas(round(w), round(h))
    d = ImageDraw.Draw(img)
    W, H = img.size
    shade = tuple(round(c * 0.75) for c in ink)
    d.line([(W * 0.42, 0), (W * 0.45, H * 0.12)], fill=ink + (255,), width=max(S, round(W * 0.06)))
    d.line([(W * 0.58, 0), (W * 0.55, H * 0.12)], fill=ink + (255,), width=max(S, round(W * 0.06)))
    d.ellipse((W * 0.12, H * 0.08, W * 0.88, H * 0.82), fill=ink + (255,))  # wrapped wings
    d.ellipse((W * 0.26, H * 0.62, W * 0.74, H * 0.94), fill=ink + (255,))  # head, at the bottom
    for side in (-1, 1):
        d.polygon([(W * (0.5 + side * 0.1), H * 0.9), (W * (0.5 + side * 0.24), H), (W * (0.5 + side * 0.22), H * 0.8)], fill=ink + (255,))
    d.arc((W * 0.2, H * 0.12, W * 0.62, H * 0.7), 200, 340, fill=shade + (255,), width=max(S, round(W * 0.05)))  # a wing's fold
    d.arc((W * 0.38, H * 0.12, W * 0.8, H * 0.7), 200, 340, fill=shade + (255,), width=max(S, round(W * 0.05)))
    for side in (-1, 1):  # closed eyes, upside down: little arches
        x = W * (0.5 + side * 0.1)
        d.arc((x - W * 0.06, H * 0.74, x + W * 0.06, H * 0.82), 180, 360, fill=fx.WHITE + (255,), width=max(S, round(W * 0.035)))
    return fx._down(img)


def _ghost(w, h, line):
    """A little sheet ghost: a dome, a wavy hem, dark oval eyes, blush."""
    S = fx.SUPER
    shape, d = fx._mask(w, h)
    d.ellipse((S, S, (w + 1) * S, (w * 0.95 + 1) * S), fill=255)
    d.rectangle((S, (w * 0.48 + 1) * S, (w + 1) * S, (h * 0.82 + 1) * S), fill=255)
    for i in range(4):
        cx = (w * (i + 0.5) / 4 + 1) * S
        r = w / 8 * S
        d.ellipse((cx - r, (h * 0.82 + 1) * S - r, cx + r, (h * 0.82 + 1) * S + r), fill=255 if i % 2 == 0 else 0)
    out = fx._filled(shape, fx.WHITE, fx.PALE, fx.MAIN_SHADE, line)
    pen = ImageDraw.Draw(out)
    for side in (-1, 1):
        x = (w * (0.5 + side * 0.17) + 1) * S
        pen.ellipse((x - w * 0.07 * S, (h * 0.33 + 1) * S, x + w * 0.07 * S, (h * 0.47 + 1) * S), fill=fx.MAIN_SHADE + (255,))
        pen.ellipse((x - w * 0.12 * S, (h * 0.5 + 1) * S, x + w * 0.04 * S * side + w * 0.0 * S, (h * 0.56 + 1) * S),
                    fill=fx.ACCENT_SOFT + (150,))
    pen.ellipse(((w * 0.46 + 1) * S, (h * 0.5 + 1) * S, (w * 0.54 + 1) * S, (h * 0.6 + 1) * S), fill=fx.MAIN_SHADE + (255,))
    return fx._down(out)


def _rose(size, ink, shade, line):
    """A rose from above: a round bloom fading from her soft accent, its
    petals' curls in a spiral, two dark leaves."""
    S = fx.SUPER
    shape, d = fx._mask(size, size)
    n = size * S
    c = (size + 2) * S / 2
    leaves = Image.new("RGBA", shape.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(leaves)
    for a in (-28, 208):  # pointed leaves peeking out low on either side
        r = math.radians(a)
        tip = (c + math.cos(r) * n * 0.5, c - math.sin(r) * n * 0.5)
        base = (c + math.cos(r) * n * 0.2, c - math.sin(r) * n * 0.2)
        side = (-math.sin(r) * n * 0.09, -math.cos(r) * n * 0.09)
        mid = ((tip[0] + base[0]) / 2, (tip[1] + base[1]) / 2)
        ld.polygon([base, (mid[0] + side[0], mid[1] + side[1]), tip, (mid[0] - side[0], mid[1] - side[1])], fill=fx.MAIN_SHADE + (255,))
    for i in range(6):
        a = math.tau * i / 6
        px_, py_ = c + math.cos(a) * n * 0.12, c + math.sin(a) * n * 0.12
        d.ellipse((px_ - n * 0.18, py_ - n * 0.18, px_ + n * 0.18, py_ + n * 0.18), fill=255)
    bloom = fx._filled(shape, fx.ACCENT_SOFT, ink, shade, line)
    pen = ImageDraw.Draw(bloom)
    width = max(S, round(n * 0.05))
    for k, (r, start) in enumerate(((0.24, 200), (0.17, 30), (0.11, 250), (0.05, 60))):
        pen.arc((c - n * r, c - n * r, c + n * r, c + n * r), start, start + 230, fill=shade + (255,), width=width)
    pen.ellipse((c - n * 0.17, c - n * 0.22, c - n * 0.09, c - n * 0.14), fill=fx.WHITE + (220,))
    leaves.alpha_composite(bloom)
    return fx._down(leaves)


def _petal(size, ink):
    """A rose petal: a rounded teardrop with a little shine."""
    S = fx.SUPER
    shape, d = fx._mask(size, size)
    n = size * S
    d.ellipse((S, n * 0.25 + S, n + S, n + S), fill=255)
    d.polygon([(S + n * 0.06, n * 0.6 + S), (n * 0.5 + S, S), (n * 0.94 + S, n * 0.6 + S)], fill=255)
    deep = tuple(round(c * 0.72) for c in ink)
    out = fx._filled(shape, ink, deep, deep, 0.01)
    ImageDraw.Draw(out).ellipse((n * 0.3, n * 0.5, n * 0.5, n * 0.7), fill=fx.WHITE + (200,))
    return fx._down(out)


def _glint(size, color):
    """A tall four-point glint, like candlelight catching silver."""
    img = fx._canvas(size, size)
    c, k = size * fx.SUPER / 2, size * fx.SUPER
    v, hz, waist = k * 0.5, k * 0.3, k * 0.07
    ImageDraw.Draw(img).polygon([(c, c - v), (c + waist, c - waist), (c + hz, c), (c + waist, c + waist), (c, c + v),
                                 (c - waist, c + waist), (c - hz, c), (c - waist, c - waist)], fill=color)
    return fx._down(img)


def _gem_glint(size, ink):
    out = _glint(size, ink)
    core = _glint(max(1, size // 2), fx.WHITE)
    out.alpha_composite(core, ((out.width - core.width) // 2, (out.height - core.height) // 2))
    return out


def _crescent(size, ink, face=False):
    """A crescent moon, pale and soft; with `face`, asleep (a closed eye's
    curve and a blush)."""
    S = fx.SUPER
    shape, d = fx._mask(size, size)
    n = size * S
    d.ellipse((S, S, n + S, n + S), fill=255)
    d.ellipse((S + n * 0.34, S - n * 0.12, n * 1.22 + S, n * 0.82 + S), fill=0)
    light = tuple(min(255, round(c + (255 - c) * 0.55)) for c in ink)
    out = fx._filled(shape, light, ink, tuple(round(c * 0.7) for c in ink), max(0.6, size / 26))
    if face:
        pen = ImageDraw.Draw(out)
        pen.arc((n * 0.14, n * 0.42, n * 0.3, n * 0.56), 20, 160, fill=tuple(round(c * 0.5) for c in ink) + (255,), width=max(S, round(n * 0.03)))
        pen.ellipse((n * 0.13, n * 0.6, n * 0.27, n * 0.67), fill=fx.ACCENT_SOFT + (150,))
    return fx._down(out)


def _stitches(pen, pts, n, width, color):
    """Cross stitches along a polyline `pts` (SUPER px), `n` of them."""
    segs = list(zip(pts, pts[1:]))
    total = sum(math.dist(a, b) for a, b in segs)
    for i in range(n):
        u = (i + 0.5) / n * total
        for a, b in segs:
            L = math.dist(a, b)
            if u <= L:
                x, y = a[0] + (b[0] - a[0]) * u / L, a[1] + (b[1] - a[1]) * u / L
                nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
                s = width * 2.2
                pen.line([(x - nx * s, y - ny * s), (x + nx * s, y + ny * s)], fill=color, width=round(width))
                break
            u -= L
    pen.line(pts, fill=color, width=max(1, round(width * 0.6)))


def _stitched_heart(size, ink, rim, line):
    """A plump heart, soft at its top, a stitched seam across it, a shine."""
    S = fx.SUPER
    n = size * S
    out = fx._filled(fx._heart_shape(size), fx.ACCENT_SOFT, ink, rim, line)
    pen = ImageDraw.Draw(out)
    _stitches(pen, [(n * 0.62, n * 0.22), (n * 0.54, n * 0.46), (n * 0.64, n * 0.7)], 3, max(S, n * 0.035), fx.WHITE + (255,))
    pen.ellipse((n * 0.2, n * 0.2, n * 0.32, n * 0.32), fill=fx.WHITE + (255,))
    return fx._down(out)


def _cracked_heart(size, line):
    """A heart in her storm colors with a zigzag crack, two stitches
    trying to hold it."""
    S = fx.SUPER
    n = size * S
    shape = fx._heart_shape(size)
    crack = [(n * 0.52, n * 0.2), (n * 0.44, n * 0.38), (n * 0.58, n * 0.52), (n * 0.46, n * 0.7), (n * 0.53, n * 0.95)]
    ImageDraw.Draw(shape).line(crack, fill=0, width=max(S, round(n * 0.07)))
    out = fx._filled(shape, fx.STORM_DEEP, fx.STORM_SHADE, fx.STORM_SHADE, line)
    pen = ImageDraw.Draw(out)
    for y in (0.33, 0.6):
        pen.line([(n * 0.4, n * y), (n * 0.62, n * (y + 0.04))], fill=fx.WHITE + (255,), width=max(S, round(n * 0.035)))
    pen.ellipse((n * 0.2, n * 0.2, n * 0.3, n * 0.3), fill=fx.WHITE + (200,))
    return fx._down(out)


def _hollow_stitched(size, band):
    """The finisher's heart: hollow, `band` px thick, her accent fading to
    soft, white running stitches around its middle, a shine."""
    S = fx.SUPER
    shape = fx._heart_shape(size)
    inner = fx._shrink(shape, 2 * round(band * S / 2) + 1)
    hollow = ImageChops.subtract(shape, inner)
    out = fx._filled(hollow, fx.ACCENT_SOFT, fx.ACCENT, fx.ACCENT_SHADE, max(1, band / 4))
    mid = fx._shrink(shape, 2 * round(band * S / 4) + 1)
    seam = ImageChops.subtract(mid, fx._shrink(mid, 2 * round(S * max(1, band / 7)) + 1))
    dashes = Image.new("L", shape.size, 0)
    dd = ImageDraw.Draw(dashes)
    c = (shape.width / 2, shape.height / 2)
    for i in range(0, 40, 2):
        dd.pieslice((c[0] - shape.width, c[1] - shape.height, c[0] + shape.width, c[1] + shape.height), i * 9, i * 9 + 5, fill=255)
    white = Image.new("RGBA", shape.size, fx.WHITE + (0,))
    white.putalpha(ImageChops.multiply(seam, dashes))
    out.alpha_composite(white)
    n = size * S
    ImageDraw.Draw(out).ellipse((n * 0.14, n * 0.17, n * 0.2, n * 0.23), fill=fx.WHITE + (255,))
    return fx._down(out)


def _lace(w, h, line, tail=False):
    """A lace bubble: an oval with a scalloped edge, white fading to her
    pale, a rim and a row of eyelets; with `tail`, a speech bubble's tail
    at its lower left, toward her."""
    S = fx.SUPER
    shape, d = fx._mask(w, h)
    r = max(1.2, min(w, h) * 0.1)
    cx, cy, rx, ry = (w / 2 + 1) * S, (h * (0.42 if tail else 0.5) + 1) * S, (w / 2 - r) * S, (h * (0.4 if tail else 0.5) - r) * S
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    count = max(8, round(math.pi * (rx + ry) / (1.55 * r * S)))
    _scallop(d, [(cx + rx * math.cos(math.tau * i / count), cy + ry * math.sin(math.tau * i / count)) for i in range(count)], r * S)
    if tail:
        d.polygon([(w * 0.2 * S, h * 0.66 * S), (w * 0.06 * S, (h + 0.6) * S), (w * 0.46 * S, h * 0.74 * S)], fill=255)
    out = fx._filled(shape, fx.WHITE, fx.PALE, fx.MAIN_SHADE, line)
    pen = ImageDraw.Draw(out)
    if w > 20:
        dot = max(S * 0.5, r * S * 0.28)
        for i in range(count):
            a = math.tau * (i + 0.5) / count
            x, y = cx + (rx - r * S * 0.2) * math.cos(a), cy + (ry - r * S * 0.2) * math.sin(a)
            pen.ellipse((x - dot, y - dot, x + dot, y + dot), fill=fx.DIM + (160,))
        pen.ellipse((w * 0.22 * S, h * 0.2 * S, w * 0.32 * S, h * 0.3 * S), fill=fx.WHITE + (255,))
    return fx._down(out)


def _gem(size, ink):
    """A round gem: her ink with a shine."""
    S = fx.SUPER
    img = fx._canvas(size, size)
    n = size * S
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, n - 1, n - 1), fill=ink + (255,))
    d.ellipse((n * 0.22, n * 0.18, n * 0.48, n * 0.44), fill=fx.WHITE + (230,))
    return fx._down(img)


def _cross_stitch(size, color):
    """One cross stitch: two strokes of thread, their light side up."""
    S = fx.SUPER
    img = fx._canvas(size, size)
    d = ImageDraw.Draw(img)
    n = size * S
    m, wd = n * 0.18, max(S, round(n * 0.2))
    light = tuple(min(255, c + 70) for c in color)
    for a, b in (((m, m), (n - m, n - m)), ((n - m, m), (m, n - m))):
        d.line([a, b], fill=color + (255,), width=wd)
        for p in (a, b):
            d.ellipse((p[0] - wd / 2, p[1] - wd / 2, p[0] + wd / 2, p[1] + wd / 2), fill=color + (255,))
    d.line([(n - m, m), (m, n - m)], fill=light + (255,), width=max(1, wd // 3))
    return fx._down(img)


def _needle(length, line):
    """A silver needle pointing down-left, its eye open."""
    S = fx.SUPER
    w = max(3, length * 0.16)
    img = fx._canvas(round(length), round(length))
    d = ImageDraw.Draw(img)
    n, k = length * S, w * S / 2
    tip, back = (n * 0.06, n * 0.94), (n * 0.94, n * 0.06)
    ux, uy = (back[0] - tip[0]) / n / 1.25, (back[1] - tip[1]) / n / 1.25
    px_, py_ = -uy, ux
    body = [tip, (back[0] - ux * k * 2 + px_ * k, back[1] - uy * k * 2 + py_ * k), (back[0], back[1]),
            (back[0] - ux * k * 2 - px_ * k, back[1] - uy * k * 2 - py_ * k)]
    d.polygon(body, fill=fx.MAIN_SHADE + (255,))
    inner = [(tip[0] + ux * line * S * 2, tip[1] + uy * line * S * 2)] + [(x - ux * line * S * 0.8, y - uy * line * S * 0.8) for x, y in body[1:]]
    d.polygon(inner, fill=fx.MAIN_LIGHT + (255,))
    ex, ey = back[0] - ux * k * 2.4, back[1] - uy * k * 2.4
    d.ellipse((ex - k * 0.45, ey - k * 0.45, ex + k * 0.45, ey + k * 0.45), fill=(0, 0, 0, 0))
    return fx._down(img)


def _candle(w, h, line):
    """A little candle: cream wax, her accent's wax dripping from the top,
    a wick (its flame is its own sprite)."""
    S = fx.SUPER
    shape, d = fx._mask(w, h)
    d.rounded_rectangle((S, h * 0.18 * S + S, (w + 1) * S, (h + 1) * S), radius=w * 0.18 * S, fill=255)
    out = fx._filled(shape, fx.WHITE, fx.PALE, fx.MAIN_SHADE, line)
    pen = ImageDraw.Draw(out)
    top = (h * 0.18 + 1) * S
    pen.rounded_rectangle((S, top, (w + 1) * S, top + w * 0.4 * S), radius=w * 0.18 * S, fill=fx.ACCENT + (255,))
    for x, drip in ((0.25, 0.32), (0.62, 0.22)):
        pen.rounded_rectangle(((w * x + 1) * S - w * 0.1 * S, top, (w * x + 1) * S + w * 0.1 * S, top + h * drip * S),
                              radius=w * 0.1 * S, fill=fx.ACCENT + (255,))
    pen.line([((w / 2 + 1) * S, S), ((w / 2 + 1) * S, top)], fill=fx.MAIN_SHADE + (255,), width=max(S, round(w * 0.1 * S)))
    return fx._down(out)


def _flame(w, h):
    """A candle flame: a soft teardrop, gold around a white heart."""
    S = fx.SUPER
    img = fx._canvas(w, h)
    d = ImageDraw.Draw(img)
    W, H = w * S, h * S
    for k, color in ((1.0, fx.GOLD), (0.55, fx.WHITE)):
        cx, r = W / 2, W / 2 * k
        cy = H - r - (1 - k) * H * 0.1
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,))
        d.polygon([(cx - r * 0.95, cy - r * 0.3), (cx, H - (H - (1 - k) * H * 0.15) * 1.0 + (1 - k) * H * 0.35), (cx + r * 0.95, cy - r * 0.3)],
                  fill=color + (255,))
    return fx._down(img)


def _mist(w, h, color, strength):
    """A soft puff of mist."""
    img = Image.new("RGBA", (w * 2, h * 2), color + (0,))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((w * 0.5, h * 0.5, w * 1.5, h * 1.5), fill=round(255 * strength))
    img.putalpha(mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.3)))
    return img


def _grumpy_cloud(w, h, line):
    """Her storm cloud, pouting: squeezed >< eyes, a wobbly mouth, blush."""
    S = fx.SUPER
    img = fx._cloud(w, h, line)
    big = img.resize((img.width * S, img.height * S), Image.LANCZOS)
    pen = ImageDraw.Draw(big)
    W, H = big.size
    width = max(S, round(W * 0.025))
    ink = fx.STORM_SHADE + (255,)
    for side in (-1, 1):
        x, y = W * (0.5 + side * 0.13), H * 0.52
        pen.line([(x - side * W * 0.05, y - H * 0.08), (x + side * W * 0.0, y), (x - side * W * 0.05, y + H * 0.08)], fill=ink, width=width,
                 joint="curve")
        pen.ellipse((x - W * 0.05 + side * W * 0.05, y + H * 0.1, x + W * 0.05 + side * W * 0.05, y + H * 0.16), fill=fx.ACCENT_SOFT + (140,))
    pen.line([(W * 0.45, H * 0.72), (W * 0.48, H * 0.69), (W * 0.52, H * 0.72), (W * 0.55, H * 0.69)], fill=ink, width=width, joint="curve")
    return big.resize(img.size, Image.LANCZOS)


def _letter(w, h, line):
    """A letter sealed in crimson wax: her pale paper in a rim, the flap's
    fold, a round seal with a tiny heart pressed in it."""
    S = fx.SUPER
    shape, d = fx._mask(w, h)
    d.rounded_rectangle((S, S, (w + 1) * S, (h + 1) * S), radius=max(1, w * 0.08) * S, fill=255)
    out = fx._filled(shape, fx.WHITE, fx.PALE, fx.MAIN_SHADE, line)
    pen = ImageDraw.Draw(out)
    fold = [(1.6 * S, 1.6 * S), ((w / 2 + 1) * S, (h * 0.56 + 1) * S), ((w + 0.4) * S, 1.6 * S)]
    pen.line(fold, fill=fx.MAIN_SHADE + (255,), width=max(S, round(line * S * 0.8)), joint="curve")
    cx, cy, r = (w / 2 + 1) * S, (h * 0.56 + 1) * S, w * 0.17 * S
    pen.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fx.ACCENT + (255,), outline=fx.ACCENT_SHADE + (255,),
                width=max(S, round(line * S * 0.6)))
    heart = fx._heart_shape(max(4, round(w * 0.16))).resize((round(r * 1.1),) * 2, Image.LANCZOS)
    pen.bitmap((round(cx - heart.width / 2), round(cy - heart.height / 2)), heart, fill=fx.ACCENT_SHADE + (255,))
    return fx._down(out)


def _winged_banner(text, size, line, tint=None, plain=None):
    """The call on her accent's sticker pill (fx._banner; or `tint`'s),
    bat wings out of its sides."""
    pill = fx._banner(text, size, line, tint, plain)
    S = fx.SUPER
    span = round(pill.height * 1.5)
    n = span * S
    wing = Image.new("L", (n, n), 0)
    ImageDraw.Draw(wing).polygon(_wing(0, n * 0.55, n * 2.0, 18, 1), fill=255)
    ink = Image.new("RGBA", (n, n), fx.MAIN_SHADE + (255,))
    ink.putalpha(wing)
    right = fx._down(ink)
    left = right.transpose(Image.FLIP_LEFT_RIGHT)
    overlap = round(pill.height * 0.35)
    out = Image.new("RGBA", (pill.width + 2 * (span - overlap), max(pill.height, span)), (0, 0, 0, 0))
    y = (out.height - pill.height) // 2
    wy = y + pill.height // 2 - round(span * 0.55)
    out.alpha_composite(left, (0, max(0, wy)))
    out.alpha_composite(right, (out.width - span, max(0, wy)))
    out.alpha_composite(pill, (span - overlap, y))
    return out


def version_banner(version, height):
    """A new version's banner: her main ink's pill, bat wings and all."""
    px = _px(height)
    words = fx.version_words(version)
    pill = _winged_banner(words, px(18), px(2), fx.version_tint(), words)
    return fx._glow(fx._sticker(pill, px(2)), fx.MAIN_LIGHT, px(4), 0.6)


def updated(w, h, t, age, calm=False):
    """Miku's fountain, in her shapes: roses, bats and glints rising."""
    return fx._updated(w, h, t, age, calm)


def build_sprites(height):
    """{name: RGBA image}: every sprite Miku's placements name, in her
    shapes, and her own (bats in flight, the ghost, moon, candle, mist)."""
    px = _px(height)
    line = px(2)
    st, gl = fx._sticker, fx._glow
    M, ML, A, AL = fx.MAIN, fx.MAIN_LIGHT, fx.ACCENT, fx.ACCENT_LIGHT
    sprites = {
        "bubble": gl(st(_lace(px(52), px(38), line), px(2)), ML, px(5), 0.5),
        "puff_s": gl(st(_lace(px(8), px(7), px(1)), px(1.5)), ML, px(3), 0.45),
        "puff_m": gl(st(_lace(px(13), px(11), px(1)), px(1.5)), ML, px(3), 0.45),
        "dot_dim": fx._ellipse(px(7), px(7), fx.DIM),
        "twinkle": gl(_glint(px(16), fx.WHITE), AL, px(3), 0.9),
        "speech": gl(st(_lace(px(44), px(42), line, tail=True), px(2)), ML, px(5), 0.5),
        "question": st(fx._glyph("?", px(22), A, fx.ACCENT_SHADE), px(1)),
        "exclaim": gl(st(fx._bang(px(12), px(30), line), px(2)), AL, px(3), 0.5),
        "drop": gl(st(fx._drop(px(15), px(22), line), px(2)), fx.SKY_DEEP, px(4), 0.45),
        "dash": st(fx._dash(px(9), px(3), A), px(1)),
        "heart": gl(st(_stitched_heart(px(18), A, fx.ACCENT_SHADE, px(1.5)), px(2)), AL, px(3), 0.5),
        "cloud": gl(st(_grumpy_cloud(px(58), px(36), line), px(2)), fx.STORM_SHADE, px(4), 0.35),
        "scribble": fx._scribble(px(34), px(16), A, px(2.2)),
        "broken_note": gl(st(_cracked_heart(px(20), px(1.5)), px(2)), fx.STORM_SHADE, px(3), 0.3),
        "z_main": gl(st(fx._zee(px(18), M, fx.MAIN_SHADE, px(2.5)), px(2)), ML, px(3), 0.5),
        "z_accent": gl(st(fx._zee(px(18), A, fx.ACCENT_SHADE, px(2.5)), px(2)), AL, px(3), 0.5),
        "love_heart": gl(st(_hollow_stitched(px(110), px(14)), px(3)), AL, px(6), 0.6),
        "core_heart": gl(st(_stitched_heart(px(30), A, fx.ACCENT_SHADE, px(2)), px(2)), AL, px(7), 0.9),
        "flash_accent": fx._flash(px(64), AL),
        "flash_main": fx._flash(px(64), ML),
        "banner": gl(st(_winged_banner(fx.CALL, px(21), px(2)), px(2)), AL, px(4), 0.6),
        "ghost": gl(st(_ghost(px(22), px(26), px(1.5)), px(2)), ML, px(4), 0.55),
        "moon": gl(st(_crescent(px(32), fx.GOLD, face=True), px(2)), fx.GOLD, px(5), 0.55),
        "bat_hang": gl(st(_hanging_bat(px(26), fx.MAIN_SHADE), px(2)), ML, px(3), 0.5),
        "stitch": gl(st(_cross_stitch(px(10), A), px(1)), AL, px(2), 0.5),
        "needle": gl(st(_needle(px(26), px(1)), px(1.5)), ML, px(3), 0.5),
        "candle": st(_candle(px(9), px(18), px(1)), px(1)),
        "flame": gl(_flame(px(6), px(10)), fx.GOLD, px(4), 1.0),
        "mist": _mist(px(70), px(26), fx.PALE, 0.55),
        "wisp": _mist(px(22), px(12), fx.PALE, 0.7),
        "letter": gl(st(_letter(px(24), px(17), px(1.5)), px(1.5)), ML, px(3), 0.5),
        "away_note": gl(st(_letter(px(32), px(23), line), px(2)), ML, px(4), 0.5),
    }
    for tint, ink, light in (("main", M, ML), ("accent", A, AL)):
        for pose, angle in (("up", 38), ("mid", 6), ("down", -32)):
            sprites[f"bat_{tint}_{pose}"] = gl(st(_bat_img(px(26), ink, angle), px(1.5)), light, px(3), 0.6)
        sprites[f"note_{tint}"] = sprites[f"bat_{tint}_mid"]
        pair = Image.new("RGBA", (round(sprites[f"note_{tint}"].width * 1.5), round(sprites[f"note_{tint}"].height * 1.3)), (0, 0, 0, 0))
        small = sprites[f"bat_{tint}_up"].resize((round(sprites[f"note_{tint}"].width * 0.75),) * 2, Image.LANCZOS)
        pair.alpha_composite(sprites[f"note_{tint}"], (0, pair.height - sprites[f"note_{tint}"].height))
        pair.alpha_composite(small, (pair.width - small.width, 0))
        sprites[f"notes_{tint}"] = pair
        sprites[f"dot_{tint}"] = gl(_gem(px(8), ink), light, px(3), 0.9)
        sprites[f"pip_{tint}"] = gl(st(_cross_stitch(px(7), ink), px(1)), light, px(2), 0.6)
        sprites[f"spark_{tint}"] = gl(_glint(px(8), fx.WHITE), light, px(2), 0.9)
    # Miku's name for her messenger: here the bat with its letter, still.
    bat, letter = sprites["bat_main_mid"], sprites["letter"]
    carried = Image.new("RGBA", (max(bat.width, letter.width), bat.height // 2 + letter.height), (0, 0, 0, 0))
    carried.alpha_composite(letter, ((carried.width - letter.width) // 2, carried.height - letter.height))
    carried.alpha_composite(bat, ((carried.width - bat.width) // 2, 0))
    sprites["messenger"] = carried
    sprites["star_main"] = gl(_gem_glint(px(22), fx.MAIN_LIGHT), ML, px(4), 0.8)
    sprites["star_accent"] = gl(st(_rose(px(18), A, fx.ACCENT_SHADE, px(1)), px(1.5)), AL, px(4), 0.6)
    sprites["star_gold"] = gl(st(_crescent(px(16), fx.GOLD), px(1.5)), fx.GOLD, px(4), 0.6)
    for tint, ink, light in (("main", fx.MAIN_LIGHT, ML), ("accent", A, AL), ("hot", fx.HOT, fx.HOT)):
        sprites[f"pixel_{tint}"] = gl(_petal(px(6), ink), light, px(2), 0.7)
    return sprites


def ornament(kind, size, color, glow=None):
    """Her ornaments for the settings window: "note" a bat, "notes" two,
    "star" a glint, "heart" a stitched heart."""
    line = max(1, round(size / 12))
    if kind == "note":
        img = fx._sticker(_bat_img(size, color, 20), line)
    elif kind == "notes":
        big, small = _bat_img(size, color, 6), _bat_img(round(size * 0.7), color, 38)
        img = Image.new("RGBA", (round(size * 1.45), round(size * 1.2)), (0, 0, 0, 0))
        img.alpha_composite(big, (0, img.height - big.height))
        img.alpha_composite(small, (img.width - small.width, 0))
        img = fx._sticker(img, line)
    elif kind == "star":
        img = _glint(size, color)
    elif kind == "heart":
        img = fx._sticker(_stitched_heart(size, color, tuple(round(c * 0.7) for c in color), line), line)
    else:
        raise ValueError(kind)
    return fx._glow(img, glow, max(1, round(size / 6)), 0.6) if glow else img


# ---------------------------------------------------------- moods


def thinking(w, h, t, age):
    """A lace thought bubble whose gem dots light in turn (Miku's motion)."""
    return fx.thinking(w, h, t, age)


STITCHES = 5
STITCH_S = 0.36  # the needle takes a stitch this often
SEAM_HOLD = 0.6  # the seam stays, finished, this long
SEAM_FADE = 0.45
SEAM_CYCLE = STITCHES * STITCH_S + SEAM_HOLD + SEAM_FADE
BAT_EVERY = 1.3  # a bat flutters off her work this often
BAT_LIFE = 2.0


def _seam_at(u, w, h):
    (x0, y0), (x1, y1) = SEAM
    return (x0 + (x1 - x0) * u) * w, (y0 + (y1 - y0) * u) * h - 0.012 * h * math.sin(math.pi * u)


def working(w, h, t, age):
    """A needle sewing cross stitches along a little seam at the upper
    right, one stitch at a time; the finished seam holds, fades, and she
    starts again. Now and then a bat flutters up off it."""
    draws = []
    grow = pop(age)
    c = age % SEAM_CYCLE
    sewing = STITCHES * STITCH_S
    sewn = c / STITCH_S
    fade = 1.0 if c < sewing + SEAM_HOLD else max(0.0, 1 - (c - sewing - SEAM_HOLD) / SEAM_FADE)
    (x0, y0), (x1, y1) = SEAM
    slope = math.degrees(math.atan2(-(y1 - y0) * h, (x1 - x0) * w))
    for i in range(STITCHES):
        if sewn > i + 0.55:
            x, y = _seam_at((i + 0.5) / STITCHES, w, h)
            draws.append(Draw("stitch", x, y, grow * pop((sewn - i - 0.55) * STITCH_S, 0, 0.18), fade, slope + 8 * (i % 2 * 2 - 1)))
    if c < sewing:
        u = min(1.0, sewn / STITCHES)
        hop = abs(math.sin(math.pi * sewn))  # up out of the cloth and back in, each stitch
        x, y = _seam_at(u, w, h)
        draws.append(Draw("needle", x + 0.02 * w * hop, y - 0.035 * h * hop, grow, 1.0, -10 + 20 * hop))
    else:
        back = fx._span(c, sewing + 0.1, SEAM_CYCLE)  # it travels back to start the next
        x, y = _seam_at(1 - back, w, h)
        draws.append(Draw("needle", x, y - 0.05 * h * math.sin(math.pi * back), grow, 1.0, -10 + 25 * math.sin(math.pi * back)))
    for k, since, p in fx._spawned(age - 0.5, BAT_EVERY, BAT_LIFE):
        if k < 0:
            continue
        x = (0.86 + 0.08 * (k % 3)) * w + 0.04 * w * math.sin(p * 7 + k)
        y = 0.17 * h - 0.22 * h * (1 - (1 - p) ** 1.6)
        alpha = min(1.0, p / 0.12, (1 - p) / 0.3)
        draws.append(Draw(_bat(t, k, "accent" if k % 2 else "main"), x, y, 0.55 + 0.25 * p, alpha, 10 * math.sin(p * 9 + k)))
    return draws


def waiting(w, h, t, age):
    """A lace speech bubble with a crimson "?" that hops now and then,
    petals bursting from it on each hop, and a bat peeking at its corner."""
    sx, sy = SYMBOL_AT[0] * w, SYMBOL_AT[1] * h
    grow = pop(age)
    beat = (age % fx.ASK_EVERY) / fx.ASK_EVERY if age > 0.4 else 0
    hop = pulse(beat / 0.25)
    draws = []
    burst = beat / 0.55 if 0 < beat < 0.55 else 0
    if burst:
        reach = 1 - (1 - burst) ** 3
        for i in range(6):
            a = math.pi * 2 * i / 6 + 0.4
            r = w * (0.06 + 0.07 * reach)
            draws.append(Draw("pixel_accent" if i % 2 else "pixel_main", sx + r * math.cos(a), sy - 0.01 * h + r * math.sin(a) * 0.85,
                              1.5 - 0.5 * burst, 1 - burst ** 2, 200 * burst + 60 * i))
    squash = 1 + 0.06 * hop
    draws.append(Draw("speech", sx, sy, grow * squash))
    draws.append(Draw("question", sx + 0.004 * w, sy - 0.016 * h - 3 * hop, grow * (1 + 0.1 * hop), 1.0, -10 * hop))
    draws.append(Draw(_bat(t, 0, "main", 3.0), sx + 0.08 * w, sy + 0.04 * h + 1.5 * math.sin(t * 3), grow * 0.6, 1.0, 10 * math.sin(t * 1.7)))
    return draws


# ---------------------------------------------------------- messages
#
# Her messenger is a bat carrying a sealed letter, at her upper left (Miku's
# phone's spot); her away note a letter at her feet.

LETTER_HANG = 0.062  # the letter hangs this share of her height under the bat


def _messenger(x, y, h, t, swing, grow, alpha=1.0, hz=FLAP_HZ):
    """A bat at (x, y) with its letter hanging under it, swung `swing`
    degrees (`h`: her frame's height)."""
    a = math.radians(swing)
    lx, ly = x - math.sin(a) * LETTER_HANG * h, y + math.cos(a) * LETTER_HANG * h
    return [Draw("letter", lx, ly, grow, alpha, swing),
            Draw(_bat(t, 7, "main", hz), x, y, grow * 1.25, alpha, 6 * math.sin(t * 2))]


def calling(w, h, t, age, calm=False):
    """The bat flutters by her head with its letter; in bursts, it shakes
    the letter at you and a petal or two falls (calm: no petals)."""
    x, y = fx.CALL_AT[0] * w, fx.CALL_AT[1] * h - 0.03 * h
    grow = pop(age)
    beat = age % fx.CALL_EVERY
    ringing = age > 0.3 and beat < fx.CALL_RING_S
    swing = 8 * math.sin(t * 1.7) + (0.0 if not ringing else 16 * math.sin(beat * 30) * (1 - beat / fx.CALL_RING_S))
    bob = 3 * math.sin(t * 3.1)
    draws = []
    if ringing and not calm:
        p = beat / fx.CALL_RING_S
        for i in range(2):
            draws.append(Draw("pixel_accent", x + (i * 2 - 1) * 0.03 * w, y + 0.06 * h + 0.06 * h * p,
                              1.3, 1 - p, 200 * p + 90 * i))
    draws += _messenger(x, y + bob, h, t, swing, grow, hz=8.0 if ringing else FLAP_HZ)
    return draws


def delivered(w, h, t, age, calm=False):
    """The bat swoops in with a letter, lets it go by her head and flies
    off; the letter flutters down past her and fades."""
    if not 0 <= age < fx.DELIVER_S:
        return []
    x1, y1 = fx.CALL_AT[0] * w, fx.CALL_AT[1] * h - 0.03 * h
    drop = 0.9  # the letter goes
    draws = []
    if age < drop:
        fly = min(1.0, age / fx.DELIVER_IN_S)
        e = 1 - (1 - fly) ** 3
        x = -0.12 * w + (x1 + 0.12 * w) * e
        y = -0.1 * h + (y1 + 0.1 * h) * e + 0.05 * h * math.sin(math.pi * fly)
        draws += _messenger(x, y + 2 * math.sin(t * 3), h, t, 10 * math.sin(age * 9), pop(age, 0, 0.3), hz=8.0)
        return draws
    q = (age - drop) / (fx.DELIVER_S - drop)
    fade = min(1.0, (1 - q) / 0.35)
    # The letter, falling and rocking like paper.
    lx = x1 + 0.08 * w * math.sin(q * 5) + 0.06 * w * q
    ly = y1 + LETTER_HANG * h + 0.5 * h * (q ** 1.4)
    draws.append(Draw("letter", lx, ly, 1.0, fade, 25 * math.sin(q * 10)))
    # The bat, off up and away.
    bx, by = x1 - 0.15 * w * q, y1 - 0.25 * h * q
    draws.append(Draw(_bat(t, 7, "main", 8.0), bx, by, 1.25 * (1 - 0.3 * q), min(1.0, (1 - q) / 0.5)))
    if not calm and q < 0.3:
        p = q / 0.3
        for i in range(4):
            a = math.tau * i / 4 + 0.5
            draws.append(Draw("spark_accent" if i % 2 else "spark_main", x1 + 0.05 * w * p * math.cos(a),
                              y1 + 0.05 * h + 0.05 * w * p * math.sin(a), 1.1 * (1 - p), 1 - p, 90 * p))
    return draws


def noted(w, h, t, age, calm=False):
    """A sealed letter waiting at her feet; a glint crosses its seal now
    and then (calm: none)."""
    x, y = fx.NOTE_AT[0] * w, fx.NOTE_AT[1] * h + 0.02 * h
    draws = [Draw("away_note", x, y, pop(age), 1.0, -12)]
    if not calm:
        p = (age % 3.4) / 0.8
        if p < 1:
            draws.append(Draw("spark_main", x + 0.02 * w, y - 0.01 * h, 1.2 * pulse(p), pulse(p), 90 * p))
    return draws


GHOST_PEEK_EVERY = 2.6  # the ghost ducks and peeks out again this often


def worried(w, h, t, age):
    """A sweat drop sliding down her hair (Miku's), and by her other temple
    a little ghost trembling, ducking now and then, nervous lines over it."""
    draws = [d for d in fx.worried(w, h, t, age) if d.sprite != "dash"]
    gx, gy = GHOST_AT[0] * w, GHOST_AT[1] * h
    q = (age % GHOST_PEEK_EVERY) / GHOST_PEEK_EVERY
    duck = pulse((q - 0.7) / 0.25)
    tremble = 1.2 * math.sin(t * 38) * (1 - duck)
    y = gy + 0.03 * h * duck + 1.5 * math.sin(t * 3)
    draws.append(Draw("ghost", gx + tremble, y, pop(age) * (1 - 0.25 * duck), 1 - 0.5 * duck, 8 * math.sin(t * 5)))
    for i, a in enumerate((-150, -118, -86)):
        flick = 0.5 + 0.5 * math.sin(t * 9 + i * 2.1)
        out = 0.07 * w + 0.01 * w * flick
        rad = math.radians(a)
        draws.append(Draw("dash", gx + out * math.cos(rad), y - 0.01 * h + out * math.sin(rad), pop(age, 0.05 * i) * (0.85 + 0.2 * flick) * (1 - duck),
                          0.55 + 0.45 * flick, -90 - a))
    return draws


def sleepy(w, h, t, age):
    """A sleepy crescent moon rocking up left of her head with a bat asleep
    upside down under its horn, swinging; z's drift up from her (Miku's)."""
    draws = [d for d in fx.sleepy(w, h, t, age) if d.sprite.startswith("z_")]
    grow = pop(age)
    mx, my = MOON_AT[0] * w, MOON_AT[1] * h
    rock = 6 * math.sin(t * 0.9)
    draws.append(Draw("moon", mx, my, grow, 1.0, rock))
    # Its lower horn, turned with it; the bat hangs from there.
    a = math.radians(rock)
    hx, hy = 0.012 * w, 0.03 * h
    horn = (mx + hx * math.cos(a) + hy * math.sin(a), my - hx * math.sin(a) + hy * math.cos(a))
    swing = 9 * math.sin(t * 1.3)
    length = 0.028 * h
    b = math.radians(swing)
    draws.append(Draw("bat_hang", horn[0] + length * math.sin(b), horn[1] + length * math.cos(b), grow * pop(age, 0.15), 1.0, swing))
    twinkle = pulse(((age + 0.6) % 2.7) / 0.8)
    if twinkle and age > 0.6:
        n = math.floor((age + 0.6) / 2.7)
        draws.append(Draw("spark_main" if n % 2 else "spark_accent", mx + (0.12 + 0.04 * (n % 3)) * w, my + (0.02 + 0.03 * (n % 2)) * h,
                          0.6 + 0.6 * twinkle, twinkle, 40 * twinkle))
    return draws


def happy(w, h, t, age):
    """A burst of bats flapping out from her head as the mood starts, then
    roses and silver glints twinkling around her raised arms and stitched
    hearts floating up (Miku's hearts, in her shape)."""
    draws = []
    hx, hy = HEAD_AT[0] * w, HEAD_AT[1] * h
    if age < fx.BURST_S:
        p = age / fx.BURST_S
        reach = 1 - (1 - p) ** 3
        for i in range(8):
            a = math.radians(-195 + 210 * i / 7)
            r = w * (0.16 + 0.3 * reach) * (1.0 if i % 2 else 0.82)
            draws.append(Draw(_bat(t, i, "accent" if i % 3 == 1 else "main"), hx + r * math.cos(a), hy + r * math.sin(a) * 0.8,
                              (1.0 - 0.45 * p) * pop(age, 0, 0.15), 1 - p ** 3, 15 * math.cos(a)))
    for i, (x, y) in enumerate(SHINE_AT):
        cycle = 1.6 + 0.3 * i
        q = ((age - 0.3 - 0.37 * i) % cycle) / cycle if age > 0.3 + 0.37 * i else 0
        twinkle = pulse(q / 0.6)
        if twinkle:
            n = math.floor((age - 0.3 - 0.37 * i) / cycle)
            kind = ("accent", "main", "accent", "main", "gold")[(i + n) % 5]
            draws.append(Draw("star_" + kind, x * w, y * h, 0.3 + 0.7 * twinkle, twinkle, (25 if kind == "accent" else 45) * q))
    draws += [d for d in fx.happy(w, h, t, age) if d.sprite == "heart"]
    return draws


def error(w, h, t, age):
    """The grumpy cloud shuddering in and huffing, pouting (Miku's motion),
    a crimson scribble fuming off its side, a cracked heart dropping out
    of it now and then."""
    draws = []
    for d in fx.error(w, h, t, age):
        if d.sprite == "scribble":  # off its face, up by its shoulder
            d = d._replace(x=d.x + 0.12 * w, y=d.y - 0.045 * h, scale=d.scale * 0.6)
        draws.append(d)
    return draws


CHARGE_S = 0.7
BANNER_S = (0.75, 2.2)
BEAM_WIDE_S = 2.3
AFTERGLOW_S = 1.9


def beam(w, h, t, age):
    """Her finisher's sprites (frame coordinates; the burst reaches well
    past the frame)."""
    hx, hy = HANDS_AT[0] * w, HANDS_AT[1] * h
    draws = []
    fired = age - CHARGE_S
    if fired < 0:
        p = age / CHARGE_S
        for i in range(10):
            q = min(1.0, max(0.0, (p - 0.04 * i) / 0.6))
            if q <= 0 or q >= 1:
                continue
            a = i * math.tau / 10 + 5 * q
            r = w * 0.5 * (1 - q) ** 1.2
            sprite = _bat(t, i, "accent" if i % 3 == 1 else "main") if i % 2 == 0 else ("pixel_accent" if i % 4 == 1 else "pixel_main")
            draws.append(Draw(sprite, hx + r * math.cos(a), hy + 0.8 * r * math.sin(a), 0.5 + 0.5 * (1 - q), min(1.0, q * 4),
                              0.0 if sprite.startswith("bat") else 160 * q))
        beat = fx._heartbeat(age, 0.35)  # lub-dub, faster as it fills
        draws.append(Draw("core_heart", hx, hy, 0.35 + 0.7 * p ** 1.5 + 0.12 * beat * p, min(1.0, p * 3)))
        return draws
    # A swarm of bats flying out at you, leaning upward (clear of the floor).
    if fired < 1.3:
        p = fired / 1.3
        reach = 1 - (1 - p) ** 2.5
        for i in range(12):
            a = math.radians(-90 + 30 * i + 9 * math.sin(i * 2.3))
            r = w * (0.18 + 0.48 * reach) * (0.85 + 0.15 * (i % 3))
            draws.append(Draw(_bat(t, i, "accent" if i % 3 == 0 else "main", 8.0), hx + r * math.cos(a), hy + 0.85 * r * math.sin(a),
                              0.65 + 0.45 * p, min(1.0, (1 - p) / 0.3), 12 * math.cos(a)))
    # Hollow stitched hearts bursting toward the viewer.
    for k in range(3):
        p = (fired - k * fx.RING_EVERY) / fx.RING_LIFE
        if 0 <= p < 1:
            grow = 1 - (1 - p) ** 2
            draws.append(Draw("love_heart", hx, hy + 0.04 * h * grow, 0.25 + 2.4 * grow, (1 - p) ** 2.2, 6 * math.sin(k + p * 3)))
    if fired < 0.9:
        draws.append(Draw("core_heart", hx, hy, 1.1 + 0.9 * pulse(fired / 0.5), max(0.0, 1 - fired / 0.9)))
    if BANNER_S[0] <= age < BANNER_S[1]:
        b = age - BANNER_S[0]
        fade = min(1.0, (BANNER_S[1] - age) / 0.3)
        draws.append(Draw("banner", 0.5 * w, -0.06 * h - 4 * pulse(b / 0.5), pop(b, 0, 0.3), fade, 6 * math.exp(-4 * b) * math.sin(b * 14) - 3))
    # Afterglow: petals drifting down, stitched hearts floating up, roses.
    if age > AFTERGLOW_S:
        g = age - AFTERGLOW_S
        for i in range(8):
            p = (g - 0.12 * i) / 1.5
            if not 0 <= p < 1:
                continue
            side = -1 if i % 2 else 1  # down either side of her, clear of her face
            x = w * (0.5 + side * (0.24 + 0.22 * _rand(i, 101))) + 0.04 * w * math.sin(p * 5 + i)
            y = h * (0.02 + 0.4 * p)
            draws.append(Draw("pixel_accent" if i % 3 else "pixel_main", x, y, 1.3, min(1.0, p / 0.1, (1 - p) / 0.3), 140 * p + 50 * i))
        for i in range(4):
            p = (g - 0.25 * i) / 1.3
            if not 0 <= p < 1:
                continue
            side = -1 if i % 2 else 1
            x = hx + side * w * (0.2 + 0.08 * i) + 6 * math.sin(p * 7 + i)
            y = hy - h * (0.05 + 0.25 * p)
            if p < 0.8:
                draws.append(Draw("heart", x, y, 0.8 * pop(p * 1.3, 0, 0.25), 1.0, 12 * math.sin(p * 5 + i)))
            else:
                q = (p - 0.8) / 0.2
                draws.append(Draw("pixel_accent", x, y, 1.6 * pulse(q), pulse(q), 90 * q))
        for i, (x, y) in enumerate(SHINE_AT[:3]):
            q = ((g - 0.3 * i) % 1.2) / 1.2 if g > 0.3 * i else 0
            if pulse(q / 0.6):
                draws.append(Draw("star_" + ("accent", "main", "accent")[i], x * w, y * h, 0.3 + 0.6 * pulse(q / 0.6), pulse(q / 0.6), 25 * q))
    return draws


def magic(start, target, flight, age, t, ended=None, calm=False):
    """Her call to the pointer: Miku's flight in her shapes (a silver glint
    trailing petals, roses bursting), its notes flapping bats."""
    return fx._magic(start, target, flight, age, t, ended, calm, note=lambda k, tint: _bat(t, k, tint))


PLACEMENTS = {"thinking": thinking, "working": working, "waiting": waiting, "worried": worried, "sleepy": sleepy,
              "happy": happy, "error": error, "beam": beam}

RAYS = 14


def _rays(size, center, inner, strength, turn):
    """Soft crimson and silver rays fanning out from `center`, turning
    slowly by `turn` degrees, fading before the canvas's edge."""
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if strength <= 0.01:
        return out
    d = ImageDraw.Draw(out)
    cx, cy = center
    reach = min(cx, cy, size[0] - cx, size[1] - cy) - 4
    for i in range(RAYS):
        a = math.radians(turn) + math.tau * i / RAYS
        half = 0.05 + 0.02 * (i % 2)
        color = (fx.ACCENT_LIGHT, fx.MAIN_LIGHT)[i % 2]
        alpha = round(255 * strength * (0.42 if i % 2 == 0 else 0.3))
        r0 = inner * (0.9 + 0.2 * (i % 3) / 2)
        d.polygon([(cx + r0 * math.cos(a - half * 0.25), cy + r0 * math.sin(a - half * 0.25)),
                   (cx + reach * math.cos(a - half), cy + reach * math.sin(a - half)),
                   (cx + reach * math.cos(a + half), cy + reach * math.sin(a + half)),
                   (cx + r0 * math.cos(a + half * 0.25), cy + r0 * math.sin(a + half * 0.25))], fill=color + (alpha,))
    out.putalpha(ImageChops.multiply(out.getchannel("A"), fx._fade_mask(size, center, reach)))
    return out


def _shockwave(out, center, radius, width, alpha):
    """A ring of her accent's light spreading out from `center`."""
    if alpha <= 0.01 or radius < 1:
        return
    layer = Image.new("RGBA", out.size, fx.ACCENT_LIGHT + (0,))
    mask = Image.new("L", out.size, 0)
    cx, cy = center
    ImageDraw.Draw(mask).ellipse((cx - radius, cy - radius * 0.85, cx + radius, cy + radius * 0.85), outline=round(255 * alpha),
                                 width=max(1, round(width)))
    layer.putalpha(mask.filter(ImageFilter.GaussianBlur(max(1, width / 3))))
    out.alpha_composite(layer)


def beamed(image, w, h, age, t, draws, sprites, calm=False):
    """The window's `image` on a canvas BEAM_PAD larger on every side, her
    rays, shockwave and flash behind her (not when `calm`), `draws` over."""
    pad = fx.BEAM_PAD
    out = Image.new("RGBA", (image.width + 2 * pad, image.height + 2 * pad), (0, 0, 0, 0))
    at = (fx.PAD_LEFT + pad, fx.PAD_TOP + pad)
    hx, hy = at[0] + HANDS_AT[0] * w, at[1] + HANDS_AT[1] * h
    fired = age - CHARGE_S
    if fired >= 0 and not calm:
        strength = pop(fired, 0, 0.12) * (1 - fx._span(fired, 0.8, 1.4))
        out.alpha_composite(_rays(out.size, (hx, hy), w * (0.28 + 0.2 * min(1.0, fired / 0.8)), strength, 18 * fired))
        p = min(1.0, fired / 0.6)
        _shockwave(out, (hx, hy), w * (0.15 + 0.75 * (1 - (1 - p) ** 2)), w * 0.05 * (1 - p) + 1, (1 - p) ** 1.5 * 0.9)
        flash = pulse(min(1.0, fired / 0.7) * 0.5 + 0.5) if fired < 0.7 else 0.0
        fx.paint(out, [Draw("flash_accent", HANDS_AT[0] * w, HANDS_AT[1] * h, 5.0, 0.8 * flash),
                       Draw("flash_main", HANDS_AT[0] * w, HANDS_AT[1] * h, 2.4, 0.6 * flash)], sprites, at)
    out.alpha_composite(image, (pad, pad))
    return fx.paint(out, draws, sprites, at)


# ---------------------------------------------------------- glitch

RIPPLE_STRIP = 6  # px: the ripple moves her in bands this tall


def glitch(frame, amount, t):
    """`frame` haunted by `amount` (0..1) at time `t`: a silver afterimage
    up left and a crimson one down right, her rows rippling like a ghost's
    sheet, a flicker of see-through."""
    w, h = frame.size
    step = math.floor(t / fx.GLITCH_STEP)
    off = max(1, round(w * 0.028 * amount * (0.5 + _rand(step, 1))))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(fx._ghost(frame, fx.MAIN_LIGHT, 0.7 * amount), (0, 0), (off, off // 2))
    out.alpha_composite(fx._ghost(frame, fx.ACCENT_LIGHT, 0.7 * amount), (off, off // 2))
    out.alpha_composite(frame)
    amp = w * 0.022 * amount
    if amp >= 0.5:
        phase = t * 11 + _rand(step, 2) * 2
        period = h * (0.1 + 0.05 * _rand(step, 3))
        rippled = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for y in range(0, h, RIPPLE_STRIP):
            dx = round(amp * math.sin(math.tau * y / period + phase))
            fx._put(rippled, out.crop((0, y, w, min(h, y + RIPPLE_STRIP))), dx, y)
        out = rippled
    see = 1 - 0.35 * amount * _rand(step, 4)
    if see < 0.99:
        out.putalpha(fx._scaled(out.getchannel("A"), see))
    return out


# ---------------------------------------------------------- status

CANDLES = (-168, -138, -42, -12)  # degrees round the floor ellipse: behind and beside her
MOON_R = 0.46  # the blood moon's radius, a share of her width
_moons = {}


def _floor(frame):
    """The floor ellipse at her feet: (cx, cy, rx, ry) in frame pixels."""
    w, h = frame.size
    feet = fx._outline(frame)["feet"] or (0, 0, w, h)
    return (feet[0] + feet[2]) / 2, feet[3] - h * 0.012, w * 0.36, h * 0.034


def _blood_moon(r):
    """A blood moon `r` px in radius on a soft halo: hot at its heart,
    deep at its rim, faint maria."""
    if r in _moons:
        return _moons[r]
    pad = max(2, r // 3)
    size = 2 * (r + pad)
    v = Image.radial_gradient("L").resize((2 * r, 2 * r), Image.BILINEAR)
    heart = tuple(round(c + (255 - c) * 0.18) for c in fx.HOT)
    face = Image.merge("RGB", [v.point(lambda x, a=a, b=b: round(a + (b - a) * min(1.0, x / fx.RADIAL_EDGE) ** 1.6))
                               for a, b in zip(heart, fx.ACCENT)]).convert("RGBA")
    disc = Image.new("L", (2 * r, 2 * r), 0)
    ImageDraw.Draw(disc).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    maria = Image.new("RGBA", face.size, fx.ACCENT_SHADE + (0,))
    mm = Image.new("L", face.size, 0)
    md = ImageDraw.Draw(mm)
    for x, y, s in ((0.32, 0.36, 0.16), (0.6, 0.3, 0.1), (0.55, 0.62, 0.2), (0.3, 0.68, 0.08)):
        md.ellipse(((x - s) * 2 * r, (y - s * 0.8) * 2 * r, (x + s) * 2 * r, (y + s * 0.8) * 2 * r), fill=110)
    maria.putalpha(mm.filter(ImageFilter.GaussianBlur(r * 0.06)))
    face.alpha_composite(maria)
    rim = Image.new("L", disc.size, 0)
    ImageDraw.Draw(rim).ellipse((0, 0, 2 * r - 1, 2 * r - 1), outline=255, width=max(1, r // 30))
    lit = Image.new("RGBA", face.size, fx.ACCENT_SOFT + (0,))
    lit.putalpha(rim.filter(ImageFilter.GaussianBlur(max(1, r / 60))))
    face.alpha_composite(lit)
    face.putalpha(disc)
    out = Image.new("RGBA", (size, size), fx.HOT + (0,))
    halo = Image.new("L", (size, size), 0)
    ImageDraw.Draw(halo).ellipse((pad * 0.5, pad * 0.5, size - pad * 0.5, size - pad * 0.5), fill=190)
    out.putalpha(halo.filter(ImageFilter.GaussianBlur(pad * 0.4)))
    out.alpha_composite(face, (pad, pad))
    _moons.clear()
    _moons[r] = out
    return out


def _candle_draws(frame, t, fade, calm, lit=None):
    """Candles round her feet, each flame flickering on its own (steady when
    `calm`); `lit` (0..1 each) for flames lighting up or snuffed."""
    w, h = frame.size
    cx, cy, rx, ry = _floor(frame)
    draws = []
    for i, a in enumerate(CANDLES):
        r = math.radians(a)
        x, y = cx + rx * math.cos(r), cy + ry * math.sin(r)
        draws.append(Draw("candle", x, y - 0.018 * h, 1.0, fade))
        b = fx.CALM_LIGHT if calm else fx._flicker(t + 1.7 * i)
        if lit is not None:
            b *= lit[i]
        if b > 0.05:
            draws.append(Draw("flame", x + (0 if calm else 0.6 * math.sin(t * 13 + i)), y - 0.046 * h, 0.55 + 0.5 * b, fade * min(1.0, b * 1.4)))
    return draws


def _candle_glow(frame, brightness):
    """The warm pool of candlelight on the floor (the floor ring's masks in
    her gold), as (image, x, y) on the canvas."""
    w, h = frame.size
    if (w, h) not in fx._rings:
        fx._rings.clear()
        fx._rings[(w, h)] = fx._floor_ring(w, h)
    light, glow = fx._rings[(w, h)]
    out = Image.new("RGBA", glow.size, fx.GOLD + (0,))
    out.putalpha(fx._scaled(ImageChops.lighter(glow, fx._scaled(light, 0.35)), 0.7 * brightness))
    cx, cy, _, _ = _floor(frame)
    return out, round(fx.PAD_LEFT + cx - out.width / 2), round(fx.PAD_TOP + cy - out.height / 2)


RISE_EVERY = 0.4
RISE_LIFE = 2.8
EMBER_EVERY = 0.08
EMBER_LIFE = 0.8
WISP_EVERY = 0.22
WISP_LIFE = 2.2


def _aura_draws(shape, w, h, level, t, fade):
    """Petals and bats rising off her (level 2 up); at a blood moon, embers
    crackling off her edges too."""
    draws = []
    for n, age, p in fx._spawned(t, RISE_EVERY, RISE_LIFE):
        side = -1 if n % 2 else 1  # off her outline, clear of her face
        spot = fx._edge_point(shape, h, 0.3 + 0.4 * _rand(n, 12), side)
        if not spot:
            continue
        x = spot[0] + side * w * (0.02 + 0.06 * _rand(n, 11)) + math.sin(age * 2.2 + n) * w * 0.03
        y = spot[1] - p * h * 0.32
        kind = _rand(n, 13)
        alpha = min(1.0, p / 0.15) * min(1.0, (1 - p) / 0.35) * 0.85 * fade
        if kind < 0.22:
            draws.append(Draw(_bat(t, n, "accent" if level >= 3 else "main"), x, y, 0.45 + 0.15 * _rand(n, 14), alpha, 8 * math.sin(age * 3 + n)))
        else:
            sprite = ("pixel_hot" if kind < 0.6 else "pixel_accent") if level >= 3 else ("pixel_accent" if kind < 0.6 else "pixel_main")
            draws.append(Draw(sprite, x, y, 0.9 + 0.5 * _rand(n, 14), alpha, 120 * age + 60 * n))
    if level >= 3:
        for n, age, p in fx._spawned(t, EMBER_EVERY, EMBER_LIFE):
            side = -1 if _rand(n, 21) < 0.5 else 1
            spot = fx._edge_point(shape, h, 0.08 + 0.8 * _rand(n, 22), side)
            if spot:
                x = spot[0] + side * (2 + p * w * 0.06)
                y = spot[1] - p * h * 0.05 + (_rand(n, 23) - 0.5) * 6
                draws.append(Draw("pixel_hot" if _rand(n, 24) < 0.6 else "pixel_accent", x, y, 0.8 - 0.4 * p, (1 - p) * fade, 200 * p))
    return draws


def _ghost_fade(frame, t, fade, calm):
    """`frame` fading into a ghost: whole down to her waist, then thinning
    toward her feet (a ghost has none), a pale tint, its hem wavering."""
    w, h = frame.size
    alpha = frame.getchannel("A")
    tint = Image.new("RGBA", (w, h), fx.PALE + (0,))
    tint.putalpha(fx._scaled(alpha, 0.22 * fade))
    out = frame.copy()
    out.alpha_composite(tint)
    wave = 0.0 if calm else 0.04 * math.sin(t * 1.7)
    values = []
    for y in range(h):
        u = y / h
        k = min(1.0, max(0.0, (u - (0.5 + wave)) / 0.45))
        values.append(round(255 * (1 - fade * (0.12 + 0.7 * k * k))))
    out.putalpha(ImageChops.multiply(out.getchannel("A"), fx._column(values, w)))
    return out


def _wisp_draws(shape, w, h, t, fade):
    draws = []
    for n, age, p in fx._spawned(t, WISP_EVERY, WISP_LIFE):
        side = -1 if _rand(n, 41) < 0.5 else 1
        spot = fx._edge_point(shape, h, 0.45 + 0.5 * _rand(n, 42), side)
        if spot:
            x = spot[0] + side * p * w * 0.04 + math.sin(age * 2 + n) * 4
            y = spot[1] - p * h * 0.2
            draws.append(Draw("wisp", x, y, 0.6 + 0.8 * p, min(1.0, p / 0.2) * (1 - p) * 0.9 * fade))
    return draws


def dress(frame, now, before, age, t, height, sprites, calm=False):
    """effects.dress in her style: the aura as moonlight, crimson, then a
    blood moon; the 5-hour limit as guttering candles; the weekly one as
    her fading into a ghost."""
    fades = fx._fades(now, before, age)
    if not fades:
        return fx.Dressed(frame, None, None, [], 0.0)
    shape = fx._shape(frame)
    w, h = frame.size
    out, draws, glitch_ = frame, [], 0.0
    behind = Image.new("RGBA", (fx.PAD_LEFT + w + fx.PAD_RIGHT, height), (0, 0, 0, 0))
    for (effect, level), fade in sorted(fades.items()):
        if effect == "aura" and level >= 3:
            beat = 0.0 if calm else fx._heartbeat(t)
            moon = _blood_moon(max(4, round(MOON_R * w)))
            moon = fx.faded(moon, (0.86 + 0.14 * beat) * fade)
            fx._put(behind, moon, fx.PAD_LEFT + 0.5 * w - moon.width / 2, fx.PAD_TOP + 0.24 * h - moon.height / 2)
    if ("five_hour", 0) in fades:
        fade = fades[("five_hour", 0)]
        glow = _candle_glow(frame, (fx.CALM_LIGHT if calm else sum(fx._flicker(t + 1.7 * i) for i in range(len(CANDLES))) / len(CANDLES)) * fade)
        behind.alpha_composite(glow[0], (max(0, glow[1]), max(0, glow[2])))
        fx.paint(behind, _candle_draws(frame, t, fade, calm), sprites)
    for (effect, level), fade in sorted(fades.items()):
        if effect != "aura":
            continue
        strength = fx.aura_strength(level, t, calm) * fade
        behind.alpha_composite(fx._aura(shape, level, strength, (behind.width, fx.PAD_TOP + h)))
        out = fx._rim(out, shape, level, strength)
        if level >= 2 and not calm:
            draws += _aura_draws(shape, w, h, level, t, fade)
        if level >= 3 and not calm and t % 3.7 > 3.7 - 0.12:
            glitch_ = 0.25 * fade
    if ("weekly", 0) in fades:
        out = _ghost_fade(out, t, fades[("weekly", 0)], calm)
        if not calm:
            draws += _wisp_draws(shape, w, h, t, fades[("weekly", 0)])
    over = fx.paint(Image.new("RGBA", behind.size, (0, 0, 0, 0)), draws, sprites) if draws else None
    return fx.Dressed(out, behind, over, draws, glitch_)


# ---------------------------------------------------------- projection
#
#   intro: a summoning circle traces itself on the floor, four candles
#     light in turn, mist rises; bats swirl in from all round and she forms
#     out of smoke from her feet up, an ember edge where she is forming;
#     at INTRO_LOCK_S she is whole (a haunt, petals and bats scattering),
#     the candles are snuffed, the circle fades, her tag fades in.
#   outro: a haunt, the circle and candles again, and she comes apart in
#     smoke as a swarm of bats flies up off her.
#   channel: a /clear: the candles blown out and lit again, a shadow
#     passing over her.

INTRO_S = fx.INTRO_S
INTRO_LOCK_S = fx.INTRO_LOCK_S
OUTRO_S = fx.OUTRO_S
CHANNEL_S = fx.CHANNEL_S
ACT_S = {"intro": INTRO_S, "outro": OUTRO_S, "channel": CHANNEL_S}
BUILD = (0.55, 1.85)
DISSOLVE = (0.3, 1.35)
SMOKE_SOFT = 60  # levels over which smoke turns into her
EMBER = 18  # levels of the glowing edge
BAT_IN_EVERY = 0.08
BAT_IN_LIFE = 0.75
BAT_OUT_EVERY = 0.03
BAT_OUT_LIFE = 0.9

_smokes = {}
_sigils = {}


def _smoke(size, rising):
    """An "L" field (0..255) of soft smoke: where she forms first. `rising`
    weights it toward her feet (she builds up from the floor); otherwise
    it is mostly smoke, so she comes apart all over."""
    key = (size, rising)
    if key not in _smokes:
        w, h = size
        cells = (max(2, w // 10), max(2, h // 10))
        noise = Image.new("L", cells)
        noise.putdata([round(255 * _rand(i, 57 + rising)) for i in range(cells[0] * cells[1])])
        noise = noise.resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(4))
        lo, hi = noise.getextrema()
        noise = noise.point(lambda v: round(255 * (v - lo) / max(1, hi - lo)))
        k = 0.72 if rising else 0.35
        ramp = fx._column([round(255 * (1 - y / max(1, h - 1))) for y in range(h)], w)
        field = Image.blend(noise, ramp, k)
        if len(_smokes) > 4:
            _smokes.clear()
        _smokes[key] = field
    return _smokes[key]


def _smoked(frame, p, building, glow):
    """`frame` `p` (0..1) of the way formed out of smoke (`building`) or
    gone into it; an ember edge where it turns; `glow` a faint misty
    silhouette of what is not there yet."""
    w, h = frame.size
    field = _smoke((w, h), building)
    thr = -SMOKE_SOFT + p * (255 + 2 * SMOKE_SOFT)
    if building:
        shown = field.point(lambda v: max(0, min(255, round((thr - v) * 255 / SMOKE_SOFT))))
    else:
        shown = field.point(lambda v: max(0, min(255, round((v - thr) * 255 / SMOKE_SOFT))))
    ember = field.point(lambda v: round(255 * max(0.0, 1 - abs(v - thr + (SMOKE_SOFT / 2 if building else -SMOKE_SOFT / 2)) / EMBER)))
    alpha = frame.getchannel("A")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow > 0.01:
        ghost = Image.new("RGBA", (w, h), fx.PALE + (0,))
        ghost.putalpha(fx._scaled(ImageChops.multiply(alpha, ImageChops.invert(shown)), 0.2 * glow))
        out.alpha_composite(ghost)
    her = frame.copy()
    her.putalpha(ImageChops.multiply(alpha, shown))
    out.alpha_composite(her)
    lit = Image.new("RGBA", (w, h), fx.PALE + (0,))
    lit.putalpha(fx._scaled(ImageChops.multiply(ember, alpha), 0.7))
    out.alpha_composite(lit)
    return out


def _sigil(w, h):
    """The summoning circle for a frame w by h, as ("L" lines, "L" glow,
    "L" pool of light inside): two rings, runes (ticks) between them,
    four diamonds, drawn SUPER large and scaled down."""
    if (w, h) in _sigils:
        return _sigils[(w, h)]
    k = fx.SUPER
    rx, ry = w * 0.4, h * 0.042
    size = (round(rx * 2 + 24) * k, round(ry * 2 + 24) * k)
    ox, oy = size[0] / 2, size[1] / 2
    lines = Image.new("L", size, 0)
    d = ImageDraw.Draw(lines)
    for f, wd in ((1.0, 2.0), (0.8, 1.3)):
        d.ellipse((ox - rx * f * k, oy - ry * f * k, ox + rx * f * k, oy + ry * f * k), outline=255, width=round(wd * k))
    for i in range(36):
        a = math.tau * i / 36
        long_ = i % 3 == 0
        f0, f1 = (0.82, 0.98) if long_ else (0.86, 0.94)
        d.line([(ox + rx * f0 * k * math.cos(a), oy + ry * f0 * k * math.sin(a)), (ox + rx * f1 * k * math.cos(a), oy + ry * f1 * k * math.sin(a))],
               fill=255 if long_ else 170, width=round(1.1 * k))
    for i in range(4):
        a = math.tau * i / 4 + math.pi / 4
        x, y = ox + rx * 0.9 * k * math.cos(a), oy + ry * 0.9 * k * math.sin(a)
        s = 3.2 * k
        d.polygon([(x, y - s), (x + s * 0.7, y), (x, y + s), (x - s * 0.7, y)], fill=255)
    pool = Image.new("L", size, 0)
    ImageDraw.Draw(pool).ellipse((ox - rx * 0.8 * k, oy - ry * 0.8 * k, ox + rx * 0.8 * k, oy + ry * 0.8 * k), fill=50)
    glow = lines.filter(ImageFilter.GaussianBlur(3.5 * k))
    light = ImageChops.lighter(lines, glow.point(lambda a: min(255, a * 2)))
    small = (size[0] // k, size[1] // k)
    _sigils.clear()
    _sigils[(w, h)] = (light.resize(small, Image.LANCZOS), glow.resize(small, Image.LANCZOS).point(lambda a: min(255, round(a * 1.6))),
                       pool.filter(ImageFilter.GaussianBlur(3 * k)).resize(small, Image.LANCZOS))
    return _sigils[(w, h)]


def ring(w, h, brightness, spread, traced=1.0):
    """The summoning circle (effects._ring's stand-in: the carry's ring
    too): brightness 0..1, `spread` of its width wide, `traced` (0..1) of
    it drawn so far, clockwise from its front (its pool of light fading
    in meanwhile)."""
    light, glow, pool = _sigil(w, h)
    size = (max(1, round(light.width * spread)), max(1, round(light.height * spread ** 0.5)))
    if size != light.size:
        light, glow, pool = (m.resize(size, Image.BILINEAR) for m in (light, glow, pool))
    if traced < 0.999:
        sweep = Image.new("L", size, 0)
        ImageDraw.Draw(sweep).pieslice((-size[0], -size[1], 2 * size[0], 2 * size[1]), 90, 90 + 360 * traced, fill=255)
        light, glow, pool = ImageChops.multiply(light, sweep), ImageChops.multiply(glow, sweep), fx._scaled(pool, traced)
    light = ImageChops.lighter(light, pool)
    out = Image.new("RGBA", size, fx.ACCENT_LIGHT + (0,))
    out.putalpha(fx._scaled(glow, brightness))
    top = Image.new("RGBA", size, fx.PALE + (0,))
    top.putalpha(fx._scaled(light, brightness))
    out.alpha_composite(top)
    return out


def _stage(frame, height, brightness, spread, traced):
    """The canvas behind her: the circle at her feet."""
    w, h = frame.size
    canvas = Image.new("RGBA", (fx.PAD_LEFT + w + fx.PAD_RIGHT, height), (0, 0, 0, 0))
    if brightness > 0.01 and spread > 0.01 and traced > 0.01:
        cx, cy, _, _ = _floor(frame)
        img = ring(w, h, brightness, spread, traced)
        canvas.alpha_composite(img, (round(fx.PAD_LEFT + cx - img.width / 2), max(0, round(fx.PAD_TOP + cy - img.height / 2))))
    return canvas


def _mist_draws(frame, age, start, end, rise=0.22):
    """Mist rising off the circle between `start` and `end`."""
    w, h = frame.size
    cx, cy, rx, _ = _floor(frame)
    draws = []
    strength = fx._span(age, start, start + 0.3) * (1 - fx._span(age, end - 0.4, end))
    if strength <= 0.01:
        return draws
    for i in range(7):
        p = ((age - start) * 0.45 + _rand(i, 81)) % 1.0
        x = cx + rx * (2 * _rand(i, 82) - 1) * (1 - 0.3 * p)
        y = cy - h * 0.02 - p * h * rise
        draws.append(Draw("mist", x, y, 0.6 + 0.6 * p, strength * pulse(p) * 0.8))
    return draws


def _bats_in(shape, w, h, age):
    """Bats swirling in from all round, each reaching her forming edge
    where it will be when it arrives, and turning into her."""
    draws = []
    first = BUILD[0] - BAT_IN_LIFE + 0.2
    last = BUILD[1] - BAT_IN_LIFE - 0.05
    for n, since, p in fx._spawned(age - first, BAT_IN_EVERY, BAT_IN_LIFE):
        if n < 0 or n * BAT_IN_EVERY > last - first:
            continue
        arrives = first + n * BAT_IN_EVERY + BAT_IN_LIFE
        u = fx._span(arrives, *BUILD)
        feet = shape["feet"] or (0, 0, w, h)
        target = fx._row_point(shape["rows"], feet[3] - u * (feet[3] - feet[1]), _rand(n, 61))
        if not target:
            continue
        a = 2 * math.pi * _rand(n, 62)
        reach = w * (0.45 + 0.3 * _rand(n, 64))
        sx = min(w + fx.PAD_RIGHT - 10, max(10 - fx.PAD_LEFT, target[0] + reach * math.cos(a)))
        sy = min(h - 10, max(10 - fx.PAD_TOP, target[1] + reach * 1.1 * math.sin(a)))
        q = p * p
        swirl = math.sin(math.pi * p) * w * 0.08 * (1 if n % 2 else -1)
        x = sx + (target[0] - sx) * q - swirl * math.sin(a)
        y = sy + (target[1] - sy) * q + swirl * math.cos(a)
        if n % 3 == 2:
            draws.append(Draw("pixel_accent", x, y, 1.3 * (1.1 - 0.5 * q), min(1.0, p / 0.25), 300 * p))
        else:
            draws.append(Draw(_bat(age, n, "accent" if n % 4 == 1 else "main", 9.0), x, y, 0.75 * (1.1 - 0.6 * q),
                              min(1.0, p / 0.25) * min(1.0, (1 - p) / 0.15)))
    return draws


def _bats_out(shape, w, h, age):
    """A swarm of bats (and petals) flying up and out off her as she comes
    apart."""
    draws = []
    for n, since, p in fx._spawned(age - DISSOLVE[0], BAT_OUT_EVERY, BAT_OUT_LIFE):
        if n < 0 or n * BAT_OUT_EVERY > DISSOLVE[1] - DISSOLVE[0]:
            continue
        feet = shape["feet"] or (0, 0, w, h)
        start = fx._row_point(shape["rows"], feet[1] + (feet[3] - feet[1]) * (0.05 + 0.85 * _rand(n, 72)), _rand(n, 71))
        if not start:
            continue
        side = 1 if start[0] > w / 2 else -1
        rise = 1 - (1 - p) ** 2
        x = start[0] + side * w * (0.1 + 0.25 * _rand(n, 73)) * rise + math.sin(p * 6 + n) * 4
        y = max(10 - fx.PAD_TOP, start[1] - h * (0.18 + 0.15 * _rand(n, 74)) * rise)
        alpha = min(1.0, p / 0.1) * (1 - p) ** 1.2
        if n % 3 == 2:
            draws.append(Draw("pixel_accent" if n % 2 else "pixel_main", x, y, 1.3 * (1 - 0.3 * p), alpha, 260 * p))
        else:
            draws.append(Draw(_bat(age, n, "accent" if n % 4 == 1 else "main", 9.0), x, y, 0.55 + 0.35 * p, alpha, 10 * side * (1 - p)))
    return draws


def _lock_pop(w, h, age):
    """She is whole: petals and bats scattering out from her head, a glint."""
    draws = []
    p = (age - INTRO_LOCK_S) / 0.8
    if not 0 <= p < 1:
        return draws
    hx, hy = HEAD_AT[0] * w, HEAD_AT[1] * h
    reach = 1 - (1 - p) ** 3
    for i in range(10):
        a = math.radians(-90 + 36 * i + 18)
        r = w * (0.14 + 0.24 * reach)
        sprite = _bat(age, i, "main") if i % 3 == 0 else ("pixel_accent" if i % 2 else "pixel_main")
        draws.append(Draw(sprite, hx + r * math.cos(a), hy + r * math.sin(a) * 0.85,
                          (0.8 if sprite.startswith("bat") else 1.5) * (1 - 0.35 * p) * pop(age, INTRO_LOCK_S, 0.15), 1 - p ** 3,
                          0.0 if sprite.startswith("bat") else 200 * p))
    draws.append(Draw("twinkle", hx + 0.13 * w, hy - 0.09 * h, 2.2 * pulse(p / 0.6), pulse(p / 0.6), 45 * p))
    return draws


def _ghostly(frame, amount):
    """`frame` still half spirit: a pale tint, a little see-through."""
    if amount <= 0.01:
        return frame
    alpha = frame.getchannel("A")
    tint = Image.new("RGBA", frame.size, fx.PALE + (0,))
    tint.putalpha(fx._scaled(alpha, 0.35 * amount))
    out = frame.copy()
    out.alpha_composite(tint)
    out.putalpha(fx._scaled(out.getchannel("A"), 1 - 0.3 * amount))
    return out


def _snuffed(age, start, every=0.08):
    """How lit each candle is: snuffed one after another from `start`."""
    return [1 - fx._span(age, start + every * i, start + every * i + 0.12) for i in range(len(CANDLES))]


def _smoke_puffs(frame, age, start):
    """A wisp of smoke off each candle as it is snuffed."""
    w, h = frame.size
    cx, cy, rx, ry = _floor(frame)
    draws = []
    for i, a in enumerate(CANDLES):
        p = (age - start - 0.08 * i) / 0.7
        if 0 <= p < 1:
            r = math.radians(a)
            draws.append(Draw("wisp", cx + rx * math.cos(r) + 3 * math.sin(p * 6), cy + ry * math.sin(r) - 0.05 * h - p * 0.06 * h,
                              0.5 + 0.6 * p, pulse(p) * 0.8))
    return draws


def _intro(frame, age, t, height):
    w, h = frame.size
    shape = fx._outline(frame)
    traced = fx._span(age, 0.0, 0.45)
    bright = pop(age, 0.0, 0.4) * (1 + 0.5 * pulse((age - 2.0) / 0.3))
    spread = 1 - fx._span(age, 2.05, 2.45) if age > 2.05 else 1.0
    behind = _stage(frame, height, min(1.3, bright), spread, traced)
    her = _smoked(frame, fx._span(age, *BUILD), True, fx._span(age, 0.4, 0.8)) if age < BUILD[1] else frame
    her = _ghostly(her, 1 - fx._span(age, INTRO_LOCK_S - 0.3, INTRO_LOCK_S + 0.15))
    lit = [fx._span(age, 0.3 + 0.13 * i, 0.4 + 0.13 * i) for i in range(len(CANDLES))]
    lit = [a * b for a, b in zip(lit, _snuffed(age, 2.05))]
    candles = _candle_draws(frame, t, 1 - fx._span(age, 2.2, 2.5), False, lit)
    draws = (candles + _mist_draws(frame, age, 0.3, 2.4) + _bats_in(shape, w, h, age) + _lock_pop(w, h, age)
             + _smoke_puffs(frame, age, 2.05))
    glitch_ = 0.7 * max(0.0, 1 - (age - INTRO_LOCK_S) / 0.25) if age >= INTRO_LOCK_S else 0.0
    return fx.Act(her, behind, draws, fx._span(age, 2.1, 2.5), glitch_)


def _outro(frame, age, t, height):
    w, h = frame.size
    shape = fx._outline(frame)
    her = _smoked(frame, fx._span(age, *DISSOLVE), False, 0.0) if age > DISSOLVE[0] else frame
    her = _ghostly(her, fx._span(age, 0.05, 0.4))
    traced = fx._span(age, 0.0, 0.3)
    bright = pop(age, 0.0, 0.3) * (1 + 0.5 * pulse((age - 1.4) / 0.3))
    spread = 1 - fx._span(age, 1.45, 1.75) if age > 1.45 else 1.0
    behind = _stage(frame, height, min(1.3, bright), spread, traced)
    lit = [fx._span(age, 0.1 + 0.06 * i, 0.2 + 0.06 * i) for i in range(len(CANDLES))]
    lit = [a * b for a, b in zip(lit, _snuffed(age, 1.3))]
    draws = (_candle_draws(frame, t, 1 - fx._span(age, 1.5, 1.75), False, lit) + _mist_draws(frame, age, 0.1, 1.7, 0.3)
             + _bats_out(shape, w, h, age) + _smoke_puffs(frame, age, 1.3))
    glitch_ = 0.85 * max(0.0, 1 - age / 0.3)
    return fx.Act(her, behind, draws, 1 - fx._span(age, 0.0, 0.35), glitch_)


def _channel(frame, age, t, height):
    """The candles blown out and lit again: a shadow dips over her, a band
    of mist rolls down her, a haunt."""
    p = min(1.0, age / CHANNEL_S)
    h = frame.height
    shadow = pulse(min(1.0, p / 0.8))
    her = frame
    if shadow > 0.01:
        dark = Image.new("RGBA", frame.size, fx.MAIN_SHADE + (0,))
        dark.putalpha(fx._scaled(frame.getchannel("A"), 0.55 * shadow))
        her = frame.copy()
        her.alpha_composite(dark)
    her = fx._band(her, -0.1 * h + 1.2 * h * p, h * 0.07, 0.7 * (1 - p * p))
    return fx.Act(her, None, [], 1.0, 0.9 * (1 - p) ** 1.5)


def projection(kind, frame, age, t, height):
    """effects.projection in her style (calm is effects' plain fade)."""
    return {"intro": _intro, "outro": _outro, "channel": _channel}[kind](frame, age, t, height)
