"""Geometry primitives for constructed SVG illustrations.

Import from a build script:
    import sys; sys.path.insert(0, '<skill>/scripts'); from svgkit import *

Conventions
- Coordinates are reference-pixel units (viewBox = reference size).
- Paths use fill-rule nonzero. Solids are emitted clockwise on screen and
  openings counter-clockwise, so overlapping solids in one path merge without
  seams and openings cut through (as long as only ONE solid covers them).
- Every function returns SVG path data (a string) for one closed subpath.
"""


def f(v):
    """Compact number formatting (2 decimals, no trailing zeros)."""
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def pt(x, y):
    return f'{f(x)},{f(y)}'


def _area(points):
    return sum(x0*y1 - x1*y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))


def poly(points, hole=False):
    """Closed polygon; orientation is fixed automatically (solid or hole)."""
    points = list(points)
    if (_area(points) > 0) == hole:
        points = points[::-1]
    return 'M' + ' '.join(pt(x, y) for x, y in points) + 'Z'


def rect(x0, y0, x1, y1, hole=False):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], hole)


def mirror(points, axis):
    """Mirror a point list about the vertical line x = axis."""
    return [(2*axis - x, y) for x, y in points]


def symmetric(half, axis):
    """Full outline from the LEFT half: `half` runs from a point on the axis
    (top) outward/downward to the bottom-left corner. Returns point list."""
    right = mirror(half, axis)[::-1]
    return right[:-1] + half if half[0][0] == axis else right + half


def arch(x, y, w, h, hole=True):
    """Window with a semicircular head; (x, y) top-left of the bounding box."""
    r = w/2
    if hole:
        return (f'M{pt(x, y+h)}H{f(x+w)}V{f(y+r)}'
                f'A{f(r)},{f(r)} 0 0 0 {pt(x, y+r)}Z')
    return (f'M{pt(x, y+h)}V{f(y+r)}'
            f'A{f(r)},{f(r)} 0 0 1 {pt(x+w, y+r)}V{f(y+h)}Z')


def arch_c(cx, top, w, bottom, hole=True):
    """Arched window by centre x, top (apex) y, width and bottom y."""
    return arch(cx - w/2, top, w, bottom - top, hole)


def facade_line(roof, ground, fraction, ground_fn=None):
    """Vanishing line on a receding facade at a constant fraction of the local
    facade height. `roof(x)` is the eaves line; `ground` is the ground y (or
    pass ground_fn(x) for a sloped base). Returns y(x)."""
    base = ground_fn or (lambda x: ground)
    return lambda x: base(x) - fraction*(base(x) - roof(x))


def perspective_arch(cx, w, head_line, sill_line):
    """Arched opening on a receding facade: the sill and the arch springing
    follow the facade's vanishing lines (head_line/sill_line map x -> y,
    head_line gives the apex height)."""
    r = w/2
    a, b = cx - r, cx + r
    return (f'M{pt(a, sill_line(a))}L{pt(b, sill_line(b))}'
            f'L{pt(b, head_line(b) + r)}A{f(r)},{f(r)} 0 0 0 {pt(a, head_line(a) + r)}Z')


def perspective_row(vx, first_cx, last_cx, n):
    """Window centres on a receding facade: distance from the vanishing point
    grows geometrically. Returns list of (cx, depth) with depth = cx - vx, so
    sizes can scale as k*depth."""
    first, last = first_cx - vx, last_cx - vx
    q = (last/first)**(1/(n - 1))
    return [(vx + first*q**k, first*q**k) for k in range(n)]


def vanishing_x(roof_point, roof_slope, ground):
    """x where an eaves line (point + slope dy/dx) meets a horizontal ground."""
    x0, y0 = roof_point
    return x0 + (ground - y0)/roof_slope


def half_ellipse(cx, cy, rx, ry, hole=False):
    """Upper half of an ellipse closed along its base chord (domes, tanks)."""
    sweep = 0 if hole else 1
    return f'M{pt(cx-rx, cy)}A{f(rx)},{f(ry)} 0 0 {sweep} {pt(cx+rx, cy)}Z'


def ellipse(cx, cy, rx, ry, hole=False):
    s = 0 if hole else 1
    return (f'M{pt(cx-rx, cy)}A{f(rx)},{f(ry)} 0 1 {s} {pt(cx+rx, cy)}'
            f'A{f(rx)},{f(ry)} 0 1 {s} {pt(cx-rx, cy)}Z')


def spike(cx, base, top, half):
    """Isosceles triangle: spires, finials, pinnacles."""
    return poly([(cx-half, base), (cx, top), (cx+half, base)])


def thin_band(points, thickness, hole=True):
    """Straight-segment polyline of constant vertical thickness (light cut
    lines, rails). points run left to right."""
    return poly(list(points) + [(x, y + thickness) for x, y in points[::-1]], hole)


def column_hole(cx, w, top, bottom, cap=1.2, inset=0.8):
    """Light classical column: shaft with slightly wider capital and base."""
    a, c = cx - w/2, cx + w/2
    return poly([(a, top), (c, top), (c, top+cap), (c-inset, top+cap),
                 (c-inset, bottom-cap), (c, bottom-cap), (c, bottom), (a, bottom),
                 (a, bottom-cap), (a+inset, bottom-cap), (a+inset, top+cap),
                 (a, top+cap)], hole=True)


def line_through(p0, p1):
    """y(x) for the straight line through two points."""
    (x0, y0), (x1, y1) = p0, p1
    m = (y1 - y0)/(x1 - x0)
    return lambda x: y0 + m*(x - x0)


def x_on_line(p0, p1, y):
    """x of the line through p0, p1 at height y (legs, struts)."""
    (x0, y0), (x1, y1) = p0, p1
    return x0 + (x1 - x0)*(y - y0)/(y1 - y0)


def translate_path(d, dx, dy):
    """Bake a translation into path data (absolute commands are shifted;
    relative ones are unchanged except an initial m). Use it to move or
    centre artwork without adding transform attributes."""
    import re
    out, cmd, nums = [], None, []

    def flush():
        if cmd is None:
            return
        v = [float(n) for n in nums]
        if cmd in 'MLCSQT':
            v = [n + (dx if k % 2 == 0 else dy) for k, n in enumerate(v)]
        elif cmd == 'H':
            v = [n + dx for n in v]
        elif cmd == 'V':
            v = [n + dy for n in v]
        elif cmd == 'A':
            v = [n + (dx if k % 7 == 5 else dy if k % 7 == 6 else 0) for k, n in enumerate(v)]
        elif cmd == 'm' and not out:
            v[:2] = [v[0] + dx, v[1] + dy]
        out.append(cmd + ' '.join(f(n) for n in v))
    for t in re.findall(r'[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?', d):
        if t.isalpha():
            flush()
            cmd, nums = t, []
        else:
            nums.append(t)
    flush()
    return ''.join(out)


class Part:
    """One editable object (one <path>): solids + openings.

    knockouts collects openings and intentional gaps so a backdrop shape
    (e.g. a coloured disc) can be clipped and not show through them."""

    def __init__(self, id, name):
        self.id, self.name = id, name
        self.solids, self.holes, self.knockouts = [], [], []

    def add(self, *d):
        self.solids.extend(d)
        return self

    def cut(self, *d, knockout=True):
        self.holes.extend(d)
        if knockout:
            self.knockouts.extend(d)
        return self

    def gap(self, d):
        """Register an intentional empty gap between two objects."""
        self.knockouts.append(d)
        return self

    @property
    def d(self):
        return ''.join(self.solids + self.holes)
