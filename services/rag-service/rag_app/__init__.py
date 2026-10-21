"""Assistant documentaire local (Ollama + LangChain + RAG FAISS) — RESILIENCE-ALPHA.

L'assistant lit, explique, cite. Il n'a AUCUN outil, aucun accès SQL/secret/runner et ne peut
déclencher aucune action : la remédiation reste déterministe (incident-service).
"""

CHUNK_CHARS = 1200  # ~350 tokens FR (≈3,5 car./token)
CHUNK_OVERLAP = 175  # ~50 tokens
