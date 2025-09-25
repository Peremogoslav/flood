# config.py
import json
import os
from constants import CONFIG_FILE

_DEFAULT_CONFIG = {
    "min_delay": 10,
    "max_delay": 15,
    "randomize_chats": True,
    "use_images": False
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(_DEFAULT_CONFIG)
        return dict(_DEFAULT_CONFIG)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except Exception:
            cfg = dict(_DEFAULT_CONFIG)
            save_config(cfg)
    # ensure defaults present
    for k, v in _DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
