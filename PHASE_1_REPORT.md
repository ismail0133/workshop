# RESILIENCE-ALPHA — Rapport de phase 1

## 1. Bilan

Phase 1 implémentée et validée sur le Mac Apple Silicon : PostgreSQL, Auth Service et Payment API fonctionnent dans Docker. **46 tests pytest réussis, 0 échoué** : 45 tests unitaires/intégration et 1 test de persistance après redémarrage. Le transfert fictif de 200 € et son rejeu sont vérifiés via API et directement dans PostgreSQL. La phase 2 n’a pas commencé.

| Statut | Périmètre |
|---|---|
| IMPLEMENTED | Authentification Argon2id/JWT RS256, rôles, autorisations, comptes, paiements, historique, pagination, logs, métriques, santé, migrations et seeds |
| TESTED | Exécution ARM64, démarrage Compose, migrations head, contraintes/droits SQL, 46 tests, transfert, idempotence, concurrence, rollback et persistance |
| NOT TESTED | Exécution native AMD64 et Windows/PA, charge prolongée, panne électrique/arrêt brutal, restauration de sauvegarde, downgrade Alembic |
| BLOCKED | Aucun critère d’acceptation de phase 1 bloqué dans l’environnement Mac disponible |

## 2. Architecture réellement développée

Deux applications FastAPI sous Python 3.12, avec séparation routes/services/repositories et une bibliothèque partagée de configuration, modèles SQLAlchemy, DTO Pydantic, sécurité, erreurs, pagination et instrumentation. PostgreSQL 17 possède trois schémas et six tables : auth.users, bank.accounts, bank.transactions, ops.incidents, ops.incident_events, ops.remediation_actions. Les tables ops préparent les phases suivantes, sans moteur de remédiation implémenté.

Un paiement verrouille d’abord la paire acteur/clé d’idempotence par verrou transactionnel PostgreSQL, puis les comptes dans l’ordre UUID. Débit, crédit et insertion de transaction appartiennent au même commit. Les montants sont des entiers en centimes, sans conversion flottante. Les rejets métier enregistrés sont aussi idempotents. Une erreur SQL annule la transaction et produit une réponse expurgée.

JWT RS256 de 900 secondes, mots de passe Argon2id, vérification de l’état et du rôle courant de l’utilisateur à chaque requête. USER agit sur ses comptes ; ADMIN/OPERATOR n’ont pas de pouvoir bancaire implicite. VALIDATOR reste isolé aux comptes synthétiques. Les changements de vocabulaire CUSTOMER → USER et SUCCEEDED → SUCCESS pour les paiements sont documentés dans docs/api/PHASE1_CONTRACT_CHANGES.md.

## 3. Fichiers créés ou modifiés

- Racine : README.md, PHASE_1_REPORT.md, Makefile, pyproject.toml, requirements.in, requirements.lock, alembic.ini, .gitignore, .dockerignore, .env.example ; docker-compose.yml, docker-compose.dev.yml, docker-compose.test.yml.
- shared/resilience_common/ : __init__.py, app.py, config.py, db.py, errors.py, models.py, pagination.py, schemas.py, security.py.
- services/auth-service/auth_app/ et services/payment-api/payment_app/ : __init__.py, main.py, routes.py, service.py, repository.py ; README.md et requirements.in des deux services.
- database/ : __init__.py, bootstrap.py ; migrations/env.py, migrations/versions/0001_schema.py, 0001_schema.sql, 0002_roles.py, migrations/README.md ; seeds/__init__.py, demo.py, README.md.
- infrastructure/docker/backend.Dockerfile ; secrets locaux générés dans infrastructure/secrets/runtime/ (non versionnés, jamais incorporés aux images).
- scripts/prepare_secrets.py, stage_secrets.py, run_tests.py, validate_demo.py, check_persistence.py ; formatage du validateur historique de phase 0.
- tests/conftest.py, unit/test_contracts.py, integration/test_backend.py, e2e/test_persistence.py.
- docs/api/API_CONTRACTS.md, PHASE1_CONTRACT_CHANGES.md, openapi.json, auth.openapi.json, payment.openapi.json ; docs/database/DATABASE_DESIGN.md, initial_schema.sql ; docs/source/phase0_schema.sql ; docs/architecture/ARCHITECTURE.md ; docs/security/SECURITY_ARCHITECTURE.md ; docs/evidence/phase1/.

