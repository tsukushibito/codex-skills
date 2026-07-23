# Validation

Validation is intentionally layered.

1. `validate --mode static` checks required paths, JSON/JSONC, lock schema,
   architecture declarations, Godot SHA-256 values, required Codex trust settings,
   and shell syntax when Bash is present.
2. `validate --mode auto` performs static checks, then uses the Dev Container CLI
   when available. Without that CLI it succeeds as a partial validation and prints
   the VS Code workflow.
3. `validate --mode container` requires the CLI and fails if it is absent.

Container validation runs:

```bash
bash scripts/dev/verify_env.sh
bash scripts/dev/verify_godot_headless.sh
```

The environment script checks only the generated tool selection. It also enforces
user-explicit version pins. The Godot script always performs a headless editor
import. It runs a five-second main-scene smoke check only when `run/main_scene` is
configured.

When the Dev Container CLI is unavailable, open the repository in VS Code and run
`Dev Containers: Rebuild and Reopen in Container`. Then execute the two commands
above in the integrated terminal.

Before a headless import in an existing repository, capture Git status. Afterwards,
review new or changed files. `.godot/`, `.import/`, and `.artifacts/` are ignored,
but required import sidecars can be repository-owned and must not be deleted or
silently discarded.
