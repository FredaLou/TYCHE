import random
import time as time_module
import os
import yaml
import requests
from datetime import datetime, time

# Load configuration file path
# Загружаем путь к файлу конфигурации
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

def load_state_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("state", {})

class TycheState:
    """
    Manages Tyche's internal emotional and physical state.
    Управляет внутренним эмоциональным и физическим состоянием Ти́хи.
    """
    def __init__(self):
        cfg = load_state_config()
        
        # Energy / Энергия
        energy_cfg = cfg.get("energy", {})
        self.energy = energy_cfg.get("initial", 0.7)
        self.energy_min = energy_cfg.get("min", 0.2)
        self.energy_max = energy_cfg.get("max", 1.0)
        self.energy_decay = energy_cfg.get("decay_rate", 0.05)
        
        # Dryness (wit/sarcasm) / Остроумие (сухость)
        dryness_cfg = cfg.get("dryness", {})
        self.dryness = dryness_cfg.get("initial", 0.5)
        self.dryness_min = dryness_cfg.get("min", 0.1)
        self.dryness_max = dryness_cfg.get("max", 1.0)
        self.dryness_decay = dryness_cfg.get("decay_rate", 0.03)
        
        # Detachment / Отстранённость
        detachment_cfg = cfg.get("detachment", {})
        self.detachment = detachment_cfg.get("initial", 0.6)
        self.detachment_min = detachment_cfg.get("min", 0.3)
        self.detachment_max = detachment_cfg.get("max", 1.0)
        self.detachment_decay = detachment_cfg.get("decay_rate", 0.03)
        
        # Affection / Привязанность
        affection_cfg = cfg.get("affection", {})
        self.affection = affection_cfg.get("initial", 0.5)
        self.affection_min = affection_cfg.get("min", 0.1)
        self.affection_max = affection_cfg.get("max", 1.0)
        self.affection_decay = affection_cfg.get("decay_rate", 0.01)
        
        # Daily rhythm phases / Фазы суточного ритма
        self.phases = cfg.get("phases", [])
        
        # Spontaneous whims / Спонтанные всплески
        self.whim_chance = cfg.get("spontaneous_whim_chance", 0.05)
        self.whim_boost_min = cfg.get("whim_boost_min", 0.1)
        self.whim_boost_max = cfg.get("whim_boost_max", 0.2)
        
        # Sentiment analysis settings (loaded once)
        # Настройки тональности (загружаем один раз)
        self.sentiment_cfg = cfg.get("sentiment", {})
        
        self.last_update = time_module.time()
        self.last_decay_check = time_module.time()

    # ------------------------------------------------------------
    # DAILY RHYTHM (phases from config)
    # СУТОЧНЫЙ РИТМ (фазы из конфига)
    # ------------------------------------------------------------
    def _time_based_modifiers(self):
        now = datetime.now()
        t = now.time()
        
        def minutes(tm: time) -> int:
            return tm.hour * 60 + tm.minute
        
        m = minutes(t)
        target_energy = None
        target_dryness = None
        target_detachment = None
        
        for phase in self.phases:
            start = phase.get("start", 0)
            end = phase.get("end", 0)
            # Handle midnight crossover (e.g., start=23:00, end=05:00)
            # Обработка перехода через полночь (например, начало=23:00, конец=05:00)
            if start <= end:
                in_phase = (start <= m < end)
            else:
                in_phase = (m >= start or m < end)
            if in_phase:
                target_energy = phase.get("energy_target", 0.5)
                target_dryness = phase.get("dryness_target", 0.5)
                target_detachment = phase.get("detachment_target", 0.5)
                break
        
        if target_energy is not None:
            # Smoothly interpolate towards the target value
            # Плавно интерполируем к целевому значению
            self.energy += (target_energy - self.energy) * 0.1
            self.dryness += (target_dryness - self.dryness) * 0.1
            self.detachment += (target_detachment - self.detachment) * 0.1

    # ------------------------------------------------------------
    # PARAMETER DECAY
    # ЗАТУХАНИЕ ПАРАМЕТРОВ
    # ------------------------------------------------------------
    def decay(self):
        now = time_module.time()
        
        # Apply daily modifiers no more than once per 60 seconds
        # Применяем суточные модификаторы не чаще одного раза в 60 секунд
        if now - self.last_decay_check >= 60:
            self._time_based_modifiers()
            self.last_decay_check = now
        
        # Decay parameters based on actual time since last full cycle
        # Затухание параметров по фактическому времени с последнего полного цикла
        elapsed = now - self.last_update
        decay_factor = min(elapsed / 60.0, 1.0) * 0.05
        
        self.energy = max(self.energy_min, self.energy - decay_factor * self.energy_decay)
        # Dryness and detachment revert to neutral (0.5) over time
        # Остроумие и отстраненность со временем возвращаются к нейтральному (0.5)
        self.dryness = self.dryness * (1 - decay_factor) + 0.5 * decay_factor
        self.detachment = self.detachment * (1 - decay_factor) + 0.5 * decay_factor
        
        # Affection decays very slowly, only if more than a day has passed
        # Привязанность затухает очень медленно и только если прошел день
        if elapsed > 86400:
            self.affection = max(self.affection_min, self.affection - self.affection_decay)
        
        self.last_update = now

    # ------------------------------------------------------------
    # UPDATE FROM USER MESSAGE
    # ОБНОВЛЕНИЕ ОТ СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ
    # ------------------------------------------------------------
    def update_from_user_message(self, text: str, similarity_to_prev: float = 0.0, assistant_reply: str = ""):
        text_lower = text.lower()
        
        # Energy changes based on message length
        # Энергия меняется в зависимости от длины сообщения
        if len(text) > 200:
            self.energy = max(self.energy_min, self.energy - 0.02)
        else:
            self.energy = min(self.energy_max, self.energy + 0.01)
        
        # Detachment changes based on repetition
        # Отстранённость меняется в зависимости от повторов
        if similarity_to_prev > 0.8:
            self.detachment = min(self.detachment_max, self.detachment + 0.05)
        else:
            self.detachment = max(self.detachment_min, self.detachment - 0.02)
        
        # Questions slightly reduce detachment
        # Вопросы немного снижают отстранённость
        if '?' in text:
            self.detachment = max(self.detachment_min, self.detachment - 0.02)
        
        # Sentiment analysis (with context)
        # Анализ тональности (с учётом контекста)
        use_llm = self.sentiment_cfg.get("use_llm", False)
        
        if use_llm:
            sentiment = self._analyze_sentiment_with_llm(text, assistant_reply)
        else:
            sentiment = self._analyze_sentiment_with_keywords(text, assistant_reply, self.sentiment_cfg)
        
        if sentiment == "positive":
            boost = self.sentiment_cfg.get("positive_affection_boost", 0.02)
            self.affection = min(self.affection_max, self.affection + boost)
        elif sentiment == "negative":
            penalty = self.sentiment_cfg.get("negative_affection_penalty", 0.05)
            detachment_boost = self.sentiment_cfg.get("negative_detachment_boost", 0.1)
            self.affection = max(self.affection_min, self.affection - penalty)
            self.detachment = min(self.detachment_max, self.detachment + detachment_boost)
        
        # Slow growth of affection from just chatting
        # Медленный рост привязанности от простого общения
        self.affection = min(self.affection_max, self.affection + 0.005)

    # ------------------------------------------------------------
    # HELPER METHODS FOR SENTIMENT ANALYSIS
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ АНАЛИЗА ТОНАЛЬНОСТИ
    # ------------------------------------------------------------
    def _analyze_sentiment_with_keywords(self, text: str, assistant_reply: str, cfg: dict) -> str:
        text_lower = text.lower()
        positive_words = cfg.get("positive_keywords", [])
        negative_words = cfg.get("negative_keywords", [])
        
        # Check for references to Tyche or an explicit reaction to her last reply
        # Есть ли обращение к Тихе или явная реакция на её последнюю реплику?
        # Added English references / Добавлены английские обращения
        references_tyche = any(w in text_lower for w in ["тиха", "тихе", "тиху", "ты", "твои", "твоя", "твоё", "tyche", "you", "your", "u"])
        is_short_response = len(text) < 50 and assistant_reply != ""
        is_response_to_tyche = references_tyche or is_short_response
        
        has_positive = any(w in text_lower for w in positive_words)
        has_negative = any(w in text_lower for w in negative_words)
        
        if is_response_to_tyche:
            if has_positive and not has_negative:
                return "positive"
            if has_negative and not has_positive:
                return "negative"
        return "neutral"

    def _analyze_sentiment_with_llm(self, text: str, assistant_reply: str) -> str:
        # Note: URL is hardcoded here. In the future, consider moving it to config.
        # Примечание: URL захардкожен. В будущем стоит вынести его в конфиг.
        prompt = f"""Определи тональность сообщения пользователя по отношению к ассистенту Тихе.
Сообщение: "{text}"
Последний ответ Тихе: "{assistant_reply}"
Ответь одним словом: positive, negative или neutral."""
        try:
            response = requests.post(
                "http://127.0.0.1:8001/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 10,
                    "stream": False
                },
                timeout=3.0
            )
            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"].strip().lower()
                if result in ("positive", "negative", "neutral"):
                    return result
        except:
            pass
        return "neutral"

    # ------------------------------------------------------------
    # SPONTANEOUS WHIM (WIT BURST)
    # СПОНТАННЫЙ ВСПЛЕСК ОСТРОУМИЯ
    # ------------------------------------------------------------
    def spontaneous_whim(self):
        if random.random() < self.whim_chance:
            boost = random.uniform(self.whim_boost_min, self.whim_boost_max)
            self.dryness = min(self.dryness_max, self.dryness + boost)
            return True
        return False

    # ------------------------------------------------------------
    # GENERATING STYLE INSTRUCTIONS
    # ФОРМИРОВАНИЕ СТИЛЕВЫХ ИНСТРУКЦИЙ
    # ------------------------------------------------------------
    def get_style_instructions(self) -> str:
        parts = []
        if self.energy < 0.35:
            parts.append("отвечай очень коротко, почти телеграфно")
        elif self.energy > 0.8:
            parts.append("можешь говорить чуть свободнее, но всё равно сдержанно")
        if self.detachment > 0.75:
            parts.append("будь предельно буквальной; отвечай ровно на то, что спросили, не больше")
        elif self.detachment < 0.35:
            parts.append("можешь быть немного более вовлечённой, но никогда не тёплой")
        if self.dryness > 0.7:
            parts.append("используй сухие, неожиданные сравнения или едва уловимые подколки с невозмутимым лицом")
        elif self.dryness < 0.3:
            parts.append("избегай юмора; говори только по факту")
        if not parts:
            return ""
        return "Стиль: " + "; ".join(parts) + "."

    def get_mood_description(self) -> str:
        # Placeholder for future mood descriptions
        # Заглушка для будущих описаний настроения
        return ""

    def get_joke_hint_instruction(self, memory_fact: str) -> str:
        # Placeholder for future joke hints based on memory
        # Заглушка для будущих подсказок для шуток на основе памяти
        return ""