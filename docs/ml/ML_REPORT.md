# Rapport ML — données, préparation, modèle, résultats, limites (ML-01 à ML-03)

Version 1.0 — 21 octobre 2026. Ce rapport couvre EPSI p.5 : un détecteur d'anomalies par apprentissage automatique, raccordé à la supervision, dont le dossier explique les données, leur préparation, le modèle, les résultats et les limites. Deux détecteurs coexistent : (A) un détecteur sur les métriques Prometheus (§1 à §6, **jamais essayé sur l'environnement réel**) et (B) un détecteur par User-Agent sur les journaux du WAF, qui alimente `blocklist.txt` (§7, **premiers résultats réels, non probants**). Le §7 est la partie à lire en premier.

## 1. Ce qui est implémenté

| Élément | Fichier (`services/ml-detector/ml_app/`) | État |
|---|---|---|
| 8 caractéristiques, requêtes PromQL exécutables, validation de fenêtre | `features.py`, `prom.py` | Implémenté ; syntaxe PromQL validée par un parseur ; **jamais exécuté contre un vrai Prometheus** |
| Collecte réelle (cadence 5 s), étiquetage par journal de scénario | `cli.py collect`, `cli.py label` | Implémenté ; non exécuté sur l'environnement réel |
| Partition temporelle sans fuite, purge ≥ 15 s | `dataset.py` | Implémenté et testé |
| Pipeline `log1p` → `StandardScaler` → `IsolationForest` (100 arbres, `random_state=42`) | `model.py` | Implémenté et testé |
| Seuil calibré sur la validation seule | `model.py: calibrate_threshold` | Implémenté et testé |
| Évaluation sur test gelé (TP/FP/FN/TN, précision, rappel, F1, latence, fausses alertes) | `evaluate.py` | Implémenté et testé |
| Artefact vérifié (SHA-256 du manifeste **et** empreinte épinglée, versions) | `model.py: load_verified` | Implémenté et testé |
| Règle de déclenchement (2 fenêtres consécutives, anti-flap, cooldown 60 s) | `gate.py` | Implémenté et testé |
| Événement Anomaly v1, envoi idempotent, retries 1/2/4 s, outbox | `detector.py`, `outbox.py` | Implémenté ; conforme au schéma JSON ; testé contre un faux Incident Service |
| Santé et métriques (`ml_decision_score`, `ml_windows_total{status}`, `ml_model_info`) | `main.py`, `metrics.py` | Implémenté et testé |

Incident-service n'existant pas encore, le détecteur fonctionne en mode **dry-run** (`INCIDENT_URL` vide : l'anomalie est journalisée, pas envoyée). Le contrat d'envoi est testé avec un récepteur simulé.

## 2. Données et préparation

- **Source** : 8 caractéristiques calculées sur une fenêtre glissante de 15 s toutes les 5 s à partir de Prometheus (service `payment-api`, trafic métier) : débit, taux de 5xx, taux de 4xx, latence p95, CPU (% du quota 0,75 cœur), mémoire (% de 384 Mio), requêtes en cours, taux d'échec des paiements.
- **Fenêtre invalide = pas d'inférence** (`DATA_UNAVAILABLE`) : cible arrêtée, moins de 3 scrapes, série périmée de plus de 10 s, remise à zéro d'un compteur, aucun trafic, aucune tentative de paiement, valeur NaN/Inf. Aucune valeur n'est reportée ni remplacée par zéro.
- **Sessions** : train 30 min de trafic normal, validation 10 min (normal varié + essais étiquetés), test 10 min (nouvelles périodes normales + SC-01). Découpage **par session et par temps**, jamais aléatoire ; purge ≥ 15 s entre splits ; un `run_id` n'appartient qu'à un split. Le split `train` refuse toute ligne dégradée.
- **Étiquettes** : issues du journal du scénario (début et fin de la dégradation réellement constatée), **jamais de la prédiction**.
- **Pipeline** : `log1p` sur le débit, la latence et les requêtes en cours, standardisation apprise sur le train seul, puis Isolation Forest (`max_samples = min(256, n_train)`, `contamination='auto'`).
- **Seuil** : `decision_function` (bas = atypique). Seuil initial 0, abaissé sur la **validation** jusqu'à ≤ 1 déclenchement par 10 min en trafic normal. Le test ne sert jamais au réglage.

