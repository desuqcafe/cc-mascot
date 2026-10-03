"""Each mood's rig: where her body bends in that pose's art, which of its
layers are drawn and how they move, and the loop's motion.

Coordinates are in See-through's 1280x1280 canvas, where she stands about
1180 px tall: at 420 px on screen, 1 screen pixel is about 2.8 canvas pixels.
Bend points left out (None) are measured on the pose's layers by animate.py:
the waist and hem are the skirt's top and bottom, the hip a little under the
waist, the tail tip the bottom of the back hair, the neck the neck layer's top
middle, the skin to paint closed eyes with is between the irises.

Motions are functions of the loop's phase p (0 .. 2 pi over the loop), taking
numpy arrays as well as numbers: the tails and skirt read them a little in
the past (their lag), row by row.
"""
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

TAU = 2 * math.pi

# How each group of layers moves (animate.py's render):
#   legs   planted (they only follow a hop)
#   body   carries the head's sway and breath, nothing at the hips, all at CHEST
#   head   moves whole with the head, tilting around NECK
#   tail   hangs from the head and swings with lag toward the tips
#   skirt  hangs from the waist and swings with lag toward the hem
#   arm    the body, plus a pump upward above the shoulders (raised arms)
#   hand   the body, plus the hand above WRIST waving around it (`wave`)
#   dangle legs off the ground (held up): swinging from the hip with lag
#          toward the boots (`legs_swing`, `legs_lag`)
GROUPS = ('legs', 'body', 'head', 'tail', 'skirt', 'arm', 'hand', 'dangle')

# What a blink or dizzy eyes read besides the drawn layers.
EYE_PARTS = ['eyelash-r', 'irides-r', 'eyelash-l', 'irides-l']


def zero(p):
    return p * 0.0


@dataclass
class Pose:
    mood: str
    order: list                 # back to front: (layer, group); a layer not listed is left out
    hip: float = None           # the upper body bends from here; legs stay planted
    waist: float = None         # the skirt hangs from here
    skirt_hem: float = None
    tail_root: float = 250      # where the twin tails start to swing
    tail_tip: float = None
    chest: float = 300          # the body carries all of the head's sway from here up
    neck: tuple = None          # (x, y) the head tilts around
    shoulder: float = 470       # arms pump above this row
    character: str = 'Miku'
    frames: int = 36
    fps: int = 12
    scale: float = 1.0          # her size against her art's, about her feet (art drawn too big)

    sway: Callable = lambda p: 3.0 * np.sin(p)                  # head side to side, px
    rise: Callable = lambda p: 4.0 * (1 - np.cos(p)) / 2        # head up on the in-breath, px
    lift: Callable = zero                                       # all of her up (a hop), px
    squash: Callable = zero                                     # all of her squashed toward the feet, fraction
    tilt: Callable = None                                       # head tilt, rad (+ leans to her left)
    pump: Callable = zero                                       # raised arms up, px
    rings: Callable = None                                      # dizzy eyes' rings flowing out, in ring widths
    wave: Callable = None                                       # a waving hand's turn about the wrist, rad
    wrist: tuple = None                                         # (x, y) the waving hand turns about

    tail_swing: float = 14.0    # twin tail tips, px
    tail_lag: float = 1.1       # rad behind the body, more toward the tips
    tail_bounce: float = 0.0    # rad the tips' lift trails hers (a hop)
    skirt_swing: float = 7.0    # skirt hem, px
    skirt_lag: float = 0.8
    skirt_bounce: float = 0.0
    legs_swing: float = 0.0     # dangling boots, px
    legs_lag: float = 0.6
    blink: dict = field(default_factory=dict)   # frame -> how closed
    skin: tuple = None                          # rows, rows, cols, cols of plain face skin (blink)

    @property
    def name(self):
        return f'{self.character}_{self.mood.capitalize()}'

    @property
    def hops(self):
        """Whether all of her moves (her legs too)."""
        return self.lift is not zero or self.squash is not zero

    def parts(self):
        """Every layer file the rig reads for this pose."""
        eyes = EYE_PARTS if self.blink or self.rings else []
        return [n for n, _ in self.order] + eyes


