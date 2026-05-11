from __future__ import annotations

import unittest

from mnix.server.infrastructure.config import ServerConfig


class ServerConfigTests(unittest.TestCase):
    def test_default_warmup_command_enables_flakes(self) -> None:
        self.assertIn("nix-command flakes", ServerConfig().warmup_command)


if __name__ == "__main__":
    unittest.main()
