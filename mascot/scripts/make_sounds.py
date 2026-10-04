"""Makes each character's own sounds, `frames/<name>/sounds/<moment>.wav`,
from nothing but code: bells, tines, sweeps and filtered noise, so every
sample is original (no recordings, no voicebanks). The same code makes the
same files, byte for byte.

    python scripts/make_sounds.py [--character miku|yunseul] [--check]

`--check` makes them in memory and says whether the files match.

Miku's are bright synth and glass: a two-note pling when she waits on you,
a sparkling arpeggio when a round is done, a charge and a chord burst for
the beam (fired at effects.CHARGE_S, as the picture is), a soft "uh-oh",
twinkles that fly to the pointer, a hologram powering up (its chime as she
locks in, effects.INTRO_LOCK_S) and down. Yunseul's are a music box, low
bells, an organ and bats: her Love Bite is an organ sting with a nibble.
"""

import argparse
import array
import io
import math
import os
import random
import sys
import wave

RATE = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(os.path.dirname(HERE), "frames")
MOMENTS = ("waiting", "done", "beam", "error", "magic", "intro", "outro")
CHARGE_S = 0.7  # effects.CHARGE_S: the beam fires
LOCK_S = 1.95  # effects.INTRO_LOCK_S: she is whole
PEAK = 0.84  # every sound's loudest sample, before its own level

NAMES = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def note(name):
    """'A4' is 440 Hz; 'C#6', 'Bb5'..."""
    letter, rest = name[0], name[1:]
    shift = 0
    while rest and rest[0] in "#b":
        shift += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 440.0 * 2 ** ((NAMES[letter] + shift + 12 * (int(rest) - 4)) / 12)


# ---------------------------------------------------------------- pieces


def silence(seconds):
    return [0.0] * round(seconds * RATE)


FADE_IN, FADE_OUT = 0.004, 0.025  # every part's edges: a cut still sounding clicks


def mix(out, part, at=0.0, gain=1.0):
    """`part` into `out` from `at` seconds, its edges faded (where `out`
    cuts it short too)."""
    start = round(at * RATE)
    n = min(len(part), len(out) - start)
    rise, fall = max(1, round(FADE_IN * RATE)), max(1, round(FADE_OUT * RATE))
    for i, v in enumerate(part[: max(0, n)]):
        g = gain * min(1.0, i / rise, (n - 1 - i) / fall)
        out[start + i] += v * g
    return out


def bell(freq, seconds, partials=((1, 1, 1),), decay=0.5, attack=0.004):
    """A struck tone: partials (ratio, level, how fast it dies relative to
    `decay`), each a sine with an exponential decay."""
    n = round(seconds * RATE)
    out = [0.0] * n
    for ratio, level, speed in partials:
        f = freq * ratio
        if f >= RATE * 0.45:
            continue
        step = 2 * math.pi * f / RATE
        fall = math.exp(-1 / (decay * speed * RATE)) if decay * speed > 0 else 0.0
        amp = level
        for i in range(n):
            out[i] += math.sin(step * i) * amp
            amp *= fall
    ramp = max(1, round(attack * RATE))
    for i in range(min(ramp, n)):
        out[i] *= i / ramp
    return out


GLASS = ((1, 1, 1), (2.0, 0.32, 0.6), (3.01, 0.18, 0.4), (5.43, 0.07, 0.22))
TINE = ((1, 1, 1), (2.0, 0.18, 0.5), (4.16, 0.14, 0.3), (6.27, 0.05, 0.18))
CHURCH = ((0.5, 0.45, 1.6), (1, 1, 1), (1.19, 0.55, 0.9), (1.5, 0.3, 0.7), (2.0, 0.32, 0.5), (2.63, 0.12, 0.3),
          (3.0, 0.08, 0.25))


def tone(f0, f1, seconds, harmonics=((1, 1),), curve=1.0, level=None):
    """A held tone gliding from f0 to f1 (exponentially), with `harmonics`
    (number, level); `level(t)` (0..1 of its length) shapes it."""
    n = round(seconds * RATE)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        p = i / max(1, n - 1)
        f = f0 * (f1 / f0) ** (p ** curve)
        phase += 2 * math.pi * f / RATE
        v = 0.0
        for k, a in harmonics:
            if f * k < RATE * 0.45:
                v += math.sin(phase * k) * a
        out[i] = v * (level(p) if level else 1.0)
    return out


