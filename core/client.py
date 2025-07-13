# core/client.py
"""
MikrotikClient – thin Paramiko wrapper with optional profile storage.

New in this revision
--------------------
• Added .cmd()  – legacy helper so older controllers that expect
  `cli.cmd("/path print")` keep working.
• __enter__/__exit__ remain unchanged so you can use `with … as cli:`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import paramiko  # pip install paramiko

from .log import append

# ---------- profile helper ----------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROFILE_FILE = DATA_DIR / "profiles.json"


class Profiles:
    """Tiny JSON wrapper for saved connection presets."""

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if PROFILE_FILE.exists():
            self._cache = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))

    def _save(self) -> None:
        PROFILE_FILE.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    def get(self, name: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return self._cache.get(name, default)

    def set(self, name: str, data: Dict[str, Any]) -> None:
        self._cache[name] = data
        self._save()

    def all(self) -> Dict[str, Dict[str, Any]]:
        return self._cache.copy()


# ---------- SSH client --------------------------------------------------------
class MikrotikClient:
    """
    Convenience wrapper around Paramiko for RouterOS CLI access.

    Usage:
        with MikrotikClient("192.0.2.1", "admin", "secret") as mt:
            print(mt.cmd("/system identity print"))
    """

    def __init__(self, host: str, user: str, password: str, port: int = 22) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self._ssh: Optional[paramiko.SSHClient] = None

    # ---------------------------------------------------------------- connect
    def login(self) -> None:
        append(f"LOGIN {self.host}")
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
        )

    def close(self) -> None:
        if self._ssh:
            append(f"CLOSE {self.host}")
            self._ssh.close()
            self._ssh = None

    # -------------------------------------------------------------- commands
    def execute(self, command: str) -> tuple[str, str]:
        """Low-level helper → (stdout, stderr) as str."""
        if not self._ssh:
            raise RuntimeError("Not connected – call .login() first")
        stdin, stdout, stderr = self._ssh.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

    def run(self, command: str) -> List[str]:
        """Return stdout split into *lines*; raise if stderr not empty."""
        out, err = self.execute(command)
        if err:
            raise RuntimeError(err)
        return out.splitlines()

    # 👉 legacy alias so older controllers using .cmd() keep working
    def cmd(self, command: str) -> str:
        """Run and return *joined* stdout for back-compat."""
        return "\n".join(self.run(command))

    def ping(self, target: str, count: int = 4) -> List[str]:
        return self.run(f"ping {target} count={count}")

    # ----------------------------------------------------------- ctx manager
    def __enter__(self) -> "MikrotikClient":
        self.login()
        return self

    def __exit__(self, exc_type, *_exc) -> None:  # noqa: D401
        self.close()
