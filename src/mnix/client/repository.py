from dataclasses import dataclass

from mnix.client.db import Database


@dataclass(slots=True)
class ServerRecord:
    name: str
    endpoint: str


@dataclass(slots=True)
class ProjectRecord:
    name: str
    server_name: str
    local_flake_path: str
    remote_workspace: str
    remote_flake_path: str
    container_name: str


class ClientRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_servers(self) -> list[ServerRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT name, endpoint FROM servers ORDER BY name"
            ).fetchall()
        return [
            ServerRecord(name=row["name"], endpoint=row["endpoint"]) for row in rows
        ]

    def add_server(self, name: str, endpoint: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO servers(name, endpoint)
                VALUES(?, ?)
                ON CONFLICT(name) DO UPDATE SET endpoint = excluded.endpoint
                """,
                (name, endpoint),
            )

    def remove_server(self, name: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM servers WHERE name = ?", (name,))
        return cursor.rowcount > 0

    def get_server(self, name: str) -> ServerRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT name, endpoint FROM servers WHERE name = ?", (name,)
            ).fetchone()
        if row is None:
            return None
        return ServerRecord(name=row["name"], endpoint=row["endpoint"])

    def list_projects(self) -> list[ProjectRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT name, server_name, local_flake_path, remote_workspace, remote_flake_path, container_name
                FROM projects
                ORDER BY name
                """
            ).fetchall()
        return [
            ProjectRecord(
                name=row["name"],
                server_name=row["server_name"],
                local_flake_path=row["local_flake_path"],
                remote_workspace=row["remote_workspace"],
                remote_flake_path=row["remote_flake_path"],
                container_name=row["container_name"],
            )
            for row in rows
        ]

    def upsert_project(self, project: ProjectRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects(
                    name, server_name, local_flake_path, remote_workspace, remote_flake_path, container_name
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    server_name = excluded.server_name,
                    local_flake_path = excluded.local_flake_path,
                    remote_workspace = excluded.remote_workspace,
                    remote_flake_path = excluded.remote_flake_path,
                    container_name = excluded.container_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    project.name,
                    project.server_name,
                    project.local_flake_path,
                    project.remote_workspace,
                    project.remote_flake_path,
                    project.container_name,
                ),
            )

    def get_project(self, name: str) -> ProjectRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT name, server_name, local_flake_path, remote_workspace, remote_flake_path, container_name
                FROM projects
                WHERE name = ?
                """,
                (name,),
            ).fetchone()
        if row is None:
            return None
        return ProjectRecord(
            name=row["name"],
            server_name=row["server_name"],
            local_flake_path=row["local_flake_path"],
            remote_workspace=row["remote_workspace"],
            remote_flake_path=row["remote_flake_path"],
            container_name=row["container_name"],
        )

    def delete_project(self, name: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM projects WHERE name = ?", (name,))
            if cursor.rowcount:
                connection.execute(
                    "DELETE FROM settings WHERE key = 'selected_project' AND value = ?",
                    (name,),
                )
        return cursor.rowcount > 0

    def set_selected_project(self, name: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value) VALUES('selected_project', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (name,),
            )

    def get_selected_project_name(self) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = 'selected_project'"
            ).fetchone()
        return None if row is None else row["value"]
