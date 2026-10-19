# EBIOS RM — cadrage initial adapté au démonstrateur

Source méthodologique : [ANSSI, EBIOS Risk Manager](https://cyber.gouv.fr/securisation/analyse-des-risques/methode-ebios-rm/). La méthode structure l’analyse du métier vers les scénarios techniques et le traitement. Les cinq ateliers ci-dessous sont une préparation à discuter avec l’équipe et le coach, pas des ateliers déjà tenus.

## Atelier 1 — Cadrage et socle

Périmètre : PC Hôte/PA, attaquant autorisé, Ollama local ou déporté, banque fictive. Valeurs métier : exécuter des paiements corrects, préserver les transactions confirmées, expliquer chaque décision. Biens supports : API, Postgres, WAF, réseau, modèles, runner, secrets. Événements redoutés : paiement indisponible (gravité3), débit incorrect/double (4), divulgation secrets (4), perte preuve (3). Échelle gravité1 faible à4 critique ; évaluations initiales d’équipe, sans statistique terrain. Socle : RBAC, TLS entrée, secrets SOPS, réseaux, traces, catalogue fermé.

Impact métier hypothétique : à 1 paiement/s, une minute d’arrêt retarde jusqu’à60 tentatives, sans prétendre à une perte financière réelle. Un coût C par tentative retardée donnerait 60×C ; C reste à définir avec commanditaire fictif. Ne pas inventer un montant financier.

## Atelier 2 — Sources de risque / objectifs visés

SR1 acteur externe cherchant indisponibilité (motivation forte, moyens limités, scénario SC-01 représentatif) ; SR2 utilisateur malveillant cherchant modifier compte tiers (gravité élevée, tests RBAC) ; SR3 composant compromis cherchant détourner runner (gravité élevée, catalogue/permissions). Retenir ces couples pour le traitement, distinguer erreurs d’exploitation/pannes comme causes non malveillantes.

## Atelier 3 — Scénarios stratégiques

Écosystème : utilisateurs, équipe, PC IA, images/dépendances publiques et campus hors cible. Scénario S1 : acteur autorisé au réseau groupe perturbe paiements ; S2 : identité volée mène à opérations non autorisées ; S3 : dépendance/service compromis exploite droits excessifs pour modifier infrastructure. Relation de confiance critique : Incident→runner→WAF. Le campus et les autres groupes ne sont pas des partenaires de test offensif.

## Atelier 4 — Scénarios opérationnels

S1 : requêtes valides nombreuses → saturation API → métriques → score ML → IP corrélée → blocage ciblé → paiement validé. S2 : token d’un client → tentative compte tiers → refus ownership et audit. S3 : token ML volé → anomalie fabriquée → SOC sans preuve refuse ; si runner compromis, contrôle local valide encore IP/catalogue. Seul S1 est la démonstration principale ; S2/S3 sont tests défensifs bornés, pas affirmation de couverture exhaustive.

## Atelier 5 — Traitement et risque résiduel

| Risque | Vraisemblance initiale 1–4 / gravité / score | Mesures et preuve attendue | Résiduel estimé, propriétaire |
|---|---|---|---|
| Surcharge | 3/3/9 | Filtrage, ML/SOC, REC-01 | 2/3/6, cyber ; NAT/distribué hors couverture |
| Double débit | 2/4/8 | ACID/idempotence, PAY-02 | 1/4/4, dev |
| Détournement remédiation | 2/4/8 | Catalogue, token, socket, SEC-07 | 1/4/4, infra ; bug contrôleur possible |
| Faux positif filtre | 3/3/9 | Corrélation, exclusions, TTL, SEC-05 | 2/3/6, IA/cyber |
| Perte stockage | 2/4/8 | Sauvegarde/restauration hors SC-01 | 2/4/8 tant que test absent, infra |
| Perte traces | 2/3/6 | Volumes/export, OBS-03 | 1/3/3, infra |

Scores sont hypothèses qualitatives, pas risques mesurés ni acceptés. Critères proposés : score≥8 traite prioritairement ; tout risque hors périmètre ou privilège non contrôlé bloque l’essai. Acceptation résiduelle à consigner par équipe/coach, avec date et preuve ; revue après chaque RECOVERY_FAILED. Recommandation industrielle : éliminer point unique DB, audit du contrôleur, analyse de menace étendue et plan de tests plus long.
