#!/usr/bin/env python3
"""Render an SVG with Inkscape and compare regions with the reference.

Example:
  python compare.py drawing.svg reference.png --region top 250 308 949 524 \
      --region bottom 215 1055 949 1293 --out checks/

For each region writes <out>/<name>-comparison.png: original, SVG render and a
difference overlay (red = only in original, blue = only in SVG), and prints the
dark-silhouette IoU. The SVG is rendered on white at the reference's pixel
size (viewBox units must equal reference pixels). Use --zoom for detail crops
rendered at higher resolution (e.g. --zoom 4 renders at 4 px per unit).

IoU is a diagnostic only: deliberate refinements and thin antialiased strokes
lower it. Always look at the images.

Requires: pillow numpy, Inkscape on PATH
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def render(svg, width, out, background=True):
    args = ['inkscape', str(svg), '--export-type=png', f'--export-filename={out}', f'--export-width={width}']
    args += ['--export-background=white', '--export-background-opacity=1'] if background else \
            ['--export-background-opacity=0']
    subprocess.run(args, check=True, capture_output=True)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('svg')
    p.add_argument('reference')
    p.add_argument('--region', nargs=5, action='append', required=True, metavar=('NAME', 'X0', 'Y0', 'X1', 'Y1'))
    p.add_argument('--out', default='checks')
    p.add_argument('--zoom', type=int, default=1, help='render scale (px per viewBox unit)')
    p.add_argument('--display', type=int, default=2, help='enlargement of the comparison images')
    p.add_argument('--threshold', type=int, default=125)
    a = p.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ref = Image.open(a.reference).convert('RGB')
    z = a.zoom
    with tempfile.TemporaryDirectory() as tmp:
        png = render(a.svg, ref.width*z, Path(tmp)/'render.png')
        svg_im = Image.open(png).convert('RGB')
        svg_im.load()
    report = {}
    for name, *box in a.region:
        box = tuple(int(v) for v in box)
        w, h = box[2]-box[0], box[3]-box[1]
        A = np.array(ref.crop(box).resize((w*z, h*z), Image.Resampling.LANCZOS))
        B = np.array(svg_im.crop(tuple(v*z for v in box)))
        ma = A.mean(axis=2) < a.threshold
        mb = B.mean(axis=2) < a.threshold
        iou = float((ma & mb).sum()/max(1, (ma | mb).sum()))
        diff = np.full(A.shape, 255, 'uint8')
        diff[ma & mb] = (60, 60, 55); diff[ma & ~mb] = (210, 65, 86); diff[~ma & mb] = (30, 124, 187)
        s = a.display
        W, H = w*z*s, h*z*s
        sheet = Image.new('RGB', (W, 3*H + 90), 'white')
        d = ImageDraw.Draw(sheet)
        for i, (im, title) in enumerate([(A, 'ORIGINAL'), (B, 'SVG'),
                                         (diff, 'OVERLAY  red = original only, blue = SVG only')]):
            y = i*(H + 30)
            d.text((8, y + 8), title, fill=(30, 30, 30))
            sheet.paste(Image.fromarray(im).resize((W, H), Image.Resampling.LANCZOS), (0, y + 30))
        dest = out/f'{name}-comparison.png'
        sheet.save(dest)
        report[name] = {'iou': round(iou, 4), 'only_original_px': int((ma & ~mb).sum()),
                        'only_svg_px': int((mb & ~ma).sum()), 'image': str(dest)}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
