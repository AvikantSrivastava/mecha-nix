from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from mnix.server.application.use_cases import ProjectUseCases
from mnix.server.domain.entities import CommandResult, ProjectSpec
from mnix.server.infrastructure.workspace import WorkspaceStore


class FakePodmanService:
    def __init__(self) -> None:
        self.rm_calls: list[str] = []

    def list_running_containers(self):
        return ["mnix-demo"]

    def ensure_container(self, project_name: str, workspace_path: Path):
        return "mnix-demo", [CommandResult(["podman"], 0, "container ready", "")]

    def warmup(self, project_name: str, workspace_path: Path, flake_path: Path):
        return CommandResult(["podman", "exec"], 0, "warmup complete", "")

    def shell(self, project_name: str, workspace_path: Path, flake_path: Path):
        return CommandResult(["podman", "exec", "-it"], 0, str(flake_path), "")

    def exec(self, project_name: str, workspace_path: Path, flake_path: Path, command: list[str]):
        return CommandResult(command, 5, str(workspace_path), str(flake_path))

    def rm(self, project_name: str):
        self.rm_calls.append(project_name)
        return CommandResult(["podman", "rm", project_name], 0, "removed", "")


def build_payload(source_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(source_dir, arcname=".")
    return buffer.getvalue()


class ProjectUseCasesTests(unittest.TestCase):
    def test_launch_extracts_workspace_and_aggregates_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "source"
            source.mkdir()
            (source / "flake.nix").write_text("{ description = \"demo\"; }")

            use_cases = ProjectUseCases(WorkspaceStore(tmp / "workspaces"), FakePodmanService())
            runtime, exit_code = use_cases.launch(
                ProjectSpec(name="Demo", flake_relative_path="flake.nix"),
                build_payload(source),
            )

            self.assertEqual(0, exit_code)
            self.assertTrue(runtime.workspace_path.endswith("demo"))
            self.assertIn("warmup complete", runtime.stdout)

    def test_shell_uses_existing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            workspace = WorkspaceStore(tmp / "workspaces")
            project_path = workspace.project_path("Demo")
            nested = project_path / "nix"
            nested.mkdir(parents=True)
            flake_path = nested / "flake.nix"
            flake_path.write_text("{ description = \"demo\"; }")

            use_cases = ProjectUseCases(workspace, FakePodmanService())

            exit_code = use_cases.shell(ProjectSpec(name="Demo", flake_relative_path="nix/flake.nix"))

            self.assertEqual(0, exit_code)

    def test_exec_uses_existing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            workspace = WorkspaceStore(tmp / "workspaces")
            project_path = workspace.project_path("Demo")
            project_path.mkdir(parents=True)
            flake_path = project_path / "flake.nix"
            flake_path.write_text("{ description = \"demo\"; }")

            use_cases = ProjectUseCases(workspace, FakePodmanService())

            exit_code = use_cases.exec(
                ProjectSpec(name="Demo", flake_relative_path="flake.nix"),
                ["echo", "hello"],
            )

            self.assertEqual(5, exit_code)

    def test_list_running_containers_passes_through(self) -> None:
        use_cases = ProjectUseCases(WorkspaceStore(Path("/tmp/unused")), FakePodmanService())

        self.assertEqual(["mnix-demo"], use_cases.list_running_containers())

    def test_rm_deletes_workspace_and_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            workspace = WorkspaceStore(tmp / "workspaces")
            project_path = workspace.project_path("Demo")
            project_path.mkdir(parents=True)
            podman = FakePodmanService()
            use_cases = ProjectUseCases(workspace, podman)

            result = use_cases.rm(ProjectSpec(name="Demo", flake_relative_path=""))

            self.assertEqual(0, result.returncode)
            self.assertEqual(["Demo"], podman.rm_calls)
            self.assertFalse(project_path.exists())


if __name__ == "__main__":
    unittest.main()
