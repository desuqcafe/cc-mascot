"""Animate one of a character's poses from its See-through layers into a loop:
breathing, sway, twin tails and skirt swaying with lag, a blink, and what
the pose adds (a hop, a head tilt, dizzy eyes). poses.py holds each pose's
rig: its bend points, its layers and its motion.

All coordinates are in See-through's 1280x1280 canvas, where she stands about
1180 px tall: at 420 px on screen, 1 screen pixel is about 2.8 canvas pixels.

    python animate.py [--character NAME] [--pose MOOD] [--layers-from SEETHROUGH_OUT] [--export FRAMES_DIR]
    python animate.py [--character NAME] --pose MOOD --clean-art      # the art for See-through

--character picks whose poses (miku by default; poses.py has each one's).
--clean-art writes the pose's art without what floats apart from her (a symbol
drawn into it) to out/<Name>_<Mood>.png, which is what See-through splits.

Reads the pose's layers kept in art/layers/<Name>_<Mood>/ (--layers-from copies
them there from See-through's output first) and always writes previews to
out/ (<mood>.gif at mascot size, <mood>_big.gif). --export also writes the
mod's frames, <mood>-1.png ... at 512x768, lined up with the pose's art
exactly as scripts/import_frames.py lines up art, and marks the mood in
FRAMES_DIR/moods.json as rigged at the pose's fps. README.md has the setup.
"""
import argparse
import json
import math
import re
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from scipy import ndimage

from poses import POSES, TAU

HERE = Path(__file__).resolve().parent
ART = HERE.parent / 'art'
LAYERS = HERE.parent / 'art/layers'   # each pose's art split up, kept as source art
OUT = HERE / 'out'
FRAME_SIZE = (512, 768)   # the mod's frames, as import_frames.py saves them

sys.path.insert(0, str(HERE.parent / 'mascot/scripts'))
from import_frames import body_only, feet  # noqa: E402  (the mod's own art rules)


def import_layers(pose, seethrough_dir):
    """Copies the layers this pose's rig uses out of See-through's output (its
    PSD holds the left/right splits, its folder the head) into its layers
    folder, as full-canvas PNGs. Without a PSD (See-through's last step can
    fail, as on a wink's single iris) the folder's whole layers are used."""
    out_dir = Path(seethrough_dir)
    psd_path = out_dir / f'{pose.name}.psd'
    psd = {l.name: l for l in PSDImage.open(psd_path).descendants()} if psd_path.exists() else {}
    dest = LAYERS / pose.name
    dest.mkdir(parents=True, exist_ok=True)
    names = pose.parts() + ['src_img']
    for name in names:
        if name in psd:
            im = Image.new('RGBA', (1280, 1280))
            im.paste(psd[name].topil().convert('RGBA'), psd[name].bbox[:2])
        else:
            im = Image.open(out_dir / pose.name / f'{name}.png').convert('RGBA')
        im.save(dest / f'{name}.png', optimize=True)
    print(f'copied {len(names)} layers into {dest}')


def read_layer(pose, name):
    return np.asarray(Image.open(LAYERS / pose.name / f'{name}.png').convert('RGBA'), dtype=np.float32) / 255


def load(pose):
    return [[name, group, read_layer(pose, name)] for name, group in pose.order], read_layer(pose, 'src_img')


def measured(pose, layers):
    """The pose with the bend points it leaves out read from its layers."""
    def box(name):
        px = next((px for n, _, px in layers if n == name), None)
        if px is None:
            return None
        ys, xs = np.nonzero(px[..., 3] > 0.5)
        return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

    found = {}
    skirt, hair, neck = box('bottomwear'), box('back hair'), box('neck')
    if skirt:
        found.update(waist=skirt[1], skirt_hem=skirt[3], hip=skirt[1] + 36)
    if hair:
        found['tail_tip'] = hair[3]
    if neck:
        found['neck'] = ((neck[0] + neck[2]) / 2, neck[1] + 40)
    if pose.blink or pose.rings:
        r, l = (np.nonzero(read_layer(pose, f'irides-{side}')[..., 3] > 0.5) for side in ('r', 'l'))
        top = max(r[0].min(), l[0].min())
        found['skin'] = (top, top + 60, r[1].max() + 8, l[1].min() - 8)
    return replace(pose, **{k: v for k, v in found.items() if getattr(pose, k) is None})