Les contrats OpenAPI auth.openapi.json/payment.openapi.json sont exportés des services en cours d’exécution et validés. Le contrat global de conception contient également les futurs services : il ne signifie pas qu’ils sont déjà implémentés. PHASE_0_REPORT.md et le validateur phase 0 restent historiques ; utiliser les commandes de phase 1 pour la recette actuelle.

## 4. Configuration Docker et environnement

Docker Desktop démarré avec autorisation ; moteur 29.4.0 et Compose 5.1.1. Python 3.12.15 et PostgreSQL 17.11 exécutés sur Linux aarch64. Python système conservé. Dépendances résolues/verrouillées et pip check réussi dans l’image Python. Bases Python et PostgreSQL figées par digest d’index ; manifestes linux/arm64 et linux/amd64 vérifiés (voir docs/evidence/phase1/IMAGES.md). L’exécution AMD64 n’a pas été testée.

Services non-root UID 10001, système de fichiers racine en lecture seule, capacités supprimées, no-new-privileges, tmpfs, limites CPU/mémoire, health checks et redémarrage unless-stopped. PostgreSQL a un volume persistant et aucun port publié. Les API ont des volumes de logs et secrets distincts. Le job administratif copie les seuls secrets nécessaires en fichiers 0400 appartenant au UID des API ; Payment ne reçoit pas la clé privée JWT. Aucun socket Docker n’est monté dans les workloads.

L’overlay dev publie Auth sur 127.0.0.1:8001 et Payment sur 127.0.0.1:8000, avec un bridge dev_access pour les API. Ce bridge permet une sortie réseau en développement ; la configuration de base reste interne. Les profils/configurations des futurs services sont conservés. Le laboratoire de test utilise le projet resilience-alpha-test et la base resilience_test, séparés de la démonstration ; il a été arrêté sans suppression de volumes après la recette.

## 5. Migrations et données

Bootstrap des rôles réussi, migrations 0001_schema et 0002_roles appliquées ; `alembic current` retourne **0002_roles (head)**. UUID, PK/FK, CHECK, UNIQUE, index et horodatages UTC sont définis dans le SQL figé. Rôles bootstrap/migrator/auth/bank/ops distincts ; bank peut modifier seulement les colonnes de solde et timestamp des comptes, pas leurs propriétaires. Les droits sont vérifiés par les tests.

Seed idempotent : Alice/Bob, opérateur, administrateur et validateur ; deux comptes clients et deux comptes synthétiques. Il ne réinitialise jamais les soldes ou mots de passe existants. Les valeurs des secrets ne sont pas présentes dans ce rapport. Les contraintes SQL des migrations sont la référence ; compléter leur représentation ORM avant de recourir à Alembic autogenerate.

## 6. Endpoints fonctionnels

| Service | Endpoints |
|---|---|
| Auth | POST /api/auth/login ; GET /api/auth/me ; GET /health ; GET /metrics |
| Payment | GET /api/accounts ; GET /api/accounts/{id} ; POST /api/payments ; GET /api/payments ; GET /api/payments/{id} |
| Santé Payment | GET /health/live ; GET /health/ready ; GET /metrics |
| Documentation | /docs et /openapi.json sur chaque API |

Nouveau paiement : 201/SUCCESS ; rejeu identique : 200/même UUID ; conflit d’idempotence ou rejet métier : 409 ; données invalides : 422 ; jeton invalide : 401 ; rôle interdit : 403 ; ressource étrangère : 404. Les logs JSON n’incluent ni password ni JWT, et les erreurs sont centralisées.

## 7. Tests réellement exécutés

| Suite / contrôle | Résultat |
|---|---|
| pytest unit + integration, images reconstruites | 45 passed, 0 failed, 25.81 s |
| pytest hôte e2e, redémarrage PostgreSQL/Auth/Payment | 1 passed, 0 failed, 9.73 s |
| Ruff, sources Python de la phase | All checks passed |
| OpenAPI exporté depuis les deux API locales | HTTP 200, validation des deux documents réussie |
| Alembic current | 0002_roles (head) |
| Vérification directe PostgreSQL | Soldes et transaction conformes |

La suite couvre login valide/invalide, absence de jeton, rôles, propriété, comptes inexistants, montants invalides, devise, solde insuffisant, compte gelé, plafond, idempotence, historique, curseurs, JWT invalides/expirés, désactivation immédiate, taille de corps, droits SQL, six tables, santé et métriques. Concurrence : 50 appels avec la même clé donnent une seule création ; paiements concurrents distincts ne produisent pas de découvert ; transferts opposés préservent la somme. Un trigger SQL provoque volontairement une erreur d’insertion pour vérifier le rollback du débit/crédit.

