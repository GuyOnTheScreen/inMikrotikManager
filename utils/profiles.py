import json, os
from pathlib import Path

_PROF_PATH = Path(__file__).resolve().parent.parent / "data" / "profiles.json"
_PROF_PATH.parent.mkdir(parents=True, exist_ok=True)
if not _PROF_PATH.exists():          # bootstrap minimal file
    _PROF_PATH.write_text(json.dumps({
        "default": "demo",
        "profiles": {
            "demo": {
                "host": "",
                "port": 22,
                "user": "demo",
                "password": "demo",
                "note": "editable demo credentials"
            }
        }
    }, indent=2))

def _load() -> dict:
    with open(_PROF_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)

def load_default_profile() -> dict:
    d = _load()
    return d["profiles"].get(d.get("default", ""), {})

def load_all_profiles() -> dict[str, dict]:
    return _load().get("profiles", {})
