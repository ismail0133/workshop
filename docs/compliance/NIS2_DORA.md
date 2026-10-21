# NIS2 et DORA — pertinence pour l'entreprise fictive et liens avec l'architecture

Version 1.0 — 21 octobre 2026. Objectif (EPSI p.5) : une analyse **liée à l'architecture et aux essais**, distinguant ce qui est démontré par le prototype de ce qui ne peut pas l'être en quatre jours. Ce n'est ni une certification ni un avis juridique.

## 1. Qualification de l'entité (hypothèses explicites)

L'entreprise fictive « Alpha Paiements » est supposée **établissement de paiement** agréé en France, hypothèse à confirmer avec le commanditaire fictif. Taille, chiffre d'affaires et activités annexes ne sont pas fixés ; aucun seuil de taille n'est donc utilisé.

| Texte | Lecture pour l'entité supposée | Source |
|---|---|---|
| **DORA** — règlement (UE) 2022/2554, applicable depuis le 17 janvier 2025 | S'applique directement aux établissements de paiement. C'est le cadre **principal** de cette analyse | [ESMA, DORA](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/digital-operational-resilience-act-dora) |
| **NIS2** — directive (UE) 2022/2555 | Sert de référentiel de bonnes pratiques et d'hypothèse alternative. Pour une entité financière soumise à DORA, les exigences équivalentes de gestion du risque TIC et de notification de DORA prévalent (lex specialis) ; l'articulation exacte est à qualifier avec la conformité | [Commission, NIS2](https://digital-strategy.ec.europa.eu/en/policies/nis2-directive) ; [lignes directrices art. 4](https://digital-strategy.ec.europa.eu/en/library/commission-guidelines-application-article-4-1-and-2-directive-eu-20222555-nis-2-directive) |
| Transposition française de NIS2 | **Non adoptée** à notre connaissance : le projet de loi « résilience » était inscrit à l'Assemblée nationale pour le 7 octobre 2026, puis son examen a été repoussé (information du 6 octobre 2026). À revérifier avant toute conclusion | [Next, brief du 23 septembre 2026, mis à jour le 6 octobre](https://next.ink/briefs/le-brief-du-23-septembre-2026/) |

Conséquence : on ne « additionne » pas toutes les obligations. On traite DORA comme obligation, NIS2 art. 21 comme grille de contrôle complémentaire, et on le dit.

## 2. DORA : exigences pertinentes face à la conception

| Enjeu (articles DORA) | Conception RESILIENCE-ALPHA | Preuve (statut) | Limite du prototype |
|---|---|---|---|
| Gouvernance, responsabilité de l'organe de direction (art. 5) | Registre des décisions (ADR-01 à ADR-11 et décisions de gouvernance), recommandations à la direction | `docs/architecture/ARCHITECTURE.md`, `docs/governance/` (établi) | Pas d'organe de direction réel ni de formation de ses membres |
| Cadre de gestion du risque TIC, identification des actifs (art. 6 à 8) | EBIOS RM, inventaire des biens supports, propriétaires de risque | `docs/ebios/EBIOS_RM.md` (établi ; validation coach à consigner) | Cotations qualitatives ; pas de revue annuelle |
| Protection et prévention (art. 9) | RBAC, JWT RS256, Argon2id, WAF, secrets SOPS, réseaux `internal`, conteneurs non-root | 45 tests backend ; WAF smoke 28/28 (établi) | Pas d'audit indépendant ; pas de MFA ; JWT sans révocation avant expiration |
| Détection d'activités anormales (art. 10) | Isolation Forest sur métriques réelles, SOC sur logs WAF, alertes Prometheus/Grafana | Détecteur et tests unitaires (implémenté) ; essais sur PC Hôte : **à produire** | Un scénario, pas toutes les classes d'incidents ; modèle à réentraîner sur la cible |
| Réponse et reprise, continuité (art. 11) | PCA/PRA, automate d'incident, remédiation bornée à un catalogue de deux actions | `docs/pca-pra/PCA_PRA.md` ; REC-01 ×3 : **à produire** | Pas de site de secours ni de haute disponibilité |
| Sauvegarde, restauration, systèmes ségrégués (art. 12) | Sauvegarde PostgreSQL, restauration vers instance distincte, contrôle comptable | `scripts/pra_backup_restore.sh`, répétition PG16 (`docs/evidence/pra`) ; PC Hôte : **à produire** | Données synthétiques ; pas d'archivage continu (RPO = dernier backup) |
| Apprentissage et évolution (art. 13) | Retour d'expérience après chaque `RECOVERY_FAILED`, révision d'EBIOS | Procédure (établi) | Pas de cycle annuel |
| Gestion, classification et notification des incidents (art. 17 à 19) | Journal d'incident structuré, exportable, horodaté UTC ; automate à états | `ops.incident_events` (conçu) ; export : voir §4 | **Aucune notification réelle** ; seuils de classification non implémentés |
| Tests de résilience (art. 24, 25) | Essais bornés, défaillances injectées (CHAOS-01), répétitions de reprise | À produire | **Pas** un programme TLPT (art. 26), réservé aux entités désignées |
| Risques liés aux prestataires TIC (art. 28 à 30) | Inventaire images, modèles et dépendances, digests et lockfile | Manifestes au gel (conçu) | Pas de contrats, pas de registre d'informations, pas de stratégie de sortie |

## 3. NIS2 art. 21 : grille de contrôle des dix mesures

| Mesure (art. 21, § 2) | Couverture | Écart |
|---|---|---|
| a) Analyse des risques et politiques de sécurité | EBIOS RM, politique de remédiation versionnée | Pas de politique de sécurité de l'information formelle |
| b) Gestion des incidents | Incident-service, états, journal | Pas d'astreinte réelle |
| c) Continuité, sauvegardes, reprise, gestion de crise | PCA/PRA, runbook, répétition de restauration | Gestion de crise limitée à l'équipe |
| d) Sécurité de la chaîne d'approvisionnement | Digests, lockfile, audit au gel | Pas d'évaluation des fournisseurs |
| e) Sécurité de l'acquisition, du développement et de la maintenance ; vulnérabilités | Tests, `pip check`, `npm audit` (0 vulnérabilité signalée en phase 2) | Pas de processus de divulgation |
| f) Évaluation de l'efficacité des mesures | Recette, essais REC/CHAOS | À produire |
| g) Hygiène informatique et formation | — | **Non couvert** |
| h) Cryptographie et chiffrement | TLS au WAF, RS256, Argon2id, SOPS/age | Gestion du cycle de vie des clés limitée |
| i) Sécurité des ressources humaines, contrôle d'accès, gestion des actifs | RBAC, inventaire des biens supports | Pas de processus RH |
| j) Authentification multifacteur, communications sécurisées | — | **Non couvert** (pas de MFA) |

