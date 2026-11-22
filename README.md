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
| `references/measuring.md` | How to extract reliable numbers from a raster or a vector reference |
| `references/typography-and-colour.md` | Font matching, editable text with consistent spacing, colour relationships, verifying content facts |
| `references/layout.md` | Consistency, margins, vertical rhythm, alignment by real ink, centring |
| `references/details-and-pitfalls.md` | Refinement rules (repeated blocks, colour derivation, text weight, small caps) and Inkscape text pitfalls |
| `references/print-output.md` | Page size and aspect changes, CMYK PDF/X pipeline, bleed, tiled home test print |
| `references/svg-structure.md` | Layers/groups for Inkscape, backdrop knockouts, print setup, delivery checklist |
| `references/floor-plans.md` | Floor plans: inventory, room-first or wall-by-wall walls, openings, doors/windows, wardrobes, hatching, labels and areas, layers, checks |
| `scripts/svgkit.py` | Geometry primitives (polygons with automatic winding, arches, perspective arches, mirroring, `Part`) |
| `scripts/plankit.py` | Floor-plan primitives: coordinate snapping, wall union with openings, room-first walls and areas, doors (swing, double, sliding, door + fixed window), windows, wardrobes, clipped hatching, markers |
| `scripts/planrender.py` | Floor-plan SVG output: scalable house style, labelled room groups, jamb ownership, Inkscape export-area and label-fit helpers |
| `scripts/vector_measure.py` | CLI for vector references (SVG/PDF): group tree, shapes with transforms applied in real units, room floors as rects + areas |
| `references/plan-3d.md` | 3D model of a floor plan: the plan JSON, the per-case config, scale and typical heights, checks |
| `scripts/plan3d.py` | Builds a glTF model and a self-contained, navigable HTML viewer (orbit, top view, first-person walk) from a plan's JSON + `config.toml` |
| `scripts/plan3d_viewer/` | The viewer: source (`viewer.js`, `template.html`), prebuilt three.js bundle and `build.sh` to rebuild it |
| `scripts/measure.py` | CLI: zoomed grids, profiles, openings, scans, colour, circle/line fits, wall rectangles for floor plans |
| `scripts/font_match.py` | Rank candidate fonts against a text crop |
| `scripts/compare.py` | Render the SVG and compare regions with the reference |
| `scripts/symmetry.py` | Mirror-symmetry residue per figure |
| `scripts/consistency.py` | Layout audit: equal objects, text styles, margins, spacing, colour pairs, centring |
| `scripts/validate.py` | Structural checks of the final SVG |
| `scripts/tile_print.py` | Split a poster PDF into A4 (or other) sheets at 100% for a home test print |
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
  (+ `svgelements` for vector references)
- [Inkscape](https://inkscape.org) on `PATH` (rendering, bounding boxes, potrace)
- Plan 3D models: Python ≥ 3.11 only (the three.js viewer ships prebuilt;
  Node.js is needed only to rebuild it)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pillow numpy scipy opencv-python-headless fonttools lxml svgelements
```

## Usage

Ask your agent to convert, redraw or vectorize an image into SVG, for example:

> Rebuild this poster as an editable, print-ready SVG for a 50×70 cm frame.

The agent asks only what changes the result (fidelity, background, text as
editable `<text>`, print size), proposes the layer/group structure, builds the
SVG from code, and verifies it section by section.

## License

MIT, see [LICENSE](LICENSE).
