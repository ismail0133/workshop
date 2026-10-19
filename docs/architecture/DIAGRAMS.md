# Diagrammes Mermaid — architecture cible v0.1

Ces onze vues décrivent les contrats prévus ; elles ne représentent pas un système déjà implémenté. Noms identiques au SERVICE_CATALOG, ports et routes dans DATA_FLOWS et OpenAPI. Les fichiers `.mmd` voisins sont extraits de ce document pour rendu ultérieur.

## 1. Architecture globale

```mermaid
flowchart LR
  U[Client légitime] --> W[waf]
  AT[PC Attaquant autorisé] --> W
  W --> F[frontend]
  W --> A[auth-service]
  W --> P[payment-api]
  W --> I[incident-service]
  W --> R[rag-service]
  A --> DB[(postgres)]
  P --> DB
  I --> DB
  PR[prometheus] -->|scrape| P
  ML[ml-detector] -->|requêtes| PR
  ML -->|anomalies| I
  P -->|logs| AL[alloy]
  W -->|logs| AL
  I -->|logs| AL
  AL --> L[loki]
  I -->|corrélation| L
  I -->|validation métriques| PR
  RUN[remediation-runner] -->|claim et result| I
  RUN -->|Ansible - socket Unix| W
  I -->|paiement de validation| W
  G[grafana] --> PR
  G --> L
  R --> FA[(FAISS et documents)]
  R --> O[ollama]
```

## 2. Composants du moteur

```mermaid
flowchart TB
  ML[ml-detector] --> API[API interne anomalies]
  subgraph INCIDENT[incident-service]
    API --> M[Incident Manager]
    M --> SOC[SOC Correlator]
    SOC --> POL[Policy Engine]
    POL --> ORCH[Remediation Orchestrator]
    ORCH --> VAL[Recovery Validator]
    M --> DB[(ops incidents et événements)]
    ORCH --> JOB[(ops remediation_actions)]
    JOBAPI[API jobs] --> JOB
    VAL --> DB
  end
  SOC --> L[loki]
  SOC --> PR[prometheus]
  RUN[Runner Ansible] -->|claim| JOBAPI
  RUN -->|result| ORCH
  RUN --> WC[Contrôleur local waf]
  VAL --> W[HTTPS waf vers payment-api]
```

## 3. Déploiement

```mermaid
flowchart TB
  subgraph DEV[Développement Mac M5 ARM64 16 Gio]
    MAC[Docker Desktop VM Linux]
    OM[Ollama natif option de développement]
  end
  subgraph HOST[PC Hôte Windows 10 ou 11 - Docker Desktop WSL2]
    PA[PA mobile Windows - 192.168.137.1]
    subgraph DOCKER[Conteneurs Linux AMD64 ou ARM64 selon machine]
      W[waf et contrôleur local]
      AP[frontend + auth + payment + incident + ML + RAG]
      TECH[postgres + prometheus + grafana + loki + alloy]
      RUN[remediation-runner]
      OH[ollama local si ressources suffisantes]
      W --> AP
      AP --> TECH
      RUN --> W
      AP --> OH
    end
    PA --> W
  end
  ATT[PC Attaquant distinct - aucun composant défensif] -->|PA du groupe uniquement| PA
  CLIENT[Client légitime] --> PA
  subgraph IA[PC IA facultatif]
    OD[Ollama et interface seulement]
  end
  AP -. accès restreint si délestage .-> OD
  MAC -. sources et configuration portables .-> DOCKER
```

## 4. Flux réseau

```mermaid
flowchart LR
  PC[Clients du PA] -->|HTTPS 8443 seul port public| W[waf]
  W -->|edge HTTP 8080| F[frontend]
  W -->|app HTTP 8001| A[auth]
  W -->|app HTTP 8000| P[payment]
  W -->|app HTTP 8002| I[incident]
  W -->|app HTTP 8004| R[RAG]
  A -->|data TCP 5432| DB[(postgres)]
  P -->|data TCP 5432| DB
  I -->|data TCP 5432| DB
  RUN[runner] -->|control HTTP 8002 token dédié| I
  RUN -->|socket Unix privé| W
  I -->|HTTPS 8443 validation| W
  PR[prometheus] -->|observability scrape 5 s| P
  PR -->|observability scrape| I
  ML[ML] -->|HTTP 9090| PR
  ML -->|HTTP 8002 token ML| I
  AL[alloy] -->|HTTP 3100| L[loki]
  I -->|HTTP 3100| L
  I -->|HTTP 9090| PR
  G[grafana loopback hôte 3000] --> PR
  G --> L
  R -->|ai HTTP 11434| O[ollama]
```

