#!/usr/bin/env python3
"""Check mirror symmetry of figures in a rendered SVG.

Example:
  python symmetry.py drawing.svg --figure "Tower A" 250.5 150 685 872 \
      --figure "Dome" 740.25 18.4 1062 1240

Each --figure is NAME AXIS HALF_WIDTH Y0 Y1 in viewBox units. The SVG is
rendered at --scale px/unit (default 4, so .25/.5 axes land on pixel
boundaries); dark pixels in [axis-half, axis+half] x [y0, y1] are compared with
their mirror image. Residue around 0.1% is antialiasing; more means something
is off-axis. Keep the window clear of neighbouring objects. Clock hands and
other intentionally asymmetric details show up as residue too.

Requires: pillow numpy, Inkscape on PATH
"""
import argparse
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import xml.etree.ElementTree as ET


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('svg')
    p.add_argument('--figure', nargs=5, action='append', required=True,
                   metavar=('NAME', 'AXIS', 'HALF', 'Y0', 'Y1'))
    p.add_argument('--scale', type=int, default=4)
    p.add_argument('--threshold', type=int, default=110)
    a = p.parse_args()

    vb = ET.parse(a.svg).getroot().get('viewBox').split()
    width = round(float(vb[2])*a.scale)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)/'r.png'
        subprocess.run(['inkscape', a.svg, '--export-type=png', f'--export-filename={out}',
                        f'--export-width={width}', '--export-background=white',
                        '--export-background-opacity=1'], check=True, capture_output=True)
        im = np.array(Image.open(out).convert('L'))
    s = a.scale
    for name, axis, half, y0, y1 in a.figure:
        axis, half, y0, y1 = map(float, (axis, half, y0, y1))
        x0, x1 = round((axis-half)*s), round((axis+half)*s)
        c = im[round(y0*s):round(y1*s), x0:x1] < a.threshold
        diff = np.logical_xor(c, c[:, ::-1]).sum()
        print(f'{name}: {diff} asymmetric of {c.sum()} dark px ({100*diff/max(1, c.sum()):.3f}%)')


if __name__ == '__main__':
    main()
