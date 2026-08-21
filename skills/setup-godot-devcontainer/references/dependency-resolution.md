# Dependency resolution and reproducibility

The planner resolves mutable channels before it proposes repository changes:

- Godot releases come from the official `godotengine/godot-builds` GitHub release.
  Both standard and .NET artifacts for `amd64`, `arm64`, and export templates must
  have release-provided SHA-256 digests. Docker verifies the selected downloads.
- uv comes from the official GHCR image. The generated multi-stage `FROM` uses an
  exact version plus the registry's immutable manifest digest; no remote install
  script is executed.
- Codex CLI resolves through the npm registry and is installed at an exact version.
- gdtoolkit resolves through PyPI and is installed at an exact version with uv.
- Node.js resolves to the latest LTS release and is passed exactly to the official
  Dev Container feature.
- VS Code resolves a common product version and the exact architecture-specific
  `code` Debian packages from Microsoft's repository metadata. Docker downloads
  those package URLs directly and verifies their published SHA-256 values.
- When selected, `@playwright/test` and `@playwright/mcp` are exact independent
  npm locks. Google Chrome comes from Google's signed stable APT channel during
  `postCreate` and intentionally remains a security-updated, non-pinned input.

The generated `.devcontainer/toolchain.lock.json` is the reviewable record. A later
container rebuild uses those exact primary versions. Values resolved because the
user omitted a version have `explicit: false`; environment verification displays
them but does not treat them as an enduring compatibility assertion. User-supplied
versions have `explicit: true` and are checked exactly by `verify_env.sh`.

This is deliberately not a complete hermetic Linux snapshot. The base image tag,
Debian package indices, Dev Container feature implementation, and transitive apt
packages can change. State this limitation when reproducibility is material. A
future stricter profile can pin an OCI base digest and feature artifact digests.

Primary sources:

- [Godot downloads and archive](https://godotengine.org/download/archive/)
- [Godot build releases](https://github.com/godotengine/godot-builds/releases)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
- [Node.js releases](https://nodejs.org/en/about/previous-releases)
- [VS Code on Linux](https://code.visualstudio.com/docs/setup/linux)
- [VS Code command line](https://code.visualstudio.com/docs/configure/command-line)
- [Development Container CLI](https://containers.dev/supporting.html)
