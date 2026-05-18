from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import rich_click as click
from rich.console import Console
from rich.table import Table

from mnix.client.config import ClientConfig
from mnix.client.db import Database
from mnix.client.repository import ClientRepository
from mnix.client.service import ClientService
from mnix.client.transport import SSHTransport

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
EXEC_SETTINGS = {
    **HELP_SETTINGS,
    "ignore_unknown_options": True,
}


def _normalize_endpoint(endpoint: str) -> str:
    return endpoint.removeprefix("ssh://")


def _console(*, stderr: bool = False) -> Console:
    return Console(stderr=stderr)


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

    table = Table(title="Projects")
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Server", style="magenta")

    for index, project in enumerate(projects, start=1):
        table.add_row(str(index), project.name, project.server_name)

    _console().print(table)

    choice = click.prompt(
        "Select project number",
        type=click.IntRange(1, len(projects)),
        show_choices=False,
    )
    return projects[choice - 1].name


def _run_client(action: Callable[[ClientService], int | None]) -> int:
    try:
        service = _build_service()
        result = action(service)
        return 0 if result is None else result
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        raise click.ClickException(str(error)) from error


def _render_projects(projects: list, selected: str | None) -> None:
    table = Table(title="Projects")
    table.add_column("Name", style="bold")
    table.add_column("Server", style="magenta")
    table.add_column("Container", style="cyan")
    table.add_column("Workspace", overflow="fold")

    for project in projects:
        name = (
            f"[bold green]* {project.name}[/bold green]"
            if project.name == selected
            else project.name
        )
        table.add_row(
            name,
            project.server_name,
            project.container_name,
            project.remote_workspace,
        )

    _console().print(table)


def _render_servers(servers: list) -> None:
    table = Table(title="Servers")
    table.add_column("Name", style="bold")
    table.add_column("Endpoint", style="cyan")

    for item in servers:
        table.add_row(item.name, item.endpoint)

    _console().print(table)


@click.group(
    context_settings=HELP_SETTINGS,
    help="Manage remote development projects.",
    no_args_is_help=True,
)
def cli() -> None:
    pass


@cli.command("ls")
def list_projects() -> int:
    def action(service: ClientService) -> int:
        selected = service.repository.get_selected_project_name()
        _render_projects(service.list_projects(), selected)
        return 0

    return _run_client(action)


@cli.command()
@click.option("--server", help="Server name.")
def sync(server: str | None) -> int:
    def action(service: ClientService) -> int:
        status = service.sync_status(server_name=server)
        if not status.matched_projects and not status.missing_projects:
            click.echo(f"no client projects tracked for server {status.server.name}")
            return 0
        if not status.missing_projects:
            click.echo(f"server {status.server.name} is in sync")
            return 0

        for project in status.missing_projects:
            should_purge = click.confirm(
                (
                    f"Container {project.container_name} for project {project.name} "
                    f"is missing on server {status.server.name}. Purge local client state?"
                ),
                default=False,
            )
            if should_purge:
                click.echo(service.purge_project(project.name))
            else:
                click.echo(f"kept local state for project {project.name}")
        return 0

    return _run_client(action)


@cli.command()
@click.argument("name", required=False)
def select(name: str | None) -> int:
    def action(service: ClientService) -> int:
        selection = name if name is not None else _interactive_project_choice(service)
        click.echo(service.select_project(selection))
        return 0

    return _run_client(action)


@cli.command()
@click.argument("name")
@click.option(
    "--flake",
    "-f",
    default="./flake.nix",
    show_default=True,
    help="Path to flake.nix.",
)
@click.option("--server", help="Server name.")
def new(name: str, flake: str, server: str | None) -> int:
    def action(service: ClientService) -> int:
        result = service.new_project(
            name=name,
            flake_path=Path(flake),
            server_name=server,
        )
        click.echo(result.message)
        if result.stdout.strip():
            click.echo(result.stdout.strip())
        if result.stderr.strip():
            click.echo(result.stderr.strip(), err=True)
        return 0

    return _run_client(action)


@cli.command("rebuild-switch")
@click.argument("flake", required=False)
@click.option("--project", help="Project name.")
def rebuild_switch(flake: str | None, project: str | None) -> int:
    def action(service: ClientService) -> int:
        flake_path = None if flake is None else Path(flake)
        result = service.rebuild_switch(flake_path=flake_path, project_name=project)
        click.echo(result.message)
        if result.stdout.strip():
            click.echo(result.stdout.strip())
        if result.stderr.strip():
            click.echo(result.stderr.strip(), err=True)
        return 0

    return _run_client(action)


@cli.command()
@click.option("--project", help="Project name.")
def shell(project: str | None) -> int:
    return _run_client(lambda service: service.shell(project_name=project))


@cli.command(context_settings=EXEC_SETTINGS)
@click.option("--project", help="Project name.")
@click.argument("exec_command", nargs=-1, type=click.UNPROCESSED)
def exec(project: str | None, exec_command: tuple[str, ...]) -> int:
    return _run_client(
        lambda service: service.exec(command=list(exec_command), project_name=project)
    )


@cli.group(
    context_settings=HELP_SETTINGS,
    help="Manage configured servers.",
    no_args_is_help=True,
)
def server() -> None:
    pass


@server.command("ls")
def list_servers() -> int:
    def action(service: ClientService) -> int:
        _render_servers(service.list_servers())
        return 0

    return _run_client(action)


@server.command("add")
@click.argument("endpoint")
@click.argument("name")
def add_server(endpoint: str, name: str) -> int:
    return _run_client(
        lambda service: click.echo(
            service.add_server(endpoint=_normalize_endpoint(endpoint), name=name)
        )
    )


@server.command("rm")
@click.argument("name")
def remove_server(name: str) -> int:
    return _run_client(lambda service: click.echo(service.remove_server(name)))


def main(argv: list[str] | None = None) -> int:
    try:
        result = cli.main(args=argv, prog_name="mnix", standalone_mode=False)
        return 0 if result is None else result
    except click.Abort:
        click.echo("Aborted!", err=True)
        return 1
    except click.ClickException as error:
        error.show(file=sys.stderr)
        return error.exit_code
    except click.exceptions.Exit as error:
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
