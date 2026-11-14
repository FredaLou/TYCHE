import os
import yaml
import requests
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

_config_cache = None
_config_mtime = None


def _load_config() -> Dict[str, Any]:
    """Ленивая загрузка конфига с кэшированием по mtime."""
    global _config_cache, _config_mtime
    try:
        mtime = os.path.getmtime(CONFIG_FILE)
    except OSError:
        # Если файл недоступен — возвращаем кэш или пустой словарь
        return _config_cache or {}

    if _config_cache is None or mtime != _config_mtime:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
        _config_mtime = mtime
    return _config_cache


def _get_validator_url() -> str:
    return _load_config()["model"]["fast_url"]


def _get_allowed_types() -> list:
    return _load_config().get("facts", {}).get("allowed_types", ["identity", "gender", "age", "city"])


def validate_fact(user_input: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
    candidate_type = candidate.get("type", "unknown")
    candidate_value = candidate.get("value", "")
    candidate_status = candidate.get("status", "stated")

    allowed_types = _get_allowed_types()

    prompt = f"""You are a fact validation module for a personal assistant. Analyze the user's message and determine if the extracted candidate represents a meaningful, non‑trivial fact about the user that should be stored in long‑term memory.

User message: "{user_input}"
Extracted candidate: "{candidate_value}" (type: {candidate_type}, status: {candidate_status})

Allowed fact types: {', '.join(allowed_types)}.
Rules:
- Valid facts are specific, concrete pieces of information (e.g., "My name is Freda", "I am 29", "I live in Moscow").
- Vague or meta statements are NOT facts.
- If the candidate correctly reflects the user's statement, set is_fact=true and keep or adjust type/value/status.

Respond ONLY with a JSON object:
{{"is_fact": true/false, "type": "...", "value": "...", "status": "...", "importance": 0.0-1.0}}

If not a fact: {{"is_fact": false}}
"""

    try:
        response = requests.post(
            _get_validator_url(),
            json={
                "messages": [
                    {"role": "system", "content": "You are a precise fact extraction module. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 150,
                "stream": False
            },
            timeout=10.0
        )
        if response.status_code != 200:
            return {"is_fact": False}

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return {"is_fact": False}
        return parsed
    except Exception:
        return {"is_fact": False}