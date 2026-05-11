from __future__ import annotations

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

    def run(self, endpoint: str, args: list[str], payload: bytes | None = None) -> RemoteExecution:
        remote_command = " ".join(shlex.quote(part) for part in [self.remote_binary, *args])
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
