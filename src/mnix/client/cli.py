from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mnix.client.config import ClientConfig
from mnix.client.db import Database
from mnix.client.repository import ClientRepository
from mnix.client.service import ClientService
from mnix.client.transport import SSHTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mnix")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ls", help="List projects")

    select_parser = subparsers.add_parser("select", help="Select a project")
    select_parser.add_argument("name", nargs="?", help="Project name")

    new_parser = subparsers.add_parser("new", help="Launch a new project")
    new_parser.add_argument("name", help="Project name")
    new_parser.add_argument(
        "-f",
        "--flake",
        default="./flake.nix",
        help="Path to flake.nix (default: ./flake.nix)",
    )
    new_parser.add_argument("--server", help="Server name")

    rebuild_parser = subparsers.add_parser("rebuild-switch", help="Rebuild the selected project")
    rebuild_parser.add_argument(
        "flake",
        nargs="?",
        default=None,
        help="Path to flake.nix (default: selected project's flake)",
    )
    rebuild_parser.add_argument("--project", help="Project name")

    server_parser = subparsers.add_parser("server", help="Manage servers")
    server_subparsers = server_parser.add_subparsers(dest="server_command", required=True)
    server_subparsers.add_parser("ls", help="List servers")

    add_parser = server_subparsers.add_parser("add", help="Add or update a server")
    add_parser.add_argument("endpoint", help="SSH endpoint, e.g. ssh://user@example.com")
    add_parser.add_argument("name", help="Server name")

    remove_parser = server_subparsers.add_parser("rm", help="Remove a server")
    remove_parser.add_argument("name", help="Server name")

    return parser


def _normalize_endpoint(endpoint: str) -> str:
    return endpoint.removeprefix("ssh://")


def _build_service() -> ClientService:
    config = ClientConfig.load()
    database = Database(config.database_path)
    repository = ClientRepository(database)
    transport = SSHTransport(config.ssh_binary, config.remote_binary)
    return ClientService(repository, config, transport)


def _interactive_project_choice(service: ClientService) -> str:
    projects = service.list_projects()
    if not projects:
        raise ValueError("no projects found")
    if len(projects) == 1:
        return projects[0].name

    for index, project in enumerate(projects, start=1):
        print(f"{index}. {project.name} ({project.server_name})")

    choice = input("Select project number: ").strip()
    if not choice.isdigit():
        raise ValueError("selection must be a number")

    selected_index = int(choice) - 1
    if selected_index < 0 or selected_index >= len(projects):
        raise ValueError("selection out of range")
    return projects[selected_index].name


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = _build_service()

    try:
        if args.command == "ls":
            selected = service.repository.get_selected_project_name()
            for project in service.list_projects():
                marker = "*" if project.name == selected else " "
                print(
                    f"{marker} {project.name}\tserver={project.server_name}\tcontainer={project.container_name}\tworkspace={project.remote_workspace}"
                )
            return 0

        if args.command == "select":
            selection = args.name if args.name is not None else _interactive_project_choice(service)
            print(service.select_project(selection))
            return 0

        if args.command == "new":
            result = service.new_project(
                name=args.name,
                flake_path=Path(args.flake),
                server_name=args.server,
            )
            print(result.message)
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
            return 0

        if args.command == "rebuild-switch":
            flake = None if args.flake is None else Path(args.flake)
            result = service.rebuild_switch(flake_path=flake, project_name=args.project)
            print(result.message)
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
            return 0

        if args.command == "server":
            if args.server_command == "ls":
                for server in service.list_servers():
                    print(f"{server.name}\t{server.endpoint}")
                return 0
            if args.server_command == "add":
                print(service.add_server(endpoint=_normalize_endpoint(args.endpoint), name=args.name))
                return 0
            if args.server_command == "rm":
                print(service.remove_server(args.name))
                return 0

        parser.error("unknown command")
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
