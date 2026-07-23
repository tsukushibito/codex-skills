# Options

The bundled command defaults to an all-in development profile. Disable a tool only
when the target repository does not need it; `verify_env.sh` checks only the tools
selected at generation time.

| Choice | Default | CLI option | Effect |
|---|---|---|---|
| Project flavor | Detect, otherwise GDScript | `--flavor auto|gdscript|dotnet` | .NET adds the Dev Container .NET feature and uses mono Godot assets. |
| Project directory | The only detected project, otherwise `.` | `--project-dir PATH` | Sets the relative `project.godot` location. |
| Architectures | `amd64,arm64` | `--architectures LIST` | Limits declared/tested build platforms. Godot URLs remain architecture-specific. |
| SSH | VS Code forwarding | `--ssh-mode vscode|fixed|off` | `vscode` forwards container port 22 without a fixed host binding. |
| Fixed SSH port | None | `--ssh-mode fixed --ssh-port PORT` | Adds a loopback-only Docker host mapping. |
| Optional tool | Enabled | `--disable-tool NAME` | Names: `github-cli`, `git-lfs`, `image-tools`, `ssh`, `vscode-cli`. Repeat as needed. |

Version options are `--godot-version`, `--node-version`, `--codex-version`,
`--uv-version`, `--gdtoolkit-version`, and `--vscode-version`. Supplying one means
the user requires that exact version. Omitting it resolves the latest appropriate
stable channel once and freezes the result in the lock file. A numeric Godot 4.x
version such as `4.7.1` is normalized to its `4.7.1-stable` release tag.

The VS Code package is installed from Microsoft's Debian repository and intentionally
exposed as `code-cli`. This avoids confusing it with a host or editor-provided
`code` command. Use `code-cli --version` and other standard VS Code CLI options in
the container.

`--resolved-toolchain PATH` reuses a compatible lock-shaped JSON file. Use it for
offline/repeat generation only after reviewing its provenance and architecture
coverage.