Un avertissement PyJWT concerne exclusivement la clé HMAC volontairement invalide utilisée par le test de rejet d’algorithme ; les jetons de l’application utilisent RSA 3072 bits. Aucun test n’est annoncé réussi sans exécution. Preuves : docs/evidence/phase1/pytest-run.txt, persistence-pytest.txt, ruff.txt, migrations.txt, postgresql.txt et payment-demo.json.

## 8. Scénario métier exécuté

| Vérification | Résultat observé |
|---|---|
| Avant paiement | A = 100000 centimes (1000 €), B = 50000 (500 €) |
| Transfert | 20000 centimes (200 €), HTTP 201, SUCCESS |
| Après paiement | A = 80000 (800 €), B = 70000 (700 €) |
| Rejeu même clé et corps | HTTP 200, même UUID, aucun mouvement supplémentaire |
| PostgreSQL direct | Une seule transaction ; somme A+B = 150000 centimes |
| Après redémarrage DB + API | Même UUID, mêmes soldes, rejeu 200 |

Transaction : `8c13befd-4718-4138-98d3-106a65cd79cb`. Clé fictive : `phase1-demo-transfer-200-eur`. Le contrôle d’historique confirme une seule entrée correspondante.

## 9. Problèmes rencontrés et corrections

- Docker Desktop initialement arrêté et accès au socket restreint : démarrage/commandes autorisés, moteur vérifié.
- Secrets hôte 0600 illisibles pour les API non-root : staging sélectif dans des volumes propres à chaque service, sans élargir les permissions des fichiers hôte.
- Divergence de vocabulaire entre phase 0 et demande de phase 1 : USER/ADMIN et SUCCESS adoptés, contrats et schéma mis à jour, source de phase 0 conservée.
- Imports et formatage signalés par Ruff : corrigés ; contrôle final réussi. Cache Ruff interdit sur montage en lecture seule : contrôle relancé avec --no-cache.
- Publication des ports sur réseaux uniquement internes non effective : ajout du bridge dans le seul overlay dev, puis accès HTTP local vérifié et test de persistance relancé.

## 10. Commandes reproductibles

Depuis la racine du projet, après génération des secrets (instructions complètes dans README.md) :

```sh
docker compose --profile tools build
docker compose up -d --wait postgres
docker compose run --rm db-tools python scripts/stage_secrets.py
docker compose run --rm db-tools python -m database.bootstrap
docker compose run --rm db-tools alembic upgrade head
docker compose run --rm db-tools python -m database.seeds.demo
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait auth-service payment-api
python3 scripts/run_tests.py
docker compose run --rm db-tools python scripts/validate_demo.py
pytest --confcutdir=tests/e2e tests/e2e/test_persistence.py -q
docker compose run --rm db-tools alembic current
docker compose exec -T postgres psql -U resilience_bootstrap -d resilience -c 'SELECT label,balance_minor FROM bank.accounts ORDER BY label'
```

Le pytest hôte a été exécuté avec ../.venv-phase0/bin/python -m pytest ; ce venv est un outil local, pas une dépendance runtime du backend. Alternative sans pytest hôte : python3 scripts/check_persistence.py. Ne pas lancer les fixtures d’intégration sur une autre base : elles refusent DB_NAME différent de resilience_test. Ne pas utiliser down -v pour redémarrer la démonstration.

## 11. Limites et préparation de la phase 2

Le backend est un démonstrateur bancaire fictif, pas un système bancaire de production. Limiteur de login en mémoire, mono-worker/mono-instance, sans stockage partagé. HTTP local de développement ; WAF/TLS prévus ultérieurement. Pas d’évaluation de charge longue, de sauvegarde/restauration ou de crash brutal réalisée. Les dépendances sont verrouillées mais aucun audit exhaustif de vulnérabilités n’est revendiqué. Les tables ops existent ; leurs routes, automatisations et orchestration ne sont pas implémentées.

Frontend, observabilité complète, ML, RAG, WAF, tests offensifs et remédiation restent aux phases suivantes. La compatibilité native AMD64/Windows doit être exécutée sur l’environnement cible ; seuls les manifestes multiarchitecture sont vérifiés ici. Les critères de phase 1 sont satisfaits sur ARM64. Le backend et ses contrats sont disponibles pour la phase 2, qui attend la validation de l’utilisateur.
