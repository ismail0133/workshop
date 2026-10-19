# Migrations phase 1

`0001_schema` crée les trois schémas et six tables avec contraintes/index. `0002_roles` applique les droits minimaux et la lecture de la version Alembic. Le bootstrap crée préalablement les rôles PostgreSQL.

Exécuter `docker compose run --rm db-tools alembic upgrade head`, puis `alembic current` avec le même préfixe. Le SQL de la première migration est figé ; ne pas modifier une migration appliquée. Ne pas exécuter le DDL documentaire ou `create_all`. Les contraintes SQL complètes sont dans les migrations ; compléter la parité des métadonnées ORM avant tout autogenerate futur. Un downgrade détruit les données : réservé à une base de test jetable.
