#!/usr/bin/env python3
"""Measure a raster reference for vector reconstruction.

Subcommands (coordinates are reference pixels; --box x0 y0 x1 y1):
  grid        zoomed crop with labelled 5/10 px grid lines (PNG)
  profile     top-edge profile per column, run-length encoded
  holes       light openings fully enclosed by dark shapes (boxes, centres)
  scan        dark (or light) runs along given rows or columns
  color       median colour of a region (optionally only dark/light pixels)
  fit-circle  robust circle fit to a selected colour region's outline
  fit-line    least-squares line through points

Requires: pillow numpy opencv-python-headless scipy
"""
import argparse
import json
import numpy as np
from PIL import Image, ImageDraw


def load(path):
    rgb = np.array(Image.open(path).convert('RGB'))
    gray = np.array(Image.open(path).convert('L'))
    return rgb, gray


def runs(values, start):
    out, s, prev = [], start, values[0]
    for i, v in enumerate(values[1:], start + 1):
        if v != prev:
            out.append((s, i - 1, prev))
            s, prev = i, v
    out.append((s, start + len(values) - 1, prev))
    return out


def cmd_grid(a):
    im = Image.open(a.image).convert('RGB')
    x0, y0, x1, y1 = a.box
    s = a.scale
    c = im.crop((x0, y0, x1, y1)).resize(((x1-x0)*s, (y1-y0)*s), Image.Resampling.NEAREST)
    d = ImageDraw.Draw(c)
    step = a.step
    for x in range(x0, x1):
        if x % step == 0:
            X = (x-x0)*s
            major = x % (step*2) == 0
            d.line([(X, 0), (X, c.height)], fill=(255, 0, 0) if major else (0, 170, 255))
            if major:
                d.text((X+2, 2), str(x), fill=(255, 0, 0))
    for y in range(y0, y1):
        if y % step == 0:
            Y = (y-y0)*s
            major = y % (step*2) == 0
            d.line([(0, Y), (c.width, Y)], fill=(255, 0, 0) if major else (0, 170, 255))
            if major:
                d.text((2, Y+2), str(y), fill=(255, 0, 0))
    c.save(a.output)
    print(a.output)


def cmd_profile(a):
    import cv2
    _, gray = load(a.image)
    x0, y0, x1, y1 = a.box
    mask = (gray < a.threshold).astype('uint8')
    if a.open:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((a.open, a.open), 'uint8'))
    tops = []
    for x in range(x0, x1):
        c = np.flatnonzero(mask[y0:y1, x])
        tops.append(int(c[0]) + y0 if len(c) else None)
    for s, e, v in runs(tops, x0):
        print(f'x {s}-{e}: top {v}')


def cmd_holes(a):
    import cv2
    _, gray = load(a.image)
    x0, y0, x1, y1 = a.box
    dark = gray[y0:y1, x0:x1] < a.threshold
    n, labels, stats, cents = cv2.connectedComponentsWithStats((~dark).astype('uint8'), 8)
    out = []
    for i, (x, y, w, h, area) in enumerate(stats[1:], 1):
        if x > 0 and y > 0 and x + w < dark.shape[1] and y + h < dark.shape[0] and area >= a.min_area:
            out.append({'x': int(x+x0), 'y': int(y+y0), 'w': int(w), 'h': int(h), 'area': int(area),
                        'cx': round(float(cents[i][0] + x0), 2), 'cy': round(float(cents[i][1] + y0), 2)})
    out.sort(key=lambda b: (round(b['y']/a.row_tol), b['x']))
    for b in out:
        print(json.dumps(b))
    print(f'# {len(out)} openings (bounding boxes of light pixels; true size ~0.3-0.5 px larger)')


def cmd_scan(a):
    _, gray = load(a.image)
    mask = gray > a.threshold if a.light else gray < a.threshold
    lo, hi = a.range
    for v in a.at:
        line = mask[v, lo:hi] if a.rows else mask[lo:hi, v]
        idx = np.flatnonzero(line) + lo
        segs = []
        for p in idx:
            if segs and p == segs[-1][1] + 1:
                segs[-1][1] = int(p)
            else:
                segs.append([int(p), int(p)])
        print(('y' if a.rows else 'x'), v, [tuple(s) for s in segs])


