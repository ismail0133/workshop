# Résultats — détecteur WAF par User-Agent (`waf-real-1`)

Données : `access.jsonl` (SHA-256 `c4bf1c0a43505504…`), 13384 requêtes lues, rejets : aucun.
Fenêtre 10 s, pas 5 s, seuil -0.1029, alerte après 3 fenêtres, ≥ 5 requêtes.
Entraînement : 95 fenêtres normales (111 requêtes).

**Mises en garde (générées par l'évaluation)**

- TEST_NORMAL_ELIGIBLE_TOO_FEW : 0 fenêtres normales assez fournies dans le test (< 30) : le taux de faux positifs n'est pas mesurable, la précision est NON PROBANTE.
- NORMAL_BURSTS_FLAGGED : 7/11 fenêtres normales de plus de 5 requêtes sont jugées atypiques ; 1 déclenchement(s) sur le seul trafic normal. Le modèle sépare mal une rafale normale d'une attaque : trop peu de pics normaux à l'entraînement.
- SINGLE_ATTACK_TOOL : un seul outil d'attaque (un User-Agent, une URI) : la généralisation n'est pas démontrée.

Contrôle de fausses alertes sur TOUT le trafic normal du journal (entraînement inclus) : 7/11 fenêtres assez fournies jugées atypiques, 1 déclenchement(s) de la règle d'alerte.

| Jeu | Fenêtres normales exploitables | Fenêtres d'attaque | TP | FP | FN | TN | Précision | Rappel |
|---|---|---|---|---|---|---|---|---|
| validation | 4 | 26 | 26 | 2 | 1 | 32 | 0.929 | 0.963 |
| test | 0 | 13 | 13 | 0 | 1 | 20 | 1.000 | 0.929 |

Rafales (blocage de bout en bout, rejeu du moteur) :

| Jeu | Requêtes d'attaque | Débit (req/s) | Détectée | Latence (s) | Blocages à tort |
|---|---|---|---|---|---|
| validation | 4211 | 71.4 | oui | 15 | 0 |
| validation | 4435 | 73.9 | oui | 15 | 0 |
| test | 4567 | 76.1 | oui | 15 | 0 |

Une règle à seuil sur une seule caractéristique suffit-elle ?

| Caractéristique | Séparable (train+validation) | Erreurs sur le test |
|---|---|---|
| req_per_s | oui | 1 |
| share_4xx | non | — |
| share_5xx | non | — |
| distinct_uris | non | — |
| top_uri_share | non | — |
| mean_duration_ms | non | — |
| share_post | non | — |

Sensibilité : le flood réel du jeu de test est sous-échantillonné (simulation d'une attaque plus lente) :

| Part conservée | Débit (req/s) | Détectée | Latence médiane (s) | Blocages à tort |
|---|---|---|---|---|
| 1 | 76.12 | 3/3 | 15 | 0 |
| 0.5 | 38.42 | 3/3 | 15 | 0 |
| 0.2 | 15.18 | 3/3 | 15 | 0 |
| 0.1 | 7.71 | 3/3 | 15 | 0 |
| 0.05 | 4.0 | 3/3 | 15 | 0 |
| 0.02 | 1.68 | 3/3 | 15 | 0 |
| 0.01 | 0.89 | 3/3 | 18 | 0 |
