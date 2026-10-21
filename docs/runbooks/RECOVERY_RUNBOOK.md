# Runbook d'exploitation et de reprise

Version 1.0 — 21 octobre 2026. Destinataires : opérateur de garde et coach. Ce runbook couvre ce que l'équipe peut **faire à la main** quand la reprise autonome échoue ou ne s'applique pas. Une intervention humaine corrective pendant un essai le rend non concluant pour le critère « reprise sans opérateur » (PCA/PRA §8) : on la consigne toujours.

Les commandes se lancent depuis la racine du dépôt, sur le PC Hôte, dans le terminal WSL2. `COMPOSE` désigne :

```sh
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.edge.yml -f docker-compose.grafana-ui.yml --profile foundation"
```

## 1. Vérifier l'état avant d'agir

1. `$COMPOSE ps` : tous les services attendus doivent être `healthy`. Un conteneur `healthy` ne prouve pas que le service métier fonctionne.
2. Faire un paiement de validation par le chemin WAF (frontend, compte `validator`) ou l'API `POST /api/payments` avec une clé `Idempotency-Key` neuve : 201 `SUCCESS` attendu. Noter l'identifiant de transaction.
3. Dans Grafana (http://127.0.0.1:3000) : dashboard « Security Events (WAF / edge) » et alerte « WAF - refused requests spike (403/429) ».
4. Ne jamais conclure « rétabli » sur un redémarrage de conteneur seul : il faut un nouveau paiement cohérent (soldes débit/crédit exacts, somme inchangée).

## 2. Incident en `RECOVERY_FAILED`

L'automate a épuisé ses essais ou dépassé 60 s. Il n'a rien « réparé » : l'incident est terminal et immuable.

1. **Geler** les nouvelles actions du runner (drapeau d'exploitation local) ; conserver logs et volumes. Ne pas arrêter PostgreSQL, ne jamais lancer `down -v`.
2. Si un blocage WAF est actif et que des clients légitimes sont touchés : retirer **uniquement** ce blocage (§3).
3. Arrêter la charge à la source si elle continue (PC Attaquant : Ctrl-C ; sinon le déconnecter du point d'accès).
4. Lancer un paiement de validation (§1). Si échec : §4 (base) puis §5 (observabilité).
5. Exporter les preuves de l'incident (§8) avant rotation des logs (Loki 72 h, Prometheus 48 h).
6. Consigner l'incident comme **échec de la reprise autonome**, avec la cause et l'action humaine. Revoir l'analyse de risques (EBIOS, atelier 5) après chaque `RECOVERY_FAILED`.

## 3. Retirer un blocage WAF erroné

Le blocage a un TTL de 120 s et s'expire seul. Pour le lever plus tôt, retirer l'entrée ajoutée par le système (jamais vider toute la configuration WAF) :

1. Identifier la règle : journal WAF dans Loki (`{service="waf"}`), champ `rule_id` / `action`.
2. Retirer l'entrée correspondante de `infrastructure/waf/blocklist/blocklist.txt` (ligne `ua:` ou IP concernée).
3. Recharger le WAF : `bash scripts/demo_reset.sh` (voir ses options `--obs`, `--hard`) ou recharger Nginx dans le conteneur WAF après `nginx -t`.
4. Vérifier avec un paiement de validation puis consigner la compensation.

Limite connue : sous Docker Desktop/WSL2 l'adresse source est masquée (`client_ip` en 172.x) ; le blocage actuel porte donc sur le User-Agent, trivial à changer (`docs/governance/LIMITES_GOUVERNANCE.md` §1).

## 4. PostgreSQL indisponible

Symptômes : `payment-api` renvoie 503, readiness en échec, paiements refusés. **Aucun paiement n'est jamais confirmé sans commit** : les clients réessaient avec la même clé d'idempotence.

1. `$COMPOSE ps postgres` puis `$COMPOSE logs --tail 50 postgres`.
2. Cause fréquente observée : disque externe déconnecté, le moteur Docker ne redémarre pas Postgres. Reconnecter le disque **ou** déplacer Docker sur le SSD interne (configuration retenue pour la démonstration), puis `$COMPOSE up -d --wait postgres`.
3. Vérifier la persistance : `python3 scripts/check_persistence.py` (redémarre uniquement postgres/auth/payment).
4. Si la base est corrompue ou le volume perdu : §6 (restauration).
5. Après retour : paiement de validation, puis contrôle comptable du §6.3.

## 5. Observabilité indisponible (Prometheus, Loki, Alloy, Grafana)

Les transactions ne dépendent pas de l'observabilité. En revanche, **sans preuves fraîches la remédiation s'abstient** (fenêtre ML invalide = `DATA_UNAVAILABLE`, aucune inférence ni action). Ne pas forcer une action « à l'aveugle ».

1. Identifier le composant : `$COMPOSE ps`, cibles Prometheus (`up == 0`).
2. Relancer le composant seul : `$COMPOSE up -d --wait <service>`.
3. Si des fichiers de logs ont été perdus par rotation, marquer le trou et suspendre toute confirmation sans preuve.
4. Une fois les scrapes revenus (au moins 3 par série), le détecteur reprend automatiquement.

## 6. Sauvegarde et restauration PostgreSQL (PRA hors scénario SC-01)

Principe : sauvegarder avant chaque séance, **restaurer vers une instance et un volume distincts**, comparer l'état comptable, puis seulement décider d'une bascule documentée. Aucune restauration automatique et destructive de la base de démonstration.

### 6.1 Sauvegarder

Dans un conteneur client PostgreSQL attaché au réseau `data` (le réseau est `internal`, PostgreSQL n'a aucun port hôte) :

```sh
mkdir -p backups
docker run --rm --network resilience-alpha_data -v "$PWD/backups:/b" -v "$PWD/scripts:/s:ro" \
  -e PGPASSWORD="$(cat infrastructure/secrets/runtime/postgres_password)" \
  postgres:17-bookworm bash /s/pra_backup_restore.sh backup \
  "host=postgres user=resilience_bootstrap dbname=resilience" /b/$(date -u +%Y%m%dT%H%M%SZ)
```

Résultat : `resilience.dump` (format custom), son SHA-256, et `snapshot.json` (nombre de comptes/transactions, somme des soldes, empreintes des soldes et des transactions, version de schéma).

### 6.2 Restaurer vers une cible vierge

1. Démarrer une instance neuve avec **son propre volume** (jamais le volume de production) :
   `docker run -d --name pg-restore --network resilience-alpha_data -e POSTGRES_PASSWORD=<temp> -v pg_restore_data:/var/lib/postgresql/data postgres:17-bookworm`
2. Créer la base `resilience` et les rôles applicatifs (équivalent de `python -m database.bootstrap`).
3. `bash /s/pra_backup_restore.sh verify "<dsn cible>" /b/<horodatage>`. Le script refuse si l'empreinte du dump est invalide ou si la cible contient déjà des tables bancaires.
4. Rejouer les droits : migration `0002_roles` (`alembic upgrade head` avec le rôle migrateur).

### 6.3 Contrôle comptable et bascule

Le script compare avant/après : comptes, transactions, `SUM(balance_minor)` et empreintes. Un écart = échec, pas de bascule. Si OK : arrêter `payment-api`/`auth-service`, pointer leur `DB_HOST` vers l'instance restaurée, redémarrer, **paiement de validation**, consigner t0 (perte de service), t1 (décision), t2 (restauré), t3 (validé). Le RPO réel = écart entre le dernier commit connu et la sauvegarde.

Statut : la **logique** de ces étapes a été répétée sur deux instances PostgreSQL 16 locales (`docs/evidence/pra/rehearsal-local-pg16.md`). La répétition sur le PC Hôte (Docker Desktop, PostgreSQL 17) reste à faire trois fois ; ses durées remplaceront toute estimation.

## 7. Perte du PC Hôte

1. Récupérer le dépôt (branche gelée) sur la machine de remplacement : Windows 10/11, droits administrateur, virtualisation, Docker Desktop + WSL2, 16 Go de RAM minimum.
2. Regénérer ou déchiffrer les secrets : `python3 scripts/prepare_secrets.py` (nouveau jeu) ou SOPS/age avec la clé **conservée hors dépôt**. Sans cette clé, les secrets ne se récupèrent pas : en générer de nouveaux (tous les JWT existants deviennent invalides, c'est voulu).
3. Démarrer selon le README : `docker compose --profile tools build`, postgres, bootstrap, migrations, seed, services.
4. Restaurer les données depuis la dernière sauvegarde (§6) **si** les données comptent, sinon seed de démonstration.
5. Paiement de validation ; rejouer la recette (`scripts/validate_demo.py`).

## 8. Collecter les preuves d'un essai

Pour chaque essai : `run_id`, horodatages t0 (première dégradation) / t1 (détection) / t2 (action) / t3 (paiement validé), identifiant de l'incident, de l'action, de la transaction de validation, empreinte du modèle (`artifact_sha256`), version de politique, configuration/quota, captures du dashboard, export des logs WAF et applicatifs de la fenêtre, résultat (RTO mesuré, pertes constatées), éventuelle intervention humaine. Exporter avant rotation, sans mot de passe ni jeton.

## 9. Arrêt d'urgence du scénario d'attaque

1. Arrêter le générateur sur le PC Attaquant (Ctrl-C). Arrêt automatique de toute façon à 45 s.
2. S'il ne répond pas : déconnecter le PC Attaquant du point d'accès du groupe.
3. Geler le runner, conserver logs et volumes. Ne pas toucher à PostgreSQL.
4. Tout effet hors périmètre (réseau campus, autre groupe, service tiers) : arrêt et information immédiate du coach.

## 10. Questions fréquentes pour l'assistant

- *Que faire quand l'automate passe en RECOVERY_FAILED ?* → §2.
- *Comment lever un blocage WAF ?* → §3.
- *La base ne redémarre pas.* → §4.
- *Prometheus ou Loki sont tombés, la remédiation ne s'est pas déclenchée.* → §5 : c'est le comportement voulu.
- *Comment restaurer une sauvegarde ?* → §6.
