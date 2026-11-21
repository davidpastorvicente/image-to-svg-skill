---
name: image-to-svg
description: Faithfully recreate a raster image (poster, illustration, skyline, logo-like artwork, infographic, silhouette art) as clean, editable, print-ready SVG built from constructed geometry rather than auto-tracing. Use this skill whenever the user wants to convert, redraw, vectorize, rebuild or "pass to SVG" a picture/PNG/JPG, wants a vector version of artwork for printing or Inkscape/Illustrator editing, or complains that a traced SVG looks wobbly, asymmetric or messy — even if they don't say "vectorize". Especially relevant for buildings, landmarks, skylines, machines and other man-made structures where straight lines, symmetry and perspective matter — and for architectural floor plans (planos de casas/viviendas) with walls, doors, windows, hatched areas and room labels.
---

# Image → SVG (constructed, editable, print-ready)

Turn a raster reference into an SVG that a designer would have drawn by hand:
straight lines where things are straight, true circles and arcs, real symmetry,
consistent repeated elements, correct perspective, a consistent centred layout, editable text, sensible
layers — and visually faithful to the original.

The core lesson behind this skill: **auto-tracing a raster gives you the
raster's defects in vector form** (wobbly edges, asymmetric domes, dents,
micro-holes, slightly different "identical" windows). Users notice immediately.
Tracing is fine for a first measurement pass or for genuinely organic shapes,
but man-made structures should be *reconstructed* from measured primitives.

## Workflow

**Floor plans** (orthogonal architectural plans: walls, doors, windows,
room labels) follow the same phases but replace the symmetry/perspective
rules with `references/floor-plans.md` and build with `scripts/plankit.py`.
Read it first when the reference is a plan. Plans are rebuilt by meaning
(walls, doors, windows as identical units), never by converting raster line
work into paths.

Work in phases and get the user's confirmation at the checkpoints marked ✋.
Communicate in the user's language; keep reports short and link to files.

### 1. Intake ✋
Ask only what changes the result (skip what the user already said):
- Faithful reproduction vs. faithful-with-cleanup (default: faithful, refine irregularities).
- Background: none/transparent (common for print on white), flat colour, or texture.
- Text: editable `<text>` (needs the font installed) vs. outlined paths.
- Intended use and size (print size → page `width/height` in mm; keep the
  source aspect ratio, or adapt the layout to a frame's ratio — see
  `references/print-output.md`).

### 2. Get the best reference
Use the highest-quality copy available (a PNG on disk beats a JPEG chat
attachment — ask the user if there's an original file). Copy it into the
project (`reference/original.png`) and never modify the user's original.
If only a chat attachment exists, it may be recoverable from the harness's
session storage; ask before digging into app databases.

### 3. Analyse and propose ✋
Before drawing anything, look at enlarged crops and describe back to the user:
- the overall composition and grid (margins, alternation, alignment);
- each figure: what it is, its parts, which parts are symmetric, repeated
  elements (windows, columns, repeated details), perspective (receding facades);
- typography candidates; colours;
- **equivalence classes and grid**: objects with the same role that must be
  identical (backdrop shapes, text roles, bars, dividers, paired rules,
  repeated blocks), the common margins, centred items and vertical rhythm.
  The reference is often inconsistent here ("equal" shapes of different
  sizes, one text role at several sizes); propose unifying and ask only
  where a difference may be intended.
  See `references/layout.md`.
Then propose the object structure (layers/groups, names). Group each
illustration as one folder-like group (e.g. `illustration`) with
its components as separate, named children; labels in short kebab-case
(naming rules in `references/svg-structure.md`). Wait for confirmation.

### 4. Measure
Measure, don't eyeball. Use `scripts/measure.py` (grid crops, top profiles,
openings, line/circle fits, colour sampling) and see
`references/measuring.md` for techniques. Record numbers per component:
outline coordinates, axes of symmetry, window boxes, circle centres/radii.

### 5. Construct the geometry
Build each object from primitives with `scripts/svgkit.py` (polygons with
automatic winding, arched windows, perspective arches, domes, ellipses, spikes,
mirroring, a `Part` that collects solids/openings/knockouts). Read
`references/construction.md` — it contains the rules that made the
difference: straight edges, symmetry by mirroring around a measured axis,
identical repeated elements, perspective via vanishing lines, merging parts
that belong together, filling micro-holes, removing dents, avoiding seams.

Write the build as a script (e.g. `build_svg.py` + `architecture.py`) so every
change is a re-run, not hand-editing XML.

### 5b. Layout system
Place everything on one grid defined as constants (margins symmetric about
the page centre, one radius per class of backdrop shape, one style per text
role, one vertical rhythm per repeated block, equal/mirrored rules). Align
text by its real ink using `inkscape --query-all`, then centre the whole
artwork on the page and bake the translation into the coordinates. Read
`references/layout.md`.

