from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "godot_devcontainer.py"
SPEC = importlib.util.spec_from_file_location("godot_devcontainer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BASH = next(
    (
        str(path)
        for path in [Path(r"C:\Program Files\Git\usr\bin\bash.exe"), Path(r"C:\Program Files\Git\bin\bash.exe")]
        if path.is_file()
    ),
    None,
)


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
            self.assertEqual("off", selection["gpu_mode"])
            self.assertEqual("volume", selection["worktree_mode"])
            self.assertEqual(MODULE.OPTIONAL_TOOLS, set(selection["enabled_tools"]))
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertEqual([22], config["forwardPorts"])
            self.assertEqual([], config["runArgs"])
            self.assertNotIn("gpu", config["hostRequirements"])
            self.assertNotIn("NVIDIA_VISIBLE_DEVICES", config["containerEnv"])
            self.assertIn(
                "source=${localWorkspaceFolderBasename}-godot-cache,target=/home/vscode/.cache/godot,type=volume",
                config["mounts"],
            )
            self.assertIn(
                "source=${localWorkspaceFolderBasename}-worktrees,target=/workspaces/${localWorkspaceFolderBasename}/.worktree,type=volume",
                config["mounts"],
            )
            self.assertNotIn("/home/vscode/.cache/inference", "\n".join(config["mounts"]))
            lock_data = json.loads(operations[".devcontainer/toolchain.lock.json"]["content"])
            self.assertEqual({"mode": "off"}, lock_data["gpu"])
            self.assertEqual(
                {
                    "worktrees": "volume",
                    "godot_cache": "volume",
                    "inference_cache": "off",
                    "playwright_cache": "off",
                    "playwright_chatgpt_profile": "off",
                },
                lock_data["volumes"],
            )
            self.assertFalse(lock_data["chatgpt_browser"]["enabled"])
            self.assertNotIn(".devcontainer/chrome-seccomp.json", operations)
            self.assertNotIn("playwright_chatgpt", operations[".codex/config.toml"]["content"])
            self.assertIn("scripts/dev/manage_worktree.sh", operations)
            self.assertIn(".devcontainer/storage-policy.md", operations)
            self.assertIn("AGENTS.md", operations)
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
            self.assertIn("/home/vscode/.cache/uv", operations[".devcontainer/post-create.sh"]["content"])
            self.assertEqual(
                'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
                operations[".codex/config.toml"]["content"],
            )

    def test_nvidia_gpu_profile_is_inference_only_and_statically_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--gpu-mode", "nvidia", "--ssh-mode", "off")
            self.assertEqual("nvidia", plan["selection"]["gpu_mode"])
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertEqual(["--gpus=all"], config["runArgs"])
            self.assertIs(True, config["hostRequirements"]["gpu"])
            self.assertEqual("all", config["containerEnv"]["NVIDIA_VISIBLE_DEVICES"])
            self.assertEqual(
                "compute,utility", config["containerEnv"]["NVIDIA_DRIVER_CAPABILITIES"]
            )
            self.assertEqual("1", config["containerEnv"]["LIBGL_ALWAYS_SOFTWARE"])
            self.assertEqual(
                "/home/vscode/.cache/inference", config["containerEnv"]["INFERENCE_CACHE_DIR"]
            )
            self.assertNotIn("HF_HOME", config["containerEnv"])
            self.assertIn(
                "source=${localWorkspaceFolderBasename}-inference-cache,target=/home/vscode/.cache/inference,type=volume",
                config["mounts"],
            )
            verifier = operations["scripts/dev/verify_env.sh"]["content"]
            self.assertIn("require_command nvidia-smi", verifier)
            self.assertIn("--query-gpu=name,memory.total,driver_version", verifier)
            lock_data = json.loads(operations[".devcontainer/toolchain.lock.json"]["content"])
            self.assertEqual({"mode": "nvidia"}, lock_data["gpu"])
            self.assertEqual("volume", lock_data["volumes"]["inference_cache"])

            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            self.assertEqual([], MODULE.static_validate(root))

            config["containerEnv"].pop("NVIDIA_DRIVER_CAPABILITIES")
            (root / ".devcontainer" / "devcontainer.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            self.assertIn(
                "NVIDIA GPU mode must expose compute and utility capabilities",
                MODULE.static_validate(root),
            )

    def test_static_validation_rejects_gpu_request_when_mode_is_off(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            config_path = root / ".devcontainer" / "devcontainer.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["runArgs"] = ["--gpus=all"]
            config_path.write_text(json.dumps(config), encoding="utf-8")
            self.assertIn("disabled GPU mode must not request GPUs", MODULE.static_validate(root))

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

    def test_project_discovery_skips_virtual_environments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "project.godot").write_text("[application]\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "project.godot").write_text("ignore\n", encoding="utf-8")
            self.assertEqual(["game"], MODULE.detect_projects(root))

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

    def test_host_worktree_mode_omits_volume_and_lock_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--worktree-mode", "host")
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertNotIn("-worktrees", "\n".join(config["mounts"]))
            self.assertNotIn("scripts/dev/manage_worktree.sh", operations)
            lock_data = json.loads(operations[".devcontainer/toolchain.lock.json"]["content"])
            self.assertEqual("host", lock_data["volumes"]["worktrees"])
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            self.assertEqual([], MODULE.static_validate(root))

    def test_instruction_precedence_and_managed_block_preserve_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "AGENTS.md").write_text("# Base\nKeep base.\n", encoding="utf-8")
            (root / "AGENTS.override.md").write_text("# Override\nKeep override.\n", encoding="utf-8")
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            operations = {item["path"]: item for item in plan["operations"]}
            self.assertEqual("merge", operations["AGENTS.override.md"]["action"])
            self.assertIn("Keep override.", operations["AGENTS.override.md"]["content"])
            self.assertIn(".devcontainer/storage-policy.md", operations["AGENTS.override.md"]["content"])
            self.assertNotIn("AGENTS.md", operations)

    def test_configured_instruction_fallback_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex").mkdir()
            (root / ".codex" / "config.toml").write_text(
                'project_doc_fallback_filenames = ["PROJECT.md"]\n', encoding="utf-8"
            )
            (root / "PROJECT.md").write_text("# Project rules\n", encoding="utf-8")
            lock = fake_lock(root / "resolved.json")
            operations = {item["path"]: item for item in plan_for(root, lock)["operations"]}
            self.assertIn("PROJECT.md", operations)
            self.assertNotIn("AGENTS.md", operations)

    def test_static_validation_rejects_storage_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--gpu-mode", "nvidia")
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            config_path = root / ".devcontainer" / "devcontainer.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["mounts"] = [item for item in config["mounts"] if "inference-cache" not in item]
            config["containerEnv"]["HF_HOME"] = "/home/vscode/.cache/inference"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            errors = MODULE.static_validate(root)
            self.assertIn("NVIDIA mode must mount the inference cache volume", errors)
            self.assertIn("NVIDIA mode must not override HF_HOME", errors)

    @unittest.skipUnless(BASH and shutil.which("git"), "Git Bash and git are required")
    def test_worktree_helper_locks_and_safely_removes_real_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "project.godot").write_text("[application]\n", encoding="utf-8")
            subprocess.run(["git", "add", "project.godot"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            helper = [BASH, "scripts/dev/manage_worktree.sh"]
            helper_env = os.environ.copy()
            helper_env["PATH"] = (
                r"C:\Program Files\Git\usr\bin;C:\Program Files\Git\mingw64\bin;"
                + helper_env.get("PATH", "")
            )
            subprocess.run([*helper, "create", "task-one", "task/one"], cwd=root, check=True, env=helper_env)
            porcelain = subprocess.check_output(["git", "worktree", "list", "--porcelain"], cwd=root, text=True)
            self.assertIn("locked managed by setup-godot-devcontainer", porcelain)
            subprocess.run([*helper, "verify"], cwd=root, check=True, env=helper_env)
            task = root / ".worktree" / "task-one"
            (task / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            refused = subprocess.run([*helper, "remove", "task-one"], cwd=root, capture_output=True, env=helper_env)
            self.assertNotEqual(0, refused.returncode)
            self.assertTrue(task.is_dir())
            (task / "dirty.txt").unlink()
            subprocess.run([*helper, "remove", "task-one"], cwd=root, check=True, env=helper_env)
            self.assertFalse(task.exists())
            branches = subprocess.check_output(["git", "branch", "--list", "task/one"], cwd=root, text=True)
            self.assertIn("task/one", branches)

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

    def test_inspect_classifies_nvidia_inference_and_inconsistent_gpu_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".devcontainer").mkdir()
            config_path = root / ".devcontainer" / "devcontainer.json"
            config_path.write_text(
                json.dumps(
                    {
                        "runArgs": ["--gpus=all"],
                        "hostRequirements": {"gpu": True},
                        "containerEnv": {
                            "NVIDIA_VISIBLE_DEVICES": "all",
                            "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
                            "LIBGL_ALWAYS_SOFTWARE": "1",
                        },
                    }
                ),
                encoding="utf-8",
            )
            inspection = MODULE.inspect_target(root)
            self.assertEqual("nvidia-inference", inspection["gpu_signals"]["mode"])
            self.assertIs(True, inspection["gpu_signals"]["host_required"])
            self.assertIs(True, inspection["gpu_signals"]["software_rendering"])
            self.assertNotIn("inconsistent", "\n".join(inspection["findings"]).lower())

            config_path.write_text(
                json.dumps({"containerEnv": {"NVIDIA_VISIBLE_DEVICES": "all"}}),
                encoding="utf-8",
            )
            inspection = MODULE.inspect_target(root)
            self.assertEqual("inconsistent", inspection["gpu_signals"]["mode"])
            self.assertIn("inconsistent", "\n".join(inspection["findings"]).lower())

    def test_inspect_classifies_storage_and_reports_missing_policy_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".devcontainer").mkdir()
            (root / ".devcontainer" / "devcontainer.json").write_text(
                json.dumps(
                    {
                        "mounts": [
                            "source=x-worktrees,target=/workspaces/${localWorkspaceFolderBasename}/.worktree,type=volume",
                            "source=x-cache,target=/home/vscode/.cache,type=volume",
                            "source=x-inference,target=/home/vscode/.cache/inference,type=volume",
                        ],
                        "containerEnv": {"INFERENCE_CACHE_DIR": "/home/vscode/.cache/inference"},
                    }
                ),
                encoding="utf-8",
            )
            inspection = MODULE.inspect_target(root)
            self.assertEqual("volume", inspection["storage_signals"]["worktrees"])
            self.assertEqual("volume", inspection["storage_signals"]["inference_cache"])
            findings = "\n".join(inspection["findings"])
            self.assertIn("broad /home/vscode/.cache", findings)
            self.assertIn("without the managed lock helper", findings)
            self.assertIn("does not link to the storage policy", findings)

    def test_fixed_ssh_is_loopback_only_and_optional_tools_are_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(
                root,
                lock,
                "--gpu-mode",
                "nvidia",
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
            self.assertEqual(
                ["--gpus=all", "-p", "127.0.0.1:2224:22"], config["runArgs"]
            )
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

    def test_chatgpt_browser_vscode_bundle_is_generated_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--chatgpt-browser")
            self.assertTrue(plan["selection"]["chatgpt_browser"])
            self.assertEqual("vscode", plan["selection"]["browser_access_mode"])
            operations = {item["path"]: item for item in plan["operations"]}
            config = json.loads(operations[".devcontainer/devcontainer.json"]["content"])
            self.assertEqual([22, 6080, 9323], config["forwardPorts"])
            self.assertIn("--shm-size=1g", config["runArgs"])
            self.assertIn(
                "seccomp=${localWorkspaceFolder}/.devcontainer/chrome-seccomp.json",
                config["runArgs"],
            )
            self.assertEqual(":99", config["containerEnv"]["DISPLAY"])
            self.assertIn(".devcontainer/chrome-seccomp.json", operations)
            self.assertIn(".devcontainer/playwright-e2e/package-lock.json", operations)
            self.assertIn(".devcontainer/playwright-mcp/package-lock.json", operations)
            codex = operations[".codex/config.toml"]["content"]
            self.assertIn('command = "playwright-chatgpt-mcp"', codex)
            self.assertNotIn("/workspaces/", codex)
            post_create = operations[".devcontainer/post-create.sh"]["content"]
            self.assertIn('npm install --global "@openai/codex@0.99.0"', post_create)
            self.assertNotIn("--prefix /home/vscode/.local", post_create)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            self.assertEqual([], MODULE.static_validate(root))
            inspection = MODULE.inspect_target(root)
            self.assertTrue(inspection["browser_signals"]["enabled"])
            self.assertEqual("vscode", inspection["browser_signals"]["access_mode"])
            self.assertTrue(inspection["browser_signals"]["mcp_configured"])

    def test_chatgpt_browser_fixed_ports_are_loopback_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(
                root,
                lock,
                "--chatgpt-browser",
                "--browser-access-mode",
                "fixed",
                "--novnc-host-port",
                "16080",
                "--playwright-ui-host-port",
                "19323",
            )
            config = json.loads(
                next(
                    item["content"]
                    for item in plan["operations"]
                    if item["path"] == ".devcontainer/devcontainer.json"
                )
            )
            self.assertNotIn(6080, config["forwardPorts"])
            self.assertIn("127.0.0.1:16080:6080", config["runArgs"])
            self.assertIn("127.0.0.1:19323:9323", config["runArgs"])
            defaults = plan_for(
                root,
                lock,
                "--chatgpt-browser",
                "--browser-access-mode",
                "fixed",
            )["selection"]
            self.assertEqual(6080, defaults["novnc_host_port"])
            self.assertEqual(9323, defaults["playwright_ui_host_port"])

    def test_browser_only_options_and_port_conflicts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            invalid = [
                ("--browser-access-mode", "fixed"),
                ("--chatgpt-browser", "--novnc-host-port", "6080"),
                (
                    "--chatgpt-browser",
                    "--browser-access-mode",
                    "fixed",
                    "--novnc-host-port",
                    "0",
                ),
                (
                    "--chatgpt-browser",
                    "--browser-access-mode",
                    "fixed",
                    "--novnc-host-port",
                    "70000",
                ),
                (
                    "--chatgpt-browser",
                    "--browser-access-mode",
                    "fixed",
                    "--novnc-host-port",
                    "6080",
                    "--playwright-ui-host-port",
                    "6080",
                ),
                (
                    "--chatgpt-browser",
                    "--browser-access-mode",
                    "fixed",
                    "--ssh-mode",
                    "fixed",
                    "--ssh-port",
                    "6080",
                ),
            ]
            for arguments in invalid:
                with self.subTest(arguments=arguments), self.assertRaises(MODULE.SetupError):
                    plan_for(root, lock, *arguments)

    def test_browser_codex_block_is_owned_and_unmanaged_server_conflicts(self) -> None:
        source = '# keep\nmodel = "gpt-5"\n'
        enabled = MODULE.merge_codex_config(source, True)
        self.assertIn(MODULE.BROWSER_CODEX_START, enabled)
        self.assertEqual(enabled, MODULE.merge_codex_config(enabled, True))
        disabled = MODULE.merge_codex_config(enabled, False)
        self.assertNotIn("playwright_chatgpt", disabled)
        self.assertIn('model = "gpt-5"', disabled)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text(
                '[mcp_servers.playwright_chatgpt]\ncommand = "custom"\n', encoding="utf-8"
            )
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--chatgpt-browser")
            operation = next(
                item for item in plan["operations"] if item["path"] == ".codex/config.toml"
            )
            self.assertEqual("conflict", operation["action"])

    def test_static_validation_catches_browser_security_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = fake_lock(root / "resolved.json")
            plan = plan_for(root, lock, "--chatgpt-browser")
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            MODULE.apply_plan(plan_path)
            config_path = root / ".devcontainer/devcontainer.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["runArgs"].remove("--shm-size=1g")
            config_path.write_text(json.dumps(config), encoding="utf-8")
            self.assertIn("ChatGPT browser must set --shm-size=1g", MODULE.static_validate(root))


if __name__ == "__main__":
    unittest.main()