## 3. Pourquoi ce modèle

Isolation Forest est non supervisé : il apprend le normal et signale ce qui s'en écarte, sans exiger d'exemples d'attaque ; il est léger (CPU, quelques Mio) et s'exécute sur le PC Hôte. Une règle `if cpu > x` n'est pas une alternative acceptable (EPSI p.5). Le modèle **déclenche l'investigation** ; la cause et l'action sont décidées par la politique SOC déterministe (arbitrage D3 du document de recommandations à la direction, pilier gouvernance).

## 4. Résultats : test de bout en bout sur données SYNTHÉTIQUES

> ⚠ Ces chiffres valident que le **pipeline fonctionne** (collecte simulée → entraînement → calibrage → évaluation). Ils ne démontrent **aucune** performance sur l'environnement réel : les données sont fabriquées par `ml_app/synthetic.py` (attaque simulée à dérive progressive). Les manifestes de modèle portent `synthetic_training_data: true`.

Cinq graines indépendantes, test gelé de 120 fenêtres (35 dégradées, 2 épisodes), reproductibles avec `python -m ml_app.cli synth --seed N` puis `train` :

| Graine | TP | FP | FN | TN | Précision | Rappel | Fausses alertes (après 2 fenêtres) | Épisodes manqués | Latence p50 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 35 | 8 | 0 | 77 | 0,81 | 1,00 | 0 | 0/2 | 10 s |
| 2 | 35 | 5 | 0 | 80 | 0,88 | 1,00 | 0 | 0/2 | 10 s |
| 3 | 35 | 10 | 0 | 75 | 0,78 | 1,00 | 1 | 0/2 | 7,5 s |
| 4 | 35 | 4 | 0 | 81 | 0,90 | 1,00 | 0 | 0/2 | 10 s |
| 5 | 35 | 10 | 0 | 75 | 0,78 | 1,00 | 2 | 0/2 | 10 s |

Lecture honnête :
- Le **rappel** est parfait parce que l'attaque simulée est franche ; un vrai SC-01, plus bruité, sera plus difficile.
- La **précision** moyenne (0,83) est proche de la cible de 0,8 mais **instable d'une graine à l'autre**. Les faux positifs se concentrent sur les rafales bénignes et sur le début de la montée en charge.
- Sur deux graines (3 et 5), les fausses alertes dépassent la cible de ≤ 1 par 10 min (1 à 2 pour environ 7 min de trafic normal) : **un seuil calibré sur une validation courte ne se généralise pas toujours**. Leçon pour l'essai réel : allonger la validation et le trafic normal varié.
- La latence est exprimée à pas de 5 s ; elle ne tient pas compte du délai de remplissage de la fenêtre de 15 s côté Prometheus, qui s'ajoute en réel (PCA/PRA §6).

## 5. Ce qu'il reste à produire sur le PC Hôte (obligatoire pour ML-01 à ML-03)

1. Lancer le client de référence (1 requête/s, paiement régulier) et collecter : `python -m ml_app.cli collect --run-id train-1 --duration 1800 --out /data/train-1.csv`.
2. Collecter validation et test (`--run-id val-1`, `test-1`) en y rejouant SC-01 (45 s, rampe 5 → 10 → 20 req/s, plafond 50) et noter le journal des dégradations constatées (`{"degraded": [{"start": ts, "end": ts}]}`), puis `cli.py label`.
3. Assembler `dataset.csv`, `splits.json`, `manifest.json` (un dossier), puis `python -m ml_app.cli train --dataset … --out /models/<version> --version <version>` (sans `--synthetic`).
4. Relever le rapport (`report.md`, `report.json`) : matrice de confusion, précision, rappel, F1, fausses alertes par heure, latence p50/p95 depuis la première dégradation, **avec la taille d'échantillon**. Cibles expérimentales : rappel ≥ 0,8, précision ≥ 0,8, détection ≤ 15 s.
5. Trois exécutions finales indépendantes sous Windows. Si la cible n'est pas atteinte : analyser les caractéristiques, le seuil et la dérive, réentraîner puis refaire un **nouveau** test indépendant.
6. Épingler l'empreinte : `ML_MODEL_SHA256=$(jq -r .artifact_sha256 manifest.json)` dans l'environnement du détecteur.

