# Sprite animation QA rubric

## Contents

1. Programmatic gates
2. Visual identity review
3. Motion review
4. Transparency and scale review
5. Engine review
6. Failure severity

## 1. Programmatic gates

The scripts report deterministic facts and heuristics. Treat hard errors as blockers. Treat warnings as mandatory review items, not automatic failures or passes.

| Metric | Default target | Meaning |
|---|---:|---|
| `frame_count` | exact | Declared temporal frames exist |
| `empty_frames` | 0 | Every used slot contains a sprite |
| `edge_touch_frames` | 0 | Normalized content keeps safety padding |
| `paste_clamped_frames` | 0 | Shared-scale placement did not overflow |
| `transparent_rgb_residue_pixels` | 0 | Fully transparent pixels have zero RGB |
| `body_scale_cv` | ≤ 0.10 | Source silhouette extent is reasonably stable |
| `normalized_anchor_y_std` | ≤ 0.05 | Source feet/baseline do not wander excessively |
| `motion_score` | > 0.005 | Frames are not effectively identical |

For a strict hero pilot, tighten `body_scale_cv` to `0.08`. Large pose changes can create a scale warning even when the art is valid; document that judgment rather than suppressing the metric.

Hard-fail unusually severe drift by default: `body_scale_cv > 0.20` or `normalized_anchor_y_std > 0.12`. Adjust thresholds only when the action design genuinely requires large silhouette or vertical changes, such as jump, squash-and-stretch, or death.

## 2. Visual identity review

Compare every frame against the canonical master and check:

- same face, head shape, eyes, hair or fur, body proportions, and silhouette family;
- same costume construction, palette, markings, material, outline, and lighting logic;
- same hand count, limb count, anatomy, grip, prop dimensions, and prop side;
- no accidental age, species, gender presentation, or camera-view changes;
- no frame reads as a second character or a redesigned version.

Reject identity drift even if all programmatic metrics pass.

## 3. Motion review

Inspect the GIF at intended speed and step through individual frames.

- The action is recognizable at target game size.
- Key poses differ meaningfully and follow a plausible temporal order.
- Weight, center of mass, contact, anticipation, follow-through, and recovery read clearly.
- Locomotion alternates limbs and faces the intended direction.
- The first and last frame join naturally for loops.
- Non-looping actions end in a stable state or transition cleanly.
- There is no unintended size pop, baseline jump, frame-order reversal, foot slide, or frozen interval.

## 4. Transparency and scale review

Inspect the contact sheet on checker, light, and dark rows.

- no chroma fringe, hidden colored RGB, white boxes, guide lines, labels, or grid marks;
- no clipped hair, weapons, clothing, feet, shadows, or effects;
- no detached specks, floor shadows, glows, motion blur, or neighboring-slot slivers;
- shared apparent scale remains stable; normalization does not shrink one frame independently;
- pixel-art frames retain consistent pixel scale and crisp nearest-neighbor edges.

## 5. Engine review

Before approving the pilot, verify in the target engine:

- atlas regions and frame order;
- FPS, per-frame duration, loop flag, and held final frame;
- pivot or anchor, collision boxes, hurt boxes, and attack boxes;
- nearest-neighbor filtering for pixel art; appropriate filtering for other styles;
- no import cropping, compression halo, premultiplied-alpha issue, or mipmap bleed;
- transition from idle or locomotion does not jump because of a different pivot.

## 6. Failure severity

- **Fail:** wrong count, empty frame, clipping, edge touch, alpha residue, severe drift, wrong character, wrong facing, broken anatomy, wrong action, or unusable loop.
- **Review:** moderate scale or anchor warning, deliberate large silhouette change, minor edge contamination, subtle loop mismatch, or uncertain action readability.
- **Pass:** deterministic gates pass, visual identity and motion pass, and engine playback is verified.
