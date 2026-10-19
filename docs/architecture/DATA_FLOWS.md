# Flux de données et réseau

Les ports sont des ports conteneur sauf mention « hôte ». Les réseaux sont des frontières de réduction d’exposition ; les autorisations applicatives restent nécessaires. Tous les logs utilisent UTC et un `request_id` généré au WAF (en-tête client écrasé), relayé jusqu’à PostgreSQL via le journal applicatif. `incident_id`, `action_id`, `event_id` sont des UUID ; jamais des labels Prometheus à haute cardinalité.

| Flux | Source → destination | Transport / chemin | Données / contrôle |
|---|---|---|---|
| F01 | Navigateur ou PC Attaquant → WAF | HTTPS hôte 8443 → 8443 | TLS CA de laboratoire ; IP TCP observée ; cible unique du PA |
| F02 | WAF → frontend | HTTP 8080 `/` | Fichiers statiques, aucun secret |
| F03 | WAF → auth-service | HTTP 8001 `/api/auth/*` | Login/jeton ; corps de login exclu des logs |
| F04 | WAF → payment-api | HTTP 8000 `/api/accounts*`, `/api/payments*` | Bearer JWT, Idempotency-Key, données fictives |
| F05 | WAF → incident-service | HTTP 8002 `/api/incidents*` | JWT operator, lecture seule |
| F06 | WAF → rag-service | HTTP 8004 `/api/assistant/*` | JWT operator, question documentaire |
| F07 | auth/payment/incident → postgres | TCP 5432, réseau data | Un rôle par schéma, aucun superutilisateur applicatif |
| F08 | Prometheus → API/ML/runner/WAF | HTTP `/metrics` ports catalogue | Scrape 5 s ; pas de credentials utilisateur |
| F09 | Services et WAF → Alloy | Fichiers JSON, volumes dédiés | Un producteur par volume ; Alloy RO ; rotation 10 MiB × 5 |
| F10 | Alloy → Loki | HTTP 3100 `/loki/api/v1/push` | Flux internes, pas de publication, label service/env |
| F11 | Grafana → Prometheus/Loki | HTTP 9090/3100 | Requêtes de visualisation ; Grafana hôte loopback seulement |
| F12 | ml-detector → Prometheus | HTTP 9090 `/api/v1/query` | 8 caractéristiques, cadence 5 s, fenêtre 15 s |
| F13 | ml-detector → incident-service | HTTP 8002 `/internal/anomalies` | Token interne scope anomaly:write ; retries idempotents |
| F14 | incident-service → Loki/Prometheus | HTTP 3100/9090 query APIs | Corrélation logs, preuves, validation ; requêtes paramétrées bornées |
| F15 | runner → incident-service | HTTP 8002 `/internal/remediation/jobs/claim` et `/{id}/result` | Token runner spécifique ; bail et fencing token |
| F16 | runner → contrôleur WAF | HTTP sur `/run/waf-control/control.sock` | Socket Unix partagé uniquement entre ces deux conteneurs ; pas de réseau de gestion |
| F17 | Recovery Validator → WAF | HTTPS 8443, `/health/ready`, `/api/payments` | Compte synthétique validator, CA validée, requête traverse le filtre |
| F18 | rag-service → Ollama | HTTP 11434 `/api/embed`, `/api/chat` | Local au réseau ai ; aucun droit de remédiation |
| F19 | RAG → documents/FAISS | Fichiers RO | Index créé hors requête, manifeste SHA-256 ; pas de désérialisation pickle externe |
| F20 | Opérateur hôte → Grafana | HTTP 127.0.0.1:3000 | Login Grafana, pas d’anonyme |

`GET /health/ready` du WAF relaie la readiness Payment API pour le validateur ; aucun détail DB public. Le chemin n’est pas contourné par un accès direct au backend. Les API internes écoutent uniquement dans Compose et refusent tout token utilisateur sur `/internal/*`.

## Implantation Windows obligatoire

PC Hôte : Wi-Fi campus pour les usages autorisés ; PA mobile Windows `RESILIENCE-G<n>`, réseau de référence 192.168.137.0/24, hôte 192.168.137.1. Publier WAF sur **l’adresse du PA uniquement**, filtrer pare-feu Windows pour le groupe. Ne pas publier sur 0.0.0.0. PC Attaquant connecté uniquement au PA du groupe, sans composants défensifs et sans cible Internet/campus. Les adresses réelles sont relevées au démarrage ; aucune substitution automatique de cible.

Docker Desktop peut modifier l’adresse source visible par le conteneur. Condition bloquante SC-01 : distinguer les IP de deux clients réels dans les logs WAF. Ne jamais faire confiance à `X-Forwarded-For` fourni par un client. Si le NAT masque les sources, diagnostic avec coach puis ajustement documenté de l’ingress Windows ; aucune règle ne doit bloquer une passerelle commune. Ne pas déclarer le filtrage ciblé fonctionnel avant ce test.

PC IA facultatif : seul Ollama et son interface, port 11434 autorisé uniquement depuis PC Hôte par pare-feu. Pour ce lien non authentifié par Ollama, ajouter tunnel authentifié/TLS ou proxy d’accès limité ; aucun accès du PC Attaquant. Aucune base/FAISS/RAG/métrique ne migre sur ce poste.

## Données, conservation et défaillances

Paiements validés et événements d’incident persistent dans PostgreSQL. Les métriques sont retenues 48 h, logs Loki 72 h, preuves sélectionnées exportées dans le dossier d’essai avant rotation. Pas de mots de passe, JWT, clés ou corps de paiement dans les logs. Un trou de collecte est DATA_UNAVAILABLE, pas une preuve d’attaque. Les transactions ne dépendent pas de la disponibilité du RAG ou de Loki ; la remédiation exige des preuves fraîches et s’abstient en leur absence.