### 6. Typography and colour
Match fonts quantitatively with `scripts/font_match.py`; keep text editable
with one x + a letter-spacing shared by every text of the same role,
calibrated from the reference ink widths. Sample
colours from flat interior areas (median, not single pixels). Details in
`references/typography-and-colour.md`.

### 7. Verify, section by section
After every build:
1. Render with Inkscape (`scripts/compare.py` does this) and compare each
   section side-by-side with the reference plus a red/blue difference overlay.
2. Check symmetric figures with `scripts/symmetry.py` (mirror about the axis;
   residue should be ~0.1% — the rest is antialiasing or intentionally
   asymmetric details like clock hands).
3. Inspect at print resolution (300 dpi crop) for seams, hairlines, gaps,
   leftover dents.
4. Audit layout consistency with `scripts/consistency.py` (equal radii,
   text styles per role, bars, rule widths, margins, vertical rhythm,
   section spacing, colour-pair relations, centring). Every finding is either fixed or confirmed as intentional.
5. Validate the file with `scripts/validate.py` (no raster images/filters,
   unique ids, resolvable `url(#…)`, text objects present, page size).
Look at the images yourself before reporting. Overlap scores are diagnostics,
not the goal — a refined construction will legitimately differ from a
blurry, irregular source.

### 8. Deliver and iterate
Report briefly: what was built, intentional deviations from the reference
(e.g. made something symmetric, unified window counts), font dependency, links
to the SVG, a preview PNG, and comparison images. Expect focused feedback
rounds ("this isn't symmetric", "make the windows follow perspective",
"match this detail") — re-measure the specific area at high zoom, rebuild,
and show a before/after crop next to the reference. When a request is
ambiguous (e.g. which perspective model), render the options as a quick
diagram and let the user pick instead of guessing. Show alternatives
(fonts, colours, spacing) as comparison sheets: original | current | option.
Content changes (new names, dates, values) keep frozen styles and are verified
facts — see `references/typography-and-colour.md`.

### 9. Refinement
Rules for repeated blocks, colour derivation, text weight, small caps, markers
next to text and Inkscape text pitfalls are in
`references/details-and-pitfalls.md`. Read it when refining text or adding
secondary graphics.

### 10. Print output (when the user will print it)
Page size as one setting (`PAGE_MM`), changing the aspect ratio by
redistributing white space, print-ready CMYK PDFs (outlined text, bleed,
PDF/X-4) and a tiled home test print with `scripts/tile_print.py`. Read
`references/print-output.md`.

## Environment notes
- Python deps (use a throwaway venv, e.g. `uv venv` in the temp dir):
  `pillow numpy scipy opencv-python-headless fonttools lxml` (+ `pymupdf` for
  print PDFs and tiling; Ghostscript for CMYK).
- Inkscape CLI renders reliably: `inkscape in.svg --export-type=png
  --export-filename=out.png --export-width=4096 --export-background=white
  --export-background-opacity=1`. Image viewers may cache — write new
  filenames for successive previews.
- Potrace ships inside Inkscape (`libpotrace`); `scripts/contour.py` wraps it
  for organic shapes or a first measurement trace.

## Files
- `references/construction.md` — geometry rules for buildings/structures, perspective, symmetry, SVG fill/holes/seams. **Read before constructing.**
- `references/measuring.md` — how to extract reliable numbers from the raster.
- `references/layout.md` — equivalence classes, grid/margins, vertical rhythm, ink alignment, shared letter-spacing, centring the artwork.
- `references/typography-and-colour.md` — font matching, editable text, colour.
- `references/details-and-pitfalls.md` — refinement rules for repeated blocks, colour derivation, text weight, small caps, matching markers to text, Inkscape text pitfalls, tidy project folders.
- `references/print-output.md` — page size/aspect changes, CMYK PDF/X pipeline, bleed, tiled home test print.
- `references/svg-structure.md` — layers/groups for Inkscape, backdrop knockouts, print setup, delivery checklist.
- `scripts/svgkit.py` — geometry primitives and `Part` (import it from your build script).
- `references/floor-plans.md` — floor plans: inventory, wall classes, openings, doors/windows, hatching, labels, grouping by room, checks.
- `scripts/plankit.py` — floor-plan primitives: snapping/clusters, wall union with openings, doors, windows, clipped hatching, markers.
- `scripts/measure.py` — CLI: `grid`, `profile`, `holes`, `color`, `fit-circle`, `fit-line`, `walls`.
- `scripts/font_match.py` — rank installed/candidate fonts against a text crop.
- `scripts/compare.py` — render + side-by-side + overlay per region.
- `scripts/symmetry.py` — mirror-symmetry residue per figure.
- `scripts/consistency.py` — layout audit: equal objects, alignment, margins, rhythm, centring.
- `scripts/validate.py` — structural checks of the final SVG.
- `scripts/tile_print.py` — split a poster PDF into A4 (or other) sheets at 100% for a home test print.
- `scripts/contour.py` — potrace-based optimised contour for organic shapes.
