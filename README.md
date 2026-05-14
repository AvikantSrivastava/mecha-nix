# mnix

`mnix` is a lightweight Python implementation of a remote development workflow built around Nix flakes, SSH, and Podman.

The repository includes a root `flake.nix`, so `mnix new` can use the default `./flake.nix` and `nix develop` works directly from the project root.

## Commands

### Client

```bash
mnix ls
mnix select [project-name]
mnix new [-f path/to/flake.nix] [--server server-name] project-name
mnix rebuild-switch [path/to/flake.nix] [--project project-name]
mnix shell [--project project-name]
mnix exec [--project project-name] -- command [args...]
mnix server ls
mnix server add ssh://user@example.com server-name
mnix server rm server-name
```

### Server

The client talks to the server by invoking `mnix-server` over SSH. The server CLI is structured so it can later be reused behind Flask or FastAPI.

```bash
mnix-server project launch --name project-name --flake flake.nix
mnix-server project rebuild-switch --name project-name --flake flake.nix
mnix-server project shell --name project-name --flake flake.nix
mnix-server project exec --name project-name --flake flake.nix -- command [args...]
```

## Configuration

Both client and server use TOML configuration.

### Client config

Default path: `~/.config/mnix/client.toml`

```toml
ssh_binary = "ssh"
remote_binary = "mnix-server"
remote_podman_binary = "podman"
default_server = "my-server"
database_path = "~/.local/state/mnix/client.db"
```

### Server config

Default path: `~/.config/mnix/server.toml`

```toml
podman_binary = "podman"
base_image = "docker.io/nixos/nix:latest"
workspace_root = "/tmp/mnix/workspaces"
warmup_command = "nix --extra-experimental-features 'nix-command flakes' develop -c true"
container_command = "sleep infinity"
```

## Architecture

- `src/mnix/client`: thin CLI, local SQLite state, SSH transport, workspace archiving.
- `src/mnix/server/domain`: domain entities and value objects.
- `src/mnix/server/application`: use cases for project launch and rebuild.
- `src/mnix/server/infrastructure`: Podman runner, config loading, workspace extraction.
- `src/mnix/server/interfaces`: server CLI adapter.

The current implementation is intentionally stateless on the server side: it stages a workspace, ensures a Podman container exists for the project, and returns command results directly to the client.
