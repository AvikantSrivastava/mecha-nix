from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mnix.client.config import ClientConfig
from mnix.client.db import Database
from mnix.client.repository import ClientRepository
from mnix.client.service import ClientService
from mnix.client.transport import RemoteExecution


class FakeTransport:
    def __init__(self, response: RemoteExecution) -> None:
        self.response = response
        self.calls: list[tuple[str, list[str], bytes | None]] = []

    def run(self, endpoint: str, args: list[str], payload: bytes | None = None) -> RemoteExecution:
        self.calls.append((endpoint, args, payload))
        return self.response


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


if __name__ == "__main__":
    unittest.main()
