from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import paramiko  # pip install paramiko
import logging

from .log import append  # Assuming this is your logging helper; keep it if it exists

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

# ---------- Shared SSH Manager (new addition for reuse) -----------------------
class SSHManager:
    _instance = None

    @classmethod
    def get_instance(cls, host: str, port: int, username: str, password: str):
        """Get the shared SSH connection. Creates it if it doesn't exist."""
        if cls._instance is None:
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    password=password,
                    timeout=10,  # Added to avoid hangs
                    look_for_keys=False,
                    allow_agent=False
                )
                cls._instance = client
                logging.info(f"SSH connection established to {host}:{port}")
                append(f"LOGIN {host}:{port}")  # Your legacy logging
            except Exception as e:
                logging.error(f"Failed to connect: {e}")
                raise
        return cls._instance

    @classmethod
    def close(cls):
        """Close the shared SSH connection when done."""
        if cls._instance:
            cls._instance.close()
            logging.info("SSH connection closed")
            append("CLOSE")  # Your legacy logging
            cls._instance = None

# ---------- SSH client (updated to use shared manager) ------------------------
class MikrotikClient:
    """
    Convenience wrapper around Paramiko for RouterOS CLI access.

    Usage:
        with MikrotikClient("192.0.2.1", "admin", "secret") as mt:
            print(mt.cmd("/system identity print"))

    New: Uses shared SSH connection to reuse across the app.
    """

    def __init__(self, host: str, user: str, password: str, port: int = 22) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self._ssh = None  # We'll set this in login using the manager

    # ---------------------------------------------------------------- connect
    def login(self) -> None:
        self._ssh = SSHManager.get_instance(self.host, self.port, self.user, self.password)

    def close(self) -> None:
        SSHManager.close()  # Close the shared one

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