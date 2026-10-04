"""Away notes, for the `away` setting: what happened while you were away,
on a note she holds once you are back.

You are away while nobody can see her (presence.py: every display off, or
the PC locked) or nobody has touched the keyboard or mouse for AWAY_S
(`idle_s`, GetLastInputInfo); from the last input on, so what happened
in those minutes counts too (`recent` keeps it). Meanwhile the overlay
tells it what happens (`saw`): a round of work done, a turn that died, her
waiting on you, a prompt from elsewhere. Back, with something to tell, she
holds her note (`note`) until the card has shown it to you (the overlay
calls `read` as the card closes) or for NOTE_KEEP_S. Only her own session's
moments, in the local time of each.
"""

import ctypes
import ctypes.wintypes as wintypes
import datetime
from collections import namedtuple

AWAY_S = 5 * 60
NOTE_KEEP_S = 60 * 60
MOST = 5  # lines on a note

# What happened (`kind`: "done", "beam", "error", "waiting", "visit") and
# when (epoch s); `about` says more where there is more: a channel's name.
Moment = namedtuple("Moment", "kind at about")
Moment.__new__.__defaults__ = (None,)

# The note: when you went away and came back (epoch s), and what happened.
Note = namedtuple("Note", "since back moments")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_s():
    """Seconds since the last keyboard or mouse input anywhere."""
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000


def clock(at):
    return datetime.datetime.fromtimestamp(at).strftime("%H:%M")


def how_long(seconds):
    mins = max(1, round(seconds / 60))
    if mins < 60:
        return f"{mins} min"
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins:02d}m"


def lines_of(moments):
    """The note's lines for `moments`, oldest first, at most MOST."""
    lines = []

    def tell(kinds, one, many):
        seen = [m for m in moments if m.kind in kinds]
        if seen:
            last = clock(seen[-1].at)
            lines.append(one.format(last) if len(seen) == 1 else many.format(len(seen), last))

    tell(("done", "beam"), "Work done at {}", "{} rounds of work done, the last at {}")
    tell(("error",), "A turn failed at {}", "{} turns failed, the last at {}")
    tell(("waiting",), "Waited on you from {}", "Waited on you {} times, the last from {}")
    visits = [m for m in moments if m.kind == "visit"]
    if visits:
        where = sorted({m.about or "Remote Control" for m in visits})
        words = "a prompt" if len(visits) == 1 else f"{len(visits)} prompts"
        lines.append(f"{words[0].upper()}{words[1:]} from {', '.join(where)}, the last at {clock(visits[-1].at)}")
    return lines[:MOST]


class Away:
    """Whether you are away, what happened meanwhile, and the note for it."""

    def __init__(self):
        self.since = None  # away since (epoch s), or None: here
        self.moments = []  # while away
        self.recent = []  # the last AWAY_S of moments, for the minutes before "away" was known
        self.note = None

    def saw(self, kind, at, about=None):
        """Something happened (`at`, epoch s)."""
        moment = Moment(kind, at, about)
        self.recent = [m for m in self.recent if at - m.at <= AWAY_S] + [moment]
        if self.since is not None:
            self.moments.append(moment)

    def step(self, now, idle, dark):
        """Looks again (`now` epoch s, `idle` s since the last input, `dark`
        nobody can see her); whether her note changed."""
        if self.note and now - self.note.back >= NOTE_KEEP_S:
            self.note = None
            return True
        if dark or idle >= AWAY_S:
            if self.since is None:
                self.since = now - idle
                self.moments = [m for m in self.recent if m.at >= self.since]
                if self.note:  # away again before reading it: one note for both
                    self.since, self.moments = self.note.since, list(self.note.moments) + self.moments
            return False
        if self.since is None:
            return False
        since, moments = self.since, self.moments
        self.since, self.moments = None, []
        if not lines_of(moments):
            return False
        self.note = Note(since, now, tuple(moments))
        return True

    def lines(self):
        """The note on the card: its heading, then what happened."""
        if not self.note:
            return []
        return [f"While you were away ({how_long(self.note.back - self.note.since)}):"] + [
            "  " + line for line in lines_of(self.note.moments)]

    def read(self):
        """The card has shown the note: she puts it away."""
        had, self.note = self.note is not None, None
        return had
