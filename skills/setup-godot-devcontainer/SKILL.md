---
name: setup-godot-devcontainer
description: Inspect, plan, create, merge, and validate a reproducible Dev Container for Godot 4.x GDScript or .NET projects. Use when Codex needs to add, migrate, repair, or audit `.devcontainer/`, Godot headless checks, container Codex policy, optional NVIDIA inference GPU access, optional SSH, or a VS Code CLI exposed as `code-cli`, while preserving an existing repository and showing conflicts instead of overwriting files.
---

# Setup Godot DevContainer

Create a reusable Godot development container without copying policies or
game-specific checks from a source repository. Use the bundled planner so that
version resolution, diffs, conflict handling, and validation follow one contract.

## Operating contract

- Inspect before planning. Read every applicable `AGENTS.md`, repository workflow,
  dirty-worktree state, existing Dev Container file, `project.godot`, `.csproj`,
  ignore rule, and validation script.
- Treat repository instructions and existing user content as authoritative.
- Keep the reusable scope limited to Godot, GDScript/.NET tooling, container-local
  Codex, generic asset tools, optional NVIDIA inference GPU access, SSH, editor
  integration, and generic validation.
  Do not introduce Beads, repository-specific review policy, game tests, telemetry,
  or production gates unless separately requested.
- Generate `.codex/config.toml` for every scaffold. This Dev Container profile is
  intentionally trusted and must set `approval_policy = "never"` and
  `sandbox_mode = "danger-full-access"`. Preserve unrelated project config keys.
- Never overwrite a complex existing file. Present its unified diff and require a
  manual merge. The only automatic merges are additive `.gitignore` and
  `.gitattributes` entries, the two required top-level Codex policy keys, and the
  marked storage-policy link in the active root Codex instruction file.
- Default to a container-native `.worktree` named volume. Generate the management
  helper, lock every managed worktree, and refuse dirty or forced removal. Use
  `--worktree-mode host` only when the user intentionally wants host-visible paths.
- Mount Godot cache only at `/home/vscode/.cache/godot`. In NVIDIA mode, mount a
  separate inference cache at `/home/vscode/.cache/inference`; never claim or mount
  all of `/home/vscode/.cache`.
- Do not expose SSH through a fixed host port unless the user selects that mode.
- Do not claim support for an architecture unless the selected Godot release has
  a checksum-bearing artifact for it.
- Before planning any creation or modification, show every applicable configurable
  choice and its proposed value in one consolidated checklist. Do not treat an
  omitted choice, a default, or the original creation request as confirmation.
- Planning is read-only, but applying is a separate approval boundary. Do not apply
  until the user has reviewed the resolved selections and proposed diffs.

## Workflow

### 1. Inspect the repository

Run:

```bash
python <skill>/scripts/godot_devcontainer.py inspect --target <repository> --json
```

Combine the result with repository instructions and Git status. For an existing
project, auto-detect .NET from C# project/source files and Godot settings. For a
new project, default to GDScript. If multiple `project.godot` files exist, select
the intended relative project directory before continuing.

### 2. Confirm every configurable choice

Before any `plan` that can create or modify the environment, read
[options.md](references/options.md) and follow its **Required pre-plan
confirmation** section. After inspection, show one consolidated checklist with
every applicable option, its proposed value, and the material consequence. This
includes detected or defaulted values, individual optional tools, and version
resolution policy.

The user may approve the whole displayed checklist in one reply or override
individual entries. Prior user choices may prefill the checklist, but every entry
must still appear in the consolidated confirmation. Do not run `plan` until the
user explicitly accepts all entries. Read-only `inspect` and `validate` requests
that do not create or modify files are exempt from this checkpoint.

### 3. Create a read-only plan

Run `plan`, passing only choices that differ from the defaults. Example:

```bash
python <skill>/scripts/godot_devcontainer.py plan \
  --target <repository> \
  --project-dir game \
  --output <plan-path-outside-repository.json>
```

The planner resolves unspecified latest versions once, writes their exact values,
Godot artifact checksums, and the uv image digest into the proposed
`.devcontainer/toolchain.lock.json`, and prints every diff. It does not modify the
target repository. Explicit version options are strict pins; latest-at-generation
values are frozen for rebuilds but are not represented as user compatibility
requirements. Read [dependency-resolution.md](references/dependency-resolution.md)
when version provenance, checksums, offline reuse, or upgrades matter.

After planning, show the complete resolved selection, including exact versions,
SSH host port when applicable, enabled tools, storage mode, and every proposed
file operation or diff. Require a second explicit user approval before `apply`.
If resolution or repository inspection changes a previously confirmed value,
return to the pre-plan checklist and reconfirm it.

Keep the plan path outside the target repository. The CLI enforces this so the
planning phase remains read-only.

If the plan reports `conflict`, show the relevant diff and merge it with the user
or repository conventions. Never bypass conflict detection or replace the file
wholesale. Rerun `plan` after the manual merge.

### 4. Apply an approved, conflict-free plan

Run:

```bash
python <skill>/scripts/godot_devcontainer.py apply --plan <temporary-plan.json>
```

The apply step checks every baseline hash before writing. If any source file has
changed, regenerate the plan. Do not edit the plan to simulate approval.

Run `apply` only after the user approves the displayed resolved plan. A general
request to create or set up the environment is not a substitute for the two
explicit confirmation checkpoints above.

Review the resulting Git diff. Confirm that selected tools alone appear in the
generated verifier and that no credentials, host-specific paths, fixed ports, or
source-project workflow rules were added.

Before creating a task worktree or downloading a model, read the generated
`.devcontainer/storage-policy.md`. In volume mode, use
`scripts/dev/manage_worktree.sh create <name> <branch> [start-point]` rather than
creating a worktree directly. NVIDIA projects must place See-Through, DWPose, and
other downloaded weights below `$INFERENCE_CACHE_DIR` or the generated framework
cache variables so the downloads persist in the inference volume.

### 5. Validate progressively

Run:

```bash
python <skill>/scripts/godot_devcontainer.py validate --target <repository> --mode auto
```

Static validation always runs. If the Dev Container CLI is installed, `auto`
builds/starts the container and runs environment plus Godot headless checks. If it
is unavailable, static validation remains a valid partial result and the script
prints exact VS Code steps. Read [validation.md](references/validation.md) when a
build fails, a project has no main scene, or generated Godot files need review.

### 6. Report the result

Report:

- created, safely merged, manually merged, and unchanged files;
- selected flavor, architectures, tool profile, GPU mode, SSH mode, and exact
  resolved versions, plus worktree/storage mode;
- static, container, headless import, and main-scene smoke results;
- skipped checks and the exact reason;
- remaining non-hermetic inputs, especially Debian package repository snapshots;
- the next VS Code or CLI command when container validation remains outstanding.

## Failure rules

- Stop before apply when the plan contains a conflict.
- Stop when a requested release lacks a SHA-256 digest or a requested architecture.
- Stop when NVIDIA mode is selected but the host cannot create a GPU-enabled
  container or `nvidia-smi` cannot see a GPU. Do not silently fall back to CPU.
- Stop when a baseline changes between plan and apply.
- Keep static validation available when Docker or the Dev Container CLI is absent.
- A missing `project.godot` is acceptable for a new-project environment check, but
  headless project validation must fail until the project exists.
- A missing main scene skips only the runtime smoke test; it does not skip import.
