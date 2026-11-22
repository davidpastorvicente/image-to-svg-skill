# 3D model of a floor plan (`scripts/plan3d.py`)

Turns a plan built with plankit into a navigable 3D model: walls with real
door and window openings, open door leaves, glass, built-in wardrobes,
floors per room, ceiling, room labels on the floor. Output:

- `<output>.glb` — glTF 2.0 in metres, Y up (Blender, macOS Preview, any viewer).
- `<output>.html` — self-contained viewer with the model and three.js inlined:
  opens with a double click, works offline. Modes: **Model** (orbit, no
  ceiling), **Plan** (top view, names drawn over the walls), **Walk** (first
  person at eye height, WASD/arrows, Shift to run, mouse look, collisions with
  walls, wardrobes, glass and door leaves, current room shown). Ceiling,
  doors and names can be toggled; "Go to…" jumps to a room. URL hash opens a
  view directly: `#plan`, `#walk:<room>:<heading>`.

Only when the user asks for 3D. Stdlib Python ≥ 3.11; the viewer bundle is
prebuilt (`scripts/plan3d_viewer/viewer.bundle.js`, three.js, MIT). Rebuild
it with `plan3d_viewer/build.sh` (Node.js) only after editing `viewer.js`.

## What each plan provides: `plan3d.json`
The SVG is not enough — it has no heights and doesn't say which gap is a
door or a window — so the plan's build script writes its semantic geometry
next to `plano.svg`. Everything is already in the build script; dump it:

```python
plan3d = {
    'units_per_m': 100,                      # plan units per metre (omit if unknown)
    'envelope': ENVELOPE,                    # room-first plans: walls = envelope - floors - holes
    # 'solids': solids,                      # OR wall-by-wall plans: the wall rects
    'floors': FLOORS,                        # {room: [rects]}; optional with 'solids' (see below)
    'wardrobes': closet_rects,               # [rects]
    'doors': {k: {'hole': u['hole'], 'leaves': u['leaves']} for k, u in doors.items()},
    'windows': {k: {'hole': u['hole'], 'frames': u['frames']} for k, u in windows.items()},
    'labels': {room: {'name': 'COCINA', 'area': '11.77 m²', 'x': cx, 'y': cy, 'rotated': False}},
    'label_size': 19,                        # name font size in plan units
    # 'roofed': [rects],                     # optional: area under the ceiling
}
(HERE / 'plan3d.json').write_text(json.dumps(plan3d, ensure_ascii=False), encoding='utf-8')
```

- Labels: `x, y` = **centre** of the name + area block (for a baseline `y`:
  `y + gap/2 - name_size*0.35`), in plan units.
- **Wall-by-wall plans** (`solids`) usually have no floor rects: every region
  enclosed by walls, doors and windows becomes the room whose label lies in
  it (nearest label if several share a region; unlabelled enclosed regions,
  e.g. shafts, get the default floor). Regions open to the outside are
  dropped, so list open-air areas bounded only by site lines (terraces,
  porches, gardens) explicitly in `floors`.
- **Ceiling**: `roofed` rects if given; otherwise indoor floors, wardrobes,
  and walls/openings whose centre is within `[roof] reach` (60 cm) of an
  indoor floor. Walls outside it get `outdoor_wall` height.
- The script prints each room's free-floor area from the geometry next to
  the label: a quick check of the scale (wardrobes are counted in labels but
  not in the free floor).

## What each case configures: `3d/config.toml`
Lengths in cm; every key optional (defaults in `plan3d.py`). Keys are
English; room / door / window keys are the plan's own ids.

```toml
plan = "../plan3d.json"     # relative to this file
output = "casa"             # casa.glb + casa.html next to this file
title = "Ibosa"
units_per_m = 127           # only if the plan JSON can't know it (pixel plans)

[heights]                   # ceiling slab door sill head wardrobe outdoor_wall eye
ceiling = 260

[doors.entrada]             # per door
height = 220

[windows.salon]             # per window: sill / head, or
match_door = "salon-terraza"   # floor to that door's height (fixed glass beside a door)

[finishes]
glass_doors = ["salon-terraza"]
exterior_doors = ["entrada"]
outdoor_rooms = ["terraza"]  # no ceiling
default_floor = "wood"

[finishes.floors]           # room = a key of [colors]; "decking" draws boards
bano-1 = "tile"
terraza = "decking"
jardin = "grass"

[colors]                    # wall outdoor_wall ceiling wardrobe door exterior_door glass
wall = "#efebe4"            # glass_opacity wood tile decking decking_gap grass threshold

[decking]                   # board / period (cm), along = "x" | "y" (plan axis of the boards)
along = "y"

[roof]
reach = 60

[walk]                      # start room, heading (0 = plan top, 90 = right), speed m/s
start = "vestibulo"
heading = 270

[viewer]
label_font = "Futura, 'Avenir Next', sans-serif"
```

Run: `python3 <skill>/scripts/plan3d.py 3d/config.toml`. Keep only the
config in the project: the script and viewer live in the skill.

## Scale and typical values
- Plans in cm: `units_per_m = 100` in the JSON. Plans in reference pixels:
  ask for a known dimension; failing that, fit `units_per_m` so the printed
  areas match the labelled ones (they usually include wardrobes, so expect
  ±3 %) and **say it is an estimate**.
- Plans carry no heights: use typical values (ceiling 250–260, doors 203–210,
  entrance 210–220, sill 90–110, head = door height, wardrobes 240) and tell
  the user they are assumptions in the config.
- Ask (or infer from the plan symbol) which windows beside a door are fixed
  glass down to the floor: `match_door`.

## Verify
- Validate the GLB: `npx gltf-validator` or the `gltf-validator` npm package
  → 0 errors.
- Headless screenshots of each mode (no server needed):
  `"<Chrome>" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader
  --window-size=1400,900 --virtual-time-budget=8000 --screenshot=out.png
  "file://…/casa.html#walk:salon:270"`. Check: openings where the plan has
  them, window sills and lintels, door leaves, labels in their rooms, no
  ceiling over open-air areas.
- The in-app browser can only navigate to http(s): serve the folder with
  `python3 -m http.server` if you need it.
