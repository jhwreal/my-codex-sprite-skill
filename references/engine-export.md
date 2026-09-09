# Engine export

## Generic atlas contract

`pack_atlas.py` writes one row per approved action. Every cell has the run's fixed frame dimensions. `atlas.json` records:

- atlas filename and dimensions;
- cell width and height;
- per-frame normalized anchor and pixel pivot (origin at top-left);
- action name, nominal FPS, exact per-frame durations, loop flag, events, and row;
- frame rectangle and duration for every frame;
- selected candidate and visual-approval note.

This contract is the source of truth for custom importers. Do not infer frame count from transparent trailing cells.

## Godot 4

Pass `--godot-resource-path` using the path where `atlas.png` will live inside the Godot project. The exporter writes `sprite_frames.tres` with one `AtlasTexture` per frame and one `SpriteFrames` animation per action.

After copying both files into the project:

1. Assign the `.tres` resource to `AnimatedSprite2D.sprite_frames`.
2. Verify every animation name, speed, and loop flag.
3. With `AnimatedSprite2D.centered = true`, apply the exported animation `godot_offset = frame_size / 2 - pivot`. A `SpriteFrames` resource itself cannot set the node offset. Verify it at action transitions.
4. Use nearest filtering for pixel art.
5. Store collision, hurt, and attack boxes separately from visual bounds.

If the resource path changes, regenerate the `.tres` with the new `res://` atlas path.

## Unity

Import `atlas.png` as Sprite Mode `Multiple`. Slice it by fixed cell size using the atlas dimensions in `atlas.json`. Use the JSON action rows and frame counts to create clips; do not animate transparent trailing cells.

Use each exported pivot consistently. The JSON uses a top-left origin; Unity normalized pivots use a bottom-left origin, so convert `y` to `1 - anchor.y`. For pixel art, use Point filtering, disable mipmaps, and select an appropriate Pixels Per Unit. Keep hitboxes in animation events or separate data rather than deriving them from changing sprite bounds.

## Phaser

Load the atlas as a spritesheet with the exported cell width and height. Build each animation from the exact frame rectangles or row indices in `atlas.json`, using its FPS and loop flag.

Do not rely on a global `endFrame` when rows have different frame counts. Generate each action's frame list explicitly.


## Timing and events

Godot frame `duration` is relative to the animation's nominal FPS. The exporter writes `duration_ms * fps / 1000`, preserving exact milliseconds. GIF previews round to 10ms and may merge identical frames; they are not exact timing evidence.

`atlas.json` keeps named events with 1-based frame indices and cumulative `time_ms` at that frame's start, plus optional phases and contact notes. Events are data for the game to dispatch; the exporter does not create attack boxes or execute gameplay code. Phaser/custom importers must use the per-frame durations when present instead of flattening them back to nominal FPS.

Schema 2 exports actual per-action/per-frame pivots. Do not use an importer that assumes the old global `bottom-center` string. Legacy fitting retains its old frame appearance and pivot convention; new fixed-canvas runs use the declared root.
