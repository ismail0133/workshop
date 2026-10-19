# RESILIENCE-ALPHA — phase 1

Backend fictif FastAPI + PostgreSQL, issu de la conception de phase 0. Authentification Argon2id/JWT RS256, contrôle des rôles et propriétaires, transferts EUR atomiques, idempotence, concurrence, métriques et logs JSON. Frontend, ML, RAG, WAF et remédiation restent aux phases suivantes.

[Organisation du dépôt](docs/PROJECT_STRUCTURE.md) · [Rapport de phase 1](PHASE_1_REPORT.md)

## Prérequis

Docker Desktop démarré, Compose récent et architecture Linux ARM64 ou AMD64. Python3.12 s’exécute **dans les conteneurs** ; ne pas remplacer Python système. Sur Mac, Python3 et openssl servent seulement à générer les secrets locaux. Sur Windows utiliser terminal WSL2 avec Python3/openssl et Docker Desktop intégré. Le PC Windows/PA exigé par EPSI reste à tester séparément.

## Démarrer depuis ce dossier

```sh
python3 scripts/prepare_secrets.py
docker compose --profile tools build
docker compose up -d --wait postgres
docker compose run --rm db-tools python scripts/stage_secrets.py
docker compose run --rm db-tools python -m database.bootstrap
docker compose run --rm db-tools alembic upgrade head
docker compose run --rm db-tools python -m database.seeds.demo
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait auth-service payment-api
```

Les secrets sont générés aléatoirement dans `infrastructure/secrets/runtime/`, répertoire0700, fichiers0600, ignorés par Git et Docker build. Aucune valeur n’est imprimée. Les identifiants fictifs sont alice@resilience.test, bob@resilience.test, operator@resilience.test, admin@resilience.test et validator@resilience.test ; mots de passe dans les fichiers `demo_<nom>_password` correspondants. Ne pas copier ces fichiers dans une archive ou une conversation.

Le job `stage_secrets` copie seulement les secrets nécessaires dans deux volumes distincts (UID10001, fichiers0400). Les API non-root les montent en lecture seule ; Payment n’obtient jamais la clé JWT privée. Le conteneur outils utilise les droits administratifs uniquement pour les étapes explicites ; aucun secret bootstrap/migration dans les services permanents.

Le seed est idempotent : A=100000 centimes, B=50000 à la **première** création. Il ne remet jamais les soldes à zéro ni ne change les mots de passe existants. Le scénario de recette laisse A=80000/B=70000.

## Accès et API

Auth : http://127.0.0.1:8001/docs ; Payment : http://127.0.0.1:8000/docs. Avec le Compose de base sans overlay dev, les API restent internes. L’overlay ajoute un réseau bridge dev_access aux seules API pour permettre la publication sur loopback ; ce réseau autorise aussi leur sortie réseau en développement. PostgreSQL n’a aucun port hôte. Login JSON : POST /api/auth/login ; puis Bearer access_token. Routes de banque : GET /api/accounts, GET /api/accounts/{id}, POST /api/payments, GET /api/payments, GET /api/payments/{id}. Header Idempotency-Key requis pour POST ; UUID comptes et montants entiers en centimes EUR.

USER paie uniquement depuis ses comptes. OPERATOR/ADMIN n’ont pas de pouvoir de paiement ni d’endpoint d’administration implicite. VALIDATOR est isolé sur ses deux comptes synthétiques. Paiement nouveau201/SUCCESS, rejeu identique200/même transaction, corps différent même clé409, rejet métier409/REJECTED, données invalides422, ressource étrangère404, token invalide401 et rôle interdit403.

[OpenAPI Auth exécuté](docs/api/auth.openapi.json) · [OpenAPI Payment exécuté](docs/api/payment.openapi.json) · [Contrats](docs/api/API_CONTRACTS.md) · [Changements phase1](docs/api/PHASE1_CONTRACT_CHANGES.md) · [Schéma](docs/database/DATABASE_DESIGN.md) · [Architecture](docs/architecture/ARCHITECTURE.md).

## PostgreSQL et migrations