def noise(seconds, rng):
    return [rng.uniform(-1, 1) for _ in range(round(seconds * RATE))]


def shape(part, level):
    """`part` times `level(p)`, p 0..1 of its length."""
    n = len(part)
    return [v * level(i / max(1, n - 1)) for i, v in enumerate(part)]


def lowpass(part, cutoff):
    """One pole; `cutoff` in Hz, or a function of p (0..1) for a sweep."""
    out, y, n = [], 0.0, len(part)
    for i, v in enumerate(part):
        c = cutoff(i / max(1, n - 1)) if callable(cutoff) else cutoff
        a = 1 - math.exp(-2 * math.pi * c / RATE)
        y += a * (v - y)
        out.append(y)
    return out


def bandpass(part, center, q=2.0):
    """A biquad band-pass; `center` in Hz, or a function of p (0..1)."""
    out = []
    x1 = x2 = y1 = y2 = 0.0
    n = len(part)
    for i, x in enumerate(part):
        f = center(i / max(1, n - 1)) if callable(center) else center
        w = 2 * math.pi * f / RATE
        alpha = math.sin(w) / (2 * q)
        a0 = 1 + alpha
        b0, b2 = alpha / a0, -alpha / a0
        a1, a2 = -2 * math.cos(w) / a0, (1 - alpha) / a0
        y = b0 * x + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out.append(y)
    return out


def reverb(part, wet=0.25, size=1.0, tail=0.6):
    """A small Schroeder room: four damped combs, two all-passes; `tail`
    seconds more."""
    dry = part + silence(tail)
    combs = [round(d * size) for d in (558, 594, 638, 678)]
    feedback = 0.78 + 0.06 * min(1.0, size - 0.8)
    wet_sum = [0.0] * len(dry)
    for d in combs:
        buf, low, at = [0.0] * d, 0.0, 0
        for i, x in enumerate(dry):
            y = buf[at]
            low = y * 0.6 + low * 0.4  # damping: highs die sooner
            buf[at] = x + low * feedback
            at = (at + 1) % d
            wet_sum[i] += y / len(combs)
    for d, g in ((113, 0.5), (278, 0.5)):
        buf, at = [0.0] * d, 0
        for i, x in enumerate(wet_sum):
            y = buf[at]
            buf[at] = x + y * g
            wet_sum[i] = y - x * g
            at = (at + 1) % d
    return [a + b * wet for a, b in zip(dry, wet_sum)]


def flutter(seconds, rng, beats=14.0, center=2400, slow=0.5):
    """Bat wings: band-passed noise in quick pulses, the beat slowing by
    `slow` over its length."""
    part = bandpass(noise(seconds, rng), lambda p: center * (1 + 0.25 * math.sin(p * 9)), q=3.0)
    n = len(part)
    phase = 0.0
    out = []
    for i, v in enumerate(part):
        p = i / max(1, n - 1)
        phase += 2 * math.pi * beats * (1 - slow * p) / RATE
        out.append(v * max(0.0, math.sin(phase)) ** 3)
    return out


def finish(part, level=1.0, fade=0.03):
    """Peak at PEAK * level, the end faded, the start without a click."""
    top = max(abs(v) for v in part) or 1.0
    k = PEAK * level / top
    n = len(part)
    edge = round(fade * RATE)
    out = []
    for i, v in enumerate(part):
        g = k
        if i > n - edge:
            g *= (n - i) / edge
        if i < 32:
            g *= i / 32
        out.append(v * g)
    return out


def ease_in(p):
    return p * p


def swell(p):
    return math.sin(math.pi * min(1.0, p)) ** 0.7


# ---------------------------------------------------------------- Miku


def miku_waiting(rng):
    out = silence(1.0)
    mix(out, bell(note("B5"), 0.8, GLASS, 0.45), 0.0, 0.8)
    mix(out, bell(note("E6"), 0.84, GLASS, 0.5), 0.16, 1.0)
    return finish(reverb(out, 0.22, 0.9, 0.4), 0.8)