IDLE = Pose(
    mood='idle',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'), ('handwear-r', 'body'),
        ('head', 'head'),
        ('objects', 'head'),
        ('front hair', 'head'),
    ],
    hip=700, waist=664, skirt_hem=860, tail_root=250, tail_tip=1025,
    blink={30: 0.5, 31: 1.0, 32: 0.5},
    skin=(300, 372, 640, 690),
)

# Hand at her chin, eyes up: a slow loop rocking her head in a gentle "hmm",
# the chin hand riding along with it.
THINKING = Pose(
    mood='thinking',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-r', 'body'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear-l', 'head'),
    ],
    frames=48,
    sway=lambda p: 1.5 * np.sin(p),
    rise=lambda p: 3.5 * (1 - np.cos(p)) / 2,
    tilt=lambda p: 0.035 * np.sin(p),
    tail_swing=10.0,
    skirt_swing=5.0,
    blink={20: 0.5, 21: 1.0, 22: 0.5},
)

def hop(p, hops=2, air=0.6):
    """Where in a hop she is: 0 on the ground .. 1 at the top; `hops` per
    loop, in the air for `air` of each."""
    u = np.mod(p * hops / TAU, 1.0)
    v = np.clip((u - (1 - air) / 2) / air, 0, 1)
    return 4 * v * (1 - v)


def crouch(p, hops=2, air=0.6):
    """How deep she crouches: 1 at the middle of her time on the ground
    (landing into the next take-off), 0 in the air."""
    u = np.mod(p * hops / TAU + 0.5, 1.0)        # 0.5 = between two hops
    ground = (1 - air) / 2
    return np.clip(1 - np.abs(u - 0.5) / ground, 0, 1) ** 1.5


# Arms up and cheering: two little hops per loop, a squash on each landing,
# the twin tails and the skirt flying up a beat behind her, fists pumping.
HAPPY = Pose(
    mood='happy',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'arm'), ('handwear-r', 'arm'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
    ],
    frames=24,
    shoulder=520,
    sway=lambda p: 3.0 * np.sin(p),
    rise=lambda p: 3.0 * hop(p),
    lift=lambda p: 30.0 * hop(p),
    squash=lambda p: 0.025 * crouch(p),
    pump=lambda p: 10.0 * hop(p - 0.25),
    tail_swing=10.0,
    tail_bounce=0.9,
    skirt_swing=5.0,
    skirt_bounce=0.5,
)

# Singing into her mic, eyes closed: she sways side to side with the music and
# dips on each beat at either end, the mic hand riding along with her head.
WORKING = Pose(
    mood='working',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'),
        ('head', 'head'),
        ('objects', 'head'),
        ('front hair', 'head'),
        ('handwear-r', 'head'),
    ],
    frames=24,
    sway=lambda p: 4.0 * np.sin(p),
    rise=lambda p: 5.0 * (1 + np.cos(2 * p)) / 2,               # down at either end of the sway
    tilt=lambda p: 0.03 * np.sin(p),
    tail_swing=14.0,
    tail_lag=1.3,
    skirt_swing=7.0,
)

# Dizzy and upset, hands pressed under her chin: her ringed eyes' rings flow
# outward (hypnotic, a whole ring a second, so the loop is seamless), a
# slow slumped breath, the twin tails swaying low. No shiver: the overlay's
# glitch carries the upset.
ERROR = Pose(
    mood='error',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'), ('handwear-r', 'body'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
    ],
    sway=lambda p: 1.5 * np.sin(p),
    rise=lambda p: 3.0 * (1 - np.cos(p)) / 2,
    rings=lambda p: 3 * p / TAU,                                # a ring a second
    tail_swing=8.0,
    skirt_swing=4.0,
)

# Waiting on you: a bright, hopeful look and an "excuse me" wave, the raised
# hand waggling three times a loop about the wrist, a little lean into it.
WAITING = Pose(
    mood='waiting',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-r', 'body'),
        ('head', 'head'),
        ('objects', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear-l', 'hand'),
    ],
    frames=24,
    sway=lambda p: 2.0 * np.sin(p),
    rise=lambda p: 3.0 * (1 - np.cos(p)) / 2,
    tilt=lambda p: 0.02 * np.sin(p),
    wave=lambda p: 0.2 * np.sin(3 * p),
    wrist=(795, 475),
    tail_swing=10.0,
    skirt_swing=5.0,
    blink={14: 0.5, 15: 1.0, 16: 0.5},
)

