"""Lay out every See-through layer on a checkerboard, labelled, in one image."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

src = Path(sys.argv[1])
out = Path(sys.argv[2])
CELL_W, CELL_H, LABEL = 200, 300, 18

names = sorted(p.stem for p in src.glob('*.png')
               if not p.stem.endswith('_depth') and p.stem not in ('src_head',))
cols = 7
rows = (len(names) + cols - 1) // cols
sheet = Image.new('RGB', (cols * CELL_W, rows * (CELL_H + LABEL)), 'white')
draw = ImageDraw.Draw(sheet)


def checker(w, h, s=10):
    im = Image.new('RGB', (w, h), (235, 235, 235))
    d = ImageDraw.Draw(im)
    for y in range(0, h, s):
        for x in range((y // s % 2) * s, w, 2 * s):
            d.rectangle([x, y, x + s - 1, y + s - 1], fill=(200, 200, 200))
    return im


stats = {}
for i, name in enumerate(names):
    im = Image.open(src / f'{name}.png').convert('RGBA')
    bbox = im.getchannel('A').point(lambda a: 255 if a > 16 else 0).getbbox()
    stats[name] = {'size': im.size, 'bbox': bbox}
    im.thumbnail((CELL_W, CELL_H))
    cell = checker(CELL_W, CELL_H)
    cell.paste(im, ((CELL_W - im.width) // 2, (CELL_H - im.height) // 2), im)
    x, y = (i % cols) * CELL_W, (i // cols) * (CELL_H + LABEL)
    sheet.paste(cell, (x, y + LABEL))
    draw.text((x + 4, y + 3), name, fill='black')

sheet.save(out)
print(json.dumps(stats, indent=1))