## 6. Limites

- Détecteur A (Prometheus) : aucune donnée réelle utilisée, aucun score réel annoncé. Détecteur B (WAF) : une seule session réelle, résultats non probants (§7).
- Un modèle entraîné sur une machine n'est pas automatiquement valable sur une autre (quota CPU, latences, versions) : réentraîner sur la cible ; toute dérive de version de scikit-learn est refusée au chargement.
- Une seule classe d'incident (saturation) : l'exfiltration, l'élévation de privilèges ou une attaque lente ne sont pas évaluées.
- Dépend de trafic légitime continu : sans paiement dans la fenêtre, le détecteur s'abstient.
- Le détecteur ne décide pas de la source (`source_ip` absent de l'événement) : c'est le travail du SOC à partir des journaux.

## 7. Détecteur B — journaux réels du WAF, par User-Agent (21 octobre 2026)

Code : `services/ml-detector/ml_app/waf/` (`python -m ml_app.waf …`). Résultats bruts : `docs/ml/results/waf-real-1.{md,json}`. Définition des jeux : `docs/ml/data/waf-2026-10-21.splits.json` (liée au journal par son SHA-256 `c4bf1c0a…86ac`, que l'entraînement refuse de traiter si le fichier diffère).

**Données.** `access.jsonl` exporté du PC Hôte : 13 384 requêtes sur 31 min (11:31:50–12:02:35 UTC), aucune ligne rejetée. Deux User-Agent seulement : un navigateur (171 requêtes, navigation et paiements) et `ResilienceAttack/1.0` (13 213 requêtes en 3 rafales d'environ 60 s à 71–76 req/s, toutes sur `/`, durée ≈ 1 ms, toutes en 200 car le journal ne contient pas de blocage). La vérité terrain est le marqueur dans le User-Agent (valable en laboratoire) ; **le modèle ne voit jamais le User-Agent**, seulement le comportement.

**Préparation.** Fenêtres de 10 s, pas de 5 s, par User-Agent. Sept caractéristiques : débit, part de 4xx, part de 5xx, nombre d'URI distinctes, concentration sur l'URI dominante, durée moyenne, part de POST. Une fenêtre n'appartient à un jeu que si elle est entièrement dans l'un de ses intervalles ; au moins une fenêtre de purge entre jeux ; l'entraînement refuse tout trafic portant le marqueur d'attaque.

| Jeu | Intervalles | Contenu |
|---|---|---|
| Entraînement | 11:31:50–11:46:59 | 111 requêtes normales (95 fenêtres) |
| Validation | 11:47:30–11:49:00, 11:49:20–11:51:00 et 11:55:00–11:58:30 | rafales 1 et 2 + 41 requêtes normales |
| Test (gelé) | 11:51:20–11:54:00 et 11:58:50–12:02:40 | rafale 3 + 15 requêtes normales |

**Modèle et règle.** Isolation Forest (200 arbres) entraîné sur le trafic normal seul ; seuil = le plus sensible (≤ 0) sans blocage à tort sur la validation (−0,103). Un User-Agent est signalé après **3** fenêtres consécutives atypiques d'au moins 5 requêtes. *Correction de conception faite pendant l'essai* : avec 2 fenêtres, un seul pic de navigation de 3 s remplissait les deux fenêtres (elles se recouvrent de moitié) et faisait signaler le navigateur ; avec 3, la première et la troisième ne se recouvrent plus.

**Résultats (test gelé, rafale 3 + trafic normal de fin)**

| Mesure | Valeur |
|---|---|
| Fenêtres d'attaque : TP / FN | 13 / 1 (rappel 0,93) |
| Fenêtres normales : FP / TN | 0 / 20 (précision 1,00 — **non probante**, voir ci-dessous) |
| Rafales détectées et bloquées | 3 sur 3 (validation 2, test 1) |
| Délai jusqu'à la décision | 15 s après la première requête d'attaque (mesuré à la fermeture de la fenêtre ; en direct s'ajoutent 1 s de tolérance et jusqu'à 5 s d'intervalle de lecture) |
| Blocage d'un User-Agent normal | 0 |
| Exécution de bout en bout | `replay` sur le journal réel : `ua:ResilienceAttack` écrit une fois, puis `ALREADY` ; le navigateur est refusé (`REFUSED_BROWSER`) |

**Ce que ces chiffres ne prouvent pas (mises en garde calculées par l'évaluation)**

1. **La précision est non probante.** Le jeu de test contient 0 fenêtre normale d'au moins 5 requêtes : tout le trafic normal y est trop faible pour pouvoir déclencher, donc aucun faux positif ne pouvait apparaître.
2. **Le modèle sépare mal une rafale normale d'une attaque.** Sur l'ensemble du trafic normal du journal (entraînement compris, donc dans le cas le plus favorable), 7 des 11 fenêtres normales d'au moins 5 requêtes sont jugées atypiques ; la règle d'alerte a signalé le navigateur une fois (11:33:45, 6 requêtes). Seul le refus des jetons de navigateur (`Mozilla`, `Chrome`…) a évité un blocage. Cause : 11 fenêtres normales « fournies » seulement pour apprendre à quoi ressemble un pic normal.
3. **Une règle à seuil sur une seule caractéristique fait aussi bien.** Le débit seul sépare l'attaque (1 erreur sur le test, comme le modèle). Sur ce journal, l'apport du ML par rapport à une règle simple n'est donc pas démontré.
4. **La sensibilité vient de la signature de l'outil, pas du débit.** Même sous-échantillonnée à 0,9 req/s, l'attaque est détectée (3 sur 3) parce qu'elle n'a qu'une URI et dure ≈ 0,6 ms, ce qu'aucune fenêtre normale ne présente. Conséquence : un client de supervision qui interroge une seule URL à cadence régulière ressemblerait à cette attaque. Il faut le déclarer avec `--never-block`.
5. **Un seul outil d'attaque, une seule session.** Aucune généralisation (autre User-Agent, URI variées, attaque lente à plusieurs identités) n'est démontrée ; changer de User-Agent contourne le blocage, et une rotation du User-Agent à chaque requête n'est pas détectée (test `test_user_agent_rotation_evades_detection_documented_limit`).

**Ce qui est prouvé** : le chaînage journal → fenêtres → modèle vérifié → règle d'alerte → écriture sûre de `ua:Token` fonctionne sur de vraies données ; un flood à plus de 70 req/s est signalé en 15 s sans bloquer le navigateur ; le blocage est atomique, borné, idempotent et simulé par défaut.

**Pour rendre les résultats probants (à refaire sur le PC Hôte)**
1. 30 minutes de navigation **active** (chargements de page, paiements rapprochés, plusieurs navigateurs, le client de référence) : viser au moins 200 fenêtres normales de 5 requêtes ou plus, dont 50 dans le jeu de test.
2. Au moins 3 rafales **de profils différents** : autre User-Agent, URI variées, débits de 5 à 80 req/s, une attaque lente.
3. Exporter `access.jsonl`, écrire un nouveau fichier de séparation (même format), relancer `python -m ml_app.waf train …`, et lire d'abord les mises en garde.

**Décision d'architecture à arbitrer** : le sujet demande que le détecteur alimente la chaîne de remédiation. L'écriture directe dans `blocklist.txt` (`--apply`) donne au détecteur un pouvoir d'action ; la voie la plus prudente est de lui faire seulement émettre l'événement (mode simulation) et de laisser l'orchestrateur écrire. Par défaut le détecteur **n'écrit pas**.
