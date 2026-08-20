# Options

The bundled command defaults to an all-in development profile. Disable a tool only
when the target repository does not need it; `verify_env.sh` checks only the tools
selected at generation time.

## Required pre-plan confirmation

For every creation or modification, inspect first and then present one consolidated
checklist containing every row below. Show the proposed value even when it was
detected or is the command default. The user must explicitly approve every row
before `plan`; a single approval of the complete displayed checklist is sufficient.

| Decision | Values to confirm | Required context |
|---|---|---|
| Target and project directory | Repository target and relative `project.godot` directory | Show detected candidates; never guess when multiple projects exist. |
| Project flavor | `gdscript` or `dotnet` | Show the detected flavor and that .NET adds the .NET feature and mono Godot assets. |
| Architectures | Any supported subset of `amd64,arm64` | Confirm the complete list, not only deviations from the default. |
| SSH mode | `vscode`, `fixed`, or `off` | Explain dynamic VS Code forwarding versus a stable loopback-only host mapping. |
| Fixed SSH port | Port number | Applicable only to `fixed`; inspect likely host-port conflicts and propose an available value. |
| Optional tools | Enable or disable each of `github-cli`, `git-lfs`, `image-tools`, `ssh`, and `vscode-cli` | List every tool separately. SSH tool state must agree with SSH mode. |
| Version policy | Latest appropriate stable channel or an exact pin for Godot, Node.js, Codex CLI, uv, gdtoolkit, and VS Code | List every dependency separately. “Latest stable” is a valid explicit choice but resolves to an exact frozen value during planning. |
| Resolved toolchain reuse | No reuse, or a reviewed `--resolved-toolchain` path | State the provenance and architecture coverage when reuse is selected. |

After `plan`, present the exact resolved versions, checksums or image digest recorded
by the plan, the complete selection, and all file operations or diffs. Obtain a
second explicit approval before `apply`. Read-only inspection and validation that
do not create or modify files do not require these checkpoints.

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
