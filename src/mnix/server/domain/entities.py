from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ProjectSpec:
    name: str
    flake_relative_path: str


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class ProjectRuntime:
    workspace_path: str
    flake_path: str
    container_name: str
    stdout: str
    stderr: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)
