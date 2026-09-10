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
    has_useful_transparency,
    output_pivot,
    edge_alpha_count,
    input_fingerprint,
    seal_processing,
    invalidate_selection,
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
    parser.add_argument("--prompt-file", help="Exact issued generation prompt; defaults to the action prompt template.")
    parser.add_argument("--already-transparent", action="store_true")
    parser.add_argument("--remove-chroma", action="store_true", help="Explicitly remove a deliberately generated flat matte.")
    parser.add_argument("--padding", type=int, default=4)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.alpha_threshold < 255:
        raise SystemExit("--alpha-threshold must be between 0 and 254.")

    run_dir = Path(args.run_dir).expanduser().resolve()
    run = read_json(run_dir / "run.json")
    action_id = slugify(args.action)
    find_action(run, action_id)
    action = read_json(run_dir / "actions" / action_id / "action.json")
    input_fingerprint(run_dir, run, action)
    if not run["character"].get("master_approved"):
        raise SystemExit("The run has no approved canonical master.")
    prompt = Path(args.prompt_file).expanduser().resolve() if args.prompt_file else run_dir / "actions" / action_id / "prompt.md"
    if not prompt.is_file():
        raise SystemExit(f"Prompt file does not exist: {prompt}")
    source_path = Path(args.input).expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"Input candidate does not exist: {source_path}")
    candidate_id = slugify(args.candidate)
    candidate_dir = run_dir / "actions" / action_id / "candidates" / candidate_id
    if candidate_dir.exists() and any(candidate_dir.iterdir()) and not args.force:
        raise SystemExit(f"Candidate directory already contains files: {candidate_dir}")
    if action.get("selected_candidate") == candidate_id:
        invalidate_selection(run_dir, run, action)
    if args.force and candidate_dir.is_dir():
        for name in ("frames", "qa"):
            if (candidate_dir / name).is_dir():
                shutil.rmtree(candidate_dir / name)
        for name in ("qc.json", "processing.json", "derivation-note.md"):
            (candidate_dir / name).unlink(missing_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = candidate_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    source_copy = candidate_dir / "source.png"
    Image.open(source_path).convert("RGBA").save(source_copy)
    source_image = Image.open(source_copy).convert("RGBA")
    transparent_path = candidate_dir / "transparent-source.png"
    if args.already_transparent and not has_useful_transparency(source_image):
        raise SystemExit("--already-transparent requires a real transparent background.")
    if has_useful_transparency(source_image):
        clear_transparent_rgb(source_image).save(transparent_path)
        chroma_removed = False
    else:
        if run.get("background_mode", "chroma") != "chroma" and not args.remove_chroma:
            raise SystemExit("Expected real alpha. Repair the background of this exact sheet while preserving its motion; use --remove-chroma only for a deliberate flat matte.")
        remove_chroma(source_copy, transparent_path, run["chroma_key"])
        transparent = clear_transparent_rgb(Image.open(transparent_path).convert("RGBA"))
        transparent.save(transparent_path)
        chroma_removed = True

    transparent = Image.open(transparent_path).convert("RGBA")
    columns = int(action["source_layout"]["columns"])
    rows = int(action["source_layout"]["rows"])
    frame_count = int(action["frame_count"])
    placement_mode = run["output"].get("placement", "legacy-fit")
    if placement_mode == "fixed" and (transparent.width % columns or transparent.height % rows
                                     or transparent.width // columns != transparent.height // rows):
        raise SystemExit("Fixed placement requires equal square source slots and exactly divisible grid dimensions.")
    all_slots = split_grid(transparent, columns, rows)
    unused_content = [i + 1 for i, slot in enumerate(all_slots) if i >= frame_count and alpha_bbox(slot)]
    slots = all_slots[:frame_count]
    source_edge_frames = [i + 1 for i, slot in enumerate(slots) if edge_alpha_count(slot, 1, args.alpha_threshold)]
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
    if placement_mode == "fixed":
        scale = min(target_width / slots[0].width, target_height / slots[0].height)
    pivot = output_pivot(run)
    source_pivot = run["output"].get("source_pivot", [0.5, 0.82])
    resampling = Image.Resampling.NEAREST if run["character"].get("pixel_art") else Image.Resampling.LANCZOS
    output_frames: list[Image.Image] = []
    output_metrics: list[dict[str, Any]] = []
    clamped_frames: list[int] = []
    for index, content in enumerate(contents, start=1):
        if placement_mode == "fixed":
            slot = slots[index - 1]
            width, height = round(slot.width * scale), round(slot.height * scale)
            resized = slot.resize((width, height), resampling)
            left = round(pivot[0] - source_pivot[0] * width)
            top = round(pivot[1] - source_pivot[1] * height)
            bbox = alpha_bbox(resized, args.alpha_threshold)
            clamped = bool(bbox and (bbox[0] + left < 0 or bbox[1] + top < 0
                                    or bbox[2] + left > target_width or bbox[3] + top > target_height))
            frame = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
            frame.alpha_composite(resized, (left, top))
            frame = clear_transparent_rgb(frame)
            placement = {"left": left, "top": top, "width": width, "height": height}
        else:
            frame, clamped, placement = compose_frame(
                content, (target_width, target_height), scale, args.padding,
                action.get("anchor", run["output"].get("anchor", "bottom-center")), resampling,
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

    if prompt.resolve() != (candidate_dir / "prompt-used.md").resolve():
        shutil.copy2(prompt, candidate_dir / "prompt-used.md")
    processing = {
        "schema_version": 1,
        "processed_at": utc_now(),
        "action": action_id,
        "candidate": candidate_id,
        "source_path": str(source_path),
        "prompt_origin": "issued-prompt-file" if args.prompt_file else "action-template-unverified",
        "source_copy": "source.png",
        "transparent_source": "transparent-source.png",
        "chroma_removed": chroma_removed,
        "placement_mode": placement_mode,
        "pivot": list(pivot),
        "source_edge_frames": source_edge_frames,
        "unused_content_slots": unused_content,
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
    seal_processing(candidate_dir, run_dir, run, action)
    print(f"candidate_dir={candidate_dir}")
    print(f"frames={frame_count}")
    print(f"shared_scale={scale:.6f}")
    print("paste_clamped_frames=" + (",".join(map(str, clamped_frames)) if clamped_frames else "none"))


if __name__ == "__main__":
    main()