Schémas auth/bank/ops, six tables plus alembic_version. `resilience_migrator` possède le DDL ; `resilience_auth` lit auth.users ; `resilience_bank` lit ses tables et seulement id/role/is_active des utilisateurs, insère transactions, modifie uniquement soldes/timestamps ; `resilience_ops` n’a aucun droit de banque. Les contrôles de propriété s’ajoutent à ces privilèges SQL. UUID, FK, CHECK, UNIQUE, index et horodatages UTC proviennent des migrations0001_schema et0002_roles.

```sh
docker compose run --rm db-tools alembic current
docker compose exec postgres psql -U resilience_bootstrap -d resilience -c 'SELECT label,balance_minor FROM bank.accounts ORDER BY label'
docker compose exec postgres psql -U resilience_bootstrap -d resilience -c 'SELECT id,status,amount_minor FROM bank.transactions'
```

Les transferts prennent un verrou transactionnel sur acteur/clé avant de verrouiller les deux comptes dans l’ordre UUID. Débit/crédit/insertion sont committés ensemble. Les contraintes DB restent la protection finale. Une erreur après mutation mais avant commit annule l’ensemble. Ne pas exécuter initial_schema.sql manuellement ni `create_all`.

## Tests isolés

Le projet Compose `resilience-alpha-test` possède ses propres volumes/réseaux et sa base `resilience_test`. Ne jamais lancer les fixtures destructives sur la base de démonstration ; elles refusent un autre DB_NAME. Le quota login est augmenté seulement dans l’overlay de test ; production reste5/min/source.

```sh
python3 scripts/run_tests.py
```

Le script crée le laboratoire de test, applique bootstrap/migrations/secrets/seeds et exécute pytest unit/integration. Les tests couvrent les erreurs, JWT/RBAC, comptes, cohérence, rollback forcé, idempotence (50 appels concurrents), concurrence de soldes, règles SQL, métriques et santé. La persistance est vérifiée séparément sur les services de démonstration :

```sh
docker compose run --rm db-tools python scripts/validate_demo.py
python3 scripts/check_persistence.py
```

Le premier script exécute le transfert de200€ et son rejeu, puis vérifie directement PostgreSQL. Le second redémarre **uniquement** postgres/auth/payment de ce projet et vérifie même transaction et soldes. Un test pytest hôte équivalent existe : `pytest --confcutdir=tests/e2e tests/e2e/test_persistence.py` (pytest local requis, aucun socket Docker monté dans les workloads).

## Variables et exploitation

`.env.example` indique paramètres non secrets. DB_HOST/DB_NAME/DB_USER et DB_PASSWORD_FILE configurent les connexions ; JWT_PUBLIC_KEY_FILE/JWT_PRIVATE_KEY_FILE les clés ; CURSOR_KEY_FILE signe les curseurs ; LOG_DIR produit JSONL ; CPU_LIMIT_CORES/MEMORY_LIMIT_BYTES reflètent les limites Compose. LOGIN_RATE_LIMIT vaut5, un seul worker Uvicorn par service ; le limiteur mémoire est adapté au démonstrateur mono-instance, pas à un cluster.

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail 30 auth-service payment-api
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart auth-service payment-api
```

Arrêt sans perte : `docker compose -f docker-compose.yml -f docker-compose.dev.yml stop`. Relance avec `up -d --wait`. Ne jamais utiliser `down -v` pour une relance normale : cela supprime les volumes. Les migrations sont explicites, pas exécutées par les API au démarrage.

Métriques Payment /metrics, santé /health/live et /health/ready ; Auth /health et /metrics. Logs expurgés de passwords/JWT, request_id généré par service tant que WAF n’existe pas. Les configurations Prometheus/Grafana/Loki/Alloy préparées sont conservées sous profil foundation ; leur intégration complète n’est pas annoncée en phase1.

## Rapports et limites

[Rapport phase1](PHASE_1_REPORT.md) · [Rapport historique phase0](PHASE_0_REPORT.md) · [Traçabilité EPSI](docs/REQUIREMENTS_TRACEABILITY.md). Le rapport de phase1 distingue IMPLEMENTED/TESTED/NOT TESTED/BLOCKED et donne les résultats réellement obtenus. Les tests Windows, la pile de résilience et le frontend sont hors phase1. Les dépendances sont verrouillées dans requirements.lock et les images de base par index digest multiarch.
