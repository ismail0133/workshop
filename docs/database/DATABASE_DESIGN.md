# Modèle PostgreSQL

DDL initial : [initial_schema.sql](initial_schema.sql), **non exécuté**, à transcrire en migration Alembic après validation de phase 1. Six tables, trois schémas ; aucun serveur ni rôle créé durant la phase 0. Le diagramme ER figure dans `../architecture/DIAGRAMS.md`.

## MCD et MLD

Un utilisateur possède 0..N comptes ; chaque compte a exactement un propriétaire. Une transaction a un acteur, un compte débité et un compte crédité distincts, chacun existant. Un compte participe à 0..N transactions dans chaque rôle. Un incident possède 0..N événements et 0..N actions. Un incident peut référencer un incident antérieur ; une transaction de validation peut prouver la reprise d’un incident (référence facultative jusqu’à RECOVERED).

MLD : `users(id PK)` → `accounts(owner_user_id FK)` ; `transactions(actor_user_id FK, source_account_id FK, destination_account_id FK)` ; `incidents(parent_incident_id FK, recovery_transaction_id FK)` → `incident_events(incident_id FK)` et `remediation_actions(incident_id FK)`. UUID fournis par l’application, sans dépendance à une extension.

## Dictionnaire et contraintes

| Table | Colonnes et types | Règles et index |
|---|---|---|
| auth.users | id uuid ; email varchar(254) ; password_hash text ; role varchar(16) ; is_active boolean ; created_at timestamptz | Email minuscule unique ; rôles USER/OPERATOR/ADMIN/VALIDATOR ; hash Argon2id jamais exposé |
| bank.accounts | id uuid ; owner_user_id uuid FK ; label varchar(80) ; currency char(3) ; balance_minor bigint ; is_synthetic boolean ; status varchar(12) ; created_at/updated_at timestamptz | EUR uniquement ; solde 0..10^12 centimes ; ACTIVE/FROZEN ; index owner,id |
| bank.transactions | id uuid ; actor_user_id/source_account_id/destination_account_id uuid FK ; amount_minor bigint ; currency char(3) ; idempotency_key varchar(128) ; request_hash char(64) ; status varchar(12) ; failure_code varchar(32) nullable ; created_at timestamptz | Montant 1..10^12, comptes distincts ; clé unique par acteur ; SUCCESS/REJECTED ; index compte source/compte destination + temps/id |
| ops.incidents | id/parent_incident_id uuid ; service/scenario/fingerprint/status/severity/summary/policy_version textes bornés ; source_ip inet nullable ; version integer ; detected_at/updated_at/deadline_at/closed_at timestamptz ; recovery_transaction_id uuid nullable | 8 états ; service payment-api ; SC-01 ; severity LOW/MEDIUM/HIGH/CRITICAL ; empreinte active unique partielle ; clôture requise seulement en état terminal ; transaction requise pour RECOVERED |
| ops.incident_events | id/incident_id/request_id uuid ; sequence bigint ; event_type varchar(40) ; occurred_at/recorded_at timestamptz ; payload jsonb | id = event_id source, globalement unique ; séquence unique par incident ; types fermés dans DDL ; JSON objet ; index incident/temps |
| ops.remediation_actions | id/incident_id/lease_token/related_action_id uuid ; kind/status/policy_version/request_hash textes ; target_ip inet ; ttl_seconds/attempt integer ; fencing_token bigint ; lease_expires_at/created_at/started_at/finished_at timestamptz ; result jsonb | BLOCK_SOURCE_IP/REMOVE_SOURCE_BLOCK ; PENDING/RUNNING/SUCCESS/FAILED ; TTL 30..300 ; max 2 essais ; une action par kind/incident ; related_action_id obligatoire pour retrait ; bail exclusif RUNNING ; index file PENDING |

Toutes les FK sont RESTRICT, toutes les PK NOT NULL. Le SQL est l’autorité pour la nullabilité détaillée et les CHECK. Pas de suppression en cascade de preuves. `updated_at` est actualisé explicitement par l’application. Le fuseau de session est UTC ; API sérialise RFC3339 `Z`. `timestamptz` représente un instant, pas le fuseau d’origine.

## Paiement atomique et concurrence