# A little flustered, holding her twin tails up by her cheeks: a quick
# fidgety sway (twice a loop), a double blink. Her hands ride with her head,
# and the tails swing only below her grip.
WORRIED = Pose(
    mood='worried',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('objects', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear-r', 'head'), ('handwear-l', 'head'),
    ],
    frames=24,
    tail_root=480,
    sway=lambda p: 2.0 * np.sin(2 * p),
    rise=lambda p: 2.0 * (1 - np.cos(2 * p)) / 2,
    tilt=lambda p: 0.025 * np.sin(2 * p),
    tail_swing=8.0,
    skirt_swing=4.0,
    blink={6: 0.5, 7: 1.0, 8: 0.5, 10: 0.5, 11: 1.0, 12: 0.5},
)

def nod(p, drop=0.8):
    """Nodding off: 0 awake .. 1 drooped. Her head sinks slowly for `drop`
    of the loop, then she catches herself and it lifts back quickly."""
    u = np.mod(p / TAU, 1.0)
    sink = np.clip(u / drop, 0, 1)
    lift = np.clip((u - drop) / (1 - drop), 0, 1)
    return np.where(u < drop, sink * sink * (3 - 2 * sink), 1 - lift * lift * (3 - 2 * lift))


# Dozing off on her feet, rubbing an eye: slow, deep breaths while her head
# slowly sinks and tips to one side, then she catches herself (a nod). The
# rubbing hand rides with her head.
SLEEPY = Pose(
    mood='sleepy',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear-r', 'head'),
    ],
    frames=48,
    sway=lambda p: 1.5 * nod(p),
    rise=lambda p: 3.0 * (1 - np.cos(2 * p)) / 2 - 9.0 * nod(p),
    tilt=lambda p: 0.035 * nod(p),
    tail_swing=6.0,
    tail_lag=1.4,
    skirt_swing=3.0,
)

# Picked up, shy: hands together at her chest, knees together, legs
# dangling and swinging softly from the hip, a little bashful head rock and a
# blink. The overlay plays it while she is carried, and swings all of her
# from the grip on top of it.
HELD = Pose(
    mood='held',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'dangle'), ('footwear', 'dangle'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('objects', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear', 'body'),
    ],
    sway=lambda p: 1.5 * np.sin(p),
    rise=lambda p: 3.0 * (1 - np.cos(p)) / 2,
    tilt=lambda p: 0.025 * np.sin(p),
    legs_swing=16.0,
    legs_lag=0.7,
    tail_swing=12.0,
    skirt_swing=6.0,
    blink={24: 0.5, 25: 1.0, 26: 0.5},
)

# "Miku Miku Beam!": heart hands held out, a wink, knees in. A cheerful bob
# twice a loop with the heart pulsing on the beat, tails swinging; no blink
# (a blink would shut the winking eye's open one too). The overlay draws the
# beam itself over it.
BEAM = Pose(
    mood='beam',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear', 'arm'),
    ],
    frames=24,
    shoulder=430,
    sway=lambda p: 2.0 * np.sin(p),
    rise=lambda p: 3.0 * (1 - np.cos(2 * p)) / 2,
    tilt=lambda p: 0.02 * np.sin(p),
    pump=lambda p: 4.0 * (1 - np.cos(2 * p - 0.6)) / 2,
    tail_swing=12.0,
    skirt_swing=5.0,
)

MIKU = {pose.mood: pose for pose in [IDLE, THINKING, HAPPY, WORKING, ERROR, WAITING, WORRIED, SLEEPY, HELD, BEAM]}


# ---------------------------------------------------------- Yunseul
#
# A sleepy little vampire doll: slower loops than Miku's (48 frames, 4 s),
# her long silver hair swinging like a cape from the crown down, low and
# late (tail_root high, more lag). Her neck sits lower: the body carries
# the head's sway from CHEST 420 up. Her little bow is no layer of its own
# (See-through leaves headwear empty): the rebuild gives it to the hair
# beside it, above where the hair swings.

