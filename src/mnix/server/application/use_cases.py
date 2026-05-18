from __future__ import annotations

from io import BytesIO
from pathlib import Path

from mnix.server.domain.entities import ProjectRuntime, ProjectSpec


class ProjectUseCases:
    def __init__(self, workspace_store, podman_service) -> None:
        self.workspace_store = workspace_store
        self.podman_service = podman_service

    def list_running_containers(self) -> list[str]:
        return self.podman_service.list_running_containers()

    def launch(self, spec: ProjectSpec, payload: bytes) -> tuple[ProjectRuntime, int]:
        return self._sync_project(spec, payload)

    def rebuild_switch(self, spec: ProjectSpec, payload: bytes) -> tuple[ProjectRuntime, int]:
        return self._sync_project(spec, payload)

    def shell(self, spec: ProjectSpec) -> int:
        workspace_path, flake_path = self._resolve_project_paths(spec)
        result = self.podman_service.shell(spec.name, workspace_path, flake_path)
        return result.returncode

    def exec(self, spec: ProjectSpec, command: list[str]) -> int:
        workspace_path, flake_path = self._resolve_project_paths(spec)
        result = self.podman_service.exec(spec.name, workspace_path, flake_path, command)
        return result.returncode

    def _sync_project(self, spec: ProjectSpec, payload: bytes) -> tuple[ProjectRuntime, int]:
        workspace_path, flake_path = self.workspace_store.replace_from_archive(
            spec.name,
            BytesIO(payload),
            spec.flake_relative_path,
        )
        container_name, results = self.podman_service.ensure_container(spec.name, workspace_path)
        warmup_result = self.podman_service.warmup(spec.name, workspace_path, flake_path)
        results.append(warmup_result)

        stdout = "\n".join(part.stdout.strip() for part in results if part.stdout.strip())
        stderr = "\n".join(part.stderr.strip() for part in results if part.stderr.strip())
        exit_code = max(result.returncode for result in results)
        runtime = ProjectRuntime(
            workspace_path=str(workspace_path),
            flake_path=str(flake_path),
            container_name=container_name,
            stdout=stdout,
            stderr=stderr,
        )
        return runtime, exit_code

    def _resolve_project_paths(self, spec: ProjectSpec) -> tuple[Path, Path]:
        workspace_path = self.workspace_store.project_path(spec.name).resolve()
        flake_path = (workspace_path / spec.flake_relative_path).resolve()
        if flake_path != workspace_path and workspace_path not in flake_path.parents:
            raise ValueError(f"unsafe flake path: {spec.flake_relative_path}")
        if not flake_path.exists():
            raise FileNotFoundError(f"flake not found in workspace: {spec.flake_relative_path}")
        return workspace_path, flake_path
