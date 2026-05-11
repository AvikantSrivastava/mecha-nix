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
    def ensure_container(self, project_name: str, workspace_path: Path):
        return "mnix-demo", [CommandResult(["podman"], 0, "container ready", "")]

    def warmup(self, project_name: str, workspace_path: Path, flake_path: Path):
        return CommandResult(["podman", "exec"], 0, "warmup complete", "")


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


if __name__ == "__main__":
    unittest.main()
