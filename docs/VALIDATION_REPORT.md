# Résultats de validation — phase 0

Date : 19 octobre 2026. **63 contrôles documentaires réussis** avec `../.venv-phase0/bin/python scripts/validate_phase0.py`, exécuté depuis le projet. Sortie complète conservée dans `validation-output.txt`.

| Vérification | Résultat réel | Portée |
|---|---|---|
| Treize documents demandés | Présents, non vides | Existence documentaire |
| JSON, YAML, TOML | Parsing réussi | Syntaxe des configurations et manifestes |
| OpenAPI 3.1 | openapi-spec-validator : valide, 19 chemins | Structure normative ; aucun endpoint exécuté |
| Événements | JSON Schema 2020-12 et exemple validés, formats inclus | Exemple fictif conforme, pas détection réelle |
| PostgreSQL | pglast : 18 instructions parsées, six tables | Syntaxe SQL ; aucune connexion/migration |
| DTO et colonnes | User/Account/Payment/Incident/IncidentEvent/Action correspondent aux colonnes | Pas de test des invariants ACID/concurrence |
| Mermaid | Onze blocs, onze .mmd identiques, six tables ER et huit états cohérents | Revue sémantique manuelle + contrôles de structure ; **pas de parseur Mermaid ni rendu graphique exécuté** |
| Traçabilité | 80 identifiants uniques, pages 1–12 valides, tous associés à un protocole | Couverture revue sur les 12 pages ; pas de conformité fonctionnelle déclarée |
| Liens Markdown | Liens locaux existants | Navigation documentaire |
| Compose | `docker compose --profile foundation config --quiet` : code 0 | Validation hors daemon, 5 composants configurés + 9 planifiés |
| Exposition/privilèges initiale | Grafana loopback seul port publié, aucun socket Docker | Revue du Compose, pas de test réseau actif |

## Revue de cohérence effectuée

Les routes demandées existent dans OpenAPI ; JWT/roles, montants, UUID et états concordent avec le DDL et les documents. Les paiements et décisions sont persistants ; les refus/retries sont décrits. La compensation possède related_action_id vers son blocage ; le contrôleur conserve les actions retirées pour éviter leur réactivation. Le contrôle SQL de rejet exige un failure_code non nul (un CHECK avec NULL seul serait insuffisant).

Le catalogue comprend explicitement le collecteur Alloy et le runner ; le SOC n’est pas présenté comme un service absent du Compose cible. Le diagramme de contrôle passe par API jobs, et les flux Loki/Prometheus sont séparés. Le WAF dérivé et son contrôleur sont des travaux futurs identifiés ; l’image CRS seule n’est pas présentée comme un moteur de remédiation prêt à l’emploi.

Le budget mémoire total, les phases et leur charge (124 h-personne plus 16 h de marge) ont été rapprochés des tableaux. Le planning conserve les cinq piliers et tous les rendus EPSI. Les valeurs ML/RTO/RAG sont des objectifs, jamais des mesures acquises.

## Non vérifié en phase 0

Daemon Docker indisponible ; aucun pull/build/start. Compatibilité effective images ARM64/AMD64, versions applicatives résolues, permissions runtime, healthchecks natifs, parsing Alloy/PromQL/Loki par leurs binaires, rendu Mermaid et passage Windows restent à tester. Aucun paiement, transaction SQL, ML entraîné, assistant RAG, scénario offensif ou remédiation n’a été exécuté. Le SQL syntaxiquement valide peut encore nécessiter des ajustements après tests transactionnels.

Outils utilisés : Python3.14 existant dans venv de validation, PyYAML6.0.3, jsonschema4.26.0, openapi-spec-validator0.9.0, pglast8.7 ; Compose5.1.1. Ces outils de contrôle sont séparés du futur runtime Python3.12 de l’application.
