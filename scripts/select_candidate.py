#!/usr/bin/env python3
"""Record explicit visual approval for one non-failing action candidate."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from _sprite_common import read_json, slugify, write_json


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a QCed and visually approved candidate.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--approve-visual", action="store_true")
    parser.add_argument("--accept-qc-review", action="store_true")
    parser.add_argument("--note", required=True)
    args = parser.parse_args()

    if not args.approve_visual:
        raise SystemExit("Selection requires --approve-visual after inspecting the contact sheet and GIF.")
    if not args.note.strip():
        raise SystemExit("A non-empty visual review note is required.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    action_id = slugify(args.action)
    candidate_id = slugify(args.candidate)
    action_path = run_dir / "actions" / action_id / "action.json"
    candidate_dir = run_dir / "actions" / action_id / "candidates" / candidate_id
    qc_path = candidate_dir / "qc.json"
    preview_path = candidate_dir / "qa" / "preview.gif"
    contact_path = candidate_dir / "qa" / "contact-sheet.png"
    if not qc_path.is_file():
        raise SystemExit("qc.json is missing. Run qc_action.py first.")
    if not preview_path.is_file() or not contact_path.is_file():
        raise SystemExit("QA media is missing. Run render_action_preview.py first.")
    qc = read_json(qc_path)
    if qc.get("status") == "fail":
        raise SystemExit("A candidate with QC status 'fail' cannot be selected.")
    if qc.get("status") == "review" and not args.accept_qc_review:
        raise SystemExit("QC warnings require --accept-qc-review plus a note that justifies them.")
    action = read_json(action_path)
    approval = {
        "candidate": candidate_id,
        "approved_at": utc_now(),
        "qc_status": qc.get("status"),
        "note": args.note.strip(),
        "contact_sheet": str(contact_path.relative_to(run_dir)),
        "preview": str(preview_path.relative_to(run_dir)),
    }
    action["selected_candidate"] = candidate_id
    action["visual_review"] = approval
    action["status"] = "approved"
    write_json(action_path, action)

    run_path = run_dir / "run.json"
    run = read_json(run_path)
    for item in run.get("actions", []):
        if item.get("id") == action_id:
            item["selected_candidate"] = candidate_id
            item["visual_review"] = approval
            item["status"] = "approved"
            break
    run["updated_at"] = utc_now()
    write_json(run_path, run)
    print(f"selected={action_id}:{candidate_id}")
    print(f"qc_status={qc.get('status')}")


if __name__ == "__main__":
    main()
