# utils/summarizer.py
import os
import yaml
import requests
import json
from typing import Optional

# Load configuration file path
# Загружаем путь к файлу конфигурации
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
FAST_URL = config["model"]["fast_url"]
MAIN_URL = config["model"]["main_url"]
SUMMARIZATION_CFG = config.get("summarization", {})

def generate_episode_summary(messages, start_time: str, end_time: str) -> Optional[dict]:
    """
    Generates a short summary of a conversation episode using the main model.
    Генерирует краткую сводку эпизода диалога с помощью основной модели.
    """
    dialog_text = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            dialog_text += f"User: {content}\n"
        elif role == "assistant":
            dialog_text += f"Assistant: {content}\n"

    prompt_template = SUMMARIZATION_CFG.get("episode_prompt", "")
    prompt = prompt_template.format(dialog_text=dialog_text)

    # Debug setting (loaded from global config, no need to reload file)
    # Настройка отладки (загружается из глобального конфига, нет нужды перечитывать файл)
    debug_episode = config.get("debug", {}).get("print_episode_summary", False)

    try:
        response = requests.post(
            MAIN_URL,
            json={
                "messages": [
                    # Updated prompt to be language-agnostic
                    # Обновленный промпт, не привязанный к конкретному языку
                    {"role": "system", "content": "You are a concise summarizer. Reply with the summary in the same language as the dialogue."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": config["model"].get("fast_max_tokens", 200),
                "stream": False
            },
            timeout=config["model"].get("timeout", 30)
        )
        if response.status_code != 200:
            if debug_episode:
                print(f"[Episode summarizer] HTTP {response.status_code}: {response.text}")
            return None

        result = response.json()
        summary = result["choices"][0]["message"]["content"].strip()
        
        # Validation: check if it's a roleplay response or a prompt
        # Проверка: является ли это ролевым ответом или промптом
        # Added English invalid patterns / Добавлены английские паттерны мусора
        invalid_patterns = [
            "Привет", "Тиха", "программа", "Проанализируй", "составь", "резюме",
            "Hello", "Tyche", "program", "Analyze", "make", "summary"
        ]
        if not summary or len(summary) < 30 or any(p in summary for p in invalid_patterns):
            if debug_episode:
                print(f"[Episode summarizer] Rejected invalid summary: {summary[:100]}")
            return None
        
        if debug_episode:
            print(f"[Episode summarizer] Generated summary: {summary[:200]}...")

        return {
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "message_count": len(messages)
        }
    except Exception as e:
        if debug_episode:
            print(f"[Episode summarizer error] {e}")
        return None

def generate_summary(messages, max_length=200):
    """
    Generates a general summary of the conversation for the context window.
    Генерирует общую сводку диалога для контекстного окна.
    """
    dialog_text = ""
    # Skip the system prompt (messages[0])
    # Пропускаем системный промпт (messages[0])
    for msg in messages[1:]:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            dialog_text += f"User: {content}\n"
        elif role == "assistant":
            dialog_text += f"Assistant: {content}\n"

    prompt_template = SUMMARIZATION_CFG.get("conversation_prompt", "")
    prompt = prompt_template.format(dialog_text=dialog_text)

    try:
        response = requests.post(
            MAIN_URL,
            json={
                "messages": [
                    {"role": "system", "content": "You are a helpful summarizer. Be concise."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": max_length,
                "stream": False
            },
            timeout=config["model"].get("timeout", 30)
        )
        result = response.json()
        summary = result["choices"][0]["message"]["content"].strip()
        return summary
    except Exception as e:
        print(f"[Summarizer error] {e}")
        return ""