#!/usr/bin/env python3
"""Shared utilities for the my-codex-sprite-skill deterministic pipeline."""

from __future__ import annotations

import json
import hashlib
import math
import re
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Use the project-selected or Codex bundled Python, "
        "or install Pillow after obtaining user approval."
    ) from exc


NUMBER_RE = re.compile(r"(\d+)")
IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}


def pixel_data(image: Image.Image):
    """Return flattened pixels across supported Pillow versions."""
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter is not None else image.getdata()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    if not value:
        raise ValueError("A non-empty name is required.")
    return value


def natural_key(path: Path) -> list[int | str]:
    parts: list[int | str] = []
    for chunk in NUMBER_RE.split(path.stem):
        if not chunk:
            continue
        parts.append(int(chunk) if chunk.isdigit() else chunk.lower())
    parts.append(path.suffix.lower())
    return parts


def image_files(path: Path) -> list[Path]:
    return sorted(
        [item for item in path.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES],
        key=natural_key,
    )


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def parse_hex_color(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raise ValueError(f"Invalid color {value!r}; expected #RRGGBB.")
    return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def color_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in rgb)


def default_layout(frame_count: int) -> tuple[int, int]:
    if frame_count < 1:
        raise ValueError("Frame count must be positive.")
    presets = {
        1: (1, 1),
        2: (2, 1),
        3: (3, 1),
        4: (2, 2),
        5: (3, 2),
        6: (3, 2),
        7: (4, 2),
        8: (4, 2),
        9: (3, 3),
    }
    if frame_count in presets:
        return presets[frame_count]
    columns = min(6, max(2, math.ceil(math.sqrt(frame_count))))
    return columns, math.ceil(frame_count / columns)


def parse_action_spec(raw: str) -> dict[str, Any]:
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) not in {4, 5}:
        raise ValueError(
            f"Invalid action {raw!r}; expected name:frames:fps:loop|once[:columnsxrows]."
        )
    name = slugify(parts[0])
    frame_count = int(parts[1])
    fps = float(parts[2])
    if frame_count < 1 or frame_count > 32:
        raise ValueError("Action frame count must be between 1 and 32.")
    if not math.isfinite(fps) or fps <= 0 or fps > 120:
        raise ValueError("Action FPS must be greater than 0 and no more than 120.")
    loop_token = parts[3].lower()
    if loop_token not in {"loop", "once"}:
        raise ValueError("Action loop mode must be 'loop' or 'once'.")
    if len(parts) == 5:
        match = re.fullmatch(r"(\d+)x(\d+)", parts[4].lower())
        if not match:
            raise ValueError(f"Invalid layout {parts[4]!r}; expected columnsxrows.")
        columns, rows = int(match.group(1)), int(match.group(2))
    else:
        columns, rows = default_layout(frame_count)
    if columns < 1 or rows < 1 or columns * rows < frame_count:
        raise ValueError("Source layout must contain at least as many slots as frames.")
    return {
        "id": name,
        "display_name": parts[0].strip(),
        "frame_count": frame_count,
        "fps": fps,
        "loop": loop_token == "loop",
        "source_layout": {"columns": columns, "rows": rows},
    }


def alpha_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A").point(lambda value: 255 if value > threshold else 0)
    return alpha.getbbox()


def visible_pixel_count(image: Image.Image, threshold: int = 8) -> int:
    return sum(1 for value in pixel_data(image.getchannel("A")) if value > threshold)


def transparent_rgb_residue_count(image: Image.Image) -> int:
    return sum(1 for red, green, blue, alpha in pixel_data(image) if alpha == 0 and (red or green or blue))


def clear_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = [
        (0, 0, 0, 0) if alpha == 0 else (red, green, blue, alpha)
        for red, green, blue, alpha in pixel_data(rgba)
    ]
    rgba.putdata(pixels)
    return rgba


def edge_alpha_count(image: Image.Image, margin: int = 1, threshold: int = 8) -> int:
    if margin < 1:
        return 0
    alpha = image.getchannel("A")
    width, height = image.size
    count = 0
    for y in range(height):
        for x in range(width):
            if x < margin or y < margin or x >= width - margin or y >= height - margin:
                if alpha.getpixel((x, y)) > threshold:
                    count += 1
    return count


def alpha_difference_ratio(left: Image.Image, right: Image.Image, threshold: int = 8) -> float:
    if left.size != right.size:
        raise ValueError("Images must have the same dimensions for alpha comparison.")
    left_alpha = pixel_data(left.getchannel("A"))
    right_alpha = pixel_data(right.getchannel("A"))
    difference = 0
    union = 0
    for left_value, right_value in zip(left_alpha, right_alpha):
        left_on = left_value > threshold
        right_on = right_value > threshold
        union += int(left_on or right_on)
        difference += int(left_on != right_on)
    return difference / union if union else 0.0