def rebuild_from_source(layers, src):
    """Give every pixel the source shows to the layer that shows it, in the
    source's exact colour; keep each layer's inpainted hidden part, colour
    matched to its visible part. At rest the stack then equals the source."""
    top = np.full(src.shape[:2], -1)
    for i, (_, _, px) in enumerate(layers):
        top[px[..., 3] > 0.5] = i
    seen = src[..., 3] > 0.02
    # Source pixels no layer claims (outlines, the headset mic) go to the
    # nearest layer.
    _, (iy, ix) = ndimage.distance_transform_edt(top < 0, return_indices=True)
    owner = np.where(top >= 0, top, top[iy, ix])
    for i, layer in enumerate(layers):
        px = layer[2]
        mine = seen & (owner == i)
        # Hidden: under a layer in front. Past the source's silhouette: dropped.
        hidden = (px[..., 3] > 0.5) & (owner > i)
        if mine.sum() > 50 and hidden.any():
            # Per-channel linear fit, layer colour -> source colour.
            for c in range(3):
                a, b = np.polyfit(px[..., c][mine & (px[..., 3] > 0.9)], src[..., c][mine & (px[..., 3] > 0.9)], 1) \
                    if (mine & (px[..., 3] > 0.9)).sum() > 50 else (1.0, 0.0)
                px[..., c] = np.where(hidden, np.clip(a * px[..., c] + b, 0, 1), px[..., c])
        out = px.copy()
        out[mine] = src[mine]
        # Pixels shown by a layer in front of this one stay this layer's own.
        out[..., 3] = np.where(mine, src[..., 3], np.where(hidden, px[..., 3], 0))
        layer[2] = out
    return layers


