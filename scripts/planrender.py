"""SVG output for floor plans built with plankit: one house style, rooms as
groups, every element labelled for Inkscape's Objects panel.

    import sys; sys.path.insert(0, '<skill>/scripts')
    from plankit import *
    from planrender import Style, Plan

Typical build script:

    st = Style.for_units(px_per_cm=1)          # plan in centimetres
    doors = {'cocina': span_door(w, 1107.7, 1180.2, 'start', 'left', **st.door_kw())}
    windows = {'cocina': window_unit(facade, 1082.7, 1189.5, 'right', **st.window_kw())}
    plan = Plan(st, doors, windows)
    plan.room('cocina', label=('COCINA', '11.77 m²', 700, 1180),
              doors=[('puerta', 'cocina')], windows=[('ventana', 'cocina')])
    plan.write('plano.svg', walls_d, viewbox=(-40, -40, 1239.3, 1782.7))

Conventions (see references/floor-plans.md §6): group id = room slug,
child ids = '<room>-<part>', inkscape:label = short part name; jambs live in
the door/window they frame, doors win jambs shared with a window, and a
jamb may never belong to two rooms. Outlines are drawn inside their shape.
"""
import csv
import io
import subprocess
from dataclasses import dataclass, fields, replace

from plankit import inset_rect, rect_d, rect_key
from svgkit import f


@dataclass(frozen=True)
class Style:
    """House style for plans: grey walls with a dark outline, white door
    leaves and jambs, thin swing arcs, glazing frame + glass/sill lines,
    grey entrance arrows, bold room name over a grey regular area.
    Defaults are in reference pixels of a plan whose exterior walls are 34 px
    (~1.3 px per cm); use for_units() for other scales."""
    wall_fill: str = '#999999'
    line: str = '#333333'
    arrow_fill: str = '#999999'
    hatch: str = '#c8c8c8'
    name_fill: str = '#000'
    area_fill: str = '#4d4d4d'
    font: str = "Futura, 'Avenir Next', sans-serif"
    # geometry (scaled)
    sw_wall: float = 2.2
    sw_jamb: float = 1.6
    sw_leaf: float = 1.6
    sw_frame: float = 1.4
    sw_arc: float = 1.6
    sw_glass: float = 1.4
    sw_site: float = 2.5
    sw_hatch: float = 1.6
    jamb: float = 8
    leaf: float = 5
    frame: float = 10
    name_size: float = 24.8
    area_size: float = 26
    label_gap: float = 29

    SCALED = ('sw_wall', 'sw_jamb', 'sw_leaf', 'sw_frame', 'sw_arc', 'sw_glass', 'sw_site',
              'sw_hatch', 'jamb', 'leaf', 'frame', 'name_size', 'area_size', 'label_gap')

    def scaled(self, k):
        """Same style with every length multiplied by k (colours unchanged)."""
        return replace(self, **{n.name: round(getattr(self, n.name)*k, 3)
                                for n in fields(self) if n.name in self.SCALED})

    @classmethod
    def for_units(cls, px_per_cm):
        """Style for a plan drawn at `px_per_cm` units per centimetre
        (1 for a plan in cm, 10 in mm, or the measured reference scale)."""
        return cls().scaled(px_per_cm/1.3)

    def door_kw(self):
        """Keyword args for door_unit / span_door / double_door_unit."""
        return dict(jamb=self.jamb, leaf=self.leaf, arc_w=self.sw_arc, jamb_w=self.sw_jamb)

    def window_kw(self):
        """Keyword args for window_unit."""
        return dict(jamb=self.jamb, frame=self.frame, sill_w=self.sw_glass, jamb_w=self.sw_jamb)


def lab(i, name, extra=''):
    return f'id="{i}" inkscape:label="{name}"{extra}'


def numbered(base, items):
    return [(base if len(items) == 1 else f'{base}-{k + 1}', it) for k, it in enumerate(items)]


