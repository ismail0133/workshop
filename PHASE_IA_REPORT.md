# Rapport de phase — pilier IA (21 octobre 2026)

| Élément | Statut | Preuve / reste à faire |
|---|---|---|
| Détecteur ML (features, pipeline, calibrage, règle d'alerte, événement, envoi) | IMPLÉMENTÉ, TESTÉ (120 tests, ruff) | Données **synthétiques** uniquement |
| Performances ML réelles | NON TESTÉ | Collecte et entraînement sur le PC Hôte : `docs/ml/ML_REPORT.md` §5 |
| Requêtes PromQL | Syntaxe validée | Jamais exécutées sur un vrai Prometheus |
| Détecteur par User-Agent sur les logs du WAF → `blocklist.txt` (`ml_app/waf/`) | IMPLÉMENTÉ, TESTÉ (68 tests dédiés, 120 au total pour le service) | Écriture atomique, simulation par défaut, rejeu et suivi du fichier ou d'un flux |
| Résultats sur journal réel du WAF (31 min, 13 384 requêtes) | MESURÉ, NON PROBANT | Flood détecté en 15 s, 0 blocage d'un navigateur ; précision non mesurable, 7/11 pics normaux jugés atypiques ; voir `docs/ml/ML_REPORT.md` §7 |
| Assistant RAG (corpus, FAISS, chaîne, API JWT, abstention, citations) | IMPLÉMENTÉ, TESTÉ (48 tests, ruff) | Faux embeddings et faux modèle ; couverture lexicale hors ligne 9/10 |
| Qualité RAG, seuil `RAG_MIN_SCORE`, injection réelle | NON TESTÉ | Nécessite Ollama |
| `docker-compose.ai.yml` | `docker compose config` OK | Jamais démarré |
| Dockerfiles ml-detector / rag-service | ÉCRITS | NON CONSTRUITS |
| Frontend (`Assistant.tsx`, pages détection) | NON RACCORDÉ | À faire |
| Consommateur incident-service | ABSENT | Le détecteur reste en dry-run |

À arbitrer : le rôle ADMIN est exclu de l'assistant par le contrat ; à confirmer.

Reproduire : `make test-ai`.