1. Valider JWT, longueur clé, JSON, montant, EUR et UUID avant DB. Interdire source=destination.
2. BEGIN READ COMMITTED ; prendre `pg_advisory_xact_lock` sur hash stable du couple acteur/clé (collision = sérialisation supplémentaire, pas corruption). Attente bornée 2 s ; timeout = 503 retryable.
3. Rechercher `(actor_user_id,idempotency_key)`. Même hash canonique des quatre champs de paiement : renvoyer la même transaction sans mutation (200 ou 409 REJECTED). Hash différent : 409 IDEMPOTENCY_CONFLICT.
4. Lire les deux comptes avec `SELECT ... FOR UPDATE` dans l’ordre UUID croissant. Vérifier source appartenant à l’acteur. VALIDATOR ne peut transférer qu’entre ses deux comptes synthétiques. Destination autorisée = tout compte actif existant ; pas de divulgation de son propriétaire/solde.
5. Si comptes introuvables/non autorisés : 404, rollback, pas de trace de transaction exposant un autre compte. Si solde insuffisant, compte gelé ou plafond destinataire dépassé : insérer REJECTED avec code, sans toucher aux soldes, puis COMMIT.
6. Débiter/créditer et insérer SUCCESS dans **la même** transaction SQL ; vérifier somme conservée. COMMIT avant réponse 201 et métrique de succès. Crash avant commit = aucun effet ; crash après commit = replay idempotent.

L’unicité DB reste la protection finale contre un bug de verrou. Ne pas débiter puis tenter une insertion dont on ignorerait le conflit. Aucun paiement PENDING persistant dans ce MVP. Les erreurs 401/403/422 ne deviennent pas des transactions métier. Les valeurs rejetées pour solde sont rejouées avec la même clé même si le solde a changé : utiliser une nouvelle clé pour une nouvelle intention.

## Incidents et durabilité

Ingestion : insertion événement + création/rattachement incident dans une transaction. `incident_events.id` déduplique les retries ; un même event_id avec contenu différent rend 409. Empreinte = SHA256(service + scénario + classe de signal), ne contient pas l’IP avant corrélation ; un seul incident SC-01 actif pour Payment API. Les événements supplémentaires sont annexés. Sous verrou de la ligne incident, incrémenter `version` et `sequence` ; état et événement changent ensemble. Les tâches sont retrouvées dans `incidents`/`remediation_actions` après redémarrage ; pas de broker indispensable.

Claim runner : `FOR UPDATE SKIP LOCKED`, max un job actif ; incrément `fencing_token`, bail 15 s, exécution max 10 s. Renouvellement non prévu pour SC-01 ; une tâche trop longue échoue. Token expiré ne peut plus clore l’action. Le contrôleur WAF mémorise id/action/hash/version pour réconcilier un crash après application. Ne jamais supposer qu’un timeout signifie « pas d’effet ».

## Droits et limites

Rôle auth : auth.users seulement. Rôle bank : accounts/transactions et SELECT limité à id/role/is_active de users si nécessaire ; pas de hash. Rôle incident : ops.* uniquement ; le validateur utilise Payment API, jamais UPDATE bank. Rôle migration distinct et non chargé dans les services. Runner/ML/RAG n’ont aucun accès SQL. Les GRANT seront une migration dédiée ; les contrôles de propriété restent obligatoires dans toutes les requêtes SQLAlchemy.

Le CHECK RECOVERED vérifie une référence, **pas** la réussite métier ou la conservation des soldes : Recovery Validator doit les vérifier via API et tests d’intégration. L’équilibrage comptable interlignes et les transitions d’état ne sont pas garantis par les seuls CHECK ; ils appartiennent aux transactions applicatives testées.

Tests de phase 1 : 50 requêtes concurrentes même clé = un débit ; clés différentes sur dernier solde = aucun découvert ; ordre croisé des comptes = absence de blocage durable ; crash avant/après commit ; replay modifié ; FK ; rôles SQL ; UTC ; mutation d’état concurrente. Aucun de ces tests métier n’a encore été exécuté.


Mise à jour phase 1 : rôles USER/OPERATOR/ADMIN (VALIDATOR technique conservé), paiement SUCCESS. Voir `docs/api/PHASE1_CONTRACT_CHANGES.md` depuis la racine. Les descriptions de phases futures restent des cibles.
