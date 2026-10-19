# Organisation du dépôt

Le dépôt contient un seul projet, RESILIENCE-ALPHA. Les commandes Docker et Python se lancent depuis sa racine.

```text
.
├── services/                 # Applications indépendantes
│   ├── auth-service/         # FastAPI : authentification et identité
│   ├── payment-api/          # FastAPI : comptes et paiements
│   ├── incident-service/     # Conception, phase future
│   ├── ml-detector/          # Conception, phase future
│   └── rag-service/          # Conception, phase future
├── shared/resilience_common/ # Configuration, sécurité, modèles et DTO communs
├── database/                 # Bootstrap des rôles, migrations Alembic, seed fictif
├── infrastructure/           # Docker, observabilité, secrets et configurations futures
├── frontend/                 # React/TypeScript, Design System, proxy et tests
├── scripts/                  # Initialisation et recette reproductibles
├── tests/                    # unit, integration et e2e
├── security/                 # Scénarios et conception de sécurité
├── docs/                     # Architecture, contrats, exigences et preuves
├── docker-compose.yml        # Backend interne et profils complémentaires
├── docker-compose.dev.yml    # Accès local aux API
├── docker-compose.test.yml   # Base et services de test isolés
├── requirements.lock         # Versions Python résolues et testées
├── README.md                 # Point d’entrée : installation et utilisation
└── PHASE_*_REPORT.md          # Bilans de phase et limites de validation
```

## Conventions

- Chaque service exécuté sépare routes HTTP, logique métier et accès aux données dans routes.py, service.py et repository.py.
- Les composants partagés restent dans shared ; les migrations SQL versionnées sont la référence des contraintes PostgreSQL.
- Les preuves sélectionnées sont dans docs/evidence/phase1. Les rapports de phase 0 décrivent l’état historique, pas la couverture actuelle.
- Les secrets générés, caches, environnements virtuels, données de base et artefacts runtime ne sont pas versionnés. Chaque membre génère ses propres secrets selon le README.
- Le frontend est opérationnel en phase 2. ML, RAG et la remédiation restent explicitement non configurés.

## Navigation

- [Démarrage et API](../README.md)
- [Rapport phase 1](../PHASE_1_REPORT.md)
- [Architecture](architecture/ARCHITECTURE.md)
- [Contrats exécutés Auth](api/auth.openapi.json) et [Payment](api/payment.openapi.json)
- [Schéma PostgreSQL](database/DATABASE_DESIGN.md)
- [Traçabilité des exigences](REQUIREMENTS_TRACEABILITY.md)
