# Print output: page size, print PDFs, home test print

## Page size as one setting
- Keep the drawing on a fixed-width canvas (e.g. 1024 units) and derive the page
  height from one constant, `PAGE_MM = (w, h)`. Write `width/height` in mm and the
  `viewBox` from it; never hard-code the height elsewhere (clip rectangles,
  Inkscape-query unit conversion, validation, centring, render sizes).
- **Changing the aspect ratio** (e.g. to fit a standard frame size): keep every
  element's size and the side margins; change only the vertical white space.
  Scale the top/bottom margin and the gaps between sections by the same factor,
  so the margin : gap ratio stays as the user approved it. With a layout that
  distributes free height over the gaps (layout.md), only the margin constant
  changes. Show a side-by-side of old vs new format before printing.
- Prefer redesigning to the frame's ratio over cropping. If a ratio differs only
  slightly, the print script may centre and crop/extend the white margin instead.
- The width in mm also changes the physical size of everything; mention it
  (a slightly narrower format makes every element proportionally smaller).

## Print PDFs
- **Ask the print shop** what they want: exact size, bleed (usually 3 mm),
  CMYK profile (FOGRA39 / ISO Coated v2 in Europe, GRACoL/SWOP in the US), PDF/X.
  Typical: PDF/X-4, CMYK, fonts outlined, no crop marks unless asked.
- **Bleed**: only needed when ink reaches the page edge. If the artwork keeps a
  white margin of a few cm, deliver the exact size without bleed (and optionally
  a bleed version); an accidental 3 mm trim then can't cut anything.
- Pipeline that works without commercial tools:
  1. Copy the SVG, set `width/height` to final size + 2·bleed and widen the
     `viewBox` by the bleed (no scaling of the artwork).
  2. `inkscape copy.svg --export-type=pdf --export-text-to-path --export-area-page`
     (outlined text: no font dependency at the printer).
  3. Ghostscript to CMYK PDF/X-4 with the ICC profile as output intent:
     `gs -dPDFX=4 -sDEVICE=pdfwrite -sColorConversionStrategy=CMYK
     -sProcessColorModel=DeviceCMYK -sOutputICCProfile=profile.icc
     -dRenderIntent=1 -dBlackPtComp=1 PDFX_def.ps in.pdf` (edit the
     `PDFX_def.ps` shipped with Ghostscript: ICC path, OutputCondition).
  4. Set TrimBox = page minus bleed and BleedBox = page (pymupdf).
  5. Check: page size in mm, trim box, 0 fonts, 0 images, no RGB operators,
     max total ink (TAC) under the profile limit (300% FOGRA39).
- Name files with size and variant (`poster-<w>x<h>cm-CMYK-Fogra39-no-bleed.pdf`),
  parameterise the script by bleed and size (default: the SVG page), and move
  outdated outputs to an `archive-…` folder instead of deleting them.
- Also export a 300 ppi PNG of the exact page for online services that want raster.
- Pastels and near-blacks shift in CMYK; tell the user that screen ≠ print and
  suggest a test print.

## Home test print (tiling)
`scripts/tile_print.py poster.pdf [--sheet 210 297] [--lang es]` splits the
no-bleed PDF into sheets at 100% scale so the user can check size and
proportions at home before paying for the real print. Rules it follows (users
asked for each of them):
- Use the poster's white margin: outer tiles sit flush with the sheet edges, so
  the sheet edge is the poster edge and needs no cutting.
- Every other sheet is cut on one or two sides only (left/top) and glued over
  the previous one; its cut falls exactly on the tile edge (no offset gap).
- Print nothing on the visible part: no frame lines, no dashed lines across the
  artwork. Only short corner ticks, scissors lying along the edge to cut, and a
  short label ("Row 2 · Column 3 | Cut along the left and top"), all in strips
  that are cut off or covered.
- Remind the user: print at 100% / actual size (not "fit to page"); measure one
  tile with a ruler to confirm the scale.
