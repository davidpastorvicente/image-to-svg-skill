#!/usr/bin/env python3
"""Rank fonts against a crop of text in the reference.

Example:
  python font_match.py ref.png --box 65 985 385 1055 --text TITLE \
      --font "/System/Library/Fonts/Avenir Next.ttc" --font ~/fonts/Montserrat-Medium.ttf \
      --sizes 50 70 0.5 --tracking 0 12 0.5 --sheet font-comparison.png

--font may be repeated; .ttc collections are expanded (italic/condensed faces
skipped). Prints IoU scores (higher is better) with the best size/tracking in
reference pixels, and writes a visual comparison sheet.

Requires: pillow numpy opencv-python-headless fonttools
"""
import argparse
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTCollection, TTFont

SKIP = ('italic', 'oblique', 'condensed', 'compressed')


def faces(paths):
    for p in paths:
        p = Path(p).expanduser()
        if p.suffix.lower() == '.ttc':
            for i, font in enumerate(TTCollection(str(p)).fonts):
                name = font['name'].getDebugName(4) or f'{p.stem} #{i}'
                if not any(s in name.lower() for s in SKIP):
                    yield p, i, name
        else:
            yield p, 0, TTFont(str(p))['name'].getDebugName(4) or p.stem


def render(text, path, index, size, tracking, ss=3):
    font = ImageFont.truetype(str(path), round(size*ss), index=index)
    width = int(sum(font.getlength(c) for c in text) + tracking*ss*len(text) + 40*ss)
    img = Image.new('L', (width, int(size*ss*2)))
    d = ImageDraw.Draw(img)
    x = 10*ss
    for c in text:
        d.text((round(x), 0), c, font=font, fill=255, anchor='lt')
        x += font.getlength(c) + tracking*ss
    small = np.array(img.resize((img.width//ss, img.height//ss), Image.Resampling.LANCZOS))
    ys, xs = np.nonzero(small > 127)
    return small[ys.min():ys.max()+1, xs.min():xs.max()+1] > 127


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('image')
    p.add_argument('--box', type=int, nargs=4, required=True)
    p.add_argument('--text', required=True)
    p.add_argument('--font', action='append', required=True)
    p.add_argument('--sizes', type=float, nargs=3, default=(20, 80, 1), metavar=('MIN', 'MAX', 'STEP'))
    p.add_argument('--tracking', type=float, nargs=3, default=(0, 15, 0.5), metavar=('MIN', 'MAX', 'STEP'))
    p.add_argument('--threshold', type=int, default=120)
    p.add_argument('--sheet', default='font-comparison.png')
    a = p.parse_args()

    ref = Image.open(a.image).convert('L').crop(tuple(a.box))
    arr = np.array(ref) < a.threshold
    ys, xs = np.nonzero(arr)
    target = arr[ys.min():ys.max()+1, xs.min():xs.max()+1]
    h, w = target.shape
    results = []
    for path, idx, name in faces(a.font):
        best = None
        for size in np.arange(*a.sizes[:2], a.sizes[2]):
            for tr in np.arange(a.tracking[0], a.tracking[1] + 1e-9, a.tracking[2]):
                m = render(a.text, path, idx, size, tr)
                if abs(m.shape[0]-h) > 2 or abs(m.shape[1]-w) > 3:
                    continue
                m = cv2.resize(m.astype('uint8'), (w, h), interpolation=cv2.INTER_NEAREST) > 0
                score = (m & target).sum()/(m | target).sum()
                if best is None or score > best[0]:
                    best = (score, size, tr)
        if best:
            results.append((best[0], name, path, idx, best[1], best[2]))
    results.sort(reverse=True)
    for score, name, path, idx, size, tr in results:
        print(f'{score:.4f}  {name}  size={size:g}px tracking={tr:g}px  ({path}#{idx})')

    rows = results[:8]
    sheet = Image.new('RGB', (max(800, ref.width + 220), 110*(len(rows)+1)), 'white')
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), 'Reference', fill='black')
    sheet.paste(ref.convert('RGB'), (200, 10))
    for j, (score, name, path, idx, size, tr) in enumerate(rows, 1):
        m = render(a.text, path, idx, size, tr)
        d.text((10, 110*j + 10), f'{name}  {score:.3f}', fill='black')
        sheet.paste(Image.fromarray(np.where(m, 0, 255).astype('uint8')).convert('RGB'), (200, 110*j + 10))
    sheet.save(a.sheet)
    print('sheet:', a.sheet)


if __name__ == '__main__':
    main()
