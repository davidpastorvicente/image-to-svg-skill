# image-to-svg

An agent skill that recreates a raster image (poster, illustration, skyline,
logo-like artwork, infographic, silhouette art) as a **clean, editable,
print-ready SVG built from constructed geometry** instead of auto-tracing.

Auto-tracing copies the raster's defects into vector form: wobbly edges,
asymmetric domes, dents, micro-holes, "identical" windows that differ. This
skill makes the agent measure the reference and rebuild it the way a designer
would: straight lines where things are straight, real symmetry, identical
repeated elements, correct perspective, editable text and a consistent,
centred layout.

## What's inside

| Path | Purpose |
|---|---|
| `SKILL.md` | The workflow (intake → analysis → measuring → construction → typography → layout → verification → delivery) |
| `references/construction.md` | Geometry rules for buildings and structures: straight edges, symmetry, repeated elements, perspective, SVG winding and seams |
| `references/measuring.md` | How to extract reliable numbers from a raster |
| `references/typography-and-colour.md` | Font matching, editable text with consistent spacing, colour relationships, verifying content facts |
| `references/layout.md` | Consistency, margins, vertical rhythm, alignment by real ink, centring |
| `references/details-and-pitfalls.md` | Refinement rules (repeated blocks, colour derivation, text weight, small caps) and Inkscape text pitfalls |
| `references/svg-structure.md` | Layers/groups for Inkscape, backdrop knockouts, print setup, delivery checklist |
| `scripts/svgkit.py` | Geometry primitives (polygons with automatic winding, arches, perspective arches, mirroring, `Part`) |
| `scripts/measure.py` | CLI: zoomed grids, profiles, openings, scans, colour, circle/line fits |
| `scripts/font_match.py` | Rank candidate fonts against a text crop |
| `scripts/compare.py` | Render the SVG and compare regions with the reference |
| `scripts/symmetry.py` | Mirror-symmetry residue per figure |
| `scripts/consistency.py` | Layout audit: equal objects, text styles, margins, spacing, colour pairs, centring |
| `scripts/validate.py` | Structural checks of the final SVG |
| `scripts/contour.py` | potrace-based contour for organic shapes |

## Install

Copy or clone this folder into your agent's skills directory, e.g.:

```bash
git clone https://github.com/davidpastorvicente/image-to-svg-skill ~/.agents/skills/image-to-svg
```

The `SKILL.md` front matter (name and description) follows the common
agent-skill format, so it works with agents that load skills from a folder
(OpenCode, Claude Code, and others).

## Requirements

- Python 3 with `pillow numpy scipy opencv-python-headless fonttools lxml`
- [Inkscape](https://inkscape.org) on `PATH` (rendering, bounding boxes, potrace)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pillow numpy scipy opencv-python-headless fonttools lxml
```

## Usage

Ask your agent to convert, redraw or vectorize an image into SVG, for example:

> Rebuild this poster as an editable, print-ready SVG for 30×45 cm.

The agent asks only what changes the result (fidelity, background, text as
editable `<text>`, print size), proposes the layer/group structure, builds the
SVG from code, and verifies it section by section.

## License

MIT, see [LICENSE](LICENSE).
