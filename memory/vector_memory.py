# memory/vector_memory.py
import os
import yaml
import requests
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from datetime import datetime
from typing import List, Dict, Optional, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_FILE = os.path.join(BASE_DIR, "config", "config.yaml")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
MEMORY_CFG = config.get("memory", {})

chroma_rel_path = MEMORY_CFG.get("chroma_path", "memory/chroma_db")
CHROMA_DB_PATH = os.path.join(BASE_DIR, chroma_rel_path)
COLLECTION_NAME = MEMORY_CFG.get("collection_name", "conversations")
EMBEDDING_MODEL = MEMORY_CFG.get("embedding_model", "paraphrase-multilingual-MiniLM-L12-v2")
COLD_THRESHOLD_DAYS = MEMORY_CFG.get("cold_threshold_days", 30)
RETRIEVAL_K = MEMORY_CFG.get("retrieval_k", 2)
RETRIEVAL_THRESHOLD = MEMORY_CFG.get("retrieval_threshold", 0.5)
WARM_THRESHOLD = MEMORY_CFG.get("warm_threshold", 0.4)
USE_HYBRID = MEMORY_CFG.get("use_hybrid", True)

FAST_URL = config["model"]["fast_url"]

print(f"[RAM] ChromaDB path: {CHROMA_DB_PATH}")
print("[RAM] Loading embedding model...")
EMBED_MODEL = SentenceTransformer(EMBEDDING_MODEL)
print("[RAM] Embedding model loaded.")

