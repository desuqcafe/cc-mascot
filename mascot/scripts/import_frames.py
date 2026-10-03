"""Copies a character's mood art into the mod's frames/<character>/ folder,
lined up with idle.

    python scripts/import_frames.py [--character NAME] [folder with the art]

The character defaults to miku, the folder to the art/ folder beside the mod.
A PNG named for the character and a mood is picked up (Miku_Idle.png), and so
is one named for the mood alone (happy.png); another character's art in the
same folder (Teto_Idle.png) is left out. A number after the mood makes it a
flipbook frame (Miku_Working_1.png, working-2.png), played in order. Each
frame is shifted so its feet land exactly where idle's do, which keeps the
character from hopping as frames change, then saved at 512x768. What floats
apart from the character is dropped first: a mood's symbol drawn into the art
(a bubble, notes), which the overlay now draws itself. A mood's old frames
are replaced, so a mood never mixes old and new art.

A mood marked rigged in the frames folder's moods.json keeps its frames: they
are a rig's loop (rig/animate.py --export), made from the art, not the art.

`/mascot character NAME` then picks the character for a project's sessions.
"""

import json
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw

MOODS = ("idle", "thinking", "working", "happy", "error", "waiting", "worried", "sleepy")
SIZE = (512, 768)
HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES_ROOT = os.path.normpath(os.path.join(HERE, "..", "frames"))
DEFAULT_ART = os.path.normpath(os.path.join(HERE, "..", "..", "art"))
DEFAULT_CHARACTER = "miku"


def solid(img):
    return img.getchannel("A").point(lambda a: 255 if a > 127 else 0)


def feet(img):
    """The bottom row of the character, and the middle of its boots."""
    mask = solid(img)
    box = mask.getbbox()
    if not box:
        raise ValueError("image is fully transparent")
    bottom = box[3]
    band = mask.crop((0, max(0, bottom - img.height // 10), img.width, bottom)).getbbox()
    return bottom, (band[0] + band[2]) / 2


def body_only(img):
    """The character without what floats apart from her: a mood's symbol drawn
    into the art (a bubble, notes, sparkles), which the overlay now draws
    itself. Keeps every piece at least a twentieth the size of the biggest."""
    mask = img.getchannel("A").point(lambda a: 255 if a > 16 else 0)
    pieces = []
    while len(pieces) < 250:
        box = mask.point(lambda v: 255 if v == 255 else 0).getbbox()
        if not box:
            break
        row = mask.crop((box[0], box[1], box[2], box[1] + 1))
        x = box[0] + list(row.getdata()).index(255)
        label = len(pieces) + 1
        ImageDraw.floodfill(mask, (x, box[1]), label, thresh=0)
        pieces.append(mask.histogram()[label])
    if not pieces:
        return img
    biggest = max(pieces)
    keep = [i + 1 for i, n in enumerate(pieces) if n * 20 >= biggest]
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), mask.point(lambda v: 255 if v in keep else 0)))
    return out


def is_for(name, character):
    """Whether a file is this character's art: named for it, or for a mood alone."""
    lower = name.lower()
    return re.match(rf"{re.escape(character.lower())}[-_ ]", lower) is not None or lower.startswith(MOODS)


def find_art(src, character):
    """{mood: [(number or None, path)]}, flipbook frames in order."""
    found = {}
    for name in sorted(os.listdir(src)):
        if not name.lower().endswith(".png") or not is_for(name, character):
            continue
        for mood in MOODS:
            match = re.search(rf"(?:^|[^a-z]){mood}(?:[-_ ]?(\d+))?(?:[^a-z0-9]|$)", name.lower())
            if match:
                number = int(match.group(1)) if match.group(1) else None
                found.setdefault(mood, []).append((number, os.path.join(src, name)))
    for mood, items in found.items():
        numbered = sorted(i for i in items if i[0] is not None)
        found[mood] = numbered or items[:1]
    return found


def rigged_moods(frames):
    """The moods whose frames a rig made (moods.json in the frames folder)."""
    try:
        with open(os.path.join(frames, "moods.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    return {mood for mood, entry in data.items() if isinstance(entry, dict) and entry.get("rigged") is True}


def clear_mood(frames, mood):
    for name in os.listdir(frames):
        if re.fullmatch(rf"{mood}(-\d+)?\.png", name, re.IGNORECASE):
            os.remove(os.path.join(frames, name))


def parse_args(argv):
    """(character, art folder) from the command line, or None when it makes no sense."""
    args = list(argv)
    character = DEFAULT_CHARACTER
    if args[:1] == ["--character"]:
        if len(args) < 2 or not re.fullmatch(r"[A-Za-z0-9_-]+", args[1]):
            return None
        character, args = args[1].lower(), args[2:]
    if len(args) > 1:
        return None
    return character, (args[0] if args else DEFAULT_ART)


def main():
    parsed = parse_args(sys.argv[1:])
    if parsed is None:
        sys.exit(__doc__)
    character, src = parsed
    found = find_art(src, character)
    if "idle" not in found:
        sys.exit(f"No idle image for {character} in {src}: it is the one every other frame lines up with.")

    idle = Image.open(found["idle"][0][1]).convert("RGBA")
    anchor_y, anchor_x = feet(idle)
    frames = os.path.join(FRAMES_ROOT, character)
    os.makedirs(frames, exist_ok=True)
    print(f"Importing {character} into {frames}")
    rigged = rigged_moods(frames)
    for mood, items in found.items():
        if mood in rigged:
            print(f"{mood}: rigged, frames kept (rig/animate.py --export remakes them)")
            continue
        clear_mood(frames, mood)
        for index, (number, path) in enumerate(items, start=1):
            img = body_only(Image.open(path).convert("RGBA"))
            if img.size != idle.size:
                img = img.resize(idle.size, Image.LANCZOS)
            bottom, center = feet(img)
            dx, dy = round(anchor_x - center), anchor_y - bottom
            aligned = Image.new("RGBA", img.size, (0, 0, 0, 0))
            aligned.paste(img, (dx, dy))
            out = f"{mood}-{index}.png" if number is not None else f"{mood}.png"
            aligned.resize(SIZE, Image.LANCZOS).save(os.path.join(frames, out), optimize=True)
            print(f"{out:14} <- {os.path.basename(path)}  shifted {dx:+d},{dy:+d}")
    missing = [m for m in MOODS if m not in found]
    if missing:
        print("No art for:", ", ".join(missing), "(the overlay shows idle, altered)")


if __name__ == "__main__":
    main()
