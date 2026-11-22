# Floor plans (architectural plans, orthogonal 2D)

A floor plan is not an illustration: no perspective, no mirror symmetry by
default. What users notice instead is **walls that aren't straight or
uniformly thick, corners with notches, doors of slightly different sizes,
hatching that wobbles or leaks out of its area, and room labels that drift**.
Build it from `scripts/plankit.py` (walls, openings, doors, windows,
wardrobes, hatches) on top of `scripts/svgkit.py`, and write the SVG with
`scripts/planrender.py` (house style, room groups, labels). Measure vector
references with `scripts/vector_measure.py`.

## 0. The rule that matters most: rebuild meaning, never trace lines
The goal is not a pixel-identical copy but a plan an architect would draw:
**a wall is a wall, a door is a door, and all doors of a class are the same
object.** A first attempt that extracted the dark line work from the raster
(morphology → segments → stroked paths) was rejected as "a mess": doubled
lines next to wall edges, random stroke weights, wall fills not matching
their outlines, door leaves and arcs that did not reach the jambs, open
gaps at wall ends. Therefore:
- **Never** turn raster line pixels into SVG paths (no segment extraction,
  no traced arcs, no per-segment stroke widths). Measurement tools only
  give numbers; every drawn element comes from a constructor.
- **Walls are one filled path that carries its own outline** (`fill` grey +
  `stroke` dark on the same `<path>`). Never draw wall edges as separate
  lines: that is what produces duplicates and mismatched grey.
- **Wall thickness = a class constant** (e.g. exterior 34, interior 11).
  Small differences in the reference (10/11/13 px) are drawing noise —
  unify them; keep genuinely different elements (pillars, shafts, thick
  corner blocks) as explicit solid rects.
- **Openings are bridged, then cut**: define each wall over its full length,
  and let every door/window unit cut its own hole. Never reuse the gaps in
  the raster mask — their sizes differ randomly.
- **Every door/window is one unit** (`door_unit`, `double_door_unit`,
  `window_unit`) on a `Wall`: jambs close both wall ends, the leaf starts at
  one jamb and the arc ends exactly on the other (opening = r + 2·jamb). Door
  radius comes from a class (`R_INT`, `R_EXT`, `R_ENT`), not from per-door
  fits.
- Place openings flush with neighbouring faces when they nearly touch (a
  1–3 px sliver of wall between a jamb and a perpendicular wall reads as a
  defect).
- **Outlines are drawn inside their shape** so the outer edge of every
  element is its true boundary. Stroke widths may differ per role (wall
  2.2, jamb 1.6, frame 1.4 …), but a centred stroke sticks out by w/2, so
  a jamb and its wall (or a boundary line and the wall corner it continues)
  end up with outer edges that step by the difference. Use
  `rects_union(..., inset=w/2)` for walls, `inset_rect(r, w/2)` for jambs,
  leaves and window frames, `window_unit(..., sill_w=w)` for the sill,
  `door_unit(..., arc_w=w)` for the swing arc, and shift open lines that
  meet a wall by w/2 so their outer edge lies on the wall face. Only lines
  that never form or meet an edge (glass lines, hatching) stay centred.
- **The swing arc pivots on the leaf's inner corner**, not on the jamb,
  and its stroke ring spans radii [r − t, r − t + w] (t = leaf thickness,
  w = arc stroke = jamb stroke). Then both ends are exact:
  - wall end: the arc lies inside the opposite jamb's inner outline band —
    its corner IS the jamb's inner corner (x and y) and the arc continues
    the jamb's edge, no step and no diagonal touch;
  - leaf end: the leaf is r − t + w long, so the arc's outer corner IS the
    leaf's inner tip corner and its butt end lies along the leaf's side;
  - double doors (`double_door_unit`): the far end of each arc is the other
    leaf's arc, not a jamb, so both rings are centred on the meeting point
    and the two arcs end at the SAME point with the same end band (no
    crossing, no doubled tip).
  An arc centred on the hinge jamb can never hit the leaf corner (that
  corner is √(r² + t²) away) and its butt end is cut at a slant. Check both
  ends with a ×16 render (`inkscape --export-area=… --export-dpi=1536`),
  including doors that share a jamb with a window.
