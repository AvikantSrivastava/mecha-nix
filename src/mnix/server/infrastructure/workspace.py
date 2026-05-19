import os
import shutil
import tarfile
from pathlib import Path

from mnix.shared.text import slugify


class WorkspaceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def project_path(self, project_name: str) -> Path:
        return self.root / slugify(project_name)

    def replace_from_archive(
        self, project_name: str, stream, flake_relative_path: str
    ) -> tuple[Path, Path]:
        workspace_path = self.project_path(project_name)
        if workspace_path.exists():
            shutil.rmtree(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=stream, mode="r:gz") as archive:
            self._safe_extract(archive, workspace_path)
        flake_path = (workspace_path / flake_relative_path).resolve()
        if not flake_path.exists():
            raise FileNotFoundError(
                f"flake not found in uploaded archive: {flake_relative_path}"
            )
        return workspace_path, flake_path

    def delete_project(self, project_name: str) -> bool:
        workspace_path = self.project_path(project_name)
        if not workspace_path.exists():
            return False
        shutil.rmtree(workspace_path)
        return True

    @staticmethod
    def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
        destination = destination.resolve()
        for member in archive.getmembers():
            member_path = (destination / member.name).resolve()
            common_prefix = os.path.commonpath([destination, member_path])
            if common_prefix != str(destination):
                raise ValueError(f"unsafe archive member: {member.name}")
        archive.extractall(destination)