## 5. Paiement

```mermaid
sequenceDiagram
  actor U as Client
  participant W as waf
  participant A as auth-service
  participant P as payment-api
  participant DB as postgres
  U->>W: POST /api/auth/login
  W->>A: Identifiants fictifs
  A->>DB: Lire utilisateur et hash
  DB-->>A: Utilisateur actif
  A-->>U: JWT via WAF
  U->>W: POST /api/payments + JWT + Idempotency-Key
  W->>P: Corps validé et request_id
  P->>P: Signature, rôle, schéma
  P->>DB: BEGIN + verrou clé acteur
  P->>DB: Recherche transaction existante
  alt Rejeu identique
    DB-->>P: Même résultat
    P-->>U: 200 SUCCEEDED ou 409 REJECTED via WAF
  else Nouvelle intention
    P->>DB: Verrouiller comptes dans ordre UUID
    P->>P: Propriété, monnaie, soldes
    P->>DB: Débit + crédit + transaction SUCCEEDED ou rejet sans mutation
    P->>DB: COMMIT
    P-->>U: 201 SUCCEEDED ou 409 REJECTED via WAF
  end
```

## 6. Incident

```mermaid
sequenceDiagram
  participant ML as ml-detector
  participant PR as prometheus
  participant I as incident-service
  participant DB as postgres
  participant L as loki
  participant RUN as remediation-runner
  participant W as waf
  ML->>PR: Requêtes features fenêtre 15 s
  PR-->>ML: Mesures réelles
  ML->>ML: Isolation Forest + deux scores anormaux
  ML->>I: POST /internal/anomalies
  I->>DB: Déduplication + incident + événement
  I-->>ML: 202 ou 200 duplicate
  I->>L: Corréler IP et request_id
  L-->>I: Preuves de fenêtre
  I->>DB: CONFIRMED et action PENDING
  RUN->>I: POST /internal/remediation/jobs/claim
  I-->>RUN: Action et bail
  RUN->>W: Ansible vers socket Unix
  W-->>RUN: Reçu configuration appliquée
  RUN->>I: POST /internal/remediation/jobs/id/result
  I->>W: Readiness puis paiement de validation
  I->>PR: Mesures entièrement post-action
  I->>DB: VALIDATION_RESULT et état terminal
```

## 7. Remédiation automatique

```mermaid
flowchart TD
  E[Anomalie persistée] --> C{Preuves SOC fraîches et IP autorisée ?}
  C -->|Non| REJ[REJECTED avec motif]
  C -->|Oui| POL[Politique SC-01 versionnée]
  POL --> JOB[Action durable unique]
  JOB --> RUN[Runner prend bail et fencing token]
  RUN --> CHECK[Validation paramètres et catalogue fermé]
  CHECK --> W[Contrôleur WAF valide config et applique atomiquement]
  W --> ACK{Reçu acquis ?}
  ACK -->|Timeout| REC[Réconcilier action_id avant retry borné]
  REC --> ACK2{Action appliquée ou retry réussi ?}
  ACK2 -->|Non| FAIL[RECOVERY_FAILED]
  ACK2 -->|Oui| V[Valider via WAF et métriques post-action]
  ACK -->|Oui| V
  V --> OK{Readiness, métriques et nouveau paiement cohérent ?}
  OK -->|Oui| DONE[RECOVERED avec transaction_id]
  OK -->|Non| FAIL
  FAIL --> COMP[Compensation ciblée si règle incorrecte]
```

## 8. Machine à états des incidents

