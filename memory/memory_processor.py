from memory.rule_engine import extract_all_facts
from memory.memory_writer import add_fact, set_identity, set_gender
from utils.fact_validator import validate_fact
import os
from datetime import datetime

REJECTED_LOG = os.path.join(os.path.dirname(__file__), "..", "logs", "rejected_facts.log")

def log_rejected(user_input: str, candidate: dict):
    os.makedirs(os.path.dirname(REJECTED_LOG), exist_ok=True)
    timestamp = datetime.now().isoformat()
    with open(REJECTED_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] USER: {user_input}\n")
        f.write(f"  CANDIDATE: {candidate}\n\n")

def apply_memory_rules(user_input: str) -> bool:
    candidates = extract_all_facts(user_input)
    if not candidates:
        return False

    # Keep only the types that are definitely needed in the JSON
    # Оставляем только типы, которые точно нужны в JSON
    ALLOWED_TYPES = {'identity', 'gender', 'age', 'city'}
    changed = False

    for cand in candidates:
        cand_type = cand.get('type')
        if cand_type not in ALLOWED_TYPES:
            continue   

        if not cand.get("value"):
            continue

        if cand_type == 'identity':
            name = cand.get('value')
            if name:
                print(f"MEMORY (BASE): identity → {name}")
                set_identity(name)
                changed = True
            continue

        if cand_type == 'gender':
            gender = cand.get('value')
            if gender:
                print(f"MEMORY (BASE): gender → {gender}")
                set_gender(gender)
                changed = True
            continue

        validation = validate_fact(user_input, cand)
        if validation.get("is_fact"):
            fact = {
                "type": validation.get("type", cand_type),
                "value": validation.get("value", cand.get("value")),
                "status": validation.get("status", "stated"),
                "importance": validation.get("importance", 0.8)
            }
            print(f"MEMORY (VALIDATED): {fact['type']} → {fact['value']} [{fact['status']}]")
            add_fact(fact)
            changed = True
        else:
            print(f"MEMORY (REJECTED): {cand_type} → {cand.get('value')}")
            log_rejected(user_input, cand)

    return changed