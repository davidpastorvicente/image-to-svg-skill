# Floor plans (architectural plans, orthogonal 2D)

A floor plan is not an illustration: no perspective, no mirror symmetry by
default. What users notice instead is **walls that aren't straight or
uniformly thick, corners with notches, doors of slightly different sizes,
hatching that wobbles or leaks out of its area, and room labels that drift**.
Build it from `scripts/plankit.py` (walls, openings, doors, windows, hatches)
on top of `scripts/svgkit.py`.

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
    leaf's inner tip corner and its butt end lies along the leaf's side.
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
  asked; mention them.

## 1. Intake (extra questions for plans)
- Keep or drop furniture and fixtures (beds, sofas, kitchen units, WC,
  shower trays)? Default when unsure: ask. Decide *before* measuring: their
  lines touch doors and walls and must not be mistaken for them.
- Scale: default = reference pixels (viewBox = image size). Only use real
  units if the user gives a dimension or a scale bar; then convert with one
  constant `PX_PER_M` measured on a known length and say how it was derived.
  Never infer metres from the area labels.
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
  dict with `hole`, `jambs`, `leaves`, `arcs`; `double_door_unit(wall, s0,
  s1, swing, r_start=None)` for equal or unequal double leaves. Pass
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
  unless the reference clearly has two types.
- **Hatching** `hatch(ring_or_rings, spacing, angle, phase)` computes lines
  already clipped to the area (no clipPath; holes via extra rings). Lines
  sit on a global grid, so adjacent areas with the same settings continue
  seamlessly. Stop hatching at walls: the area ring is the free floor, not
  the wall's outline.
- **Dashed elements** `dashed_rect` + `stroke-dasharray`; **entrance
  arrows** `arrow(tip, size, direction)`.
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

## 6. Structure (Objects panel)
```
plan (layer)
├─ hatching   terraza, porche, jardin …   (stroked)
├─ outlines   parcela, terraza, tendedero (stroked, dashes)
├─ walls      one filled + outlined path
├─ windows    one group per window: frame, lines
├─ doors      one group per door (named by room): leaf, swing
├─ jambs      one path with all jamb boxes
├─ markers    entrance arrows
└─ labels     cocina, salon-comedor … (text)
```
Draw order: hatching → outlines → walls → windows → doors → jambs → labels,
so walls cover hatch ends and labels stay on top. Move a label off a door
arc when they collide (name and area share one centre x).

## 7. Verify
- `compare.py` per zone (walls, doors, hatches) and a full overlay — expect
  differences only where furniture was dropped.
- Check at 300 dpi: corners without notches, door arcs ending exactly at the
  jamb, hatch lines ending at the area boundary, no hairlines in walls.
- Zoom on every door and wall junction of the render and look for: doubled
  parallel lines, lines heavier than the wall outline, wall ends left open,
  leaves/arcs not touching jambs, slivers between a jamb and a wall, edges
  that step where a jamb, frame or boundary line meets a wall (mismatched
  stroke widths or coordinates). Any of these means something was traced
  or styled per element instead of constructed from shared constants.
- `validate.py --text "COCINA" --text "8.02 m²" …` for every label.
- Report: wall thickness classes used, door/window classes, dropped
  elements, any coordinates that were unified (e.g. two walls snapped onto
  one line).
