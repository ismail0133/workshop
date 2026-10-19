# Contrats API — v0.1

Spécification machine : [openapi.json](openapi.json), OpenAPI 3.1 ; événements : [events.schema.json](events.schema.json), JSON Schema 2020-12. Les endpoints auth/payment sont implémentés en phase 1 ; incident/RAG restent à implémenter. Voir PHASE1_CONTRACT_CHANGES.md. Le préfixe `/api` est conservé au proxy. Aucun endpoint de commande privilégiée n’est public.

## Conventions communes

JSON UTF-8, UUID canoniques, horodatage RFC3339 UTC `Z`, montants **entiers** en centimes EUR. Rejet 422 pour champ inconnu, valeur hors borne, UUID invalide ou corps absent. Réponses d’erreur `{code,message,request_id}`, sans stack ni secrets. 401 token absent/invalide/expiré ; 403 rôle incompatible ; 404 ressource absente **ou hors périmètre** ; 429 quota (Retry-After secondes) ; 503 dépendance indisponible ; 504 génération RAG trop lente. Taille corps maximum 16 KiB. Le WAF génère X-Request-ID et les API le reflètent ; appels internes génèrent leur propre identifiant.

Listes : limit défaut 20, max 100 ; cursor opaque signé base64url portant dernier couple temps/id et filtre, rejet 422 si invalide. Comptes : tri id ; transactions/incident : date descendante puis id ; événements : sequence ascendante ; actions : created_at ascendante puis id. next_cursor null à la fin. Filtrage par utilisateur **avant** pagination. Pas de recherche globale de comptes ni d’API d’administration bancaire dans le MVP.

JWT RS256 sub/role/iss/aud/exp, validité 900 s. USER et VALIDATOR n’accèdent qu’aux ressources autorisées. OPERATOR ne peut pas payer avec ses droits de supervision. Health/metrics sont internes sans données sensibles ; ils ne passent pas par l’ingress sauf readiness Payment relayée par WAF pour le validateur. Les scopes internes sont authentifiés par secrets distincts X-Service-Token et ne sont jamais disponibles dans React.

## Endpoints et erreurs métier

| Service / endpoint | Entrée | Réponse et codes | Autorisation |
|---|---|---|---|
| auth POST /api/auth/login | email, password | 200 LoginResponse ; 401 INVALID_CREDENTIALS ; 422 ; 429 ; 503 | Public, rate limit 5/min/IP |
| auth GET /api/auth/me | Bearer | 200 User ; 401 ; 503 | Tout rôle utilisateur actif |
| auth GET /health | Aucun | 200 Health / 503 | Réseau interne, teste DB |
| payment GET /api/accounts | limit,cursor | 200 AccountPage ; 401/403/422/429/503 | USER/VALIDATOR, ses comptes |
| payment GET /api/accounts/{id} | UUID id | 200 Account ; 404 ; erreurs communes | Propriétaire |
| payment POST /api/payments | PaymentRequest + Idempotency-Key 8..128 chars | 201 Payment ; 200 replay ; 409 rejet/conflit ; 404 ; 422 ; erreurs communes | USER source à soi ; VALIDATOR deux synthetic |
| payment GET /api/payments | limit,cursor | 200 PaymentPage ; erreurs communes | Transactions dont compte source ou destination lui appartient |
| payment GET /api/payments/{id} | UUID id | 200 Payment ; 404 ; erreurs communes | Même filtre de propriété |
| payment GET /health/live | Aucun | 200 Health | Interne, processus |
| payment GET /health/ready | Aucun | 200 Health / 503 | Interne et relais WAF, DB/schéma prêts |
| payment GET /metrics | Aucun | 200 texte Prometheus | Interne seulement |
| incident POST /internal/anomalies | Anomaly complet | 202 AnomalyAck ; 200 duplicate ; 409 EVENT_ID_CONFLICT ; 422 ; 401/403/429/503 | ML token anomaly:write |
| incident GET /api/incidents | limit,cursor | 200 IncidentPage ; erreurs communes | OPERATOR |
| incident GET /api/incidents/{id} | UUID id | 200 Incident ; 404 ; erreurs communes | OPERATOR |
| incident GET /api/incidents/{id}/events | UUID id, limit,cursor | 200 IncidentEventPage ; 404 ; erreurs communes | OPERATOR |
| incident GET /api/incidents/{id}/actions | UUID id, limit,cursor | 200 ActionPage ; 404 ; erreurs communes | OPERATOR |
| incident POST /internal/remediation/jobs/claim | Aucun corps | 200 Job ou 204 vide ; 401/403/429/503 | Runner token, 1 job, bail 15 s |
| incident POST /internal/remediation/jobs/{id}/result | id action, ActionResult | 200 Action ; 409 STALE_LEASE/RESULT_CONFLICT ; 401/403/404/422/503 | Runner, bail courant |
| rag POST /api/assistant/chat | message 1..2000 caractères | 200 ChatResponse ; 422/429/503/504 ; 401/403 | OPERATOR, 1 génération simultanée |
| rag GET /api/assistant/health | Bearer | 200 Health / 503 ; 401/403 | OPERATOR, index/Ollama |

