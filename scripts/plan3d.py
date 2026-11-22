#!/usr/bin/env python3
"""Navigable 3D model of a floor plan built with plankit.

    python3 <skill>/scripts/plan3d.py path/to/config.toml

Inputs
  plan JSON   geometry written by the plan's build script (walls, rooms,
              doors, windows, wardrobes, labels) — see references/plan-3d.md
  config.toml heights, per-opening overrides, finishes, colours, walk start
              (every key optional; defaults below)
Outputs (next to the config)
  <output>.glb   glTF 2.0 model in metres, Y up (Blender, Preview, three.js…)
  <output>.html  self-contained viewer (model + three.js inlined): opens with
                 a double click, offline. Model / plan / first-person walk.

A floor plan has no heights: every vertical value comes from the config.
Plan x -> X, plan y -> Z, height -> Y. Python >= 3.11, stdlib only.
"""
import argparse
import base64
import json
import struct
import tomllib
from array import array
from bisect import bisect_right
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEWER = HERE / 'plan3d_viewer'
FLOOR_T = 2   # cm, floor finish thickness below level 0

DEFAULTS = {
    'plan': 'plan3d.json',          # plan JSON, relative to the config
    'output': 'model',              # basename of the .glb / .html
    'title': 'Floor plan',
    'units_per_m': None,            # plan units per metre (overrides the JSON)
    'heights': {                    # cm
        'ceiling': 260, 'slab': 25, 'door': 210, 'sill': 100, 'head': 210,
        'wardrobe': 240, 'outdoor_wall': 200, 'eye': 165,
    },
    'roof': {'reach': 60},          # cm: walls this close to an indoor floor are roofed
    'doors': {},                    # [doors.<key>] height
    'windows': {},                  # [windows.<key>] sill, head | match_door
    'finishes': {
        'glass_doors': [], 'exterior_doors': [], 'outdoor_rooms': [],
        'default_floor': 'wood', 'floors': {},
    },
    'colors': {
        'wall': '#efebe4', 'outdoor_wall': '#e2dbcf', 'ceiling': '#ffffff', 'wardrobe': '#e9dfcc',
        'door': '#ffffff', 'exterior_door': '#6b4f3a', 'glass': '#a9cfe3', 'glass_opacity': 0.25,
        'wood': '#c39b6e', 'tile': '#d9d8d3', 'decking': '#8b6a4b', 'decking_gap': '#4a3a2c',
        'grass': '#a3c47a', 'threshold': '#b8ad9c',
    },
    'decking': {'board': 12.6, 'period': 14, 'along': 'y'},   # cm; boards run along plan x or y
    'walk': {'start': None, 'heading': 0, 'speed': 1.4},      # heading: 0 = plan top, 90 = right
    'viewer': {'label_font': "Futura, 'Avenir Next', sans-serif"},
}


