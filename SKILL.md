---
name: my-codex-sprite-skill
description: Create, repair, normalize, validate, preview, and package consistent 2D game-character sprite animations from reference art or text. Use for idle, walk, run, attack, jump, hurt, death, directional animations, sprite sheets, frame extraction, identity or anchor drift diagnosis, chroma-key cleanup, animation QA, and generic or Godot atlas export. This skill composes $imagegen for canonical character and per-action visual generation, then uses deterministic scripts for layout, transparency, shared-scale normalization, QC, previews, minimal-scope repairs, and packaging.
---

# My Codex Sprite Skill

## Overview

Build production-oriented 2D character animations through a gated pipeline: lock one canonical identity, generate one whole action sheet at a time, normalize it deterministically, inspect both metrics and motion, repair only the smallest failing scope, and package only approved actions.

Do not promise that an AI-generated sheet is shippable merely because it was split successfully. Programmatic QC and visual animation review are both mandatory.

## Non-negotiable rules

1. Load and follow the installed `$imagegen` skill before any visual generation or edit. Use its built-in-first path and current tool schema. Do not call an image API or ad-hoc image CLI directly.
2. Establish one approved transparent canonical master before generating actions. Treat its silhouette, face, proportions, palette, outfit, materials, handedness, markings, and props as invariants.
3. Generate one complete action sheet per image request. Do not generate isolated frames unless repairing one bad frame after the action sheet has otherwise passed.
4. Attach the canonical master for identity. Treat the anchor sheet as positioning reference only, never as an action sequence; attach it only when spatial ambiguity needs it. When a motion image is needed, use a separate action/pose reference, preferably an existing successful action or a phase guide; do not generate an extra guide by default. Include a layout guide only when it resolves layout ambiguity.
5. Keep character-body animation separate from sword arcs, projectiles, dust, smoke, hit flashes, and other effects unless the effect is physically attached and intentionally part of the silhouette.
6. Let scripts own exact grid slicing, transparency cleanup, shared scaling, anchors, atlas geometry, metadata, and previews. Never rely on generated pixels for exact engine geometry.
7. Start with one pilot action for a new hero. Do not expand the full action set until the pilot passes identity, motion, loop, transparency, and in-engine checks.
8. Repair the smallest failing scope: processing settings, then one frame, then one action, and only then the canonical master or full set.

## Batch time budget

Aim to finish the agreed action batch in 30–60 minutes, including generation, background repairs, processing and review. This is a planning target, not a provider-latency guarantee. Reuse approved masters and successful motion; do not add a pose-guide image call, candidate comparison or model benchmark by default. Begin with the user's action list and priorities; use 60 minutes when no tighter target is given. Check elapsed time after each external generation call and use observed latency to decide whether another call fits, reserving roughly 10 minutes for processing, review and handoff.

Use one candidate per action first. The two-attempt per-action cap is a ceiling, not an allocation: the whole-batch time budget takes precedence, and background/guide calls count too. After the pilot passes, move through the requested actions without repeated approvals or redundant checks. Inspect identity and motion together in one review pass, recording compact frame findings. Do not reduce required action quality or silently drop requested actions to meet the clock. If the remaining work cannot fit, stop optional generation/retries, deliver the approved subset with unresolved items and an estimate, and ask only when scope or additional time actually needs a user decision. Do not continue for hours by repeatedly resetting the budget per action.

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

Reuse approved project art when possible. Otherwise request one full-body neutral reference with genuine transparent alpha through built-in `$imagegen`. Inspect it on light, dark, and checker backgrounds before attaching it. An existing user decision accepting this exact master is sufficient approval; do not ask again.

If a deliberate matte is needed, create the run with `--background-mode chroma`, use its key color and the installed imagegen removal helper. Do not treat CLI model limitations as limitations of the built-in tool, and do not silently change providers or models.

```bash
python "$SKILL_DIR/scripts/prepare_sprite_run.py" \
  --output-dir /absolute/path/to/sprite-run \
  --master /absolute/path/to/approved-master.png \
  --approve-master
```

Update `character-spec.md` with the actual identity invariants. If the master changes later, require explicit replacement approval and regenerate every dependent action.

### 4. Generate action candidates with `$imagegen`