def cmd_color(a):
    import cv2
    rgb, gray = load(a.image)
    x0, y0, x1, y1 = a.box
    reg, g = rgb[y0:y1, x0:x1], gray[y0:y1, x0:x1]
    if a.dark:
        m = (g < a.threshold).astype('uint8')
    elif a.light:
        m = (g > a.threshold).astype('uint8')
    else:
        m = np.ones(g.shape, 'uint8')
    m = cv2.erode(m, np.ones((2, 2), 'uint8')) > 0 if (a.dark or a.light) else m > 0
    med = np.median(reg[m], axis=0).astype(int)
    print('median RGB', med.tolist(), 'hex #%02x%02x%02x' % tuple(med))


def cmd_fit_circle(a):
    import cv2
    from scipy.optimize import least_squares
    rgb, _ = load(a.image)
    r, g, b = [rgb[:, :, i].astype(float) for i in range(3)]
    sel = eval(a.select, {}, {'r': r, 'g': g, 'b': b, 'np': np})
    x0, y0, x1, y1 = a.box
    mask = sel[y0:y1, x0:x1].astype('uint8')
    cnt = max(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0],
              key=cv2.contourArea)[:, 0, :] + [x0, y0]
    cx, cy, rad = a.guess
    keep = np.abs(np.hypot(cnt[:, 0]-cx, cnt[:, 1]-cy) - rad) < a.tolerance
    if a.above is not None:
        keep &= cnt[:, 1] < a.above
    p = cnt[keep]
    res = least_squares(lambda v: np.hypot(p[:, 0]-v[0], p[:, 1]-v[1]) - v[2], a.guess, loss='soft_l1')
    print('circle cx=%.2f cy=%.2f r=%.2f' % tuple(res.x), 'median residual %.2f px' % np.median(abs(res.fun)),
          f'({len(p)} points)')


def cmd_fit_line(a):
    pts = np.array([[float(v) for v in s.split(',')] for s in a.points.split()])
    if a.x_of_y:
        m, c = np.polyfit(pts[:, 1], pts[:, 0], 1)
        print(f'x = {m:.5f}*y + {c:.3f}')
    else:
        m, c = np.polyfit(pts[:, 0], pts[:, 1], 1)
        print(f'y = {m:.5f}*x + {c:.3f}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def box(sp):
        sp.add_argument('image')
        sp.add_argument('--box', type=int, nargs=4, required=True, metavar=('X0', 'Y0', 'X1', 'Y1'))

    s = sub.add_parser('grid'); box(s)
    s.add_argument('--scale', type=int, default=6); s.add_argument('--step', type=int, default=5)
    s.add_argument('-o', '--output', default='grid.png'); s.set_defaults(fn=cmd_grid)

    s = sub.add_parser('profile'); box(s)
    s.add_argument('--threshold', type=int, default=120)
    s.add_argument('--open', type=int, default=0, help='opening kernel to ignore thin lines')
    s.set_defaults(fn=cmd_profile)

    s = sub.add_parser('holes'); box(s)
    s.add_argument('--threshold', type=int, default=135)
    s.add_argument('--min-area', type=int, default=3)
    s.add_argument('--row-tol', type=float, default=20)
    s.set_defaults(fn=cmd_holes)

    s = sub.add_parser('scan'); s.add_argument('image')
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument('--rows', action='store_true'); g.add_argument('--cols', action='store_true')
    s.add_argument('--at', type=int, nargs='+', required=True)
    s.add_argument('--range', type=int, nargs=2, required=True)
    s.add_argument('--threshold', type=int, default=120)
    s.add_argument('--light', action='store_true', help='report light runs instead of dark')
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser('color'); box(s)
    s.add_argument('--dark', action='store_true'); s.add_argument('--light', action='store_true')
    s.add_argument('--threshold', type=int, default=100)
    s.set_defaults(fn=cmd_color)

    s = sub.add_parser('fit-circle'); box(s)
    s.add_argument('--guess', type=float, nargs=3, required=True, metavar=('CX', 'CY', 'R'))
    s.add_argument('--select', required=True, help='numpy expression on r,g,b arrays, e.g. "(b-r>8)&(r>130)"')
    s.add_argument('--tolerance', type=float, default=5)
    s.add_argument('--above', type=float, help='only use contour points above this y')
    s.set_defaults(fn=cmd_fit_circle)

    s = sub.add_parser('fit-line')
    s.add_argument('--points', required=True, help='"x,y x,y ..."')
    s.add_argument('--x-of-y', action='store_true', help='fit x = m*y + c (near-vertical edges)')
    s.set_defaults(fn=cmd_fit_line)

    a = p.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