def miku_done(rng):
    out = silence(1.3)
    for i, name in enumerate(("C6", "E6", "G6", "C7")):
        mix(out, bell(note(name), 1.1 - i * 0.1, GLASS, 0.35 + 0.1 * i), 0.07 * i, 0.75 + 0.1 * i)
    for _ in range(6):
        f = note(rng.choice(("C7", "D7", "E7", "G7", "A7", "C8")))
        mix(out, bell(f, 0.3, ((1, 1, 1), (2.0, 0.2, 0.5)), 0.12), rng.uniform(0.25, 0.65), 0.18)
    return finish(reverb(out, 0.25, 1.0, 0.5), 0.85)


def miku_error(rng):
    out = silence(0.8)
    soft = ((1, 1), (2, 0.18), (3, 0.22), (5, 0.06))
    for at, f in ((0.0, note("E5")), (0.2, note("C5"))):
        blip = tone(f * 1.02, f * 0.97, 0.22, soft, level=lambda p: (1 - p) ** 1.5 * min(1, p * 30))
        mix(out, lowpass(blip, 2400), at, 0.9)
    return finish(reverb(out, 0.15, 0.85, 0.3), 0.75)


def miku_magic(rng):
    out = silence(1.25)
    scale = ("C6", "D6", "E6", "G6", "A6", "C7", "D7", "E7", "G7", "A7", "C8")
    for i, name in enumerate(scale):
        mix(out, bell(note(name), 0.4, GLASS, 0.18), 0.055 * i, 0.5 + 0.03 * i)
    shimmer = shape(bandpass(noise(1.0, rng), 7000, 1.2), swell)
    mix(out, shimmer, 0.05, 0.12)
    return finish(reverb(out, 0.3, 1.0, 0.5), 0.75)


def miku_beam(rng):
    out = silence(3.0)
    # The charge, spiralling up into her hands.
    charge = tone(180, 1500, CHARGE_S, ((1, 1), (2, 0.4), (3, 0.25), (4, 0.15)), curve=1.4,
                  level=lambda p: ease_in(p) * (0.6 + 0.4 * math.sin(p * p * 90)))
    mix(out, lowpass(charge, lambda p: 900 + 4000 * p), 0.0, 0.7)
    mix(out, shape(bandpass(noise(CHARGE_S, rng), lambda p: 800 + 5000 * p, 2.5), ease_in), 0.0, 0.5)
    # The burst: a bright detuned chord, a thump, a whoosh, sparkles falling.
    chord = silence(2.2)
    for name in ("C5", "E5", "G5", "C6", "E6"):
        for detune in (0.996, 1.0, 1.004):
            saw = tone(note(name) * detune, note(name) * detune, 2.2, tuple((k, 1 / k) for k in range(1, 9)))
            mix(chord, saw, 0, 0.06)
    chord = lowpass(chord, lambda p: 600 + 5200 * math.exp(-p * 3.0))
    mix(out, shape(chord, lambda p: math.exp(-p * 2.2) * min(1, p * 60)), CHARGE_S, 1.0)
    mix(out, tone(90, 38, 0.3, level=lambda p: (1 - p) ** 2), CHARGE_S, 0.9)
    mix(out, shape(bandpass(noise(0.6, rng), lambda p: 4000 - 2500 * p, 0.9), lambda p: (1 - p) ** 2), CHARGE_S, 0.45)
    for i in range(12):
        f = note(("C8", "A7", "G7", "E7", "D7", "C7")[i % 6]) * (1 + 0.002 * i)
        mix(out, bell(f, 0.35, GLASS, 0.14), CHARGE_S + 0.1 + 0.09 * i, 0.22 - 0.012 * i)
    return finish(reverb(out, 0.28, 1.1, 0.6), 1.0)


