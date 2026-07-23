from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "godot_devcontainer.py"
SPEC = importlib.util.spec_from_file_location("godot_devcontainer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fake_lock(path: Path) -> Path:
    digest_a = "a" * 64
    digest_b = "b" * 64
    digest_c = "c" * 64

    def asset(name: str, digest: str) -> dict[str, str]:
        return {
            "name": name,
            "url": f"https://example.invalid/{name}",
            "sha256": digest,
        }

    version = "4.7-stable"
    data = {
        "schema_version": 1,
        "resolved_at": "2026-07-21T00:00:00+00:00",
        "architectures": ["amd64", "arm64"],
        "tools": {
            "godot": {
                "version": version,
                "source": "https://example.invalid/godot",
                "explicit": False,
                "assets": {
                    "gdscript": {
                        "amd64": asset(f"Godot_v{version}_linux.x86_64.zip", digest_a),
                        "arm64": asset(f"Godot_v{version}_linux.arm64.zip", digest_b),
                        "templates": asset(f"Godot_v{version}_export_templates.tpz", digest_c),
                    },
                    "dotnet": {
                        "amd64": asset(f"Godot_v{version}_mono_linux_x86_64.zip", digest_a),
                        "arm64": asset(f"Godot_v{version}_mono_linux_arm64.zip", digest_b),
                        "templates": asset(f"Godot_v{version}_mono_export_templates.tpz", digest_c),
                    },
                },
            },
            "node": {
                "version": "22.17.0",
                "source": "https://example.invalid/node",
                "explicit": False,
                "lts": "Jod",
            },
            "codex": {
                "version": "0.99.0",
                "source": "https://example.invalid/codex",
                "explicit": False,
                "integrity": "sha512-test",
            },
            "uv": {
                "version": "0.8.0",
                "source": "https://example.invalid/uv",
                "explicit": False,
                "image": f"ghcr.io/astral-sh/uv:0.8.0@sha256:{digest_a}",
                "digest": f"sha256:{digest_a}",
            },
            "gdtoolkit": {
                "version": "4.3.4",
                "source": "https://example.invalid/gdtoolkit",
                "explicit": False,
            },
            "vscode-cli": {
                "version": "1.102.1",
                "source": "https://example.invalid/vscode",
                "explicit": False,
                "packages": {
                    "amd64": {
                        "version": "1.102.1-100",
                        "url": "https://example.invalid/code-amd64.deb",
                        "sha256": digest_a,
                    },
                    "arm64": {
                        "version": "1.102.1-101",
                        "url": "https://example.invalid/code-arm64.deb",
                        "sha256": digest_b,
                    },
                },
            },
        },
        "notes": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def plan_for(target: Path, lock: Path, *extra: str) -> dict:
    args = MODULE.parser().parse_args(
        ["plan", "--target", str(target), "--resolved-toolchain", str(lock), *extra]
    )
    return MODULE.create_plan(args)


class PlannerTests(unittest.TestCase):
    def test_invalid_architecture_and_ssh_port_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            with self.assertRaises(MODULE.SetupError):
                plan_for(root, lock, "--architectures", "amd64,amd64")
            with self.assertRaises(MODULE.SetupError):
                plan_for(root, lock, "--ssh-mode", "fixed", "--ssh-port", "70000")

    def test_new_project_defaults_to_full_gdscript_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            selection = plan["selection"]
            self.assertEqual("gdscript", selection["flavor"])
            self.assertEqual(["amd64", "arm64"], selection["architectures"])
            self.assertEqual("vscode", selection["ssh_mode"])
            self.assertEqual(MODULE.OPTIONAL_TOOLS, set(selection["enabled_tools"]))
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertEqual([22], config["forwardPorts"])
            self.assertEqual([], config["runArgs"])
            self.assertEqual("https://example.invalid/code-amd64.deb", config["build"]["args"]["VSCODE_AMD64_URL"])
            self.assertEqual("a" * 64, config["build"]["args"]["VSCODE_AMD64_SHA256"])
            dockerfile = operations[".devcontainer/Dockerfile"]["content"]
            verifier = operations["scripts/dev/verify_env.sh"]["content"]
            self.assertIn("env -u VSCODE_IPC_HOOK_CLI /usr/share/code/bin/code", dockerfile)
            self.assertIn(
                "VSCODE_IPC_HOOK_CLI=/tmp/code-cli-must-not-use-vscode-ipc.sock",
                verifier,
            )
            self.assertIn("rev-parse --is-inside-work-tree", operations[".devcontainer/post-create.sh"]["content"])
            self.assertEqual(
                'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
                operations[".codex/config.toml"]["content"],
            )

    def test_dotnet_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "project.godot").write_text("[application]\n", encoding="utf-8")
            (root / "Game.csproj").write_text("<Project />\n", encoding="utf-8")
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            self.assertEqual("dotnet", plan["selection"]["flavor"])
            operation = next(item for item in plan["operations"] if item["path"] == ".devcontainer/devcontainer.json")
            config = json.loads(operation["content"])
            self.assertIn("ghcr.io/devcontainers/features/dotnet:2", config["features"])
            self.assertIn("mono_linux_x86_64", config["build"]["args"]["GODOT_AMD64_URL"])
            verifier = next(item for item in plan["operations"] if item["path"] == "scripts/dev/verify_env.sh")
            self.assertIn("require_command dotnet", verifier["content"])
            self.assertIn("Expected the .NET/mono Godot build", verifier["content"])

    def test_safe_merges_preserve_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex").mkdir()
            (root / ".codex" / "config.toml").write_text(
                '# keep\nmodel = "gpt-5"\n\n[features]\nfoo = true\n', encoding="utf-8"
            )
            (root / ".gitignore").write_text("custom.tmp\n", encoding="utf-8")
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--disable-tool", "ssh", "--ssh-mode", "off")
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            changed = MODULE.apply_plan(plan_path)
            self.assertIn(".codex/config.toml", changed)
            codex = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn('# keep\nmodel = "gpt-5"', codex)
            self.assertIn('approval_policy = "never"', codex)
            self.assertIn('sandbox_mode = "danger-full-access"', codex)
            self.assertIn("[features]\nfoo = true", codex)
            self.assertIn("custom.tmp", (root / ".gitignore").read_text(encoding="utf-8"))
            self.assertEqual([], json.loads((root / ".devcontainer" / "devcontainer.json").read_text())["forwardPorts"])
            self.assertEqual([], MODULE.static_validate(root))

    def test_existing_complex_file_blocks_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".devcontainer").mkdir()
            existing = root / ".devcontainer" / "Dockerfile"
            existing.write_text("FROM custom\n", encoding="utf-8")
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            self.assertEqual(
                "conflict",
                next(item for item in plan["operations"] if item["path"] == ".devcontainer/Dockerfile")["action"],
            )
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(MODULE.SetupError):
                MODULE.apply_plan(plan_path)
            self.assertEqual("FROM custom\n", existing.read_text(encoding="utf-8"))
            self.assertFalse((root / ".codex" / "config.toml").exists())

    def test_changed_baseline_blocks_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".gitignore").write_text("before\n", encoding="utf-8")
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            (root / ".gitignore").write_text("changed after plan\n", encoding="utf-8")
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(MODULE.SetupError):
                MODULE.apply_plan(plan_path)
            self.assertFalse((root / ".codex" / "config.toml").exists())

    def test_apply_rolls_back_when_a_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            real_replace = MODULE.os.replace
            calls = 0

            def fail_second_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated replace failure")
                return real_replace(source, destination)

            with mock.patch.object(MODULE.os, "replace", side_effect=fail_second_replace):
                with self.assertRaises(OSError):
                    MODULE.apply_plan(plan_path)
            self.assertFalse((root / ".devcontainer" / "devcontainer.json").exists())
            self.assertFalse((root / ".codex" / "config.toml").exists())

    def test_inspect_flags_fixed_architecture_remote_script_and_host_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".devcontainer").mkdir()
            (root / ".devcontainer" / "Dockerfile").write_text(
                "RUN curl -fsSL https://example.invalid/install.sh | sh\n"
                "RUN curl -o godot-linux.x86_64.zip https://example.invalid/godot.zip\n",
                encoding="utf-8",
            )
            (root / ".devcontainer" / "devcontainer.json").write_text(
                '{"runArgs":["-p","2224:22"]}\n', encoding="utf-8"
            )
            inspection = MODULE.inspect_target(root)
            findings = "\n".join(inspection["findings"])
            self.assertIn("fixed to x86_64/amd64", findings)
            self.assertIn("not guarded by Docker TARGETARCH", findings)
            self.assertIn("remote install script", findings)
            self.assertIn("fixed SSH host port", findings)
            self.assertIn("not explicitly loopback-only", findings)

    def test_fixed_ssh_is_loopback_only_and_optional_tools_are_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(
                root,
                lock,
                "--ssh-mode",
                "fixed",
                "--ssh-port",
                "2224",
                "--disable-tool",
                "github-cli",
                "--disable-tool",
                "vscode-cli",
            )
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertEqual(["-p", "127.0.0.1:2224:22"], config["runArgs"])
            verify = operations["scripts/dev/verify_env.sh"]["content"]
            self.assertIn('if [[ "false" == true ]]; then require_command gh; fi', verify)
            self.assertIn('if [[ "false" == true ]]; then\n  require_command code-cli', verify)

    def test_static_validation_rejects_vscode_cli_without_ipc_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            dockerfile = root / ".devcontainer" / "Dockerfile"
            dockerfile.write_text(
                dockerfile.read_text(encoding="utf-8").replace(
                    "env -u VSCODE_IPC_HOOK_CLI /usr/share/code/bin/code",
                    "/usr/share/code/bin/code",
                ),
                encoding="utf-8",
            )
            self.assertIn(
                "code-cli must ignore the VS Code Remote CLI IPC hook",
                MODULE.static_validate(root),
            )

    def test_single_architecture_does_not_claim_other_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--architectures", "amd64")
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertIn("GODOT_AMD64_URL", config["build"]["args"])
            self.assertNotIn("GODOT_ARM64_URL", config["build"]["args"])
            installer = operations[".devcontainer/install-godot.sh"]["content"]
            self.assertIn("amd64)", installer)
            self.assertNotIn("arm64)", installer)


if __name__ == "__main__":
    unittest.main()
