#!/usr/bin/env python3
"""Prepare or extend a canonical-master-driven sprite animation run."""

from __future__ import annotations

import argparse
import datetime as dt
import math
import shutil
import sys
from pathlib import Path
from typing import Any

from _sprite_common import (
    Image,
    ImageDraw,
    durations_ms,
    has_useful_transparency,
    sha256_file,
    validate_action_config,
    output_pivot,
    invalidate_selection,
    alpha_bbox,
    color_hex,
    parse_action_spec,
    parse_hex_color,
    pixel_data,
    read_json,
    slugify,
    write_json,
    write_text,
)


KEY_CANDIDATES = ["#00FF00", "#FF00FF", "#00FFFF", "#FFFF00", "#3F00FF"]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_mapping(values: list[str], flag_name: str) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(f"{flag_name} expects action=/absolute/path.")
        action, path = raw.split("=", 1)
        output[slugify(action)] = Path(path).expanduser().resolve()
    return output


def sample_opaque_colors(image: Image.Image, limit: int = 2048) -> list[tuple[int, int, int]]:
    opaque = [(r, g, b) for r, g, b, a in pixel_data(image.convert("RGBA")) if a > 200]
    if not opaque:
        return []
    step = max(1, len(opaque) // limit)
    return opaque[::step][:limit]


def choose_chroma_key(master: Image.Image | None, requested: str) -> str:
    if requested.lower() != "auto":
        return color_hex(parse_hex_color(requested))
    if master is None:
        return KEY_CANDIDATES[0]
    samples = sample_opaque_colors(master)
    if not samples:
        return KEY_CANDIDATES[0]
    best_key = KEY_CANDIDATES[0]
    best_score = -1.0
    for key in KEY_CANDIDATES:
        kr, kg, kb = parse_hex_color(key)
        distances = [math.sqrt((r - kr) ** 2 + (g - kg) ** 2 + (b - kb) ** 2) for r, g, b in samples]
        distances.sort()
        score = distances[max(0, int(len(distances) * 0.05) - 1)]
        if score > best_score:
            best_key, best_score = key, score
    return best_key


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    fill: tuple[int, int, int, int],
    dash: int = 10,
    gap: int = 7,
    width: int = 2,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    position = 0.0
    while position < length:
        segment_end = min(length, position + dash)
        draw.line(
            (
                x1 + dx * position,
                y1 + dy * position,
                x1 + dx * segment_end,
                y1 + dy * segment_end,
            ),
            fill=fill,
            width=width,
        )
        position += dash + gap


def create_layout_guide(path: Path, action: dict[str, Any], key: str, slot_size: int, source_pivot: list[float]) -> None:
    columns = int(action["source_layout"]["columns"])
    rows = int(action["source_layout"]["rows"])
    canvas = Image.new("RGBA", (columns * slot_size, rows * slot_size), (*parse_hex_color(key), 255))
    draw = ImageDraw.Draw(canvas)
    line = (255, 255, 255, 220)
    baseline = (24, 24, 24, 210)
    for index in range(columns * rows):
        column, row = index % columns, index // columns
        left, top = column * slot_size, row * slot_size
        right, bottom = left + slot_size - 1, top + slot_size - 1
        inset = max(12, slot_size // 12)
        draw_dashed_line(draw, (left + inset, top + inset), (right - inset, top + inset), line)
        draw_dashed_line(draw, (right - inset, top + inset), (right - inset, bottom - inset), line)
        draw_dashed_line(draw, (right - inset, bottom - inset), (left + inset, bottom - inset), line)
        draw_dashed_line(draw, (left + inset, bottom - inset), (left + inset, top + inset), line)
        foot_y = top + round(slot_size * source_pivot[1])
        draw_dashed_line(draw, (left + inset, foot_y), (right - inset, foot_y), baseline, dash=6, gap=5)
        label = f"{index + 1}" if index < int(action["frame_count"]) else "unused"
        draw.text((left + inset + 2, top + inset + 2), label, fill=baseline)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def create_anchor_sheet(
    path: Path,
    master: Image.Image,
    action: dict[str, Any],
    key: str,
    slot_size: int,
    pixel_art: bool,
    source_pivot: list[float],
    transparent: bool,
) -> None:
    columns = int(action["source_layout"]["columns"])
    rows = int(action["source_layout"]["rows"])
    canvas = Image.new("RGBA", (columns * slot_size, rows * slot_size), (*parse_hex_color(key), 255))
    if transparent:
        canvas = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bbox = alpha_bbox(master)
    if bbox is None:
        raise SystemExit("The canonical master contains no visible pixels.")
    cropped = master.crop(bbox)
    scale = min((slot_size * 0.62) / cropped.width, (slot_size * 0.62) / cropped.height)
    width = max(1, int(round(cropped.width * scale)))
    height = max(1, int(round(cropped.height * scale)))
    resampling = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    sprite = cropped.resize((width, height), resampling)
    for index in range(int(action["frame_count"])):
        column, row = index % columns, index // columns
        center_x = column * slot_size + round(slot_size * source_pivot[0])
        foot_y = row * slot_size + round(slot_size * source_pivot[1])
        canvas.alpha_composite(sprite, (center_x - width // 2, foot_y - (height // 2 if action.get("anchor") == "center" else height)))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def character_spec(name: str, view: str, style_notes: str) -> str:
    return f"""# Character specification

Character: {name}
Camera view: {view}
Style notes: {style_notes or 'Fill from the approved project art.'}

## Identity invariants

- Face and head shape:
- Head-to-body ratio and body proportions:
- Hair, fur, ears, horns, or silhouette:
- Outfit construction and palette:
- Markings, materials, outline, and lighting logic:
- Handedness and asymmetric details:
- Prop or weapon dimensions, grip, and side:
- Features that may deform during motion:
- Features that must never change:

## Production constraints

- Keep the declared camera view and facing convention.
- Keep the complete body and props inside every slot safety margin.
- Keep character-body animation separate from detached effects.
- Do not introduce text, scenery, guide marks, shadows, or new props.
"""


def background_prompt(run: dict[str, Any]) -> str:
    if run.get("background_mode", "chroma") == "transparent":
        return "genuine transparent alpha; no painted checkerboard, floor, shadows, or backdrop"
    return f"perfectly flat solid {run['chroma_key']}; no shadows, gradients, floor, or lighting variation"


def canonical_prompt(run: dict[str, Any]) -> str:
    return f"""Use case: stylized-concept
Asset type: canonical identity master for future 2D game sprite animation
Primary request: create one neutral full-body reference for {run['character']['name']}
Subject: use character-spec.md and any user reference art as the identity authority
Style/medium: {run['character']['style_notes'] or 'preserve the approved project style'}
Composition/framing: one complete centered character, {run['character']['view']} view, generous padding
Background: {background_prompt(run)}
Constraints: readable silhouette, stable proportions, neutral pose, complete limbs and props
Avoid: text, labels, scenery, cast or contact shadow, glow, motion blur, detached effects, watermark
"""


def action_prompt(run: dict[str, Any], action: dict[str, Any]) -> str:
    columns = action["source_layout"]["columns"]
    rows = action["source_layout"]["rows"]
    frame_count = action["frame_count"]
    loop_phrase = "a seamless loop" if action["loop"] else "a non-looping action with a stable final pose"
    pose_line = (
        "Pose guide: references/pose-guide.png is the temporal-pose authority."
        if action.get("pose_guide")
        else "Action beats: specify anticipation, contact, follow-through and recovery before generation."
    )
    frame_timing = durations_ms(action)
    timing = "\n".join(
        f"Frame {i + 1}: {action.get('phases', ['unspecified'] * frame_count)[i]}; "
        f"contact={action.get('contacts', ['unspecified'] * frame_count)[i]}; hold={frame_timing[i]:g}ms"
        for i in range(frame_count)
    )
    source_pivot = run["output"].get("source_pivot", [0.5, 0.82])
    return f"""Use case: identity-preserve
Asset type: candidate production action sheet for a 2D game character
Primary request: edit the supplied references into exactly {frame_count} temporal poses for {action['display_name']}; create {loop_phrase}
Input images:
- references/canonical-master.png — authoritative character identity
- references/anchor-sheet.png — authoritative body scale and neutral root; keep contacts or deliberate displacement from the motion plan
- references/layout-guide.png — optional construction-only layout; omit if redundant and never reproduce its marks
{pose_line}
{timing}
Spatial contract: fixed square slots; root at normalized {source_pivot}; preserve deliberate motion relative to this root. Do not recenter each pose.
Composition: exactly {columns}x{rows} slots in row-major temporal order; one complete isolated character in each of the first {frame_count} slots
Style/medium: {run['character']['style_notes'] or 'preserve the canonical master exactly'}
Background: {background_prompt(run)}
Constraints: same face, silhouette family, proportions, outfit, palette, materials, markings, handedness, prop design, view, apparent body scale as the canonical master; preserve grounded contacts and intentional airborne displacement
Avoid: text, labels, visible guide marks, scenery, duplicate characters, overlapping slots, cropped limbs, extra props, motion blur, afterimages, detached effects, cast or contact shadows, glow, watermark
"""


def create_action_files(
    run_dir: Path,
    run: dict[str, Any],
    action: dict[str, Any],
    pose_guides: dict[str, Path],
    master: Image.Image | None,
) -> None:
    action["anchor"] = run["output"]["anchor"]
    validate_action_config(action)
    action_dir = run_dir / "actions" / action["id"]
    references = action_dir / "references"
    references.mkdir(parents=True, exist_ok=True)
    (action_dir / "candidates").mkdir(parents=True, exist_ok=True)
    create_layout_guide(
        references / "layout-guide.png", action, run["chroma_key"], int(run["output"]["source_slot_size"]), run["output"].get("source_pivot", [0.5, 0.82])
    )
    pose = pose_guides.get(action["id"])
    if pose:
        if not pose.is_file():
            raise SystemExit(f"Pose guide does not exist: {pose}")
        target_pose = references / "pose-guide.png"
        if pose.resolve() != target_pose.resolve():
            shutil.copy2(pose, target_pose)
        action["pose_guide"] = "references/pose-guide.png"
    if master is not None:
        create_anchor_sheet(
            references / "anchor-sheet.png",
            master,
            action,
            run["chroma_key"],
            int(run["output"]["source_slot_size"]),
            bool(run["character"]["pixel_art"]),
            run["output"].get("source_pivot", [0.5, 0.82]),
            run.get("background_mode", "chroma") == "transparent",
        )
        action["status"] = "ready"
    else:
        action["status"] = "blocked-on-master"
    action["anchor"] = run["output"]["anchor"]
    action["frame_size"] = {
        "width": run["output"]["frame_width"],
        "height": run["output"]["frame_height"],
    }
    action["candidate_count"] = run["output"]["candidate_count"]
    action["updated_at"] = utc_now()
    write_json(action_dir / "action.json", action)
    write_text(action_dir / "prompt.md", action_prompt(run, action))


def validate_master(path: Path) -> Image.Image:
    if not path.is_file():
        raise SystemExit(f"Canonical master does not exist: {path}")
    master = Image.open(path).convert("RGBA")
    if alpha_bbox(master) is None:
        raise SystemExit("Canonical master has no visible pixels.")
    if not has_useful_transparency(master):
        raise SystemExit(
            "Canonical master lacks a meaningful transparent background. Request real alpha or remove a deliberate matte through the installed "
            "$imagegen chroma-key helper before attaching it."
        )
    return master


def attach_master(
    run_dir: Path,
    run: dict[str, Any],
    master_path: Path,
    approved: bool,
    replace: bool,
) -> dict[str, Any]:
    if not approved:
        raise SystemExit("Attaching a canonical master requires --approve-master.")
    master = validate_master(master_path)
    target = run_dir / "references" / "canonical-master.png"
    if target.exists() and not replace:
        existing_image = Image.open(target).convert("RGBA")
        same_pixels = existing_image.size == master.size and existing_image.tobytes() == master.tobytes()
        recorded_hash = run["character"].get("master_sha256")
        if not same_pixels or (recorded_hash and recorded_hash != sha256_file(target)):
            raise SystemExit(
                "A canonical master is already attached. Use --replace-master only after explicit approval; "
                "all selected actions will be invalidated."
            )
    if target.exists() and not replace and run["character"].get("master_sha256") == sha256_file(target):
        return run
    target.parent.mkdir(parents=True, exist_ok=True)
    master.save(target)
    run["chroma_key"] = choose_chroma_key(master, run.get("requested_chroma_key", "auto"))
    run["character"]["master_file"] = "references/canonical-master.png"
    run["character"]["master_approved"] = True
    run["character"]["master_sha256"] = sha256_file(target)
    run["character"]["master_approved_at"] = utc_now()
    run["status"] = "ready"
    pose_guides: dict[str, Path] = {}
    for action in run["actions"]:
        action_path = run_dir / "actions" / action["id"] / "action.json"
        if action_path.exists():
            prior = read_json(action_path)
            if prior.get("pose_guide"):
                pose_guides[action["id"]] = run_dir / "actions" / action["id"] / prior["pose_guide"]
        if replace:
            action.pop("selected_candidate", None)
            action.pop("visual_review", None)
        create_action_files(run_dir, run, action, pose_guides, master)
    run["updated_at"] = utc_now()
    write_json(run_dir / "run.json", run)
    write_text(run_dir / "prompts" / "canonical-master.md", canonical_prompt(run))
    return run


def create_new_run(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    if not args.character_name:
        raise SystemExit("--character-name is required when creating a new run.")
    if run_dir.exists() and any(run_dir.iterdir()) and not args.force:
        raise SystemExit(f"Output directory is not empty: {run_dir}. Use --force only to adopt it intentionally.")
    if args.master and not args.approve_master:
        raise SystemExit("Providing --master for a new run also requires --approve-master.")
    actions = [parse_action_spec(raw) for raw in (args.action or ["run-right:6:12:loop:3x2"])]
    ids = [action["id"] for action in actions]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate action ids are not allowed.")
    master = validate_master(Path(args.master).expanduser().resolve()) if args.master else None
    key = choose_chroma_key(master, args.chroma_key)
    source_pivot = [0.5, 0.5 if args.anchor == "center" else 0.82]
    pivot = ([float(v) for v in args.pivot.split(",")] if args.pivot else
             [args.frame_width / 2, args.frame_height * source_pivot[1]])
    run = {
        "schema_version": 2,
        "background_mode": args.background_mode,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "ready" if master is not None and args.approve_master else "needs-master",
        "requested_chroma_key": args.chroma_key,
        "chroma_key": key,
        "character": {
            "id": slugify(args.character_name),
            "name": args.character_name,
            "view": args.view,
            "style_notes": args.style_notes,
            "pixel_art": args.pixel_art,
            "master_file": None,
            "master_approved": False,
        },
        "output": {
            "frame_width": args.frame_width,
            "frame_height": args.frame_height,
            "anchor": args.anchor,
            "placement": args.placement,
            "source_pivot": source_pivot,
            "pivot": pivot,
            "engine": args.engine,
            "source_slot_size": args.source_slot_size,
            "candidate_count": args.candidates,
        },
        "qc": {
            "body_scale_cv_max": args.body_scale_cv_max,
            "anchor_y_std_max": args.anchor_y_std_max,
            "edge_margin": args.edge_margin,
        },
        "actions": actions,
    }
    output_pivot(run)
    configs = load_action_configs(args.action_config, actions)
    for action in actions:
        action.update(configs.get(action["id"], {}))
        validate_action_config(action)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompts").mkdir(exist_ok=True)
    (run_dir / "references").mkdir(exist_ok=True)
    write_text(run_dir / "character-spec.md", character_spec(args.character_name, args.view, args.style_notes))
    write_text(run_dir / "prompts" / "canonical-master.md", canonical_prompt(run))
    pose_guides = parse_mapping(args.pose_guide, "--pose-guide")
    for action in actions:
        create_action_files(run_dir, run, action, pose_guides, master if args.approve_master else None)
    write_json(run_dir / "run.json", run)
    if master is not None:
        run = attach_master(run_dir, run, Path(args.master).expanduser().resolve(), args.approve_master, False)
    return run


def load_action_configs(values: list[str], actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    configs = {}
    ids = {a["id"] for a in actions}
    allowed = {"durations_ms", "phases", "contacts", "events", "qc_profile"}
    for name, path in parse_mapping(values, "--action-config").items():
        if name not in ids:
            raise SystemExit(f"Unknown action config target: {name}")
        config = read_json(path)
        if set(config) - allowed:
            raise SystemExit(f"Unknown action config fields: {sorted(set(config) - allowed)}")
        action = next(a for a in actions if a["id"] == name)
        validate_action_config({**action, **config})
        configs[name] = config
    return configs


def update_run(args: argparse.Namespace, run_dir: Path, run: dict[str, Any]) -> dict[str, Any]:
    if not args.update and not args.master:
        raise SystemExit("The run already exists. Use --update to add actions or --master to attach a master.")
    master: Image.Image | None = None
    master_file = run["character"].get("master_file")
    if master_file:
        master = Image.open(run_dir / master_file).convert("RGBA")
    pose_guides = parse_mapping(args.pose_guide, "--pose-guide")
    if args.update:
        existing = {item["id"] for item in run["actions"]}
        additions = [parse_action_spec(raw) for raw in args.action]
        for action in additions:
            if action["id"] in existing:
                raise SystemExit(f"Action already exists: {action['id']}")
            existing.add(action["id"])
        current_actions = [read_json(run_dir / "actions" / a["id"] / "action.json") for a in run["actions"]]
        configs = load_action_configs(args.action_config, current_actions + additions)
        for action in current_actions:
            if action["id"] in configs:
                action.update(configs[action["id"]])
                invalidate_selection(run_dir, run, action)
                write_text(run_dir / "actions" / action["id"] / "prompt.md", action_prompt(run, action))
        for action in additions:
            action.update(configs.get(action["id"], {}))
            run["actions"].append(action)
            create_action_files(run_dir, run, action, pose_guides, master)
        run["updated_at"] = utc_now()
        write_json(run_dir / "run.json", run)
    if args.master:
        run = attach_master(
            run_dir,
            run,
            Path(args.master).expanduser().resolve(),
            args.approve_master,
            args.replace_master,
        )
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or extend a my-codex-sprite-skill animation run.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--character-name")
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--pose-guide", action="append", default=[], help="action=/absolute/path")
    parser.add_argument("--master", help="Approved transparent canonical master PNG.")
    parser.add_argument("--approve-master", action="store_true")
    parser.add_argument("--replace-master", action="store_true")
    parser.add_argument("--update", action="store_true", help="Add new actions to an existing run.")
    parser.add_argument("--frame-width", type=int, default=128)
    parser.add_argument("--frame-height", type=int, default=128)
    parser.add_argument("--source-slot-size", type=int, default=256)
    parser.add_argument("--candidates", type=int, default=1)
    parser.add_argument("--anchor", choices=["bottom-center", "center"], default="bottom-center")
    parser.add_argument("--background-mode", choices=["transparent", "chroma"], default="transparent",
                        help="New runs: request native alpha, or deliberately use a flat removable matte.")
    parser.add_argument("--placement", choices=["fixed", "legacy-fit"], default="fixed",
                        help="New runs: fixed slot geometry, or legacy per-action crop fitting.")
    parser.add_argument("--pivot", help="New runs: output root x,y in pixels; default matches source root.")
    parser.add_argument("--action-config", action="append", default=[], help="action=/path/to/timing-and-motion.json")
    parser.add_argument("--view", default="side")
    parser.add_argument("--style-notes", default="")
    parser.add_argument("--pixel-art", action="store_true")
    parser.add_argument("--engine", choices=["generic", "godot", "unity", "phaser"], default="generic")
    parser.add_argument("--chroma-key", default="auto", help="auto or #RRGGBB")
    parser.add_argument("--body-scale-cv-max", type=float, default=0.10)
    parser.add_argument("--anchor-y-std-max", type=float, default=0.05)
    parser.add_argument("--edge-margin", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    for value, name in (
        (args.frame_width, "--frame-width"),
        (args.frame_height, "--frame-height"),
        (args.source_slot_size, "--source-slot-size"),
        (args.candidates, "--candidates"),
    ):
        if value < 1:
            raise SystemExit(f"{name} must be positive.")
    run_dir = Path(args.output_dir).expanduser().resolve()
    run_path = run_dir / "run.json"
    if run_path.exists():
        creation_flags = {"--frame-width", "--frame-height", "--source-slot-size", "--pivot", "--placement",
                          "--anchor", "--background-mode", "--pixel-art", "--view", "--style-notes",
                          "--chroma-key", "--candidates", "--engine", "--character-name",
                          "--body-scale-cv-max", "--anchor-y-std-max", "--edge-margin"}
        supplied = {token.split("=", 1)[0] for token in sys.argv[1:]}
        if supplied & creation_flags:
            raise SystemExit("Geometry/style/default flags apply only to new runs; create a sibling run to change them.")
        run = update_run(args, run_dir, read_json(run_path))
    else:
        run = create_new_run(args, run_dir)
    print(f"run_dir={run_dir}")
    print(f"status={run['status']}")
    print(f"chroma_key={run['chroma_key']}")
    print("actions=" + ",".join(action["id"] for action in run["actions"]))


if __name__ == "__main__":
    main()
