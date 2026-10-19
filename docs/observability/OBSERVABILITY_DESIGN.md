# Observabilité

Prometheus (métriques), Grafana (visualisation), Loki (logs) sont obligatoires EPSI p.4. Alloy est notre collecteur explicite : fichiers JSON de volumes producteurs RO, expédition vers Loki. Cette méthode est documentée par [Grafana Alloy](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/). Aucun accès Docker socket.

## Instrumentation

Tous les compteurs exposent `service`, `route` (template, jamais id), `method`, `status_class`, `traffic` business/health. Ne pas mettre user_id, IP, JWT, request_id, incident_id ou montant en labels Prometheus.

| Mesure | Type | Source |
|---|---|---|
| http_requests_total | Counter | Middleware API, classes 2xx/4xx/5xx initialisées |
| http_request_duration_seconds | Histogram | API, buckets du ML_DESIGN |
| http_requests_in_progress | Gauge | API, incrément/décrément finally |
| payment_attempts_total{outcome} | Counter | API, succès/rejet/exception traitée ; init success/failure |
| payment_cpu_limit_cores / payment_memory_limit_bytes | Gauge | Config/quota explicitement alignés |
| process_cpu_seconds_total / process_resident_memory_bytes | Counter/Gauge | Processus Python |
| ml_decision_score / ml_inference_duration_seconds | Gauge/Histogram | ML réel |
| ml_windows_total{status} / ml_model_info{version} | Counter/Gauge | ML, invalid/valid et version |
| incidents_total{status} / remediation_actions_total{kind,result} | Counter | Worker incident ; éviter double incrément au retry |
| recovery_duration_seconds | Histogram | Première dégradation connue → validation |
| waf_requests_total{decision} / waf_active_blocks | Counter/Gauge | Adaptateur WAF, preuve réelle ; pas de compteur fictif |
| up / scrape_duration_seconds | Gauge | Prometheus |

Scrape/evaluation 5 s, timeout 2 s. Health/live ne compte pas comme trafic métier. Pour l’infrastructure, quotas/volumes Docker sont mesurés séparément lors des essais via outils hôte ; pas de faux dashboard « CPU Mac » à partir du seul processus API.

## Journaux

Une ligne JSON par événement : timestamp UTC, level, service, event_type, request_id, route, method, status_code, duration_ms ; pour WAF source_ip TCP, rule_id, action ; pour incident event_id/incident_id/action_id/state. Aucun password, token, Authorization, cookie, corps login ou donnée bancaire réelle. Normaliser les logs ModSecurity dans l’adaptateur WAF en conservant référence au journal brut expurgé ; ne pas supposer que tous les formats d’image sont déjà JSON.

Chaque producteur a son propre volume, pas de RW partagé entre applications. Alloy monte tous ces volumes RO ; conserve ses positions dans un volume RW séparé. Rotation producteur 10 MiB × 5 ; Loki 72 h (compactor actif), Prometheus 48 h et max 1 GiB. Quota disque cible logs 2 GiB, surveillance avant saturation. Exporter les preuves de chaque essai avant expiration. Si Alloy/Loki tombe, les fichiers permettent un rattrapage borné ; si rotation a perdu des données, marquer le trou et suspendre toute confirmation sans preuve.

## Alertes et tableaux de bord

| Dashboard | Panneaux réels | Décision rendue possible |
|---|---|---|
| System Health | up, readiness, processus CPU/RSS, freshness scrapes | Identifier composant indisponible |
| Payment Performance | débit, p95, 4xx/5xx, tentatives succès/échec | Mesurer la perturbation et le retour |
| Security Events | logs WAF, source, règles CRS, SOC evidence | Justifier source et filtrage |
| AI Detection | score/seuil/version, fenêtres invalides, alertes | Examiner détection et qualité des données |
| Recovery Timeline | états depuis logs incident, actions, durée, transaction preuve | Vérifier la chaîne zéro-touch |

React interroge les API incidents/events/actions toutes les 2 s (arrêt en onglet masqué), affiche données de banque et chronologie ; les métriques techniques détaillées restent dans Grafana. Pas d’intégration publique directe à Loki/Prometheus. Aucun panneau statique avec valeurs inventées.

Règles initiales : service up=0 pendant 10 s ; absence de scrapes 15 s ; 5xx >5 % sous trafic pendant 10 s ; p95>500 ms pendant 10 s ; fenêtre ML invalide ; action échouée ou incident RECOVERY_FAILED. Les alertes Prometheus aident l’exploitation ; elles ne remplacent pas le détecteur ML et ne déclenchent pas seules le runner. Alertmanager non requis dans ce MVP : les règles sont consultables via Prometheus et Grafana.

Les fichiers initiaux fournissent scrapes, règles et provisioning de sources. Les dashboards et exporters applicatifs sont des travaux futurs (phases 3/5), sans affichage factice en phase 0.
