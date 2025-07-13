#utils/settings.py
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"

def load_settings():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"limit_at_default": "1600k/6200k"}

def save_settings(settings):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(settings, f, indent=2)

def get_limit_at_default():
    return load_settings().get("limit_at_default", "1600k/6200k")

def set_limit_at_default(value):
    settings = load_settings()
    settings["limit_at_default"] = value
    save_settings(settings)
