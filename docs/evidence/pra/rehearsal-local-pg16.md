# Répétition PRA — sauvegarde / restauration PostgreSQL (21/10/2026)

Environnement : conteneur de développement Linux, PostgreSQL 16.15 (deux instances distinctes src/dst, sockets Unix).
**Ce n'est PAS le PC Hôte ni PostgreSQL 17 sous Docker Desktop.** Les durées ne sont pas des RTO représentatifs ; la répétition prouve la LOGIQUE (dump, empreinte, restauration vers cible vierge, contrôle comptable, refus sur cible non vierge).
Jeu : schéma de la migration 0001_schema.sql, 40 utilisateurs, 80 comptes, 20 000 virements SUCCESS fictifs cohérents (somme des soldes conservée = 80 000 000 centimes).

```
$ scripts/pra_backup_restore.sh backup <src> backup/
snapshot: {"accounts" : 80, "transactions" : 20000, "tx_success" : 20000, "sum_balance_minor" : 80000000, "accounts_digest" : "d3e314ce0be20a1fbb66a889a6a1dd73", "tx_digest" : "709a48861cc5ad12be20e6e54b9b2125", "users" : 40, "schema_version" : "0002_roles"}
sha256 dump : 84b0fd373eed088bd1ad8e3e67cefe782cd39759ee529253268a259a3aa3e0c8
```

| Essai | Résultat observé |
|---|---|
| Sauvegarde (`pg_dump -Fc`, 20 000 virements) | 262 à 285 ms selon l'exécution (deux exécutions), 834 924 octets, empreinte SHA-256 enregistrée |
| Restauration vers instance VIERGE | 408 à 453 ms (deux exécutions) ; contrôle comptable **identique** (80 comptes, 20 000 transactions, somme des soldes 80 000 000 centimes, empreintes MD5 des soldes et des transactions) |
| Restauration vers cible déjà peuplée | **refusée** (code 3, « la cible contient déjà des tables bancaires ») : pas de restauration destructive |
| Dump altéré d'un octet | **refusé** avant restauration (« empreinte de la sauvegarde invalide ») |
| Écart comptable simulé (+1 centime sur le snapshot) | **détecté** (`sum_balance_minor` 80 000 001 ≠ 80 000 000), code 1 |

## Ce que cette répétition ne prouve pas

- Aucune mesure de RTO/RPO sur le PC Hôte (Docker Desktop/WSL2, PostgreSQL 17, volumes Docker) : à refaire selon `docs/runbooks/RECOVERY_RUNBOOK.md` §6, trois fois, et à consigner ici.
- Les droits SQL (migration 0002_roles) ne sont pas rejoués par le script : le runbook l'exige après restauration (`alembic upgrade head` / bootstrap des rôles) et la vérification applicative reste le paiement de validation.
- Les données sont synthétiques et d'un volume sans rapport avec une production.
