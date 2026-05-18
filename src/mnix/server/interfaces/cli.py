from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable

import rich_click as click

from mnix.server.application.use_cases import ProjectUseCases
from mnix.server.domain.entities import ProjectSpec
from mnix.server.infrastructure.config import ServerConfig
from mnix.server.infrastructure.podman import PodmanService
from mnix.server.infrastructure.workspace import WorkspaceStore

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
EXEC_SETTINGS = {
    **HELP_SETTINGS,
    "ignore_unknown_options": True,
}


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


def _emit_json(payload: dict[str, object], exit_code: int) -> int:
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return exit_code


def _emit(runtime, exit_code: int) -> int:
    return _emit_json(runtime.as_dict(), exit_code)


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


def _emit_attached_error(message: str) -> int:
    click.echo(message, err=True)
    return 1


def _project_spec(name: str, flake: str) -> ProjectSpec:
    return ProjectSpec(name=name, flake_relative_path=flake)


def _attached_command(
    action: Callable[[ProjectUseCases], int],
) -> int:
    try:
        return action(_build_use_cases())
    except (FileNotFoundError, ValueError) as error:
        return _emit_attached_error(str(error))
    except Exception as error:
        return _emit_attached_error(f"{error}\n{traceback.format_exc()}")


def _detached_command(
    action: Callable[[ProjectUseCases], int],
) -> int:
    try:
        return action(_build_use_cases())
    except (FileNotFoundError, ValueError) as error:
        return _emit_error(str(error))
    except Exception as error:
        return _emit_error(f"{error}\n{traceback.format_exc()}")


def _project_options(command: Callable) -> Callable:
    command = click.option(
        "--flake", required=True, help="Relative flake path inside the archive."
    )(command)
    command = click.option("--name", required=True, help="Project name.")(command)
    return command


@click.group(
    context_settings=HELP_SETTINGS,
    help="Run remote project lifecycle operations.",
    no_args_is_help=True,
)
def cli() -> None:
    pass


@cli.group(
    context_settings=HELP_SETTINGS,
    help="Project lifecycle commands.",
    no_args_is_help=True,
)
def project() -> None:
    pass


@project.command("ls")
def list_projects() -> int:
    def action(use_cases: ProjectUseCases) -> int:
        return _emit_json({"containers": use_cases.list_running_containers()}, 0)

    return _detached_command(action)


@project.command()
@_project_options
def launch(name: str, flake: str) -> int:
    def action(use_cases: ProjectUseCases) -> int:
        runtime, exit_code = use_cases.launch(
            _project_spec(name, flake), sys.stdin.buffer.read()
        )
        return _emit(runtime, exit_code)

    return _detached_command(action)


@project.command("rebuild-switch")
@_project_options
def rebuild_switch(name: str, flake: str) -> int:
    def action(use_cases: ProjectUseCases) -> int:
        runtime, exit_code = use_cases.rebuild_switch(
            _project_spec(name, flake),
            sys.stdin.buffer.read(),
        )
        return _emit(runtime, exit_code)

    return _detached_command(action)


@project.command()
@_project_options
def shell(name: str, flake: str) -> int:
    return _attached_command(
        lambda use_cases: use_cases.shell(_project_spec(name, flake))
    )


@project.command(context_settings=EXEC_SETTINGS)
@_project_options
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def exec(name: str, flake: str, command: tuple[str, ...]) -> int:
    if not command:
        return _emit_attached_error("command required")
    return _attached_command(
        lambda use_cases: use_cases.exec(_project_spec(name, flake), list(command))
    )


def main(argv: list[str] | None = None) -> int:
    try:
        result = cli.main(args=argv, prog_name="mnix-server", standalone_mode=False)
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
