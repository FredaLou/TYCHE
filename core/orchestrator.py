# core/orchestrator.py
import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any

class Orchestrator:
    def __init__(self, config: Dict[str, Any], ram, state):
        self.config = config
        self.ram = ram
        self.state = state
        self.url_main = config["model"]["main_url"]
        self.url_fast = config["model"]["fast_url"]
        self.conversation_summary = ""
        self.session_episodes = []
        self.episode_messages = []
        self.episode_start_time = datetime.now().isoformat()
        self.message_counter = 0
        self.last_assistant_reply = ""
        self._finalized = False


    def process_message(self, user_input: str, messages_history: List[Dict]) -> tuple[str, List[Dict]]:
        # 1. Updating state with consideration for context / Обновление состояния с учётом контекста
        self.state.decay()
        self.state.update_from_user_message(user_input, 0.0, self.last_assistant_reply)
        if self.config["debug"]["print_state"]:
            print(f"[STATE] energy={self.state.energy:.2f} dryness={self.state.dryness:.2f} detachment={self.state.detachment:.2f}")

        # 2. Processing of facts / Обработка фактов (JSON/SQLite)
        from memory.memory_processor import apply_memory_rules
        memory_changed = apply_memory_rules(user_input)
        if memory_changed and self.config["debug"]["print_memory_changes"]:
            print("DEBUG: memory changed!")
        from memory.memory_writer import load_memory_text
        mem_text = load_memory_text()

        # 3. Constructing the system prompt/ Сборка системного промпта
        system_content = self._build_system_prompt(user_input, mem_text)
        
        # 4. Updating history / Обновление истории
        messages = self._update_history(messages_history, system_content, user_input)

        # 5. Inner_monologue (if needs) / Внутренний монолог (опционально)"""

        if self.config["inner_monologue"]["enabled"]:
            thought = self._generate_inner_thought(user_input)
            if thought:
                messages[0]["content"] += f"\n[Internal thought: {thought}]\n"

        response_text = self._call_main_model(messages)
        self.last_assistant_reply = response_text   # <-- сохраняем для следующего хода

        self._update_episodes(user_input, response_text, messages)

        messages.append({"role": "assistant", "content": response_text})

        messages = self._trim_history(messages)

        return response_text, messages

    def _build_system_prompt(self, user_input: str, mem_text: str) -> str:
        """
        Assembles a system prompt based on the configuration and state
        Собирает системный промпт на основе конфига и состояния
        """
        from utils.system_prompt import build_system_content
        return build_system_content(
            mem_text,
            self.conversation_summary,
            self.state,
            user_input,
            self.session_episodes
        )

    def _update_history(self, messages: List[Dict], system_content: str, user_input: str) -> List[Dict]:
        """
        Updates the list of messages: inserts the system prompt and the user message.
        Обновляет список сообщений: вставляет системный промпт и сообщение пользователя.
        """
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": system_content})
        else:
            messages[0]["content"] = system_content
        messages.append({"role": "user", "content": user_input})
        self.episode_messages.append({"role": "user", "content": user_input})
        self.message_counter += 1
        return messages

    def _call_main_model(self, messages: List[Dict]) -> str:
        """
        Sends a request to the main model and returns the response.
        Отправляет запрос к основной модели и возвращает ответ.
        """
        full_text = ""
        try:
            response = requests.post(
                self.url_main,
                json={
                    "messages": messages,
                    "temperature": self.config["model"]["temperature"],
                    "top_p": self.config["model"]["top_p"],
                    "stream": self.config["model"]["stream"],
                    "frequency_penalty": self.config["model"]["frequency_penalty"],
                    "presence_penalty": self.config["model"]["presence_penalty"],
                    "stop": self.config["model"]["stop"],
                },
                stream=self.config["model"]["stream"],
                timeout=self.config["model"]["timeout"],
            )
            if self.config["model"]["stream"]:
                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line.replace("data: ", "")
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            print(delta, end="", flush=True)
                            full_text += delta
                    except:
                        continue
            else:
                result = response.json()
                full_text = result["choices"][0]["message"]["content"]
                print(full_text)
        except Exception as e:
            print(f"\n[ERROR] {e}")
            full_text = "(no response due to error)"
        return full_text

    def _generate_inner_thought(self, user_input: str) -> Optional[str]:
        """
        Generates an internal thought via a fast model.
        Генерирует внутреннюю мысль через быструю модель.
        """
        prompt = self.config["inner_monologue"]["prompt"].format(
            energy=self.state.energy,
            dryness=self.state.dryness,
            detachment=self.state.detachment,
            user_input=user_input
        )
        try:
            response = requests.post(
                self.url_fast,
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 50,
                    "stream": False
                },
                timeout=5.0
            )
            if response.status_code == 200:
                thought = response.json()["choices"][0]["message"]["content"].strip()
                print(f"[INNER] {thought}")
                return thought
        except:
            pass
        return None

    def _update_episodes(self, user_input: str, response_text: str, messages: List[Dict]):
            """
            Updates the episode buffer and, if necessary, generates a summary.
            Обновляет буфер эпизодов и при необходимости генерирует суммаризацию.
            """
            self.episode_messages.append({"role": "assistant", "content": response_text})
        
            episode_interval = self.config["memory"]["episode_interval"]
            should_summarize = self.message_counter % episode_interval == 0 and len(messages) > 10
        
            if should_summarize:
                from utils.summarizer import generate_summary, generate_episode_summary
                print("\n[Generating conversation summary...]")
                new_summary = generate_summary(messages)
                if new_summary:
                    self.conversation_summary = new_summary
                    print(f"[Summary updated: {self.conversation_summary[:80]}...]")

                # Суммаризация и сохранение эпизода
                if self.episode_messages:
                    episode_end_time = datetime.now().isoformat()
                    episode_data = generate_episode_summary(
                        self.episode_messages,
                        self.episode_start_time,
                        episode_end_time
                    )
                    if episode_data:
                        episode = {
                            "summary": episode_data["summary"],
                            "start_time": episode_data["start_time"],
                            "end_time": episode_data["end_time"],
                            "message_count": episode_data["message_count"]
                        }
                        self.session_episodes.append(episode)
                        print(f"[RAM] Episode added to hot layer. Total in session: {len(self.session_episodes)}")

                        if len(self.session_episodes) >= self.config["memory"]["max_session_episodes"]:
                            for ep in self.session_episodes:
                                self.ram.add_episode(ep["summary"], ep["start_time"], ep["end_time"], ep["message_count"])
                            self.session_episodes.clear()
                            print("[RAM] Hot episodes flushed to warm storage.")
                
                    # Clearing the episode buffer / Сбрасываем буфер эпизода
                    self.episode_start_time = episode_end_time
                    self.episode_messages = []
            else:
                # Overflow protection: if the buffer grows too large, we flush it without summarization.
                # Защита от переполнения: если буфер вырос слишком сильно, сбрасываем без суммаризации
                max_buffer = self.config["memory"].get("max_episode_buffer", 50)
                if len(self.episode_messages) > max_buffer:
                    print(f"[EPISODE] Buffer exceeded {max_buffer} messages, clearing without summary.")
                    self.episode_start_time = datetime.now().isoformat()
                    self.episode_messages = []

    def _trim_history(self, messages: List[Dict]) -> List[Dict]:
        """
        Truncates the history to max_history_messages.
        Обрезает историю до max_history_messages.
        """
        max_hist = self.config["memory"]["max_history_messages"]
        if len(messages) - 1 > max_hist:
            system_msg = messages[0]
            messages = [system_msg] + messages[-(max_hist):]
        return messages

    def finalize_session(self):
        """
        Preserves remaining episodes when the session ends.
        Сохраняет оставшиеся эпизоды при завершении сессии.
        """
        if self._finalized:
            return
        self._finalized = True


        if self.session_episodes:
            print("[RAM] Saving remaining session episodes to warm storage...")
            for ep in self.session_episodes:
                self.ram.add_episode(ep["summary"], ep["start_time"], ep["end_time"], ep["message_count"])
            self.session_episodes.clear()





