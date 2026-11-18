# Constructing figures (buildings, structures, objects)

These rules come from real user feedback on vectorised illustrations. Each one fixed
something the user saw and disliked. They apply to any man-made subject:
buildings, bridges, machines, furniture, vehicles, signage.

## Table of contents
1. Mindset: reconstruct, don't trace
2. Straight, simple, intentional outlines
3. Symmetry
4. Repeated elements must be identical
5. Perspective (receding facades)
6. Openings, separation lines and details
7. Simplify where the eye won't miss it
8. Structures made of members (frames, trusses, wheels, cables)
9. SVG mechanics: one path per object, winding, seams
10. Deliberate deviations — and saying so

---

## 1. Mindset: reconstruct, don't trace
Ask "what is this object really?" — a rectangular tower with a hipped roof,
a dome that is half an ellipse on a drum, a row of 12 identical arched
windows. Then draw *that*, positioned and sized from measurements. The
reference tells you where and how big; your knowledge of the object tells you
the form. A traced outline encodes JPEG noise, antialiasing and the artist's
small slips as permanent geometry.

Tracing (potrace via `scripts/contour.py`) is still useful for:
- a first pass to read coordinates;
- genuinely organic shapes (trees, clouds, people, hand-lettering) where no
  clean primitive exists — even then use a high `opttolerance` and remove
  speckles.

## 2. Straight, simple, intentional outlines
- Walls are vertical, eaves/parapets are straight lines, roofs are straight
  slopes. If a measured edge wobbles ±1px, it is a straight line.
- Prefer a skyline *profile polygon* per building: walk the top edge as a
  polyline, close along the ground.
- Curves only where the object is curved (domes, arches, wheels, tanks), and
  then use true arcs/ellipses, not freeform Béziers.
- Where two lines meet, make a real corner. Users notice immediately when a
  curve smears a junction that is sharp in the original.
- Kill dents: little notches and bumps along an edge (from the raster) should
  be removed unless they are real features (crenellations, statues,
  pinnacles) — and then draw them as deliberate, regular shapes.
- Unify fussy stepped tops into one straight line when the steps aren't
  meaningful; keep the corner where the direction really changes.

## 3. Symmetry
Most man-made objects are symmetric about a vertical axis (facades, domes,
towers, gates, wheels, many machines and vehicles seen front-on).
- Find the axis from several paired features (paired corners, an apex, a top
  ornament, paired openings) and average; it is often a .5 coordinate.
- Draw **one half** and mirror it (`svgkit.mirror`), or define elements by
  offsets from the axis (`A ± d`). Never position left and right copies
  independently.
- If the source itself is slightly asymmetric (an extra opening on one side,
  paired parts a few px off), choose the symmetric version and tell the user.
- Symmetry also applies across a composite: paired towers, piers, legs or
  spans are mirror images about the composite's axis (fit one side to the
  reference, mirror the other).
- Verify with `scripts/symmetry.py` — render at a scale where the axis lands
  on a pixel boundary (e.g. 4 px/unit) and compare with the flipped image.

## 4. Repeated elements must be identical
Windows in a row, columns, slits, items around a wheel, crenellations,
teeth, rivets: same width, same height, same shape, same spacing.
- Measure all instances, then take the median size and a regular spacing
  (or a fitted progression if there is perspective — see §5).
- Build them in a loop from one definition.
- Equal across rows too, unless the design really differs per storey.
- Sizes measured from light pixels underestimate openings by ~0.3–0.5px
  (antialiasing); add that back.

## 5. Perspective (receding facades)
A facade seen at an angle: its roof line slopes and windows grow toward the
viewer. Model it as real perspective, not as ad-hoc slanting:
- The roof (eaves) line and the ground line converge at a **vanishing
  point** (VP). With a horizontal ground line, the VP sits on the ground line
  where the extended roof line meets it.
- Local facade height at x: `H(x) = ground − roof(x)`; it is linear in x.
- Every horizontal feature on the facade (window heads, sills, string
  courses) is a straight line at a constant *fraction* of `H(x)` →
  `svgkit.facade_line(roof, ground, fraction)`. All of them pass through
  the VP. Measure the fractions on a couple of windows at both ends and
  average.
