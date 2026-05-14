from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mnix.client.config import ClientConfig
from mnix.client.db import Database
from mnix.client.repository import ClientRepository, ProjectRecord
from mnix.client.service import ClientService
from mnix.client.transport import RemoteExecution


class FakeTransport:
    def __init__(self, response: RemoteExecution | None = None, attach_returncode: int = 0) -> None:
        self.response = response
        self.attach_returncode = attach_returncode
        self.calls: list[tuple[str, list[str], bytes | None]] = []
        self.attach_calls: list[tuple[str, list[str], bool]] = []
        self.attach_command_calls: list[tuple[str, list[str], bool]] = []

    def run(self, endpoint: str, args: list[str], payload: bytes | None = None) -> RemoteExecution:
        self.calls.append((endpoint, args, payload))
        if self.response is None:
            raise AssertionError("unexpected transport.run call")
        return self.response

    def attach(self, endpoint: str, args: list[str], *, allocate_tty: bool = False) -> int:
        self.attach_calls.append((endpoint, args, allocate_tty))
        return self.attach_returncode

    def attach_command(
        self, endpoint: str, command_args: list[str], *, allocate_tty: bool = False
    ) -> int:
        self.attach_command_calls.append((endpoint, command_args, allocate_tty))
        return self.attach_returncode


class ClientServiceTests(unittest.TestCase):
    def test_new_project_stores_remote_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            flake = tmp / "flake.nix"
            flake.write_text("{ description = \"demo\"; }")

            repository = ClientRepository(Database(tmp / "client.db"))
            repository.add_server("dev", "example.org")
            config = ClientConfig(database_path=tmp / "client.db")
            transport = FakeTransport(
                RemoteExecution(
                    returncode=0,
                    stdout='{"workspace_path":"/srv/demo","flake_path":"/srv/demo/flake.nix","container_name":"mnix-demo","stdout":"ready","stderr":""}',
                    stderr="",
                )
            )

            service = ClientService(repository, config, transport)
            result = service.new_project("demo", flake, server_name="dev")

            self.assertEqual("launched project demo on dev", result.message)
            self.assertEqual("demo", repository.get_selected_project_name())
            self.assertEqual("project", transport.calls[0][1][0])

    def test_new_project_surfaces_remote_stderr_when_ssh_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            flake = tmp / "flake.nix"
            flake.write_text("{ description = \"demo\"; }")

            repository = ClientRepository(Database(tmp / "client.db"))
            repository.add_server("dev", "example.org")
            config = ClientConfig(database_path=tmp / "client.db")
            transport = FakeTransport(
                RemoteExecution(
                    returncode=255,
                    stdout="",
                    stderr="bash: /bad/path/mnix-server: No such file or directory",
                )
            )

            service = ClientService(repository, config, transport)

            with self.assertRaisesRegex(RuntimeError, "No such file or directory"):
                service.new_project("demo", flake, server_name="dev")

    def test_new_project_surfaces_invalid_remote_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            flake = tmp / "flake.nix"
            flake.write_text("{ description = \"demo\"; }")

            repository = ClientRepository(Database(tmp / "client.db"))
            repository.add_server("dev", "example.org")
            config = ClientConfig(database_path=tmp / "client.db")
            transport = FakeTransport(
                RemoteExecution(
                    returncode=0,
                    stdout="Last login: today\n",
                    stderr="",
                )
            )

            service = ClientService(repository, config, transport)

            with self.assertRaisesRegex(RuntimeError, "invalid remote response"):
                service.new_project("demo", flake, server_name="dev")

    def test_shell_attaches_to_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repository = ClientRepository(Database(tmp / "client.db"))
            repository.add_server("dev", "example.org")
            repository.upsert_project(
                ProjectRecord(
                    name="demo",
                    server_name="dev",
                    local_flake_path=str(tmp / "flake.nix"),
                    remote_workspace="/srv/demo",
                    remote_flake_path="/srv/demo/nix/flake.nix",
                    container_name="mnix-demo",
                )
            )
            repository.set_selected_project("demo")
            config = ClientConfig(database_path=tmp / "client.db")
            transport = FakeTransport(attach_returncode=0)

            service = ClientService(repository, config, transport)

            self.assertEqual(0, service.shell())
            self.assertEqual(
                (
                    "example.org",
                    [
                        "podman",
                        "exec",
                        "-it",
                        "--workdir",
                        "/workspace/nix",
                        "mnix-demo",
                        "nix",
                        "--extra-experimental-features",
                        "nix-command flakes",
                        "develop",
                    ],
                    True,
                ),
                transport.attach_command_calls[0],
            )

    def test_exec_runs_command_in_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repository = ClientRepository(Database(tmp / "client.db"))
            repository.add_server("dev", "example.org")
            repository.upsert_project(
                ProjectRecord(
                    name="demo",
                    server_name="dev",
                    local_flake_path=str(tmp / "flake.nix"),
                    remote_workspace="/srv/demo",
                    remote_flake_path="/srv/demo/flake.nix",
                    container_name="mnix-demo",
                )
            )
            repository.set_selected_project("demo")
            config = ClientConfig(database_path=tmp / "client.db")
            transport = FakeTransport(attach_returncode=7)

            service = ClientService(repository, config, transport)

            self.assertEqual(7, service.exec(["echo", "hello"]))
            self.assertEqual(
                (
                    "example.org",
                    [
                        "podman",
                        "exec",
                        "--workdir",
                        "/workspace",
                        "mnix-demo",
                        "nix",
                        "--extra-experimental-features",
                        "nix-command flakes",
                        "develop",
                        "-c",
                        "echo",
                        "hello",
                    ],
                    False,
                ),
                transport.attach_command_calls[0],
            )


if __name__ == "__main__":
    unittest.main()
