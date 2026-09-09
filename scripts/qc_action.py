#!/usr/bin/env python3
"""Compute deterministic gates and motion heuristics for one action candidate."""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path
from typing import Any

from _sprite_common import (
    Image,
    candidate_digest,
    alpha_difference_ratio,
    edge_alpha_count,
    image_files,
    mean,
    read_json,
    slugify,
    transparent_rgb_residue_count,
    visible_pixel_count,
    write_json,
)


def coefficient_of_variation(values: list[float]) -> float:
    average = mean(values)
    if average == 0 or len(values) < 2:
        return 0.0
    return statistics.pstdev(values) / average


def main() -> None:
    parser = argparse.ArgumentParser(description="Run programmatic QC on one processed action candidate.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--min-visible-pixels", type=int, default=32)
    parser.add_argument("--body-scale-cv-max", type=float)
    parser.add_argument("--anchor-y-std-max", type=float)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    action_id = slugify(args.action)
    candidate_id = slugify(args.candidate)
    run = read_json(run_dir / "run.json")
    action_dir = run_dir / "actions" / action_id
    action = read_json(action_dir / "action.json")
    candidate_dir = action_dir / "candidates" / candidate_id
    current_digest = candidate_digest(candidate_dir, run_dir, run, action)
    processing = read_json(candidate_dir / "processing.json")
    frames = image_files(candidate_dir / "frames")
    if not frames:
        raise SystemExit("No normalized frames were found. Run process_action_sheet.py first.")
    images = [Image.open(path).convert("RGBA") for path in frames]

    expected = int(action["frame_count"])
    edge_margin = int(run.get("qc", {}).get("edge_margin", 1))
    body_scale_limit = float(
        args.body_scale_cv_max
        if args.body_scale_cv_max is not None
        else run.get("qc", {}).get("body_scale_cv_max", 0.10)
    )
    anchor_limit = float(
        args.anchor_y_std_max
        if args.anchor_y_std_max is not None
        else run.get("qc", {}).get("anchor_y_std_max", 0.05)
    )

    empty_frames = [index + 1 for index, image in enumerate(images) if visible_pixel_count(image) < args.min_visible_pixels]
    edge_touch_frames = [
        index + 1 for index, image in enumerate(images) if edge_alpha_count(image, edge_margin) > 0
    ]
    residue_counts = [transparent_rgb_residue_count(image) for image in images]
    residue_total = sum(residue_counts)
    clamped_frames = list(processing.get("paste_clamped_frames", []))

    source_frames = [item for item in processing.get("source_frames", []) if item.get("bbox")]
    scale_extents = [math.sqrt(float(item["bbox_area"])) for item in source_frames]
    body_scale_cv = coefficient_of_variation(scale_extents)
    anchor_values = [float(item["normalized_anchor_y"]) for item in source_frames]
    anchor_y_std = statistics.pstdev(anchor_values) if len(anchor_values) > 1 else 0.0
    center_values = [float(item["normalized_center_x"]) for item in source_frames]
    center_x_std = statistics.pstdev(center_values) if len(center_values) > 1 else 0.0

    consecutive_differences = [
        alpha_difference_ratio(images[index], images[index + 1]) for index in range(max(0, len(images) - 1))
    ]
    if action.get("loop") and len(images) > 1:
        consecutive_differences.append(alpha_difference_ratio(images[-1], images[0]))
    motion_score = mean(consecutive_differences)
    first_last_difference = alpha_difference_ratio(images[0], images[-1]) if len(images) > 1 else 0.0

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    profile = action.get("qc_profile", "grounded")
    if processing.get("source_edge_frames"):
        errors.append({"code": "source-slot-clipping", "frames": processing["source_edge_frames"]})
    if processing.get("unused_content_slots"):
        errors.append({"code": "content-in-unused-slots", "slots": processing["unused_content_slots"]})
    if processing.get("placement_mode", "legacy-fit") == "legacy-fit":
        warnings.append({"code": "legacy-action-fit", "message": "Per-action fitting does not preserve cross-action scale or source displacement."})
    if len(frames) != expected:
        errors.append({"code": "frame-count", "message": f"Expected {expected} frames; found {len(frames)}."})
    if empty_frames:
        errors.append({"code": "empty-frames", "frames": empty_frames})
    if edge_touch_frames:
        errors.append({"code": "edge-touch", "frames": edge_touch_frames})
    if clamped_frames:
        errors.append({"code": "paste-clamped", "frames": clamped_frames})
    if residue_total:
        errors.append({"code": "transparent-rgb-residue", "pixels": residue_total})
    # Bounding boxes include weapons and pose deformation, so they cannot prove body-scale drift.
    if profile != "deforming" and body_scale_cv > body_scale_limit:
        warnings.append({"code": "silhouette-extent-change", "value": body_scale_cv, "limit": body_scale_limit})
    if profile == "grounded" and anchor_y_std > anchor_limit:
        warnings.append({"code": "ground-contact-review", "value": anchor_y_std, "limit": anchor_limit})
    if len(images) > 1 and motion_score <= 0.005:
        warnings.append({"code": "near-static-animation", "value": motion_score})
    if profile == "grounded" and center_x_std > 0.12:
        warnings.append({"code": "source-center-x-drift", "value": center_x_std})

    status = "fail" if errors else "review" if warnings else "pass"
    result = {
        "schema_version": 2,
        "candidate_digest": current_digest,
        "qc_profile": profile,
        "status": status,
        "action": action_id,
        "candidate": candidate_id,
        "metrics": {
            "expected_frame_count": expected,
            "frame_count": len(frames),
            "empty_frames": empty_frames,
            "edge_touch_frames": edge_touch_frames,
            "paste_clamped_frames": clamped_frames,
            "transparent_rgb_residue_pixels": residue_total,
            "body_scale_cv": body_scale_cv,
            "normalized_anchor_y_std": anchor_y_std,
            "normalized_center_x_std": center_x_std,
            "motion_score": motion_score,
            "first_last_alpha_difference": first_last_difference,
        },
        "thresholds": {
            "min_visible_pixels": args.min_visible_pixels,
            "edge_margin": edge_margin,
            "body_scale_cv_max": body_scale_limit,
            "normalized_anchor_y_std_max": anchor_limit,
        },
        "errors": errors,
        "warnings": warnings,
        "visual_review_required": True,
    }
    write_json(candidate_dir / "qc.json", result)
    print(f"status={status}")
    print(f"qc={candidate_dir / 'qc.json'}")
    print(f"body_scale_cv={body_scale_cv:.6f}")
    print(f"normalized_anchor_y_std={anchor_y_std:.6f}")
    print(f"motion_score={motion_score:.6f}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
