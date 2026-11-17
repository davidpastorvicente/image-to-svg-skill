#!/usr/bin/env python3
"""Structural validation of a print-ready, editable SVG.

Example:
  python validate.py drawing.svg --page-mm 300 450 --text "TITLE" --text "12.3456° N" \
      --layers 3 --transparent-at 10,10 --transparent-at 749,355

Checks: parses; optional physical page size; no <image>, <filter>, <script>,
<foreignObject> or external hrefs; unique ids; every url(#id) resolves; no
NaN/inf in path data; expected text strings present as <text> (editable);
optional minimum number of Inkscape layers; optional points that must be
transparent (rendered with Inkscape, alpha sampled; coordinates in viewBox
units). Prints a summary; exits non-zero on failure.

Requires: Inkscape on PATH only for --transparent-at (and pillow)
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('svg')
    p.add_argument('--page-mm', type=float, nargs=2)
    p.add_argument('--text', action='append', default=[])
    p.add_argument('--layers', type=int)
    p.add_argument('--transparent-at', action='append', default=[], help='x,y in viewBox units')
    a = p.parse_args()

    problems = []
    raw = Path(a.svg).read_text(encoding='utf-8')
    root = ET.fromstring(raw)
    if a.page_mm:
        w, h = root.get('width', ''), root.get('height', '')
        if w != f'{a.page_mm[0]:g}mm' or h != f'{a.page_mm[1]:g}mm':
            problems.append(f'page size is {w} x {h}')
    for tag in ('image', 'filter', 'script', 'foreignObject'):
        if root.iter(SVG + tag) and list(root.iter(SVG + tag)):
            problems.append(f'contains <{tag}>')
    if re.search(r'href="(?!#)', raw):
        problems.append('external href present')
    ids = [e.get('id') for e in root.iter() if e.get('id')]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        problems.append(f'duplicate ids: {sorted(dup)[:10]}')
    for ref in re.findall(r'url\(#([^)]+)\)', raw):
        if ref not in ids:
            problems.append(f'unresolved url(#{ref})')
    for e in root.iter(SVG + 'path'):
        d = e.get('d', '')
        if not d.strip() or re.search(r'nan|inf', d, re.I):
            problems.append(f'bad path data in {e.get("id")}')
    texts = [''.join(t.itertext()) for t in root.iter(SVG + 'text')]
    for t in a.text:
        if t not in texts:
            problems.append(f'missing editable text {t!r}')
    layers = [g for g in root.iter(SVG + 'g') if g.get(INK + 'groupmode') == 'layer']
    if a.layers is not None and len(layers) < a.layers:
        problems.append(f'only {len(layers)} layers')
    if a.transparent_at:
        from PIL import Image
        vb = [float(v) for v in root.get('viewBox').split()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'t.png'
            subprocess.run(['inkscape', a.svg, '--export-type=png', f'--export-filename={out}',
                            f'--export-width={round(vb[2])}', '--export-background-opacity=0'],
                           check=True, capture_output=True)
            im = Image.open(out).convert('RGBA')
            for s in a.transparent_at:
                x, y = (round(float(v)) for v in s.split(','))
                alpha = im.getpixel((x, y))[3]
                if alpha > 12:
                    problems.append(f'not transparent at {x},{y} (alpha {alpha})')
    print(f'paths: {len(list(root.iter(SVG + "path")))}, circles: {len(list(root.iter(SVG + "circle")))}, '
          f'texts: {len(texts)}, layers: {len(layers)}, bytes: {len(raw.encode())}')
    if problems:
        print('FAIL'); print('\n'.join(' - ' + p for p in problems)); sys.exit(1)
    print('OK')


if __name__ == '__main__':
    main()
