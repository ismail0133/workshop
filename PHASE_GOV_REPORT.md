# Rapport de phase — pilier gouvernance et transformation (21 octobre 2026)

| Élément | Statut | Preuve / reste à faire |
|---|---|---|
| EBIOS RM (5 ateliers, scénarios, registre de risques) | RÉDIGÉ | Validation du coach à tracer ; cotations qualitatives |
| PCA/PRA (BIA, scénarios, RTO/RPO, RACI, risques résiduels) | RÉDIGÉ | Titulaires de rôles « À confirmer » |
| NIS2 / DORA | RÉDIGÉ | Hypothèse d'entité « Alpha Paiements » (établissement de paiement) à valider ; transposition française de NIS2 non adoptée au 6 octobre 2026 |
| Recommandations à la direction (arbitrages D1–D11, go/no-go, feuille de route) | RÉDIGÉ | À relire par l'équipe |
| Runbook de reprise | RÉDIGÉ | À répéter sur le PC Hôte |
| Script de sauvegarde/restauration | TESTÉ sur 2 clusters PostgreSQL 16 locaux | Preuve : `docs/evidence/pra/rehearsal-local-pg16.md` ; pas sur le PC Hôte |
| RTO réel | NON MESURÉ | Budget théorique 52–67 s pour une cible de 60 s |

Ces documents s'appuient sur l'architecture et les essais réels de l'équipe ; les chiffres à confirmer sont signalés comme tels.