def yunseul(**kw):
    """One of Yunseul's poses: her defaults, then the pose's own."""
    base = dict(character='Yunseul', chest=420, tail_root=200, tail_lag=1.4, frames=48)
    return Pose(**{**base, **kw})


# Standing with her sleeves hanging, a slow, drowsy breath and sway, her
# hair drifting a beat behind; a slow blink.
Y_IDLE = yunseul(
    mood='idle',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'), ('handwear-r', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
    ],
    sway=lambda p: 2.5 * np.sin(p),
    rise=lambda p: 4.0 * (1 - np.cos(p)) / 2,
    tilt=lambda p: 0.015 * np.sin(p),
    tail_swing=12.0,
    skirt_swing=5.0,
    blink={40: 0.5, 41: 1.0, 42: 1.0, 43: 0.5},
)

# Heart hands at her chest, a wink and a fang: a happy bob twice a loop,
# the heart pumping on the beat. No blink (the wink). Her art draws her 6%
# taller than idle's, up to the canvas top, so the bob clipped her hair:
# she is shrunk to idle's height. The overlay draws her finisher over it.
Y_BEAM = yunseul(
    mood='beam',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
        ('handwear', 'arm'),
    ],
    frames=24,
    shoulder=380,
    scale=0.94,
    sway=lambda p: 2.0 * np.sin(p),
    rise=lambda p: 3.0 * (1 - np.cos(2 * p)) / 2,
    tilt=lambda p: 0.02 * np.sin(p),
    pump=lambda p: 4.0 * (1 - np.cos(2 * p - 0.6)) / 2,
    tail_swing=12.0,
    tail_lag=1.1,
    skirt_swing=5.0,
)

# A finger at her chin, eyes up: a slow, dreamy "hmm", her head rocking
# and the chin hand riding with it.
Y_THINKING = yunseul(
    mood='thinking',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
        ('handwear-r', 'head'),
    ],
    sway=lambda p: 1.5 * np.sin(p),
    rise=lambda p: 3.5 * (1 - np.cos(p)) / 2,
    tilt=lambda p: 0.035 * np.sin(p),
    tail_swing=10.0,
    skirt_swing=4.0,
    blink={20: 0.5, 21: 1.0, 22: 0.5},
)

# Picked up, bashful: hands together at her chest, knees together, her
# boots dangling and swinging softly, a shy head rock. No blink: See-through
# made no PSD of this one (the only one), so its eyes are not split left and
# right. The overlay plays it while she is carried and swings all of her on
# top.
Y_HELD = yunseul(
    mood='held',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'dangle'), ('footwear', 'dangle'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
        ('handwear', 'body'),
    ],
    frames=36,
    sway=lambda p: 1.5 * np.sin(p),
    rise=lambda p: 3.0 * (1 - np.cos(p)) / 2,
    tilt=lambda p: 0.025 * np.sin(p),
    legs_swing=16.0,
    legs_lag=0.7,
    tail_swing=12.0,
    skirt_swing=6.0,
)

# Fists at her chest, a determined little frown: she works in small,
# eager nods (two a loop), her fists pumping on each one, a quick blink.
Y_WORKING = yunseul(
    mood='working',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
        ('handwear-r', 'arm'), ('handwear-l', 'arm'),
    ],
    frames=24,
    shoulder=390,
    sway=lambda p: 2.0 * np.sin(p),
    rise=lambda p: 3.5 * (1 + np.cos(2 * p)) / 2,
    tilt=lambda p: 0.025 * np.sin(p),
    pump=lambda p: 4.0 * (1 + np.cos(2 * p - 0.5)) / 2,
    tail_swing=11.0,
    tail_lag=1.2,
    skirt_swing=5.0,
    blink={9: 0.5, 10: 1.0, 11: 0.5},
)

# Hands folded in front, a hopeful little smile, waiting on you: she rocks
# gently side to side, her head tipping into it, and blinks.
Y_WAITING = yunseul(
    mood='waiting',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear', 'body'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
    ],
    frames=36,
    sway=lambda p: 3.5 * np.sin(p),
    rise=lambda p: 2.5 * (1 - np.cos(2 * p)) / 2,
    tilt=lambda p: 0.04 * np.sin(p),
    tail_swing=13.0,
    skirt_swing=6.0,
    blink={27: 0.5, 28: 1.0, 29: 0.5},
)

