# memory/rule_engine.py
import re
import os
import yaml
from typing import List, Dict, Optional

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

def load_facts_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("facts", {})

_facts_cfg = load_facts_config()
STOP_PHRASES = set(_facts_cfg.get("stop_phrases", ["что-то", "это", "ничего", "всё", "так", "просто"]))
MIN_FACT_LENGTH = _facts_cfg.get("min_length", 5)

def extract_all_facts(text: str) -> List[Dict]:
    """
    Extracts all known facts from the user's message
    Извлекает все известные факты из сообщения пользователя
    """
    facts = []
    text_lower = text.lower()

    # 1. Name / Имя
    name = extract_name(text_lower)
    if name:
        facts.append({"type": "identity", "value": name, "status": "stated"})

    # 2. Age / Возраст
    age = extract_age(text_lower)
    if age:
        facts.append({"type": "age", "value": age, "status": "stated"})

    # 3. Gender / Пол
    gender = extract_gender(text_lower)
    if gender:
        facts.append({"type": "gender", "value": gender, "status": "stated"})

    # 4. City / Город
    city = extract_city(text_lower)
    if city:
        facts.append({"type": "city", "value": city, "status": "stated"})

    # 5. Preferences (likes/enjoys) / Предпочтения (любит/нравится)
    prefs = extract_preferences(text_lower)
    for p in prefs:
        facts.append({"type": "preference", "value": p, "status": "likes"})

    # 6. Possessions / wants / past possessions / Владение / желание / прошлое обладание
    possessions = extract_possessions(text_lower)
    for item, status in possessions:
        facts.append({"type": "possession", "value": item, "status": status})

    # 7. Occupation / Профессия
    occ = extract_occupation(text_lower)
    if occ:
        facts.append({"type": "occupation", "value": occ, "status": "stated"})

    # 8. Hobby / Хобби
    hobby = extract_hobby(text_lower)
    if hobby:
        facts.append({"type": "hobby", "value": hobby, "status": "stated"})

    # 9. Pet / Питомец
    pet = extract_pet(text_lower)
    if pet:
        facts.append({"type": "pet", "value": pet, "status": "owns"})

    # 10. Relationships / Отношения
    rel = extract_relationship(text_lower)
    if rel:
        facts.append({"type": "relationship", "value": rel, "status": "stated"})

    # Wishes (want, dream, etc.) / НОВОЕ: Желания (хочу, мечтаю и т.д.)
    wishes = extract_wishes(text_lower)
    for w in wishes:
        facts.append({"type": "wish", "value": w, "status": "desired"})

    # Plans (planning, going to, etc.) / НОВОЕ: Планы (планирую, собираюсь и т.д.)
    plans = extract_plans(text_lower)
    for p in plans:
        facts.append({"type": "plan", "value": p, "status": "intended"})

    past_desires = extract_past_wishes_plans(text_lower)
    for item, type_ in past_desires:   # item — что именно, type_ — "wish" или "plan"
        facts.append({
            "type": "past_" + type_,   # past_wish или past_plan
            "value": item,
            "status": "unfulfilled"     # можно уточнять, если есть информация
        })

    return facts


# ------------- Auxiliary private functions -------------
# ---------- Вспомогательные приватные функции ----------
import re
from typing import Optional, List

def extract_name(text_lower: str) -> Optional[str]:
    patterns = [r"меня зовут (\w+)", r"моё имя (\w+)", r"my name is (\w+)"]
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            return m.group(1).capitalize()
    return None

def extract_age(text_lower: str) -> Optional[int]:
    # Added English support / Добавлена поддержка английского
    m = re.search(r"(?:мне|i am)\s+(\d{1,3})\s*(?:год|года|лет|years old|yo)?", text_lower)
    return int(m.group(1)) if m else None

def extract_gender(text_lower: str) -> Optional[str]:
    # Added English patterns / Добавлены английские паттерны
    if re.search(r"\b(я парень|я мужчина|я мальчик|i am a man|i am male|i am a boy)\b", text_lower):
        return "male"
    if re.search(r"\b(я девушка|я женщина|я девочка|i am a woman|i am female|i am a girl)\b", text_lower):
        return "female"
    return None

def extract_city(text_lower: str) -> Optional[str]:
    if not isinstance(text_lower, str):
        return None
    # Working with the text already converted to lowercase
    # Работаем с уже приведённым к нижнему регистру текстом
    patterns = [
        r"(?:я живу в|я из)\s+([а-яё][а-яё]+)",
        r"(?:i live in|i am from)\s+([a-z][a-z]+)"
    ]
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            return m.group(1).capitalize()
    return None

