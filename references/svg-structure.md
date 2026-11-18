# SVG structure, print setup and delivery

## Document
```xml
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="200mm" height="300mm" viewBox="0 0 1000 1500">
```
- `viewBox` = reference pixel size, so measurements are used verbatim.
- `width/height` = physical print size with the same aspect ratio, derived
  from one `PAGE_MM` constant (see print-output.md).
- No background rectangle when the user wants a transparent/white page.
- `<title>`/`<desc>` describing the artwork.

## Objects panel (Inkscape)
- Top-level sections as **layers**: `<g inkscape:groupmode="layer"
  inkscape:label="section-a">`.
- Inside, the agreed objects in a sensible order, each with an `id` and an
  `inkscape:label`. The illustration is one **group** (e.g. `illustration`) with
  one child path per component.

### Label naming and grouping
Users read the Objects panel as a tree; labels should read like a clean folder
structure, not like descriptions.
- **kebab-case, short, lowercase**: one or two words (`main-tower`), not a
  sentence describing everything the part contains.
- **No repeated context**: a label is read inside its parent, so don't repeat
  the parent's or section's name in it (`section-a > outline`, not
  "Section A outline").
- **Name by role, not by look or colour**: what the object *is* (`underline`,
  `backdrop`), not how it looks ("blue bar", "pastel circle"). Avoid vague words
  that don't say what the object is.
- **Name symbols by meaning**: a marker that shows a letter, icon or value is
  named after what it stands for, not after its shape ("badge", "circle 2").
- **Group siblings that share a prefix or role** and drop the prefix:
  `x-left`/`x-right` → `xs > left, right`; `x-outer`/`x-inner` → `xs > outer,
  inner`; numbered items → `items > 01, 02, …`. A block of related objects
  (e.g. a text with its markers) gets its own group.
- Don't group where it would change the stacking order of overlapping parts;
  say so instead.
- **No status suffixes** ("— editable", "(copy)", "final").
- Labels are local; **ids stay globally unique and stable** (prefixed with their
  section), so scripts and validation don't break when labels change. Set
  labels from the build script, never by hand.
- Label/grouping refactors must not change the artwork: render before and after
  and check the images are pixel-identical.
- Use real primitives where they are the natural edit handle: `<circle>` for
  discs, rings and dots; `<rect>` for bars; `<text>` for text; stroked
  `<path>`s for rules and thin members.
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
