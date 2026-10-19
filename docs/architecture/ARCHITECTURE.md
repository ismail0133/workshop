# Architecture de référence — phase 0

Version 0.1, 19 octobre 2026. **Conception, sans implémentation métier.** Les exigences EPSI sont référencées dans [la matrice](../REQUIREMENTS_TRACEABILITY.md). Les choix ci-dessous sont des décisions d’équipe, non des prescriptions supplémentaires attribuées à l’EPSI.

## Besoin et périmètre

Une entreprise financière fictive doit conserver un service de transfert utilisable après une perturbation contrôlée. La preuve attendue (EPSI p.3) est un nouveau paiement cohérent après une correction automatique ; le redémarrage d’un conteneur ne suffit pas. Le laboratoire traite exclusivement des identités, comptes et montants fictifs.

Le MVP conserve les cinq piliers (EPSI p.2–5) : paiement/authentification/dashboard React, Compose/Ansible/Prometheus/Grafana/Loki, ML réel et RAG Ollama/LangChain, WAF/SOC/SOPS/durcissement/scénario externe, EBIOS/PCA-PRA/NIS2-DORA. Hors MVP facultatif : plusieurs attaques, Kafka, Kubernetes, microservices supplémentaires, haute disponibilité et fraude bancaire industrielle.

## Décisions

| ID | Décision | Justification et conséquence |
|---|---|---|
| ADR-01 | Six composants applicatifs : frontend, payment-api, auth-service, incident-service, ml-detector, rag-service | Frontend statique ; cinq processus Python. Pas de service SOC indépendant. |
| ADR-02 | PostgreSQL unique, schémas `auth`, `bank`, `ops`, rôles séparés | Moins de mémoire ; un point de défaillance accepté. Les FK interschémas impliquent migrations coordonnées. |
| ADR-03 | Incident Service contient Incident Manager, SOC Correlator, Policy Engine, Remediation Orchestrator et Recovery Validator | Les quatre modules demandés sont conservés, la corrélation ajoutée au même processus. Un worker durable traite la file PostgreSQL ; pas de tâche volatile dépendant d’une requête HTTP. |
| ADR-04 | Isolation Forest sur métriques Prometheus, aucune décision privilégiée par LLM | Séparation détection/cause/action. Politique déterministe après preuve SOC. |
| ADR-05 | WAF Nginx + ModSecurity + OWASP CRS, base officielle à figer par digest | Filtrage applicatif exigé. Adaptateur de contrôle local à développer ; compatibilité et visibilité IP sont des risques bloquants à tester tôt. |
| ADR-06 | Ansible dans un runner Linux isolé | Ni socket Docker, ni root hôte. Catalogue fermé ; contrôle du seul WAF par socket Unix. |
| ADR-07 | Alloy collecte des fichiers JSON via volumes séparés en lecture seule | Un collecteur explicite est nécessaire pour alimenter Loki. Aucun accès à l’API Docker. |
| ADR-08 | Ollama natif Mac pour développement, conteneur CPU sur PC Hôte Windows ou PC IA dédié | Le PC IA ne reçoit que modèle/interface ; RAG et FAISS restent sur le PC Hôte. Modèle 1.54B, donc sous le plafond EPSI 8B. |
| ADR-09 | HTTP REST interne, HTTPS au WAF, JWT RS256 courts | Ports internes non publiés. Réseaux Compose ne remplacent pas authentification/RBAC. |
| ADR-10 | Paiements en centimes EUR, verrouillage pessimiste ordonné, idempotence persistée | Aucun flottant, solde jamais négatif, résultat rejouable. |
| ADR-11 | SOPS + age | Alternative explicitement autorisée p.5, plus légère que Vault pour quatre jours. Clé hors dépôt ; aucun secret utilisable dans les exemples. |

## Chaîne de confiance et reprise

Le navigateur passe exclusivement par WAF pour `/`, `/api/auth/*`, `/api/accounts*`, `/api/payments*`, `/api/incidents*` et `/api/assistant/*`. WAF refuse `/internal/*` et `/metrics`. Les JWT sont validés localement par clé publique dans chaque API : aucun appel auth obligatoire par paiement. Auth possède seule la clé de signature. Les utilisateurs `user` voient leurs comptes et transactions ; les `operator` voient incidents et assistant. Le `validator` est un compte technique limité à deux comptes synthétiques.

Le ML envoie une anomalie à `/internal/anomalies`. Incident Service interroge Loki sur la même fenêtre, vérifie une source unique autorisée et la dégradation. Un événement isolé ne suffit pas. Si la politique SC-01 est satisfaite, une action durable `BLOCK_SOURCE_IP` est créée. Runner récupère un bail de travail, exécute un playbook immuable, contacte le contrôleur Unix du WAF, puis renvoie le résultat. Le contrôleur vérifie l’IP, le TTL, le fencing token, teste la configuration et recharge atomiquement le WAF. Ce contrôleur est un adaptateur dans le conteneur WAF, pas une API publique ni un microservice métier.

Recovery Validator teste le **chemin WAF**, pas seulement Payment API interne : readiness, métriques post-action puis nouveau paiement unique et lecture de sa confirmation. Toute panne d’observation empêche RECOVERED. Les incidents terminaux restent immuables ; une rechute crée un nouvel incident lié par `parent_incident_id`.

## Déploiement et séparation

14 composants d’exécution au maximum : 6 applicatifs + postgres, prometheus, grafana, loki, waf, ollama, alloy, remediation-runner. Sur Mac, Ollama natif remplace son conteneur. Les composants IA lourds ne sont chargés qu’à la demande. Un seul replica par service pour la démonstration.

Réseaux prévus : `edge` (WAF/frontal), `app` (WAF/API), `data` (trois API/Postgres), `observability` (scrapes/logs/ML/SOC), `control` (incident/runner), `ai` (RAG/Ollama). Pas de publication DB, Prometheus, Loki, runner, Ollama ni API directe. Grafana disponible uniquement sur 127.0.0.1:3000 sur l’hôte ; le dashboard React est la supervision accessible au jury via WAF. Les flux exacts figurent dans DATA_FLOWS.md.

Le fichier Compose de phase 0 contient seulement le socle technique configurable et une extension `x-planned-services` décrivant la cible. Il ne prétend pas démarrer l’application inexistante. Les configurations devront être complétées et figées en phases 1–8.

## Exigences, recommandations, hypothèses

**Obligatoire EPSI** : contraintes p.3–8, dont PC Hôte Windows, PA Windows, PC Attaquant distinct, reprise autonome et cinq piliers.
**Décisions** : ADR ci-dessus, REST, schémas PostgreSQL, SC-01, seuils initiaux et budget mémoire.
**Facultatif** : PC IA, 32 Go RAM, seconde attaque, mesures de sécurité supplémentaires après MVP.
**À confirmer** : poste Windows/virtualisation/admin, numéro de groupe, personnes, autorisation réseau du coach, IP réellement observée après Docker Desktop, image WAF multiarch, budget RAM mesuré, RTO et qualité ML/RAG. Aucun de ces points n’est considéré validé par ce document.


Mise à jour phase 1 : rôles USER/OPERATOR/ADMIN (VALIDATOR technique conservé), paiement SUCCESS. Voir `docs/api/PHASE1_CONTRACT_CHANGES.md` depuis la racine. Les descriptions de phases futures restent des cibles.
