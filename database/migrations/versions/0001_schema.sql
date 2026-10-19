-- Phase 1 : frozen SQL executed by Alembic revision 0001_schema.
-- UUID créés par l'application. Toutes les sessions doivent utiliser UTC.
CREATE SCHEMA auth;
CREATE SCHEMA bank;
CREATE SCHEMA ops;
CREATE TABLE auth.users (
 id uuid PRIMARY KEY,
 email varchar(254) NOT NULL UNIQUE CHECK (email = lower(email)),
 password_hash text NOT NULL,
 role varchar(16) NOT NULL CHECK (role IN ('USER','OPERATOR','ADMIN','VALIDATOR')),
 is_active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE bank.accounts (
 id uuid PRIMARY KEY,
 owner_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
 label varchar(80) NOT NULL,
 currency char(3) NOT NULL DEFAULT 'EUR' CHECK (currency = 'EUR'),
 balance_minor bigint NOT NULL DEFAULT 0 CHECK (balance_minor BETWEEN 0 AND 1000000000000),
 is_synthetic boolean NOT NULL DEFAULT false,
 status varchar(12) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','FROZEN')),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX accounts_owner_idx ON bank.accounts(owner_user_id, id);
CREATE TABLE bank.transactions (
 id uuid PRIMARY KEY,
 actor_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
 source_account_id uuid NOT NULL REFERENCES bank.accounts(id) ON DELETE RESTRICT,
 destination_account_id uuid NOT NULL REFERENCES bank.accounts(id) ON DELETE RESTRICT,
 amount_minor bigint NOT NULL CHECK (amount_minor BETWEEN 1 AND 1000000000000),
 currency char(3) NOT NULL CHECK (currency = 'EUR'),
 idempotency_key varchar(128) NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 128),
 request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
 status varchar(12) NOT NULL CHECK (status IN ('SUCCESS','REJECTED')),
 failure_code varchar(32),
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK (source_account_id <> destination_account_id),
 CHECK ((status = 'SUCCESS' AND failure_code IS NULL) OR
        (status = 'REJECTED' AND failure_code IS NOT NULL AND failure_code IN ('INSUFFICIENT_FUNDS','ACCOUNT_FROZEN','BALANCE_LIMIT'))),
 UNIQUE (actor_user_id, idempotency_key)
);
CREATE INDEX transactions_source_time_idx ON bank.transactions(source_account_id, created_at DESC, id);
CREATE INDEX transactions_destination_time_idx ON bank.transactions(destination_account_id, created_at DESC, id);
CREATE TABLE ops.incidents (
 id uuid PRIMARY KEY,
 parent_incident_id uuid REFERENCES ops.incidents(id) ON DELETE RESTRICT,
 service varchar(32) NOT NULL CHECK (service = 'payment-api'),
 scenario varchar(16) NOT NULL DEFAULT 'SC-01' CHECK (scenario = 'SC-01'),
 fingerprint char(64) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
 status varchar(24) NOT NULL CHECK (status IN ('DETECTED','ANALYZING','CONFIRMED','REJECTED','REMEDIATING','VALIDATING','RECOVERED','RECOVERY_FAILED')),
 severity varchar(12) NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
 source_ip inet,
 summary varchar(500) NOT NULL,
 policy_version varchar(32),
 version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
 detected_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now(),
 deadline_at timestamptz NOT NULL,
 closed_at timestamptz,
 recovery_transaction_id uuid REFERENCES bank.transactions(id) ON DELETE RESTRICT,
 CHECK (deadline_at >= detected_at),
 CHECK ((status IN ('REJECTED','RECOVERED','RECOVERY_FAILED')) = (closed_at IS NOT NULL)),
 CHECK (status <> 'RECOVERED' OR recovery_transaction_id IS NOT NULL),
 CHECK (source_ip IS NULL OR (family(source_ip) = 4 AND masklen(source_ip) = 32))
);
CREATE UNIQUE INDEX incidents_active_fingerprint_idx ON ops.incidents(fingerprint)
 WHERE status NOT IN ('REJECTED','RECOVERED','RECOVERY_FAILED');
CREATE INDEX incidents_time_idx ON ops.incidents(detected_at DESC, id);
CREATE TABLE ops.incident_events (
 id uuid PRIMARY KEY,
 incident_id uuid NOT NULL REFERENCES ops.incidents(id) ON DELETE RESTRICT,
 sequence bigint NOT NULL CHECK (sequence > 0),
 event_type varchar(40) NOT NULL CHECK (event_type IN ('ANOMALY_DETECTED','SOC_EVIDENCE','STATE_CHANGED','ACTION_QUEUED','ACTION_RESULT','VALIDATION_RESULT','DATA_UNAVAILABLE','DUPLICATE_SUPPRESSED')),
 occurred_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),
 request_id uuid,
 payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
 UNIQUE (incident_id, sequence)
);
CREATE INDEX incident_events_time_idx ON ops.incident_events(incident_id, occurred_at);
CREATE TABLE ops.remediation_actions (
 id uuid PRIMARY KEY,
 incident_id uuid NOT NULL REFERENCES ops.incidents(id) ON DELETE RESTRICT,
 related_action_id uuid REFERENCES ops.remediation_actions(id) ON DELETE RESTRICT,
 kind varchar(24) NOT NULL CHECK (kind IN ('BLOCK_SOURCE_IP','REMOVE_SOURCE_BLOCK')),
 status varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')),
 target_ip inet NOT NULL CHECK (family(target_ip) = 4 AND masklen(target_ip) = 32),
 ttl_seconds integer NOT NULL CHECK (ttl_seconds BETWEEN 30 AND 300),
 policy_version varchar(32) NOT NULL,
 attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 2),
 fencing_token bigint NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),
 lease_token uuid,
 lease_expires_at timestamptz,
 request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
 result jsonb CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
 created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz,
 finished_at timestamptz,
 CHECK ((status = 'RUNNING') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
 CHECK ((status IN ('SUCCEEDED','FAILED')) = (finished_at IS NOT NULL)),
 CHECK ((kind = 'REMOVE_SOURCE_BLOCK') = (related_action_id IS NOT NULL)),
 UNIQUE (incident_id, kind)
);
CREATE INDEX remediation_pending_idx ON ops.remediation_actions(created_at) WHERE status = 'PENDING';
