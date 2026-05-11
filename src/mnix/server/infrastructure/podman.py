from __future__ import annotations

import subprocess
from pathlib import Path

from mnix.server.domain.entities import CommandResult
from mnix.shared.text import slugify


class PodmanService:
    def __init__(self, podman_binary: str, base_image: str, container_command: str, warmup_command: str) -> None:
        self.podman_binary = podman_binary
        self.base_image = base_image
        self.container_command = container_command
        self.warmup_command = warmup_command

    def _run(self, argv: list[str]) -> CommandResult:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
        return CommandResult(
            argv=argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _container_name(self, project_name: str) -> str:
        return f"mnix-{slugify(project_name)}"

    def ensure_container(self, project_name: str, workspace_path: Path) -> tuple[str, list[CommandResult]]:
        container_name = self._container_name(project_name)
        results = [
            self._run([self.podman_binary, "pull", self.base_image]),
            self._run(
                [
                    self.podman_binary,
                    "run",
                    "--detach",
                    "--replace",
                    "--name",
                    container_name,
                    "--workdir",
                    "/workspace",
                    "--volume",
                    f"{workspace_path}:/workspace",
                    self.base_image,
                    "sh",
                    "-lc",
                    self.container_command,
                ]
            ),
        ]
        return container_name, results

    def warmup(self, project_name: str, workspace_path: Path, flake_path: Path) -> CommandResult:
        container_name = self._container_name(project_name)
        relative_dir = flake_path.parent.relative_to(workspace_path)
        container_dir = Path("/workspace") / relative_dir
        command = f"cd {container_dir} && {self.warmup_command}"
        return self._run([self.podman_binary, "exec", container_name, "sh", "-lc", command])