class VectorMemory:
    """
    Manages long-term memory using ChromaDB.
    Управляет долговременной памятью с использованием ChromaDB.
    """
    def __init__(self):
        # Initialize persistent ChromaDB client
        # Инициализация постоянного клиента ChromaDB
        self.client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        # Get or create collection with cosine similarity space
        # Получаем или создаем коллекцию с косинусным расстоянием
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"[RAM] Persistent collection '{COLLECTION_NAME}' ready. Docs count: {self.collection.count()}")
        # [RAM] Постоянная коллекция готова. Количество документов: ...

    def add_episode(self, summary: str, start_time: str, end_time: str, message_count: int):
        """
        Adds a new episode to memory, or merges it with an existing similar one.
        Добавляет новый эпизод в память или объединяет его с существующим похожим.
        """
        if not summary:
            return

        # Check for similar existing episodes (threshold 0.3 means very similar)
        # Проверяем на наличие похожих существующих эпизодов (порог 0.3 означает очень высокое сходство)
        similar = self.retrieve_similar(summary, k=1, use_hybrid=False)
        if similar:
            best = similar[0]
            # If distance is <= 0.3, we consider it the same topic
            # Если расстояние <= 0.3, считаем, что это та же тема
            if best['distance'] <= 0.3:
                existing_id = best['metadata'].get('id')
                if existing_id:
                    # Merge the old summary with the new one
                    # Объединяем старую сводку с новой
                    combined = self._update_episode(existing_id, best['document'], summary)
                    combined_embedding = EMBED_MODEL.encode(combined).tolist()
                    new_meta = {
                        "type": "episode",
                        "start_time": best['metadata']['start_time'],
                        "end_time": end_time,
                        "message_count": best['metadata']['message_count'] + message_count,
                        "layer": "warm",
                        "id": existing_id
                    }
                    self.collection.update(
                        ids=[existing_id],
                        documents=[combined],
                        embeddings=[combined_embedding],
                        metadatas=[new_meta]
                    )
                    print(f"[RAM] Episode merged with {existing_id}.")
                    # [RAM] Эпизод объединен с ...
                    return

        # If no similar episode found, create a new one
        # Если похожий эпизод не найден, создаем новый
        embedding = EMBED_MODEL.encode(summary).tolist()
        doc_id = f"ep_{start_time}_{end_time}"
        meta = {
            "type": "episode",
            "start_time": start_time,
            "end_time": end_time,
            "message_count": message_count,
            "layer": "warm",
            "id": doc_id
        }
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[summary],
            metadatas=[meta]
        )
        print(f"[RAM] New episode saved: {doc_id}")
        # [RAM] Новый эпизод сохранен: ...

    def _update_episode(self, existing_id: str, old_summary: str, new_summary: str) -> str:
        """
        Uses the fast model to merge two summaries into one.
        Использует быструю модель для объединения двух сводок в одну.
        """
        prompt = f"""Combine the following two summaries of the same conversation topic into a single coherent summary of 2-4 sentences.
Old summary: {old_summary}
New details: {new_summary}
Combined summary:"""
        # Примечание: здесь жестко задан русский язык вывода для сводок. 
        # Если нужна поддержка английского, можно динамически менять язык.
        try:
            response = requests.post(
                FAST_URL,
                json={
                    "messages": [
                        {"role": "system", "content": "You are a concise summarizer. Reply only with the combined summary"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": config["model"].get("fast_max_tokens", 200),
                    "stream": False
                },
                timeout=config["model"].get("timeout", 30)
            )
            result = response.json()
            combined = result["choices"][0]["message"]["content"].strip()
            self.collection.update(ids=[existing_id], documents=[combined])
            print(f"[RAM] Episode {existing_id} text updated.")
            # [RAM] Текст эпизода ... обновлен.
            return combined
        except Exception as e:
            print(f"[RAM] Episode update error: {e}")
            # [RAM] Ошибка обновления эпизода: ...
            return old_summary

    def age_episodes(self, cold_threshold_days: int = COLD_THRESHOLD_DAYS):
        """
        Moves warm episodes to the cold layer if they are older than the threshold.
        Перемещает горячие эпизоды в холодный слой, если они старше порога.
        """
        now = datetime.now()
        results = self.collection.get(include=["metadatas"])
        ids = results.get('ids')
        metas = results.get('metadatas')
        if not ids or not metas:
            return

        for i, doc_id in enumerate(ids):
            meta = dict(metas[i])
            if meta is None:
                continue
            if meta.get('layer') == 'cold':
                continue
            end_time_val = meta.get('end_time')
            if not isinstance(end_time_val, str):
                continue
            try:
                end_time = datetime.fromisoformat(end_time_val)
                # Check if episode is older than the threshold
                # Проверяем, старше ли эпизод установленного порога
                if (now - end_time).days >= cold_threshold_days:
                    meta['layer'] = 'cold'
                    self.collection.update(ids=[doc_id], metadatas=[meta])
                    print(f"[RAM] Episode {doc_id} moved to cold layer.")
                    # [RAM] Эпизод ... перемещен в холодный слой.
            except Exception:
                continue

    def retrieve_similar(self, query: str, k: int = RETRIEVAL_K, warm_threshold: float = WARM_THRESHOLD, use_hybrid: bool = USE_HYBRID) -> List[Dict]:
        """
        Retrieves relevant episodes based on semantic similarity and recency.
        Извлекает релевантные эпизоды на основе семантического сходства и свежести.
        """
        if self.collection.count() == 0:
            return []

        query_embedding = EMBED_MODEL.encode(query).tolist()
        now = datetime.now()

        def search_layer(layer: str, n_results: int) -> List[Dict]:
            # Search specific layer (warm or cold)
            # Поиск в конкретном слое (горячий или холодный)
            try:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(n_results, self.collection.count()),
                    where={"layer": layer},
                    include=["documents", "metadatas", "distances"]
                )
            except Exception:
                return []

            fragments = []
            ids = results.get('ids')
            docs = results.get('documents')
            metas = results.get('metadatas')
            dists = results.get('distances')
            if not ids or not docs or not metas or not dists:
                return fragments
            if ids[0] is None:
                return fragments

            for i in range(len(ids[0])):
                doc = docs[0][i]
                meta = metas[0][i]
                dist = dists[0][i]
                sim = 1.0 - dist

                end_time_val = meta.get('end_time')
                if isinstance(end_time_val, str):
                    try:
                        end_time = datetime.fromisoformat(end_time_val)
                        age_days = (now - end_time).total_seconds() / 86400.0
                        # Calculate recency weight: drops over 60 days, minimum 0.3
                        # Вычисляем вес свежести: снижается за 60 дней, минимум 0.3
                        recency_weight = max(0.3, 1.0 - age_days / 60.0)
                    except:
                        recency_weight = 0.5
                else:
                    recency_weight = 0.5
                
                # Apply recency penalty to similarity
                # Применяем штраф за давность к сходству
                weighted_sim = sim * recency_weight

                fragments.append({
                    'document': doc,
                    'metadata': meta,
                    'distance': dist,
                    'similarity': sim,
                    'weighted_similarity': weighted_sim,
                    'recency_weight': recency_weight
                })
            return fragments

        # Fetch more from warm layer first
        # Сначала берем больше результатов из горячего слоя
        warm_results = search_layer("warm", k * 2)
        cold_results = []
        
        # Fetch from cold layer only if warm results are insufficient or not relevant enough
        # Берем из холодного слоя только если горячих результатов недостаточно или они не достаточно релевантны
        if len(warm_results) < k or (warm_results and warm_results[0]['similarity'] < warm_threshold):
            cold_results = search_layer("cold", k)

        all_results = warm_results + cold_results
        
        # Sort by weighted similarity in descending order (highest first)
        # Сортируем по взвешенному сходству по убыванию (сначала самые релевантные)
        all_results.sort(key=lambda x: x['weighted_similarity'], reverse=True)

        # Hybrid search: literal keyword filtering (if enabled and query is not empty)
        # Гибридный поиск: фильтрация по точным ключевым словам (если включен и запрос не пустой)
        if use_hybrid and query.strip():
            # Added English stop words for better multilingual support
            # Добавлены английские стоп-слова для лучшей поддержки мультиязычности
            stop_words = {
                'я', 'ты', 'он', 'она', 'мы', 'вы', 'они', 'это', 'как', 'что', 'где', 'когда',
                'почему', 'зачем', 'для', 'на', 'в', 'с', 'по', 'к', 'у', 'о', 'от', 'до', 'из',
                'а', 'и', 'но', 'или', 'не', 'то', 'же', 'бы', 'ли',
                'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that', 'how', 'what', 
                'where', 'when', 'why', 'for', 'on', 'in', 'with', 'by', 'to', 'at', 'of', 
                'from', 'and', 'or', 'not', 'is', 'are', 'was', 'were', 'be', 'been', 'a', 'an', 'the'
            }
            
            # Extract meaningful words from the query
            # Извлекаем значимые слова из запроса
            query_words = set(
                word.lower() for word in query.split()
                if word.isalpha() and len(word) > 2 and word.lower() not in stop_words
            )
            
            if query_words:
                # Keep only results containing at least one query word
                # Оставляем только результаты, содержащие хотя бы одно слово из запроса
                filtered = [
                    item for item in all_results
                    if any(qw in item['document'].lower() for qw in query_words)
                ]
                # If filter is not empty, apply it
                # Если фильтр не пустой, применяем его
                if filtered:
                    all_results = filtered

        # Filter by final threshold and return top K
        # Фильтруем по финальному порогу и возвращаем топ K
        all_results = [item for item in all_results if item['similarity'] >= RETRIEVAL_THRESHOLD]
        return all_results[:k]

_ram_instance = None

def get_vector_memory() -> VectorMemory:
    global _ram_instance
    if _ram_instance is None:
        _ram_instance = VectorMemory()
    return _ram_instance