def merged(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = merged(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


# ---------- plan -> classified grid ----------

def inside(px, py, r):
    return min(r[0], r[2]) < px < max(r[0], r[2]) and min(r[1], r[3]) < py < max(r[1], r[3])


def rect_gap(a, b):
    dx = max(0, a[0] - b[2], b[0] - a[2])
    dy = max(0, a[1] - b[3], b[1] - a[3])
    return (dx*dx + dy*dy)**0.5


class Grid:
    """The plan's coordinate grid (every rect edge), one class per cell:
    ('floor', room|None) ('wardrobe',) ('door', key) ('window', key) ('wall',) or None."""

    def __init__(self, P):
        floors = P.get('floors', {})
        self.regions = [('floor', room, r) for room, rs in floors.items() for r in rs]
        self.regions += [('wardrobe', None, r) for r in P.get('wardrobes', [])]
        self.regions += [('door', k, u['hole']) for k, u in P.get('doors', {}).items()]
        self.regions += [('window', k, u['hole']) for k, u in P.get('windows', {}).items()]
        self.solids, self.envelope = P.get('solids'), P.get('envelope')
        assert bool(self.solids) != bool(self.envelope), 'plan JSON needs "envelope" or "solids"'
        every = [r for *_, r in self.regions] + (self.solids or self.envelope)
        xs = {round(v, 3) for r in every for v in (r[0], r[2])}
        ys = {round(v, 3) for r in every for v in (r[1], r[3])}
        xs |= {min(xs) - 1, max(xs) + 1}           # margin ring: outside always touches the border
        ys |= {min(ys) - 1, max(ys) + 1}
        self.xs, self.ys = sorted(xs), sorted(ys)
        self.nx, self.ny = len(self.xs) - 1, len(self.ys) - 1
        self.c = [[self.cell_class(i, j) for i in range(self.nx)] for j in range(self.ny)]

    def centre(self, i, j):
        return (self.xs[i] + self.xs[i + 1])/2, (self.ys[j] + self.ys[j + 1])/2

    def cell_class(self, i, j):
        cx, cy = self.centre(i, j)
        for kind, key, r in self.regions:
            if inside(cx, cy, r):
                return (kind, key) if kind != 'wardrobe' else ('wardrobe',)
        if self.solids:
            return ('wall',) if any(inside(cx, cy, r) for r in self.solids) else 'free'
        return ('wall',) if any(inside(cx, cy, r) for r in self.envelope) else None

    def locate(self, x, y):
        return bisect_right(self.xs, x) - 1, bisect_right(self.ys, y) - 1

    def flood_rooms(self, labels):
        """Free cells (plans given wall by wall) become rooms: each enclosed
        region takes the label inside it (nearest label if several); regions
        open to the outside are dropped."""
        seen = [[False]*self.nx for _ in range(self.ny)]
        pts = {room: self.locate(lb['x'], lb['y']) for room, lb in labels.items()}
        for j0 in range(self.ny):
            for i0 in range(self.nx):
                if self.c[j0][i0] != 'free' or seen[j0][i0]:
                    continue
                comp, q, outside = [], deque([(i0, j0)]), False
                seen[j0][i0] = True
                while q:
                    i, j = q.popleft()
                    comp.append((i, j))
                    if i in (0, self.nx - 1) or j in (0, self.ny - 1):
                        outside = True
                    for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                        if 0 <= a < self.nx and 0 <= b < self.ny and not seen[b][a] and self.c[b][a] == 'free':
                            seen[b][a] = True
                            q.append((a, b))
                cells = set(comp)
                rooms = [room for room, p in pts.items() if p in cells]
                for i, j in comp:
                    if outside:
                        self.c[j][i] = None
                    elif len(rooms) <= 1:
                        self.c[j][i] = ('floor', rooms[0] if rooms else None)
                    else:
                        cx, cy = self.centre(i, j)
                        self.c[j][i] = ('floor', min(rooms, key=lambda r: (labels[r]['x'] - cx)**2
                                                     + (labels[r]['y'] - cy)**2))

    def merge(self, key=lambda c: c):
        """{key(class): [rects]}: horizontal runs, stacked when the extent matches."""
        out, open_ = {}, {}
        for j in range(self.ny + 1):
            runs, i = {}, 0
            row = [key(c) for c in self.c[j]] if j < self.ny else [None]*self.nx
            while i < self.nx:
                c, i0 = row[i], i
                while i < self.nx and row[i] == c:
                    i += 1
                if c is not None:
                    runs[(c, i0, i)] = j
            for k, j0 in list(open_.items()):
                if k in runs:
                    runs[k] = j0
                else:
                    c, i0, i1 = k
                    out.setdefault(c, []).append((self.xs[i0], self.ys[j0], self.xs[i1], self.ys[j]))
            open_ = runs
        return out


def roof_flags(grid, P, outdoor, reach):
    """roofed[j][i]: explicit `roofed` rects from the plan, else indoor floors,
    wardrobes, and walls/openings within `reach` of an indoor floor."""
    if P.get('roofed'):
        return [[grid.c[j][i] is not None and any(inside(*grid.centre(i, j), r) for r in P['roofed'])
                 for i in range(grid.nx)] for j in range(grid.ny)]
    indoor = [r for (kind, *rest), rs in grid.merge().items() if kind == 'floor' and rest[0] not in outdoor
              for r in rs]
    flags = []
    for j in range(grid.ny):
        row = []
        for i in range(grid.nx):
            c = grid.c[j][i]
            if c is None:
                row.append(False)
            elif c[0] == 'floor':
                row.append(c[1] not in outdoor)
            elif c[0] == 'wardrobe':
                row.append(True)
            else:
                cx, cy = grid.centre(i, j)
                row.append(any(rect_gap((cx, cy, cx, cy), r) <= reach for r in indoor))
        flags.append(row)
    return flags


# ---------- boxes -> glTF ----------

def srgb_to_linear(hexcol, alpha=1.0):
    h = hexcol.lstrip('#')
    rgb = [int(h[k:k + 2], 16)/255 for k in (0, 2, 4)]
    return [c/12.92 if c <= 0.04045 else ((c + 0.055)/1.055)**2.4 for c in rgb] + [alpha]


class Mesh:
    """Boxes grouped by material; one glTF primitive per material.
    Rects in plan units (scaled by k to metres), heights in cm."""

    def __init__(self, k):
        self.k, self.parts = k, {}

    def box(self, rect, z0, z1, mat):
        if z1 <= z0:
            return
        x0, y0, x1, y1 = (v*self.k for v in rect)
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = z0/100, z1/100
        pos, nor, idx = self.parts.setdefault(mat, (array('f'), array('f'), array('I')))
        # (normal, 4 corners) in glTF axes: X = plan x, Y = height, Z = plan y
        faces = [((1, 0, 0), [(x1, z0, y0), (x1, z1, y0), (x1, z1, y1), (x1, z0, y1)]),
                 ((-1, 0, 0), [(x0, z0, y0), (x0, z0, y1), (x0, z1, y1), (x0, z1, y0)]),
                 ((0, 1, 0), [(x0, z1, y0), (x0, z1, y1), (x1, z1, y1), (x1, z1, y0)]),
                 ((0, -1, 0), [(x0, z0, y0), (x1, z0, y0), (x1, z0, y1), (x0, z0, y1)]),
                 ((0, 0, 1), [(x0, z0, y1), (x1, z0, y1), (x1, z1, y1), (x0, z1, y1)]),
                 ((0, 0, -1), [(x0, z0, y0), (x0, z1, y0), (x1, z1, y0), (x1, z0, y0)])]
        for n, q in faces:
            a, b, c = q[0], q[1], q[2]
            u = [b[m] - a[m] for m in range(3)]
            v = [c[m] - a[m] for m in range(3)]
            cr = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
            if sum(cr[m]*n[m] for m in range(3)) < 0:      # CCW seen from outside
                q = q[::-1]
            base = len(pos)//3
            for p in q:
                pos.extend(p)
                nor.extend(n)
            idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])


