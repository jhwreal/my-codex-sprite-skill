---
name: my-codex-sprite-skill
description: Create, repair, normalize, validate, preview, and package consistent 2D game-character sprite animations from reference art or text. Use for idle, walk, run, attack, jump, hurt, death, directional animations, sprite sheets, frame extraction, identity or anchor drift diagnosis, chroma-key cleanup, animation QA, and generic or Godot atlas export. This skill composes $imagegen for canonical character and per-action visual generation, then uses deterministic scripts for layout, transparency, shared-scale normalization, QC, previews, minimal-scope repairs, and packaging.
---

# My Codex Sprite Skill

## Overview

Build production-oriented 2D character animations through a gated pipeline: lock one canonical identity, generate one whole action sheet at a time, normalize it deterministically, inspect both metrics and motion, repair only the smallest failing scope, and package only approved actions.

Do not promise that an AI-generated sheet is shippable merely because it was split successfully. Programmatic QC and visual animation review are both mandatory.

## Non-negotiable rules

1. Load and follow the installed `$imagegen` skill before any visual generation or edit. Use its built-in-first path and approval rules. Do not call an image API or ad-hoc image CLI directly.
2. Establish one approved transparent canonical master before generating actions. Treat its silhouette, face, proportions, palette, outfit, materials, handedness, markings, and props as invariants.
3. Generate one complete action sheet per image request. Do not generate isolated frames unless repairing one bad frame after the action sheet has otherwise passed.
4. Attach the canonical master and matching anchor sheet to every action request. Attach a pose guide whenever timing or anatomy matters.
5. Keep character-body animation separate from sword arcs, projectiles, dust, smoke, hit flashes, and other effects unless the effect is physically attached and intentionally part of the silhouette.
6. Let scripts own exact grid slicing, transparency cleanup, shared scaling, anchors, atlas geometry, metadata, and previews. Never rely on generated pixels for exact engine geometry.
7. Start with one pilot action for a new hero. Do not expand the full action set until the pilot passes identity, motion, loop, transparency, and in-engine checks.
8. Repair the smallest failing scope: processing settings, then one frame, then one action, and only then the canonical master or full set.

## Runtime and project setup

Set the installed skill directory and choose a Python runtime that has Pillow. Prefer the project-selected or bundled Codex runtime. Do not install packages without the user's approval.

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/my-codex-sprite-skill"
python3 -c "from PIL import Image; print(Image.__version__)"
```

If system Python lacks Pillow and the Codex desktop bundled runtime is available, use the Python path returned by the workspace-dependencies tool.

Read these references only when relevant:

- `references/workflow.md`: run structure, CLI recipes, candidate lifecycle, and repair flow.
- `references/prompting.md`: reference-image roles, action-sheet prompts, layout selection, and identity locks.
- `references/action-design.md`: recommended key poses for common game actions.
- `references/qa-rubric.md`: deterministic thresholds and visual acceptance criteria.
- `references/engine-export.md`: generic atlas contract and Godot, Unity, or Phaser integration.

## Workflow

### 1. Audit before generating

Inspect the user's current canonical art, raw sheets, extracted frames, previews, engine settings, and existing scripts. Classify every visible problem as one or more of:

- identity, costume, palette, prop, or handedness drift;
- action design, cadence, facing, or loop failure;
- grid or frame-order error;
- scale, baseline, pivot, or anchor drift;
- chroma-key spill, alpha residue, or edge contamination;
- clipping, overlapping slots, detached effects, or empty frames;
- engine FPS, filtering, region, import, or pivot misconfiguration.

Diagnose first when the user asks only for an audit. Implement repairs only when requested.

### 2. Prepare a pilot run

For a new side-view hero, default to a 6-frame `run-right` pilot at 12 FPS in a `3x2` source grid. Adapt the action, frame count, dimensions, view, style, and engine to the project.

```bash
python "$SKILL_DIR/scripts/prepare_sprite_run.py" \
  --character-name "Hero" \
  --output-dir /absolute/path/to/sprite-run \
  --action 'run-right:6:12:loop:3x2' \
  --frame-width 128 \
  --frame-height 128 \
  --view side \
  --engine godot
```

The run starts in `needs-master` state unless an already approved transparent master is attached.

### 3. Establish and approve the canonical master

Reuse approved project art when possible. Otherwise use `$imagegen` to create one full-body neutral reference on a flat removable chroma-key background. Use the key chosen in `run.json`, remove it with the installed imagegen helper, inspect on light, dark, and checker backgrounds, then obtain explicit approval before attaching it.

```bash
python "$SKILL_DIR/scripts/prepare_sprite_run.py" \
  --output-dir /absolute/path/to/sprite-run \
  --master /absolute/path/to/approved-master.png \
  --approve-master
