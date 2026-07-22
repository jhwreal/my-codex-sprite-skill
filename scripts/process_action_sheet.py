#!/usr/bin/env python3
"""Remove chroma, split a declared grid, and normalize frames with shared geometry."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from _sprite_common import (
    Image,
    alpha_bbox,
    clear_transparent_rgb,
    read_json,
    slugify,
    transparent_rgb_residue_count,
    visible_pixel_count,
    write_json,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def find_action(run: dict[str, Any], action_id: str) -> dict[str, Any]:
    for action in run.get("actions", []):
        if action.get("id") == action_id:
            return action
    raise SystemExit(f"Unknown action: {action_id}")


def has_useful_transparency(image: Image.Image) -> bool:
    alpha_min, alpha_max = image.convert("RGBA").getchannel("A").getextrema()
    return alpha_min < 250 and alpha_max > 8


def imagegen_chroma_helper() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    helper = codex_home / "skills" / ".system" / "imagegen" / "scripts" / "remove_chroma_key.py"
    if not helper.is_file():
        raise SystemExit(
            "The installed $imagegen chroma-key helper was not found at "
            f"{helper}. Load/install the system imagegen skill before processing opaque output."
        )
    return helper


def remove_chroma(source: Path, output: Path, key: str) -> None:
    command = [
        sys.executable,
        str(imagegen_chroma_helper()),
        "--input",
        str(source),
        "--out",
        str(output),
        "--key-color",
        key,
        "--auto-key",
        "border",
        "--soft-matte",
        "--transparent-threshold",
        "12",
        "--opaque-threshold",
        "220",
        "--despill",
        "--force",
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"Chroma-key removal failed: {detail}")


def split_grid(image: Image.Image, columns: int, rows: int) -> list[Image.Image]:
    slots: list[Image.Image] = []
    for row in range(rows):
        for column in range(columns):
            left = round(column * image.width / columns)
            right = round((column + 1) * image.width / columns)
            top = round(row * image.height / rows)
            bottom = round((row + 1) * image.height / rows)
            slots.append(image.crop((left, top, right, bottom)))
    return slots


def source_metric(index: int, slot: Image.Image, bbox: tuple[int, int, int, int] | None) -> dict[str, Any]:
    metric: dict[str, Any] = {
        "index": index,
        "slot_width": slot.width,
        "slot_height": slot.height,
        "visible_pixels": visible_pixel_count(slot),
    }
    if bbox is None:
        metric["bbox"] = None
        return metric
    left, top, right, bottom = bbox
    metric.update(
        {
            "bbox": [left, top, right, bottom],
            "bbox_width": right - left,
            "bbox_height": bottom - top,
            "bbox_area": (right - left) * (bottom - top),
            "normalized_center_x": ((left + right) / 2) / slot.width,
            "normalized_anchor_y": bottom / slot.height,
        }
    )
    return metric


def compose_frame(
    content: Image.Image,
    target_size: tuple[int, int],
    scale: float,
    padding: int,
    anchor: str,
    resampling: Image.Resampling,
) -> tuple[Image.Image, bool, dict[str, int]]:
    target_width, target_height = target_size
    width = max(1, int(round(content.width * scale)))
    height = max(1, int(round(content.height * scale)))
    resized = content.resize((width, height), resampling)
    if anchor == "center":
        left = (target_width - width) // 2
        top = (target_height - height) // 2
    else:
        left = (target_width - width) // 2
        top = target_height - padding - height
    clamped = left < 0 or top < 0 or left + width > target_width or top + height > target_height
    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    canvas.alpha_composite(resized, (left, top))
    canvas = clear_transparent_rgb(canvas)
    return canvas, clamped, {"left": left, "top": top, "width": width, "height": height}


def main() -> None:
    parser = argparse.ArgumentParser(description="Process one generated action sheet candidate.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--already-transparent", action="store_true")
    parser.add_argument("--padding", type=int, default=4)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    run = read_json(run_dir / "run.json")
    action_id = slugify(args.action)
    action = find_action(run, action_id)
    if not run["character"].get("master_approved"):
        raise SystemExit("The run has no approved canonical master.")
    source_path = Path(args.input).expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"Input candidate does not exist: {source_path}")
    candidate_id = slugify(args.candidate)
    candidate_dir = run_dir / "actions" / action_id / "candidates" / candidate_id
    if candidate_dir.exists() and any(candidate_dir.iterdir()) and not args.force:
        raise SystemExit(f"Candidate directory already contains files: {candidate_dir}")
    candidate_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = candidate_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    source_copy = candidate_dir / "source.png"
    Image.open(source_path).convert("RGBA").save(source_copy)
    source_image = Image.open(source_copy).convert("RGBA")
    transparent_path = candidate_dir / "transparent-source.png"
    if args.already_transparent or has_useful_transparency(source_image):
        clear_transparent_rgb(source_image).save(transparent_path)
        chroma_removed = False
    else:
        remove_chroma(source_copy, transparent_path, run["chroma_key"])
        transparent = clear_transparent_rgb(Image.open(transparent_path).convert("RGBA"))
        transparent.save(transparent_path)
        chroma_removed = True

    transparent = Image.open(transparent_path).convert("RGBA")
    columns = int(action["source_layout"]["columns"])
    rows = int(action["source_layout"]["rows"])
    frame_count = int(action["frame_count"])
    slots = split_grid(transparent, columns, rows)[:frame_count]
    bboxes = [alpha_bbox(slot, args.alpha_threshold) for slot in slots]
    source_metrics = [source_metric(index + 1, slot, bbox) for index, (slot, bbox) in enumerate(zip(slots, bboxes))]
    empty = [index + 1 for index, bbox in enumerate(bboxes) if bbox is None]
    if empty:
        raise SystemExit(f"No sprite content detected in source slots: {empty}")
    contents = [slot.crop(bbox) for slot, bbox in zip(slots, bboxes) if bbox is not None]

    target_width = int(run["output"]["frame_width"])
    target_height = int(run["output"]["frame_height"])
    if args.padding < 0 or args.padding * 2 >= min(target_width, target_height):
        raise SystemExit("--padding must leave positive content space in the target frame.")
    max_width = max(content.width for content in contents)
    max_height = max(content.height for content in contents)
    scale = min(
        (target_width - 2 * args.padding) / max_width,
        (target_height - 2 * args.padding) / max_height,
    )
    resampling = Image.Resampling.NEAREST if run["character"].get("pixel_art") else Image.Resampling.LANCZOS
    output_frames: list[Image.Image] = []
    output_metrics: list[dict[str, Any]] = []
    clamped_frames: list[int] = []
    for index, content in enumerate(contents, start=1):
        frame, clamped, placement = compose_frame(
            content,
            (target_width, target_height),
            scale,
            args.padding,
            action.get("anchor", run["output"].get("anchor", "bottom-center")),
            resampling,
        )
        if clamped:
            clamped_frames.append(index)
        path = frames_dir / f"{index:04d}.png"
        frame.save(path)
        output_metrics.append(
            {
                "index": index,
                "file": str(path.relative_to(candidate_dir)),
                "visible_pixels": visible_pixel_count(frame),
                "transparent_rgb_residue_pixels": transparent_rgb_residue_count(frame),
                "placement": placement,
            }
        )
        output_frames.append(frame)

    sheet = Image.new("RGBA", (target_width * frame_count, target_height), (0, 0, 0, 0))
    for index, frame in enumerate(output_frames):
        sheet.alpha_composite(frame, (index * target_width, 0))
    sheet = clear_transparent_rgb(sheet)
    sheet.save(candidate_dir / "sheet.png")

    prompt = run_dir / "actions" / action_id / "prompt.md"
    if prompt.is_file():
        shutil.copy2(prompt, candidate_dir / "prompt-used.md")
    processing = {
        "schema_version": 1,
        "processed_at": utc_now(),
        "action": action_id,
        "candidate": candidate_id,
        "source_path": str(source_path),
        "source_copy": "source.png",
        "transparent_source": "transparent-source.png",
        "chroma_removed": chroma_removed,
        "chroma_key": run["chroma_key"],
        "source_layout": {"columns": columns, "rows": rows},
        "frame_count": frame_count,
        "target_frame_size": {"width": target_width, "height": target_height},
        "anchor": action.get("anchor", run["output"].get("anchor", "bottom-center")),
        "padding": args.padding,
        "shared_scale": scale,
        "resampling": "nearest" if run["character"].get("pixel_art") else "lanczos",
        "paste_clamped_frames": clamped_frames,
        "source_frames": source_metrics,
        "output_frames": output_metrics,
    }
    write_json(candidate_dir / "processing.json", processing)
    print(f"candidate_dir={candidate_dir}")
    print(f"frames={frame_count}")
    print(f"shared_scale={scale:.6f}")
    print("paste_clamped_frames=" + (",".join(map(str, clamped_frames)) if clamped_frames else "none"))


if __name__ == "__main__":
    main()
