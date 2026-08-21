# Validation

Validation is intentionally layered.

1. `validate --mode static` checks required paths, JSON/JSONC, lock schema,
   architecture declarations, Godot SHA-256 values, required Codex trust settings,
   storage lock consistency, exact purpose-specific mounts, inference environment,
   optional browser ports/mounts/environment/seccomp/MCP/locks, the active
   instruction link, and shell syntax when Bash is present and executable.
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
user-explicit version pins. In NVIDIA mode it requires `nvidia-smi` and reports
the visible GPU name, memory, and driver version; it does not infer that a
project-specific CUDA framework is installed. The Godot script always performs a
headless editor import. It runs a five-second main-scene smoke check only when
`run/main_scene` is configured.

In worktree-volume mode, environment validation also runs
`scripts/dev/manage_worktree.sh verify`, so an unlocked `.worktree` entry fails the
container check. In NVIDIA mode it verifies that `$INFERENCE_CACHE_DIR` is writable.
Static validation rejects a broad `/home/vscode/.cache` mount, missing or extra
worktree/inference mounts, cache variables that disagree with the lock, `HF_HOME`
override, a missing storage policy, or a missing link in the active root Codex
instruction file.

With the ChatGPT browser enabled, environment validation checks Google Chrome
stable without `--no-sandbox`, launches the Chrome channel through Playwright,
checks the exact E2E and MCP package pins, and verifies the stable MCP launcher.
It does not log in to ChatGPT or inspect profile contents. `postStart` requires
`DEVCONTAINER_DESKTOP_PASSWORD`; a missing password fails the noVNC desktop rather
than starting an unauthenticated listener. See
[chatgpt-browser.md](chatgpt-browser.md) for manual login and lock handling.

NVIDIA mode is required, not best-effort. A failure while Docker creates the
container usually means the host lacks a compatible NVIDIA driver or Docker GPU
runtime. A later `nvidia-smi` failure means the requested device or driver utility
was not exposed. Keep `LIBGL_ALWAYS_SOFTWARE=1`; this profile validates inference
GPU access while retaining portable software-rendered Godot checks.
See the [Godot command-line reference](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)
for the headless display-driver behavior.

When the Dev Container CLI is unavailable, open the repository in VS Code and run
`Dev Containers: Rebuild and Reopen in Container`. Then execute the two commands
above in the integrated terminal.

Before a headless import in an existing repository, capture Git status. Afterwards,
review new or changed files. `.godot/`, `.import/`, and `.artifacts/` are ignored,
but required import sidecars can be repository-owned and must not be deleted or
silently discarded.
