# from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mnix.shared.config import read_toml
from mnix.shared.paths import config_dir

DEFAULT_WORKSPACE_ROOT = Path("/tmp/mnix/workspaces")


@dataclass(slots=True)
class ServerConfig:
    podman_binary: str = "podman"
    base_image: str = "docker.io/nixos/nix:latest"
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT
    warmup_command: str = "nix --extra-experimental-features 'nix-command flakes' develop -c true"
    container_command: str = "sleep infinity"

    @classmethod
    def load(cls) -> "ServerConfig":
        explicit = os.environ.get("MNIX_SERVER_CONFIG")
        config_path = Path(explicit).expanduser() if explicit else config_dir() / "server.toml"
        data = read_toml(config_path)
        workspace_root = Path(data.get("workspace_root", DEFAULT_WORKSPACE_ROOT)).expanduser()
        return cls(
            podman_binary=data.get("podman_binary", "podman"),
            base_image=data.get("base_image", "docker.io/nixos/nix:latest"),
            workspace_root=workspace_root,
            warmup_command=data.get(
                "warmup_command",
                "nix --extra-experimental-features 'nix-command flakes' develop -c true",
            ),
            container_command=data.get("container_command", "sleep infinity"),
        )
