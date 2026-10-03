# rig

Turns a character's art into a rigged loop for the mascot: the art split
into layers that move on their own, so she breathes, blinks, and her twin
tails and skirt sway, plus what a pose adds (a head tilt, a hop, dizzy eyes).
Every Miku loop (`mascot/frames/miku/<mood>-*.png`) comes from here: idle,
thinking, working, happy, error, waiting, worried, sleepy, the beam, and
held (the pose she is carried in). So is every Yunseul loop
(`mascot/frames/yunseul/`), the same ten.

Two steps, the first done once per image:

1. **Split the art into layers** with [See-through](https://github.com/shitagaki-lab/see-through)
   (SIGGRAPH 2026): one anime image in, up to 23 inpainted layers out (hair,
   face, eyes, skirt...). Needs an NVIDIA GPU with 12–16 GB; about 10 minutes
   on an RTX 4080 SUPER. The layers the rig uses are kept in
   `art/layers/<Name>_<Mood>/` (about 3 MB a pose), so this step is not needed again
   to change the motion.
2. **Animate** with `animate.py`: rebuilds each layer's visible pixels from the
   source (exact colors, and what See-through dropped, like the headset mic),
   then warps the layers row by row each frame. Needs only numpy, scipy,
   Pillow, scikit-image and psd-tools.

Of this folder only `animate.py`, `poses.py`, `contact_sheet.py` and this
file are in git (the layers they read are in `art/layers/`); the clone, the
venv and the renders (`out/`) are not.

## Setup

From this folder, in PowerShell (`uv` gives the rig its own Python 3.12,
leaving the overlay's Python alone):

```
python -m pip install --user uv
python -m uv venv --python 3.12 .venv
git clone --depth 1 https://github.com/shitagaki-lab/see-through
python -m uv pip install --python .venv\Scripts\python.exe torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
cd see-through
python -m uv pip install --python ..\.venv\Scripts\python.exe -r requirements.txt
Copy-Item -Recurse common\assets assets
cd ..
```

Only animating (layers already in `art/layers/`): the venv and
`python -m uv pip install --python .venv\Scripts\python.exe numpy scipy pillow scikit-image psd-tools`
are enough.

## Use

One pose at a time (`--pose`, idle by default; `poses.py` lists them), for
one character (`--character`, miku by default; `poses.py` has `MIKU` and
`YUNSEUL`, and her art is `art/Yunseul_<Mood>.png`, exported with
`--export ..\mascot\frames\yunseul`):

```
# 1. Split (weights download on the first run; about 5-10 minutes)
.venv\Scripts\python.exe animate.py --pose happy --clean-art     # out\Miku_Happy.png: the art, symbols dropped
cd see-through
..\.venv\Scripts\python.exe inference/scripts/inference_psd.py --srcp ..\out\Miku_Happy.png --save_to_psd --tblr_split --group_offload
cd ..
.venv\Scripts\python.exe contact_sheet.py see-through\workspace\layerdiff_output\Miku_Happy out\sheet.png   # look at every layer

# 2. Animate: previews in out/ (happy.gif is mascot size)
.venv\Scripts\python.exe animate.py --pose happy --layers-from see-through\workspace\layerdiff_output
.venv\Scripts\python.exe animate.py --pose happy                                  # again, from art/layers
.venv\Scripts\python.exe animate.py --pose happy --export ..\mascot\frames\miku   # into the plugin
```

`--export` writes `happy-1.png` ... lined up exactly with the pose's art (the
still pose lands where `import_frames.py` puts the art), and marks the mood
rigged at its fps in `frames/miku/moods.json`; the overlay then plays it, and
`import_frames.py` leaves it alone.

## A pose's rig (`poses.py`)

Each mood is a `Pose`:

- `order`: its layers back to front, each in a group that says how it moves
  (`legs` planted, `body` carrying the head's sway from the hips up, `head`,
  `tail` and `skirt` swinging with lag, `arm` pumping above the shoulders,
  `hand` waving about the `wrist`, `dangle` legs swinging from the hip when
  she is held off the ground).
  A layer not listed is left out. See-through names vary by image (the
  headset is `objects` in one, `headwear` in another): read the contact sheet.
  A hand touching the face goes in `head`, so it stays on her cheek.
- Bend points, in See-through's 1280 px canvas (1 screen pixel at 420 px tall
  is about 2.8 canvas pixels): `hip`, `waist`, `skirt_hem`, `tail_root`,
  `tail_tip`, `neck` (what the head tilts around), `chest`, `shoulder`. Those
  left out are measured from the layers (waist and hem: the skirt's top and
  bottom; tail tip: the back hair's bottom; neck: the neck layer).
- Motion, as functions of the loop's phase `p` (0 to 2 pi; numpy arrays
  too, since the tails and skirt read it row by row with lag): `sway`,
  `rise` (breath), `tilt`, `lift` and `squash` (a hop; `hop` and `crouch`
  shape one), `pump`, `rings` (ringed dizzy eyes flowing outward), `wave`
  (the hand's turn about the wrist; `nod` shapes a doze). Amounts:
  `tail_swing`/`tail_lag`/`tail_bounce`, `skirt_swing`/`skirt_lag`/
  `skirt_bounce`, `legs_swing`/`legs_lag`; `blink` (frame: how closed),
  `frames`, `fps`; `scale` (her size against her art's, for art drawn too
  big, as Yunseul's beam). A hand holding something that swings (worried's
  twin tails) goes in `head`, and `tail_root` moves down to the grip.

Keep every loop seamless (whole cycles per loop: two hops, three rings) and
the motion inside the frame: `--export` warns when a frame touches its top.

## Learned the hard way

- See-through's `face` and `eyewhite` layers can come out empty; the face
  with its eyes is `head.png` in the output folder, which the PSD leaves out.
- Its layers are slightly paler than the source: hence the rebuild from the
  source, which also makes the still pose equal the art.
- A blink paints the eyes out with nearby skin only. Inpainting (OpenCV)
  dragged the face's outline and the layer's transparent black edge into the
  skin as a grey smudge.
- Feed See-through the art without its symbols (`--clean-art`): a bubble or
  sparkles otherwise become layers and shift the fit.
- Error's "spiral" eyes are concentric rings: turning them shows nothing, so
  the rings flow outward instead (`rings`), a ring period scrolled between
  the eye's two dark rings, where the wrap leaves no seam.
- A winking pose (the beam) has no `blink`: the blink paints both eyes out
  and would draw the open one shut too.
- See-through's last step (the PSD) fails on some images (Miku's wink;
  Yunseul's held): the folder's whole layers are used then, with no
  left/right split, so such a pose cannot blink.
- flat2rig (another rigging tool) only rotates parts stiffly, which suits a
  nod but not hair or cloth; it was tried and dropped.
