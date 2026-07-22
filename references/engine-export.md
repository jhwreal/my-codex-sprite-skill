# Engine export

## Generic atlas contract

`pack_atlas.py` writes one row per approved action. Every cell has the run's fixed frame dimensions. `atlas.json` records:

- atlas filename and dimensions;
- cell width and height;
- bottom-center anchor convention;
- action name, FPS, loop flag, and row;
- frame rectangle and duration for every frame;
- selected candidate and visual-approval note.

This contract is the source of truth for custom importers. Do not infer frame count from transparent trailing cells.

## Godot 4

Pass `--godot-resource-path` using the path where `atlas.png` will live inside the Godot project. The exporter writes `sprite_frames.tres` with one `AtlasTexture` per frame and one `SpriteFrames` animation per action.

After copying both files into the project:

1. Assign the `.tres` resource to `AnimatedSprite2D.sprite_frames`.
2. Verify every animation name, speed, and loop flag.
3. Keep the node origin consistent with bottom-center frame placement.
4. Use nearest filtering for pixel art.
5. Store collision, hurt, and attack boxes separately from visual bounds.

If the resource path changes, regenerate the `.tres` with the new `res://` atlas path.

## Unity

Import `atlas.png` as Sprite Mode `Multiple`. Slice it by fixed cell size using the atlas dimensions in `atlas.json`. Use the JSON action rows and frame counts to create clips; do not animate transparent trailing cells.

Set a consistent bottom-center pivot. For pixel art, use Point filtering, disable mipmaps, and select an appropriate Pixels Per Unit. Keep hitboxes in animation events or separate data rather than deriving them from changing sprite bounds.

## Phaser

Load the atlas as a spritesheet with the exported cell width and height. Build each animation from the exact frame rectangles or row indices in `atlas.json`, using its FPS and loop flag.

Do not rely on a global `endFrame` when rows have different frame counts. Generate each action's frame list explicitly.
