# codex-skills

Reusable Codex skills for development environments, automation, and project
workflows.

## Available skill

### `setup-godot-devcontainer`

This skill inspects a new or existing Godot repository,
plans a reproducible GDScript or .NET Dev Container, shows diffs, safely merges a
small set of configuration files, and validates the result.

The default environment includes Godot 4.x, export templates, Node.js, Codex CLI,
uv, gdtoolkit, GitHub CLI, Git LFS, image tooling, SSH, and the VS Code CLI exposed
as `code-cli`. Godot downloads are architecture-specific and checksum-verified.

To use the skill from a Git checkout, install or link the
`skills/setup-godot-devcontainer` directory into your Codex skills directory, then
invoke `$setup-godot-devcontainer` in the target repository.

Run the bundled tests with:

```bash
python -m unittest discover -s skills/setup-godot-devcontainer/scripts/tests -v
```
