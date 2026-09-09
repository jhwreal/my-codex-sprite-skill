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
3. Preserve native alpha; for a deliberately generated matte, remove it with the installed `$imagegen` helper.
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


## 7. Fixed geometry and old runs

New schema-2 runs default to `--placement fixed --background-mode transparent --candidates 1`. Source grids must divide exactly into equally sized square slots. The source root is normalized `(0.5, 0.82)`, or `(0.5, 0.5)` with `--anchor center`. The default output root follows the same fractions; set `--pivot 64,100` for a different output root. The scale is `min(target_width / slot_width, target_height / slot_height)`, independent of pose bounds. Mapping whole slots preserves deliberate root-relative motion, while the master/anchor reference establishes apparent body scale. Output dimensions need not be square.

Freeze source view, anchor-sheet framing, target canvas and pivot before generation. A candidate with the wrong grid aspect or clipped content should be repaired/regenerated; do not squash the image to force square slots. Pixel-art output uses nearest-neighbor sampling, which does not turn antialiased source art into true pixel art.

Existing schema-1 runs without a placement field retain `legacy-fit`. Explicit `--placement legacy-fit` is also available for new runs. It preserves old crop-and-center processing and cannot guarantee cross-action scale. Do not silently migrate already generated art. For fixed geometry, start a sibling run and reuse compatible raw sources only after inspecting their framing.

Creation flags set new-run geometry; `--update` only adds actions or applies action configs. Changes to master, geometry, references, prompts, action timing, processed frames, QC or review media make dependent evidence stale. Old unsigned candidates need processing, QC, preview and visual selection again. `--force` rebuilds only the named candidate, removes its old QC/preview/frame outputs and clears its selection; a new candidate ID preserves the previously selected candidate.

## 8. Action timing and motion contract

Optional JSON config (frame indices are 1-based):

```json
{
  "durations_ms": [120, 40, 60, 180],
  "phases": ["anticipation", "contact", "follow-through", "recovery"],
  "contacts": ["both feet", "left foot", "left foot", "both feet"],
  "events": [{"frame": 2, "name": "hit"}],
  "qc_profile": "grounded"
}
```

All fields are optional. Durations, phases and contacts, when supplied, must have exactly one entry per frame. Durations are positive finite milliseconds; absent durations default to `1000 / fps`. Profiles are `grounded`, `aerial` or `deforming`. Contact labels are visual intent, not collision geometry.

```bash
python "$SKILL_DIR/scripts/prepare_sprite_run.py" \
  --output-dir /absolute/path/to/sprite-run --update \
  --action 'attack:4:10:once:2x2' \
  --action-config 'attack=/absolute/path/to/attack.json'
```

Apply a config to an existing action by omitting `--action` and retaining `--update --action-config`. Supplied fields merge with the existing config and invalidate its selection. Reprocess, rerun QC and render before reviewing it again. Complete phase/contact planning before generating a complex action; a pose guide should reflect these beats.

## 9. Validation and model comparisons

Developer validation (Python with Pillow; no network or paid generation):

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts
```

Procedural tests cover the actual prepare → process → QC → preview → select → generic/Godot export CLI flow, source clipping, airborne displacement, cross-action body scale, timing, mirroring and stale evidence rejection. They verify pipeline behavior, not model quality or actual engine playback.

For a deliberate real-generation benchmark, keep the master, action beats, target canvas and engine constant across candidates. Include a run loop, weapon attack and jump/landing. Record available generation model/usage, elapsed time, failed frame numbers, repair count, use/redo decision and in-engine evidence. Keep raw art and benchmark outputs outside the Skill repository. Do not claim the model upgrade improved acceptance without this comparison.


Use `process_action_sheet.py --prompt-file /path/to/issued-prompt.txt` to preserve the exact prompt sent to generation. Without this flag, `prompt-used.md` is a copy of the action template and `processing.json` labels it `action-template-unverified`; it must not be described as a verified tool transcript. Keep any available model ID, returned usage and elapsed time in a separate local generation log, without raw responses, signed URLs or credentials.


Optional real-engine smoke test: set `SPRITE_TEST_GODOT` to an existing Godot 4 executable when running the suite. The test imports the exported resource in a temporary project, loads it in Godot, checks relative frame durations and applies the exported node offset. It does not replace visual gameplay acceptance. The installed imagegen chroma helper is also exercised when available; these two integrations report explicit skips when their dependencies are absent.