class Plan:
    """Collects room groups and writes the two-layer SVG (walls, rooms)."""

    def __init__(self, style, doors=None, windows=None):
        self.st, self.doors, self.windows = style, doors or {}, windows or {}
        self.rooms, self._used = [], set()

    # ----- parts -----
    def jambs(self, g, js):
        if not js:
            return ''
        st = self.st
        d = ''.join(rect_d(inset_rect(j, st.sw_jamb/2)) for j in js)
        return f'<path {lab(g + "-marcos", "marcos")} fill="#fff" stroke="{st.line}" stroke-width="{st.sw_jamb}" d="{d}"/>'

    def door(self, g, name, u, own):
        st = self.st
        leaves = ''.join(f'<path {lab(g + "-" + n, n)} d="{rect_d(inset_rect(r, st.sw_leaf/2))}"/>'
                         for n, r in numbered('hoja', u['leaves']))
        arcs = ''.join(f'<path {lab(g + "-" + n, n)} fill="none" stroke-width="{st.sw_arc}" d="{d}"/>'
                       for n, d in numbered('arco', u['arcs']))
        attrs = f' fill="#fff" stroke="{st.line}" stroke-width="{st.sw_leaf}"'
        return f'<g {lab(g, name, attrs)}>' + leaves + arcs + self.jambs(g, own) + '</g>'

    def window(self, g, name, u, own):
        st = self.st
        frames = ''.join(f'<path {lab(g + "-" + n, n)} d="{rect_d(inset_rect(r, st.sw_frame/2))}"/>'
                         for n, r in numbered('cristal', u['frames']))
        attrs = f' fill="#fff" stroke="{st.line}" stroke-width="{st.sw_frame}"'
        return (f'<g {lab(g, name, attrs)}>' + frames
                + f'<path {lab(g + "-lineas", "lineas")} fill="none" stroke-width="{st.sw_glass}" d="{u["lines"]}"/>'
                + self.jambs(g, own) + '</g>')

    def label(self, room, name, area, cx, y, rotate=False):
        """Name (bold) + area (regular) centred on cx; name baseline at y.
        rotate=True turns the block 90° (reads bottom-to-top) around its own
        centre: use it in corridors narrower than the name."""
        st = self.st
        g = f'{room}-etiqueta'
        attrs = f' font-family="{st.font}" text-anchor="middle"'
        if rotate:
            cy = y + st.label_gap/2 - st.name_size*0.35
            attrs += f' transform="rotate(-90 {f(cx)} {f(cy)})"'
        return (f'<g {lab(g, "etiqueta", attrs)}>'
                f'<text {lab(g + "-nombre", "nombre")} x="{f(cx)}" y="{f(y)}" font-size="{st.name_size}" '
                f'font-weight="700" fill="{st.name_fill}">{name}</text>'
                f'<text {lab(g + "-area", "area")} x="{f(cx)}" y="{f(y + st.label_gap)}" font-size="{st.area_size}" '
                f'font-weight="400" fill="{st.area_fill}">{area}</text></g>')

    def line(self, room, part, d, stroke=None, sw=None, extra=''):
        """Open stroked path (hatching, wardrobe fronts, site lines…)."""
        stroke = stroke or self.st.line
        sw = self.st.sw_jamb if sw is None else sw
        return (f'<path {lab(f"{room}-{part}", part)} fill="none" stroke="{stroke}" '
                f'stroke-width="{sw}"{extra} d="{d}"/>')

    def marker(self, room, d, part='flecha'):
        return f'<path {lab(f"{room}-{part}", part)} fill="{self.st.arrow_fill}" d="{d}"/>'

    # ----- rooms -----
    def room(self, room, label=None, doors=(), windows=(), below=(), above=(), marker=None):
        """Add one room group. `doors`/`windows` = [(part name, key in the
        doors/windows dict)]; `label` = (name, area, cx, y[, rotate]);
        `below` = parts under the openings (hatching, frames), `above` =
        parts over them (wardrobe fronts, site lines); `marker` = arrow
        path data. Draw order: below → windows → doors → above → marker →
        label. Jambs shared by two units of the room are drawn once (by the
        door); a jamb in two rooms raises."""
        taken, keys = [], set()

        def take(units):
            out = []
            for u in units:
                own = [j for j in u['jambs'] if rect_key(j) not in keys]
                keys.update(rect_key(j) for j in own)
                taken.extend(own)
                out.append(own)
            return out
        d_own = take([self.doors[k] for _, k in doors])
        w_own = take([self.windows[k] for _, k in windows])
        clash = keys & self._used
        assert not clash, f'jamb shared between rooms ({room}): {sorted(clash)}'
        self._used |= keys
        parts = list(below)
        parts += [self.window(f'{room}-{n}', n, self.windows[k], o) for (n, k), o in zip(windows, w_own)]
        parts += [self.door(f'{room}-{n}', n, self.doors[k], o) for (n, k), o in zip(doors, d_own)]
        parts += list(above)
        if marker:
            parts.append(self.marker(room, marker))
        if label:
            parts.append(self.label(room, *label))
        self.rooms.append(f'<g {lab(room, room)}>' + ''.join(parts) + '</g>')

    # ----- document -----
    def svg(self, walls_d, viewbox, size=None, title='Plano de vivienda',
            desc='Floor plan rebuilt from walls, doors and windows; furniture and fixtures omitted.'):
        """`viewbox` = (x, y, w, h); `size` = (width, height) attribute values
        (default: the viewBox size, unitless)."""
        st = self.st
        x, y, w, h = viewbox
        sw_, sh_ = size or (f(w), f(h))

        def layer(i, body):
            return f'<g id="{i}" inkscape:groupmode="layer" inkscape:label="{i}">{body}</g>'
        walls = (f'<path id="muros" inkscape:label="muros" fill="{st.wall_fill}" stroke="{st.line}" '
                 f'stroke-width="{st.sw_wall}" stroke-linejoin="miter" d="{walls_d}"/>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                f'width="{sw_}" height="{sh_}" viewBox="{f(x)} {f(y)} {f(w)} {f(h)}"><title>{title}</title>'
                f'<desc>{desc}</desc>' + layer('walls', walls) + layer('rooms', ''.join(self.rooms)) + '</svg>')

    def write(self, path, walls_d, viewbox, **kw):
        from pathlib import Path
        Path(path).write_text(self.svg(walls_d, viewbox, **kw), encoding='utf-8')


