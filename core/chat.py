# core/chat.py (или run.py)
import sys
import signal
import os
import yaml
from datetime import datetime

from memory.vector_memory import get_vector_memory
from utils.state_manager import TycheState
from core.orchestrator import Orchestrator
from memory.memory_writer import load_memory_text

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def graceful_shutdown(signum, frame, orchestrator):
    print("\n[!] Interrupted. Saving session...")
    raise KeyboardInterrupt()

def main():
    config = load_config()
    ram = get_vector_memory()
    state = TycheState()

    orchestrator = Orchestrator(config, ram, state)

    signal.signal(signal.SIGINT, lambda sig, frame: graceful_shutdown(sig, frame, orchestrator))

    messages = [
        {"role": "system", "content": orchestrator._build_system_prompt("", load_memory_text())}
    ]

    print("\nTYCHE online. Type 'exit' to quit.\n")

    try:
        while True:
            user_input = input("You: ")
            if user_input.lower() == "exit":
                break

            print("\nTYCHE: ", end="", flush=True)

            response, messages = orchestrator.process_message(user_input, messages)

            print("\n")
    except KeyboardInterrupt:
        print("\n[!] Session interrupted.")
    finally:
        orchestrator.finalize_session()

if __name__ == "__main__":
    main()