def miku_intro(rng):
    out = silence(2.6)
    rise = tone(140, 880, LOCK_S, ((1, 1), (2, 0.35), (3, 0.2)), curve=1.3,
                level=lambda p: 0.15 + 0.85 * ease_in(p))
    mix(out, lowpass(rise, lambda p: 500 + 3000 * p), 0.0, 0.45)
    t = 0.3
    while t < LOCK_S - 0.1:
        f = note(rng.choice(("C6", "E6", "G6", "A6", "C7")))
        mix(out, tone(f, f, 0.04, ((1, 1), (3, 0.3)), level=lambda p: 1 - p), t, 0.18)
        t += rng.uniform(0.08, 0.16)
    for i, name in enumerate(("C6", "G6", "C7", "E7")):
        mix(out, bell(note(name), 0.65, GLASS, 0.3), LOCK_S + 0.015 * i, 0.55)
    return finish(reverb(out, 0.25, 1.0, 0.4)[: round(2.6 * RATE)], 0.8)


def miku_outro(rng):
    out = silence(1.8)
    fall = tone(900, 110, 1.3, ((1, 1), (2, 0.35), (3, 0.2)), curve=0.8, level=lambda p: (1 - p) ** 1.3)
    mix(out, lowpass(fall, lambda p: 3500 - 3000 * p), 0.0, 0.5)
    for i, name in enumerate(("C7", "A6", "G6", "E6", "C6")):
        f = note(name)
        mix(out, tone(f, f, 0.045, ((1, 1), (3, 0.3)), level=lambda p: 1 - p), 0.1 + 0.16 * i, 0.2 - 0.025 * i)
    mix(out, shape(bandpass(noise(0.5, rng), 6000, 1.0), lambda p: min(1, p * 6) * (1 - p) ** 2), 1.15, 0.2)
    return finish(reverb(out, 0.2, 0.9, 0.3)[: round(1.8 * RATE)], 0.75)


# ---------------------------------------------------------------- Yunseul


def box(name, seconds=1.0, decay=0.55, detune=1.0):
    """A music box tine."""
    return bell(note(name) * detune, seconds, TINE, decay, attack=0.002)


def yunseul_waiting(rng):
    out = silence(1.3)
    mix(out, box("A5"), 0.0, 0.8)
    mix(out, box("C6", 1.1, 0.6, 1.003), 0.22, 0.9)
    return finish(reverb(out, 0.35, 1.2, 0.6), 0.75)


def yunseul_done(rng):
    out = silence(1.8)
    for i, (name, at) in enumerate((("A5", 0.0), ("C6", 0.14), ("E6", 0.28), ("A6", 0.46))):
        mix(out, box(name, 1.3, 0.5 + 0.12 * i, 1 + rng.uniform(-0.003, 0.003)), at, 0.7 + 0.1 * i)
    return finish(reverb(out, 0.38, 1.25, 0.7), 0.8)


def yunseul_error(rng):
    out = silence(1.2)
    mix(out, bell(note("A4"), 1.0, CHURCH, 0.45), 0.0, 0.9)
    mix(out, bell(note("G#4"), 1.0, CHURCH, 0.45), 0.24, 0.8)
    return finish(reverb(lowpass(out, 3000), 0.3, 1.2, 0.5), 0.75)


def yunseul_magic(rng):
    out = silence(1.3)
    mix(out, flutter(0.9, rng, 15, 2600, 0.45), 0.0, 0.9)
    mix(out, bell(note("E7"), 0.6, GLASS, 0.25), 0.55, 0.35)
    mix(out, bell(note("B7"), 0.5, GLASS, 0.2), 0.62, 0.2)
    return finish(reverb(out, 0.3, 1.1, 0.5), 0.7)


ORGAN = ((1, 1), (2, 0.55), (3, 0.3), (4, 0.25), (6, 0.12), (8, 0.08))


def organ(name, seconds, level=None, wobble=5.5):
    f = note(name)
    held = tone(f, f, seconds, ORGAN, level=level)
    return [v * (0.88 + 0.12 * math.sin(2 * math.pi * wobble * i / RATE)) for i, v in enumerate(held)]