```

Update `character-spec.md` with the actual identity invariants. If the master changes later, require explicit replacement approval and regenerate every dependent action.

### 4. Generate action candidates with `$imagegen`

Read `actions/<action>/prompt.md`. Load the canonical master, anchor sheet, layout guide, and optional pose guide so they are visible to the built-in edit flow. Label each image's role explicitly.

Generate candidates in separate calls. Default to two candidates for a hero action and one for low-risk secondary characters; use three when the action is critical or earlier candidates fail. Save each selected raw output into the project run. Do not accept the first output automatically.

For simple opaque characters, use the flat chroma-key workflow from `$imagegen`. Ask before switching to true native transparency or another model/path, exactly as `$imagegen` requires.

### 5. Process one candidate deterministically

```bash
python "$SKILL_DIR/scripts/process_action_sheet.py" \
  --run-dir /absolute/path/to/sprite-run \
  --action run-right \
  --input /absolute/path/to/generated-candidate.png \
  --candidate candidate-01
```

The processor removes the key through the installed imagegen helper when needed, slices the declared source grid, applies one shared scale to all frames, aligns one shared anchor, clears hidden RGB under fully transparent pixels, and writes normalized frames plus a horizontal transparent sheet.

Never rescale each frame independently to fill its cell. That hides source instability and creates motion popping.

### 6. Run programmatic QC and render motion previews

```bash
python "$SKILL_DIR/scripts/qc_action.py" \
  --run-dir /absolute/path/to/sprite-run \
  --action run-right \
  --candidate candidate-01
```

```bash
python "$SKILL_DIR/scripts/render_action_preview.py" \
  --run-dir /absolute/path/to/sprite-run \
  --action run-right \
  --candidate candidate-01
```

Inspect `qc.json`, `qa/contact-sheet.png`, and `qa/preview.gif`. A script result cannot judge identity, anatomy, weight, appeal, or action semantics. Apply the full rubric in `references/qa-rubric.md`.

### 7. Select only a visually approved candidate

Reject any candidate with QC status `fail`. A `review` candidate requires a documented visual justification and explicit override.

```bash
python "$SKILL_DIR/scripts/select_candidate.py" \
  --run-dir /absolute/path/to/sprite-run \
  --action run-right \
  --candidate candidate-01 \
  --approve-visual \
  --note "Identity, gait, loop, baseline, and edges verified."
```

Add `--accept-qc-review` only after inspecting and justifying every warning.

### 8. Expand actions incrementally

After the pilot works in-engine, add actions without recreating passed work:

```bash
python "$SKILL_DIR/scripts/prepare_sprite_run.py" \
  --output-dir /absolute/path/to/sprite-run \
  --update \
  --action 'idle:4:6:loop:2x2' \
  --action 'attack:6:12:once:3x2' \
  --action 'hurt:4:10:once:2x2'
```

Mirror a direction only when the character is visually symmetric and mirroring does not swap a weapon hand, shield side, text, emblem, scar, lighting direction, or gameplay meaning. Preserve frame order when mirroring; never mirror the whole strip in a way that reverses temporal cadence.

When mirroring is explicitly approved, derive it frame-by-frame and then run the normal QC, preview, and selection gates:

```bash
python "$SKILL_DIR/scripts/mirror_action.py" \
  --run-dir /absolute/path/to/sprite-run \
  --source-action run-right \
  --target-action run-left \
  --confirm-safe-mirror \
  --note "Character and equipment are symmetric; frame order is preserved."
```

### 9. Package approved actions

```bash
python "$SKILL_DIR/scripts/pack_atlas.py" \
  --run-dir /absolute/path/to/sprite-run \
  --output-dir /absolute/path/to/sprite-run/final
```

For Godot, also pass the atlas path as it will appear inside the project:

```bash
python "$SKILL_DIR/scripts/pack_atlas.py" \
  --run-dir /absolute/path/to/sprite-run \
  --output-dir /absolute/path/to/sprite-run/final \
  --godot-resource-path 'res://art/hero/atlas.png'
```

Inspect the final atlas, manifest, and in-engine playback before declaring completion.

## Repair decision tree

- Raw sheet is sound but the preview pops: fix layout metadata, shared anchor, or processing; do not regenerate first.
- One generated slot is wrong: repair that slot with a grounded edit, then re-run processing and QC for the whole action.
- One action has identity or action-design failure: regenerate only that action with the canonical master, anchor sheet, pose guide, and failure note.
- Many actions drift in the same way: repair or replace the canonical master/spec, then invalidate dependent actions.
- Character is stable but attacks need large effects: keep the body action and create a separately anchored effects animation.
- GIF is correct but the game is wrong: inspect frame order, FPS, pivot, atlas regions, texture filtering, loop flags, and import settings.

## Acceptance criteria

Accept an action only when all are true:

- exact expected frame count; no empty, clipped, overlapping, or edge-touching frames;
- fully transparent pixels have zero RGB residue; no key-color fringe on light or dark backgrounds;
- one character identity, silhouette family, palette, outfit, handedness, props, and view throughout;
- shared scale and anchor produce no unintended size pop or baseline jump;
- action semantics, facing, cadence, anticipation, contact, recovery, and loop/ending read at target game size;
- effects are intentionally layered; no detached noise, shadows, guide marks, labels, or scenery;
- contact sheet and animated preview are inspected visually;
- selected action is verified in the target engine before full-set expansion.
