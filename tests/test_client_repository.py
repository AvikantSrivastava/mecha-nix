from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mnix.client.db import Database
from mnix.client.repository import ClientRepository, ProjectRecord


class ClientRepositoryTests(unittest.TestCase):
    def test_server_and_project_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Database(Path(tmpdir) / "client.db")
            repository = ClientRepository(database)

            repository.add_server("alpha", "devbox")
            repository.upsert_project(
                ProjectRecord(
                    name="demo",
                    server_name="alpha",
                    local_flake_path="/tmp/flake.nix",
                    remote_workspace="/srv/demo",
                    remote_flake_path="/srv/demo/flake.nix",
                    container_name="mnix-demo",
                )
            )
            repository.set_selected_project("demo")

            self.assertEqual("demo", repository.get_selected_project_name())
            self.assertEqual("alpha", repository.get_project("demo").server_name)
            self.assertEqual("devbox", repository.get_server("alpha").endpoint)

    def test_delete_project_clears_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Database(Path(tmpdir) / "client.db")
            repository = ClientRepository(database)

            repository.add_server("alpha", "devbox")
            repository.upsert_project(
                ProjectRecord(
                    name="demo",
                    server_name="alpha",
                    local_flake_path="/tmp/flake.nix",
                    remote_workspace="/srv/demo",
                    remote_flake_path="/srv/demo/flake.nix",
                    container_name="mnix-demo",
                )
            )
            repository.set_selected_project("demo")

            self.assertTrue(repository.delete_project("demo"))
            self.assertIsNone(repository.get_project("demo"))
            self.assertIsNone(repository.get_selected_project_name())


if __name__ == "__main__":
    unittest.main()
