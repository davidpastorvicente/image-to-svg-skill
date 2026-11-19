"""Primitives for orthogonal architectural floor plans.

Import next to svgkit:
    import sys; sys.path.insert(0, '<skill>/scripts')
    from svgkit import *; from plankit import *

Conventions (same as svgkit)
- Coordinates are reference-pixel units (viewBox = reference size), y down.
- Filled outlines are emitted for fill-rule nonzero: solids clockwise on
  screen, holes counter-clockwise.
- Functions return SVG path data strings. Fills (walls) are meant for a
  filled <path>; doors, windows and hatches return *centre lines* meant for a
  stroked <path> (fill="none", one stroke-width per role).
"""
from math import cos, sin, radians

from svgkit import f, poly, pt

DIRS = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


# --- snapping ---------------------------------------------------------------

def snap(v, step=0.5):
    return round(v/step)*step


def clusters(values, tol=2.0, step=0.5):
    """Group measured coordinates that are within `tol` of each other and map
    each to the cluster mean (snapped to `step`). Returns {raw: snapped}.
    Use it on all wall-edge x's (and separately y's) so walls that line up in
    the plan share exactly one coordinate."""
    vals = sorted(set(values))
    out, group = {}, []

    def close():
        m = snap(sum(group)/len(group), step)
        out.update({g: m for g in group})
    for v in vals:
        if group and v - group[-1] > tol:
            close()
            group = []
        group.append(v)
    if group:
        close()
    return out


# --- walls ------------------------------------------------------------------

def wall_h(y, x0, x1, t, extend=True):
    """Horizontal wall by centre line y (x0..x1 between wall axes) and
    thickness t -> rect tuple. `extend` adds t/2 at both ends so corners and
    T-junctions with perpendicular walls close without notches."""
    e = t/2 if extend else 0
    return (min(x0, x1) - e, y - t/2, max(x0, x1) + e, y + t/2)


def wall_v(x, y0, y1, t, extend=True):
    """Vertical wall by centre line x and thickness t -> rect tuple."""
    e = t/2 if extend else 0
    return (x - t/2, min(y0, y1) - e, x + t/2, max(y0, y1) + e)


def rects_union(solids, holes=()):
    """Boolean union of axis-aligned rects (x0, y0, x1, y1) minus `holes`,
    as clean path data: one outline per connected wall mass, inner courtyards
    as holes, no overlapping subpaths (so no seams, and openings always cut),
    collinear vertices removed. Rects may overlap freely."""
    xs = sorted({v for r in list(solids) + list(holes) for v in (r[0], r[2])})
    ys = sorted({v for r in list(solids) + list(holes) for v in (r[1], r[3])})
    xi = {v: i for i, v in enumerate(xs)}
    yi = {v: i for i, v in enumerate(ys)}
    nx, ny = len(xs) - 1, len(ys) - 1
    grid = [[False]*nx for _ in range(ny)]

    def paint(r, val):
        x0, x1 = sorted((r[0], r[2]))
        y0, y1 = sorted((r[1], r[3]))
        for j in range(yi[y0], yi[y1]):
            for i in range(xi[x0], xi[x1]):
                grid[j][i] = val
    for r in solids:
        paint(r, True)
    for r in holes:
        paint(r, False)

    def filled(i, j):
        return 0 <= i < nx and 0 <= j < ny and grid[j][i]

    # directed boundary edges, clockwise on screen around filled cells
    nxt = {}
    for j in range(ny):
        for i in range(nx):
            if not grid[j][i]:
                continue
            if not filled(i, j-1):
                nxt.setdefault((i, j), []).append((i+1, j))
            if not filled(i+1, j):
                nxt.setdefault((i+1, j), []).append((i+1, j+1))
            if not filled(i, j+1):
                nxt.setdefault((i+1, j+1), []).append((i, j+1))
            if not filled(i-1, j):
                nxt.setdefault((i, j+1), []).append((i, j))

    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, cur, prev_dir = [start], start, None
        while True:
            outs = nxt[cur]
            if len(outs) > 1 and prev_dir is not None:
                # pinch vertex: take the right-hand turn so loops stay simple
                def turn(o):
                    d = (o[0]-cur[0], o[1]-cur[1])
                    return prev_dir[0]*d[1] - prev_dir[1]*d[0]
                outs.sort(key=turn, reverse=True)
            nx_ = outs.pop(0)
            if not outs:
                del nxt[cur]
            prev_dir = (nx_[0]-cur[0], nx_[1]-cur[1])
            cur = nx_
            if cur == start:
                break
            loop.append(cur)
        loops.append(loop)

    d = []
    for loop in loops:
        n = len(loop)
        keep = []
        for k in range(n):
            a, b, c = loop[k-1], loop[k], loop[(k+1) % n]
            if (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]) != 0:
                keep.append(b)
        d.append('M' + ' '.join(pt(xs[i], ys[j]) for i, j in keep) + 'Z')
    return ''.join(d)


# --- doors and windows (stroked centre lines) ---------------------------------

def _arc(hinge, a, b, r):
    """90° (or any) arc from point a to point b around hinge."""
    v1 = (a[0]-hinge[0], a[1]-hinge[1])
    v2 = (b[0]-hinge[0], b[1]-hinge[1])
    sweep = 1 if v1[0]*v2[1] - v1[1]*v2[0] > 0 else 0
    return f'M{pt(*a)}A{f(r)},{f(r)} 0 0 {sweep} {pt(*b)}'