def checkerboard(size: tuple[int, int], tile: int = 16) -> Image.Image:
    image = Image.new("RGBA", size, (238, 241, 244, 255))
    draw = ImageDraw.Draw(image)
    colors = ((238, 241, 244, 255), (214, 220, 226, 255))
    for top in range(0, size[1], tile):
        for left in range(0, size[0], tile):
            color = colors[((left // tile) + (top // tile)) % 2]
            draw.rectangle((left, top, left + tile - 1, top + tile - 1), fill=color)
    return image


def composite_on(image: Image.Image, background: tuple[int, int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", image.size, background)
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


# Versioned, local evidence. Never include credentials or provider responses.
PIPELINE_VERSION = 2
ACTION_FIELDS = ("id", "frame_count", "fps", "loop", "source_layout", "anchor",
                 "durations_ms", "phases", "contacts", "events", "qc_profile")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def durations_ms(action: dict[str, Any]) -> list[float]:
    count = int(action["frame_count"])
    fps = float(action["fps"])
    if not math.isfinite(fps) or not 0 < fps <= 120:
        raise SystemExit("FPS must be finite and in (0, 120].")
    values = action.get("durations_ms", [1000 / fps] * count)
    if not isinstance(values, list) or len(values) != count:
        raise SystemExit("durations_ms must contain exactly one duration per frame.")
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or v <= 0 for v in values):
        raise SystemExit("Frame durations must be positive finite milliseconds.")
    return [float(v) for v in values]


def validate_action_config(action: dict[str, Any]) -> None:
    durations_ms(action)
    count = int(action["frame_count"])
    layout = action["source_layout"]
    if (type(layout.get("columns")) is not int or type(layout.get("rows")) is not int
            or layout["columns"] < 1 or layout["rows"] < 1 or layout["columns"] * layout["rows"] < count
            or not 1 <= count <= 32):
        raise SystemExit("Action needs a positive grid with enough slots for 1-32 frames.")
    if action.get("qc_profile", "grounded") not in {"grounded", "aerial", "deforming"}:
        raise SystemExit("qc_profile must be grounded, aerial, or deforming.")
    for key in ("phases", "contacts"):
        if key in action and (not isinstance(action[key], list) or len(action[key]) != count
                              or any(not isinstance(v, str) or not v.strip() for v in action[key])):
            raise SystemExit(f"{key} must contain one non-empty string per frame.")
    events = action.get("events", [])
    if not isinstance(events, list):
        raise SystemExit("events must be a list.")
    for event in events:
        if (not isinstance(event, dict) or set(event) != {"frame", "name"}
                or type(event["frame"]) is not int or not 1 <= event["frame"] <= count
                or not isinstance(event["name"], str) or not event["name"].strip()):
            raise SystemExit("Each event needs a 1-based frame and a non-empty name.")


def output_pivot(run: dict[str, Any]) -> tuple[float, float]:
    output = run["output"]
    w, h = int(output["frame_width"]), int(output["frame_height"])
    default_y = h / 2 if output.get("anchor") == "center" else h
    pivot = output.get("pivot", [w / 2, default_y])
    if (not isinstance(pivot, list) or len(pivot) != 2
            or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in pivot)
            or not 0 <= pivot[0] <= w or not 0 <= pivot[1] <= h):
        raise SystemExit("Output pivot must be finite x,y coordinates inside the frame.")
    return float(pivot[0]), float(pivot[1])


def has_useful_transparency(image: Image.Image) -> bool:
    # A single transparent pixel or translucent opaque backdrop is not a cutout.
    alpha = image.convert("RGBA").getchannel("A")
    histogram = alpha.histogram()
    return sum(histogram[:9]) >= max(1, math.ceil(image.width * image.height * 0.01)) and sum(histogram[9:]) > 0


def input_fingerprint(run_dir: Path, run: dict[str, Any], action: dict[str, Any]) -> str:
    validate_action_config(action)
    output_pivot(run)
    placement = run["output"].get("placement", "legacy-fit")
    if placement not in {"fixed", "legacy-fit"}:
        raise SystemExit("Placement must be fixed or legacy-fit.")
    root = run["output"].get("source_pivot", [0.5, 0.82])
    if (not isinstance(root, list) or len(root) != 2
            or any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in root)):
        raise SystemExit("Source pivot must contain two finite normalized coordinates in [0, 1].")
    master_file = run["character"].get("master_file")
    if not master_file or not run["character"].get("master_approved"):
        raise SystemExit("An approved canonical master is required.")
    master_hash = sha256_file(run_dir / master_file)
    expected = run["character"].get("master_sha256")
    if expected and expected != master_hash:
        raise SystemExit("Canonical master changed; attach and approve its replacement first.")
    action_dir = run_dir / "actions" / action["id"]
    refs = {}
    for path in sorted((action_dir / "references").glob("*.png")):
        refs[path.name] = sha256_file(path)
    for path in (action_dir / "prompt.md", run_dir / "character-spec.md"):
        if path.is_file():
            refs[str(path.relative_to(run_dir))] = sha256_file(path)
    return digest_json({"version": PIPELINE_VERSION, "master": master_hash,
                        "output": run["output"], "pixel_art": run["character"].get("pixel_art"),
                        "qc": run.get("qc", {}), "chroma_key": run.get("chroma_key"),
                        "background": run.get("background_mode", "chroma"),
                        "action": {k: action[k] for k in ACTION_FIELDS if k in action}, "refs": refs})


def artifact_hashes(candidate_dir: Path) -> dict[str, str]:
    paths = image_files(candidate_dir / "frames")
    for name in ("source.png", "transparent-source.png", "sheet.png", "prompt-used.md", "derivation-note.md"):
        if (candidate_dir / name).is_file():
            paths.append(candidate_dir / name)
    return {str(p.relative_to(candidate_dir)): sha256_file(p) for p in paths}


def seal_processing(candidate_dir: Path, run_dir: Path, run: dict[str, Any], action: dict[str, Any]) -> None:
    path = candidate_dir / "processing.json"
    processing = read_json(path)
    processing["schema_version"] = PIPELINE_VERSION
    processing["input_fingerprint"] = input_fingerprint(run_dir, run, action)
    processing["artifact_hashes"] = artifact_hashes(candidate_dir)
    write_json(path, processing)


def candidate_digest(candidate_dir: Path, run_dir: Path, run: dict[str, Any], action: dict[str, Any]) -> str:
    processing = read_json(candidate_dir / "processing.json")
    if processing.get("input_fingerprint") != input_fingerprint(run_dir, run, action):
        raise SystemExit("Candidate inputs changed or legacy evidence is unsigned; reprocess this candidate.")
    artifacts = artifact_hashes(candidate_dir)
    if processing.get("artifact_hashes") != artifacts:
        raise SystemExit("Candidate artifacts changed; reprocess before QC, review, or packaging.")
    if len(image_files(candidate_dir / "frames")) != int(action["frame_count"]):
        raise SystemExit("Candidate frame count does not match the action.")
    return digest_json({"processing": sha256_file(candidate_dir / "processing.json"), "artifacts": artifacts})


def review_evidence(candidate_dir: Path, run_dir: Path, run: dict[str, Any], action: dict[str, Any]) -> dict[str, str]:
    current = candidate_digest(candidate_dir, run_dir, run, action)
    qc = read_json(candidate_dir / "qc.json")
    if qc.get("candidate_digest") != current or qc.get("status") not in {"pass", "review"}:
        raise SystemExit("QC is failing or stale; run QC again.")
    preview = read_json(candidate_dir / "qa" / "preview.json")
    if preview.get("candidate_digest") != current:
        raise SystemExit("Preview is stale; render and inspect it again.")
    for name in ("contact-sheet.png", "preview.gif"):
        if preview.get("hashes", {}).get(name) != sha256_file(candidate_dir / "qa" / name):
            raise SystemExit("Preview artifacts changed; render and inspect them again.")
    return {"candidate_digest": current, "qc_sha256": sha256_file(candidate_dir / "qc.json"),
            "preview_sha256": sha256_file(candidate_dir / "qa" / "preview.json")}


def verify_approval(candidate_dir: Path, run_dir: Path, run: dict[str, Any], action: dict[str, Any]) -> None:
    evidence = review_evidence(candidate_dir, run_dir, run, action)
    approval = action.get("visual_review", {})
    if (action.get("status") != "approved" or action.get("selected_candidate") != candidate_dir.name
            or approval.get("evidence") != evidence):
        raise SystemExit("Approval is missing or stale; inspect and select this exact candidate again.")


def invalidate_selection(run_dir: Path, run: dict[str, Any], action: dict[str, Any]) -> None:
    action.pop("selected_candidate", None)
    action.pop("visual_review", None)
    action["status"] = "ready"
    write_json(run_dir / "actions" / action["id"] / "action.json", action)
    for index, summary in enumerate(run["actions"]):
        if summary["id"] == action["id"]:
            run["actions"][index] = dict(action)
    write_json(run_dir / "run.json", run)
