#!/usr/bin/env python3
"""Measure a VECTOR reference (SVG, or PDF converted to SVG) instead of a
raster: every shape with its transforms applied, in real units.

When the reference is already vector (an architect's SVG/PDF, an Inkscape
drawing with named groups), its coordinates are exact — read them rather
than rasterising and fitting lines. Still rebuild by meaning: these numbers
are measurements for the constructors, never paths to copy.

Usage:
  vector_measure.py tree  ref.svg                     # group hierarchy: labels, ids, bboxes
  vector_measure.py dump  ref.svg [--label pared --label suelo] [--under puerta] [--points]
  vector_measure.py rooms ref.svg --floor suelo     # each room's floor as rects + area
Options: --units cm|mm|px (default cm, from the document's physical size),
         --nd decimals (default 1).

PDF: convert first, keeping the geometry:
  inkscape plan.pdf --export-plain-svg --export-filename=plan.svg
  (add --pdf-poppler if text or clipping comes out wrong)

Labels are Inkscape's `inkscape:label` (fallback: id). `--under X` keeps
shapes with an ancestor group whose label contains X (e.g. every door).

Requires: svgelements, lxml (pip install svgelements lxml)
"""
import argparse
import sys

import svgelements as se
from lxml import etree

NS_INK = '{http://www.inkscape.org/namespaces/inkscape}label'
UNITS = {'px': 1.0, 'mm': 96/25.4, 'cm': 96/2.54}


def load(path):
    tree = etree.parse(path)
    meta = {}
    for e in tree.iter():
        if not isinstance(e.tag, str) or e.get('id') is None:
            continue
        anc = [a.get(NS_INK) or a.get('id') for a in e.iterancestors()
               if isinstance(a.tag, str) and a.tag.endswith('}g')]
        meta[e.get('id')] = (e.get(NS_INK) or e.get('id'), list(reversed(anc)))
    doc = se.SVG.parse(path, reify=True)   # transforms + viewBox applied: px at 96 dpi
    return doc, meta


def rings(shape, k, nd):
    """Subpaths as point lists (curve segments reduced to their end points,
    marked with '~' in dump output)."""
    out = []
    for sub in se.Path(shape).as_subpaths():
        pts = []
        for s in se.Path(sub).segments():
            if s.end is None:
                continue
            curved = not isinstance(s, (se.Move, se.Line, se.Close))
            pts.append((round(s.end.x/k, nd), round(s.end.y/k, nd), curved))
        if pts and pts[-1][:2] == pts[0][:2]:
            pts.pop()
        out.append(pts)
    return out


def shapes(doc, meta):
    for el in doc.elements():
        if isinstance(el, se.Shape) and not isinstance(el, se.SVG):
            p = se.Path(el)
            if len(p) == 0 or p.bbox() is None:
                continue
            yield el, p, meta.get(el.id, (el.id, []))


def cmd_tree(a, doc, meta, k):
    groups = {}
    for el, p, (lab, anc) in shapes(doc, meta):
        bb = p.bbox()
        for d in range(1, len(anc) + 1):
            key = tuple(anc[:d])
            g = groups.setdefault(key, [1e18, 1e18, -1e18, -1e18, 0])
            g[0], g[1] = min(g[0], bb[0]), min(g[1], bb[1])
            g[2], g[3] = max(g[2], bb[2]), max(g[3], bb[3])
            g[4] += 1
    for key in sorted(groups):
        if len(key) > a.depth:
            continue
        x0, y0, x1, y1, n = groups[key]
        print(f'{"  "*(len(key) - 1)}{key[-1]}  shapes={n}  '
              f'bbox=({x0/k:.{a.nd}f},{y0/k:.{a.nd}f})-({x1/k:.{a.nd}f},{y1/k:.{a.nd}f})')


def cmd_dump(a, doc, meta, k):
    for el, p, (lab, anc) in shapes(doc, meta):
        if a.label and lab not in a.label:
            continue
        if a.under and not any(u in (x or '') for u in a.under for x in anc):
            continue
        bb = [v/k for v in p.bbox()]
        sw = (el.stroke_width or 0)/k if el.stroke is not None and el.stroke.value is not None else 0
        print(f'{"/".join(map(str, anc))} :: {lab} [{el.id}] fill={el.fill} stroke={el.stroke} '
              f'sw={sw:.2f} bbox=({bb[0]:.{a.nd}f},{bb[1]:.{a.nd}f})-({bb[2]:.{a.nd}f},{bb[3]:.{a.nd}f}) '
              f'size={bb[2]-bb[0]:.{a.nd}f}x{bb[3]-bb[1]:.{a.nd}f}')
        if a.points:
            for r in rings(el, k, a.nd):
                print('    ' + ' '.join(f'{"~" if c else ""}{x:g},{y:g}' for x, y, c in r))


def rect_decompose(poly):
    """Orthogonal polygon (point list) -> list of rects (x0, y0, x1, y1) by
    horizontal slabs, merged vertically when identical."""
    ys = sorted({y for _, y in poly})
    xs_edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    verts = [(p[0], min(p[1], q[1]), max(p[1], q[1])) for p, q in xs_edges if p[0] == q[0]]
    rects = []
    for y0, y1 in zip(ys, ys[1:]):
        ym = (y0 + y1)/2
        xs = sorted(x for x, a, b in verts if a < ym < b)
        for xa, xb in zip(xs[::2], xs[1::2]):
            prev = next((r for r in rects if r[0] == xa and r[2] == xb and r[3] == y0), None)
            if prev:
                rects[rects.index(prev)] = (xa, prev[1], xb, y1)
            else:
                rects.append((xa, y0, xb, y1))
    return rects


def cmd_rooms(a, doc, meta, k):
    for el, p, (lab, anc) in shapes(doc, meta):
        if lab != a.floor or not anc:
            continue
        name = '/'.join(anc)
        rs = rings(el, k, a.nd)
        pts = [(x, y) for x, y, _ in rs[0]]
        if any(c for _, _, c in rs[0]) or any(x0 != x1 and y0 != y1 for (x0, y0), (x1, y1)
                                               in zip(pts, pts[1:] + pts[:1])):
            print(f'{name}: not orthogonal, points: {pts}')
            continue
        rects = rect_decompose(pts)
        area = sum((x1 - x0)*(y1 - y0) for x0, y0, x1, y1 in rects)
        unit2 = {'cm': 1e4, 'mm': 1e6}.get(a.units)
        ar = f'{area/unit2:.2f} m²' if unit2 else f'{area:.0f} {a.units}²'
        print(f"'{name}': {rects},  # {ar}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['tree', 'dump', 'rooms'])
    ap.add_argument('svg')
    ap.add_argument('--units', default='cm', choices=list(UNITS))
    ap.add_argument('--nd', type=int, default=1)
    ap.add_argument('--label', action='append')
    ap.add_argument('--under', action='append')
    ap.add_argument('--points', action='store_true')
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--floor', default='suelo', help='label of the floor shapes (rooms)')
    a = ap.parse_args()
    doc, meta = load(a.svg)
    k = UNITS[a.units]
    {'tree': cmd_tree, 'dump': cmd_dump, 'rooms': cmd_rooms}[a.cmd](a, doc, meta, k)


if __name__ == '__main__':
    sys.exit(main())
