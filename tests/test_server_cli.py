from __future__ import annotations

import io
import json
import sys
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from mnix.server.interfaces import cli as server_cli


class FakeRuntime:
    def as_dict(self) -> dict[str, str]:
        return {
            "workspace_path": "/srv/demo",
            "flake_path": "/srv/demo/flake.nix",
            "container_name": "mnix-demo",
            "stdout": "ready",
            "stderr": "",
        }


class FakeUseCases:
    def __init__(self) -> None:
        self.exec_calls: list[tuple[str, str, list[str]]] = []
        self.launch_calls: list[tuple[str, str, bytes]] = []

    def list_running_containers(self) -> list[str]:
        return ["mnix-demo"]

    def launch(self, spec, payload: bytes):
        self.launch_calls.append((spec.name, spec.flake_relative_path, payload))
        return FakeRuntime(), 0

    def exec(self, spec, command: list[str]) -> int:
        self.exec_calls.append((spec.name, spec.flake_relative_path, command))
        return 5


class ServerCliTests(unittest.TestCase):
    def test_exec_accepts_passthrough_arguments(self) -> None:
        use_cases = FakeUseCases()

        with patch(
            "mnix.server.interfaces.cli._build_use_cases", return_value=use_cases
        ):
            exit_code = server_cli.main(
                [
                    "project",
                    "exec",
                    "--name",
                    "demo",
                    "--flake",
                    "flake.nix",
                    "echo",
                    "-n",
                    "hello",
                ]
            )

        self.assertEqual(5, exit_code)
        self.assertEqual(
            ("demo", "flake.nix", ["echo", "-n", "hello"]),
            use_cases.exec_calls[0],
        )

    def test_launch_emits_json_payload(self) -> None:
        use_cases = FakeUseCases()
        stdout = io.StringIO()
        stdin = type("Stdin", (), {"buffer": io.BytesIO(b"payload")})()

        with (
            patch(
                "mnix.server.interfaces.cli._build_use_cases", return_value=use_cases
            ),
            patch.object(sys, "stdin", stdin),
            patch.object(sys, "stdout", stdout),
        ):
            exit_code = server_cli.main(
                [
                    "project",
                    "launch",
                    "--name",
                    "demo",
                    "--flake",
                    "flake.nix",
                ]
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(("demo", "flake.nix", b"payload"), use_cases.launch_calls[0])
        self.assertEqual("mnix-demo", json.loads(stdout.getvalue())["container_name"])

    def test_help_supports_short_flag(self) -> None:
        runner = CliRunner()

        result = runner.invoke(server_cli.cli, ["-h"])

        self.assertEqual(0, result.exit_code)
        self.assertIn("Usage:", result.output)

    def test_project_ls_emits_json_payload(self) -> None:
        use_cases = FakeUseCases()
        stdout = io.StringIO()

        with (
            patch(
                "mnix.server.interfaces.cli._build_use_cases", return_value=use_cases
            ),
            patch.object(sys, "stdout", stdout),
        ):
            exit_code = server_cli.main(["project", "ls"])

        self.assertEqual(0, exit_code)
        self.assertEqual(["mnix-demo"], json.loads(stdout.getvalue())["containers"])


if __name__ == "__main__":
    unittest.main()
