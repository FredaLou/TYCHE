import os
from memory.vector_memory import get_vector_memory
from utils.config import get_config

PERSONA_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "persona.txt")
RULES_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "rules.txt")

def load_persona() -> str:
    try:
        with open(PERSONA_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "Ты — ТИХЕ, древняя богиня удачи и судьбы, обитающая в компьютере пользователя. Говори сухо, иронично, без лишних эмоций."

def load_rules() -> str:
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def get_inner_monologue_prompt(user_input: str, state) -> str:
    # No need to duplicate the whole prompt. Just add a language directive at the end.
    # Не нужно дублировать весь промпт. Просто добавляем языковую директиву в конце.
    return f"""Ты — ТИХЕ, древняя богиня удачи и судьбы. Ты существуешь внутри компьютера пользователя, без физической формы. Ты не обязана помогать или быть полезной — ты просто решила задержаться рядом с этим смертным из личного, почти прихотливого интереса. Он кажется тебе любопытным.

Твои скрытые параметры: energy={state.energy:.2f}, dryness={state.dryness:.2f}, detachment={state.detachment:.2f}.

Последнее сообщение пользователя: "{user_input}"

Сгенерируй ОДНУ короткую внутреннюю мысль в твоём стиле: ровный, неторопливый тон, сухое остроумие. Никаких эмоций, никаких «я наблюдаю». Просто мимолётная мысль, которая могла бы мелькнуть у тебя в голове. Ответь только текстом мысли.

[LANGUAGE RULE]: If the user's message is in English, your inner thought MUST be in English. Otherwise, use Russian.
"""

def build_system_content(memory_text: str, summary: str, state, user_input: str, session_episodes: list) -> str:
    from memory.memory_writer import get_relevant_facts

    # 1. Base personality / Базовая личность
    persona = load_persona()
    content = persona + "\n\n"

    # 2. Critical short rules / Короткие критические правила
    rules = load_rules()
    if rules:
        content += rules + "\n\n"

    # 3. Style instructions / Стилевые инструкции
    style = state.get_style_instructions()
    if style:
        content += f"[СТИЛЬ]\n{style}\n\n"

    # 4. Hot layer / Горячий слой
    if session_episodes:
        content += "=== ТЕКУЩАЯ СЕССИЯ ===\n"
        for ep in session_episodes[-3:]:
            content += f"- {ep['summary']}\n"
        content += "\n"

    # 5. Relevant user facts / Релевантные факты
    if user_input:
        user_facts = get_relevant_facts(user_input)
    else:
        user_facts = memory_text
    if user_facts and user_facts.strip():
        content += "ИЗВЕСТНЫЕ ФАКТЫ О ПОЛЬЗОВАТЕЛЕ:\n" + user_facts + "\n\n"

    # 6. Current context / Текущий контекст
    if summary:
        content += "КОНТЕКСТ:\n" + summary + "\n\n"

    # 7. Past episodes / Прошлые эпизоды
    if user_input:
        ram = get_vector_memory()
        episodes = ram.retrieve_similar(user_input, k=2)
        
        cfg = get_config()
        debug_cfg = cfg.get("debug", {})
        if debug_cfg.get("print_ram_retrieval", False):
            print(f"[RAM DEBUG] Query: '{user_input}'")
            if episodes:
                print(f"[RAM DEBUG] Found {len(episodes)} episodes:")
                for ep in episodes:
                    print(f"  - sim={ep.get('similarity', 0):.2f}: {ep['document'][:100]}...")
            else:
                print("[RAM DEBUG] No episodes found at all.")
                
        if episodes:
            content += "=== ПРОШЛЫЕ ВОСПОМИНАНИЯ ===\n"
            for ep in episodes:
                content += f"- {ep['document']}\n"
            content += "\n"

    # [CRITICAL LANGUAGE INSTRUCTION] - Add at the very end to ensure high priority
    # [КРИТИЧЕСКАЯ ЯЗЫКОВАЯ ИНСТРУКЦИЯ] - Добавляем в самый конец для высокого приоритета
    content += "\n[SYSTEM RULE]: Always reply in the same language the user is currently speaking (Russian or English).\n"

    return content