Read `actions/<action>/prompt.md`. Inspect local references before editing and attach them using the actual tool schema. Label identity, positioning, and action references separately. Repeated neutral poses in anchor-sheet.png specify scale/root only; never copy their limb poses or cadence. For walk/run, plan both half-cycles with stable left/right leg labels and explicit support, passing and opposite contact; use a motion reference when text alone has failed. Use `--action-config` to record per-frame phases, contacts, timing, and events when they matter; see `references/workflow.md`.

Start with one candidate per action and inspect it. Generate a second only for a diagnosed failure or a requested comparison. Default to at most two generation attempts per action; after repeated failure, report the concrete defect and revise the action plan before spending more. A requested candidate comparison or retry budget takes precedence. Save source images and the actual issued prompt in the run. Inspect raw motion before spending time on background edits or full processing: for walk/run, quickly confirm both half-cycles and the loop seam. A failed motion candidate may be kept for diagnosis, but must not become the selected/exported action.

New runs request true transparency. Validate the actual alpha channel; a painted checkerboard is not transparency. `--remove-chroma` is an explicit processing fallback for a deliberately generated flat matte. Ordinary opaque or partially transparent backgrounds must be repaired, not silently keyed. If motion is already good, edit that exact sheet for background only and compare every pose before accepting the repair; regeneration is a separate candidate, never a silent source replacement.

### 5. Process one candidate deterministically

```bash
python "$SKILL_DIR/scripts/process_action_sheet.py" \
  --run-dir /absolute/path/to/sprite-run \
  --action run-right \
  --input /absolute/path/to/generated-candidate.png \
  --candidate candidate-01
```

New runs use `fixed` placement: equally sized square source slots map through one uniform scale and root translation to the target canvas. No per-pose bounding-box crop or recentering occurs. The same normalized source canvas maps to the same character scale across actions. Generation must still respect the declared neutral-master scale, whether or not the optional positioning image is attached. Source clipping and content in unused slots are checked before normalization.

The output root defaults to `(width × 0.5, height × 0.82)` for grounded sprites; `--pivot x,y` sets a custom root when creating a run. `--anchor center` uses a centered source and output root. Freeze geometry before generating actions. See `references/workflow.md` for legacy runs and exact timing.

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

Inspect `qc.json`, `qa/contact-sheet.png`, and `qa/preview.gif`. A script pass means the implemented structural/heuristic checks passed, not that motion is correct. It cannot judge identity, anatomy, weight, appeal, or action semantics. Walk/run review must track each leg through both half-cycles and the loop seam; crossing silhouettes or bobbing alone do not prove alternation. Review every frame against the master; report frame number, observed defect, and smallest repair. Inspect loop seams and playback at target size. Apply `references/qa-rubric.md`; bounding-box changes are review heuristics, not proof that the character changed scale.

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

Add `--accept-qc-review` only after inspecting and justifying every warning. Selection binds the current inputs, frame hashes, QC, and preview. Reprocessing, changing timings, editing the master, or altering reviewed files requires fresh evidence and review; packaging rejects stale approval.

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

Inspect the final atlas, manifest, and in-engine playback before declaring completion. Apply exported pivot/offset metadata in the engine; a Godot `SpriteFrames` resource does not set node position or dispatch gameplay events.

## Repair decision tree

- Raw sheet is sound but the preview pops: fix layout metadata, shared anchor, or processing; do not regenerate first.
- One generated slot is wrong: repair that slot with a grounded edit, then re-run processing and QC for the whole action.
- One action has identity or action-design failure: regenerate only that action with the canonical master, a distinct motion reference when needed, positioning guidance as needed, and failure note.
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


## Model upgrades and autonomy

The task's reasoning model plans and inspects; imagegen supplies pixels. Do not hardcode Astra or an image model into these deterministic scripts, and do not claim a hidden built-in backend model was verified. Use the selected task model and current imagegen contract. `references/prompting.md` records Image 2-specific guidance for an explicitly chosen CLI path.

For Astra, preserve the user's accepted decisions across steps. Complete authorized processing, targeted repair, QC, previews, and packaging without repeated permission questions. Resolve routine layout and file choices from the project. Ask only for an unresolved identity/art-direction choice, an exhausted generation budget, or authorization for a different external generation path. Do not confuse programmatic `pass` with visual or in-engine acceptance.

Model upgrades do not prove higher sprite acceptance rates. Compare a run loop, a weapon attack, and jump/landing with one fixed master and action specification; record pass/retry results, elapsed time and reported usage. Never invent unavailable model IDs, costs, engine tests, or quality improvements. Keep paid model comparisons explicit; deterministic regression tests need no image API.
