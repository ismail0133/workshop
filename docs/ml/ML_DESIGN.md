# Détection ML — Isolation Forest

EPSI p.5 impose un véritable traitement ML sur données de l’environnement. Isolation Forest est notre choix, pas un algorithme imposé par EPSI. Aucun modèle entraîné ni résultat de performance n’existe encore.

## Données et définition des caractéristiques

Prometheus scrape toutes les 5 s. ML interroge toutes les 5 s une fenêtre glissante de 15 s ; au moins 3 échantillons réels par série. Le rapport secondaire proposait 10 s : nous retenons 15 s pour limiter l’instabilité des taux. Fenêtre post-remédiation distincte de 10 s pour ne pas mélanger avant/après. Un vecteur correspond à un instant UTC et un seul service payment-api.

| Feature | Calcul PromQL conceptuel | Unité / origine |
|---|---|---|
| request_rate | sum(rate(http_requests_total{service="payment-api",traffic="business"}[15s])) | req/s ; compteur middleware hors metrics/health |
| http_5xx_rate | sum(rate(http_requests_total{service="payment-api",traffic="business",status_class="5xx"}[15s])) / request_rate | proportion 0..1 ; 0 si aucun 5xx et trafic présent |
| http_4xx_rate | même calcul status_class="4xx" / request_rate | proportion 0..1 |
| latency_p95_ms | 1000 * histogram_quantile(0.95, sum by(le)(rate(http_request_duration_seconds_bucket{service="payment-api",traffic="business"}[15s]))) | ms, buckets 0.005/0.01/0.025/0.05/0.1/0.25/0.5/1/2/5 |
| cpu_usage_percent | 100 * rate(process_cpu_seconds_total{job="payment-api"}[15s]) / payment_cpu_limit_cores | pourcentage du quota explicite 0.75 cœur, borné 0..100 |
| memory_usage_percent | 100 * process_resident_memory_bytes{job="payment-api"} / payment_memory_limit_bytes | RSS du processus / limite explicite conteneur 384 MiB, 0..100 |
| active_requests | avg_over_time(http_requests_in_progress{service="payment-api"}[15s]) | moyenne, flottant admis |
| payment_failure_rate | rate(payment_attempts_total{outcome="failure"}[15s]) / sum(rate(payment_attempts_total[15s])) | proportion sur tentatives de paiement, client légitime actif |

Les deux métriques de limites sont des gauges de configuration exportées par Payment API, leur valeur doit être égale aux quotas Compose. CPU/RSS mesurent le processus API, **pas tout le Mac ni tous les conteneurs**. Un worker par API conserve cette définition simple. Les exceptions/timeout de tentative client ne sont pas toutes visibles dans l’API : conserver aussi les journaux du client de référence dans les essais, sans les injecter artificiellement dans les features.

## Préparation

Valider timestamp, service, ensemble de features ordonné et unicité (run_id,timestamp). Compteurs initialisés à zéro pour toutes les classes attendues ; absence de série != zéro. Une série absente, stale >10 s, NaN/Inf ou moins de 3 scrapes → fenêtre invalidée, DATA_UNAVAILABLE, aucune inférence ni remédiation. Si aucun paiement dans la fenêtre, payment_failure_rate est inconnu : le protocole maintient le client normal ; ne pas inventer 0. Rejeter fenêtres de démarrage/restart (détection compteur reset). Aucun forward-fill d’erreur ou latence.

Pipeline sérialisé : ordre fixe des 8 features, log1p pour request_rate/latency/active_requests, StandardScaler appris sur train seulement (option de stabilité documentée, pas une nécessité théorique pour l’arbre), IsolationForest(n_estimators=100,max_samples=min(256,n_train),contamination='auto',random_state=42,n_jobs=1). Sauver versions Python/sklearn/numpy, schéma features, hash données et artefact. Ne jamais charger un pickle/joblib reçu du réseau ; artefact interne vérifié par SHA256.

## Entraînement et évaluation sans fuite

Constituer trois sessions temporelles séparées : train normal 30 min (360 points à 5 s), validation 10 min avec trafic normal varié et essais autorisés étiquetés, test 10 min comprenant nouvelles périodes normales et SC-01. Diversifier charge normale, utilisateurs fictifs, périodes calmes et paiements ; ne pas collecter uniquement une ligne répétée. Prévoir délai de purge ≥15 s entre splits pour les fenêtres chevauchantes. Les essais de test ne servent jamais au réglage du seuil.

Labels d’évaluation issus du journal de scénario (début/fin, dégradation réellement constatée), pas de la prédiction elle-même. Étiqueter séparément trafic anormal et dégradation : une charge sans effet métier n’est pas une preuve de reprise. Séparer datasets par run_id et timestamp ; conserver dataset.csv + manifest.json + split manifest. Pas de séparation aléatoire de fenêtres voisines.

`decision_function` : plus bas = plus atypique. Seuil initial 0, ajusté **sur validation uniquement** pour une cible de faux positifs ≤1/10 min en conditions normales. Déclenchement après 2 scores consécutifs sous seuil ; anti-flap et déduplication d’incident ensuite. Sauver seuil, courbe de scores et décisions brutes pour expliquer ce post-traitement : le détecteur reste un modèle entraîné, pas une règle de seuil sur CPU.

Sur test gelé : matrice TP/FP/FN/TN, precision/recall/F1 (indéfinis explicitement si dénominateur nul), faux positifs/heure, latence p50/p95 depuis la première dégradation. Cibles expérimentales : recall ≥0.8, precision ≥0.8 et détection ≤15 s sur SC-01 ; aucun score ne sera annoncé sans taille d’échantillon et preuve. Trois exécutions indépendantes finales sur Windows. Si objectifs manqués, analyser features/seuil/dérive, réentraîner puis **nouveau** test indépendant. Une règle if/else seule n’est pas une alternative acceptable.

## Inférence et pannes

Chargement unique au démarrage, readiness false si modèle ou manifeste absent. Requêtes Prometheus timeout 2 s, traitement mémoire borné ; vérifier modèle contre feature_schema_version. Événement Anomaly v1 et ack idempotent définis dans API_CONTRACTS. Aucun champ source_ip décidé par ML ; le SOC le déduit des logs. Un modèle Mac n’est pas automatiquement valable sous Windows : baseline/quota/latences doivent être comparés, idéalement réentraîner sur cible. Toute dérive de version ou quota invalide la calibration.