def door(hinge, width, closed, opened):
    """Swing door. `hinge` = pivot point at one jamb; `closed` = direction
    from the hinge across the opening ('up'/'down'/'left'/'right');
    `opened` = direction of the open leaf (perpendicular to `closed`).
    Returns (leaf, arc) path data: draw the leaf with the heavier stroke and
    the swing arc with the thin one."""
    hx, hy = hinge
    c, o = DIRS[closed], DIRS[opened]
    tip_open = (hx + o[0]*width, hy + o[1]*width)
    tip_closed = (hx + c[0]*width, hy + c[1]*width)
    return f'M{pt(hx, hy)}L{pt(*tip_open)}', _arc(hinge, tip_open, tip_closed, width)


def double_door(jamb_a, jamb_b, opened):
    """Two equal leaves hinged at both jambs of one opening."""
    (ax, ay), (bx, by) = jamb_a, jamb_b
    horizontal = ay == by
    half = abs(bx-ax)/2 if horizontal else abs(by-ay)/2
    toward_b = ('right' if bx > ax else 'left') if horizontal else ('down' if by > ay else 'up')
    toward_a = {'right': 'left', 'left': 'right', 'up': 'down', 'down': 'up'}[toward_b]
    l1, a1 = door(jamb_a, half, toward_b, opened)
    l2, a2 = door(jamb_b, half, toward_a, opened)
    return l1 + l2, a1 + a2


def sliding_door(x0, y0, x1, y1, panels=2, overlap=0.1):
    """Sliding panels as thin rect outlines staggered across the wall
    thickness; box = the wall opening."""
    horizontal = (x1-x0) >= (y1-y0)
    L = (x1-x0) if horizontal else (y1-y0)
    T = (y1-y0) if horizontal else (x1-x0)
    w = L/panels*(1 + overlap)
    d = []
    for k in range(panels):
        s = x0 + k*(L - w)/(panels - 1) if horizontal else y0 + k*(L - w)/(panels - 1)
        off = T*(0.25 if k % 2 == 0 else 0.55)
        if horizontal:
            d.append(f'M{pt(s, y0+off)}H{f(s+w)}V{f(y0+off+T*0.2)}H{f(s)}Z')
        else:
            d.append(f'M{pt(x0+off, s)}V{f(s+w)}H{f(x0+off+T*0.2)}V{f(s)}Z')
    return ''.join(d)


def window(x0, y0, x1, y1, lines=3, ends=True):
    """Window in a wall opening (box = opening). `lines` parallel lines along
    the long axis spread evenly across the wall thickness (2 = frame faces
    only, 3 = with glass line); `ends` closes both jambs."""
    horizontal = (x1-x0) >= (y1-y0)
    d = []
    for k in range(lines):
        t = k/(lines-1) if lines > 1 else 0.5
        if horizontal:
            d.append(f'M{pt(x0, y0 + t*(y1-y0))}H{f(x1)}')
        else:
            d.append(f'M{pt(x0 + t*(x1-x0), y0)}V{f(y1)}')
    if ends:
        if horizontal:
            d.append(f'M{pt(x0, y0)}V{f(y1)}M{pt(x1, y0)}V{f(y1)}')
        else:
            d.append(f'M{pt(x0, y0)}H{f(x1)}M{pt(x0, y1)}H{f(x1)}')
    return ''.join(d)


# --- hatching -----------------------------------------------------------------

def hatch(rings, spacing, angle=45, phase=0.0):
    """Parallel hatch lines clipped exactly to a region, as stroked path data
    (no clipPath needed). `rings` = one point list or a list of point lists
    (outer outline + holes, even-odd). `angle` in degrees as seen on screen,
    counter-clockwise from horizontal (0 = horizontal, 90 = vertical,
    45 = '/'). Lines sit on a global grid (offset = phase + k*spacing), so
    adjacent regions with the same settings continue seamlessly."""
    if rings and isinstance(rings[0][0], (int, float)):
        rings = [rings]
    a = radians(angle)
    u = (cos(a), -sin(a))
    n = (sin(a), cos(a))
    edges = []
    for ring in rings:
        for p, q in zip(ring, ring[1:] + ring[:1]):
            edges.append(((p[0]*n[0] + p[1]*n[1], p[0]*u[0] + p[1]*u[1]),
                          (q[0]*n[0] + q[1]*n[1], q[0]*u[0] + q[1]*u[1])))
    smin = min(min(e[0][0], e[1][0]) for e in edges)
    smax = max(max(e[0][0], e[1][0]) for e in edges)
    k0 = int((smin - phase)//spacing) + 1
    d = []
    s = phase + k0*spacing
    while s < smax:
        ts = []
        for (sp, tp), (sq, tq) in edges:
            if (sp <= s < sq) or (sq <= s < sp):
                ts.append(tp + (s - sp)/(sq - sp)*(tq - tp))
        ts.sort()
        for t0, t1 in zip(ts[::2], ts[1::2]):
            p0 = (s*n[0] + t0*u[0], s*n[1] + t0*u[1])
            p1 = (s*n[0] + t1*u[0], s*n[1] + t1*u[1])
            d.append(f'M{pt(*p0)}L{pt(*p1)}')
        s += spacing
    return ''.join(d)


def rect_ring(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# --- misc symbols ---------------------------------------------------------------

def arrow(tip, size, direction):
    """Solid triangle marker (entrance arrows) pointing in `direction`."""
    dx, dy = DIRS[direction]
    bx, by = tip[0] - dx*size, tip[1] - dy*size
    px, py = -dy*size*0.6, dx*size*0.6
    return poly([tip, (bx + px, by + py), (bx - px, by - py)])


def dashed_rect(x0, y0, x1, y1):
    """Outline for a stroked path with stroke-dasharray (hidden/overhead
    elements: shelving, tendederos, cupboards above)."""
    return f'M{pt(x0, y0)}H{f(x1)}V{f(y1)}H{f(x0)}Z'
