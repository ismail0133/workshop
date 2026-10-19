# NIS2 / DORA — analyse de pertinence pour l’entreprise fictive

L’objectif EPSI p.5 est une analyse liée à l’architecture, pas une certification. Le statut juridique, la taille, le pays et les activités exactes de l’entreprise fictive restent à définir : aucune conclusion définitive d’assujettissement n’est tirée.

DORA traite la résilience numérique du secteur financier : gestion du risque TIC, incidents et reporting, tests, risques liés aux prestataires. Source officielle : [ESMA, DORA](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/digital-operational-resilience-act-dora). NIS2 encadre cybersécurité, gestion des risques et notification dans les secteurs concernés : [Commission européenne, NIS2](https://digital-strategy.ec.europa.eu/en/policies/nis2-directive). L’articulation avec les textes sectoriels doit être examinée, sans simplement additionner toutes les obligations : [lignes directrices de la Commission sur l’article4](https://digital-strategy.ec.europa.eu/en/library/commission-guidelines-application-article-4-1-and-2-directive-eu-20222555-nis-2-directive).

| Enjeu pertinent | Conception RESILIENCE-ALPHA | Preuve future | Limite prototype |
|---|---|---|---|
| Pilotage du risque TIC | EBIOS, propriétaires et ADR | GOV-01/02/05, validation équipe | Pas de gouvernance réelle d’établissement |
| Prévention et accès | RBAC, WAF, SOPS, durcissement | SEC-03/04/06/07 | Pas d’audit indépendant complet |
| Détection et gestion incident | ML/SOC, journal et timeline | ML-03, SEC-05, REC-01 | Un scénario, pas toutes classes d’incidents |
| Continuité et reprise | PCA/PRA, validation par transaction | REC-02 et RTO/RPO mesurés | Pas de site de secours/HA |
| Tests de résilience | Essais bornés et défaillances injectées | SC-02, CHAOS-01 | Ne constitue pas un programme TLPT réglementaire |
| Risques prestataires | Inventaire images/modèles/dépendances et digests | Manifestes au gel | Pas de contrats ni registre fournisseur réglementaire complet |
| Notification et reporting | Données incident structurées exportables | Journal horodaté | Aucune notification à une autorité, seuils/délais juridiques non implémentés |

Recommandation à une direction : qualifier d’abord l’entité et les textes applicables avec responsables juridiques/conformité ; financer disponibilité DB, gestion des identités/secrets, qualification des fournisseurs et essais indépendants avant toute industrialisation. Ne pas présenter RECOVERED ou un dashboard comme une preuve générale de conformité. Le dossier final remplacera chaque preuve attendue par résultat réel ou limite explicite. Les obligations détaillées et leur transposition doivent être revérifiées au moment de cette qualification.

Sources consultées le 19 octobre 2026 ; accès direct aux pages ELI EUR-Lex partiellement bloqué par protection anti-robot, complété par sources officielles Commission/ESMA. Aucune certification ni avis juridique n’est produit.
