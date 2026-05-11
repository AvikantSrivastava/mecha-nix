from __future__ import annotations

import argparse
import json
import traceback
import sys

from mnix.server.application.use_cases import ProjectUseCases
from mnix.server.domain.entities import ProjectSpec
from mnix.server.infrastructure.config import ServerConfig
from mnix.server.infrastructure.podman import PodmanService
from mnix.server.infrastructure.workspace import WorkspaceStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mnix-server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    project_parser = subparsers.add_parser("project", help="Project lifecycle commands")
    project_subparsers = project_parser.add_subparsers(dest="project_command", required=True)

    for command_name in ("launch", "rebuild-switch"):
        command_parser = project_subparsers.add_parser(command_name)
        command_parser.add_argument("--name", required=True, help="Project name")
        command_parser.add_argument("--flake", required=True, help="Relative flake path inside the archive")

    return parser


def _build_use_cases() -> ProjectUseCases:
    config = ServerConfig.load()
    return ProjectUseCases(
        workspace_store=WorkspaceStore(config.workspace_root),
        podman_service=PodmanService(
            podman_binary=config.podman_binary,
            base_image=config.base_image,
            container_command=config.container_command,
            warmup_command=config.warmup_command,
        ),
    )


def _emit(runtime, exit_code: int) -> int:
    payload = runtime.as_dict()
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return exit_code


def _emit_error(message: str) -> int:
    payload = {
        "workspace_path": "",
        "flake_path": "",
        "container_name": "",
        "stdout": "",
        "stderr": message,
    }
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = sys.stdin.buffer.read()
    use_cases = _build_use_cases()
    spec = ProjectSpec(name=args.name, flake_relative_path=args.flake)

    try:
        if args.project_command == "launch":
            runtime, exit_code = use_cases.launch(spec, payload)
            return _emit(runtime, exit_code)
        if args.project_command == "rebuild-switch":
            runtime, exit_code = use_cases.rebuild_switch(spec, payload)
            return _emit(runtime, exit_code)
    except (FileNotFoundError, ValueError) as error:
        return _emit_error(str(error))
    except Exception as error:
        return _emit_error(f"{error}\n{traceback.format_exc()}")

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
