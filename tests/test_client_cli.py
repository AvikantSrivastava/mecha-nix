from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from mnix.client import cli as client_cli


class FakeClientService:
    def __init__(self) -> None:
        self.exec_calls: list[tuple[list[str], str | None]] = []
        self.select_calls: list[str] = []
        self.add_server_calls: list[tuple[str, str]] = []
        self.sync_calls: list[str | None] = []
        self.purge_calls: list[str] = []
        self.repository = SimpleNamespace(get_selected_project_name=lambda: "beta")

    def list_projects(self):
        return [
            SimpleNamespace(
                name="alpha",
                server_name="dev",
                container_name="mnix-alpha",
                remote_workspace="/tmp/mnix/workspaces/alpha",
            ),
            SimpleNamespace(
                name="beta",
                server_name="prod",
                container_name="mnix-beta",
                remote_workspace="/tmp/mnix/workspaces/beta",
            ),
        ]

    def list_servers(self):
        return [
            SimpleNamespace(name="dev", endpoint="user@example.com"),
            SimpleNamespace(name="prod", endpoint="prod.example.com"),
        ]

    def select_project(self, name: str) -> str:
        self.select_calls.append(name)
        return f"selected {name}"

    def exec(self, command: list[str], project_name: str | None = None) -> int:
        self.exec_calls.append((command, project_name))
        return 7

    def add_server(self, endpoint: str, name: str) -> str:
        self.add_server_calls.append((endpoint, name))
        return f"added {name}"

    def sync_status(self, server_name: str | None = None):
        self.sync_calls.append(server_name)
        return SimpleNamespace(
            server=SimpleNamespace(name="dev"),
            matched_projects=[
                SimpleNamespace(
                    name="beta",
                    container_name="mnix-beta",
                )
            ],
            missing_projects=[
                SimpleNamespace(
                    name="alpha",
                    container_name="mnix-alpha",
                )
            ],
        )

    def purge_project(self, name: str) -> str:
        self.purge_calls.append(name)
        return f"purged local state for project {name}"


class ClientCliTests(unittest.TestCase):
    def test_ls_renders_rich_table(self) -> None:
        service = FakeClientService()
        runner = CliRunner()

        with patch("mnix.client.cli._build_service", return_value=service):
            result = runner.invoke(client_cli.cli, ["ls"])

        self.assertEqual(0, result.exit_code)
        self.assertIn("Projects", result.output)
        self.assertIn("alpha", result.output)
        self.assertIn("* beta", result.output)
        self.assertIn("mnix-beta", result.output)

    def test_exec_accepts_passthrough_arguments(self) -> None:
        service = FakeClientService()

        with patch("mnix.client.cli._build_service", return_value=service):
            exit_code = client_cli.main(
                ["exec", "--project", "demo", "echo", "-n", "hello"]
            )

        self.assertEqual(7, exit_code)
        self.assertEqual((["echo", "-n", "hello"], "demo"), service.exec_calls[0])

    def test_select_uses_click_prompt_for_interactive_choice(self) -> None:
        service = FakeClientService()
        runner = CliRunner()

        with patch("mnix.client.cli._build_service", return_value=service):
            result = runner.invoke(client_cli.cli, ["select"], input="2\n")

        self.assertEqual(0, result.exit_code)
        self.assertIn("Projects", result.output)
        self.assertIn("alpha", result.output)
        self.assertIn("beta", result.output)
        self.assertIn("selected beta", result.output)
        self.assertEqual(["beta"], service.select_calls)

    def test_server_ls_renders_rich_table(self) -> None:
        service = FakeClientService()
        runner = CliRunner()

        with patch("mnix.client.cli._build_service", return_value=service):
            result = runner.invoke(client_cli.cli, ["server", "ls"])

        self.assertEqual(0, result.exit_code)
        self.assertIn("Servers", result.output)
        self.assertIn("user@example.com", result.output)

    def test_server_add_normalizes_ssh_prefix(self) -> None:
        service = FakeClientService()

        with patch("mnix.client.cli._build_service", return_value=service):
            exit_code = client_cli.main(
                ["server", "add", "ssh://user@example.com", "dev"]
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(("user@example.com", "dev"), service.add_server_calls[0])

    def test_sync_prompts_to_purge_missing_project_state(self) -> None:
        service = FakeClientService()
        runner = CliRunner()

        with patch("mnix.client.cli._build_service", return_value=service):
            result = runner.invoke(client_cli.cli, ["sync"], input="y\n")

        self.assertEqual(0, result.exit_code)
        self.assertIn("Container mnix-alpha for project alpha is missing", result.output)
        self.assertIn("purged local state for project alpha", result.output)
        self.assertEqual([None], service.sync_calls)
        self.assertEqual(["alpha"], service.purge_calls)


if __name__ == "__main__":
    unittest.main()
