import json
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer
import numpy as np

# Lazy loading of the model (to avoid loading it on every call)
# Ленивая загрузка модели (чтобы не грузить при каждом вызове)
_embedder = None

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "identity": {"name": None, "gender": None},  # добавили gender
            "preferences": [],
            "facts": []
        }

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def set_gender(gender: str):
    if gender not in ("male", "female", "other"):
        return
    data = load_memory()
    data["identity"]["gender"] = gender
    save_memory(data)

def norm(x: str) -> str:
    return x.strip().lower()

def load_memory_text() -> str:
    data = load_memory()
    lines = []
    name = data["identity"].get("name")
    gender = data["identity"].get("gender")
    if name:
        pronoun = " (он)" if gender == "male" else " (она)" if gender == "female" else ""
        lines.append(f"Имя: {name}{pronoun}")
    # Оставляем только age и city из facts
    for fact in data.get("facts", []):
        if fact.get("type") in ("age", "city"):
            lines.append(f"{fact['type']}: {fact['value']}")
    return "\n".join(lines) if lines else "(пусто)"

def set_identity(name: str):
    if not name:
        return
    data = load_memory()
    current = data["identity"].get("name")
    if current != name:
        data["identity"]["name"] = name
        save_memory(data)

def add_preference(pref: str):
    if not pref:
        return
    data = load_memory()
    prefs_norm = {norm(p): p for p in data["preferences"]}
    if norm(pref) not in prefs_norm:
        data["preferences"].append(pref)
        save_memory(data)

def add_fact(fact: dict):
    if not fact.get("value"):
        return
    data = load_memory()
    value = fact["value"]
    value_str = str(value)
    norm_value = norm(value_str)
    fact_type = fact.get("type", "general")
    status = fact.get("status", "stated")
    importance = fact.get("importance", 0.5)
    now = datetime.now().isoformat()

    existing = None
    for f in data["facts"]:
        if f.get("type") == fact_type and norm(str(f["value"])) == norm_value:
            existing = f
            break

    if existing:
        old_status = existing.get("status")
        old_importance = existing.get("importance")
        existing["status"] = status
        existing["last_updated"] = now
        if importance != old_importance:
            existing["importance"] = importance
        print(f"  ↳ Updated existing fact: {fact_type} ({old_status} → {status})")
    else:
        new_fact = {
            "type": fact_type,
            "value": value,
            "status": status,
            "importance": importance,
            "last_updated": now
        }
        data["facts"].append(new_fact)
        print(f"  ↳ Added new fact: {fact_type}")

    save_memory(data)


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _embedder


def get_relevant_facts(user_input: str) -> str:
    # We no longer perform semantic selection—there are few facts, and all of them are important.
    # Больше не делаем семантический отбор – фактов мало, все важны
    return load_memory_text()