def extract_preferences(text_lower: str) -> List[str]:
    prefs = []
    patterns = [
        r"(?:я люблю|мне нравится|обожаю|предпочитаю)\s+(.+?)(?:[.,!?]|$| и | или )",
        r"(?:i love|i like|i prefer)\s+(.+?)(?:[.,!?]|$| and | or )"
    ]
    for p in patterns:
        for m in re.finditer(p, text_lower):
            pref = m.group(1).strip()
            pref = re.sub(r'[.!?,;]$', '', pref)
            if pref:
                prefs.append(pref.capitalize())
    return prefs

def extract_possessions(text_lower: str) -> List[tuple]:
    """Returns a list of tuples (item, status) / Возвращает список кортежей (предмет, статус)."""
    items = []
    
    # Ownership (owns) / Владение (owns)
    owns_pattern = r"(?:купил|приобрёл|заказал|есть у меня|у меня есть|bought|purchased|ordered|i have)\s+(.+?)(?:[.,!?]|$| и | или | and | or )"
    for m in re.finditer(owns_pattern, text_lower):
        item = m.group(1).strip()
        item = re.sub(r'[.!?,;]$', '', item)
        if item:
            items.append((item.capitalize(), "owns"))

    # Wants — kept for compatibility, but extract_wishes handles new ones
    # Желание (wants) — оставляем для совместимости, но новые желания ловит extract_wishes
    wants_pattern = r"(?:хочу купить|планирую купить|присматриваю|ищу|want to buy|planning to buy|looking for)\s+(.+?)(?:[.,!?]|$| и | или | and | or )"
    for m in re.finditer(wants_pattern, text_lower):
        item = m.group(1).strip()
        item = re.sub(r'[.!?,;]$', '', item)
        if item:
            items.append((item.capitalize(), "wants"))

    # Had / Было (had)
    had_pattern = r"(?:раньше был|был у меня|выбросил|продал|used to have|had a|threw away|sold)\s+(.+?)(?:[.,!?]|$| и | или | and | or )"
    for m in re.finditer(had_pattern, text_lower):
        item = m.group(1).strip()
        item = re.sub(r'[.!?,;]$', '', item)
        if item:
            items.append((item.capitalize(), "had"))
    return items

def extract_occupation(text_lower: str) -> Optional[str]:
    patterns = [
        r"я работаю (.+?)(?:[.,!?]|$| и | или )",
        r"я (инженер|программист|врач|учитель|дизайнер|менеджер|студент|фрилансер|безработный|пенсионер|домохозяйка)\b",
        r"i am an? (.+?)(?:[.,!?]|$| and | or )",
        r"my job is (.+?)(?:[.,!?]|$)"
    ]
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            occ = m.group(1).strip() if m.lastindex else m.group(0).strip()
            occ = re.sub(r'[.!?,;]$', '', occ)
            return occ.capitalize()
    return None

def extract_hobby(text_lower: str) -> Optional[str]:
    patterns = [
        r"(?:моё хобби|увлекаюсь|занимаюсь|my hobby is|i am into|i do)\s+(.+?)(?:[.,!?]|$| и | или | and | or )",
        r"(?:я играю на|i play (?:the )?)\s*(\w+)",
        r"(?:я коллекционирую|я собираю|i collect)\s+(.+?)(?:[.,!?]|$| и | or )"
    ]
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            hobby = m.group(1).strip()
            hobby = re.sub(r'[.!?,;]$', '', hobby)
            return hobby.capitalize()
    return None

def extract_pet(text_lower: str) -> Optional[str]:
    patterns = [
        r"у меня (?:есть|жив[её]т)\s+(.+?)(?:[.,!?]|$| по имени | и )",
        r"i have a pet (.+?)(?:[.,!?]|$| named )"
    ]
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            pet = m.group(1).strip()
            pet = re.sub(r'[.!?,;]$', '', pet)
            return pet.capitalize()
    return None

def extract_relationship(text_lower: str) -> Optional[str]:
    patterns = [
        r"я (женат|замужем|в отношениях|свободен|одинок|встречаюсь с .+)",
        r"i am (married|single|in a relationship|divorced)"
    ]
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            return m.group(0).capitalize()
    return None

