# rag-service

Assistant documentaire local (port 8004) : LangChain, Ollama, index FAISS natif, réponses citées, abstention sous seuil. Accès : rôle OPERATOR (`ASSISTANT_ROLES`).

- Conception : `docs/rag/RAG_DESIGN.md`. Limites : `docs/ml/LIMITES_IA.md`.
- Tests : `PYTHONPATH=. python3 -m pytest tests -q --confcutdir=. -p no:cacheprovider` (48 tests, faux embeddings et faux modèle, sans Ollama).
- Indexation : `python -m rag_app.ingest`. Recette : `python -m rag_app.evaluate --corpus <repo> [--offline] [--generate]` ; la version avec Ollama réel fixe `RAG_MIN_SCORE`.
- Image Docker : écrite, **non construite**.
