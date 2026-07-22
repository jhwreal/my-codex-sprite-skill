#!/usr/bin/env python3
"""Derive a directional action by mirroring frames without reversing time order."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
from pathlib import Path
from typing import Any

from _sprite_common import (
    Image,
    alpha_bbox,
    clear_transparent_rgb,
    image_files,
    read_json,
    slugify,
    visible_pixel_count,
    write_json,
    write_text,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def find_action(run: dict[str, Any], action_id: str) -> dict[str, Any]:
    for action in run.get("actions", []):
        if action.get("id") == action_id:
            return action
    raise SystemExit(f"Unknown action: {action_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror an approved action frame-by-frame.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-action", required=True)
    parser.add_argument("--target-action", required=True)
    parser.add_argument("--candidate", default="derived-mirror-01")
    parser.add_argument("--confirm-safe-mirror", action="store_true")
    parser.add_argument("--note", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.confirm_safe_mirror:
        raise SystemExit("Mirroring requires --confirm-safe-mirror after checking character asymmetry.")
    if not args.note.strip():
        raise SystemExit("A non-empty mirror decision note is required.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    run = read_json(run_dir / "run.json")
    source_id = slugify(args.source_action)
    target_id = slugify(args.target_action)
    source_summary = find_action(run, source_id)
    target_summary = find_action(run, target_id)
    source_action = read_json(run_dir / "actions" / source_id / "action.json")
    target_action_path = run_dir / "actions" / target_id / "action.json"
    target_action = read_json(target_action_path)
    selected = source_action.get("selected_candidate")
    if source_action.get("status") != "approved" or not selected:
        raise SystemExit("The source action must be QCed, visually approved, and selected before mirroring.")
    if int(source_action["frame_count"]) != int(target_action["frame_count"]):
        raise SystemExit("Source and target actions must have the same frame count.")
    if float(source_action["fps"]) != float(target_action["fps"]) or bool(source_action["loop"]) != bool(
        target_action["loop"]
    ):
        raise SystemExit("Source and target actions must have matching FPS and loop semantics.")

    source_candidate = run_dir / "actions" / source_id / "candidates" / selected
    source_frames = image_files(source_candidate / "frames")
    candidate_id = slugify(args.candidate)
    candidate_dir = run_dir / "actions" / target_id / "candidates" / candidate_id
    if candidate_dir.exists() and any(candidate_dir.iterdir()) and not args.force:
        raise SystemExit(f"Target candidate already contains files: {candidate_dir}")
    frames_dir = candidate_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    target_frames: list[Image.Image] = []
    source_metrics: list[dict[str, Any]] = []
    output_metrics: list[dict[str, Any]] = []
    for index, source_path in enumerate(source_frames, start=1):
        frame = Image.open(source_path).convert("RGBA")
        mirrored = clear_transparent_rgb(frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
        output = frames_dir / f"{index:04d}.png"
        mirrored.save(output)
        bbox = alpha_bbox(mirrored)
        if bbox is None:
            raise SystemExit(f"Mirrored frame became empty: {index}")
        left, top, right, bottom = bbox
        metric = {
            "index": index,
            "slot_width": mirrored.width,
            "slot_height": mirrored.height,
            "visible_pixels": visible_pixel_count(mirrored),
            "bbox": [left, top, right, bottom],
            "bbox_width": right - left,
            "bbox_height": bottom - top,
            "bbox_area": (right - left) * (bottom - top),
            "normalized_center_x": ((left + right) / 2) / mirrored.width,
            "normalized_anchor_y": bottom / mirrored.height,
        }
        source_metrics.append(metric)
        output_metrics.append(
            {
                "index": index,
                "file": str(output.relative_to(candidate_dir)),
                "visible_pixels": visible_pixel_count(mirrored),
                "transparent_rgb_residue_pixels": 0,
            }
        )
        target_frames.append(mirrored)

    frame_width = int(run["output"]["frame_width"])
    frame_height = int(run["output"]["frame_height"])
    sheet = Image.new("RGBA", (frame_width * len(target_frames), frame_height), (0, 0, 0, 0))
    for index, frame in enumerate(target_frames):
        sheet.alpha_composite(frame, (index * frame_width, 0))
    clear_transparent_rgb(sheet).save(candidate_dir / "sheet.png")
    shutil.copy2(run_dir / "actions" / target_id / "prompt.md", candidate_dir / "prompt-used.md")
    write_text(candidate_dir / "derivation-note.md", args.note.strip())
    write_json(
        candidate_dir / "processing.json",
        {
            "schema_version": 1,
            "processed_at": utc_now(),
            "action": target_id,
            "candidate": candidate_id,
            "derivation": {
                "type": "per-frame-horizontal-mirror",
                "source_action": source_id,
                "source_candidate": selected,
                "temporal_order_preserved": True,
                "decision_note": args.note.strip(),
            },
            "frame_count": len(target_frames),
            "target_frame_size": {"width": frame_width, "height": frame_height},
            "anchor": target_action.get("anchor", "bottom-center"),
            "padding": None,
            "shared_scale": 1.0,
            "resampling": "none",
            "paste_clamped_frames": [],
            "source_frames": source_metrics,
            "output_frames": output_metrics,
        },
    )
    print(f"candidate_dir={candidate_dir}")
    print(f"source={source_id}:{selected}")
    print("temporal_order_preserved=true")


if __name__ == "__main__":
    main()
