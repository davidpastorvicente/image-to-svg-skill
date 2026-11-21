# Measuring the reference

Coordinates in the SVG should equal reference pixel coordinates
(`viewBox="0 0 W H"` of the source), and the physical size goes in
`width`/`height` (mm). Then every measurement drops straight into the build.

## Vector references (SVG / PDF)
If the "image" is already vector — an Inkscape or CAD SVG, a PDF exported
from a drawing program — measure the vector, not a render of it: the
coordinates are exact and often in physical units, and the group names
tell you what each shape is.
```bash
V=~/.agents/skills/image-to-svg/scripts/vector_measure.py
inkscape plan.pdf --export-plain-svg --export-filename=plan.svg   # PDFs first
python $V tree plan.svg --depth 2                  # named groups with bboxes
python $V dump plan.svg --under puerta --points    # shapes (transforms applied), cm
python $V rooms plan.svg --floor suelo             # orthogonal floors → rects + m²
```
Units: `--units cm|mm|px` (from the document's `width`/`height`). Keep the
numbers as measurements for the constructors — still rebuild by meaning.
Several files of one project may disagree (an older PDF next to the
current SVG): ask which one is current and say which you used.

## Tools (`scripts/measure.py`)
```bash
M=~/.agents/skills/image-to-svg/scripts/measure.py
python $M grid ref.png --box 520 410 750 520 --scale 6 -o grid.png    # zoom with labelled 5/10 px grid
python $M profile ref.png --box 255 300 945 516 [--open 4]           # top-edge profile (run-length)
python $M holes ref.png --box 255 300 945 516                         # light openings inside dark shapes
python $M color ref.png --box 78 320 135 326                          # median colour of a flat area
python $M fit-circle ref.png --box 500 230 840 517 --guess 678 393 155 --select "r-b>25"
python $M fit-line ref.png --points "440,781 500,768 530,762"
```

## Techniques
- **Look first, at zoom.** Grid crops (6–10×, NEAREST) with labelled lines are
  the fastest way to read coordinates and understand a shape. Read them before
  writing geometry, and again after each change, side by side with the render.
- **Top profiles.** For silhouettes, the first dark pixel per column,
  run-length encoded, gives roof heights, steps, spires and domes as numbers.
  Use `--open N` (morphological opening) to ignore thin lines (cables, spokes,
  thin frames) that would otherwise contaminate the profile.
- **Openings.** Connected components of light pixels fully enclosed in dark
  give windows/slits/columns with bounding boxes. Group them into rows and
  columns, then regularise (median size, regular spacing / perspective fit).
- **Row/column scans.** Printing dark runs along a row or column (e.g. at
  several y through a tower) gives widths per storey and reveals tiers.
- **Mirrored scans.** For a suspected axis A, print the profile at `A−d` and
  `A+d` side by side — differences show where the source is asymmetric and
  help pick the axis.
- **Fits.** Least-squares lines for edges of legs, roof lines, cables;
  robust circle fits (soft-L1) for circles and rings using only
  contour points near the expected radius.
- **Light-pixel runs along a column** reveal thin light lines (cornices,
  arched bands under domes) and their curvature: sample several x.
- **Thresholds.** Dark silhouette ≈ gray < 120–135; light openings ≈ gray >
  150. Sub-pixel: an edge sits at the 50% transition; light-region bounding
  boxes are ~0.3–0.5 px too small.
- **Colours.** Median of an eroded mask of a flat region, never a single
  pixel. Near-black ink is rarely #000 (often a warm or cool dark grey); keep it.
- **Backdrop circles/discs.** Fit to the coloured region's outer contour,
  excluding points where buildings overlap.
- **Text.** Column projections of a text line give per-glyph ink extents —
  used to position glyphs (see typography reference).

## Recording
Keep measurements in the build script as named constants or small tables
(e.g. measured window boxes) and derive the clean geometry from them in code.
That keeps the provenance visible and makes refits easy when the user asks
for changes.
