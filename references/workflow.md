# Sprite production workflow

## Contents

1. Run layout
2. Action specification
3. Canonical-master lifecycle
4. Candidate lifecycle
5. Repair workflow
6. Dependency guidance

## 1. Run layout

`prepare_sprite_run.py` creates an engine-neutral working folder:

```text
sprite-run/
├── run.json
├── character-spec.md
├── prompts/
│   └── canonical-master.md
├── references/
│   └── canonical-master.png
├── actions/
│   └── run-right/
│       ├── action.json
│       ├── prompt.md
│       ├── references/
│       │   ├── layout-guide.png
│       │   ├── anchor-sheet.png
│       │   └── pose-guide.png
│       └── candidates/
│           └── candidate-01/
│               ├── source.png
│               ├── transparent-source.png
│               ├── processing.json
│               ├── prompt-used.md
│               ├── frames/
│               ├── sheet.png
│               ├── qc.json
│               └── qa/
│                   ├── contact-sheet.png
│                   └── preview.gif
└── final/
    ├── atlas.png
    ├── atlas.json
    ├── validation.json
    └── sprite_frames.tres
```

Keep failed candidates for diagnosis until an action is approved. Clean them only after the user confirms they are not needed.

## 2. Action specification

Pass each action as:

```text
name:frame-count:fps:loop|once:columnsxrows
```

Examples:

```text
idle:4:6:loop:2x2
walk-right:6:10:loop:3x2
run-right:6:12:loop:3x2
attack-light:6:12:once:3x2
jump:5:10:once:3x2
hurt:4:10:once:2x2
death:8:10:once:4x2
```

The source grid may have unused trailing slots, but the generated output must not put stray content in them. The deterministic output is always repacked in temporal order.

Use compact grids for five or more frames because they preserve useful character scale in common image-generation aspect ratios. A short horizontal strip remains appropriate for two or three pixel-art frames when the requested canvas supports it.

## 3. Canonical-master lifecycle

The canonical master is the visual source of truth, not merely another reference.

1. Prefer an approved in-game frame or cleaned model sheet.
2. If none exists, generate a neutral full-body master before any action.
3. Remove its chroma background using the installed `$imagegen` helper.
4. Inspect the cutout on light, dark, and checker backgrounds.
5. Record immutable traits in `character-spec.md`.
6. Obtain explicit approval.
7. Attach it with `--approve-master`.

Changing the master invalidates all dependent action selections. Do not silently replace it.

## 4. Candidate lifecycle

Each candidate moves through these states:

```text
generated → processed → qc-pass|qc-review|qc-fail → visual-approved → selected
```

For each generated image:

1. Copy the selected image into the run through `process_action_sheet.py`.
2. Run `qc_action.py`.
3. Render the contact sheet and GIF.
4. Inspect identity, anatomy, action semantics, cadence, loop, edges, and target-size readability.
5. Select only after explicit visual approval.

Do not let a later candidate overwrite an earlier candidate directory. Use stable ids such as `candidate-01`, `candidate-02`, and `repair-01`.

## 5. Repair workflow

Preserve successful work and repair the smallest scope.

### Processing-induced failures

Symptoms include baseline jumps, inconsistent cell padding, wrong source-grid order, alpha fringe, or clipped normalization despite a stable raw sheet.

Repair by correcting action metadata or processing parameters and re-running deterministic steps. Never hide instability with per-frame fit-to-cell scaling.

### Single-slot visual failures

Use an identity-preserving image edit grounded by:

- canonical master;
- current action sheet;
- anchor and layout guides;
- pose guide;
- a concise description of the one bad slot;
- an invariant that every other slot must remain unchanged.

Re-run processing and QC for the entire edited action because an image edit can affect neighboring pixels.

### Action-level failures

Regenerate only the failing action. Include the canonical master, anchor sheet, pose guide, and the exact failure note. Do not regenerate passed actions.

### Master-level failures

Replace the master only when identity errors recur across several independently generated actions. Obtain approval, then mark every dependent action unapproved.

## 6. Dependency guidance

The bundled scripts require Python 3.9+ and Pillow. The chroma-key stage also composes the helper installed with `$imagegen`:

```text
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/scripts/remove_chroma_key.py
```

Prefer an existing project environment or the Codex desktop bundled Python. If neither has Pillow, explain the missing dependency and ask before installing it.