class GLB:
    def __init__(self, colors):
        self.colors, self.bin, self.mats = colors, bytearray(), {}
        self.j = {'asset': {'version': '2.0', 'generator': 'image-to-svg plan3d.py'},
                  'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'name': 'house', 'children': []}],
                  'meshes': [], 'materials': [], 'accessors': [], 'bufferViews': [], 'buffers': []}

    def material(self, name):
        if name not in self.mats:
            glass = name == 'glass'
            col = srgb_to_linear(self.colors[name], self.colors['glass_opacity'] if glass else 1.0)
            m = {'name': name, 'pbrMetallicRoughness': {'baseColorFactor': col, 'metallicFactor': 0.0,
                                                        'roughnessFactor': 0.1 if glass else 0.9}}
            if glass:
                m.update(alphaMode='BLEND', doubleSided=True)
            self.mats[name] = len(self.j['materials'])
            self.j['materials'].append(m)
        return self.mats[name]

    def view(self, data, target):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.j['bufferViews'].append({'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data),
                                      'target': target})
        self.bin += data
        return len(self.j['bufferViews']) - 1

    def accessor(self, arr, kind):
        if kind == 'idx':
            a = {'bufferView': self.view(arr.tobytes(), 34963), 'componentType': 5125, 'count': len(arr),
                 'type': 'SCALAR'}
        else:
            a = {'bufferView': self.view(arr.tobytes(), 34962), 'componentType': 5126, 'count': len(arr)//3,
                 'type': 'VEC3'}
            if kind == 'pos':
                a['min'] = [min(arr[m::3]) for m in range(3)]
                a['max'] = [max(arr[m::3]) for m in range(3)]
        self.j['accessors'].append(a)
        return len(self.j['accessors']) - 1

    def node(self, name, mesh=None, parent=0, extras=None):
        n = {'name': name}
        if mesh is not None and mesh.parts:
            prims = [{'attributes': {'POSITION': self.accessor(p, 'pos'), 'NORMAL': self.accessor(nr, 'nor')},
                      'indices': self.accessor(ix, 'idx'), 'material': self.material(mat)}
                     for mat, (p, nr, ix) in mesh.parts.items()]
            self.j['meshes'].append({'name': name, 'primitives': prims})
            n['mesh'] = len(self.j['meshes']) - 1
        if extras:
            n['extras'] = extras
        self.j['nodes'].append(n)
        i = len(self.j['nodes']) - 1
        self.j['nodes'][parent].setdefault('children', []).append(i)
        return i

    def bytes(self):
        self.j['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(self.j, separators=(',', ':')).encode()
        js += b' '*(-len(js) % 4)
        bn = bytes(self.bin) + b'\0'*(-len(self.bin) % 4)
        total = 12 + 8 + len(js) + 8 + len(bn)
        return (struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(js), 0x4E4F534A) + js
                + struct.pack('<II', len(bn), 0x004E4942) + bn)


