# SVG structure, print setup and delivery

## Document
```xml
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="300mm" height="450mm" viewBox="0 0 1024 1536">
```
- `viewBox` = reference pixel size, so measurements are used verbatim.
- `width/height` = physical print size with the same aspect ratio.
- No background rectangle when the user wants a transparent/white page.
- `<title>`/`<desc>` describing the artwork.

## Objects panel (Inkscape)
- Top-level sections as **layers**: `<g inkscape:groupmode="layer"
  inkscape:label="Section A">`.
- Inside, the agreed objects in a sensible order, each with an `id` and an
  `inkscape:label` (human name). The illustration is one **group**
  ("Architectural silhouette") with one child path per building/structure.
- Use real primitives where they are the natural edit handle: `<circle>` for
  backdrop discs, wheel rims, cabins, hubs; `<rect>` for accent bars;
  `<text>` for text; stroked `<path>`s for rules, spokes, cables.
- Set `fill` on the group so children inherit it.

## Backdrop shapes behind silhouettes
If a coloured disc sits behind a silhouette whose openings show the *paper*
colour in the reference (windows read white, not pastel), the disc must not
show through the openings. Clip the disc with a clipPath = big rectangle +
every opening/separation gap (fill/clip-rule evenodd). Collect these
"knockouts" automatically while building (`svgkit.Part.knockouts`). Also clip
the disc at the ground line if it shouldn't show below it.

## Build pipeline
- `build_svg.py` writes the whole SVG with lxml from code (geometry module +
  text + layers). Never hand-edit the output; edit the code and rebuild.
- One `rebuild.py` that runs: build → Inkscape renders (preview, 300 dpi,
  transparent, 4 px/unit for symmetry) → `compare.py` → `validate.py`.

## Delivery checklist
- [ ] Opens in Inkscape; Objects panel shows the agreed layers/groups/names.
- [ ] No `<image>`, filters, scripts or external hrefs; unique ids; all
      `url(#…)` resolve (`scripts/validate.py`).
- [ ] Text objects editable and spelled correctly (incl. diacritics).
- [ ] `scripts/consistency.py` clean: equal objects identical, margins symmetric,
      rhythm equal, artwork centred on the page.
- [ ] Section comparisons reviewed at zoom; symmetry residue ≈ 0.
- [ ] 300 dpi crop free of seams, hairlines, dents, micro-holes.
- [ ] Thinnest stroke printable at the target size (≥ ~0.1 mm).
- [ ] Transparent where intended (render with background opacity 0 and
      sample alpha in openings and page).
- [ ] README/notes: font dependency, size, colour mode, deviations from the
      reference, how to rebuild.
- [ ] Report to the user: links to SVG, preview PNG and comparison crops;
      list intentional deviations; offer next refinements.
