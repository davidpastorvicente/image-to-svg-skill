# Typography and colour

## Finding the font
1. Identify the style (geometric sans, humanist, grotesque, serif, slab…).
   Typical poster faces: Avenir/Avenir Next, Futura, Montserrat, Gotham-like,
   Josefin Sans, Raleway, Lato, Helvetica Neue.
2. Rank candidates quantitatively with `scripts/font_match.py`: crop a word in
   capitals (one without accents is best), render each candidate at a range of
   sizes/trackings, and score IoU of ink masks. Include installed system fonts
   *and* free candidates you download (Google Fonts, OFL).
3. Show the user a comparison sheet (the script writes one). The best match
   by eye and by score usually agree; weight (Regular/Medium/SemiBold) matters
   as much as the family.
4. Check coverage of all characters in the artwork (accented capitals, °, ligatures, currency signs…).

Prefer an installed, licensed font if it matches clearly better; otherwise an
open-licensed one that can be shipped alongside the SVG. Tell the user about
the font dependency: editable `<text>` renders correctly only where the font is
installed; for a printer, export with embedded fonts or a separate outlined
copy.

## Editable text with consistent spacing
- One `<text>` per line with a single `x` and a `letter-spacing` shared by
  all texts of the same role (all titles, all coordinates…). Retyping keeps
  the spacing, and equivalent texts are guaranteed identical.
- Calibrate letter-spacing from the reference ink widths (linear in the
  spacing) and align by the rendered ink with `inkscape --query-all` — see
  `layout.md` §4–5.
- Per-glyph `x="x1 x2 …"` lists reproduce irregular reference spacing
  exactly, but copy its inconsistencies and break when edited; use them only
  for genuinely irregular lettering the user wants kept.
- Fit font-size from cap height and baseline from the bottom of the ink; one
  size per role (average the measurements).
- Avoid CSS properties Inkscape ignores (e.g. `font-kerning`).
- **Freeze the calibrated letter-spacing** as constants once it is fitted.
  If the user later changes the content (new coordinates, names, dates), a
  calibration that solves spacing from the reference *widths* would silently
  re-space the new text to the old width.
- Weight can differ per role: compare candidates per role (titles vs small
  text) — a heavier weight may match big titles while the lighter one matches
  captions. Show a sheet (original | current | candidate per role) and let
  the user choose; don't switch silently.

## Text content and facts
Text in the artwork may encode facts (coordinates, dates, addresses,
populations). When the user asks to change them:
- Geocode addresses with two independent sources (e.g. OpenStreetMap
  Nominatim + a postcode service such as postcodes.io for the UK) and check
  that the match is really the requested place — same postcode/district.
  Ambiguous street names often resolve to another neighbourhood.
- Say how precise each result is (building vs street vs postcode centroid).
  If the user provides their own values (e.g. from Google Maps), use them.
- Keep the artwork's format (decimals, `°`, hemisphere letters N/S/E/W instead
  of negative numbers) and update the validation's expected strings.

## Colour
- Sample medians of flat interiors (eroded masks). Keep slightly warm
  near-blacks and muted pastels exactly — they define the mood.
- Text and illustration ink may differ slightly; sample both.
- Paper texture/background: by default drop it (transparent page) unless the
  user wants a background. Openings then show the paper they print on.
- **Colour relationships**: colours that come in pairs across sections
  (backdrop tint + darker accent, light/dark theme pairs) must follow ONE
  rule in every section, like sizes do. References are often inconsistent
  (each accent darker by a different amount, hue drifting different ways).
  Keep the colours the user likes as the base, derive the others in OKLCH
  (perceptual): same hue, lightness −ΔL, chroma ×k, with ΔL and k = mean of
  the reference pairs. Encode it as a function in the build (`accent(base)`),
  so changing a base colour updates its partner. Show before/after swatches
  in context — deriving tints from saturated colours at exactly the same hue
  can look pinkish/cold (light terracotta → salmon), which is why designers
  shift light tints slightly warm; if that happens prefer the light colour as
  the base.
- Colours are RGB; mention that print colour management/CMYK is the
  printer's step unless the user provides a profile.
