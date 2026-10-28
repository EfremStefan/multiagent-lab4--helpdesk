"""Shared settings and the single entry point for chat calls.

All modules read settings as `config.X` at call time, so the evaluation can
switch model or chunk size at runtime (used by the ablation).
"""
import os
from pathlib import Path

import ollama

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
CACHE_DIR = ROOT / ".cache"
MANUAL_PATH = DATA_DIR / "mycovault_manual.md"
TEST_SET_PATH = DATA_DIR / "test_set.json"
TICKETS_PATH = ROOT / "tickets.jsonl"

CHAT_MODEL = os.environ.get("MV_CHAT_MODEL", "llama3.1:8b")
ABLATION_MODEL = os.environ.get("MV_ABLATION_MODEL", "qwen2.5:3b")
EMBED_MODEL = os.environ.get("MV_EMBED_MODEL", "nomic-embed-text")

CHUNK_SIZE = int(os.environ.get("MV_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = 150
RAG_K = 4
RETRIEVER_K = 5
TAU = float(os.environ.get("MV_TAU", "0.50"))  # chosen with `evaluate.py --tau-sweep`

# Incremented by every chat call; the evaluation reads and resets it per question.
LLM_CALLS = 0


def chat(messages, *, model=None, format=None, tools=None, temperature=0.0):
    """Thin wrapper around ollama.chat that counts calls."""
    global LLM_CALLS
    LLM_CALLS += 1
    return ollama.chat(
        model=model or CHAT_MODEL,
        messages=messages,
        format=format,
        tools=tools,
        options={"temperature": temperature},
    )
