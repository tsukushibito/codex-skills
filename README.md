# codex-skills

Reusable Codex skills for development environments, automation, and project
workflows.

## Available skills

### `setup-godot-devcontainer`

This skill inspects a new or existing Godot repository,
plans a reproducible GDScript or .NET Dev Container, shows diffs, safely merges a
small set of configuration files, and validates the result.

The default environment includes Godot 4.x, export templates, Node.js, Codex CLI,
uv, gdtoolkit, GitHub CLI, Git LFS, image tooling, SSH, and the VS Code CLI exposed
as `code-cli`. Optional NVIDIA inference GPU access uses a separate persistent
model cache, while managed task worktrees default to a locked container-native
volume. Godot downloads are architecture-specific and checksum-verified. Creation
and modification require explicit approval of every configurable choice before
planning and approval of the resolved plan before applying it.

To use the skill from a Git checkout, install or link the
`skills/setup-godot-devcontainer` directory into your Codex skills directory, then
invoke `$setup-godot-devcontainer` in the target repository.

Run the bundled tests with:

```bash
python -m unittest discover -s skills/setup-godot-devcontainer/scripts/tests -v
```

### `design-build-validate-ui`

This skill designs, critiques, implements, and visually validates new or existing
UI across games, web, desktop, and mobile. It routes evaluation, design, and
implementation requests separately; starts existing-UI work from the actual
render; starts greenfield work from users, tasks, states, devices, and inputs; and
requires implemented screens to re-enter a render-inspect-correct loop.

Install it with the bundled Codex skill installer:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo tsukushibito/codex-skills \
  --path skills/design-build-validate-ui
```

Invoke it as `$design-build-validate-ui`.
