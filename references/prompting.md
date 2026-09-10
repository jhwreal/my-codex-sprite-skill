# Prompting and reference roles

## Contents

1. Input roles
2. Identity contract
3. Layout selection
4. Prompt construction
5. Candidate strategy
6. Common failure corrections

## 1. Input roles

Label every image when invoking `$imagegen`:

- **Canonical master** — authoritative identity, costume, palette, proportions, facing, and props.
- **Anchor sheet / positioning reference（定位参考）** — slot count, body scale, and neutral root only. Its repeated neutral figures are measurement examples, not temporal poses; do not copy their limbs or cadence. Optional attachment when needed for geometry; keep numeric geometry in the prompt even when omitted.
- **Layout guide** — construction-only grid and safe margins; never reproduce its lines, labels, colors, or background marks.
- **Pose guide / action reference（动作参考）** — authoritative temporal pose sequence, support legs, passing poses and weight transfer; preserve character identity from the master rather than copying the guide's appearance.
- **Current action sheet** — edit target during a repair; change only the named slot or defect.
- **Style reference** — style only; never replace the master character with its subject.

Do not attach redundant or contradictory references. Identity, positioning and action references must have distinct roles. A successful earlier action can supply motion even when its background is defective; identify the intended frame mapping and any unverified beats. The master controls identity, the action reference controls motion, and positioning controls scale/root without freezing deliberate displacement. Never treat repeated standing figures as a pose guide. Prefer a compact textual phase/contact plan for a first attempt when motion is simple; reuse an existing guide before generating a new one. A guide with a different frame count/facing requires an explicit phase mapping, not blind copying. For background-only repair, the current sheet is the pose authority; avoid redundant references that invite redesign.

## 2. Identity contract

Repeat only the invariants that matter:

```text
Keep exactly the same character as the canonical master: same face, head-to-body ratio,
hair or fur silhouette, costume construction, palette, markings, materials, handedness,
weapon dimensions, prop side, camera view, outline treatment, and lighting logic.
Change only the action pose and the minimal deformation required by motion.
```

Record detailed invariants once in `character-spec.md`; keep action prompts compact enough that the action remains legible.

## 3. Layout selection

Use one sheet per action, never one independent generation per frame.

| Frames | Default source layout | Notes |
|---:|---:|---|
| 1 | 1x1 | Canonical master or a single repair frame |
| 2 | 2x1 | Short transition |
| 3 | 3x1 | Short pixel-art strip |
| 4 | 2x2 | Balanced square layout |
| 5–6 | 3x2 | Good default for locomotion and attacks |
| 7–8 | 4x2 | Wider actions and death cycles |
| 9 | 3x3 | Use only when eight frames are insufficient |

Prefer fewer meaningful frames over many weakly differentiated frames. Deterministically repack the approved grid into the engine's required strip or atlas.

## 4. Prompt construction

The generated `actions/<action>/prompt.md` is the starting template. Resolve unspecified beats and keep only references actually attached in the issued prompt; save that prompt using `--prompt-file`. The master lives at run-level `references/canonical-master.png`; action guides live under `actions/<action>/references/`. Add action-specific beats without redesigning the character.

Use this concise structure:

```text
Use case: identity-preserve
Asset type: candidate production action sheet for a 2D game character
Primary request: edit the references into exactly <N> temporal poses for <action>
Input images: canonical master (identity); action/pose reference (motion, if available); optional anchor sheet (positioning only); optional layout guide
Composition: <columns>x<rows> row-major grid; one complete isolated character per used slot
Action beats: <frame-by-frame timing or named animation phases>
Constraints: preserve identity contract; shared body scale, declared contact points and intentional airborne motion; complete unclipped body
Background: genuine transparent alpha; no painted checkerboard, shadows, or floor
Spatial contract: fixed square slots; declared root and body scale (optional anchor sheet illustrates positioning only); preserve intended source-relative displacement
Avoid: text, labels, visible guide marks, scenery, duplicate characters, detached effects,
motion blur, afterimages, contact shadows, cropped limbs, overlapping slots, extra props
```

For pixel art, also require crisp clusters, fixed apparent pixel scale, a restrained palette, nearest-neighbor-compatible edges, and no antialiasing. For painted, sticker, clay, or 3D-rendered sprites, require consistent material and lighting with real alpha and clean edges. Use matte-specific prompting only for a deliberate chroma workflow.

## 5. Candidate strategy

- Start with one candidate. Add a second after a specific failure diagnosis or when the user requests a comparison.
- Default retry ceiling: two generation attempts per action, also bounded by the 30–60 minute whole-batch budget in SKILL.md; count background repairs and extra guide generation in elapsed time. Report persistent defects before extending it. Do not automatically double every image request.
- Never ask one image call to produce several distinct candidate sheets.
- Make one targeted correction per iteration. Preserve all verified invariants.
- Keep prompt, input roles, selected source, processing report, QC, and preview together under the candidate directory.

## 6. Common failure corrections

### Character gets smaller during wide poses

Remove detached effects and oversized weapon trails. Keep body and effects on separate sheets. Increase slot safety margin only if the body itself is clipped.

### Identity drifts across slots

Strengthen the canonical-master role while preserving the action reference. Use an anchor sheet only for a diagnosed scale/root problem, explicitly excluding its neutral poses from motion authority. Do not generate frames independently.

### Animation is static

Specify distinct temporal beats, weight transfer, contact poses, anticipation, and recovery. Reject a sheet made of near-duplicate poses even if frame count is correct. For walk/run, label anatomical left/right legs consistently across both half-cycles; require opposite support/contact and passing, not simply two similar rear-foot lifts. After text-only motion failure, reuse a better action sheet or supply a separate pose guide before retrying.

### Grid lines appear in output

Remove a redundant guide or restate that it is construction-only. Keep numeric scale/root constraints and forbid visible borders, labels, guide colors, and frame numbers.

### Chroma edge is dirty

Choose a key farther from the character palette, forbid shadows and translucent effects, rerun soft-matte despill, and inspect on both light and dark backgrounds.


## Model and reference guidance

- Built-in imagegen: use the actual exposed tool fields. Inspect local inputs before editing. Attach the master for identity and a distinct action reference when needed; attach the clean anchor sheet only for positioning ambiguity. Do not send redundant copies or assume the tool exposes API-only options such as `quality`, `size`, or `input_fidelity`.
- Preserve the current edit target for repairs. Change one named slot/defect, then inspect all resulting frames because neighboring pixels may change.
- For an explicitly chosen Image 2 CLI/API path, `gpt-image-2` processes reference images at high fidelity automatically; omit `input_fidelity`. Use the installed imagegen skill for supported sizes, quality and background constraints. Do not substitute Image 2.5 capabilities or change models silently.
- Choose a total canvas whose dimensions divide into equal square slots. Increase source resolution for tiny face/costume details before increasing frame count. Express desired dimensions in the built-in prompt and validate the actual file; a requested layout is not a guarantee.
- Additional frames, higher resolution, and fewer reference images are benchmark variables, not guaranteed improvements. Retain the 6-frame pilot until actual results justify a new default.
- Record the actual prompt and available generation metadata with the candidate. When the tool does not report a model ID or usage, record it as unknown rather than inferring it from the task model.

Official references (checked 2026-09-09):
- https://developers.openai.com/api/docs/models/gpt-image-2
- https://developers.openai.com/api/docs/guides/image-generation
- https://developers.openai.com/api/docs/guides/latest-model

These are guidance links, not pinned provider contracts. The installed imagegen skill and live tool schema own execution details.
