# utils/action_manager.py
import json, threading
from pathlib import Path
from datetime import datetime

_ACTIONS_FILE = Path(__file__).resolve().parent.parent / "action_history.json"
_LOCK = threading.Lock()


class ActionManager:
    def __init__(self, path: Path = _ACTIONS_FILE):
        self.path = path
        self._ensure_file()

    # ------------------------------------------------ file helpers
    def _ensure_file(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load(self):
        with _LOCK, self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, actions):
        with _LOCK, self.path.open("w", encoding="utf-8") as fh:
            json.dump(actions, fh, indent=2)

    # ------------------------------------------------ public API
    def record(self, kind: str, details: dict) -> int:
        actions = self._load()
        entry = {
            "id": len(actions) + 1,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": kind,
            "details": details,
        }
        actions.append(entry)
        self._save(actions)
        return entry["id"]

    def list_actions(self) -> list[dict]:
        return self._load()

    def clear(self):
        self._save([])

    def undo(self, action_id: int, ssh_client) -> None:
        entry = next((a for a in self._load() if a["id"] == action_id), None)
        if not entry:
            raise ValueError(f"Action {action_id} not found")

        inv = entry["details"].get("inverse_cmds")
        if not inv:
            raise NotImplementedError("Nothing to undo for this action")

        for cmd in inv:
            out, err = ssh_client.execute(cmd)
            if err or "failure" in out.lower():
                raise RuntimeError(f"Undo failed on '{cmd}': {err or out}")


# singleton
manager = ActionManager()