# ----- Inkscape helpers -----

def page_area(viewbox, rect, scale=1.0):
    """--export-area value for a rect in viewBox units. Inkscape's export
    area is measured from the PAGE corner in px, so a viewBox that does not
    start at (0, 0) (e.g. a margin of -40) must be offset, and a document
    whose width differs from the viewBox width must be scaled (`scale` =
    width in px / viewBox width)."""
    vx, vy = viewbox[0], viewbox[1]
    x0, y0, x1, y1 = rect
    return ':'.join(f((v - o)*scale) for v, o in ((x0, vx), (y0, vy), (x1, vx), (y1, vy)))


def inkscape(*args, **kw):
    """Run Inkscape and judge success by the output, not the exit code: in
    sandboxed shells (macOS) Inkscape may print a sandbox_extension error
    and exit 1 after writing the file correctly."""
    r = subprocess.run(['inkscape', *map(str, args)], capture_output=True, text=True, **kw)
    return r


def query_boxes(svg_path, viewbox, scale=1.0):
    """{id: (x0, y0, x1, y1)} in viewBox units, from `inkscape --query-all`
    (which reports px from the page corner)."""
    out = inkscape('--query-all', svg_path).stdout
    vx, vy = viewbox[0], viewbox[1]
    boxes = {}
    for row in csv.reader(io.StringIO(out)):
        if len(row) == 5:
            x, y, w, h = (float(v)/scale for v in row[1:])
            boxes[row[0]] = (x + vx, y + vy, x + w + vx, y + h + vy)
    return boxes


def label_overflow(svg_path, viewbox, floors, tol=0.0, scale=1.0):
    """Rooms whose rendered label (ink of '<room>-etiqueta') does not fit
    inside the room's free floor. `floors` = {room: [rects]}. Returns
    {room: label box} for every misfit; fix by moving the label, rotating it
    in narrow rooms, or abbreviating as the reference does ('DISTRIB.')."""
    boxes = query_boxes(svg_path, viewbox, scale)

    def inside(px, py, rects):
        return any(r[0] - tol <= px <= r[2] + tol and r[1] - tol <= py <= r[3] + tol for r in rects)
    bad = {}
    for room, rects in floors.items():
        b = boxes.get(f'{room}-etiqueta')
        if b is None:
            continue
        x0, y0, x1, y1 = b
        samples = [(x0 + (x1 - x0)*i/4, y0 + (y1 - y0)*j/2) for i in range(5) for j in range(3)]
        if not all(inside(px, py, rects) for px, py in samples):
            bad[room] = b
    return bad
