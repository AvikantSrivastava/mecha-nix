from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mnix.client.archive import build_archive
from mnix.client.config import ClientConfig
from mnix.client.repository import ClientRepository, ProjectRecord, ServerRecord


@dataclass
class OperationResult:
    message: str
    stdout: str = ""
    stderr: str = ""


@dataclass
class SyncStatus:
    server: ServerRecord
    matched_projects: list[ProjectRecord]
    missing_projects: list[ProjectRecord]


class ClientService:
    def __init__(
        self, repository: ClientRepository, config: ClientConfig, transport
    ) -> None:
        self.repository = repository
        self.config = config
        self.transport = transport

    @staticmethod
    def _decode_remote_response(execution, failure_message: str) -> dict:
        stdout = execution.stdout.strip()
        stderr = execution.stderr.strip()

        if not stdout:
            if stderr:
                raise RuntimeError(stderr)
            raise RuntimeError(failure_message)

        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as error:
            details = stderr or stdout
            raise RuntimeError(f"invalid remote response: {details}") from error

        if execution.returncode != 0:
            raise RuntimeError(response.get("stderr") or stderr or failure_message)

        return response

    @staticmethod
    def _remote_flake_relative_path(project: ProjectRecord) -> str:
        try:
            relative_path = Path(project.remote_flake_path).relative_to(
                project.remote_workspace
            )
        except ValueError as error:
            raise RuntimeError(
                f"project {project.name} has inconsistent remote paths; rebuild or relaunch it"
            ) from error
        return relative_path.as_posix()

    @classmethod
    def _remote_container_dir(cls, project: ProjectRecord) -> str:
        relative_path = Path(cls._remote_flake_relative_path(project))
        return str(Path("/workspace") / relative_path.parent)

    def list_projects(self) -> list[ProjectRecord]:
        return self.repository.list_projects()

    def list_servers(self) -> list[ServerRecord]:
        return self.repository.list_servers()

    def add_server(self, endpoint: str, name: str) -> str:
        self.repository.add_server(name=name, endpoint=endpoint)
        return f"saved server {name} -> {endpoint}"

    def remove_server(self, name: str) -> str:
        removed = self.repository.remove_server(name)
        if not removed:
            raise ValueError(f"unknown server: {name}")
        return f"removed server {name}"

    def select_project(self, name: str | None = None) -> str:
        projects = self.repository.list_projects()
        if not projects:
            raise ValueError("no projects found")

        if name is None:
            if len(projects) == 1:
                name = projects[0].name
            else:
                raise ValueError("interactive selection required")

        project = self.repository.get_project(name)
        if project is None:
            raise ValueError(f"unknown project: {name}")

        self.repository.set_selected_project(project.name)
        return f"selected project {project.name}"

    def purge_project(self, name: str) -> str:
        removed = self.repository.delete_project(name)
        if not removed:
            raise ValueError(f"unknown project: {name}")
        return f"purged local state for project {name}"

    def rm(self, project_name: str | None = None) -> OperationResult:
        project = self.resolve_project(project_name)
        server = self.resolve_server(project.server_name)
        execution = self.transport.rm(server.endpoint, project.name)
        response = self._decode_remote_response(execution, "remote remove failed")
        self.purge_project(project.name)
        return OperationResult(
            message=f"removed project {project.name}",
            stdout=response.get("stdout", ""),
            stderr=response.get("stderr", ""),
        )

    def resolve_server(self, requested_name: str | None = None) -> ServerRecord:
        if requested_name:
            server = self.repository.get_server(requested_name)
            if server is None:
                raise ValueError(f"unknown server: {requested_name}")
            return server

        if self.config.default_server:
            server = self.repository.get_server(self.config.default_server)
            if server is not None:
                return server

        servers = self.repository.list_servers()
        if len(servers) == 1:
            return servers[0]
        if not servers:
            raise ValueError("no servers configured")
        available = ", ".join(server.name for server in servers)
        raise ValueError(
            f"multiple servers configured; choose one with --server ({available})"
        )

    def resolve_project(self, name: str | None = None) -> ProjectRecord:
        name = name or self.repository.get_selected_project_name()
        if name is None:
            raise ValueError("no selected project; use mnix select <name>")

        project = self.repository.get_project(name)
        if project is None:
            raise ValueError(f"unknown project: {name}")
        return project

    def _list_remote_containers(self, server: ServerRecord) -> set[str]:
        execution = self.transport.run(server.endpoint, ["project", "ls"])
        response = self._decode_remote_response(
            execution, "remote project listing failed"
        )
        containers = response.get("containers")
        if not isinstance(containers, list) or not all(
            isinstance(item, str) for item in containers
        ):
            raise RuntimeError(f"invalid remote response: {execution.stdout.strip()}")
        return set(containers)

    def sync_status(self, server_name: str | None = None) -> SyncStatus:
        server = self.resolve_server(server_name)
        projects = [
            project
            for project in self.repository.list_projects()
            if project.server_name == server.name
        ]
        if not projects:
            return SyncStatus(
                server=server,
                matched_projects=[],
                missing_projects=[],
            )

        running_containers = self._list_remote_containers(server)
        matched_projects: list[ProjectRecord] = []
        missing_projects: list[ProjectRecord] = []

        for project in projects:
            if project.container_name in running_containers:
                matched_projects.append(project)
            else:
                missing_projects.append(project)

        return SyncStatus(
            server=server,
            matched_projects=matched_projects,
            missing_projects=missing_projects,
        )

    def new_project(
        self, name: str, flake_path: Path, server_name: str | None = None
    ) -> OperationResult:
        server = self.resolve_server(server_name)
        bundle = build_archive(flake_path)
        execution = self.transport.run(
            server.endpoint,
            [
                "project",
                "launch",
                "--name",
                name,
                "--flake",
                bundle.flake_relative_path,
            ],
            payload=bundle.payload,
        )
        response = self._decode_remote_response(execution, "remote launch failed")

        project = ProjectRecord(
            name=name,
            server_name=server.name,
            local_flake_path=str(flake_path.expanduser().resolve()),
            remote_workspace=response["workspace_path"],
            remote_flake_path=response["flake_path"],
            container_name=response["container_name"],
        )
        self.repository.upsert_project(project)
        self.repository.set_selected_project(name)
        return OperationResult(
            message=f"launched project {name} on {server.name}",
            stdout=response.get("stdout", ""),
            stderr=response.get("stderr", ""),
        )

    def rebuild_switch(
        self, flake_path: Path | None = None, project_name: str | None = None
    ) -> OperationResult:
        project = self.resolve_project(project_name)
        flake = flake_path or Path(project.local_flake_path)
        bundle = build_archive(flake)
        server = self.resolve_server(project.server_name)
        execution = self.transport.run(
            server.endpoint,
            [
                "project",
                "rebuild-switch",
                "--name",
                project.name,
                "--flake",
                bundle.flake_relative_path,
            ],
            payload=bundle.payload,
        )
        response = self._decode_remote_response(
            execution, "remote rebuild-switch failed"
        )

        self.repository.upsert_project(
            ProjectRecord(
                name=project.name,
                server_name=project.server_name,
                local_flake_path=str(flake.expanduser().resolve()),
                remote_workspace=response["workspace_path"],
                remote_flake_path=response["flake_path"],
                container_name=response["container_name"],
            )
        )
        return OperationResult(
            message=f"rebuilt project {project.name}",
            stdout=response.get("stdout", ""),
            stderr=response.get("stderr", ""),
        )

    def shell(self, project_name: str | None = None) -> int:
        project = self.resolve_project(project_name)
        server = self.resolve_server(project.server_name)
        return self.transport.attach_command(
            server.endpoint,
            [
                self.config.remote_podman_binary,
                "exec",
                "-it",
                "--workdir",
                self._remote_container_dir(project),
                project.container_name,
                "nix",
                "--extra-experimental-features",
                "nix-command flakes",
                "develop",
            ],
            allocate_tty=True,
        )

    def exec(self, command: list[str], project_name: str | None = None) -> int:
        if not command:
            raise ValueError("command required")

        project = self.resolve_project(project_name)
        server = self.resolve_server(project.server_name)
        return self.transport.attach_command(
            server.endpoint,
            [
                self.config.remote_podman_binary,
                "exec",
                "--workdir",
                self._remote_container_dir(project),
                project.container_name,
                "nix",
                "--extra-experimental-features",
                "nix-command flakes",
                "develop",
                "-c",
                *command,
            ],
        )
