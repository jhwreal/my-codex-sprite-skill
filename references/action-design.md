# Common action design

Use these phase sequences as pose guidance, not rigid frame-count requirements. Adapt timing to the game's scale, speed, and combat feel.

## Idle

- neutral base;
- slight compression or breath-in;
- blink, small head motion, or material sway;
- return through a compatible pose.

Keep the silhouette quiet. Do not let idle read as walking, waving, attacking, or reacting.

## Walk

- contact;
- down;
- passing;
- up;
- opposite contact;
- repeat the mirrored leg cycle.

Keep hips and shoulders coherent. The planted foot should not slide unless the game style intentionally exaggerates it.

## Run

- contact;
- compression;
- passing;
- launch;
- airborne or extended stride;
- opposite contact and recovery.

Require clear alternation, forward lean, and weight transfer. Avoid a walk cycle merely played faster.

## Light attack

- readable ready pose;
- anticipation;
- acceleration;
- contact or peak extension;
- follow-through;
- recovery toward the locomotion or idle stance.

Keep weapon length and grip constant. Put sword trails, projectiles, dust, and hit flashes on separate aligned effects sheets.

## Heavy attack

- longer anticipation;
- deep weight shift;
- explosive acceleration;
- strong contact pose;
- overshoot;
- longer recovery and settle.

Favor fewer strong key poses over many ambiguous frames.

## Jump

- crouch or anticipation;
- takeoff;
- rising pose;
- apex;
- falling pose;
- landing compression;
- settle when the game needs it.

For gameplay-controlled air time, export rise, apex/fall, and landing as separate states instead of forcing one fixed loop.

## Hurt

- impact recognition;
- recoil or compression;
- peak reaction;
- recovery or transition to knockdown.

Avoid introducing unexplained damage effects or changing costume damage unless requested.

## Death or defeat

- hit or loss of balance;
- fall progression;
- ground contact;
- settle into a stable final frame.

Use a non-looping sequence. Hold the last frame in-engine instead of duplicating it many times.

## Directional sets

Create one direction first. Mirror only symmetric characters. Generate separate directions for asymmetric outfits, shields, weapons, text, emblems, hair parts, scars, lighting, or gameplay-dependent handedness.
