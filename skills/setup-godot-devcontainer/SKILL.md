---
name: setup-godot-devcontainer
description: Inspect, plan, create, merge, and validate a reproducible Dev Container for Godot 4.x GDScript or .NET projects. Use when Codex needs to add, migrate, repair, or audit `.devcontainer/`, Godot headless checks, container Codex policy, optional SSH, or a VS Code CLI exposed as `code-cli`, while preserving an existing repository and showing conflicts instead of overwriting files.
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
  Codex, generic asset tools, SSH, editor integration, and generic validation.
  Do not introduce Beads, worktree policy, review policy, game tests, telemetry,
  or production gates unless separately requested.
- Generate `.codex/config.toml` for every scaffold. This Dev Container profile is
  intentionally trusted and must set `approval_policy = "never"` and
  `sandbox_mode = "danger-full-access"`. Preserve unrelated project config keys.
- Never overwrite a complex existing file. Present its unified diff and require a
  manual merge. The only automatic merges are additive `.gitignore` and
  `.gitattributes` entries plus the two required top-level Codex policy keys.
- Do not expose SSH through a fixed host port unless the user selects that mode.
- Do not claim support for an architecture unless the selected Godot release has
  a checksum-bearing artifact for it.

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

### 2. Select only material options

Use the full profile by default: Godot, Node.js, Codex CLI, uv, gdtoolkit, GitHub
CLI, Git LFS, image tooling, SSH, and the VS Code CLI named `code-cli`.

Default to:

- latest stable Godot 4.x;
- latest Node.js LTS;
- latest stable Codex CLI, uv, gdtoolkit, and VS Code package;
- both `amd64` and `arm64`;
- VS Code-managed forwarding of container port 22;
- GDScript for a new project and detected flavor for an existing project.

Read [options.md](references/options.md) when changing the profile, pinning a
version, using .NET, changing architectures, or configuring SSH.

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

Keep the plan path outside the target repository. The CLI enforces this so the
planning phase remains read-only.

If the plan reports `conflict`, show the relevant diff and merge it with the user
or repository conventions. Never bypass conflict detection or replace the file
wholesale. Rerun `plan` after the manual merge.

### 4. Apply a conflict-free plan

Run:

```bash
python <skill>/scripts/godot_devcontainer.py apply --plan <temporary-plan.json>
```

The apply step checks every baseline hash before writing. If any source file has
changed, regenerate the plan. Do not edit the plan to simulate approval.

Review the resulting Git diff. Confirm that selected tools alone appear in the
generated verifier and that no credentials, host-specific paths, fixed ports, or
source-project workflow rules were added.

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
- selected flavor, architectures, tool profile, SSH mode, and exact resolved
  versions;
- static, container, headless import, and main-scene smoke results;
- skipped checks and the exact reason;
- remaining non-hermetic inputs, especially Debian package repository snapshots;
- the next VS Code or CLI command when container validation remains outstanding.

## Failure rules

- Stop before apply when the plan contains a conflict.
- Stop when a requested release lacks a SHA-256 digest or a requested architecture.
- Stop when a baseline changes between plan and apply.
- Keep static validation available when Docker or the Dev Container CLI is absent.
- A missing `project.godot` is acceptable for a new-project environment check, but
  headless project validation must fail until the project exists.
- A missing main scene skips only the runtime smoke test; it does not skip import.
