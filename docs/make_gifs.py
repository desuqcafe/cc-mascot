"""Renders the README's GIFs with the overlay's own drawing code: her frames,
mood symbols, glitch, status effects and the hologram intro, exactly as the
overlay composes them (effects.py is pure functions of time), onto a dark
backdrop since GIFs have no soft alpha.

    python docs/make_gifs.py [--character NAME] [hero] [moods] [held] [beam] [magic] [status] [social] [settings]

Writes docs/media/*.gif, and settings.png (the settings window); another
character's (`--character yunseul`: her art, colors and style) into
docs/media/<name>/. MASCOT_DIR renders another copy of the plugin folder
instead of this repo's.
"""

import json

import os
import re
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASCOT = os.environ.get("MASCOT_DIR") or os.path.join(ROOT, "mascot")
sys.path.insert(0, os.path.join(MASCOT, "overlay"))

import effects as fx  # noqa: E402
from mascot_overlay import HEIGHT, THEME_FILE, prepare, tag_image  # noqa: E402

ARGS = sys.argv[1:]
CHARACTER = "miku"
if "--character" in ARGS:
    i = ARGS.index("--character")
    CHARACTER = ARGS[i + 1]
    del ARGS[i:i + 2]
FRAMES = os.path.join(MASCOT, "frames", CHARACTER)
OUT = os.path.join(ROOT, "docs", "media", *([] if CHARACTER == "miku" else [CHARACTER]))
with open(os.path.join(FRAMES, THEME_FILE), encoding="utf-8") as f:
    fx.use(fx.look_of(json.load(f)))
BACKDROP = (22, 27, 34)  # GitHub dark's canvas, reads as a card on light too
FPS = 20
TAG_PX = 15

_frames = {}


def frames(mood):
    """A mood's frames and fps; a mood without art plays idle's."""
    if mood not in _frames:
        names = [n for n in os.listdir(FRAMES) if re.fullmatch(rf"{mood}-\d+\.png", n)]
        names.sort(key=lambda n: int(n.rsplit("-", 1)[1][:-4]))
        _frames[mood] = [prepare(os.path.join(FRAMES, n), HEIGHT) for n in names]
    return (_frames[mood], 12) if _frames[mood] else frames("idle")


def render(mood, t, age, status=fx.CALM, act=None, tag=None):
    """One window image, as mascot_overlay's draw() makes it (the beam's on
    its larger canvas while it bursts: crop with `steady`)."""
    pics, fps = frames(mood)
    frame = pics[int(max(0.0, age) * fps) % len(pics)]
    height = fx.PAD_TOP + frame.height + fx.UNDER_GAP + tag.height
    if act:
        kind, since = act
        shown = fx.projection(kind, frame, t - since, t, height)
        glitch = max(shown.glitch, fx.glitch_amount(mood, age) if age >= 0 else 0.0)
        draws = list(shown.draws)
        if age >= 0:
            draws += fx.placements(mood, frame.width, frame.height, t, age)
        return fx.compose(fx.glitch(shown.frame, glitch, t), draws, SPRITES, fx.faded(tag, shown.tag), shown.behind)
    look = fx.dress(frame, status, status, 99.0, t, height, SPRITES)
    her = look.frame if mood != "beam" else fx.recoil(look.frame, age)
    her = fx.glitch(her, max(fx.glitch_amount(mood, age), look.glitch), t)
    draws = fx.placements(mood, frame.width, frame.height, t, age)
    if mood == "beam" and fx.beam_wide(age):
        image = fx.compose(her, [], SPRITES, tag, look.behind, look.over)
        return fx.beamed(image, her.width, her.height, age, t, draws, SPRITES)
    return fx.compose(her, draws, SPRITES, tag, look.behind, look.over)


def steady(images, pad):
    """Images some of which are `pad` larger on every side (the beam's), all
    on one canvas with her in the same place."""
    big = max(images, key=lambda im: im.width)
    out = []
    for im in images:
        card = Image.new("RGBA", big.size, (0, 0, 0, 0))
        off = 0 if im.size == big.size else pad
        card.alpha_composite(im, (off, off))
        out.append(card)
    return out


