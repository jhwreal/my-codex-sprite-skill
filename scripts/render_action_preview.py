#!/usr/bin/env python3
"""Render light/dark/checker QA views and a motion GIF for one candidate."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from _sprite_common import Image, ImageDraw, checkerboard, image_files, read_json, slugify


def background_for(kind: str, size: tuple[int, int]) -> Image.Image:
    if kind == "checker":
        return checkerboard(size)
    if kind == "light":
        return Image.new("RGBA", size, (250, 250, 248, 255))
    return Image.new("RGBA", size, (24, 28, 34, 255))


def main() -> None:
    parser = argparse.ArgumentParser(description="Render contact-sheet and GIF QA media.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--columns", type=int, default=0)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    action_id = slugify(args.action)
    candidate_id = slugify(args.candidate)
    action_dir = run_dir / "actions" / action_id
    action = read_json(action_dir / "action.json")
    candidate_dir = action_dir / "candidates" / candidate_id
    frames = image_files(candidate_dir / "frames")
    if not frames:
        raise SystemExit("No normalized frames were found. Run process_action_sheet.py first.")
    images = [Image.open(path).convert("RGBA") for path in frames]
    width = max(image.width for image in images)
    height = max(image.height for image in images)
    columns = args.columns if args.columns > 0 else min(len(images), 6)
    rows_per_background = math.ceil(len(images) / columns)
    label_width = 74
    header_height = 30
    gap = 8
    group_gap = 16
    sheet_width = label_width + columns * width + max(0, columns - 1) * gap
    group_height = rows_per_background * height + max(0, rows_per_background - 1) * gap
    sheet_height = header_height + 3 * group_height + 2 * group_gap
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (34, 38, 44, 255))
    draw = ImageDraw.Draw(sheet)
    qc_path = candidate_dir / "qc.json"
    qc_status = read_json(qc_path).get("status", "not-run") if qc_path.exists() else "not-run"
    draw.text((8, 8), f"{action_id} / {candidate_id} / QC {qc_status}", fill=(245, 247, 249, 255))

    top = header_height
    for kind in ("checker", "light", "dark"):
        draw.text((8, top + 8), kind, fill=(245, 247, 249, 255))
        for index, image in enumerate(images):
            row, column = divmod(index, columns)
            left = label_width + column * (width + gap)
            frame_top = top + row * (height + gap)
            cell = background_for(kind, (width, height))
            cell.alpha_composite(image, ((width - image.width) // 2, (height - image.height) // 2))
            sheet.alpha_composite(cell, (left, frame_top))
            draw.text((left + 4, frame_top + 4), str(index + 1), fill=(235, 82, 82, 255))
        top += group_height + group_gap

    qa_dir = candidate_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    contact_path = qa_dir / "contact-sheet.png"
    sheet.save(contact_path)

    gif_frames: list[Image.Image] = []
    for image in images:
        canvas = checkerboard((width, height), max(4, min(width, height) // 8))
        canvas.alpha_composite(image, ((width - image.width) // 2, (height - image.height) // 2))
        gif_frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
    duration = max(1, int(round(1000 / float(action["fps"]))))
    gif_path = qa_dir / "preview.gif"
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=[duration] * len(gif_frames),
        loop=0 if action.get("loop") else 1,
        disposal=2,
    )
    print(f"contact_sheet={contact_path}")
    print(f"preview={gif_path}")


if __name__ == "__main__":
    main()
