# Catalogue des services

Cible à construire ; les endpoints ci-dessous sont des contrats, pas des services actuellement démarrés. RAM = plafond initial MiB, à mesurer ; CPU = quota initial en cœurs. Entrées/sorties structurées dans `docs/api/openapi.json` et schémas d’événements.

| Service | Responsabilité / technologie | Entrées → sorties et dépendances | API et health | Données / sécurité | RAM / CPU |
|---|---|---|---|---|---|
| frontend | Banque fictive + supervision ; React/TS/Vite/Tailwind compilé, serveur statique | WAF → pages ; appels API via même origine | HTTP 8080 ; `/health` statique | JWT en mémoire, CSP, pas de secrets embarqués ; customer/operator | 128 / 0.25 |
| payment-api | Comptes et transferts ; Python 3.12/FastAPI/SQLAlchemy | JWT + paiement → résultat ; PostgreSQL | 8000 : accounts/payments ; `/health/live`, `/health/ready`, `/metrics` | bank.*, clé publique JWT RO ; rôle bank ; idempotence et ACID | 384 / 0.75 |
| auth-service | Login et identité ; FastAPI/Argon2id/JWT RS256 | Identifiants → token ; PostgreSQL | 8001 : login/me ; `/health`, `/metrics` | auth.users, seule clé privée JWT, rate limit login | 256 / 0.5 |
| incident-service | Manager, SOC, politiques, orchestration, validation ; FastAPI + worker | Anomalies/JSON Loki → incidents/jobs ; DB, Prometheus, Loki, WAF | 8002 : incidents, anomalies, jobs ; `/health/live`, `/health/ready`, `/metrics` | ops.*, secrets internes séparés ; worker unique + verrous DB ; aucun socket Docker/WAF | 512 / 0.75 |
| ml-detector | Extraction et inférence Isolation Forest ; sklearn/pandas/NumPy | Prometheus → événement anomalie ; Incident API | 8003 : `/health/live`, `/health/ready`, `/metrics` (aucune API publique) | Modèle signé par hash, features versionnées, token anomaly:write | 512 / 0.5 |
| rag-service | Recherche documentaire et génération ; LangChain/FAISS/FastAPI | question → réponse citée ; fichiers RO, Ollama | 8004 : chat/health, `/metrics` | operator seulement ; aucun SQL/secret infra/outils shell ; timeout 30 s | 512 / 0.5 |
| postgres | Persistance PostgreSQL 17 cible | SQL auth/bank/ops → lignes ACID | 5432 ; `pg_isready`, puis SELECT applicatif | Volume durable, rôles limités, max_connections 40 | 768 / 1 |
| prometheus | Séries et requêtes ; Prometheus | scrapes → PromQL/alertes | 9090 ; `/-/ready` | Volume 48 h / 1 GiB, sans port hôte | 512 / 0.5 |
| grafana | Cinq dashboards techniques | Prometheus/Loki → graphiques | 3000 ; `/api/health` | Admin secret fichier, pas d’accès anonyme, loopback hôte | 384 / 0.5 |
| loki | Logs centralisés mono-instance | Alloy → LogQL pour SOC/Grafana | 3100 ; `/ready` | Volume 72 h, flux internes seulement, pas d’Elastic | 512 / 0.5 |
| waf | Reverse proxy TLS, CRS, règle ciblée et contrôle local | requêtes → API + logs ; commandes fermées runner → ack | 8443 public ; `/health/live`, `/health/ready` ; 9113 interne `/metrics` ; socket Unix | Certificat labo, refus internal/metrics, config validée, contrôle non exposé | 384 / 0.75 |
| ollama | LLM/embeddings uniquement | RAG → vecteurs/réponse | 11434 ; `/api/tags` et inférence smoke | qwen2.5:1.5b, nomic-embed-text:v1.5 ; aucun outil d’administration | 3072 / 2 |
| alloy | Expédition logs | volumes JSON RO → Loki | 12345 ; `/-/ready`, `/metrics` internes | Volumes producteurs séparés, pas de socket Docker ; positions durables | 256 / 0.25 |
| remediation-runner | Poll jobs, Ansible immuable | job/bail → résultat ; Incident API + socket WAF | 8005 `/health/live`, `/metrics` ; aucune soumission publique | Non-root, socket WAF seul, token runner, pas de DB ni Docker ; 1 job | 384 / 0.5 |

Total plafonds : 8 576 MiB avec Ollama (5 504 MiB sans). Ces maxima ne garantissent pas l’occupation réelle. Réserver macOS/IDE et VM ; ne pas attribuer tous les cœurs simultanément sous charge. Le collecteur et le runner sont des composants techniques nécessaires, pas deux nouveaux microservices métier.

## Health checks et dépendances

Liveness : processus seulement, toutes les 10 s, timeout 2 s, 3 échecs. Readiness : DB et schéma pour auth/payment ; DB + configuration politiques pour incident ; modèle + métriques fraîches pour ML ; index + Ollama pour RAG. Grace period 30 s, 120 s pour Ollama. Une panne Loki est visible dans la santé SOC et suspend les décisions, sans faire redémarrer Payment API. L’orchestrateur ne confond pas Docker `healthy` et validation métier.

Le worker d’incident relit les états non terminaux au démarrage. L’état d’une action inconnue est réconcilié auprès du contrôleur WAF avant toute réexécution. Les credentials du validateur sont distincts des tokens de runner et ML.