# Fists up, eyes squeezed shut in a fanged grin: two little hops a loop, a
# squash on each landing, her long hair and skirt flying up a beat behind,
# fists pumping. No blink (her eyes are shut).
Y_HAPPY = yunseul(
    mood='happy',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'arm'), ('handwear-r', 'arm'),
        ('head', 'head'),
        ('front hair', 'head'),
    ],
    frames=24,
    shoulder=520,
    sway=lambda p: 2.5 * np.sin(p),
    rise=lambda p: 3.0 * hop(p),
    lift=lambda p: 24.0 * hop(p),
    squash=lambda p: 0.025 * crouch(p),
    pump=lambda p: 8.0 * hop(p - 0.25),
    tail_swing=10.0,
    tail_lag=1.2,
    tail_bounce=0.9,
    skirt_swing=5.0,
    skirt_bounce=0.5,
)

# Flustered, both sleeves pressed to her mouth, eyes teary: a quick fidgety
# sway (twice a loop), her hands riding with her head, a double blink.
Y_WORRIED = yunseul(
    mood='worried',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
        ('handwear', 'head'),
    ],
    frames=24,
    sway=lambda p: 2.0 * np.sin(2 * p),
    rise=lambda p: 2.0 * (1 - np.cos(2 * p)) / 2,
    tilt=lambda p: 0.025 * np.sin(2 * p),
    tail_swing=8.0,
    skirt_swing=4.0,
    blink={6: 0.5, 7: 1.0, 8: 0.5, 10: 0.5, 11: 1.0, 12: 0.5},
)

# A pouty little tantrum, fists clenched at her sides, cheeks puffed: she
# stamps in small hops (one a second), shaking her head "hmph" at each. No
# blink: shut, her eyes look peaceful, not pouty.
Y_ERROR = yunseul(
    mood='error',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'), ('handwear-r', 'body'),
        ('head', 'head'),
        ('front hair', 'head'),
    ],
    sway=lambda p: 2.5 * np.sin(2 * p),
    rise=lambda p: 2.0 * hop(p, hops=4, air=0.4),
    lift=lambda p: 8.0 * hop(p, hops=4, air=0.4),
    squash=lambda p: 0.02 * crouch(p, hops=4, air=0.4),
    tilt=lambda p: 0.045 * np.sin(2 * p),
    tail_swing=9.0,
    tail_bounce=0.8,
    skirt_swing=4.0,
    skirt_bounce=0.5,
)

# Yawning behind one sleeve, her bunny doll tucked under the other arm:
# slow, deep breaths while her head sinks and tips, her eyes falling shut,
# then she catches herself (a nod) and they open. The yawning hand rides
# with her head.
Y_SLEEPY = yunseul(
    mood='sleepy',
    order=[
        ('back hair', 'tail'),
        ('legwear', 'legs'), ('footwear', 'legs'),
        ('neck', 'body'),
        ('bottomwear', 'skirt'),
        ('topwear', 'body'),
        ('handwear-l', 'body'),
        ('head', 'head'),
        ('headwear', 'head'),
        ('front hair', 'head'),
        ('handwear-r', 'head'),
    ],
    sway=lambda p: 1.5 * nod(p),
    rise=lambda p: 3.0 * (1 - np.cos(2 * p)) / 2 - 9.0 * nod(p),
    tilt=lambda p: 0.035 * nod(p),
    tail_swing=6.0,
    tail_lag=1.5,
    skirt_swing=3.0,
    blink={26: 0.3, 27: 0.5, 28: 0.7, **{f: 1.0 for f in range(29, 39)}, 39: 0.5},
)

YUNSEUL = {pose.mood: pose for pose in [Y_IDLE, Y_THINKING, Y_HAPPY, Y_WORKING, Y_ERROR, Y_WAITING, Y_WORRIED, Y_SLEEPY, Y_HELD, Y_BEAM]}

POSES = {'miku': MIKU, 'yunseul': YUNSEUL}
