"""Her sounds (settings.py: `sound`, `volume`, `sounds`, `waitingAfter`).

Each moment (settings.MOMENTS) plays her own sound, `frames/<name>/sounds/
<moment>.wav` (Miku's when a character has none; made by
scripts/make_sounds.py), or a file of yours: a name in the mascot folder's
`sounds/` (beside settings.json, never in the plugin's folder, which an
update replaces). One of yours that has gone missing plays hers.

Played with MCI (winmm's mciSendString, no dependency), always as
`mpegvideo` so a WAV and an MP3 both take a volume. A `Player` keeps one
thread for it: an MCI device answers only the thread that opened it, and an
MP3's open can take tens of ms, which her drawing must not wait for. A sound
plays at most MAX_S.

Sounds never overlap. Within a process, one plays at a time: a new one
cuts what plays only when it matters more (PRIORITY), else it is dropped.
Between mascots, `sound-gate.json` in the mascot folder says until when
one is playing ({until: epoch s, pid}); a sound that finds it taken is
dropped too, not kept for later: a late chime only says something old.
"""

import ctypes
import json
import os
import queue
import threading
import time

FOLDER = "sounds"  # yours, in the mascot folder; hers, in her frames folder
GATE_FILE = "sound-gate.json"
DEFAULT_CHARACTER = "miku"
MAX_S = 8.0  # longer files are stopped there; the settings window refuses them
GAP_S = 0.25  # the gate stays taken this long after a sound, so two never touch
# What a sound cuts when it comes while another plays (the higher cuts).
PRIORITY = {"beam": 6, "error": 5, "waiting": 4, "done": 3, "magic": 2, "intro": 1, "outro": 1}


def mci():
    """winmm's mciSendStringW, or None where there is none."""
    try:
        send = ctypes.windll.winmm.mciSendStringW
    except (AttributeError, OSError):
        return None
    send.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
    send.restype = ctypes.c_uint
    return send


def ask(send, command):
    """(MCI's error code, its answer) for one command string."""
    answer = ctypes.create_unicode_buffer(128)
    code = send(command, answer, len(answer), None)
    return code, answer.value


def own_path(name, state_dir):
    """Where a file of yours called `name` lives."""
    return os.path.join(state_dir, FOLDER, name)


def hers(moment, frames_dir):
    """Her own sound for `moment`, else Miku's; None without either."""
    for folder in (frames_dir, os.path.join(os.path.dirname(os.path.normpath(frames_dir)), DEFAULT_CHARACTER)):
        path = os.path.join(folder, FOLDER, f"{moment}.wav")
        if os.path.isfile(path):
            return path
    return None


def resolve(choice, moment, frames_dir, state_dir):
    """The file a moment plays: None for none (`choice` False); a file of
    yours (`choice` its name) while it is there; else hers."""
    if choice is False:
        return None
    if isinstance(choice, str):
        path = own_path(choice, state_dir)
        if os.path.isfile(path):
            return path
    return hers(moment, frames_dir)


def length_of(path, send=None):
    """How long the file at `path` plays, in seconds; None when MCI cannot
    open it (not a sound, or no codec for it)."""
    send = send or mci()
    if send is None:
        return None
    alias = f"mascot_len{threading.get_ident()}"
    if ask(send, f'open "{path}" type mpegvideo alias {alias}')[0]:
        return None
    try:
        ask(send, f"set {alias} time format milliseconds")
        code, answer = ask(send, f"status {alias} length")
        return int(answer) / 1000 if not code and answer.isdigit() else None
    finally:
        ask(send, f"close {alias}")


def gate_taken(path, now=None):
    """Whether another process's sound holds the gate at `path` now."""
    try:
        with open(path, encoding="utf-8") as f:
            gate = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(gate, dict):
        return False
    until, pid = gate.get("until"), gate.get("pid")
    now = time.time() if now is None else now
    return isinstance(until, (int, float)) and until > now and pid != os.getpid()


def take_gate(path, seconds):
    """Holds the gate at `path` for `seconds` from now: written whole and
    swapped in, so a reader never sees half."""
    if not path:
        return
    temp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temp, "w", encoding="utf-8") as f:
            json.dump({"until": time.time() + seconds, "pid": os.getpid()}, f)
        os.replace(temp, path)
    except OSError:
        pass


class Player:
    """Plays one sound at a time on a thread of its own. `gate`: the gate
    file shared with the other mascots (None: none); `send`: stands in for
    mciSendStringW (tests)."""

    def __init__(self, gate=None, send=None):
        self.gate = gate
        self._send = send
        self._jobs = queue.Queue()
        self._thread = None
        self._lock = threading.Lock()
        self._now = None  # (priority, until monotonic s) of the sound playing

    def playing(self):
        """The priority of the sound playing now, or None."""
        with self._lock:
            now = self._now
        return now[0] if now and time.monotonic() < now[1] else None

    def play(self, path, volume, priority=0, force=False):
        """Plays `path` at `volume` (0-100) unless a sound that matters as
        much or more plays (here, or in another mascot: the gate); `force`
        (trying one out) plays it anyway. Whether it will play."""
        if not path:
            return False
        if not force:
            current = self.playing()
            if current is not None and priority <= current:
                return False
            if self.gate and gate_taken(self.gate):
                return False
        # Held at once, for MAX_S until the thread knows the sound's length.
        with self._lock:
            self._now = (priority, time.monotonic() + MAX_S)
        take_gate(self.gate, MAX_S)
        self._start()
        self._jobs.put(("play", path, volume, priority))
        return True

    def stop(self):
        self._jobs.put(("stop",))

    def close(self):
        """Stops what plays and ends the thread."""
        if self._thread:
            self._jobs.put(("quit",))

    def _start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="mascot-sound", daemon=True)
            self._thread.start()

    def _run(self):
        send = self._send or mci()
        alias, ends, count = None, None, 0
        while True:
            wait = None if ends is None else max(0.0, ends - time.monotonic())
            try:
                job = self._jobs.get(timeout=wait)
            except queue.Empty:
                job = ("stop",)  # it has played out, or reached MAX_S
            if alias:
                ask(send, f"close {alias}")
                alias, ends = None, None
                if job[0] == "stop":
                    with self._lock:
                        self._now = None
            if job[0] == "quit":
                return
            if job[0] != "play" or send is None:
                continue
            _, path, volume, priority = job
            count += 1
            alias = f"mascot{count}"
            if ask(send, f'open "{path}" type mpegvideo alias {alias}')[0]:
                alias = None  # unplayable: nothing to wait for
                with self._lock:
                    self._now = None
                take_gate(self.gate, 0)
                continue
            ask(send, f"set {alias} time format milliseconds")
            code, answer = ask(send, f"status {alias} length")
            seconds = min(MAX_S, int(answer) / 1000) if not code and answer.isdigit() else MAX_S
            ask(send, f"setaudio {alias} volume to {round(max(0, min(100, volume)) * 10)}")
            ask(send, f"play {alias} from 0")
            ends = time.monotonic() + seconds
            with self._lock:
                self._now = (priority, ends)
            take_gate(self.gate, seconds + GAP_S)
