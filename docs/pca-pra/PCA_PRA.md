# PCA / PRA — plateforme de paiement fictive RESILIENCE-ALPHA

Version 1.0 — 21 octobre 2026. Remplace la conception initiale du 19 octobre. Le plan est écrit **pour la solution livrée** : chaque objectif renvoie à un mécanisme présent dans l'architecture et à une preuve, existante ou à produire. Il ne prétend pas couvrir une production réelle.

## 1. Périmètre, hypothèses et statut des preuves

L'entreprise est fictive (« Alpha Paiements », hypothèse de travail : établissement de paiement). Aucune donnée réelle. Le commanditaire fictif est la Direction Nationale de la Sûreté Numérique. Les noms et titulaires de rôles sont à confirmer par l'équipe (§7).

Chaque ligne de ce plan porte l'un de ces statuts :

| Statut | Sens |
|---|---|
| **Établi** | Observé sur l'environnement de l'équipe (note d'avancement du 20/10/2026) ou répété ici avec preuve versionnée |
| **Conçu** | Décrit dans l'architecture, pas encore exécuté de bout en bout |
| **À mesurer** | Objectif chiffré provisoire, sans mesure sur le PC Hôte |

Rien n'est annoncé « Établi » sans preuve. Les composants incident-service, runner, ML et RAG n'étaient pas branchés dans la note du 20/10 : la chaîne de reprise autonome complète est donc **Conçue**.

## 2. Services critiques et analyse d'impact (BIA)

Question posée par la direction : quels services protéger en premier et que coûte leur arrêt ?

| Service | Fonction métier | Criticité | MTD (hyp.) | RTO cible | RPO cible | Dépendances | Statut |
|---|---|---|---|---|---|---|---|
| Paiement (WAF → payment-api → PostgreSQL) | Exécuter un virement correct, idempotent | **Critique** | 15 min | **60 s** dans SC-01 ; 30 min hors scénario | **0** transaction confirmée perdue dans SC-01 ; dernier backup hors scénario | WAF, auth (nouveaux jetons), PostgreSQL | WAF + paiement : Établi ; chaîne autonome : Conçu ; RTO : À mesurer |
| Authentification | Délivrer des jetons JWT 15 min | Haute | 30 min | 5 min | 0 (comptes en base) | PostgreSQL | Établi |
| PostgreSQL | Soldes, transactions, incidents | **Critique** (point unique) | 15 min | 30 min (restauration) | Dernier backup | Volume Docker sur SSD interne | Logique de restauration répétée ; PC Hôte : À mesurer |
| Détection (ML + Prometheus + Loki + incident-service + runner) | Détecter et réagir sans opérateur | Haute | 1 h | Reprise manuelle §RUNBOOK 5 | n/a | Scrapes frais | Conçu |
| Frontend / supervision | Confort jury et opérateur | Moyenne | 4 h | 30 min | n/a | WAF | Établi |
| Assistant RAG (Ollama) | Aide à la lecture des procédures | **Faible** | 24 h | Hors chemin critique | n/a | Ollama, index | Implémenté, tests unitaires |

**Principe** : le RAG et l'IA générative ne sont jamais dans la chaîne de reprise ; une panne de l'assistant n'a aucun effet sur le paiement ni sur la remédiation.

**Coût d'un arrêt.** Aucun montant n'est inventé. Le coût d'une minute d'arrêt se calcule ainsi : `C_arrêt(T) = λ × T × (c_retard + c_support) + P_SLA(T)`, où λ est le débit de tentatives, T la durée, `c_retard` le coût unitaire d'une tentative retardée ou perdue, `c_support` le coût de traitement des réclamations et `P_SLA` d'éventuelles pénalités contractuelles. Le volume concerné est, lui, calculable :

| Débit λ | 1 min | 15 min | 1 h |
|---|---|---|---|
| 1 tentative/s (client de référence de la démonstration) | 60 | 900 | 3 600 |
| 10 tentatives/s | 600 | 9 000 | 36 000 |
| 100 tentatives/s | 6 000 | 90 000 | 360 000 |

Le commanditaire fictif doit fixer `c_retard` ; c'est l'arbitrage qui justifie de dépenser pour un RTO d'une minute plutôt que de quinze.

## 3. Scénarios couverts

| ID | Scénario | Détection | Stratégie | Automatique ? | Objectifs | Statut / preuve |
|---|---|---|---|---|---|---|
| S1 | **SC-01** : saturation du paiement par une source autorisée du réseau du groupe | Score ML sur deux fenêtres consécutives, puis corroboration SOC (logs WAF) | **PCA** : filtrage ciblé de la source, clients légitimes préservés. **PRA** : paiement de validation | Oui, sans opérateur | RTO ≤ 60 s, RPO 0 | Blocage WAF par User-Agent : Établi (200→403 en ~2 s). Chaîne complète : Conçu ; trois essais à produire |
| S2 | PostgreSQL indisponible (ex. disque externe déconnecté) | Readiness en échec, 503 | PCA : refus explicite, jamais de succès avant commit, retry idempotent. PRA : relance ou restauration | Non (relance manuelle, §Runbook 4) | RTO 30 min, RPO 0 si volume intact | Cause observée par l'équipe ; contournement : Docker sur SSD interne |
| S3 | Perte ou corruption du volume PostgreSQL | Échec de persistance, incohérence comptable | PRA : restauration vers instance **distincte**, contrôle comptable, bascule documentée | Non (jamais de restauration destructive automatique) | RTO 30 min, RPO = dernier backup | Logique répétée (PG16 local, `docs/evidence/pra`) ; PC Hôte : À mesurer |
| S4 | Compromission d'identité ou de jeton (vol de JWT, de jeton ML) | Corrélation SOC indépendante, refus de l'ownership | **Ce n'est pas une reprise** : révoquer (TTL 15 min, rotation des clés), isoler, enquêter. Un redémarrage n'est jamais une correction | Non | n/a | Contrôles RBAC testés (45 tests backend) ; rotation : Conçu |
| S5 | Observabilité indisponible (Prometheus, Loki, Alloy) | `up == 0`, fenêtres ML invalides | PCA : les paiements continuent ; **la remédiation s'abstient sans preuve fraîche** | Abstention automatique | Reprise 15 min | Conçu (`DATA_UNAVAILABLE`), testé unitairement côté ML |
| S6 | Faux positif : blocage de clients légitimes | Paiement de validation en échec après action, plaintes | Compensation unique `REMOVE_SOURCE_BLOCK` ; TTL 120 s ; l'incident finit en `RECOVERY_FAILED` (jamais `RECOVERED` après simple retrait) | Oui (une fois) | Retour < 2 min | Conçu |
| S7 | Perte du PC Hôte | Machine hors service | Reconstruction depuis le dépôt, secrets SOPS/age (clé hors dépôt), dernier backup | Non | RTO 2–4 h (hypothèse), RPO dernier backup | Procédure écrite (Runbook 7) ; non répétée |
| S8 | Assistant IA / Ollama indisponible | Readiness RAG | Aucune action : hors chemin critique, l'opérateur lit les procédures | n/a | n/a | Implémenté (503 explicite, jamais de réponse fabriquée) |

**Hors périmètre, assumé** : exfiltration de données, élévation de privilèges, déni de service distribué, attaque depuis plusieurs sources ou derrière un NAT commun, sinistre du site, panne simultanée de l'hôte et des sauvegardes. Elles ne sont pas couvertes par S1 et ne doivent pas être confondues avec la restauration de disponibilité (EPSI p.3).

## 4. Continuité (PCA) : comment le service tient pendant l'incident

1. **Filtrage ciblé** plutôt que coupure globale : seule la source identifiée est bloquée, TTL 120 s, jamais un `/24` ni la passerelle.
2. **Pas de paiement optimiste** : succès affiché seulement après commit ; échec explicite avec clé de retry ; rejeu identique = même transaction, aucun double débit.
3. **Quotas** CPU/RAM par conteneur pour borner l'impact d'un service sur l'hôte ; plafond global de sécurité sur la charge d'essai.
4. **Supervision indépendante** du chemin de paiement (Prometheus/Loki/Grafana) : une panne de l'observabilité suspend la remédiation, pas les paiements.
5. **IA hors chemin critique** : la détection ML déclenche l'**investigation** ; la décision est une politique déterministe après preuve SOC ; le LLM ne décide ni n'exécute rien.

## 5. Reprise (PRA)

**Nominal automatique (S1).** `DETECTED → ANALYZING → CONFIRMED → REMEDIATING → VALIDATING → RECOVERED`, états terminaux `REJECTED`, `RECOVERED`, `RECOVERY_FAILED`. `RECOVERED` exige : readiness 200, p95 < 500 ms et 5xx < 1 % sur une fenêtre de 10 s entièrement postérieure à l'action (≥ 5 requêtes légitimes), reçu du contrôleur WAF, et **un nouveau paiement de 1 centime** entre deux comptes synthétiques dédiés avec débit/crédit exacts et somme inchangée. Un conteneur qui redémarre n'est pas une preuve.

**Restauration de données (S3).** Sauvegarde avant chaque séance ; restauration vers une instance et un volume **distincts** ; contrôle comptable (comptes, transactions, somme des soldes, empreintes) ; bascule seulement si identique. Le script `scripts/pra_backup_restore.sh` refuse une cible non vierge et un dump altéré. Détail : `docs/runbooks/RECOVERY_RUNBOOK.md` §6.

**Reconstruction (S7).** Tout est reproductible depuis le dépôt (Compose, scripts, SOPS). La clé age est le seul élément **non** reconstructible depuis le dépôt : sa perte oblige à régénérer tous les secrets et invalide les jetons existants. Elle est conservée hors dépôt par l'équipe.

**Compromission (S4).** On ne « récupère » pas d'une compromission en redémarrant : on révoque, on isole, on conserve les preuves, on analyse. Ces actions sont humaines et ne comptent pas dans la reprise autonome.

## 6. Budget de temps du RTO de SC-01

Les délais maximaux de la machine à états (`docs/security/REMEDIATION_DESIGN.md`) permettent de vérifier si 60 s est tenable :

| Étape | Délai max nominal |
|---|---|
| Latence de détection : fenêtre glissante de 15 s à remplir, puis **2 fenêtres consécutives** à 5 s d'intervalle | 10 à 25 s (estimation à mesurer) |
| DETECTED → ANALYZING | 2 s |
| ANALYZING → CONFIRMED (corrélation SOC) | 8 s |
| CONFIRMED → REMEDIATING | 2 s |
| REMEDIATING → VALIDATING (action WAF et reçu, un essai) | 15 s |
| VALIDATING → RECOVERED (fenêtre post-action + paiement) | 15 s |
| **Total** | **52 à 67 s** |

Conclusions : les délais maximaux ajoutés dépassent déjà 60 s dans le pire cas ; l'objectif ne se tient que si les étapes consomment **moins que leur maximum**, ce que seule la mesure sur le PC Hôte établira. Leviers si l'objectif est manqué, du moins coûteux au plus risqué : raccourcir la fenêtre post-action (compromis avec la fiabilité de la validation), accélérer l'évaluation ML (compromis avec les faux positifs), abaisser `consecutive` à 1 (déconseillé : un pic isolé déclencherait). Un RTO manqué est **rapporté tel quel**, le chronomètre n'est pas modifié (REMEDIATION_DESIGN).

## 7. Rôles et responsabilités

| Rôle | Responsabilité dans le PCA/PRA | Titulaire |
|---|---|---|
| Coordination / gouvernance | Déclarer l'incident, arbitrer, informer le coach, tenir le journal et consigner les décisions | À confirmer |
| Infrastructure | Sauvegardes, restauration, relance des services, volumes, observabilité | À confirmer |
| Cybersécurité | Périmètre d'attaque, arrêt d'urgence, WAF/SOC, analyse de cause | À confirmer |
| Développement | Cohérence comptable, idempotence, correctifs applicatifs | À confirmer |
| IA / données | Détecteur, qualité des données, assistant ; gel du modèle avant essai | À confirmer |
| Coach | Valide le périmètre, reçoit tout dépassement d'autorisation | Coach du campus |

Escalade : tout effet hors périmètre ou toute action inconnue du catalogue → arrêt et information immédiate du coach. Décision de bascule de base (S3) : coordination + infrastructure, jamais un seul membre.

## 8. Plan de test et critères d'acceptation

| Essai | Contenu | Critère | Statut |
|---|---|---|---|
| REC-01 ×3 | SC-01 complet sur PC Hôte, sans intervention | `RECOVERED`, RTO mesuré, pas de rechute après expiration du TTL | À produire |
| CHAOS-01 | Défaillances injectées bornées (arrêt d'un exporter, Loki, WAF) | S5/S6 conformes : abstention, compensation | À produire |
| Restauration (PC Hôte) ×3 | Runbook §6 | Contrôle comptable identique, durée consignée | À produire (logique déjà répétée en local) |
| Revue après échec | Après chaque `RECOVERY_FAILED` | EBIOS mise à jour | Procédure |

Livrable de chaque essai : chronologie t0 (dégradation) / t1 (détection) / t2 (action) / t3 (validation), identifiants (incident, action, transaction), empreinte du modèle, configuration, RTO mesuré, pertes constatées, limites. Une intervention humaine corrective est consignée et **invalide le succès autonome** de l'essai. Les objectifs sont révisés avec le coach après trois répétitions.

## 9. Risques résiduels après reprise

- **Point unique** : un seul PostgreSQL, pas de réplication, pas de site de secours ; RPO hors scénario = dernier backup.
- **Visibilité de la source** : sous Docker Desktop/WSL2 l'adresse IP source est masquée ; le blocage actuel par User-Agent est contournable en changeant l'en-tête. Le scénario reste crédible seulement tant que l'attaquant ne s'adapte pas.
- **Attaque distribuée ou NAT** : une source commune légitime et malveillante ne peut être séparée : l'automate s'abstient plutôt que de bloquer une passerelle.
- **Faux négatifs et dérive du modèle** : un modèle entraîné sur la machine de développement n'est pas valable sur le PC Hôte sans réentraînement.
- **Preuve non indépendante** : essais menés par l'équipe elle-même, pas d'audit externe.

## 10. Retour à la normale et amélioration

Fin de charge contrôlée ; expiration du TTL de 120 s ; absence de rechute ; export des preuves ; restitution des ressources ; données remises à l'état de référence **entre** les essais seulement (`scripts/demo_reset.sh`), jamais pendant une séquence filmée. Après chaque échec, retour d'expérience daté dans l'analyse de risques.
