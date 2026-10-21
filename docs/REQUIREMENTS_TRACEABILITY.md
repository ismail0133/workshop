# Matrice de traçabilité EPSI

Source : sujet officiel de 12 pages, registre `source/SOURCE_REGISTER.md`. Chaque ligne distingue obligation, recommandation, option, condition de finale et cadre d’évaluation. « Conçu — à prouver » ne signifie pas conformité démontrée. Les tests sont définis dans `tests/TEST_PLAN.md`. Les responsabilités humaines restent à nommer.

| Identifiant | Description | Page source | Domaine | Caractère | Composant responsable | Preuve attendue | Test associé | Statut initial |
|---|---|---|---|---|---|---|---|---|
| EPSI-001 | Cinq piliers présents quelle que soit la composition du consortium | 2 | Transverse | Obligatoire | Ensemble | Architecture + preuves par domaine | AC-01 | Conçu — à prouver |
| EPSI-002 | Métier, opérations et données intégralement fictifs ; aucune donnée bancaire réelle | 3 | DEV | Obligatoire | Banque et seeds | Données de démonstration revues | SEC-01 | Conçu — à prouver |
| EPSI-003 | Transaction fictive initiée et traitée dans infrastructure conteneurisée | 3 | DEV | Obligatoire | frontend/payment/postgres | Reçu paiement + Compose | PAY-01 | Conçu — à prouver |
| EPSI-004 | Incident contrôlé depuis un second ordinateur dans le périmètre propre | 3 | CYBER | Obligatoire | PC Attaquant/SC-01 | Inventaire + capture lancement externe | SC-01 | Conçu — à prouver |
| EPSI-005 | Collecte, détection, décision et action sans intervention corrective humaine | 3 | Transverse | Obligatoire | ML/incident/runner | Chronologie complète et vidéo continue | REC-01 | Conçu — à prouver |
| EPSI-006 | Reprise métier vérifiée par nouvelle transaction, API et données cohérentes | 3 | DEV | Obligatoire | Recovery Validator | Transaction + delta soldes + readiness | REC-02 | Conçu — à prouver |
| EPSI-007 | État avant, pendant et après visible ; redémarrage seul insuffisant | 3 | DEV | Obligatoire | React/Grafana | Trois états observables | OBS-01 | Conçu — à prouver |
| EPSI-008 | Attaque principale crédible, reproductible, expliquée, correction efficace | 3 | CYBER | Obligatoire | SC-01 | Protocole + trois répétitions | SC-02 | Conçu — à prouver |
| EPSI-009 | Plusieurs attaques possibles ; distinguer disponibilité, compromission et fuite | 3 | CYBER | Facultatif | Sécurité | Limites explicites ; autres attaques hors MVP | DOC-01 | Pris en compte |
| EPSI-010 | Équipe de cinq ; quatre/six seulement si coach autorise | 4 | Organisation | Obligatoire | Équipe/coach | Composition nominative validée | ORG-01 | Conçu — à prouver |
| EPSI-011 | Responsables identifiés, contributions individuelles et décisions partagées | 4 | Organisation | Obligatoire | Équipe | RACI et journal contributions/ADR | ORG-02 | Conçu — à prouver |
| EPSI-012 | Interface, API, transactions, accès et données intégrés | 4 | DEV | Obligatoire | frontend/auth/payment/postgres | Parcours de bout en bout | PAY-01 | Conçu — à prouver |
| EPSI-013 | Microservices conteneurisés incluant DB, API métier, auth et frontal | 4 | DEV | Obligatoire | Compose | Inventaire conteneurs et explication | DEP-01 | Conçu — à prouver |
| EPSI-014 | Moteur reçoit incidents, engage opérations et suit retour utilisable | 4 | DEV | Obligatoire | incident/runner | État/action/résultat persistés | REC-01 | Conçu — à prouver |
| EPSI-015 | Supervision composants, événements, alertes et reprise | 4 | DEV | Obligatoire | React/Grafana | Dashboard réel | OBS-01 | Conçu — à prouver |
| EPSI-016 | Services REST ou gRPC parmi Node.js, Python/FastAPI ou Go | 4 | DEV | Obligatoire | FastAPI REST | OpenAPI + manifestes | API-01 | Conçu — à prouver |
| EPSI-017 | Dashboard React et Tailwind CSS | 4 | DEV | Obligatoire | frontend | Dépendances + interface compilée | UI-01 | Conçu — à prouver |
| EPSI-018 | Déploiement reproductible sur PC Hôte avec Docker Compose | 4 | INFRA | Obligatoire | infrastructure/docker | Installation propre documentée | DEP-01 | Conçu — à prouver |
| EPSI-019 | Playbooks Ansible pour opérations prévues ; rôle des outils expliqué | 4 | INFRA | Obligatoire | runner/Ansible | Playbook et résultat réel | REC-03 | Conçu — à prouver |
| EPSI-020 | Prometheus collecte métriques réelles utiles à analyse | 4 | INFRA | Obligatoire | Prometheus | Scrapes et features | OBS-02 | Conçu — à prouver |
| EPSI-021 | Grafana visualise état réel | 4 | INFRA | Obligatoire | Grafana | Cinq dashboards interrogent sources | OBS-01 | Conçu — à prouver |
| EPSI-022 | Loki centralise journaux exploitables par analyse | 4 | INFRA | Obligatoire | Loki/Alloy/SOC | LogQL et request_id joints | OBS-03 | Conçu — à prouver |
| EPSI-023 | Elastic Stack non attendu compte tenu de la mémoire | 4 | INFRA | Recommandation | Architecture | Aucun Elastic dans cible | DOC-01 | Pris en compte |
| EPSI-024 | Dépôt explique installation et relance hors machine auteur | 4 | INFRA | Obligatoire | README/plan déploiement | Recette depuis environnement propre | DEP-02 | Conçu — à prouver |
| EPSI-025 | Détecteur véritable ML sur métriques/logs réels, pas if/else seul | 5 | IA | Obligatoire | ml-detector | Artefact entraîné + features et scores | ML-01 | Implémenté ; premiers résultats réels (journal WAF, 1 session) non probants — `docs/ml/ML_REPORT.md` §7 |
| EPSI-026 | Détecteur raccordé supervision et chaîne de remédiation | 5 | IA | Obligatoire | ML/incident | Événement réel accepté | ML-02 | Implémenté : écriture de `ua:Token` dans `blocklist.txt` testée et exécutée sur journal réel (simulation par défaut) ; consommateur Incident absent |
| EPSI-027 | Dossier documente données, préparation, modèle, résultats et limites | 5 | IA | Obligatoire | ML_DESIGN/essais | Splits séparés et métriques test | ML-03 | Rapport rédigé (`docs/ml/ML_REPORT.md`) — métriques réelles à produire |
| EPSI-028 | Assistant local Ollama + LangChain + RAG sur documents équipe | 5 | IA | Obligatoire | rag-service/Ollama | Réponses avec références | RAG-01 | Implémenté, testé hors Ollama — recette réelle à faire |
| EPSI-029 | LLM local ne dépasse pas 8 milliards de paramètres | 5 | IA | Obligatoire | Ollama | Manifeste modèle 1.54B | RAG-02 | Modèle 1.54B configuré — manifeste à relever après pull |
| EPSI-030 | Assistant séparé de l’automate et sans privilèges incontrôlés | 5 | IA | Obligatoire | RAG/RBAC | Montages et tests injection | SEC-02 | Conçu — à prouver |
| EPSI-031 | Au moins un scénario externe produit effet observable réel | 5 | CYBER | Obligatoire | SC-01 | Dégradation mesurée | SC-01 | Conçu — à prouver |
| EPSI-032 | Durcissement composants et accès | 5 | CYBER | Obligatoire | Tous | Revue montages/UID/RBAC | SEC-03 | Conçu — à prouver |
| EPSI-033 | Filtrage applicatif WAF déployé | 5 | CYBER | Obligatoire | waf | CRS actif et filtrage ciblé | SEC-04 | Conçu — à prouver |
| EPSI-034 | SIEM ou fonction SOC intégrée et journaux exploitables | 5 | CYBER | Obligatoire | SOC dans incident/Loki | Règle corrélée avec preuves | SEC-05 | Conçu — à prouver |
| EPSI-035 | Secrets HashiCorp Vault ou SOPS | 5 | CYBER | Obligatoire | SOPS/age | Fichier chiffré et archive sans secrets | SEC-06 | Conçu — à prouver |
| EPSI-036 | Privilèges maîtrisés, remédiation sans administration ouverte | 5 | CYBER | Obligatoire | Runner/contrôleur WAF | Catalogue fermé et refus commandes | SEC-07 | Conçu — à prouver |
| EPSI-037 | Offensif limité au SI fictif et machines autorisées ; campus/groupes/tiers/Internet exclus | 5,11 | CYBER | Obligatoire | SC-01/réseau | Allowlist exacte + arrêt urgence | SEC-08 | Conçu — à prouver |
| EPSI-038 | Services critiques, risques et coût métier d’un arrêt expliqués | 5 | GOUV | Obligatoire | EBIOS/PCA | Scénarios et hypothèses impact | GOV-01 | Conçu — à prouver |
| EPSI-039 | Analyse structurée basée sur EBIOS RM | 5 | GOUV | Obligatoire | Gouvernance | Cinq ateliers adaptés, décisions | GOV-02 | Conçu — à prouver |
| EPSI-040 | Objectifs continuité/reprise cohérents ; PCA/PRA adapté | 5 | GOUV | Obligatoire | PCA/PRA | RTO/RPO et responsabilités/scénarios/risques résiduels | GOV-03 | Conçu — à prouver |
| EPSI-041 | Analyser NIS2/DORA, pertinence et limites prototype | 5 | GOUV | Obligatoire | Conformité | Matrice liée à architecture et essais | GOV-04 | Conçu — à prouver |
| EPSI-042 | Arbitrages et recommandations direction fondés sur éléments vérifiables | 5 | GOUV | Obligatoire | Architecture/risques | ADR + résultats + limites | GOV-05 | Conçu — à prouver |
| EPSI-043 | PC Hôte distinct de PC Attaquant | 6 | INFRA | Obligatoire | Équipe | Inventaire physique | DEP-03 | Conçu — à prouver |
| EPSI-044 | PC Hôte Windows 10/11, admin, virtualisation, Docker Desktop WSL2 | 6 | INFRA | Obligatoire | PC Hôte | Audit réel Windows | DEP-04 | Conçu — à prouver |
| EPSI-045 | PC Hôte minimum 4 cœurs, 16 Go RAM, 50 Go SSD libres | 6 | INFRA | Obligatoire | PC Hôte | Inventaire CPU/RAM/disque | DEP-04 | Conçu — à prouver |
| EPSI-046 | 32 Go, 6–8 cœurs et 100 Go libres offrent plus de marge | 6 | INFRA | Recommandation | PC Hôte | Capacité à confirmer | DEP-04 | Pris en compte |
| EPSI-047 | Attaquant distinct, outils nécessaires, seulement PA groupe, aucun défensif (schéma) | 6 | CYBER | Obligatoire | PC Attaquant | Connexions et processus relevés | DEP-03 | Conçu — à prouver |
| EPSI-048 | Attaquant 8 Go point de départ, 16 Go confort | 6 | CYBER | Recommandation | PC Attaquant | Inventaire | DEP-03 | Pris en compte |
| EPSI-049 | PC IA sur réseau groupe, uniquement modèle local et interface | 6 | IA | Facultatif | Ollama déporté | Inventaire et filtrage hôte seul | DEP-05 | Pris en compte |
| EPSI-050 | Point d’accès sans fil mobile Windows ; réseau du groupe | 6 | INFRA | Obligatoire | PC Hôte/PA | SSID et IP réels ; référence RESILIENCE-G<n>, 192.168.137.0/24 | DEP-06 | Conçu — à prouver |
| EPSI-051 | Publication discernée ; DB/secrets/gestion non exposés réseau pédagogique | 6 | CYBER | Obligatoire | Réseaux/pare-feu | Contrôle ports depuis PC Attaquant | SEC-09 | Conçu — à prouver |
| EPSI-052 | Difficulté matérielle signalée au coach ; pas de contournement sécurité | 6 | Organisation | Obligatoire | Équipe | Registre blocages/validation coach | ORG-03 | Conçu — à prouver |
| EPSI-053 | IA générative et outils publics autorisés ; aucun starter fourni | 7 | Organisation | Facultatif | Équipe | Usage documenté | ORG-04 | Pris en compte |
| EPSI-054 | Vérifier intégrations IA, respecter stack, maîtriser et défendre fonctionnement | 7 | Organisation | Obligatoire | Équipe | Revue code/config et démonstration expliquée | AC-02 | Conçu — à prouver |
| EPSI-055 | Ne transmettre aucun secret, donnée personnelle réelle ou document confidentiel aux IA | 7 | CYBER | Obligatoire | Équipe | Revue sources et usage IA | SEC-01 | Conçu — à prouver |
| EPSI-056 | Lundi : consortium, postes/réseau, interfaces/architecture/risques et validation coach | 7 | Planning | Obligatoire | Équipe | Revue de lancement | ORG-05 | Conçu — à prouver |
| EPSI-057 | Mardi : Compose/Ansible, microservices, ML, Red Team et dossier NIS2/DORA | 7 | Planning | Obligatoire | Équipe | Jalon production | ORG-06 | Conçu — à prouver |
| EPSI-058 | Mercredi : intégration WAF/SIEM/AIOps/remédiation/dashboard et premiers essais | 7 | Planning | Obligatoire | Équipe | Premier REC-01 | ORG-07 | Conçu — à prouver |
| EPSI-059 | Jeudi : recette, injection défaillances, Clip ; gel 17 h, remise avant 23 h 59 | 7 | Planning | Obligatoire | Équipe | Tag gel et réception fichiers | DEL-01 | Conçu — à prouver |
| EPSI-060 | Vendredi matin : jury live ; pas de production pendant soutenance | 7 | Planning | Obligatoire | Équipe | Répétition préalable et démonstration | DEL-02 | Conçu — à prouver |
| EPSI-061 | Dossier Workshop2026-M2-G<n> et noms prescrits | 8 | Livraison | Obligatoire | Livraison | Archive contrôlée | DEL-03 | Conçu — à prouver |
| EPSI-062 | Dossier.pdf : architecture/flux/composants/incident/détection/reprise/essais/sécurité/risques/PCA-PRA/gouvernance/contributions | 8 | Livraison | Obligatoire | Équipe | PDF final et annexes référencées | DEL-04 | Conçu — à prouver |
| EPSI-063 | Dossier environ 8–12 pages hors annexes, pas quota | 8 | Livraison | Recommandation | Équipe | Revue lisibilité | DEL-04 | Pris en compte |
| EPSI-064 | Pres.pptx adapté à pitch court, ne remplace pas démo | 8 | Livraison | Obligatoire | Équipe | Support présenté | DEL-05 | Conçu — à prouver |
| EPSI-065 | VidChrono.mp4 ≤60 s, séquence continue attaque externe/anomalie/réaction/reprise, pas coupe masquant correction | 8 | Livraison | Obligatoire | Équipe | Vidéo et durée vérifiées | DEL-06 | Conçu — à prouver |
| EPSI-066 | Code.zip structuré : sources, infra, attaque, ML, tests, API, README déploiement/vérification, aucun secret clair | 8 | Livraison | Obligatoire | Équipe | Archive extraite et revue | DEL-07 | Conçu — à prouver |
| EPSI-067 | Démonstrateur réel sur machines, incident/pris en charge/reprise observables | 8 | Livraison | Obligatoire | Équipe | Recette live | REC-01 | Conçu — à prouver |
| EPSI-068 | Note locale = (individuelle + 2×collective)/3 ; suivi 5 critères ×4 | 9 | Évaluation | Cadre | Équipe | Leadership/expertise/résolution/coopération/rigueur documentés | ORG-02 | Pris en compte |
| EPSI-069 | Jury /20 : live reprise 5, cinq domaines 4, clip/dashboard 4, gouvernance/pitch 4, dossier/questions 3 | 9 | Évaluation | Cadre | Équipe | Checklist soutenance | AC-01 | Pris en compte |
| EPSI-070 | 10 min locales : 5 présentation/démo et 5 questions | 9 | Évaluation | Obligatoire | Équipe | Répétition chronométrée | DEL-02 | Conçu — à prouver |
| EPSI-071 | Correction humaine pendant live : 0/5 sur axe remédiation | 9 | Évaluation | Cadre | Équipe | Preuve zéro-touch ; limites assumées | REC-01 | Pris en compte |
| EPSI-072 | Si sélection : environ 3 semaines plus tard, Teams depuis PC Hôte, 10 campus | 10 | Finale | Conditionnel | Équipe | Préparation diffusion | DEL-08 | Pris en compte |
| EPSI-073 | 5 min : 1 min démarche et introduction individuelle anglais, 1 min clip, 3 min live | 10 | Finale | Conditionnel | Équipe | Répétition format national | DEL-08 | Pris en compte |
| EPSI-074 | National /70 : pitch 10, clip 15, live 25, technique 10, gouvernance 10 | 10 | Évaluation | Cadre | Équipe | Support de préparation | DEL-08 | Pris en compte |
| EPSI-075 | 20 jurys, classement 1–10 ; votes 12/10/8/6/4/2/1/0/0/0 =43 | 10 | Évaluation | Cadre | Jury national | Cadre consigné, aucune fonctionnalité applicative | DOC-01 | Pris en compte |
| EPSI-076 | Edusign dans 15 premières minutes de chaque demi-journée | 11 | Organisation | Obligatoire | Chaque membre | Émargement | ORG-08 | Conçu — à prouver |
| EPSI-077 | Espaces groupe, accès selon coach, locaux/équipements propres et en bon état | 11 | Organisation | Obligatoire | Chaque membre | Respect consignes et restitution | ORG-09 | Conçu — à prouver |
| EPSI-078 | Présence à toutes soutenances locales et retransmission finale | 11 | Organisation | Obligatoire | Chaque membre | Présence | ORG-10 | Conçu — à prouver |
| EPSI-079 | Expérimentation risquant sortie périmètre interrompue et signalée | 11 | CYBER | Obligatoire | Responsable sécurité | Arrêt urgence et procédure coach | SEC-08 | Conçu — à prouver |
| EPSI-080 | Prototype crédible et vérifié, pas plateforme industrielle exigée ; défendre choix sous contrainte | 11 | Transverse | Cadre | Équipe | Limites et preuves réelles | AC-02 | Pris en compte |

## Couverture et périmètre de la matrice

Pages 1 et 12 : couverture et glossaire, sans nouvelle obligation. Toutes les sections prescriptives p.2–11 sont décomposées ci-dessus, y compris organisation, sécurité, rendus et finale conditionnelle. Les choix de Python 3.12, PostgreSQL, Isolation Forest, FAISS, onze diagrammes et noms des documents proviennent de la demande utilisateur, pas du PDF. Ils sont suivis par le manifeste et les validations de phase 0.

Le PC Mac satisfait l’environnement de développement demandé mais **ne valide pas** EPSI-044/045/050 concernant la démonstration Windows. Aucun test métier ni déploiement de conformité n’est réputé passé en phase 0. La lecture de cette matrice avec le coach le lundi reste une étape de validation humaine prévue par le sujet.
