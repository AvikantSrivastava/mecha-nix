# from __future__ import annotations

import os
from pathlib import Path


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def config_dir() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    if root:
        return _expand_path(root) / "mnix"
    return Path.home() / ".config" / "mnix"


def state_dir() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return _expand_path(root) / "mnix"
    return Path.home() / ".local" / "state" / "mnix"


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