# ---------- model ----------

class Model:
    def __init__(self, cfg, P):
        self.cfg, self.P = cfg, P
        self.upm = cfg['units_per_m'] or P.get('units_per_m')
        assert self.upm, 'set units_per_m in the config (plan units per metre)'
        self.k = 1/self.upm
        self.H, self.fin = cfg['heights'], cfg['finishes']
        self.outdoor = set(self.fin['outdoor_rooms'])

    def cm(self, v):
        """cm -> plan units."""
        return v*self.upm/100

    def door_h(self, key):
        return self.cfg['doors'].get(key, {}).get('height', self.H['door'])

    def window_h(self, key):
        o = self.cfg['windows'].get(key, {})
        if 'match_door' in o:
            return 0, self.door_h(o['match_door'])
        return o.get('sill', self.H['sill']), o.get('head', self.H['head'])

    def mesh(self):
        return Mesh(self.k)

    def build(self):
        P, H = self.P, self.H
        labels = P.get('labels', {})
        grid = Grid(P)
        grid.flood_rooms(labels)
        roof = roof_flags(grid, P, self.outdoor, self.cm(self.cfg['roof']['reach']))
        ceiling, out_h = H['ceiling'], H['outdoor_wall']
        for j in range(grid.ny):
            for i in range(grid.nx):
                c = grid.c[j][i]
                if c is not None and c[0] in ('wall', 'door', 'window'):
                    grid.c[j][i] = (*c, roof[j][i])
        cells = grid.merge()
        glb = GLB(self.cfg['colors'])

        def top(roofed):
            return ceiling if roofed else out_h

        def wall_mat(roofed):
            return 'wall' if roofed else 'outdoor_wall'

        walls, openings = self.mesh(), self.mesh()
        for c, rs in cells.items():
            kind = c[0]
            for r in rs:
                if kind == 'wall':
                    walls.box(r, 0, top(c[1]), wall_mat(c[1]))
                elif kind == 'door':
                    t = top(c[2])
                    openings.box(r, min(self.door_h(c[1]), t), t, wall_mat(c[2]))
                    openings.box(r, -FLOOR_T, 0, 'threshold')
                elif kind == 'window':
                    sill, head = self.window_h(c[1])
                    openings.box(r, 0, sill, wall_mat(c[2]))
                    if sill <= 0:
                        openings.box(r, -FLOOR_T, 0, 'threshold')
                    openings.box(r, head, top(c[2]), wall_mat(c[2]))
        g = glb.node('walls', walls)
        glb.node('openings', openings, parent=g)

        wardrobes = self.mesh()
        for r in cells.get(('wardrobe',), []):
            wardrobes.box(r, 0, H['wardrobe'], 'wardrobe')
            wardrobes.box(r, H['wardrobe'], ceiling, 'wall')
        glb.node('wardrobes', wardrobes)

        roof_m = self.mesh()
        classes = grid.c
        grid.c = [[True if roof[j][i] else None for i in range(grid.nx)] for j in range(grid.ny)]
        roof_rects = grid.merge().get(True, [])
        grid.c = classes
        for r in roof_rects:
            roof_m.box(r, ceiling, ceiling + H['slab'], 'ceiling')
        glb.node('ceiling', roof_m)

        gd = glb.node('doors')
        for key, u in P.get('doors', {}).items():
            m = self.mesh()
            mat = ('glass' if key in self.fin['glass_doors'] else
                   'exterior_door' if key in self.fin['exterior_doors'] else 'door')
            for leaf in u.get('leaves', []):
                m.box(leaf, 0, self.door_h(key) - 1, mat)
            glb.node(f'door-{key}', m, parent=gd)

        gw = glb.node('windows')
        for key, u in P.get('windows', {}).items():
            sill, head = self.window_h(key)
            m = self.mesh()
            for fr in u.get('frames', []):
                m.box(fr, sill, head, 'glass')
            glb.node(f'window-{key}', m, parent=gw)

        gf = glb.node('floors')
        rooms, areas = [], {}
        floor_cells = {c[1]: rs for c, rs in cells.items() if c[0] == 'floor'}
        for room in list(labels) + [r for r in floor_cells if r not in labels]:
            rs = floor_cells.get(room, [])
            if not rs:
                continue
            mat = self.fin['floors'].get(room, self.fin['default_floor'])
            m = self.mesh()
            if mat == 'decking':
                self.deck(m, rs)
            else:
                for r in rs:
                    m.box(r, -FLOOR_T, 0, mat)
            areas[room] = sum((r[2] - r[0])*(r[3] - r[1]) for r in rs)/self.upm**2
            lb = labels.get(room)
            info = None
            if lb:
                info = {'name': lb['name'], 'area': lb.get('area', ''), 'x': lb['x']*self.k,
                        'z': lb['y']*self.k, 'rotated': bool(lb.get('rotated')), 'outdoor': room in self.outdoor}
                rooms.append({'id': room, **info})
            glb.node(f'floor-{room or "unnamed"}', m, parent=gf, extras=info)
        return glb, rooms, areas

    def deck(self, m, rs):
        """Decking boards along plan x or y, starting at the room's edge."""
        d = self.cfg['decking']
        board, period = self.cm(d['board']), self.cm(d['period'])
        along_y = d['along'] == 'y'
        start = min(r[0] if along_y else r[1] for r in rs)
        for r in rs:
            x0, y0, x1, y1 = r
            m.box(r, -FLOOR_T, -FLOOR_T/2, 'decking_gap')
            lo, hi = (x0, x1) if along_y else (y0, y1)
            s = start
            while s < hi:
                a, b = max(s, lo), min(s + board, hi)
                if b > a:
                    m.box((a, y0, b, y1) if along_y else (x0, a, x1, b), -FLOOR_T, 0, 'decking')
                s += period

    def bounds(self):
        rects = (self.P.get('solids') or self.P.get('envelope')) + [
            r for rs in self.P.get('floors', {}).values() for r in rs]
        return [min(r[0] for r in rects)*self.k, min(r[1] for r in rects)*self.k,
                max(r[2] for r in rects)*self.k, max(r[3] for r in rects)*self.k]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('config', type=Path)
    a = ap.parse_args()
    cfg_path = a.config.resolve()
    cfg = merged(DEFAULTS, tomllib.loads(cfg_path.read_text(encoding='utf-8')))
    P = json.loads((cfg_path.parent / cfg['plan']).read_text(encoding='utf-8'))
    model = Model(cfg, P)
    glb, rooms, areas = model.build()
    data = glb.bytes()
    out = cfg_path.parent / cfg['output']
    out.with_suffix('.glb').write_bytes(data)
    scene = {'glb': base64.b64encode(data).decode(), 'rooms': rooms, 'bounds': model.bounds(),
             'heights': {k: v/100 for k, v in cfg['heights'].items()}, 'walk': cfg['walk'],
             'title': cfg['title'], 'labelSize': P.get('label_size', model.cm(19))*model.k,
             'labelFont': cfg['viewer']['label_font']}
    bundle = (VIEWER / 'viewer.bundle.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
    html = (VIEWER / 'template.html').read_text(encoding='utf-8')
    html = html.replace('/*SCENE*/', 'window.SCENE = ' + json.dumps(scene, ensure_ascii=False) + ';')
    html = html.replace('/*VIEWER*/', bundle)
    out.with_suffix('.html').write_text(html, encoding='utf-8')
    print(f'{out.name}.glb  {len(data)/1024:.0f} KB, {len(glb.j["meshes"])} meshes')
    print(f'{out.name}.html {len(html)/1024:.0f} KB')
    print('free floor per room (m², model geometry; built-in wardrobes excluded) vs label:')
    labels = P.get('labels', {})
    for room, ar in areas.items():
        given = labels.get(room, {}).get('area', '')
        print(f'  {str(room):22s} {ar:7.2f}   {given}')


if __name__ == '__main__':
    main()