def yunseul_beam(rng):
    out = silence(3.0)
    # Creeping up: the organ gathering, a note at a time.
    for i, name in enumerate(("D4", "F4", "A4")):
        start = i * 0.18
        mix(out, organ(name, CHARGE_S - start, level=lambda p: ease_in(p)), start, 0.22)
    # The sting: D minor on the full organ, a low D, a bell, bats, a nibble.
    for name in ("D3", "D4", "F4", "A4", "D5"):
        mix(out, organ(name, 2.2, level=lambda p: math.exp(-p * 2.4) * min(1, p * 50)), CHARGE_S, 0.24)
    mix(out, bell(note("D6"), 1.8, CHURCH, 0.6), CHARGE_S, 0.5)
    mix(out, flutter(1.3, rng, 17, 2200, 0.5), CHARGE_S + 0.05, 0.55)
    for at in (CHARGE_S - 0.02, CHARGE_S + 0.08):
        nib = shape(bandpass(noise(0.05, rng), 1400, 3.0), lambda p: (1 - p) ** 3)
        mix(out, nib, at, 1.6)
    return finish(reverb(out, 0.38, 1.3, 0.7)[: round(3.0 * RATE)], 1.0)


def yunseul_intro(rng):
    out = silence(2.6)
    # A bell played backwards swells into her arrival; mist under it.
    struck = bell(note("A4"), LOCK_S, CHURCH, 0.5)
    mix(out, [v * 0.6 for v in reversed(struck)], 0.0, 0.7)
    mix(out, shape(lowpass(lowpass(noise(2.2, rng), 600), 600), swell), 0.0, 0.5)
    mix(out, bell(note("D4"), 0.65, CHURCH, 0.6), LOCK_S, 0.9)
    for i, name in enumerate(("A6", "E6", "C7")):
        mix(out, box(name, 0.6, 0.3), LOCK_S + 0.08 + 0.09 * i, 0.3)
    return finish(reverb(out, 0.4, 1.3, 0.4)[: round(2.6 * RATE)], 0.8)


def yunseul_outro(rng):
    out = silence(1.8)
    for i in range(5):
        mix(out, flutter(0.7, rng, rng.uniform(13, 19), rng.uniform(1800, 3200), 0.4), 0.12 * i, 0.55 - 0.07 * i)
    for i, name in enumerate(("E6", "C6", "A5")):
        mix(out, box(name, 0.7, 0.35), 0.2 + 0.25 * i, 0.35 - 0.06 * i)
    return finish(reverb(out, 0.3, 1.1, 0.3)[: round(1.8 * RATE)], 0.72)


SOUNDS = {
    "miku": {"waiting": miku_waiting, "done": miku_done, "beam": miku_beam, "error": miku_error,
             "magic": miku_magic, "intro": miku_intro, "outro": miku_outro},
    "yunseul": {"waiting": yunseul_waiting, "done": yunseul_done, "beam": yunseul_beam, "error": yunseul_error,
                "magic": yunseul_magic, "intro": yunseul_intro, "outro": yunseul_outro},
}


# ---------------------------------------------------------------- files


def wav_bytes(samples):
    data = array.array("h", (max(-32767, min(32767, round(v * 32767))) for v in samples))
    if sys.byteorder != "little":
        data.byteswap()
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    return out.getvalue()


def make(character, moment):
    """One sound's WAV file, as bytes. Each has its own seed: making one
    never changes another."""
    rng = random.Random(f"{character}/{moment}")
    return wav_bytes(SOUNDS[character][moment](rng))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--character", choices=sorted(SOUNDS), action="append")
    parser.add_argument("--check", action="store_true", help="say whether the files match, write nothing")
    args = parser.parse_args()
    differ = []
    for character in args.character or sorted(SOUNDS):
        folder = os.path.join(FRAMES, character, "sounds")
        os.makedirs(folder, exist_ok=True)
        for moment in MOMENTS:
            data = make(character, moment)
            path = os.path.join(folder, f"{moment}.wav")
            if args.check:
                try:
                    with open(path, "rb") as f:
                        same = f.read() == data
                except OSError:
                    same = False
                if not same:
                    differ.append(path)
                continue
            with open(path, "wb") as f:
                f.write(data)
            print(f"{path}: {(len(data) - 44) / 2 / RATE:.2f} s")
    if args.check:
        print("\n".join(differ) if differ else "Every sound matches.")
        sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
