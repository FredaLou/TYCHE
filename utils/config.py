# utils/config.py
import os
import yaml
from functools import lru_cache

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_config() -> dict:
    return load_config()