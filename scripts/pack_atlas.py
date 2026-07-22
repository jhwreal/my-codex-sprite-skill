#!/usr/bin/env python3
"""Pack visually approved actions into a generic atlas and optional Godot resource."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _sprite_common import (
    Image,
    clear_transparent_rgb,
    image_files,
    read_json,
    transparent_rgb_residue_count,
    write_json,
    write_text,
)


def godot_resource(
    atlas_resource_path: str,
    animations: list[dict[str, Any]],
) -> str:
    subresources: list[str] = []
    animation_entries: list[str] = []
    resource_index = 1
    for animation in animations:
        frame_entries: list[str] = []
        for frame in animation["frames"]:
            resource_id = f"AtlasTexture_{resource_index}"
            resource_index += 1
            region = frame["frame"]
            subresources.append(
                "\n".join(
                    [
                        f'[sub_resource type="AtlasTexture" id="{resource_id}"]',
                        'atlas = ExtResource("1_atlas")',
                        f"region = Rect2({region['x']}, {region['y']}, {region['w']}, {region['h']})",
                    ]
                )
            )
            frame_entries.append(
                '{"duration": 1.0, "texture": SubResource("' + resource_id + '")}')
        animation_entries.append(
            "{\n"
            + f'"frames": [{", ".join(frame_entries)}],\n'
            + f'"loop": {str(bool(animation["loop"])).lower()},\n'
            + f'"name": &"{animation["name"]}",\n'
            + f'"speed": {float(animation["fps"]):g}\n'
            + "}"
        )
    header = [
        f'[gd_resource type="SpriteFrames" load_steps={resource_index + 1} format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{atlas_resource_path}" id="1_atlas"]',
        "",
    ]
    body = "\n\n".join(subresources)
    return "\n".join(header) + body + "\n\n[resource]\nanimations = [" + ",\n".join(animation_entries) + "]\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack approved sprite actions into a fixed-cell atlas.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--godot-resource-path", help="Godot res:// path to the exported atlas.png.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    run = read_json(run_dir / "run.json")
    selected: list[tuple[dict[str, Any], dict[str, Any], list[Path]]] = []
    for action_summary in run.get("actions", []):
        action_id = action_summary["id"]
        action_dir = run_dir / "actions" / action_id
        action = read_json(action_dir / "action.json")
        candidate = action.get("selected_candidate")
        if not candidate or action.get("status") != "approved":
            raise SystemExit(f"Action is not visually approved: {action_id}")
        frames = image_files(action_dir / "candidates" / candidate / "frames")
        if len(frames) != int(action["frame_count"]):
            raise SystemExit(f"Action {action_id} has {len(frames)} frames; expected {action['frame_count']}.")
        selected.append((action, action_summary, frames))
    if not selected:
        raise SystemExit("No approved actions were found.")

    frame_width = int(run["output"]["frame_width"])
    frame_height = int(run["output"]["frame_height"])
    columns = max(len(frames) for _action, _summary, frames in selected)
    rows = len(selected)
    atlas = Image.new("RGBA", (columns * frame_width, rows * frame_height), (0, 0, 0, 0))
    animations: list[dict[str, Any]] = []
    frame_records: dict[str, Any] = {}
    for row, (action, _summary, frame_paths) in enumerate(selected):
        animation_frames: list[dict[str, Any]] = []
        duration_ms = max(1, int(round(1000 / float(action["fps"]))))
        for column, frame_path in enumerate(frame_paths):
            frame = Image.open(frame_path).convert("RGBA")
            if frame.size != (frame_width, frame_height):
                raise SystemExit(f"Unexpected frame size in {frame_path}: {frame.size}")
            atlas.alpha_composite(frame, (column * frame_width, row * frame_height))
            key = f"{action['id']}/{column + 1:04d}"
            rectangle = {
                "x": column * frame_width,
                "y": row * frame_height,
                "w": frame_width,
                "h": frame_height,
            }
            record = {"frame": rectangle, "duration_ms": duration_ms, "anchor": {"x": 0.5, "y": 1.0}}
            frame_records[key] = record
            animation_frames.append(record)
        animations.append(
            {
                "name": action["id"],
                "row": row,
                "fps": float(action["fps"]),
                "loop": bool(action["loop"]),
                "selected_candidate": action["selected_candidate"],
                "visual_review": action.get("visual_review", {}),
                "frames": animation_frames,
            }
        )

    atlas = clear_transparent_rgb(atlas)
    output_dir.mkdir(parents=True, exist_ok=True)
    atlas_path = output_dir / "atlas.png"
    json_path = output_dir / "atlas.json"
    validation_path = output_dir / "validation.json"
    for path in (atlas_path, json_path, validation_path):
        if path.exists() and not args.force:
            raise SystemExit(f"Refusing to overwrite {path}; pass --force after confirming replacement.")
    atlas.save(atlas_path)
    manifest = {
        "schema_version": 1,
        "image": atlas_path.name,
        "size": {"width": atlas.width, "height": atlas.height},
        "grid": {"columns": columns, "rows": rows, "cell_width": frame_width, "cell_height": frame_height},
        "anchor": "bottom-center",
        "frames": frame_records,
        "animations": animations,
    }
    write_json(json_path, manifest)
    residue = transparent_rgb_residue_count(atlas)
    validation = {
        "ok": residue == 0,
        "atlas": str(atlas_path),
        "dimensions": [atlas.width, atlas.height],
        "transparent_rgb_residue_pixels": residue,
        "action_count": len(animations),
        "actions": [animation["name"] for animation in animations],
    }
    write_json(validation_path, validation)
    if args.godot_resource_path:
        if not args.godot_resource_path.startswith("res://"):
            raise SystemExit("--godot-resource-path must start with res://")
        write_text(output_dir / "sprite_frames.tres", godot_resource(args.godot_resource_path, animations))
    print(f"atlas={atlas_path}")
    print(f"manifest={json_path}")
    print(f"validation={validation_path}")
    if args.godot_resource_path:
        print(f"godot={output_dir / 'sprite_frames.tres'}")
    if residue:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
