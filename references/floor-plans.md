# Floor plans (architectural plans, orthogonal 2D)

A floor plan is not an illustration: no perspective, no mirror symmetry by
default. What users notice instead is **walls that aren't straight or
uniformly thick, corners with notches, doors of slightly different sizes,
hatching that wobbles or leaks out of its area, and room labels that drift**.
Build it from `scripts/plankit.py` (walls, openings, doors, windows, hatches)
on top of `scripts/svgkit.py`.

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
- **Doors** `door(hinge, width, closed, opened)` → (leaf, arc): leaf with the
  heavier stroke, arc with the hairline. `double_door`, `sliding_door` for
  the other types. Build all doors of a class from one width constant.
- **Windows** `window(x0, y0, x1, y1, lines=2|3)` inside the wall opening,
  same line count for every window of the plan unless the reference clearly
  uses two types.
- **Hatching** `hatch(ring_or_rings, spacing, angle, phase)` computes lines
  already clipped to the area (no clipPath; holes via extra rings). Lines
  sit on a global grid, so adjacent areas with the same settings continue
  seamlessly. Stop hatching at walls: the area ring is the free floor, not
  the wall's outline.
- **Dashed elements** `dashed_rect` + `stroke-dasharray`; **entrance
  arrows** `arrow(tip, size, direction)`.
- Strokes: one stroke-width per role (leaf, arc/window, outline, hatch),
  set on the group, `fill="none"`, `stroke-linecap="butt"`.

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
├─ walls      one filled path
├─ windows    one stroked path per window or one combined
├─ doors      01, 02 … each a group: leaf, swing
├─ markers    entrance arrows
└─ labels     cocina, salon-comedor … (text)
```
Draw order: hatching → outlines → walls → windows → doors → labels, so walls
cover hatch ends and labels stay on top.

## 7. Verify
- `compare.py` per zone (walls, doors, hatches) and a full overlay — expect
  differences only where furniture was dropped.
- Check at 300 dpi: corners without notches, door arcs ending exactly at the
  jamb, hatch lines ending at the area boundary, no hairlines in walls.
- `validate.py --text "COCINA" --text "8.02 m²" …` for every label.
- Report: wall thickness classes used, door/window classes, dropped
  elements, any coordinates that were unified (e.g. two walls snapped onto
  one line).