# ---------- NEW FUNCTIONS FOR WISHES AND PLANS ----------
# ---------- НОВЫЕ ФУНКЦИИ ДЛЯ ЖЕЛАНИЙ И ПЛАНОВ ----------
def _get_sentence_containing(text_lower: str, match_start: int, match_end: int) -> str:
    """
    Returns the full sentence containing the match from match_start to match_end.
    Возвращает полное предложение, содержащее совпадение от match_start до match_end.
    """
    # Find sentence start / Находим начало предложения
    sentence_start = 0
    for i in range(match_start - 1, -1, -1):
        if text_lower[i] in '.!?':
            sentence_start = i + 1
            break
    
    # Find sentence end / Находим конец предложения
    sentence_end = len(text_lower)
    for i in range(match_end, len(text_lower)):
        if text_lower[i] in '.!?':
            sentence_end = i + 1
            break
    
    return text_lower[sentence_start:sentence_end]


def _has_negation_in_sentence(text_lower: str, match_start: int, match_end: int, target_verbs: str) -> bool:
    """
    Checks if there is a negation ("не" or "not") in the same sentence before the verb.
    Проверяет, есть ли отрицание "не" (или "not") в том же предложении перед глаголом.
    target_verbs — string with verb variants separated by | for regex.
    target_verbs — строка с вариантами глаголов через | для regex.
    """
    sentence = _get_sentence_containing(text_lower, match_start, match_end)
    # Look for "не" / "not" followed by words ending with one of the verbs
    # Ищем "не" / "not" с последующими словами, заканчивающимися одним из глаголов
    pattern = r'\b(?:не|not|don\'t|doesn\'t|didn\'t)\b[\w\s]*?' + target_verbs + r'\b'
    return bool(re.search(pattern, sentence, re.IGNORECASE))


def extract_wishes(text_lower: str) -> List[str]:
    """
    Extracts user wishes (not directly related to purchases).
    Извлекает желания пользователя (не связанные напрямую с покупкой).
    Examples: 'хочу научиться играть на гитаре', 'я хочу кофе', 'мечтаю о путешествии', 'i want to learn guitar'
    """
    wishes = []
    # Verbs / phrases expressing desire
    # Глаголы / обороты, выражающие желание
    patterns = [
        # Optional word (pronoun) before the verb / Опциональное слово (местоимение) перед глаголом
        r"(?:\w+\s+)?(?:хочу|желаю|мечтаю|хотел бы|не прочь|стремлюсь|want to|wish to|dream of|would like to|i want|i wish|i dream)\s+(.+?)(?:[.,!?]|$| и | или |, а также| and | or )",
        r"(?:было бы здорово|было бы неплохо|it would be great|it would be nice)\s+(.+?)(?:[.,!?]|$| и | или | and | or)",
        r"(?:мечта о|dream of|dream about) (.+?)(?:[.,!?]|$)"
    ]
    for pat in patterns:
        for m in re.finditer(pat, text_lower):
            # Check for negation in the same sentence before the verb
            # Проверяем, нет ли отрицания в том же предложении перед глаголом
            if _has_negation_in_sentence(text_lower, m.start(), m.end(), r'хочу|желаю|мечтаю|хотел бы|стремлюсь|want|wish|dream|like'):
                continue
            wish = m.group(1).strip()
            wish = re.sub(r'[.!?,;]$', '', wish)
            if wish and len(wish) > 2:
                wishes.append(wish.capitalize())
    # Remove duplicates / Убираем дубликаты
    unique = []
    for w in wishes:
        if w not in unique:
            unique.append(w)
    filtered = []
    for item in unique:
        val = item if isinstance(item, str) else item[0]
        if len(val) < MIN_FACT_LENGTH or val.lower() in STOP_PHRASES:
            continue
        filtered.append(item)
    return filtered

def extract_plans(text_lower: str) -> List[str]:
    """
    Extracts user plans and intentions.
    Извлекает планы и намерения пользователя.
    Examples / Примеры: 'планирую сменить работу', 'я собираюсь в спортзал', 
    'он решил начать бегать', 'i plan to change my job', 'i am going to the gym'
    """
    plans = []
    patterns = [
        # Added English patterns and conjunctions / Добавлены английские паттерны и союзы
        r"(?:\w+\s+)?(?:планирую|собираюсь|намереваюсь|задумал|решил|plan to|planning to|going to|intend to|decided to|i plan|i intend)\s+(.+?)(?:[.,!?]|$| и | или |, а также| and | or )",
        r"(?:в планах|in my plans to)\s+(.+?)(?:[.,!?]|$)"
    ]
    for pat in patterns:
        for m in re.finditer(pat, text_lower):
            # Check for negation in the same sentence
            # Проверка на отрицание в том же предложении
            if _has_negation_in_sentence(text_lower, m.start(), m.end(), r'планирую|собираюсь|намереваюсь|задумал|решил|plan|intend|decide'):
                continue
            plan = m.group(1).strip()
            plan = re.sub(r'[.!?,;]$', '', plan)
            if plan and len(plan) > 2:
                plans.append(plan.capitalize())
    
    # Remove duplicates / Удаляем дубликаты
    unique = []
    for p in plans:
        if p not in unique:
            unique.append(p)
            
    filtered = []
    for item in unique:
        val = item if isinstance(item, str) else item[0]
        if len(val) < MIN_FACT_LENGTH or val.lower() in STOP_PHRASES:
            continue
        filtered.append(item)
    return filtered


