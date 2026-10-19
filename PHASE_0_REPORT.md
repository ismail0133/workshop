# Rapport final — phase 0

Date : 19 octobre 2026. Statut : **architecture et initialisation documentaire réalisées ; aucune fonctionnalité implémentée**. La phase 1 attend la validation utilisateur.

## Cahier des charges et couverture

Sujet EPSI officiel de 12 pages lu intégralement ; schéma matériel et tableaux p.6/9/10/12 également inspectés visuellement. Le rapport secondaire de 43 pages n’a pas été confondu avec la source officielle. Registre/empreinte/extraction conservés dans docs/source. La matrice recense 80 obligations, recommandations, options et éléments de cadre avec pages, responsables, preuves, tests et statuts.

Exigences décisives : cinq domaines, technologies prescrites, données fictives, attaque réelle contrôlée depuis second poste, collecte/détection/décision/action automatiques, paiement nouveau prouvant la reprise ; PC Hôte Windows/WSL2 et PA mobile Windows ; gouvernance liée aux essais. Délais : gel jeudi 17 h, remise avant 23 h59, vendredi 10 min local (5+5). Finale conditionnelle et règles d’organisation incluses dans traçabilité. La couverture de conception n’est pas une conformité d’exécution.

## Travaux livrés

Arborescence demandée créée avec ajout explicite Alloy (collecte logs), documentation RAG/observabilité et runner Ansible prévu. Treize documents demandés présents, plus spécifications de remédiation, scénario SC-01, EBIOS/PCA-PRA/conformité, protocole de tests et sources.

Onze diagrammes Mermaid cohérents avec les services cibles, disponibles en DIAGRAMS.md et fichiers .mmd. OpenAPI3.1, événements JSON Schema, exemple d’anomalie explicitement fictif. PostgreSQL : six tables, contraintes/index/FK, rôles conceptuels, idempotence/ACID/concurrence documentées, SQL initial non exécuté. Compose initial limité au socle technique et extension de topologie ; manifestes de dépendances candidats, configurations observabilité/secrets/Ansible et Makefile de validation.

## Environnement réellement détecté

ARM64, Apple M5,16 Gio ; macOS26.6.2. Volume926 Gio dont743 Gio libres au contrôle. Python3.14.3, Node25.9.0, npm11.12.1, Git2.50.1. Docker Desktop4.69.0, CLI29.4.0, Compose5.1.1 ; moteur inaccessible (socket absent). Python3.12, Ollama et Ansible non trouvés dans PATH ; cela ne prouve pas leur absence de tout le disque. Sorties dans ENVIRONMENT_AUDIT.json.

Aucune installation système. Seul un venv local de validation documentaire a été créé avec le Python existant ; validateurs JSON/YAML/OpenAPI/SQL téléchargés après autorisation. Il ne valide pas la cible applicative3.12. Docker n’a pas été démarré.

## Architecture et décisions

Six composants applicatifs ; SOC et quatre modules d’incident regroupés dans Incident Service. PostgreSQL commun avec trois schémas/rôles séparés. ML Isolation Forest à 8 features réelles ; aucune causalité ni commande décidée par LLM. Runner Ansible non-root sans socket Docker, catalogue fermé, contrôle WAF local via socket Unix. Le contrôleur WAF reste à implémenter explicitement. RECOVERED requiert mesures fraîches et transfert synthetic réussi via WAF. Ollama qwen2.5:1.5b et FAISS pour consultation documentaire sans privilèges. Secrets SOPS/age.

Technologies **retenues sur le plan de conception**, avec sources officielles consultées ; dépendances applicatives et images **non résolues/testées ensemble**. Références Compose candidates, pas de digests ni de certification de sécurité. Les écarts Mac/Windows et alternatives compatibles EPSI figurent dans TECHNOLOGY_VALIDATION et FEASIBILITY_STUDY.

## Risques et décisions à confirmer

1. Identifier le PC Windows conforme, activer PA autorisé et valider réseau avec coach. Le Mac ne satisfait pas à lui seul la cible de démonstration EPSI.
2. Vérifier IP TCP distinctes derrière Docker Desktop avant de s’engager sur filtrage ciblé ; source NAT commune bloque SC-01.
3. Valider image WAF multiarch et adaptateur de contrôle/Ansible sans privilèges hôte.
4. Calibrer dégradation bornée puis détection/réponse réelle ; aucune performance ML/RTO déclarée aujourd’hui.
5. Mesurer RAM totale : budget composants 8 576 MiB dont Ollama 3 072 ; PC IA optionnel si nécessaire.
6. Confirmer membres, numéro de groupe, dates exactes et acceptation des risques résiduels. Équipe de cinq et planning 124 h-personne + 16 h marge sont hypothèses de travail.

## Vérifications et limites

Voir `docs/VALIDATION_REPORT.md` pour commandes et résultats de validation documentaire. Aucun test fonctionnel, migration, scénario offensif, modèle entraîné, génération RAG, déploiement Windows, benchmark ou rendu final workshop n’a été réalisé. Les validations syntaxiques ne remplacent pas ces essais.

## Préparation phase 1

Les responsabilités, contrats et modèle de données sont prêts comme base de développement. **Prêt pour engager la phase 1 après votre validation**, avec préparation Python3.12/Docker et gestion explicite des risques matériels. Pas encore prêt pour exécuter l’application ou démontrer une reprise. Arrêt volontaire à la limite de la phase 0 demandée.
