# Analyse de risques EBIOS Risk Manager — RESILIENCE-ALPHA

Version 1.0 — 21 octobre 2026. Méthode : [ANSSI, EBIOS Risk Manager](https://cyber.gouv.fr/securisation/analyse-des-risques/methode-ebios-rm/), cinq ateliers adaptés à un démonstrateur de quatre jours. L'analyse est reliée à l'architecture réelle (`docs/architecture/ARCHITECTURE.md`) et aux essais ; elle remplace le cadrage initial du 19 octobre.

**Statut de la validation.** Les cotations sont des **estimations qualitatives de l'équipe**, sans statistique de terrain. La validation par le coach (jalon du lundi) et l'acceptation des risques résiduels sont à consigner dans le tableau de l'atelier 5 (date, nom, preuve). Aucune cotation n'est présentée comme « mesurée ».

**Échelles.** Gravité G et vraisemblance V de 1 (faible) à 4 (critique / quasi certaine). Score = V × G. Lecture : ≤ 4 acceptable sous suivi ; 5–7 tolérable avec surveillance ; **≥ 8 à traiter en priorité** ; ≥ 12 bloque l'essai tant qu'une mesure n'est pas en place.

## Atelier 1 — Cadrage et socle de sécurité

**Périmètre.** PC Hôte (Windows, Docker Desktop/WSL2) et point d'accès du groupe ; PC Attaquant autorisé ; Ollama local ou déporté (PC IA facultatif) ; banque fictive « Alpha Paiements » (hypothèse : établissement de paiement). Hors périmètre : réseaux du campus, autres groupes, services tiers, Internet.

**Valeurs métier.**

| ID | Valeur métier | Pourquoi elle compte |
|---|---|---|
| VM1 | Exécuter des paiements corrects et disponibles | C'est le service ; sa panne retarde les partenaires et fait perdre la confiance |
| VM2 | Intégrité et traçabilité des transactions confirmées | Un débit double ou perdu est un incident majeur |
| VM3 | Confidentialité des secrets et des identités | Les clés JWT et jetons internes donnent des pouvoirs |
| VM4 | Capacité à prouver et expliquer chaque décision de reprise | Le jury, la direction et un régulateur exigent des preuves |

**Biens supports.** payment-api, auth-service, PostgreSQL, WAF (Nginx), frontend, Prometheus/Loki/Alloy/Grafana, ml-detector, incident-service et runner (prévus), Ollama et rag-service, secrets (SOPS/age), PC Hôte et point d'accès Windows, images et dépendances publiques.

**Événements redoutés.**

| ID | Événement redouté | Valeur | G | Justification |
|---|---|---|---|---|
| ER1 | Paiement indisponible | VM1 | 3 | Reprise possible, impact opérationnel et réputation |
| ER2 | Débit incorrect ou double | VM2 | 4 | Perte financière, non-réversible sans traçabilité |
| ER3 | Divulgation de secrets (clé privée JWT, jetons internes) | VM3 | 4 | Prise de contrôle de l'authentification ou de la remédiation |
| ER4 | Perte de preuves et de traces | VM4 | 3 | La reprise ne peut être ni prouvée ni auditée |
| ER5 | Clients légitimes coupés par la défense elle-même | VM1 | 3 | L'automate devient la cause de l'indisponibilité |
| ER6 | Perte de la base PostgreSQL | VM1, VM2 | 4 | Point unique de défaillance ; données perdues |

**Impact métier.** Un arrêt d'une minute à 1 tentative/s retarde 60 tentatives ; à 100/s, 6 000. Le coût unitaire `c_retard` reste à fixer par le commanditaire (`docs/pca-pra/PCA_PRA.md` §2). Aucun montant n'est inventé.

**Socle de sécurité (état et écarts).**

| Mesure | État |
|---|---|
| RBAC USER/OPERATOR/ADMIN/VALIDATOR, 404 sur ressource étrangère, JWT RS256 15 min | Établi : 45 tests backend |
| Mots de passe Argon2id, limite de login | Établi |
| Réseaux Compose `internal`, aucune API ni base publiée, quotas CPU/RAM, conteneurs non-root, `cap_drop ALL` | Établi (configuration) |
| WAF Nginx devant frontend, auth et payment ; smoke test 28/28 | Établi (note d'avancement du 20/10) |
| Secrets : fichiers 0600 générés, SOPS/age prévu | Partiel : génération locale établie ; chiffrement SOPS : à finaliser |
| Journaux JSON, Loki/Alloy, Prometheus, Grafana | Établi côté WAF ; reste du chemin : en cours |
| Remédiation autonome, détecteur ML, assistant RAG | Implémentés côté service (tests unitaires) ; intégration PC Hôte : à faire |

## Atelier 2 — Sources de risque et objectifs visés

| Couple | Source de risque (SR) | Objectif visé (OV) | Motivation / moyens | Retenu |
|---|---|---|---|---|
| C1 | Acteur externe au réseau du groupe | Rendre le paiement indisponible | Forte / limités (génération de charge) | **Oui** — scénario SC-01 |
| C2 | Utilisateur légitime malveillant | Voir ou modifier le compte d'un tiers | Moyenne / un compte valide | **Oui** |
| C3 | Composant ou dépendance compromis | Détourner le runner ou le WAF | Moyenne / chaîne d'approvisionnement | **Oui** |
| C4 | Acteur voulant retourner la défense contre le service | Provoquer des blocages de clients légitimes | Moyenne / jeton ML volé ou signal fabriqué | **Oui** |
| C5 | Erreur d'exploitation ou panne (non malveillant) | — (cause) | n/a | **Oui, comme cause** (disque externe déconnecté, `down -v`) |

## Atelier 3 — Scénarios stratégiques

**Écosystème.** Utilisateurs, équipe, registres d'images (Docker), dépôts de paquets (PyPI, npm), modèles publiés par Ollama (`qwen2.5:1.5b`, `nomic-embed-text`), PC IA facultatif. Le campus et les autres groupes ne sont **pas** des parties prenantes de test offensif.

| ID | Chemin d'attaque stratégique | Couple | Parties prenantes | Relation de confiance critique |
|---|---|---|---|---|
| SS1 | Un acteur du réseau du groupe sature le paiement | C1 | Aucune | WAF → payment-api |
| SS2 | Vol d'identité, puis opérations non autorisées | C2 | Utilisateurs | Auth → JWT → payment-api |
| SS3 | Image, dépendance ou modèle compromis exécute du code avec des droits excessifs | C3 | Registres, Ollama | Incident → runner → WAF |
| SS4 | Un signal fabriqué (jeton ML volé) déclenche un blocage de clients légitimes | C4 | ml-detector | ml-detector → incident-service → runner |

## Atelier 4 — Scénarios opérationnels

| ID | Séquence | Vraisemblance | Mesures qui interrompent la séquence |
|---|---|---|---|
| SO1 | Requêtes valides en nombre → saturation de payment-api → métriques dégradées → score ML sous le seuil sur 2 fenêtres → corrélation SOC (IP dominante, ≥ 20 requêtes, ≥ 10 request_id joints) → blocage ciblé → paiement de validation | 3 | Quotas ; détection ; politique SC-01 ; blocage TTL 120 s |
| SO2 | Jeton d'un client → tentative sur un compte tiers → refus d'ownership (404) → journal | 3 | RBAC et tests d'ownership |
| SO3 | Paquet ou image compromis → exécution dans un conteneur → recherche d'une interface d'administration | 2 | Digests figés, non-root, pas de socket Docker, réseaux isolés |
| SO4 | Jeton ML volé → fausse anomalie → SOC sans preuve refuse (`REJECTED`) ; si le runner est compromis, le contrôleur WAF revalide IP et catalogue | 2 | Corroboration indépendante, catalogue fermé de deux actions, fencing token |
| SO5 | **Contournement du blocage** : l'attaquant change d'en-tête User-Agent, ou passe par un NAT commun | 3 | Aujourd'hui : aucune mesure efficace (limite connue) ; cible : blocage sur l'IP TCP réelle |

SO1 est la démonstration principale ; SO2–SO5 sont des tests défensifs bornés, **sans affirmation de couverture exhaustive**. SO5 est consigné parce qu'il est observé : sous Docker Desktop/WSL2 l'IP source est masquée (`client_ip` en 172.x), si bien que le blocage actuel s'appuie sur le User-Agent.

## Atelier 5 — Traitement du risque et risque résiduel

| ID | Risque (couple → événement redouté) | V / G / score initial | Mesures (statut) | V / G / score résiduel | Propriétaire | Décision |
|---|---|---|---|---|---|---|
| R1 | Saturation du paiement (C1 → ER1) | 3 / 3 / **9** | Quotas (établi) ; WAF (établi) ; détection ML + SOC + blocage ciblé (implémenté côté ML, intégration à faire) | Aujourd'hui 3 / 3 / 9 (blocage par UA) ; **cible 2 / 3 / 6** une fois l'IP source visible | Cybersécurité | Réduire ; DDoS et NAT hors couverture |
| R2 | Débit incorrect ou double (ER2) | 2 / 4 / **8** | Transactions ACID, idempotence persistée, verrous ordonnés, tests de concurrence (établi) | 1 / 4 / 4 | Développement | Réduire |
| R3 | Détournement de la remédiation (C3 → ER3/ER5) | 2 / 4 / **8** | Catalogue fermé, contrôleur sur socket Unix, tokens séparés (conçu) | 1 / 4 / 4 | Infrastructure | Réduire ; bug du contrôleur possible |
| R4 | Blocage de clients légitimes, y compris signal fabriqué (C4 → ER5) | 3 / 3 / **9** | Corrélation SOC, exclusions, TTL 120 s, compensation, refus sans preuve (conçu) | 2 / 3 / 6 | IA + Cybersécurité | Réduire |
| R5 | Perte ou corruption de PostgreSQL (ER6) | 2 / 4 / **8** | Docker sur SSD interne (établi) ; sauvegarde et restauration vers instance distincte avec contrôle comptable (logique répétée, PC Hôte à faire) | 2 / 4 / **8** tant que le test PC Hôte n'est pas fait | Infrastructure | Réduire ; **point unique non supprimé** |
| R6 | Perte de traces (ER4) | 2 / 3 / 6 | Volumes producteurs séparés, rotation 10 Mio × 5, export des preuves avant rotation (établi/conçu) | 1 / 3 / 3 | Infrastructure | Accepter sous suivi |
| R7 | Compromission d'identité (C2 → ER2/ER3) | 3 / 4 / **12** | Argon2id, 5 essais/min, JWT 15 min, ownership (établi) ; pas de MFA, pas de révocation avant expiration, JWT lisible par un script XSS | 2 / 4 / **8** | Développement | Réduire ; **non accepté** : limite à présenter |
| R8 | Divulgation de secrets, y compris envoi à un outil d'IA générative (ER3) | 2 / 4 / **8** | Secrets en fichiers 0600, montés en lecture seule par service, Payment sans clé privée, SOPS/age, contrôle d'archive avant remise, règle : aucun secret dans un prompt (EPSI p.7) | 1 / 4 / 4 | Cybersécurité | Réduire |
| R9 | Chaîne d'approvisionnement : image, paquet, modèle (C3) | 2 / 3 / 6 | Digests d'images, `requirements.lock`, audit au gel ; modèles Ollama épinglés par nom et version | 2 / 3 / 6 | Infrastructure + IA | Accepter sous suivi ; pas de registre fournisseur |
| R10 | Mauvaise réponse ou injection de prompt via l'assistant (ER4, ER5) | 3 / 2 / 6 | RAG sans outil, rôle OPERATOR, abstention sous seuil, balises neutralisées, aucune question journalisée (établi : tests) | 2 / 2 / 4 | IA | Réduire |
| R11 | Aveuglement ou dérive du détecteur (faux négatifs, fenêtres sans données) (ER1) | 3 / 3 / **9** | Seuil calibré sur la validation seule ; test gelé ; `DATA_UNAVAILABLE` sans inférence ; alerte `MLDataUnavailable` ; réentraînement sur la cible | 2 / 3 / 6 | IA | Réduire |
| R12 | Erreur d'exploitation : `down -v`, disque externe, mauvaise cible (C5 → ER1/ER6) | 3 / 3 / **9** | Runbook, README (« ne jamais `down -v` »), SSD interne, `demo_reset.sh` encadré | 2 / 3 / 6 | Coordination | Réduire |

**Risques résiduels à présenter à la direction** : R5 (point unique) et R7 (identité) restent à 8 ; R1 reste à 9 tant que le blocage s'appuie sur le User-Agent. Ils sont **signalés, pas acceptés** : leur acceptation relève de la direction, avec date et preuve.

**Acceptation.** Signataire, date et preuve à consigner par risque résiduel ≥ 5 : _à compléter par l'équipe et le coach_. Revue obligatoire après chaque `RECOVERY_FAILED`.

**Plan d'amélioration.** Priorité 1 : restaurer la visibilité de l'IP source (liaison du WAF sur l'adresse du point d'accès, test avec deux clients réels). Priorité 2 : trois restaurations de base sur le PC Hôte avec durées. Priorité 3 : MFA et révocation de jeton avant toute industrialisation. Recommandation industrielle : éliminer le point unique PostgreSQL, auditer le contrôleur WAF, étendre l'analyse de menace et la durée des tests (`docs/governance/RECOMMANDATIONS_DIRECTION.md`).