def flatten(img, scale, size=None):
    size = size or img.size
    card = Image.new("RGBA", size, BACKDROP + (255,))
    card.alpha_composite(img, ((size[0] - img.width) // 2, size[1] - img.height))
    card = card.convert("RGB")
    if scale != 1:
        card = card.resize((round(card.width * scale), round(card.height * scale)), Image.LANCZOS)
    return card


def save(name, images):
    path = os.path.join(OUT, name)
    pal = images[len(images) // 2].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    quantized = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in images]
    quantized[0].save(path, save_all=True, append_images=quantized[1:], duration=1000 // FPS, loop=0, optimize=True)
    print(f"{name}: {len(images)} frames, {images[0].size}, {os.path.getsize(path) // 1024} KB")


def hero():
    """The intro, then a turn: thinking, working, happy, back to idle."""
    tag = tag_image("my-app", TAG_PX)
    script = [("idle", 0.0, 2.9), ("thinking", 2.9, 5.4), ("working", 5.4, 8.4), ("happy", 8.4, 11.4), ("idle", 11.4, 12.4)]
    images = []
    for i in range(int(12.4 * FPS)):
        t = i / FPS
        mood, start, _ = next(s for s in script if s[1] <= t < s[2])
        act = ("intro", 0.0) if t < fx.INTRO_S else None
        age = t - start if mood != "idle" or start else t - fx.INTRO_LOCK_S
        images.append(render(mood, t, age, act=act, tag=tag))
    size = (max(im.width for im in images), max(im.height for im in images))
    save("hero.gif", [flatten(im, 0.75, size) for im in images])


def moods():
    tag = tag_image("my-app", TAG_PX)
    for mood in ("thinking", "working", "waiting", "worried", "happy", "error", "sleepy"):
        start = 0.0 if mood in ("happy", "error") else 1.0
        loop = max(3.0, len(frames(mood)[0]) / 12)  # a whole loop of her art, so the GIF repeats smoothly
        images = [render(mood, 100 + i / FPS, start + i / FPS, tag=tag) for i in range(round(loop * FPS))]
        size = (max(im.width for im in images), max(im.height for im in images))
        save(f"{mood}.gif", [flatten(im, 0.5, size) for im in images])


def held():
    """Her held pose's loop, as she hangs while carried (the swing itself is
    the carry's, from the pointer's motion)."""
    tag = tag_image("my-app", TAG_PX)
    images = [render("held", 100 + i / FPS, i / FPS, tag=tag) for i in range(3 * FPS)]
    save("held.gif", [flatten(im, 0.5) for im in images])


def beam():
    """The beam from the start, then a moment of afterglow."""
    tag = tag_image("my-app", TAG_PX)
    images = steady([render("beam", 100 + i / FPS, i / FPS, tag=tag) for i in range(int(3.4 * FPS))], fx.BEAM_PAD)
    save("beam.gif", [flatten(im, 0.5) for im in images])


def pointer_image(scale=1.0):
    """Windows' arrow pointer, white in a black edge, its tip at (1, 1)."""
    from PIL import ImageDraw

    tip = [(0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12)]
    k = 1.5 * scale
    img = Image.new("RGBA", (round(16 * k) + 3, round(23 * k) + 3), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([(1 + x * k, 1 + y * k) for x, y in tip], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255),
                                width=max(1, round(k)))
    return img


def magic():
    """Her call: happy as a round ends, magic flies from her heart hands to
    the pointer up and right of her, bursts, circles it, and goes at a click."""
    tag = tag_image("my-app", TAG_PX)
    first = render("happy", 100, 0.0, tag=tag)
    w, h = frames("happy")[0][0].size
    card_w, card_h = round(first.width * 2.9), round(first.height * 1.25)
    at = (24, card_h - first.height)  # her window's top left on the card
    hands = fx.magic_from(w, h)
    start = (at[0] + fx.PAD_LEFT + hands[0], at[1] + fx.PAD_TOP + hands[1])
    target = (card_w - round(0.16 * card_w), round(0.2 * card_h))
    flight = fx.magic_flight(start, target)
    leaves = fx.CHARGE_S  # as the overlay sends it: as she fires her finish
    ended = flight + 2.6  # a click, this long after it left
    arrow = pointer_image()
    images = []
    for i in range(int((leaves + ended + fx.MAGIC_LEAVE_S + 0.4) * FPS)):
        t = i / FPS
        card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        card.alpha_composite(render("happy", 100 + t, t, tag=tag), at)
        age = t - leaves
        gone = ended if age >= ended else None
        if age >= 0 and not fx.magic_over(age, gone):
            # Drawn around the comet's head, as in its own window.
            head = fx.magic_head(start, target, flight, age)
            fx.paint(card, fx.magic(start, target, flight, age, 100 + t, gone), SPRITES, head)
        card.alpha_composite(arrow, (target[0] - 1, target[1] - 1))
        images.append(card)
    save("magic.gif", [flatten(im, 0.5) for im in images])


def status():
    tag = tag_image("my-app", TAG_PX)
    looks = {
        "aura": fx.Status(1),
        "sparkles": fx.Status(2),
        "overload": fx.Status(3),
        "stage-light": fx.Status(0, True),
        "hologram": fx.Status(0, False, True),
    }
    for name, look in looks.items():
        images = [render("idle", 200 + i / FPS, 5 + i / FPS, status=look, tag=tag) for i in range(int(3.7 * FPS))]
        size = (max(im.width for im in images), max(im.height for im in images))
        save(f"status-{name}.gif", [flatten(im, 0.5, size) for im in images])


def use_character(name):
    """Draws `name` from now on: her frames, look and sprites."""
    global FRAMES, SPRITES
    FRAMES = os.path.join(MASCOT, "frames", name)
    with open(os.path.join(FRAMES, THEME_FILE), encoding="utf-8") as f:
        fx.use(fx.look_of(json.load(f)))
    _frames.clear()
    SPRITES = fx.build_sprites(HEIGHT)


def social():
    """GitHub's social preview (1280x640): the title, teal into crimson,
    over two of Miku's moods and two of Yunseul's. Uploaded by hand:
    Settings, General, Social preview."""
    from PIL import ImageDraw, ImageFont

    from settings_window import blend

    no_tag = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    shots = []
    for name, moods in (("miku", [("thinking", 101.3, 1.3, fx.CALM), ("happy", 100.6, 0.6, fx.CALM)]),
                        ("yunseul", [("working", 102.0, 2.0, fx.CALM), ("idle", 200.4, 5.4, fx.Status(2))])):
        use_character(name)
        shots += [render(mood, t, age, status=status, tag=no_tag) for mood, t, age, status in moods]
    use_character(CHARACTER)
    card = Image.new("RGBA", (1280, 640), BACKDROP + (255,))
    scale = 0.9
    shots = [s.resize((round(s.width * scale), round(s.height * scale)), Image.LANCZOS) for s in shots]
    gap = (card.width - sum(s.width for s in shots)) // (len(shots) + 1)
    x = gap
    for s in shots:
        card.alpha_composite(s, (x, card.height - s.height - 8))
        x += s.width + gap
    # The title, from Miku's teal around the color wheel to Yunseul's crimson.
    title = ImageFont.truetype("segoeuib.ttf", 64)
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).text((card.width // 2, 70), "cc-mascot", font=title, fill=255, anchor="mm")
    left, _, right, _ = mask.getbbox()
    ramp = Image.new("RGBA", card.size)
    for column in range(left, right):
        color = blend((57, 197, 187), (202, 39, 57), (column - left) / max(1, right - left - 1))
        ramp.paste(color + (255,), (column, 0, column + 1, card.height))
    card.paste(ramp, (0, 0), mask)
    sub = ImageFont.truetype("segoeui.ttf", 30)
    ImageDraw.Draw(card).text((card.width // 2, 132), "anime desktop mascots for Claude Code", font=sub,
                              fill=(201, 209, 217), anchor="mm")
    path = os.path.join(OUT, "social-preview.png")
    card.convert("RGB").save(path, optimize=True)
    print(f"social-preview.png: {os.path.getsize(path) // 1024} KB")


def settings():
    """The settings window at its defaults, drawn off screen as it would
    show on a display at 125%."""
    import tempfile

    import settings_window

    app = settings_window.App(tempfile.mkdtemp(), FRAMES, show=False, scale=1.25)
    try:
        path = os.path.join(OUT, "settings.png")
        app.image().save(path, optimize=True)
        print(f"settings.png: {os.path.getsize(path) // 1024} KB")
    finally:
        app.root.destroy()


SPRITES = fx.build_sprites(HEIGHT)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    which = ARGS or ["hero", "moods", "held", "beam", "magic", "status", "settings"] + (["social"] if CHARACTER == "miku" else [])
    for job in which:
        globals()[job]()