Les schémas exhaustifs (types, champs requis, bornes) sont dans OpenAPI. Les endpoints santé des autres composants partagent Health avec leur port du SERVICE_CATALOG ; ils ne représentent pas de nouvelles routes publiques. ML n’expose aucune API d’inférence utilisateur.

## Paiement et idempotence

Requête : `{"source_account_id":"10000000-0000-4000-8000-000000000010","destination_account_id":"10000000-0000-4000-8000-000000000011","amount_minor":100,"currency":"EUR"}` avec une clé nouvelle. Deux comptes distincts, mêmes unités EUR. Hash SHA256 du JSON canonique trié des quatre champs. Résultat 201 après commit, status SUCCESS et failure_code null. Une répétition identique renvoie 200 et le même id ; un rejet métier est rejoué en 409 avec le même Payment REJECTED. Clé réutilisée avec autre corps = Error IDEMPOTENCY_CONFLICT. Aucun nouveau débit lors d’un retry.

409 REJECTED : INSUFFICIENT_FUNDS, ACCOUNT_FROZEN ou BALANCE_LIMIT. 404 masque compte absent/non autorisé. 422 refuse montant nul/négatif/flottant et source=destination (contrainte sémantique non exprimable par simple type OpenAPI). Le validateur doit refuser transfert vers un compte non synthetic même s’il connaît son id.

## Événements et livraison

Anomaly v1 contient toutes les 8 caractéristiques et la fenêtre réelle. `anomaly.example.json` contient des **valeurs fictives d’illustration** et un hash nul, jamais utilisables comme preuve ou modèle. score = decision_function IsolationForest (bas = atypique). Version de modèle et hash doivent correspondre à l’artefact chargé. Un timestamp >5 s dans le futur ou >30 s dans le passé rend 422 STALE_EVENT ; un doublon déjà accepté est reconnu avant ce contrôle de fraîcheur. Fenêtre 15 s, end >= start et end <= timestamp.

Transport ML → incident : au moins une fois, retries bornés 1/2/4 s, même event_id et même corps. Après épuisement, conserver une petite outbox locale et signaler l’échec ; les vieux événements sont archivés sans déclencher une nouvelle correction. L’ack signifie persistance, pas remédiation. Les autres événements sont locaux au journal durable : enveloppe schema_version/event_id/incident_id/timestamp/event_type/payload. Lors de lecture API, mapping timestamp→occurred_at, event_id→id ; recorded_at/sequence sont attribués par Incident Service. ANOMALY_DETECTED garde le message complet en payload. Les formats SOC/état/action/validation/absence de données sont discriminés dans events.schema.json.

Résultats runner : une soumission répétée identique après succès renvoie la même Action ; corps contradictoire rend 409. SUCCEEDED requiert exit_code=0, controller_receipt et config_sha256 ; sinon 422. Après expiration du bail, réconcilier le contrôleur avant nouvel essai. Aucune réponse API ne peut déclarer RECOVERED sans la procédure du validateur.

## Assistant

Réponse sans document pertinent : 200, grounded=false, citations=[], réponse explicite d’abstention. Panne Ollama/index absent : 503 ; délai 30 s dépassé : 504. Ne pas fabriquer une réponse de secours ni une citation. Aucun historique conversationnel persisté dans le MVP ; chaque requête est autonome. Les références sont des chemins autorisés de documentation, jamais des chemins arbitraires demandés par l’utilisateur.


Mise à jour phase 1 : rôles USER/OPERATOR/ADMIN (VALIDATOR technique conservé), paiement SUCCESS. Voir `docs/api/PHASE1_CONTRACT_CHANGES.md` depuis la racine. Les descriptions de phases futures restent des cibles.
