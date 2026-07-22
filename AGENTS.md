# AGENTS.md

## Scope

This directory is the source of truth for the `my-codex-sprite-skill` Codex Skill. It was renamed from its prior installation; preserve its sprite-production behavior unless a task explicitly requests a functional change.

- Source: `/Users/john/Documents/slothsunolyric/my-codex-sprite-skill`
- Codex install: `~/.codex/skills/my-codex-sprite-skill`
- Skill name: the directory name, `SKILL.md` frontmatter `name`, install-directory name, and `$my-codex-sprite-skill` invocation must stay identical.
- Git: keep this as an independent repository with `origin` set to `git@github.com:jhwreal/my-codex-sprite-skill.git`. Commit or push only when the user explicitly requests it.

## Purpose and boundaries

Create, repair, normalize, validate, preview, and package consistent 2D game-character sprite animations. Preserve the gated canonical-master, per-action generation, deterministic processing, visual review, minimal repair, and approved-action packaging workflow defined in `SKILL.md`.

Inputs may include reference art, text descriptions, action specifications, raw action sheets, extracted frames, run directories, and target-engine settings. Outputs may include run manifests, normalized frames, sprite sheets, QC reports, previews, atlases, metadata, and engine-specific resources.

Do not add user media, generated runs, credentials, model weights, caches, or machine-specific absolute paths to this repository. Keep runtime outputs outside the Skill source directory.

## Dependencies

- Python 3.9 or newer.
- Pillow for the deterministic image scripts.
- The installed `$imagegen` Skill for visual generation, editing, and chroma-key removal.

Do not install packages or switch generation providers without user approval. Keep script behavior deterministic and preserve the `CODEX_HOME` fallback used to locate installed Skills.

## Change workflow

Before changing behavior, read `SKILL.md`, the relevant file under `references/`, and every affected script. Keep documentation, CLI help, metadata, and implementation synchronized. Add or update tests when changing script behavior; a pure metadata rename may use structural and smoke validation instead.

Validate at minimum with:

1. The `skill-creator` `quick_validate.py` check.
2. Python bytecode compilation for every bundled script.
3. `--help` smoke checks for all CLI scripts.
4. A temporary pilot-run smoke test when `prepare_sprite_run.py` or shared run creation changes.
5. A scan for stale Skill names, absolute paths, secrets, caches, and generated media.

Install only after source validation passes. Exclude `.git`, caches, virtual environments, tests, and local outputs from the Codex installation copy, then compare the installed files with the source files that are meant to ship.
