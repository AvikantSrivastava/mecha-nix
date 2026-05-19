import json
import shlex
import subprocess
from dataclasses import dataclass


@dataclass(slots=True)
class RemoteExecution:
    returncode: int
    stdout: str
    stderr: str

    def decode_json(self) -> dict:
        if not self.stdout.strip():
            raise ValueError("remote command returned no JSON payload")
        return json.loads(self.stdout)


class SSHTransport:
    def __init__(self, ssh_binary: str, remote_binary: str) -> None:
        self.ssh_binary = ssh_binary
        self.remote_binary = remote_binary

    def _remote_command(self, args: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in [self.remote_binary, *args])

    @staticmethod
    def _quote_command(args: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in args)

    def run(
        self, endpoint: str, args: list[str], payload: bytes | None = None
    ) -> RemoteExecution:
        remote_command = self._remote_command(args)
        completed = subprocess.run(
            [self.ssh_binary, endpoint, remote_command],
            input=payload,
            capture_output=True,
            check=False,
        )
        return RemoteExecution(
            returncode=completed.returncode,
            stdout=completed.stdout.decode(),
            stderr=completed.stderr.decode(),
        )

    def attach(
        self, endpoint: str, args: list[str], *, allocate_tty: bool = False
    ) -> int:
        command = [self.ssh_binary]
        if allocate_tty:
            command.append("-tt")
        command.extend([endpoint, self._remote_command(args)])
        completed = subprocess.run(command, check=False)
        return completed.returncode

    def attach_command(
        self, endpoint: str, command_args: list[str], *, allocate_tty: bool = False
    ) -> int:
        command = [self.ssh_binary]
        if allocate_tty:
            command.append("-tt")
        command.extend([endpoint, self._quote_command(command_args)])
        completed = subprocess.run(command, check=False)
        return completed.returncode

    def rm(self, endpoint: str, project_name: str) -> RemoteExecution:
        return self.run(endpoint, ["project", "rm", "--name", project_name])
