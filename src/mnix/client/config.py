from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mnix.shared.config import read_toml
from mnix.shared.paths import config_dir, ensure_parent, state_dir

DEFAULT_CLIENT_DB_PATH = state_dir() / "client.db"


@dataclass(slots=True)
class ClientConfig:
    ssh_binary: str = "ssh"
    remote_binary: str = "mnix-server"
    remote_podman_binary: str = "podman"
    default_server: str | None = None
    database_path: Path = DEFAULT_CLIENT_DB_PATH

    @classmethod
    def load(cls) -> "ClientConfig":
        explicit = os.environ.get("MNIX_CLIENT_CONFIG")
        config_path = Path(explicit).expanduser() if explicit else config_dir() / "client.toml"
        data = read_toml(config_path)

        database_value = data.get("database_path")
        if database_value:
            database_path = Path(database_value).expanduser()
        else:
            database_path = DEFAULT_CLIENT_DB_PATH

        ensure_parent(database_path)
        return cls(
            ssh_binary=data.get("ssh_binary", "ssh"),
            remote_binary=data.get("remote_binary", "mnix-server"),
            remote_podman_binary=data.get("remote_podman_binary", "podman"),
            default_server=data.get("default_server"),
            database_path=database_path,
        )