- **Touching elements share one border, they don't stack two.** Where a
  wall end meets a jamb, the wall's end outline + the jamb's outline side
  by side make a seam twice as heavy as any other edge. Shorten the wall
  hole by the jamb's stroke width (`jamb_w=` on `door_unit`,
  `double_door_unit`, `window_unit`) so the wall's outline ends exactly
  where the jamb's white begins and covers the jamb's outline. Same for
  every element that abuts another: window frame, glass and sill lines
  reach `jamb_w` into the jambs; the leaf's hinge side shares the jamb's
  inner outline. Draw the element whose outline should win later (jambs
  after doors/windows).
- **Lines that continue a wall sit exactly on its face.** A plot or terrace
  boundary that starts at a building corner takes the wall's outer face
  (`ext_top.f0 + w/2` for a line of width w, so the line's outer edge is
  the face) and reads as one straight edge with the wall. Derive these
  coordinates from the `Wall` objects, never from separate measurements;
  hatch ends and divider lines use the same constants as the frame they
  stop at.
- Drop finish lines (tiling, skirting) and furniture-like built-ins unless
  asked; mention them. Built-in **wardrobes are not furniture**: keep them
  as recesses (see §4, `closet_unit`).

## 1. Intake (extra questions for plans)
- Keep or drop furniture and fixtures (beds, sofas, kitchen units, WC,
  shower trays)? Default when unsure: ask. Decide *before* measuring: their
  lines touch doors and walls and must not be mistaken for them.
- Scale: default = reference pixels (viewBox = image size). Only use real
  units if the user gives a dimension or a scale bar, **or the reference is
  a vector file in physical units** (an Inkscape/CAD SVG with
  `width="1159.3cm"`, a PDF from a CAD tool); then convert with one
  constant `PX_PER_M` (or work directly in cm) and say how it was derived.
  Never infer metres from the area labels.
- Labels: if the reference has none, ask what to write (room names from
  the user's own files or groups — e.g. `Habitación Miriam.svg` — vs
  generic DORMITORIO 1/2…, with or without areas). Areas may only be
  computed when the plan is at real scale (see §5).
