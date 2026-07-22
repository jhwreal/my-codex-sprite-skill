#!/usr/bin/env python3
"""Shared utilities for the my-codex-sprite-skill deterministic pipeline."""

from __future__ import annotations

import json
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
        [item for item in path.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES],
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
    if fps <= 0 or fps > 120:
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