L'article 20 (responsabilité de l'organe de direction) et l'article 23 (notification) sont traités au §4 et dans les recommandations.

## 4. Notification : ce que la plateforme fournit et ce qui manque

Délais DORA pour un incident **majeur** lié aux TIC, selon le règlement délégué (UE) 2025/301, art. 5 (source : [FMA, « DORA — ICT-related incidents »](https://www.fma.gv.at/en/dora-ict-related-incidents/)) :

| Rapport | Délai |
|---|---|
| Notification initiale | Dès que possible, **4 h** au plus après la classification en incident majeur, et **24 h** au plus après la prise de connaissance |
| Rapport intermédiaire | **72 h** après la notification initiale, puis à chaque mise à jour importante |
| Rapport final | **1 mois** au plus après le dernier rapport intermédiaire |

Formulaires : règlement d'exécution (UE) 2025/302. Critères de classification : règlement délégué (UE) 2024/1772. NIS2 prévoit un calendrier voisin (alerte précoce 24 h, notification 72 h, rapport final un mois) à l'article 23.

**Ce que le journal d'incident peut alimenter** : identifiant, horodatages de la dégradation, de la détection, de l'action et de la validation, services concernés, source corrélée, actions exécutées et leur résultat, durée, transaction de validation. **Ce qu'il ne contient pas** : nombre de clients touchés, volume de transactions affectées, pertes de données, impact économique, cause racine et mesures correctives, nécessaires pour classer l'incident et rédiger les rapports. Ces champs relèvent de la production, pas d'un prototype.

**Qualification de SC-01** : la classification en incident majeur dépend de seuils chiffrés du règlement 2024/1772 que ce dossier n'applique pas. SC-01 est un incident **simulé** sans client réel : aucune notification n'est due, et la plateforme n'en envoie aucune.

## 5. Ce qu'un prototype de quatre jours ne peut pas démontrer

1. La **conformité** : un tableau de bord ou un état `RECOVERED` n'est pas une preuve de conformité DORA ou NIS2.
2. La notification effective à une autorité, et l'application des seuils de classification.
3. Les contrats avec les prestataires TIC et le registre d'informations (art. 28 à 30).
4. Les tests TLPT (art. 26) et l'audit indépendant.
5. La formation et la responsabilité réelle de l'organe de direction.
6. La haute disponibilité, le site de secours et les objectifs RTO/RPO d'une production.
7. La couverture d'autres classes d'incidents (exfiltration, élévation de privilèges, DDoS).

## 6. Recommandations

Voir `docs/governance/RECOMMANDATIONS_DIRECTION.md` : qualifier l'entité avec les responsables juridique et conformité avant tout investissement ; financer d'abord le point unique PostgreSQL, les identités et secrets, la qualification des fournisseurs et un test indépendant.

Sources consultées les 19 et 21 octobre 2026. L'accès direct aux pages EUR-Lex était partiellement bloqué par une protection anti-robot ; les articles cités s'appuient sur les sources officielles de la Commission et de l'ESMA et sur la page de la FMA pour les délais de notification. Les obligations détaillées et leur transposition sont à revérifier au moment de la qualification.