- House style: when the user points to an earlier plan ("same format as
  X"), they mean its *visual* conventions — wall colours, door and window
  symbols, label styles, arrows. Reuse its `planrender.Style`, scaled to
  the new units (`Style.for_units`), instead of re-deriving widths.
- Output: usually one editable SVG; no print pipeline unless asked.

## 2. Analyse: inventory before geometry
List and show back to the user:
- **wall classes**: exterior, interior structural, partitions — one
  thickness per class (`measure.py walls` prints a thickness histogram);
- **openings**: doors (swing side, hinge side, width class), sliding doors,
  windows (number of lines), open passages;
- **areas with hatching**: terraces, porches, gardens — line angle, spacing,
  colour per area;
- **thin outlines**: plot boundary, terrace edges, dashed elements
  (tendedero, overhead cupboards), entrance markers;
- **labels**: room name (bold caps) + area (`8.02 m²`) per room;
- what is dropped (furniture, fixtures).

## 3. Measure
- **Vector reference (SVG, or PDF → `inkscape x.pdf --export-plain-svg`):**
  don't rasterise it. `vector_measure.py tree ref.svg` lists the groups
  (often already named per room), `dump --label suelo --points` prints the
  exact coordinates with transforms applied, in cm, and `rooms` turns each
  room's floor polygon into rects + area, ready to paste into `FLOORS`.
  Typical drawings have per-room "floor" and "wall ring" shapes plus
  door groups whose floor patch marks the opening: the opening is that
  patch, the leaf length is the door class. Snap 0.1-unit noise
  (825.7/825.8) with `clusters`, but keep real steps (a 3.6 cm offset
  between two rooms' outer walls is a measurement, not noise). Wall
  regions covered by a white box in the source are usually built-ins
  (wardrobes) drawn over a solid fill: check the group names before
  treating them as wall.
- `measure.py walls image.png -o overlay.png` → raw wall rectangles,
  thickness classes and frequent edges. Tune `--select` (wall fill colour),
  `--min-thickness` (just above line/text thickness) and check the overlay.
  Raw rects are a measurement, not the final geometry.
- Snap all wall edges: collect x's and y's separately and run
  `plankit.clusters(values, tol=2)` so aligned walls share one coordinate.
- Openings: `measure.py scan` along a wall's centre line gives the gaps;
  door widths go into width classes (e.g. 70/80/90 equivalents) — doors of
  one class are identical.
- Door hinge and swing from a `grid` crop at high zoom: the hinge is the jamb
  where the leaf line starts; the arc ends at the other jamb.
- Hatch spacing: scan across the hatching and take the median period;
  angle with `fit-line` on one line.

## 4. Construct
- **Room-first walls** (preferred when the reference is organised by rooms,
  as most vector sources and listing plans are): list each room's free
  floor as rects (`FLOORS`), the building outline as `ENVELOPE` rects, and
  get the walls as `walls_from_rooms(envelope, floors, holes, inset=w/2)`
  with `holes` = wardrobe recesses + every door/window `hole`. Wall
  thicknesses, pillars, shafts and stepped blocks then come out exactly as
  drawn with no per-wall bookkeeping, and the same rects give the areas
  (`rects_area`). Create `Wall` objects only for the walls that carry
  openings.
- **Walls = one filled path**, built with `rects_union(solids, holes)`:
  - define walls on axes: `wall_h(y, x0, x1, t)` / `wall_v(x, y0, y1, t)`
    between wall axes (they extend t/2 so corners and T-joints close);
    walls that are flush on one face but differ in thickness can be given as
    plain `(x0, y0, x1, y1)` rects instead;
  - openings (doors, windows, passages) are rects in `holes` spanning the
    full wall thickness (slightly beyond it is fine);
  - the union removes overlaps and collinear points, so there are no seams,
    no hairlines between wall pieces and openings always cut.
  - Non-orthogonal walls (rare): separate `svgkit.poly` solids in the same
    path, not overlapping any opening.
- **Walls as `Wall` objects** (preferred): `w = Wall('v', x0, x1)` (faces)
  and `w.rect(y0, y1)` for its extent; openings are placed on the same
  object, so solids, holes and jambs share coordinates exactly.
- **Doors** `door_unit(wall, centre, r, hinge='start'|'end', swing)` →
  dict with `hole`, `jambs`, `leaves`, `arcs`; `span_door(wall, s0, s1,
  hinge, swing)` when the reference gives the opening (jamb to jamb)
  rather than the clear width; `double_door_unit(wall, s0,
  s1, swing, r_start=None)` for equal or unequal double leaves (for "hoja y
  media", make the big leaf equal to the interior door class);
  `sliding_door_unit(wall, s0, s1, leaf_len, at='end')` for sliding/pocket
  doors (leaf on the wall axis, no arc). Pass
  `arc_w` and `jamb_w` (= jamb stroke width) to every unit, put all holes
  into `rects_union(solids, holes, inset=wall_w/2)`, draw jambs, leaves and
  frames as white `inset_rect`s with their outline stroke and arcs with
  `arc_w`. Doors and windows that
  share an opening (door + fixed window) share one jamb: deduplicate jamb
  rects. The older `door(...)`/`window(...)` helpers only draw symbols
  without cutting walls; avoid them for real plans.
- **Windows** `window_unit(wall, s0, s1, inner)` → jambs (plus a centre
  mullion for long windows), a glazing frame flush with the inner face, a
  glass line and a sill line on the outer face. Same unit for every window
  unless the reference clearly has two types. Give `mullions=` explicitly
  when the reference disagrees with the >120 default (a short window with
  a post, a long fixed pane without one).
- **Door + fixed window in one opening** (balcony/terrace doors):
  `door_with_window(wall, s0, s1, split, door_at, swing, inner=…)` returns
  the door and the window sharing the jamb centred on `split`; pass
  `inner` when the door opens outwards.
- **Wardrobes** `closet_unit(rect, front, close=(), t)`: a built-in
  wardrobe is a recess that reads as a **box** — walls on three sides and
  a front line running wall to wall. When the room continues past one end
  of the recess (the front line would stop in mid-air, which users read as
  a stray line), close that end with a wall of the interior class
  (`close=('start',)`/`('end',)`). Add `hole` to the room's floor and to
  the wall holes, draw `front` as the room's `armario` line; in
  wall-by-wall plans add `end_walls` to the solids. Count wardrobes in the
  room area and say so. An irregular recess (L-shaped behind a shaft) is
  one `closet_unit` plus extra hole rects.
- **Comparing rects** built by different expressions (a jamb from the door
  and the same jamb from the window): use `rect_key` (rounded), never `==`
  or `in` on raw float tuples.
- **Hatching** `hatch(ring_or_rings, spacing, angle, phase)` computes lines
  already clipped to the area (no clipPath; holes via extra rings). Lines
  sit on a global grid, so adjacent areas with the same settings continue
  seamlessly. Stop hatching at walls: the area ring is the free floor, not
  the wall's outline.
- **Dashed elements** `dashed_rect` + `stroke-dasharray`; **entrance
  arrows** `arrow(tip, size, direction, spread)`.
- Strokes: one width per role (wall, jamb, leaf, frame, arc, hatch) as named
  constants; outlined solids are inset by half their width (see §0) so
  widths never move edges; `stroke-linecap="butt"`.

## 5. Labels
- One `<text>` per room with two lines or two tspans: name (bold caps) and
  area (regular). Centre with `text-anchor="middle"` on the label's
  reference centre; one font size per role.
- Write the superscript as the Unicode `²` (`m²`), not a raised tspan — it
  stays editable, searchable and survives font changes. If the reference
  font's `²` looks different, mention it rather than faking it.
- Keep the area numbers exactly as in the reference (they are facts); check
  diacritics (BAÑO, JARDÍN, SALÓN) — and keep missing accents as written
  unless the user asks to correct them.
- **Computed areas** (reference without areas, plan at real scale only):
  `rects_area(room floor rects)/1e4` m², printed by the build script so
  they can be reviewed. State what is included (built-in wardrobes yes,
  wall thickness no) and recompute after any geometry change — closing a
  wardrobe with an end wall changes the room's area.
- **Fit:** a label must sit inside its room's free floor, clear of door
  arcs. In corridors narrower than the name, rotate the label 90°
  (`Plan.label(..., rotate=True)`, reads bottom-to-top) rather than
  shrinking one label's font; abbreviate only when the reference does
  ('DISTRIB.'). Check with `planrender.label_overflow` after rendering.

## 6. Structure (Objects panel)
Use `scripts/planrender.py` instead of hand-writing the SVG: `Style` holds
the house style (grey `#999999` walls with a `#333333` outline, white
leaves and jambs, glazing frame + glass/sill lines, grey arrows, bold name
over a grey area, all stroke widths per role) with `door_kw()` /
`window_kw()` for the units, and `Plan.room(...)` emits one fully labelled
room group — doors, windows, jamb ownership, wardrobe fronts, marker,
label — following the rules below; `Plan.write` adds the two layers.
Override single values with `dataclasses.replace(style, jamb=6, …)`.

Organise by **room**, not by element type, so the user can find and move
everything belonging to one room:
```
walls (layer)   muros — one filled + outlined path, shared by all rooms
rooms (layer)
├─ cocina
│  ├─ cocina-puerta           label "puerta"
│  │  ├─ cocina-puerta-hoja / -arco / -marcos   (jambs live inside their door)
│  ├─ cocina-puerta-terraza   label "puerta-terraza"
│  ├─ cocina-flecha           label "flecha"
│  └─ cocina-etiqueta         label "etiqueta"
│     ├─ cocina-etiqueta-nombre / -area         (the two <text> elements)
├─ salon-comedor  (ventana → cristal, lineas, marcos; puerta-vestibulo …)
├─ terraza        (rayado, marco, etiqueta)
└─ …
```
- Group `id` = room slug. Child `id` = full prefix (`room-part`; ids must be
  unique). `inkscape:label` = the short part name only, no room prefix.
- A door belongs to the room it swings into (entrance → vestibule), a
  window to the room it lights. Arrows and cupboard lines go with their
  door/room. An arrow is named `flecha`; only when a room has more than
  one is each named after its door (`flecha-<destino>`: `puerta-terraza` →
  `flecha-terraza`).
- Jambs (`marcos`) live inside the door or window they frame; a jamb shared
  by a door and a window goes to the door (drawn later, so its outline stays
  on top) and must not appear in two rooms (assert it).
- **No element may be left unlabeled**: a bare `<g>`, `<path>` or `<text>`
  shows up in Inkscape as `g40` / `text43`. Give every one an id and an
  `inkscape:label` (double doors: `hoja-1`, `hoja-2`, `arco-1`, `arco-2`;
  label texts: `nombre`, `area`). Put `font-family`/`text-anchor` on the
  `etiqueta` group instead of a wrapper group. Check with a regex that
  lists elements lacking `inkscape:label`.
- Walls stay one shared layer: interior walls are merged into one outline.
- Draw order: walls first, then rooms; inside a room hatching → frame →
  windows → doors → markers → lines → label. Order rooms so that
  overlapping site lines stay on top (a boundary line after the hatch it
  touches). Compare against a pre-refactor render: regrouping must give
  the same image (a few antialiasing pixels where a path is split are fine).
- Move a label off a door arc when they collide (name and area share one
  centre x).

## 7. Verify
- `compare.py` per zone (walls, doors, hatches) and a full overlay — expect
  differences only where furniture was dropped. For a vector reference,
  render the same area of both files side by side instead (reference in
  its own units, e.g. `--export-area` of cm × 37.795 px).
- **Inkscape pitfalls when rendering crops:**
  - `--export-area` is measured in px from the **page corner**, not in
    viewBox coordinates: with a margin (`viewBox="-40 -40 …"`) or a
    `width` that differs from the viewBox size, convert with
    `planrender.page_area(viewbox, rect, scale)`. A wrong area renders a
    blank or shifted crop that looks like a drawing bug.
  - In sandboxed shells (macOS) Inkscape may print
    `sandbox_extension_issue_file_to_process failed` and exit 1 even
    though the PNG was written; check the output file, not the exit code
    (`planrender.inkscape` returns the result without raising).
  - Image viewers cache by path: write successive renders to new names
    before looking at them again.
- Check at 300 dpi: corners without notches, door arcs ending exactly at the
  jamb, hatch lines ending at the area boundary, no hairlines in walls.
- Zoom on every door and wall junction of the render and look for: doubled
  parallel lines, lines heavier than the wall outline, wall ends left open,
  leaves/arcs not touching jambs, slivers between a jamb and a wall, edges
  that step where a jamb, frame or boundary line meets a wall (mismatched
  stroke widths or coordinates). Any of these means something was traced
  or styled per element instead of constructed from shared constants.
- `validate.py --text "COCINA" --text "8.02 m²" …` for every label, and
  `planrender.label_overflow(svg, viewbox, floors)` → must be empty.
- Wardrobe fronts: every `armario` line must end on a wall at both ends.
- Report: wall thickness classes used, door/window classes, dropped
  elements, any coordinates that were unified (e.g. two walls snapped onto
  one line).

## 8. 3D model (on request)
A plan built this way already holds everything a 3D model needs except
heights. See `references/plan-3d.md`: dump the geometry to `plan3d.json`
from the build script, write a `3d/config.toml`, run `scripts/plan3d.py`.
