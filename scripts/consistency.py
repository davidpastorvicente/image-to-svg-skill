#!/usr/bin/env python3
"""Audit layout consistency of an SVG: equivalent objects must be identical
and aligned, and the artwork must be centred on the page.

Example:
  python consistency.py poster.svg [--tolerance 0.3] [--json report.json]

Uses Inkscape's own visual bounding boxes (`inkscape --query-all`), so text is
measured by its real rendered ink. Checks (each prints OK or a finding):
  circles      radii that are close (within 25%) but not identical
  text styles  texts of a similar size (within 15%) that differ in font-size,
               letter-spacing, family, weight or fill; per-glyph x lists
               (irregular spacing) are flagged
  rects        near-identical rectangles (e.g. accent bars) that differ
  rules        horizontal lines: similar widths that differ; lines on the same
               y that should be equal and mirrored about the page centre
  margins      left/right edges of layout objects (text, rects, rules) that
               almost line up but don't; left vs right margin symmetry
  colour pairs backdrop-circle vs accent-rect colour relation (OKLCH lightness
               difference, chroma ratio, hue shift) that differs between
               sections of the same structure
  rhythm       per-layer vertical gaps between stacked text/rect objects
               that differ between layers with the same structure
  centring     union bbox of all visible content vs page centre
  centred text texts close to the page centre but not exactly on it
Findings are suggestions: decide with the user what is intentionally different.
Exit status 1 if any finding.

Requires: Inkscape on PATH
"""
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
import xml.etree.ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'
UNITS = {'mm': 96/25.4, 'cm': 96/2.54, 'in': 96, 'pt': 4/3, 'px': 1, '': 1}


def length(v):
    m = re.match(r'([\d.]+)\s*([a-z]*)', v or '')
    return float(m.group(1))*UNITS[m.group(2)] if m else None


def style(e, key):
    m = re.search(rf'(?:^|;)\s*{key}\s*:\s*([^;]+)', e.get('style', ''))
    return (m.group(1).strip() if m else None) or e.get(key)


def oklch(hex_):
    """Perceptual lightness, chroma, hue (degrees) of a #rrggbb colour."""
    import math
    r, g, b = [int(hex_[i:i+2], 16)/255 for i in (1, 3, 5)]
    r, g, b = [c/12.92 if c <= .04045 else ((c + .055)/1.055)**2.4 for c in (r, g, b)]
    l, m, s = [v**(1/3) for v in (.4122214708*r + .5363325363*g + .0514459929*b,
                                  .2119034982*r + .6806995451*g + .1073969566*b,
                                  .0883024619*r + .2817188376*g + .6299787005*b)]
    L = .2104542553*l + .7936177850*m - .0040720468*s
    a = 1.9779984951*l - 2.4285922050*m + .4505937099*s
    bb = .0259040371*l + .7827717662*m - .8086757660*s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def fill_of(e):
    f = style(e, 'fill') or ''
    return f.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', f) else None


