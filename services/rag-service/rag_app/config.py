from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    corpus_root: Path
    index_dir: Path
    ollama_url: str
    chat_model: str
    embed_model: str
    top_k: int
    min_score: float
    num_ctx: int
    num_predict: int
    temperature: float
    timeout_seconds: float
    jwt_public_key_file: Path | None
    issuer: str
    audience: str
    roles: frozenset[str]
    log_dir: Path | None

    @staticmethod
    def load() -> "Settings":
        key = os.getenv("JWT_PUBLIC_KEY_FILE")
        log_dir = os.getenv("LOG_DIR")
        return Settings(
            corpus_root=Path(os.getenv("CORPUS_ROOT", "/corpus")),
            index_dir=Path(os.getenv("INDEX_DIR", "/index")),
            ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
            chat_model=os.getenv("CHAT_MODEL", "qwen2.5:1.5b"),
            embed_model=os.getenv("EMBED_MODEL", "nomic-embed-text:v1.5"),
            top_k=int(os.getenv("RAG_TOP_K", "3")),
            # Seuil d'abstention : À CALIBRER sur les 10 questions de recette (rag_eval/).
            min_score=float(os.getenv("RAG_MIN_SCORE", "0.45")),
            num_ctx=int(os.getenv("RAG_NUM_CTX", "2048")),
            num_predict=int(os.getenv("RAG_NUM_PREDICT", "384")),
            temperature=float(os.getenv("RAG_TEMPERATURE", "0.1")),
            timeout_seconds=float(os.getenv("RAG_TIMEOUT_SECONDS", "30")),
            jwt_public_key_file=Path(key) if key else None,
            issuer=os.getenv("JWT_ISSUER", "resilience-alpha-auth"),
            audience=os.getenv("JWT_AUDIENCE", "resilience-alpha"),
            roles=frozenset(os.getenv("ASSISTANT_ROLES", "OPERATOR").split(",")),
            log_dir=Path(log_dir) if log_dir else None,
        )