def extract_past_wishes_plans(text_lower: str) -> List[tuple]:
    """
    Extracts past wishes and plans that are likely unrealized.
    Извлекает прошлые желания и планы, которые, вероятно, не реализованы.
    Returns a list of tuples (wish/plan, type: 'wish' or 'plan').
    Возвращает список кортежей (желание/план, тип: 'wish' или 'plan').
    Examples / Примеры:
        "я хотел купить машину" -> ("Купить машину", 'wish')
        "он планировал переехать" -> ("Переехать", 'plan')
        "i wanted to buy a car" -> ("Buy a car", 'wish')
    """
    results = []

    wish_patterns = [
        # Optional past markers + optional word + past wish verb
        # Опциональные маркеры прошлого + опциональное слово + глагол прош. времени
        r"(?:раньше|когда-то|в прошлом|в детстве|до этого|прежде|ранее|previously|before|in the past|as a child)?\s*(?:\w+\s+)?(?:хотел|хотела|хотело|хотели|мечтал|мечтала|мечтали|желал|желала|стремился|стремилась|wanted|wished|dreamt|dreamed|desired|strove)\s+(.+?)(?:[.,!?]|$| и | или |, но|, однако| and | or |, but|, however)",
        r"(?:было желание|i had a wish to)\s+(.+?)(?:[.,!?]|$|, но|, but)",
        r"(?:раньше|когда-то|в детстве|previously|before|as a child).{0,15}(?:мечта о|dream of|dream about)\s+(.+?)(?:[.,!?]|$)"
    ]

    plan_patterns = [
        r"(?:раньше|когда-то|в прошлом|до этого|прежде|ранее|previously|before|in the past)?\s*(?:\w+\s+)?(?:планировал|планировала|собирался|собиралась|намеревался|намеревалась|задумывал|задумывала|planned|intended|was going to|were going to|decided to)\s+(.+?)(?:[.,!?]|$| и | или |, но| and | or |, but)",
        r"(?:в планах было|in my past plans to)\s+(.+?)(?:[.,!?]|$)"
    ]

    def extract_items(patterns, type_name):
        items = []
        for pat in patterns:
            for m in re.finditer(pat, text_lower):
                # Check for negation in the same sentence
                # Проверяем отрицание в том же предложении
                if type_name == 'wish':
                    neg_pattern = r'хотел|хотела|хотело|хотели|мечтал|мечтала|мечтали|желал|желала|стремился|стремилась|wanted|wished|dreamt|dreamed|desired|strove'
                else:
                    neg_pattern = r'планировал|планировала|собирался|собиралась|намеревался|намеревалась|задумывал|задумывала|planned|intended|was going to|were going to|decided to'
                
                if _has_negation_in_sentence(text_lower, m.start(), m.end(), neg_pattern):
                    continue
                
                item = m.group(1).strip()
                item = re.sub(r'[.!?,;]$', '', item)
                
                if item and len(item) > 2 and not item.isspace():
                    # Remove leading conjunctions / Убираем ведущие союзы
                    item = re.sub(r'^(что|чтобы|that|to)\s+', '', item)
                    items.append((item.capitalize(), type_name))
        return items

    results.extend(extract_items(wish_patterns, 'wish'))
    results.extend(extract_items(plan_patterns, 'plan'))

    # Remove duplicates / Удаляем дубликаты
    unique = []
    for val, typ in results:
        if (val, typ) not in unique:
            unique.append((val, typ))
            
    filtered = []
    for item in unique:
        val = item if isinstance(item, str) else item[0]
        if len(val) < MIN_FACT_LENGTH or val.lower() in STOP_PHRASES:
            continue
        filtered.append(item)
    return filtered


