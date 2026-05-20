from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ArchiveBundle:
    workspace_root: Path
    flake_relative_path: str
    payload: bytes


def build_archive(flake_path: Path) -> ArchiveBundle:
    resolved_flake = flake_path.expanduser().resolve()
    if not resolved_flake.exists():
        raise FileNotFoundError(f"flake path does not exist: {resolved_flake}")
    if resolved_flake.name != "flake.nix":
        raise ValueError(f"expected a flake.nix file, got: {resolved_flake}")

    workspace_root = resolved_flake.parent
    relative_flake = resolved_flake.relative_to(workspace_root).as_posix()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(workspace_root, arcname=".")
    return ArchiveBundle(
        workspace_root=workspace_root,
        flake_relative_path=relative_flake,
        payload=buffer.getvalue(),
    )
