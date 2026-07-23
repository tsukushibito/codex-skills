#!/usr/bin/env python3
"""Plan, apply, and validate a reproducible Godot Dev Container scaffold.

The planner is deliberately read-only with respect to the target repository.  It
stores complete candidate files and baseline hashes in a JSON plan.  The apply
step refuses the entire plan if a conflict or a changed baseline is present.
"""

from __future__ import annotations

import argparse
import difflib
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "scaffold"
PLAN_SCHEMA = 1
LOCK_SCHEMA = 1
SAFE_MERGE_PATHS = {".gitignore", ".gitattributes", ".codex/config.toml"}
OPTIONAL_TOOLS = {"github-cli", "git-lfs", "image-tools", "ssh", "vscode-cli"}
ALL_ARCHITECTURES = {"amd64", "arm64"}


class SetupError(RuntimeError):
    """Expected, user-actionable setup failure."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.is_file() else None


def normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def http_bytes(url: str, headers: dict[str, str] | None = None) -> tuple[bytes, Any]:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "setup-godot-devcontainer-skill",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(), response.headers
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SetupError(f"Could not resolve dependency metadata from {url}: {exc}") from exc


def http_json(url: str) -> Any:
    body, _ = http_bytes(url)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SetupError(f"Dependency endpoint returned invalid JSON: {url}") from exc


def version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers[:4])


def release_assets(release: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for asset in release.get("assets", []):
        digest = str(asset.get("digest") or "")
        if not digest.startswith("sha256:"):
            continue
        result[str(asset["name"])] = {
            "url": str(asset["browser_download_url"]),
            "sha256": digest.removeprefix("sha256:"),
        }
    return result


def resolve_godot(requested: str | None) -> dict[str, Any]:
    if requested:
        tag = requested.removeprefix("v")
        if re.fullmatch(r"4\.\d+(?:\.\d+)?", tag):
            tag += "-stable"
        release = http_json(
            "https://api.github.com/repos/godotengine/godot-builds/releases/tags/"
            + urllib.parse.quote(tag)
        )
    else:
        releases = http_json(
            "https://api.github.com/repos/godotengine/godot-builds/releases?per_page=100"
        )
        stable = [
            release
            for release in releases
            if re.fullmatch(r"4\.\d+(?:\.\d+)?-stable", str(release.get("tag_name", "")))
            and not release.get("draft")
            and not release.get("prerelease")
        ]
        if not stable:
            raise SetupError("No stable Godot 4.x release was found.")
        release = max(stable, key=lambda item: version_tuple(str(item["tag_name"])))

    version = str(release["tag_name"]).removeprefix("v")
    assets = release_assets(release)
    required_names = {
        "gdscript": {
            "amd64": f"Godot_v{version}_linux.x86_64.zip",
            "arm64": f"Godot_v{version}_linux.arm64.zip",
            "templates": f"Godot_v{version}_export_templates.tpz",
        },
        "dotnet": {
            "amd64": f"Godot_v{version}_mono_linux_x86_64.zip",
            "arm64": f"Godot_v{version}_mono_linux_arm64.zip",
            "templates": f"Godot_v{version}_mono_export_templates.tpz",
        },
    }
    selected: dict[str, Any] = {}
    for flavor, names in required_names.items():
        selected[flavor] = {}
        for key, name in names.items():
            if name not in assets:
                raise SetupError(
                    f"Godot release {version} lacks a SHA-256 digest for required asset {name}."
                )
            selected[flavor][key] = {"name": name, **assets[name]}
    return {
        "version": version,
        "source": str(release.get("html_url") or "https://github.com/godotengine/godot-builds"),
        "explicit": bool(requested),
        "assets": selected,
    }


def resolve_npm(package: str, requested: str | None) -> dict[str, Any]:
    encoded = urllib.parse.quote(package, safe="")
    if requested:
        normalized = requested.removeprefix("v")
        metadata = http_json(f"https://registry.npmjs.org/{encoded}/{urllib.parse.quote(normalized)}")
    else:
        metadata = http_json(f"https://registry.npmjs.org/{encoded}/latest")
    version = str(metadata["version"])
    return {
        "version": version,
        "source": f"https://www.npmjs.com/package/{package}/v/{version}",
        "explicit": bool(requested),
        "integrity": str(metadata.get("dist", {}).get("integrity", "")),
    }


def resolve_pypi(package: str, requested: str | None) -> dict[str, Any]:
    suffix = f"/{urllib.parse.quote(requested)}" if requested else ""
    metadata = http_json(f"https://pypi.org/pypi/{package}{suffix}/json")
    version = str(metadata["info"]["version"])
    return {
        "version": version,
        "source": f"https://pypi.org/project/{package}/{version}/",
        "explicit": bool(requested),
    }


def resolve_node(requested: str | None) -> dict[str, Any]:
    releases = http_json("https://nodejs.org/dist/index.json")
    candidates = [item for item in releases if item.get("lts")]
    if requested:
        normalized = requested.removeprefix("v")
        candidates = [item for item in releases if str(item.get("version", "")).removeprefix("v") == normalized]
    if not candidates:
        raise SetupError(f"No matching Node.js LTS release was found for {requested or 'latest LTS'}.")
    release = max(candidates, key=lambda item: version_tuple(str(item["version"])))
    version = str(release["version"]).removeprefix("v")
    return {
        "version": version,
        "source": f"https://nodejs.org/dist/v{version}/",
        "explicit": bool(requested),
        "lts": release.get("lts"),
    }


def resolve_uv(requested: str | None) -> dict[str, Any]:
    if requested:
        normalized = requested.removeprefix("v")
        release = http_json(
            "https://api.github.com/repos/astral-sh/uv/releases/tags/"
            + urllib.parse.quote(normalized)
        )
    else:
        release = http_json("https://api.github.com/repos/astral-sh/uv/releases/latest")
    version = str(release["tag_name"]).removeprefix("v")
    token_data = http_json(
        "https://ghcr.io/token?service=ghcr.io&scope=repository:astral-sh/uv:pull"
    )
    token = str(token_data["token"])
    _, headers = http_bytes(
        f"https://ghcr.io/v2/astral-sh/uv/manifests/{urllib.parse.quote(version)}",
        {
            "Authorization": f"Bearer {token}",
            "Accept": ", ".join(
                [
                    "application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json",
                ]
            ),
        },
    )
    digest = headers.get("Docker-Content-Digest")
    if not digest or not str(digest).startswith("sha256:"):
        raise SetupError("GHCR did not return an immutable digest for the uv image.")
    return {
        "version": version,
        "source": str(release.get("html_url") or "https://github.com/astral-sh/uv"),
        "explicit": bool(requested),
        "image": f"ghcr.io/astral-sh/uv:{version}@{digest}",
        "digest": str(digest),
    }


def parse_debian_packages(raw: bytes) -> list[dict[str, str]]:
    text = gzip.decompress(raw).decode("utf-8", errors="replace")
    records: list[dict[str, str]] = []
    for stanza in text.split("\n\n"):
        record: dict[str, str] = {}
        for line in stanza.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                record[key] = value
        if record:
            records.append(record)
    return records


def resolve_vscode(requested: str | None, architectures: Iterable[str]) -> dict[str, Any]:
    packages: dict[str, dict[str, str]] = {}
    for architecture in architectures:
        raw, _ = http_bytes(
            f"https://packages.microsoft.com/repos/code/dists/stable/main/binary-{architecture}/Packages.gz"
        )
        available = [record for record in parse_debian_packages(raw) if record.get("Package") == "code"]
        if requested:
            available = [
                record
                for record in available
                if record.get("Version") == requested or record.get("Version", "").startswith(f"{requested}-")
            ]
        if not available:
            raise SetupError(f"VS Code package {requested or 'latest'} is unavailable for {architecture}.")
        selected = max(available, key=lambda record: version_tuple(record["Version"]))
        if not re.fullmatch(r"[0-9a-fA-F]{64}", selected.get("SHA256", "")):
            raise SetupError(f"VS Code package metadata lacks SHA-256 for {architecture}.")
        filename = selected.get("Filename", "")
        if not filename:
            raise SetupError(f"VS Code package metadata lacks a filename for {architecture}.")
        packages[architecture] = {
            "version": selected["Version"],
            "url": "https://packages.microsoft.com/repos/code/" + filename.lstrip("/"),
            "sha256": selected["SHA256"].lower(),
        }
    product_versions = {item["version"].split("-", 1)[0] for item in packages.values()}
    if len(product_versions) != 1:
        raise SetupError(f"VS Code has no common product version for requested architectures: {packages}")
    version = next(iter(product_versions))
    return {
        "version": version,
        "source": "https://packages.microsoft.com/repos/code",
        "explicit": bool(requested),
        "packages": packages,
    }


def load_resolution(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"Could not read resolved toolchain file {path}: {exc}") from exc
    if result.get("schema_version") != LOCK_SCHEMA or not isinstance(result.get("tools"), dict):
        raise SetupError("Resolved toolchain file has an unsupported schema.")
    return result


def resolve_toolchain(args: argparse.Namespace, architectures: list[str], enabled: set[str]) -> dict[str, Any]:
    if args.resolved_toolchain:
        lock = load_resolution(Path(args.resolved_toolchain).resolve())
        lock["architectures"] = architectures
        return lock
    tools: dict[str, Any] = {
        "godot": resolve_godot(args.godot_version),
        "node": resolve_node(args.node_version),
        "codex": resolve_npm("@openai/codex", args.codex_version),
        "uv": resolve_uv(args.uv_version),
        "gdtoolkit": resolve_pypi("gdtoolkit", args.gdtoolkit_version),
    }
    if "vscode-cli" in enabled:
        tools["vscode-cli"] = resolve_vscode(args.vscode_version, architectures)
    return {
        "schema_version": LOCK_SCHEMA,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "architectures": architectures,
        "tools": tools,
        "notes": [
            "Versions resolved from latest channels are frozen by this file.",
            "Debian apt dependencies are repository snapshots, not hermetic content locks.",
        ],
    }


def detect_projects(target: Path) -> list[str]:
    projects: list[str] = []
    for path in target.rglob("project.godot"):
        if any(part in {".git", ".worktree", ".godot"} for part in path.relative_to(target).parts):
            continue
        projects.append(path.parent.relative_to(target).as_posix() or ".")
    return sorted(projects)


def detect_dotnet(target: Path, project_dir: str) -> bool:
    root = target / project_dir
    if list(root.glob("*.csproj")) or list(root.glob("*.sln")) or list(root.rglob("*.cs")):
        return True
    project_file = root / "project.godot"
    if project_file.is_file():
        text = project_file.read_text(encoding="utf-8", errors="replace")
        return "dotnet" in text.lower() or "mono" in text.lower()
    return False


def inspect_target(target: Path) -> dict[str, Any]:
    if not target.is_dir():
        raise SetupError(f"Target directory does not exist: {target}")
    projects = detect_projects(target)
    devcontainer_files = []
    devcontainer = target / ".devcontainer"
    if devcontainer.is_dir():
        devcontainer_files = [path.relative_to(target).as_posix() for path in devcontainer.rglob("*") if path.is_file()]
    inspected_files = [
        target / relative
        for relative in devcontainer_files
        if relative.endswith((".json", ".sh")) or Path(relative).name == "Dockerfile"
    ]
    verify_script = target / "scripts" / "dev" / "verify_env.sh"
    if verify_script.is_file():
        inspected_files.append(verify_script)
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in inspected_files
    )
    architecture_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in inspected_files
        if path.name == "Dockerfile" or path.suffix == ".sh"
    )
    findings: list[str] = []
    has_x86 = bool(re.search(r"(?:x86_64|amd64)", architecture_text, re.IGNORECASE))
    has_arm64 = bool(re.search(r"(?:aarch64|arm64)", architecture_text, re.IGNORECASE))
    has_targetarch = "TARGETARCH" in architecture_text
    if has_x86 and not has_arm64:
        findings.append("Existing setup appears fixed to x86_64/amd64; declare architecture support explicitly.")
    if has_x86 and has_arm64 and not has_targetarch:
        findings.append("Multiple architecture strings exist but Docker TARGETARCH selection was not found.")
    if not has_targetarch and re.search(
        r"(?:https?://|Godot[^\s]*)[^\s\"']*(?:x86_64|amd64)", architecture_text, re.IGNORECASE
    ):
        findings.append("An x86_64-specific download or binary path is not guarded by Docker TARGETARCH.")
    if re.search(r"curl\b[^\n|]*(?:\||>)\s*(?:ba)?sh\b", combined):
        findings.append("A remote install script invocation was found; replace it with a pinned artifact.")
    fixed_ssh = re.search(r"(?:(127\.0\.0\.1|0\.0\.0\.0):)?\d{2,5}:22\b", combined)
    if fixed_ssh:
        findings.append("A fixed SSH host port was found; make fixed publishing optional and configurable.")
        if fixed_ssh.group(1) != "127.0.0.1":
            findings.append("The fixed SSH host-port mapping is not explicitly loopback-only.")
    codex_policy: dict[str, Any] | None = None
    codex_path = target / ".codex" / "config.toml"
    if codex_path.is_file():
        try:
            parsed_codex = tomllib.loads(codex_path.read_text(encoding="utf-8"))
            codex_policy = {
                "approval_policy": parsed_codex.get("approval_policy"),
                "sandbox_mode": parsed_codex.get("sandbox_mode"),
            }
        except tomllib.TOMLDecodeError:
            findings.append("Existing .codex/config.toml is not valid TOML.")
    return {
        "target": str(target),
        "projects": projects,
        "dotnet_projects": [project for project in projects if detect_dotnet(target, project)],
        "existing_devcontainer_files": sorted(devcontainer_files),
        "has_codex_config": (target / ".codex" / "config.toml").is_file(),
        "git_repository": (target / ".git").exists(),
        "architecture_signals": {
            "x86_64_or_amd64": has_x86,
            "arm64_or_aarch64": has_arm64,
            "docker_targetarch": has_targetarch,
        },
        "codex_policy": codex_policy,
        "findings": findings,
    }


def template(name: str, values: dict[str, str]) -> str:
    path = TEMPLATE_ROOT / name
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"Missing skill template {path}: {exc}") from exc
    for key, value in values.items():
        content = content.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", content)))
    if unresolved:
        raise SetupError(f"Template {name} has unresolved values: {', '.join(unresolved)}")
    return normalize_newlines(content).rstrip() + "\n"


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def merge_lines(existing: str, managed: str, label: str) -> str:
    existing = normalize_newlines(existing)
    missing = [line for line in managed.splitlines() if line.strip() and line not in existing.splitlines()]
    if not missing:
        return existing if existing.endswith("\n") else existing + "\n"
    prefix = "" if not existing.strip() else existing.rstrip() + "\n\n"
    return prefix + f"# {label}\n" + "\n".join(missing) + "\n"


def merge_codex_config(existing: str) -> str:
    """Set required top-level policy keys while preserving unrelated TOML text."""
    lines = normalize_newlines(existing).splitlines()
    wanted = {
        "approval_policy": 'approval_policy = "never"',
        "sandbox_mode": 'sandbox_mode = "danger-full-access"',
    }
    seen: set[str] = set()
    section_seen = False
    output: list[str] = []
    assignment = re.compile(r"^\s*(approval_policy|sandbox_mode)\s*=")
    for line in lines:
        if re.match(r"^\s*\[", line):
            if not section_seen:
                for key, rendered in wanted.items():
                    if key not in seen:
                        output.append(rendered)
                        seen.add(key)
                if output and output[-1] != "":
                    output.append("")
            section_seen = True
        match = assignment.match(line) if not section_seen else None
        if match:
            key = match.group(1)
            if key not in seen:
                output.append(wanted[key])
                seen.add(key)
            continue
        output.append(line)
    if not section_seen:
        for key, rendered in wanted.items():
            if key not in seen:
                output.append(rendered)
    return "\n".join(output).rstrip() + "\n"


def chosen_project(target: Path, requested: str | None) -> str:
    if requested:
        project = Path(requested).as_posix().strip("/") or "."
        if Path(project).is_absolute() or ".." in Path(project).parts:
            raise SetupError("--project-dir must be a relative path inside the target repository.")
        return project
    projects = detect_projects(target)
    if len(projects) > 1:
        raise SetupError("Multiple project.godot files found; pass --project-dir explicitly.")
    return projects[0] if projects else "."


def build_candidates(
    target: Path,
    project_dir: str,
    flavor: str,
    architectures: list[str],
    enabled: set[str],
    ssh_mode: str,
    ssh_port: int | None,
    lock: dict[str, Any],
) -> dict[str, str]:
    tools = lock["tools"]
    godot = tools["godot"]
    assets = godot["assets"][flavor]
    node = tools["node"]
    dotnet_feature = (
        ',\n    "ghcr.io/devcontainers/features/dotnet:2": {"version": "8.0"}'
        if flavor == "dotnet"
        else ""
    )
    forward_ports: list[int] = []
    ports_attributes: dict[str, Any] = {}
    run_args: list[str] = []
    if ssh_mode == "vscode" and "ssh" in enabled:
        forward_ports = [22]
        ports_attributes = {"22": {"label": "SSH", "onAutoForward": "notify"}}
    elif ssh_mode == "fixed" and "ssh" in enabled:
        assert ssh_port is not None
        run_args = ["-p", f"127.0.0.1:{ssh_port}:22"]

    mounts = [
        "source=${localWorkspaceFolderBasename}-codex,target=/home/vscode/.codex,type=volume",
        "source=${localWorkspaceFolderBasename}-godot-cache,target=/home/vscode/.cache,type=volume",
    ]
    if "github-cli" in enabled:
        mounts.append("source=${localWorkspaceFolderBasename}-gh,target=/home/vscode/.config/gh,type=volume")
    if "vscode-cli" in enabled:
        mounts.append("source=${localWorkspaceFolderBasename}-vscode-data,target=/home/vscode/.vscode-data,type=volume")
    if "ssh" in enabled:
        mounts.append("source=${localWorkspaceFolderBasename}-ssh,target=/home/vscode/.ssh,type=volume")

    build_args: dict[str, str] = {
        "UV_IMAGE": tools["uv"]["image"],
        "GODOT_VERSION": godot["version"],
        "GODOT_FLAVOR": flavor,
        "GODOT_TEMPLATES_URL": assets["templates"]["url"],
        "GODOT_TEMPLATES_SHA256": assets["templates"]["sha256"],
        "INSTALL_GITHUB_CLI": str("github-cli" in enabled).lower(),
        "INSTALL_GIT_LFS": str("git-lfs" in enabled).lower(),
        "INSTALL_IMAGE_TOOLS": str("image-tools" in enabled).lower(),
        "INSTALL_SSH": str("ssh" in enabled).lower(),
        "INSTALL_VSCODE_CLI": str("vscode-cli" in enabled).lower(),
        "VSCODE_AMD64_URL": tools.get("vscode-cli", {}).get("packages", {}).get("amd64", {}).get("url", ""),
        "VSCODE_AMD64_SHA256": tools.get("vscode-cli", {}).get("packages", {}).get("amd64", {}).get("sha256", ""),
        "VSCODE_ARM64_URL": tools.get("vscode-cli", {}).get("packages", {}).get("arm64", {}).get("url", ""),
        "VSCODE_ARM64_SHA256": tools.get("vscode-cli", {}).get("packages", {}).get("arm64", {}).get("sha256", ""),
    }
    for architecture in architectures:
        prefix = architecture.upper()
        build_args[f"GODOT_{prefix}_URL"] = assets[architecture]["url"]
        build_args[f"GODOT_{prefix}_SHA256"] = assets[architecture]["sha256"]
    devcontainer = {
        "name": "Godot Development",
        "build": {"dockerfile": "Dockerfile", "context": "..", "args": build_args},
        "features": {
            "ghcr.io/devcontainers/features/node:1": {"version": node["version"]}
        },
        "remoteUser": "vscode",
        "workspaceFolder": "/workspaces/${localWorkspaceFolderBasename}",
        "init": True,
        "hostRequirements": {"cpus": 2, "memory": "4gb"},
        "containerEnv": {
            "CODEX_HOME": "/home/vscode/.codex",
            "GODOT_PROJECT_DIR": project_dir,
            "GODOT_ARTIFACT_DIR": ".artifacts/godot",
            "LIBGL_ALWAYS_SOFTWARE": "1",
        },
        "remoteEnv": {"PATH": "/home/vscode/.local/bin:${containerEnv:PATH}"},
        "mounts": mounts,
        "forwardPorts": forward_ports,
        "portsAttributes": ports_attributes,
        "runArgs": run_args,
        "postCreateCommand": "bash .devcontainer/post-create.sh",
        "postStartCommand": "bash .devcontainer/start-sshd.sh",
        "customizations": {
            "vscode": {"extensions": ["geequlim.godot-tools"]}
        },
    }
    if flavor == "dotnet":
        devcontainer["features"]["ghcr.io/devcontainers/features/dotnet:2"] = {"version": "8.0"}

    enabled_list = sorted(enabled)
    lock = dict(lock)
    lock.update(
        {
            "flavor": flavor,
            "project_dir": project_dir,
            "enabled_tools": enabled_list,
            "ssh": {"mode": ssh_mode, "host_port": ssh_port},
        }
    )
    values = {
        "ENABLED_TOOLS_JSON": json.dumps(enabled_list),
        "PROJECT_DIR": project_dir,
        "GODOT_VERSION": godot["version"],
        "GODOT_FLAVOR": flavor,
        "CODEX_VERSION": tools["codex"]["version"],
        "GDTOOLKIT_VERSION": tools["gdtoolkit"]["version"],
        "NODE_VERSION": node["version"],
        "UV_VERSION": tools["uv"]["version"],
        "UV_IMAGE": tools["uv"]["image"],
        "VSCODE_VERSION": tools.get("vscode-cli", {}).get("version", ""),
        "SUPPORTED_ARCH_PATTERN": "|".join(architectures),
        "ARCHIVE_CASES": "\n".join(
            f'  {architecture})\n    archive_url="$GODOT_{architecture.upper()}_URL"\n'
            f'    archive_sha256="$GODOT_{architecture.upper()}_SHA256"\n    ;;'
            for architecture in architectures
        ),
        "INSTALL_GITHUB_CLI": str("github-cli" in enabled).lower(),
        "INSTALL_GIT_LFS": str("git-lfs" in enabled).lower(),
        "INSTALL_IMAGE_TOOLS": str("image-tools" in enabled).lower(),
        "INSTALL_SSH": str("ssh" in enabled).lower(),
        "INSTALL_VSCODE_CLI": str("vscode-cli" in enabled).lower(),
    }
    candidates = {
        ".devcontainer/devcontainer.json": json_text(devcontainer),
        ".devcontainer/toolchain.lock.json": json_text(lock),
        ".devcontainer/Dockerfile": template("Dockerfile.tmpl", values),
        ".devcontainer/install-godot.sh": template("install-godot.sh.tmpl", values),
        ".devcontainer/post-create.sh": template("post-create.sh.tmpl", values),
        ".devcontainer/start-sshd.sh": template("start-sshd.sh.tmpl", values),
        "scripts/dev/verify_env.sh": template("verify_env.sh.tmpl", values),
        "scripts/dev/verify_godot_headless.sh": template("verify_godot_headless.sh.tmpl", values),
        ".codex/config.toml": 'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
        ".gitignore": template("gitignore.fragment", values),
        ".gitattributes": template("gitattributes.fragment", values),
    }
    return candidates


def merged_candidate(relative: str, existing: str, generated: str) -> str:
    if relative == ".gitignore":
        return merge_lines(existing, generated, "setup-godot-devcontainer")
    if relative == ".gitattributes":
        return merge_lines(existing, generated, "setup-godot-devcontainer")
    if relative == ".codex/config.toml":
        return merge_codex_config(existing)
    return generated


def unified_diff(relative: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            normalize_newlines(before).splitlines(keepends=True),
            normalize_newlines(after).splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )


def create_plan(args: argparse.Namespace) -> dict[str, Any]:
    target = Path(args.target).resolve()
    if not target.is_dir():
        raise SetupError(f"Target directory does not exist: {target}")
    project_dir = chosen_project(target, args.project_dir)
    flavor = args.flavor
    if flavor == "auto":
        flavor = "dotnet" if detect_dotnet(target, project_dir) else "gdscript"
    architectures = [item.strip() for item in args.architectures.split(",") if item.strip()]
    if not architectures or set(architectures) - ALL_ARCHITECTURES:
        raise SetupError("--architectures accepts only amd64 and arm64.")
    if len(architectures) != len(set(architectures)):
        raise SetupError("--architectures must not contain duplicates.")
    enabled = set(OPTIONAL_TOOLS)
    enabled -= set(args.disable_tool)
    if args.ssh_mode == "off":
        enabled.discard("ssh")
    if args.ssh_mode == "fixed" and args.ssh_port is None:
        raise SetupError("--ssh-port is required with --ssh-mode fixed.")
    if args.ssh_port is not None and not 1 <= args.ssh_port <= 65535:
        raise SetupError("--ssh-port must be between 1 and 65535.")
    if args.ssh_mode != "fixed" and args.ssh_port is not None:
        raise SetupError("--ssh-port is only valid with --ssh-mode fixed.")

    lock = resolve_toolchain(args, architectures, enabled)
    candidates = build_candidates(
        target, project_dir, flavor, architectures, enabled, args.ssh_mode, args.ssh_port, lock
    )
    operations: list[dict[str, Any]] = []
    for relative, generated in candidates.items():
        path = target / relative
        before = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        baseline = file_hash(path)
        after = merged_candidate(relative, before, generated) if path.is_file() else generated
        if before == after:
            action = "unchanged"
        elif not path.exists():
            action = "create"
        elif relative in SAFE_MERGE_PATHS:
            action = "merge"
        else:
            action = "conflict"
        operations.append(
            {
                "path": relative,
                "action": action,
                "baseline_sha256": baseline,
                "content": after,
                "content_sha256": sha256_bytes(after.encode("utf-8")),
                "diff": unified_diff(relative, before, after),
            }
        )
    return {
        "schema_version": PLAN_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": str(target),
        "selection": {
            "project_dir": project_dir,
            "flavor": flavor,
            "architectures": architectures,
            "enabled_tools": sorted(enabled),
            "ssh_mode": args.ssh_mode,
            "ssh_port": args.ssh_port,
        },
        "operations": operations,
    }


def print_plan(plan: dict[str, Any]) -> None:
    selection = plan["selection"]
    print(
        f"Target: {plan['target']}\n"
        f"Godot flavor: {selection['flavor']}\n"
        f"Architectures: {', '.join(selection['architectures'])}\n"
        f"SSH mode: {selection['ssh_mode']}\n"
    )
    for operation in plan["operations"]:
        print(f"[{operation['action']}] {operation['path']}")
        if operation["diff"]:
            print(operation["diff"], end="" if operation["diff"].endswith("\n") else "\n")


def apply_plan(path: Path) -> list[str]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"Could not read plan {path}: {exc}") from exc
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise SetupError("Plan has an unsupported schema version.")
    target = Path(plan["target"]).resolve()
    operations = plan.get("operations", [])
    conflicts = [item["path"] for item in operations if item["action"] == "conflict"]
    if conflicts:
        raise SetupError(
            "Plan contains files requiring manual merge; no files were written: " + ", ".join(conflicts)
        )
    for item in operations:
        destination = (target / item["path"]).resolve()
        try:
            destination.relative_to(target)
        except ValueError as exc:
            raise SetupError(f"Plan path escapes target: {item['path']}") from exc
        if file_hash(destination) != item["baseline_sha256"]:
            raise SetupError(f"Baseline changed for {item['path']}; regenerate the plan. No files were written.")
        if sha256_bytes(item["content"].encode("utf-8")) != item["content_sha256"]:
            raise SetupError(f"Plan content hash is invalid for {item['path']}.")

    pending = [item for item in operations if item["action"] != "unchanged"]
    staged: list[tuple[Path, Path]] = []
    original_content: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        for item in pending:
            destination = target / item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            original_content[destination] = destination.read_bytes() if destination.is_file() else None
            handle, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(item["content"])
            staged.append((Path(temporary_name), destination))
        for temporary, destination in staged:
            os.replace(temporary, destination)
            replaced.append(destination)
    except Exception:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        for destination in reversed(replaced):
            before = original_content[destination]
            if before is None:
                destination.unlink(missing_ok=True)
                continue
            handle, restore_name = tempfile.mkstemp(prefix=f".{destination.name}.restore.", dir=destination.parent)
            with os.fdopen(handle, "wb") as stream:
                stream.write(before)
            os.replace(restore_name, destination)
        raise
    return [item["path"] for item in pending]


def strip_jsonc(value: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(value):
        char = value[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
        elif value[index : index + 2] == "//":
            index = value.find("\n", index)
            if index == -1:
                break
        elif value[index : index + 2] == "/*":
            end = value.find("*/", index + 2)
            if end == -1:
                raise SetupError("Unclosed block comment in JSONC file.")
            index = end + 2
        else:
            output.append(char)
            index += 1
    return re.sub(r",\s*([}\]])", r"\1", "".join(output))


def run_checked(command: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command, cwd=cwd, text=True, capture_output=True, timeout=1800, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode == 0, output


def static_validate(target: Path) -> list[str]:
    errors: list[str] = []
    required = [
        ".devcontainer/devcontainer.json",
        ".devcontainer/Dockerfile",
        ".devcontainer/install-godot.sh",
        ".devcontainer/post-create.sh",
        ".devcontainer/start-sshd.sh",
        ".devcontainer/toolchain.lock.json",
        ".codex/config.toml",
        "scripts/dev/verify_env.sh",
        "scripts/dev/verify_godot_headless.sh",
    ]
    for relative in required:
        if not (target / relative).is_file():
            errors.append(f"missing {relative}")
    if errors:
        return errors
    config: dict[str, Any] | None = None
    lock: dict[str, Any] | None = None
    try:
        config = json.loads(strip_jsonc((target / ".devcontainer/devcontainer.json").read_text(encoding="utf-8")))
        if config.get("build", {}).get("dockerfile") != "Dockerfile":
            errors.append("devcontainer build.dockerfile must reference Dockerfile")
    except (json.JSONDecodeError, SetupError) as exc:
        errors.append(f"invalid .devcontainer/devcontainer.json: {exc}")
    try:
        lock = json.loads((target / ".devcontainer/toolchain.lock.json").read_text(encoding="utf-8"))
        if lock.get("schema_version") != LOCK_SCHEMA:
            errors.append("unsupported toolchain lock schema")
        if set(lock.get("architectures", [])) - ALL_ARCHITECTURES:
            errors.append("toolchain lock contains unsupported architecture")
        if not lock.get("architectures") or len(lock["architectures"]) != len(set(lock["architectures"])):
            errors.append("toolchain lock must contain one or more unique architectures")
        if lock.get("flavor") not in {"gdscript", "dotnet"}:
            errors.append("toolchain lock has an invalid Godot flavor")
        required_tools = {"godot", "node", "codex", "uv", "gdtoolkit"}
        required_tools.update(set(lock.get("enabled_tools", [])) & {"vscode-cli"})
        missing_tools = required_tools - set(lock.get("tools", {}))
        if missing_tools:
            errors.append("toolchain lock is missing tools: " + ", ".join(sorted(missing_tools)))
        godot_assets = lock.get("tools", {}).get("godot", {}).get("assets", {})
        selected_architectures = lock.get("architectures", [])
        for flavor in ("gdscript", "dotnet"):
            for key in [*selected_architectures, "templates"]:
                digest = godot_assets.get(flavor, {}).get(key, {}).get("sha256", "")
                if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                    errors.append(f"Godot {flavor}/{key} is missing a SHA-256 digest")
        uv_image = lock.get("tools", {}).get("uv", {}).get("image", "")
        if not re.search(r"@sha256:[0-9a-fA-F]{64}$", uv_image):
            errors.append("uv image is not pinned by SHA-256 digest")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid toolchain lock: {exc}")
    if config is not None and lock is not None:
        build_args = config.get("build", {}).get("args", {})
        tools = lock.get("tools", {})
        godot = tools.get("godot", {})
        flavor = lock.get("flavor")
        if build_args.get("UV_IMAGE") != tools.get("uv", {}).get("image"):
            errors.append("devcontainer UV_IMAGE does not match the toolchain lock")
        if build_args.get("GODOT_VERSION") != godot.get("version"):
            errors.append("devcontainer GODOT_VERSION does not match the toolchain lock")
        if build_args.get("GODOT_FLAVOR") != flavor:
            errors.append("devcontainer GODOT_FLAVOR does not match the toolchain lock")
        selected_assets = godot.get("assets", {}).get(flavor, {})
        for architecture in lock.get("architectures", []):
            prefix = architecture.upper()
            asset = selected_assets.get(architecture, {})
            if build_args.get(f"GODOT_{prefix}_URL") != asset.get("url"):
                errors.append(f"Godot {architecture} URL does not match the toolchain lock")
            if build_args.get(f"GODOT_{prefix}_SHA256") != asset.get("sha256"):
                errors.append(f"Godot {architecture} checksum does not match the toolchain lock")
        templates = selected_assets.get("templates", {})
        if build_args.get("GODOT_TEMPLATES_URL") != templates.get("url"):
            errors.append("Godot template URL does not match the toolchain lock")
        if build_args.get("GODOT_TEMPLATES_SHA256") != templates.get("sha256"):
            errors.append("Godot template checksum does not match the toolchain lock")
        option_args = {
            "github-cli": "INSTALL_GITHUB_CLI",
            "git-lfs": "INSTALL_GIT_LFS",
            "image-tools": "INSTALL_IMAGE_TOOLS",
            "ssh": "INSTALL_SSH",
            "vscode-cli": "INSTALL_VSCODE_CLI",
        }
        enabled = set(lock.get("enabled_tools", []))
        for tool, argument in option_args.items():
            expected = str(tool in enabled).lower()
            if build_args.get(argument) != expected:
                errors.append(f"{argument} does not match enabled_tools")
        ssh = lock.get("ssh", {})
        run_args = config.get("runArgs", [])
        forward_ports = config.get("forwardPorts", [])
        if any("0.0.0.0:" in str(item) for item in run_args):
            errors.append("SSH host publishing must not bind to 0.0.0.0")
        if ssh.get("mode") == "vscode" and "ssh" in enabled and 22 not in forward_ports:
            errors.append("VS Code SSH mode must forward container port 22")
        if ssh.get("mode") == "fixed" and "ssh" in enabled:
            mapping = f"127.0.0.1:{ssh.get('host_port')}:22"
            if mapping not in run_args:
                errors.append("fixed SSH mode must use its loopback-only host mapping")
        if (ssh.get("mode") == "off" or "ssh" not in enabled) and (22 in forward_ports or run_args):
            errors.append("disabled SSH must not publish or forward a port")
        if "vscode-cli" in enabled:
            packages = tools.get("vscode-cli", {}).get("packages", {})
            for architecture in lock.get("architectures", []):
                package = packages.get(architecture, {})
                if build_args.get(f"VSCODE_{architecture.upper()}_URL") != package.get("url"):
                    errors.append(f"VS Code {architecture} URL does not match the toolchain lock")
                if build_args.get(f"VSCODE_{architecture.upper()}_SHA256") != package.get("sha256"):
                    errors.append(f"VS Code {architecture} checksum does not match the toolchain lock")
            dockerfile = (target / ".devcontainer/Dockerfile").read_text(
                encoding="utf-8", errors="replace"
            )
            verifier = (target / "scripts/dev/verify_env.sh").read_text(
                encoding="utf-8", errors="replace"
            )
            if "env -u VSCODE_IPC_HOOK_CLI /usr/share/code/bin/code" not in dockerfile:
                errors.append("code-cli must ignore the VS Code Remote CLI IPC hook")
            if "VSCODE_IPC_HOOK_CLI=/tmp/code-cli-must-not-use-vscode-ipc.sock" not in verifier:
                errors.append("environment verification must test code-cli IPC isolation")
    try:
        codex = tomllib.loads((target / ".codex/config.toml").read_text(encoding="utf-8"))
        if codex.get("approval_policy") != "never":
            errors.append(".codex/config.toml must set approval_policy = never")
        if codex.get("sandbox_mode") != "danger-full-access":
            errors.append(".codex/config.toml must set sandbox_mode = danger-full-access")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"invalid .codex/config.toml: {exc}")
    dockerfile = (target / ".devcontainer/Dockerfile").read_text(encoding="utf-8", errors="replace")
    installer = (target / ".devcontainer/install-godot.sh").read_text(encoding="utf-8", errors="replace")
    if "TARGETARCH" not in dockerfile or "TARGETARCH" not in installer:
        errors.append("Godot installation must select artifacts from Docker TARGETARCH")
    if re.search(r"curl\b[^\n|]*(?:\||>)\s*(?:ba)?sh\b", dockerfile + "\n" + installer):
        errors.append("remote install scripts are not allowed")
    bash = shutil.which("bash")
    if bash:
        for relative in [
            ".devcontainer/install-godot.sh",
            ".devcontainer/post-create.sh",
            ".devcontainer/start-sshd.sh",
            "scripts/dev/verify_env.sh",
            "scripts/dev/verify_godot_headless.sh",
        ]:
            ok, output = run_checked([bash, "-n", relative], target)
            if not ok:
                errors.append(f"shell syntax failed for {relative}: {output}")
    return errors


def validate_target(target: Path, mode: str) -> int:
    errors = static_validate(target)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Static validation passed.")
    devcontainer = shutil.which("devcontainer")
    if mode == "static":
        return 0
    if not devcontainer:
        if mode == "container":
            print("ERROR: Dev Container CLI is not installed.", file=sys.stderr)
            return 1
        print(
            "Dev Container CLI was not found; container validation was skipped.\n"
            "In VS Code, run: Dev Containers: Rebuild and Reopen in Container\n"
            "Then run: bash scripts/dev/verify_env.sh && bash scripts/dev/verify_godot_headless.sh"
        )
        return 0
    ok, output = run_checked([devcontainer, "up", "--workspace-folder", str(target)], target)
    if output:
        print(output)
    if not ok:
        return 1
    for command in ["bash scripts/dev/verify_env.sh", "bash scripts/dev/verify_godot_headless.sh"]:
        ok, output = run_checked(
            [devcontainer, "exec", "--workspace-folder", str(target), "bash", "-lc", command], target
        )
        if output:
            print(output)
        if not ok:
            return 1
    return 0


def add_common_plan_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", default=".", help="Target repository (default: current directory).")
    parser.add_argument("--project-dir", help="Relative directory containing project.godot.")
    parser.add_argument("--flavor", choices=["auto", "gdscript", "dotnet"], default="auto")
    parser.add_argument("--architectures", default="amd64,arm64")
    parser.add_argument("--ssh-mode", choices=["vscode", "fixed", "off"], default="vscode")
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--disable-tool", action="append", default=[], choices=sorted(OPTIONAL_TOOLS))
    parser.add_argument("--godot-version")
    parser.add_argument("--node-version")
    parser.add_argument("--codex-version")
    parser.add_argument("--uv-version")
    parser.add_argument("--gdtoolkit-version")
    parser.add_argument("--vscode-version")
    parser.add_argument(
        "--resolved-toolchain",
        help="Use a previously resolved lock file (useful for offline or repeatable generation).",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect", help="Inspect a target without changing it.")
    inspect_parser.add_argument("--target", default=".")
    inspect_parser.add_argument("--json", action="store_true")
    plan_parser = commands.add_parser("plan", help="Resolve versions and create a read-only change plan.")
    add_common_plan_options(plan_parser)
    plan_parser.add_argument("--output", help="Plan JSON path (default: a temporary file).")
    apply_parser = commands.add_parser("apply", help="Apply a conflict-free plan after baseline checks.")
    apply_parser.add_argument("--plan", required=True)
    validate_parser = commands.add_parser("validate", help="Validate generated files and optionally a container.")
    validate_parser.add_argument("--target", default=".")
    validate_parser.add_argument("--mode", choices=["auto", "static", "container"], default="auto")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_target(Path(args.target).resolve())
            print(json_text(result) if args.json else "\n".join(f"{key}: {value}" for key, value in result.items()))
            return 0
        if args.command == "plan":
            plan = create_plan(args)
            if args.output:
                output = Path(args.output).resolve()
                try:
                    output.relative_to(Path(plan["target"]))
                except ValueError:
                    pass
                else:
                    raise SetupError("--output must be outside the target so planning remains read-only.")
                output.parent.mkdir(parents=True, exist_ok=True)
            else:
                handle, name = tempfile.mkstemp(prefix="godot-devcontainer-plan-", suffix=".json")
                os.close(handle)
                output = Path(name)
            output.write_text(json_text(plan), encoding="utf-8", newline="\n")
            print_plan(plan)
            print(f"\nPlan saved to: {output}")
            if any(item["action"] == "conflict" for item in plan["operations"]):
                print("Manual merge is required; apply will refuse this plan.")
            else:
                command = [sys.executable, str(Path(__file__).resolve()), "apply", "--plan", str(output)]
                rendered = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
                print(f"Apply with: {rendered}")
            return 0
        if args.command == "apply":
            changed = apply_plan(Path(args.plan).resolve())
            print("Applied: " + (", ".join(changed) if changed else "no changes"))
            return 0
        if args.command == "validate":
            return validate_target(Path(args.target).resolve(), args.mode)
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
