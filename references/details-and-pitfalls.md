# Refinement rules and pitfalls

## Apply every rule to every repeated block
Any change (spacing, weight, a new element) goes through the shared
function/constants, never to one block by hand. After each change run the
consistency and validate scripts. The rule must hold for mirrored blocks too
(left- vs right-aligned): an element that comes first on one side comes last on
the other.

## One source per colour family
Define each section's base colour once and derive every related colour from it
with functions (OKLCH, see typography-and-colour.md). Anything that belongs to
that section (outlines, markers, symbols) must come from those functions, so
changing the base updates all of them.

## Text weight without changing font
Heavier-looking text can be had with a same-colour `stroke` proportional to
font size (`stroke-width = size × k`, `stroke-linejoin="round"`), keeping the
text editable. Use one k per role, and compare values on a zoomed sheet.

## Small caps from one font
Full-size first letters and a reduced size (≈ 0.8–0.85) for the rest, with the
same letter-spacing, emitted as `<tspan font-size=…>`. Keep the ratio a constant.

## Matching a marker to adjacent text
- When glyphs of one set have very different widths, font cuts won't fix it and
  squeezing single glyphs distorts them; consider a fixed-size container
  (circle, box) so the markers are equal.
- Size such markers from the real ink of the neighbouring text (use the round
  digit for round markers, plus half the stroke on each side) so tops and
  bottoms line up; centre contents on glyph bounds, not the advance.
- Where columns must align, position from font metrics (tabular digits give a
  fixed advance) rather than from rendered queries.
- Expose gaps, sizes and weights as constants.
- When several design options exist, render a mock-up sheet in the real colours
  and size and let the user choose before building.

## Data-derived graphics
If a graphic encodes data that also appears as text (positions, values), compute
it from the same source as the text so they can't disagree, and keep the data
and projection in a small file in the project so the build needs no downloads.
Smooth polygons lightly if facets show at the final size.

## Editable-text pitfalls (Inkscape / SVG)
- Inkscape ignores `textLength` on `<tspan>`.
- A tspan with absolute `x`/`y` needs an explicit `y` on the chunk that follows.
- Translation helpers that bake offsets must also shift `x`/`y` on `<tspan>`.
- Hand-built tspans need explicit empty tails (`tail = ''`), otherwise
  pretty-printing inserts whitespace and breaks text checks.
- Attribute names use hyphens (`stroke-width`); `stroke_width` is silently
  ignored. `scripts/validate.py` flags underscore attribute names.
- Image viewers/readers cache files: write each preview to a new filename.

## Refactors must not change the artwork
Renames, regrouping, code clean-ups and format plumbing are invisible changes:
render before and after at a fixed size and require pixel identity (or an
identical SVG) before regenerating print files.

## Tidy project folder
```
build scripts   geometry + layout + text
data/           extracted datasets
reference/      original image copy
checks/         files the scripts read/write (layout, renders, reports)
checks/iterations/   exploration sheets and option mock-ups (not used by build)
README.md       structure, rebuild command, font dependency
```
Keep scripts relative to their own folder (`Path(__file__).parent`) so the
project can be moved without changes. Move outdated outputs to an `archive-…`
folder instead of deleting them.
