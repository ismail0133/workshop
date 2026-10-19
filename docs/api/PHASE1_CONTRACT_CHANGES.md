# Contrats phase 1 — changements explicitement demandés

La demande utilisateur de phase 1 prévaut sur le vocabulaire initial : USER remplace CUSTOMER ; ADMIN s’ajoute à OPERATOR ; paiement réussi = SUCCESS au lieu de SUCCEEDED. Le statut SUCCEEDED des **actions de remédiation** reste inchangé. Aucun déploiement ni donnée de phase 0 n’existait à migrer ; la première migration démarre directement sur ces valeurs. L’ancien SQL est conservé dans docs/source/phase0_schema.sql.

USER possède/consulte ses comptes et paie depuis ses comptes. OPERATOR et ADMIN peuvent s’authentifier et consulter `/api/auth/me`, mais n’ont aucun accès bancaire global ni route d’administration dans cette phase. Le rôle technique VALIDATOR reste réservé aux comptes synthétiques ; les paiements USER vers ces comptes sont également refusés pour préserver la validation future.

Les comptes désactivés et changements de rôle sont vérifiés en DB à chaque requête protégée (projection autorisée id/role/is_active pour Payment). Cela renforce la proposition initiale de révocation seulement à expiration. JWT reste RS256, 900 s, issuer/audience figés. Le traitement des montants est strict : ni flottant, booléen, chaîne ou valeur nulle.

L’ingress WAF arrive dans une phase ultérieure. En phase 1, `docker-compose.dev.yml` publie seulement 127.0.0.1:8001 et 127.0.0.1:8000 pour l’essai local. Aucune publication PostgreSQL. En base Compose, aucune API n’est publiée. Les requêtes de test sont internes aux réseaux Docker. Pas de TLS/WAF prétendu actif.

Les schémas OpenAPI live sont exposés par chaque service sur `/openapi.json` et Swagger `/docs`. Le contrat d’ensemble `openapi.json` conserve aussi les composants futurs. Les réponses d’erreur centralisées ont code/message/request_id, avec 413 ajouté pour la limite de corps16 KiB. L’auth utilise login JSON (pas formulaire OAuth).
