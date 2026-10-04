"""The mascot's settings: `settings.json` in the mascot folder, shared by every
session. The mod writes it (/mascot size, calm, aura, beam after...), so does
the settings window, and anyone may edit it by hand; every overlay follows it
live. A key left out is its default, and so is a value that is not a valid
one, so a slip in the file never breaks a mascot:

    size           her height in px, SIZE_RANGE (420)
    calm           no glitch, particles, flicker or flashes (false)
    smooth         her status's particles move with her symbols, 36 fps
                   over her 12 fps frames, rather than at 12: smoother,
                   more CPU while one moves (false)
    aura           the context, in tokens, at which each of her aura's three
                   levels starts, ascending; false: no aura
                   ([300000, 400000, 500000])
    beamAfter      minutes a round of work lasts before it ends in the beam,
                   BEAM_RANGE; false: never (2)
    beamForAgents  a round that used subagents or background agents ends in
                   the beam too (true)
    magicAfter     minutes a round of work lasts before its end sends magic
                   to your pointer, MAGIC_RANGE (0: every round); false:
                   never (false)
    checkUpdates   the mod looks for a newer release on GitHub once a day
                   (false: the mascot never goes online)
    sound          she plays sounds (false); hidden, or while the screen
                   is dark or locked, she is quiet whatever this says
    volume         her sounds' volume, VOLUME_RANGE (60)
    sounds         a sound per moment (MOMENTS): false none, true her own,
                   or the name of a file of yours in the mascot folder's
                   sounds/ (.wav or .mp3, SOUND_FILE). A moment left out,
                   or not valid, is its default (SOUNDS)
    waitingAfter   seconds she waits on you before her waiting sound,
                   WAITING_RANGE (30)
    nudge          once she has waited on you that long, her messenger
                   calls and her terminal's taskbar button flashes; a
                   click on her brings her terminal forward (false)
    remote         her messenger brings in a prompt sent from Remote
                   Control (a phone, the web) or a chat (false)
    away           what happened while you were away, on a note she holds
                   once you are back (false)

The mod (hooks/register.tsx) checks the same keys by the same rules.
"""

import json
import os
import re
from collections import namedtuple

FILE = "settings.json"

# The moments she has a sound for, and which of them sound once `sound` is
# on: the ones that tell you something. Coming and going (every show and
# hide) only when asked for.
MOMENTS = ("waiting", "done", "beam", "error", "magic", "intro", "outro")
SOUNDS = {"waiting": True, "done": True, "beam": True, "error": True, "magic": False, "intro": False, "outro": False}
# A file of yours: a bare name (no folder: it is looked for in sounds/ and
# nowhere else), .wav or .mp3. The mod checks names by the same pattern.
SOUND_FILE = re.compile(r'^[^\\/:*?"<>|\x00-\x1f]{1,120}\.(wav|mp3)$', re.IGNORECASE)

Settings = namedtuple("Settings", "size calm smooth aura beamAfter beamForAgents magicAfter checkUpdates "
                                  "sound volume sounds waitingAfter nudge remote away")
DEFAULTS = Settings(size=420, calm=False, smooth=False, aura=(300_000, 400_000, 500_000), beamAfter=2,
                    beamForAgents=True, magicAfter=False, checkUpdates=False,
                    sound=False, volume=60, sounds=dict(SOUNDS), waitingAfter=30,
                    nudge=False, remote=False, away=False)

SIZE_RANGE = (240, 640)
SIZES = {"small": 300, "normal": 420, "large": 560}
AURA_RANGE = (10_000, 10_000_000)
BEAM_RANGE = (1, 120)
MAGIC_RANGE = (0, 120)
VOLUME_RANGE = (0, 100)
WAITING_RANGE = (10, 300)


def _number(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def check(key, value):
    """`value` as the setting `key` takes it, or None when it is not a valid one."""
    if key == "size":
        return round(value) if _number(value, *SIZE_RANGE) else None
    if key in ("calm", "smooth", "beamForAgents", "checkUpdates", "sound", "nudge", "remote", "away"):
        return value if isinstance(value, bool) else None
    if key == "aura":
        if value is False:
            return False
        if isinstance(value, (list, tuple)) and len(value) == 3 and all(_number(v, *AURA_RANGE) for v in value):
            tiers = tuple(round(v) for v in value)
            return tiers if tiers[0] < tiers[1] < tiers[2] else None
        return None
    if key == "beamAfter":
        if value is False:
            return False
        return round(value) if _number(value, *BEAM_RANGE) else None
    if key == "magicAfter":
        if value is False:
            return False
        return round(value) if _number(value, *MAGIC_RANGE) else None
    if key == "volume":
        return round(value) if _number(value, *VOLUME_RANGE) else None
    if key == "waitingAfter":
        return round(value) if _number(value, *WAITING_RANGE) else None
    if key == "sounds":
        # Every moment, each on its own: one not valid is its default alone.
        if not isinstance(value, dict):
            return None
        out = dict(SOUNDS)
        for moment in MOMENTS:
            choice = sound_choice(value.get(moment))
            if choice is not None:
                out[moment] = choice
        return out
    return None


def sound_choice(value):
    """A moment's sound as `sounds` takes it (False, True or a file's name),
    or None when it is not a valid one."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip() == value and SOUND_FILE.match(value):
        return value
    return None


def written(key, value):
    """A checked `value` as the file holds it: `sounds` keeps only the
    moments that differ from their defaults."""
    if key == "sounds":
        return {m: v for m, v in value.items() if v is not SOUNDS[m]}
    return list(value) if isinstance(value, tuple) else value


def default(key):
    """The setting `key`'s default, a copy of it when it is a dict (`sounds`):
    a change to one Settings' never reaches DEFAULTS."""
    value = getattr(DEFAULTS, key)
    return dict(value) if isinstance(value, dict) else value


def read_raw(path):
    """The file's object as written (unchecked); {} when there is none."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load(path):
    """Settings from the file at `path`, every key checked; defaults for the rest."""
    raw = read_raw(path)
    values = {}
    for key in Settings._fields:
        value = check(key, raw.get(key)) if key in raw else None
        values[key] = default(key) if value is None else value
    return Settings(**values)


def save(path, **changes):
    """Sets keys in the file at `path`, keeping whatever else it holds. A
    default value (or None) takes its key out, so the file holds only what
    was changed. Written whole and swapped in: a reader never sees half."""
    raw = read_raw(path)
    for key, value in changes.items():
        value = None if value is None else check(key, value)
        # Compared as written, as the mod does: 0 minutes is not false.
        if value is None or json.dumps(value) == json.dumps(getattr(DEFAULTS, key)):
            raw.pop(key, None)
        else:
            raw[key] = written(key, value)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    os.replace(temp, path)


def reset(path):
    """Every setting back to its default."""
    save(path, **{key: None for key in Settings._fields})