class Eyes:
    """What a blink needs: each eye's area (the hull of its lash and iris),
    the head with both eyes painted out, and the lash colour. And what a
    moving rings need: each iris's middle and radius."""

    def __init__(self, pose, head):
        from skimage.morphology import convex_hull_image
        self.eyes, self.irises = [], []
        mask_all = np.zeros(head.shape[:2], bool)
        for side in ('r', 'l'):
            iris = read_layer(pose, f'irides-{side}')[..., 3] > 0.16
            m = (read_layer(pose, f'eyelash-{side}')[..., 3] > 0.16) | iris
            m = ndimage.binary_dilation(convex_hull_image(m), iterations=4)
            ys, xs = np.nonzero(m)
            self.eyes.append((m, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
            mask_all |= m
            ys, xs = np.nonzero(iris)
            self.irises.append((xs.mean(), ys.mean(), math.sqrt(iris.sum() / math.pi)))
        # Paint the eyes out with skin only: each pixel takes the nearest
        # skin-coloured pixel outside the eyes (never the face's outline or
        # the transparent edge), then a blur from inside the eyes smooths it.
        y0, y1, x0, x1 = pose.skin
        yy, xx = np.mgrid[y0:y1, x0:x1]
        skin = np.median(head[yy, xx][head[yy, xx][..., 3] > 0.99][:, :3], axis=0)
        skinlike = ~mask_all & (head[..., 3] > 0.9) & (np.abs(head[..., :3] - skin).max(axis=2) < 0.08)
        _, (iy, ix) = ndimage.distance_transform_edt(~skinlike, return_indices=True)
        painted = head[iy, ix, :3]
        w = mask_all.astype(np.float32)
        norm = np.maximum(ndimage.gaussian_filter(w, 4), 1e-4)
        soft = np.stack([ndimage.gaussian_filter(painted[..., c] * w, 4) / norm for c in range(3)], axis=2)
        self.eyeless = head.copy()
        self.eyeless[mask_all, :3] = soft[mask_all]
        dark = mask_all & (head[..., :3].mean(axis=2) < 0.25) & (head[..., 3] > 0.9)
        self.lash = np.median(head[dark][:, :3], axis=0)

    def head(self, head, closed):
        """The head with both eyes `closed` (0 open .. 1 shut): the eye
        squashes down toward the lower lid; shut is one soft lash curve."""
        if closed <= 0:
            return head
        out = self.eyeless.copy()
        for m, x0, y0, x1, y1 in self.eyes:
            w, h = x1 - x0, y1 - y0
            if closed < 1:
                eye = head[y0:y1, x0:x1].copy()
                eye[~m[y0:y1, x0:x1]] = 0
                keep = max(2, round(h * (1 - closed)))
                eye = np.asarray(Image.fromarray((eye * 255).astype(np.uint8)).resize((w, keep), Image.LANCZOS),
                                 dtype=np.float32) / 255
                sub = out[y1 - keep:y1, x0:x1]
                a = eye[..., 3:4]
                sub[..., :3] = eye[..., :3] * a + sub[..., :3] * (1 - a)
            else:
                self._curve(out, x0, y0, w, h)
        return out

    def rings(self, head, shift):
        """The head with each ringed (dizzy) eye's rings moved outward by
        `shift` ring widths: inside the outermost dark ring, every pixel takes
        the one a fraction of a ring further in, the pattern repeating every
        ring (from the inner dark ring to the outer one, both dark, so the
        wrap leaves no seam). Outside it the eye stays as drawn."""
        out = head.copy()
        lum = head[..., :3].mean(axis=2)
        for cx, cy, r in self.irises:
            x0, x1, y0, y1 = int(cx - r) - 2, int(cx + r) + 3, int(cy - r) - 2, int(cy + r) + 3
            ys, xs = GY[y0:y1, x0:x1] - cy, GX[y0:y1, x0:x1] - cx
            dist = np.hypot(xs, ys)
            profile = np.array([lum[y0:y1, x0:x1][(dist >= k) & (dist < k + 1)].mean() for k in range(int(r) + 2)])
            inner = int(np.argmin(profile[int(0.2 * r):int(0.5 * r)])) + int(0.2 * r)
            outer = int(np.argmin(profile[int(0.7 * r):])) + int(0.7 * r)
            period = outer - inner
            src_r = inner + np.mod(dist - shift * period - inner, period)
            scale = np.where(dist < outer, src_r / np.maximum(dist, 1e-3), 1.0)
            sx, sy = cx + xs * scale, cy + ys * scale
            patch = np.stack([ndimage.map_coordinates(head[..., k], [sy, sx], order=1) for k in range(4)], axis=2)
            inside = (dist < outer)[..., None]
            out[y0:y1, x0:x1] = np.where(inside, patch, out[y0:y1, x0:x1])
        return out

    def _curve(self, out, x0, y0, w, h):
        """A closed eye: a tapered curve sagging a little, drawn at 4x and
        scaled down for clean edges."""
        from PIL import ImageDraw
        k = 4
        im = Image.new('L', (w * k, h * k), 0)
        d = ImageDraw.Draw(im)
        base, sag = h * 0.62, w * 0.10
        pts = []
        for i in range(41):
            t = i / 40
            x = (0.08 + 0.84 * t) * w
            y = base + sag * math.sin(math.pi * t)
            pts.append((x, y, 0.8 + 2.4 * math.sin(math.pi * t) ** 0.7))
        for (xa, ya, ra), (xb, yb, rb) in zip(pts, pts[1:]):
            r = (ra + rb) / 2 * k
            d.line([(xa * k, ya * k), (xb * k, yb * k)], fill=255, width=max(1, round(2 * r)))
            d.ellipse([xb * k - r, yb * k - r, xb * k + r, yb * k + r], fill=255)
        a = np.asarray(im.resize((w, h), Image.LANCZOS), dtype=np.float32)[..., None] / 255
        sub = out[y0:y0 + h, x0:x0 + w]
        sub[..., :3] = self.lash * a + sub[..., :3] * (1 - a)


GY, GX = np.mgrid[0:1280, 0:1280].astype(np.float32)
WAVE_BLEND = 24
ROWS = np.arange(1280, dtype=np.float32)[:, None]


def warp(px, dx, dy):
    """Move each pixel by (dx, dy): per row (1280x1 arrays) or per pixel."""
    sy = GY - dy
    sx = GX - dx
    out = np.empty_like(px)
    for c in range(4):
        out[..., c] = ndimage.map_coordinates(px[..., c] * (px[..., 3] if c < 3 else 1), [sy, sx], order=1, mode='constant')
    a = out[..., 3:4]
    out[..., :3] = np.where(a > 1e-4, out[..., :3] / np.maximum(a, 1e-4), 0)
    return out


def ramp(rows, start, end, power=1.0):
    return np.clip((rows - start) / (end - start), 0, 1) ** power


def render(pose, layers, eyes, f, sole):
    """Frame f of the pose's loop on the 1280 canvas; `sole` is her feet's row."""
    p = TAU * f / pose.frames
    head_dx, head_dy = pose.sway(p), -pose.rise(p)
    # How much of the body's sway a row carries: nothing at the hips, all at the chest.
    carry = ramp(-ROWS, -pose.hip, -pose.chest)
    body_dx, body_dy = head_dx * carry, head_dy * carry

    def whole(rows, lag=0.0):
        """All of her moving: a hop's lift (read `lag` rad in the past) and
        a squash toward her feet."""
        return -pose.lift(p - lag) + pose.squash(p) * (sole - rows)

    def tilt():
        """The head turned around the neck (small angles), per pixel."""
        a = pose.tilt(p)
        nx, ny = pose.neck
        return -a * (GY - ny), a * (GX - nx)

    canvas = np.zeros((1280, 1280, 4), dtype=np.float32)
    for name, group, px in layers:
        if group == 'legs':
            moved = warp(px, 0, whole(ROWS)) if pose.hops else px
        elif group in ('body', 'arm', 'hand'):
            dx, dy = body_dx, body_dy + whole(ROWS)
            if group == 'arm':
                dy = dy - pose.pump(p) * ramp(-ROWS, -pose.shoulder, -pose.shoulder + 200)
            if group == 'hand':
                # The hand turns about the wrist; the sleeve under it stays,
                # blending over WAVE_BLEND px so the cuff does not tear.
                a, (wx, wy) = pose.wave(p), pose.wrist
                k = ramp(-GY, -wy, -wy + WAVE_BLEND)
                dx, dy = dx - a * (GY - wy) * k, dy + a * (GX - wx) * k
            moved = warp(px, dx, dy)
        elif group == 'dangle':
            s = ramp(ROWS, pose.hip, sole)
            dx = pose.legs_swing * s ** 1.3 * np.sin(p - pose.legs_lag * s)
            moved = warp(px, dx, whole(ROWS))
        elif group == 'head':
            if name == 'head' and eyes:
                px = eyes.head(px, pose.blink.get(f, 0))
                if pose.rings:
                    px = eyes.rings(px, pose.rings(p))
            dx, dy = head_dx, head_dy + whole(ROWS)
            if pose.tilt:
                tx, ty = tilt()
                dx, dy = dx + tx, dy + ty
            moved = warp(px, dx, dy)
        elif group == 'tail':
            s = ramp(ROWS, pose.tail_root, pose.tail_tip)
            dx = head_dx + pose.tail_swing * s ** 1.6 * np.sin(p - pose.tail_lag * s - 0.4) - head_dx * s ** 1.6 * 0.5
            dy = head_dy + whole(ROWS, pose.tail_bounce * s)
            if pose.tilt:
                tx, ty = tilt()
                dx, dy = dx + tx * (1 - s), dy + ty * (1 - s)
            moved = warp(px, dx, dy)
        elif group == 'skirt':
            s = ramp(ROWS, pose.waist, pose.skirt_hem, 1.4)
            dx = body_dx[int(pose.waist)] * (1 - s) + pose.skirt_swing * s * np.sin(p - pose.skirt_lag)
            moved = warp(px, dx, whole(ROWS, pose.skirt_bounce * s))
        a = moved[..., 3:4]
        canvas[..., :3] = moved[..., :3] * a + canvas[..., :3] * (1 - a)
        canvas[..., 3:4] = a + canvas[..., 3:4] * (1 - a)
    return canvas


def solid_box(img):
    return img.getchannel('A').point(lambda a: 255 if a > 127 else 0).getbbox()


def to_frame(canvas_img, fit):
    """A 1280-canvas render as one of the mod's frames: scaled and placed so
    the still pose lands exactly where its art's frame has her."""
    scale, (ox, oy) = fit
    side = round(1280 * scale)
    out = Image.new('RGBA', FRAME_SIZE, (0, 0, 0, 0))
    out.paste(canvas_img.resize((side, side), Image.LANCZOS), (round(ox), round(oy)))
    return out


def fit_to_art(pose, src):
    """(scale, offset) taking See-through's canvas to the mod's frame of the
    pose's art: matched on her outline's height (times the pose's `scale`),
    feet on the same row, and shifted as import_frames.py shifts the art onto
    idle's feet."""
    art = body_only(Image.open(ART / f'{pose.name}.png').convert('RGBA'))
    idle = Image.open(ART / f'{pose.character}_Idle.png').convert('RGBA')
    (anchor_y, anchor_x), (bottom, center) = feet(idle), feet(art)
    shift_x, shift_y = round(anchor_x - center), anchor_y - bottom
    a = solid_box(art)
    s = solid_box(Image.fromarray((src * 255).astype(np.uint8)))
    k = FRAME_SIZE[1] / art.height                        # art -> frame
    scale = (a[3] - a[1]) / (s[3] - s[1]) * k * pose.scale
    feet_x = lambda box: (box[0] + box[2]) / 2
    return scale, ((feet_x(a) + shift_x) * k - feet_x(s) * scale, (a[3] + shift_y) * k - s[3] * scale)


def export(pose, frames, src, frames_dir):
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    fit = fit_to_art(pose, src)
    for name in [p.name for p in frames_dir.iterdir()]:
        if re.fullmatch(rf'{pose.mood}(-\d+)?\.png', name, re.IGNORECASE):
            (frames_dir / name).unlink()
    for i, im in enumerate(frames, start=1):
        frame = to_frame(im, fit)
        if frame.getchannel('A').crop((0, 0, FRAME_SIZE[0], 1)).getbbox():
            print(f'warning: frame {i} touches the top of the frame (a hop too high?)')
        frame.save(frames_dir / f'{pose.mood}-{i}.png', optimize=True)
    moods_path = frames_dir / 'moods.json'
    moods = json.loads(moods_path.read_text(encoding='utf-8')) if moods_path.exists() else {}
    moods[pose.mood] = {'fps': pose.fps, 'rigged': True}
    moods_path.write_text(json.dumps(moods, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'exported {len(frames)} {pose.mood} frames at {pose.fps} fps to {frames_dir}')


def previews(pose, frames, src):
    """<mood>.gif at mascot size (420 px tall) and <mood>_big.gif, on a light
    background, framed on her with room for a hop."""
    x0, y0, x1, y1 = solid_box(Image.fromarray((src * 255).astype(np.uint8)))
    box = (max(0, (x0 + x1) // 2 - 360), max(0, y0 - 40), min(1280, (x0 + x1) // 2 + 360), min(1280, y1 + 10))
    w, h = box[2] - box[0], box[3] - box[1]
    for suffix, size in (('', (round(w * 420 / h), 420)), ('_big', (w * 2 // 3, h * 2 // 3))):
        gif = []
        for im in frames:
            bg = Image.new('RGBA', (w, h), (236, 240, 244, 255))
            bg.alpha_composite(im.crop(box))
            gif.append(bg.convert('RGB').resize(size, Image.LANCZOS))
        gif[0].save(OUT / f'{pose.mood}{suffix}.gif', save_all=True, append_images=gif[1:],
                    duration=1000 // pose.fps, loop=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--character', default='miku', choices=sorted(POSES), help='whose poses (default miku)')
    parser.add_argument('--pose', default='idle', choices=sorted({m for c in POSES.values() for m in c}), help='which mood (default idle)')
    parser.add_argument('--layers-from', metavar='DIR', help="first copy the layers from See-through's output folder")
    parser.add_argument('--clean-art', action='store_true', help="only write the pose's art, symbols dropped, for See-through")
    parser.add_argument('--export', metavar='FRAMES_DIR', help="the character's frames folder, e.g. mascot/frames/miku")
    args = parser.parse_args()
    if args.pose not in POSES[args.character]:
        parser.error(f'{args.character} has no {args.pose} pose')
    pose = POSES[args.character][args.pose]
    OUT.mkdir(parents=True, exist_ok=True)
    if args.clean_art:
        body_only(Image.open(ART / f'{pose.name}.png').convert('RGBA')).save(OUT / f'{pose.name}.png')
        print(f'wrote {OUT / pose.name}.png')
        return
    if args.layers_from:
        import_layers(pose, args.layers_from)

    layers, src = load(pose)
    layers = rebuild_from_source(layers, src)
    pose = measured(pose, layers)
    print('bend points:', {k: getattr(pose, k) for k in ('hip', 'waist', 'skirt_hem', 'tail_root', 'tail_tip', 'neck', 'skin')})
    head = next((px for name, _, px in layers if name == 'head'), None)
    eyes = Eyes(pose, head) if (pose.blink or pose.rings) and head is not None else None
    sole = solid_box(Image.fromarray((src * 255).astype(np.uint8)))[3]
    frames = []
    for f in range(pose.frames):
        frames.append(Image.fromarray((np.clip(render(pose, layers, eyes, f, sole), 0, 1) * 255).astype(np.uint8)))
    print(f'rendered {pose.frames} {pose.mood} frames')
    if args.export:
        export(pose, frames, src, args.export)
    previews(pose, frames, src)


if __name__ == '__main__':
    main()
