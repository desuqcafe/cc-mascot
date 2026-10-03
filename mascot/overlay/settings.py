"""The mascot's settings: `settings.json` in the mascot folder, shared by every
session. The mod writes it (/mascot size, calm, aura, beam after...), so does
the settings window, and anyone may edit it by hand; every overlay follows it
live. A key left out is its default, and so is a value that is not a valid
one, so a slip in the file never breaks a mascot:

    size           her height in px, SIZE_RANGE (420)
    calm           no glitch, particles, flicker or flashes (false)
    aura           the context, in tokens, at which each of her aura's three
                   levels starts, ascending; false: no aura
                   ([300000, 400000, 500000])
    beamAfter      minutes a round of work lasts before it ends in the beam,
                   BEAM_RANGE; false: never (2)
    beamForAgents  a round that used subagents or background agents ends in
                   the beam too (true)
    checkUpdates   the mod looks for a newer release on GitHub once a day
                   (false: the mascot never goes online)

The mod (hooks/register.tsx) checks the same keys by the same rules.
"""

import json
import os
from collections import namedtuple

FILE = "settings.json"

Settings = namedtuple("Settings", "size calm aura beamAfter beamForAgents checkUpdates")
DEFAULTS = Settings(size=420, calm=False, aura=(300_000, 400_000, 500_000), beamAfter=2, beamForAgents=True,
                    checkUpdates=False)

SIZE_RANGE = (240, 640)
SIZES = {"small": 300, "normal": 420, "large": 560}
AURA_RANGE = (10_000, 10_000_000)
BEAM_RANGE = (1, 120)


def _number(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high


def check(key, value):
    """`value` as the setting `key` takes it, or None when it is not a valid one."""
    if key == "size":
        return round(value) if _number(value, *SIZE_RANGE) else None
    if key in ("calm", "beamForAgents", "checkUpdates"):
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
    return None


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
        values[key] = getattr(DEFAULTS, key) if value is None else value
    return Settings(**values)


def save(path, **changes):
    """Sets keys in the file at `path`, keeping whatever else it holds. A
    default value (or None) takes its key out, so the file holds only what
    was changed. Written whole and swapped in: a reader never sees half."""
    raw = read_raw(path)
    for key, value in changes.items():
        value = None if value is None else check(key, value)
        if value is None or value == getattr(DEFAULTS, key):
            raw.pop(key, None)
        else:
            raw[key] = list(value) if isinstance(value, tuple) else value
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp = f"{path}.{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    os.replace(temp, path)


def reset(path):
    """Every setting back to its default."""
    save(path, **{key: None for key in Settings._fields})
