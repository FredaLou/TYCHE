# 🗺️ TYCHE Roadmap

This document outlines the current development status, architectural implementation, and future plans for TYCHE.

## ✅ Implemented (v1.0 - Core Architecture)
*The foundation is stable and fully functional.*

| Feature | Implementation Details |
| :--- | :--- |
| **Local LLM Server** | `llama.cpp` with GPU support & speculative decoding (`start_server.bat`) |
| **Streaming Chat** | Context management & streaming (`core/chat.py`, `orchestrator.py`) |
| **Modular Orchestrator** | Handler separation & centralized config (`core/orchestrator.py`, `config.yaml`) |
| **Fact Memory** | JSON storage with fast-model validation (`memory.json`, `memory_writer.py`, `fact_validator.py`) |
| **Vector RAM** | ChromaDB with episode summaries (`memory/vector_memory.py`) |
| **Hybrid Search** | Semantics + stopwords + recency weighting, hot/warm/cold layers (`vector_memory.py`) |
| **Dynamic State** | Hidden parameters (`energy`, `dryness`, `detachment`, `affection`) (`utils/state_manager.py`) |
| **Circadian Rhythms** | Time-based phases loaded from config (`state_manager.py`) |
| **System Prompt** | Modular: `persona.txt` + `rules.txt` (~700 chars) (`utils/system_prompt.py`) |
| **Summarization** | Auto-episode generation every N messages (`orchestrator.py`, `utils/summarizer.py`) |

## 🚧 In Progress (v1.1 - Polish & Fixes)
*Current focus: eliminating bottlenecks and improving stability.*

- [ ] **SQLite Migration**: Replacing JSON to eliminate duplicates and memory clutter. *(High Priority)*
- [ ] **Post-Processing**: Adding regex filters to truncate repetitions, control length, and stop the model from breaking character.
- [ ] **LLM Sentiment Analysis**: The code is already written (`state_manager._analyze_sentiment_with_llm`), but currently disabled (`use_llm: false`). Needs testing and enabling.
- [ ] **Inner Monologue Fix**: Resolving instability with the fast model calls.

## 💡 Planned Features (v2.0+)
*Long-term plans for advanced autonomous behavior.*

- [ ] **Autonomous Impulses (Ticker)**: 
  - Background script checking `[DATA]`, state parameters, and user silence.
  - Uses Perlin Noise to trigger spontaneous activity.
  - `[SILENCE]` token rule to prevent spam.
- [ ] **Dynamic [DATA] Injection**:
  - Universal format for external sources (weather, PC stats, prices).
  - Router decides which function to call and injects the result directly into the prompt.
  - Includes "sporadic lying" logic and `NOT_FOUND` handling for character immersion.
- [ ] **Question Classification**: Using a fast model to tag user inputs as `[OPINION]` or `[FACT]`.

## 🗄️ Cancelled / Postponed
- [x] ~~**LoRA Fine-tuning**~~: Cancelled. Switching the base model to Qwen 27B provided the required persona stability and style out-of-the-box. Fine-tuning is no longer necessary.

## ⚠️ Known Issues
*Bugs and limitations currently being addressed.*

- **Memory Hallucinations**: The model occasionally invents details when recalling context.
- **JSON Clutter**: Fact duplicates still occur until the SQLite migration is complete.
- **Persona Drift**: The model sometimes breaks character and reverts to a standard "helpful assistant" mode.