- Windows keep the same proportions; their size scales with `H(x)`:
  `width = k·(x − vx)`.
- Spacing grows geometrically: `x_i − vx = d₀·qⁱ` with `q` from the first
  and last measured centres. This gives a smooth, believable progression.
- The sill (bottom edge) and the head line follow the vanishing lines too —
  the bottom of each window is a *sloped* straight line, and the arch springs
  from the sloped head line: `svgkit.perspective_arch`.
- Small secondary facades (an annex, a rooftop block) use the same VP so
  everything agrees.
- If the user proposes a different perspective model (e.g. eye-level
  horizon), draw both options with guide lines before changing anything —
  some models are incompatible with the drawn roof/ground lines.

## 6. Openings, separation lines and details
- Windows, doors, oculi, slits and columns-shown-as-light are **holes** in
  the dark silhouette (transparent, so they show the paper), not white shapes
  on top.
- Thin light "cut lines" (cornices, roof edges, joints between buildings,
  pediment frames) are straight thin holes (≈1–1.3 units), or real gaps
  between two neighbouring objects. Keep them straight, parallel to the
  architecture, ending in clean corners.
- Classical columns as light shapes: shaft + slightly wider capital and base.
- A pediment frame = outer triangle hole + inner triangle (tympanum) solid.
- Domes: half-ellipse on a drum; the separating line under a dome is usually
  an arched band (higher in the middle).
- Arched windows: rectangle + semicircular head (`svgkit.arch`).
- Fill **micro-holes** (1–2 px specks) and drop tiny details that read as
  noise at print size. Keep small details that carry meaning (a small
  window, a clock face, a logo) but redraw them with the same rules as the
  big ones (same shapes, same perspective).

## 7. Simplify where the eye won't miss it
- Background clutter (low roofs, distant blocks) → stepped rectangles with an
  occasional rounded tank/dome or a pointed spire.
- Merge things that belong together into one silhouette: an appendage with
  the body it stands on (a chimney on a roof, a block on a wing).
- Remove decorative noise inside structures (a lattice inside a frame) when it
  adds no recognisability.

## 8. Structures made of members
- Frames, trusses, legs, arms: each member is a straight quadrilateral defined
  by fitted edge lines (fit `x = a·y + b` to each edge). Where members meet,
  intersect the lines for exact apexes.
- Small mechanical details: decompose into a few boxes, thin quads following
  fitted lines, and small circles for rounded tips. Match the reference at 10×
  zoom — this is where users notice.
- Radial structures (wheels, rosettes, dials): concentric stroked circles, a
  hub, N spokes as thin straight strokes, repeated items as individual
  primitives at equal angles, supports as equal strokes.
- Cables and ropes: smooth cubic curves fitted to the reference; vertical
  hangers are straight strokes with round caps. Mirror spans about the
  structure's axis.

## 9. SVG mechanics: one path per object, winding, seams
- One `<path>` per editable object, fill-rule **nonzero**: solids clockwise
  on screen, holes counter-clockwise (`svgkit.poly(..., hole=True)` handles
  orientation). Overlapping solids inside a path merge with no seam.
- A hole only works where exactly one solid covers it. If two solids
  overlap at a hole, the hole disappears (winding 2 − 1 = 1). Either make the
  object a single outline there, or keep the solids from overlapping under
  holes.
- Neighbouring *separate* paths that merely touch produce antialias
  hairlines. Overlap them by 1–2 units where no gap is intended; leave an
  explicit ~0.9-unit gap where a light separation line is intended.
- Avoid tiny gaps between stacked parts of one object (e.g. cornice ending at
  339.2, body starting at 339.4) — they render as lines. Overlap instead.
- Objects drawn later cover earlier ones: order components so that a
  covering object never hides another object's intentional hole.

## 10. Deliberate deviations — and saying so
Refinements change the drawing slightly (symmetrised parts, equalised counts of
repeated elements, merged or removed details). That's the point — but list them
in the report so the user can veto any.