def clusters(items, key, rel=None, abs_=None):
    """Group items whose key values are close (single-linkage)."""
    items = sorted(items, key=key)
    groups = []
    for it in items:
        v = key(it)
        if groups:
            p = key(groups[-1][-1])
            close = (abs_ is not None and abs(v - p) <= abs_) or \
                    (rel is not None and abs(v - p) <= rel*max(abs(v), abs(p), 1e-9))
            if close:
                groups[-1].append(it)
                continue
        groups.append([it])
    return [g for g in groups if len(g) > 1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('svg')
    ap.add_argument('--tolerance', type=float, default=0.3, help='allowed difference in user units')
    ap.add_argument('--json')
    a = ap.parse_args()
    tol = a.tolerance

    root = ET.parse(a.svg).getroot()
    vb = [float(v) for v in root.get('viewBox').split()]
    width_px = length(root.get('width')) or vb[2]
    scale = vb[2]/width_px
    out = subprocess.run(['inkscape', a.svg, '--query-all'], capture_output=True, text=True, check=True).stdout
    box = {}
    for line in out.splitlines():
        id, *v = line.split(',')
        x, y, w, h = (float(t)*scale for t in v)
        box[id] = (x + 0*vb[0], y, x + w, y + h)
    parent = {c: p for p in root.iter() for c in p}
    defs = {e for d in root.iter(SVG + 'defs') for e in d.iter()}
    els = [e for e in root.iter() if e.get('id') in box and e not in defs]
    findings = []

    def report(check, msg, data=None):
        findings.append({'check': check, 'message': msg, 'data': data})

    # circles
    circles = [e for e in els if e.tag == SVG + 'circle']
    for g in clusters(circles, lambda e: float(e.get('r')), rel=.25):
        centres = {(round(float(e.get('cx')), 1), round(float(e.get('cy')), 1)) for e in g}
        if len(centres) < len(g):
            continue  # concentric rings are intentionally different
        rs = [float(e.get('r')) for e in g]
        if max(rs) - min(rs) > tol and len(g) <= 6:
            report('circles', 'similar circles with different radii', {e.get('id'): float(e.get('r')) for e in g})

    # text styles
    texts = [e for e in els if e.tag == SVG + 'text']
    fsize = lambda e: length(style(e, 'font-size')) or 0
    # Texts with the same role (same inkscape:label, e.g. "City name") must
    # share a style; unlabelled texts are grouped by similar size.
    roles = defaultdict(list)
    for e in texts:
        roles[e.get(INK + 'label')].append(e)
    groups = [g for k, g in roles.items() if k and len(g) > 1]
    loose = [e for e in texts if not any(e in g for g in groups)]
    for g in groups + clusters(loose, fsize, rel=.08):
        for key in ['font-size', 'letter-spacing', 'font-family', 'font-weight', 'fill']:
            vals = {e.get('id'): style(e, key) for e in g}
            if len(set(vals.values())) > 1:
                report('text styles', f'similar texts differ in {key}', vals)
    for e in texts:
        if len((e.get('x') or '').split()) > 1:
            report('text styles', 'per-glyph x positions (irregular spacing; prefer one x + letter-spacing)',
                   e.get('id'))

    # rects
    rects = [e for e in els if e.tag == SVG + 'rect']
    for g in clusters(rects, lambda e: float(e.get('width')), rel=.15):
        for g2 in clusters(g, lambda e: float(e.get('height')), rel=.25):
            for key in ['width', 'height']:
                vals = {e.get('id'): float(e.get(key)) for e in g2}
                if max(vals.values()) - min(vals.values()) > tol:
                    report('rects', f'similar rectangles differ in {key}', vals)

    # horizontal rules
    def is_rule(e):
        if e.tag != SVG + 'path' or not (style(e, 'stroke') or 'none') != 'none':
            return False
        x0, y0, x1, y1 = box[e.get('id')]
        return y1 - y0 < 4 and x1 - x0 > 30
    rules = [e for e in els if is_rule(e)]
    rw = lambda e: box[e.get('id')][2] - box[e.get('id')][0]
    for g in clusters(rules, rw, rel=.12):
        vals = {e.get('id'): round(rw(e), 2) for e in g}
        if max(vals.values()) - min(vals.values()) > tol:
            report('rules', 'horizontal lines of similar width differ', vals)
    ymid = lambda e: (box[e.get('id')][1] + box[e.get('id')][3])/2
    for g in clusters(rules, ymid, abs_=3):
        ys = {e.get('id'): round(ymid(e), 2) for e in g}
        if max(ys.values()) - min(ys.values()) > tol:
            report('rules', 'lines meant to be on one row are at different heights', ys)
        if len(g) == 2:
            (l0, _, l1, _), (r0, _, r1, _) = sorted(box[e.get('id')] for e in g)
            if abs((l0 + r1) - (2*vb[0] + vb[2])) > tol or abs((l1 - l0) - (r1 - r0)) > tol:
                report('rules', 'paired lines are not equal/mirrored about the page centre',
                       {e.get('id'): [round(v, 2) for v in box[e.get('id')]] for e in g})

    # margins
    layout = texts + rects + rules
    aligned = {}
    for side, k in [('left', 0), ('right', 2)]:
        aligned[side] = {e for g in clusters(layout, lambda e: box[e.get('id')][k], abs_=tol)
                         for e in g}
    for side, k in [('left', 0), ('right', 2)]:
        # objects already exactly aligned on the other side are ragged here by design
        other = aligned['right' if side == 'left' else 'left']
        cand = [e for e in layout if e not in other or e in aligned[side]]
        for g in clusters(cand, lambda e: box[e.get('id')][k], abs_=8):
            vals = {e.get('id'): round(box[e.get('id')][k], 2) for e in g}
            if max(vals.values()) - min(vals.values()) > tol:
                report('margins', f'{side} edges almost aligned', vals)
    lefts = [box[e.get('id')][0] for e in layout]
    rights = [box[e.get('id')][2] for e in layout]
    if lefts and rights:
        lm, rm = min(lefts) - vb[0], vb[0] + vb[2] - max(rights)
        if abs(lm - rm) > tol:
            report('margins', 'outer left and right margins differ', {'left': round(lm, 2), 'right': round(rm, 2)})

    # vertical rhythm per layer
    layers = [e for e in root if e.get(INK + 'groupmode') == 'layer']
    seqs = {}
    for L in layers:
        stack = [e for e in L.iter() if e in texts or e in rects]
        stack.sort(key=lambda e: box[e.get('id')][1])
        sig = tuple((e.tag.split('}')[1], e.get(INK + 'label') if e in texts else None) for e in stack)
        if len(stack) > 1:
            tops = [box[e.get('id')][1] if e in rects else float(e.get('y', 0)) for e in stack]
            seqs.setdefault(sig, []).append((L.get('id'), [round(b - a, 2) for a, b in zip(tops, tops[1:])]))
    for sig, rows in seqs.items():
        if len(rows) > 1:
            for k in range(len(rows[0][1])):
                vals = {lid: gaps[k] for lid, gaps in rows}
                if max(vals.values()) - min(vals.values()) > tol:
                    report('rhythm', f'vertical gap #{k+1} differs between layers', vals)

    # section spacing: equal gaps between sections of the same structure, and
    # wide dividers centred in the gap between the sections they separate
    sections = sorted({lid for rows in seqs.values() if len(rows) > 1 for lid, _ in rows},
                      key=lambda i: box[i][1])
    gaps = {f'{a}->{b}': round(box[b][1] - box[a][3], 2) for a, b in zip(sections, sections[1:])
            if box[b][1] > box[a][3]}
    if gaps and max(gaps.values()) - min(gaps.values()) > tol:
        report('section spacing', 'gaps between sections differ (use the mean)', gaps)
    for e in rules:
        x0, y0, x1, y1 = box[e.get('id')]
        if x1 - x0 < .5*vb[2]:
            continue
        y = (y0 + y1)/2
        if any(box[s][1] < y < box[s][3] for s in sections):
            continue  # a line inside a section (e.g. a ground line), not a divider
        above = [box[s][3] for s in sections if box[s][3] <= y]
        below = [box[s][1] for s in sections if box[s][1] >= y]
        if above and below:
            up, down = y - max(above), min(below) - y
            if abs(up - down) > tol:
                report('section spacing', 'divider not centred between sections',
                       {e.get('id'): {'above': round(up, 2), 'below': round(down, 2)}})

    # colour pairs: the relation between a section's backdrop shape (circle)
    # and its accent (rect) must be the same in every section
    pairs = {}
    for L in layers:
        if L.get('id') not in sections:
            continue
        c = next((fill_of(e) for e in L.iter(SVG + 'circle') if fill_of(e)), None)
        r = next((fill_of(e) for e in L.iter(SVG + 'rect') if fill_of(e)), None)
        if c and r:
            (l1, c1, h1), (l2, c2, h2) = oklch(c), oklch(r)
            pairs[L.get('id')] = {'circle': c, 'accent': r, 'dL': round(l1 - l2, 3),
                                  'chroma_x': round(c2/max(c1, 1e-6), 2),
                                  'dHue': round((h2 - h1 + 180) % 360 - 180, 1)}
    if len(pairs) > 1:
        spread = lambda k: max(p[k] for p in pairs.values()) - min(p[k] for p in pairs.values())
        if spread('dL') > .01 or spread('chroma_x') > .1 or spread('dHue') > 3:
            report('colour pairs', 'backdrop/accent colour relation differs between sections '
                   '(derive one from the other with one OKLCH rule)', pairs)

    # centring
    vis = [box[L.get('id')] for L in layers] or [box[root.get('id')]]
    x0, y0 = min(b[0] for b in vis), min(b[1] for b in vis)
    x1, y1 = max(b[2] for b in vis), max(b[3] for b in vis)
    cx, cy = vb[0] + vb[2]/2, vb[1] + vb[3]/2
    dx, dy = cx - (x0 + x1)/2, cy - (y0 + y1)/2
    if abs(dx) > tol or abs(dy) > tol:
        report('centring', 'artwork bbox is not centred on the page (translate by dx, dy)',
               {'bbox': [round(v, 2) for v in (x0, y0, x1, y1)], 'dx': round(dx, 2), 'dy': round(dy, 2)})
    for e in texts:
        t0, _, t1, _ = box[e.get('id')]
        off = (t0 + t1)/2 - cx
        if tol < abs(off) < 15:
            report('centred text', 'text nearly centred on the page', {e.get('id'): round(off, 2)})

    for f in findings:
        print(f"[{f['check']}] {f['message']}: {json.dumps(f['data'], ensure_ascii=False)}")
    checks = ['circles', 'text styles', 'rects', 'rules', 'margins', 'rhythm', 'section spacing',
              'colour pairs', 'centring', 'centred text']
    for c in checks:
        if not any(f['check'] == c for f in findings):
            print(f'[{c}] OK')
    print(f"artwork bbox {[round(v, 2) for v in (x0, y0, x1, y1)]}, page centre ({cx:g}, {cy:g})")
    if a.json:
        open(a.json, 'w').write(json.dumps(findings, indent=2, ensure_ascii=False))
    sys.exit(1 if findings else 0)


if __name__ == '__main__':
    main()
