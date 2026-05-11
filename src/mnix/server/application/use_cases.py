from __future__ import annotations

from io import BytesIO

from mnix.server.domain.entities import ProjectRuntime, ProjectSpec


class ProjectUseCases:
    def __init__(self, workspace_store, podman_service) -> None:
        self.workspace_store = workspace_store
        self.podman_service = podman_service

    def launch(self, spec: ProjectSpec, payload: bytes) -> tuple[ProjectRuntime, int]:
        return self._sync_project(spec, payload)

    def rebuild_switch(self, spec: ProjectSpec, payload: bytes) -> tuple[ProjectRuntime, int]:
        return self._sync_project(spec, payload)

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