```mermaid
stateDiagram-v2
  [*] --> DETECTED
  DETECTED --> ANALYZING
  ANALYZING --> CONFIRMED: preuves et politique valides
  ANALYZING --> REJECTED: insuffisant ou délai analyse
  CONFIRMED --> REMEDIATING: action persistée
  CONFIRMED --> RECOVERY_FAILED: erreur ou deadline
  REMEDIATING --> VALIDATING: reçu WAF vérifié
  REMEDIATING --> RECOVERY_FAILED: essais épuisés ou deadline
  VALIDATING --> RECOVERED: paiement et mesures valides
  VALIDATING --> RECOVERY_FAILED: échec ou timeout
  REJECTED --> [*]
  RECOVERED --> [*]
  RECOVERY_FAILED --> [*]
```

## 9. Pipeline ML

```mermaid
flowchart LR
  PR[prometheus] --> COL[Collecte toutes les 5 s - fenêtre 15 s]
  COL --> Q{8 features fraîches et complètes ?}
  Q -->|Non| MISS[DATA_UNAVAILABLE - abstention]
  Q -->|Oui| PRE[Ordre features + log1p + scaler train]
  PRE --> IF[Isolation Forest figée]
  TRAIN[Session train normale] --> FIT[Apprentissage et manifeste]
  FIT --> IF
  VALID[Session validation indépendante] --> TH[Seuil et anti-flap]
  IF --> TH
  TH --> EVT[Anomaly v1 vers incident-service]
  TEST[Session test gelée] --> EVAL[Precision recall F1 FP et délais]
  IF --> EVAL
```

## 10. Système RAG

```mermaid
flowchart TB
  DOC[Documentation et runbooks autorisés] --> HASH[Manifestes et SHA256]
  HASH --> CH[Chunks par sections 350 tokens overlap 50]
  CH --> EMB[Ollama nomic-embed-text]
  EMB --> IDX[(FAISS IndexFlatIP + métadonnées JSON)]
  OP[Opérateur authentifié] --> API[rag-service LangChain]
  API --> EMB
  API --> RET[Retrieval top 3]
  IDX --> RET
  RET --> REL{Pertinence suffisante ?}
  REL -->|Non| AB[Abstention citée comme telle]
  REL -->|Oui| CTX[Prompt borné et contexte non fiable]
  CTX --> LLM[Ollama qwen2.5 1.5b]
  LLM --> VERIFY[Validation des références]
  VERIFY --> RES[Réponse documentaire sans outil administratif]
```

## 11. Entité-relation

```mermaid
erDiagram
  users ||--o{ accounts : possede
  users ||--o{ transactions : initie
  accounts ||--o{ transactions : debite
  accounts ||--o{ transactions : credite
  incidents ||--o{ incident_events : contient
  incidents ||--o{ remediation_actions : autorise
  remediation_actions o|--o{ remediation_actions : compense
  incidents o|--o{ incidents : parent
  transactions o|--o{ incidents : preuve_reprise
  users {
    uuid id PK
    varchar email UK
    text password_hash
    varchar role
    boolean is_active
    timestamptz created_at
  }
  accounts {
    uuid id PK
    uuid owner_user_id FK
    varchar label
    char currency
    bigint balance_minor
    boolean is_synthetic
    varchar status
    timestamptz created_at
    timestamptz updated_at
  }
  transactions {
    uuid id PK
    uuid actor_user_id FK
    uuid source_account_id FK
    uuid destination_account_id FK
    bigint amount_minor
    char currency
    varchar idempotency_key
    char request_hash
    varchar status
    varchar failure_code
    timestamptz created_at
  }
  incidents {
    uuid id PK
    uuid parent_incident_id FK
    varchar service
    varchar scenario
    char fingerprint
    varchar status
    varchar severity
    inet source_ip
    varchar summary
    varchar policy_version
    integer version
    timestamptz detected_at
    timestamptz updated_at
    timestamptz deadline_at
    timestamptz closed_at
    uuid recovery_transaction_id FK
  }
  incident_events {
    uuid id PK
    uuid incident_id FK
    bigint sequence
    varchar event_type
    timestamptz occurred_at
    timestamptz recorded_at
    uuid request_id
    jsonb payload
  }
  remediation_actions {
    uuid id PK
    uuid incident_id FK
    varchar kind
    varchar status
    inet target_ip
    integer ttl_seconds
    varchar policy_version
    integer attempt
    bigint fencing_token
    uuid lease_token
    uuid related_action_id FK
    timestamptz lease_expires_at
    char request_hash
    jsonb result
    timestamptz created_at
    timestamptz started_at
    timestamptz finished_at
  }
```
