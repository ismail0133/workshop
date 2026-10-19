# Plan de tests et revues

Protocoles à exécuter dans les phases 1–10. Aucun résultat métier n’est déclaré en phase 0. `scripts/validate_phase0.py` vérifie les artefacts de conception séparément. Chaque essai crée un dossier run_id avec date, machine, commit, config, données, résultats et limites.

| ID | Protocole et résultat attendu | Statut |
|---|---|---|
| AC-01 | Revue cinq domaines et grille jury avec matrice complète, aucune obligation supprimée. | À exécuter |
| AC-02 | Chaque membre explique sa contribution et les limites ; vérifie sorties IA intégrées. | À exécuter |
| API-01 | Valider OpenAPI puis, après implémentation, réponses/erreurs/RBAC des endpoints avec client généré ; aucun écart schéma/SQL. | À exécuter |
| DEL-01 | Revue humaine documentée : Jeudi : recette, injection défaillances, Clip ; gel 17 h, remise avant 23 h 59. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-02 | Revue humaine documentée : Vendredi matin : jury live ; pas de production pendant soutenance ; 10 min locales : 5 présentation/démo et 5 questions. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-03 | Revue humaine documentée : Dossier Workshop2026-M2-G<n> et noms prescrits. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-04 | Revue humaine documentée : Dossier.pdf : architecture/flux/composants/incident/détection/reprise/essais/sécurité/risques/PCA-PRA/gouvernance/contributions ; Dossier environ 8–12 pages hors annexes, pas quota. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-05 | Revue humaine documentée : Pres.pptx adapté à pitch court, ne remplace pas démo. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-06 | Revue humaine documentée : VidChrono.mp4 ≤60 s, séquence continue attaque externe/anomalie/réaction/reprise, pas coupe masquant correction. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-07 | Revue humaine documentée : Code.zip structuré : sources, infra, attaque, ML, tests, API, README déploiement/vérification, aucun secret clair. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEL-08 | Revue humaine documentée : Si sélection : environ 3 semaines plus tard, Teams depuis PC Hôte, 10 campus ; 5 min : 1 min démarche et introduction individuelle anglais, 1 min clip, 3 min live ; National /70 : pitch 10, clip 15, live 25, technique 10, gouvernance 10. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| DEP-01 | Installation propre depuis dépôt sur PC Hôte ; services séparés et intégration complète. | À exécuter |
| DEP-02 | Relance après arrêt contrôlé, volumes conservés, procédure reproductible par second membre. | À exécuter |
| DEP-03 | Relever deux machines distinctes, ressources attaquant, réseau et absence de défensif sur celui-ci. | À exécuter |
| DEP-04 | Audit Windows admin/virtualisation/WSL2/4 cœurs/16 Go/50 Go ; capture versions et mémoire en charge. | À exécuter |
| DEP-05 | Si délestage : seul Ollama/interface sur PC IA, accès depuis hôte seul. | À exécuter |
| DEP-06 | PA Windows actif, réseau groupe inventorié ; deux IP sources distinctes visibles au WAF. | À exécuter |
| DOC-01 | Revue documentaire : conformité des limites/options et cohérence des sources. | À exécuter |
| GOV-01 | Revue valeur métier/arrêt et hypothèses de coût avec responsable gouvernance. | À exécuter |
| GOV-02 | Revue cinq ateliers EBIOS adaptés, risques et traitement par coach/équipe. | À exécuter |
| GOV-03 | Mesurer RTO et absence de perte confirmée SC-01 ; PRA hors scénario distingue ses limites. | À exécuter |
| GOV-04 | Vérifier sources NIS2/DORA et relier enjeux aux preuves ; ne pas revendiquer certification. | À exécuter |
| GOV-05 | Pour chaque arbitrage mémoire/complexité/sécurité, donner preuve ou hypothèse et propriétaire. | À exécuter |
| ML-01 | Charger artefact entraîné, inférer sur métriques collectées ; preuve modèle et scores, pas if/else seul. | À exécuter |
| ML-02 | Transmettre anomalie réelle deux fois ; ack idempotent et un seul incident actif. | À exécuter |
| ML-03 | Évaluer sur session indépendante ; publier matrice confusion, FP, délais, taille datasets et limites. | À exécuter |
| OBS-01 | Afficher valeurs avant/pendant/après ; rapprocher panneaux des séries/logs réels et chronologie API. | À exécuter |
| OBS-02 | Vérifier scrape 5 s, unités/features, quota et absence de données ; ne pas traiter métrique manquante comme zéro. | À exécuter |
| OBS-03 | Émettre logs WAF/app corrélés, les retrouver dans Loki ; tester rotation/rattrapage et trou détecté. | À exécuter |
| ORG-01 | Revue humaine documentée : Équipe de cinq ; quatre/six seulement si coach autorise. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-02 | Revue humaine documentée : Responsables identifiés, contributions individuelles et décisions partagées ; Note locale = (individuelle + 2×collective)/3 ; suivi 5 critères ×4. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-03 | Revue humaine documentée : Difficulté matérielle signalée au coach ; pas de contournement sécurité. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-04 | Revue humaine documentée : IA générative et outils publics autorisés ; aucun starter fourni. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-05 | Revue humaine documentée : Lundi : consortium, postes/réseau, interfaces/architecture/risques et validation coach. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-06 | Revue humaine documentée : Mardi : Compose/Ansible, microservices, ML, Red Team et dossier NIS2/DORA. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-07 | Revue humaine documentée : Mercredi : intégration WAF/SIEM/AIOps/remédiation/dashboard et premiers essais. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-08 | Revue humaine documentée : Edusign dans 15 premières minutes de chaque demi-journée. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-09 | Revue humaine documentée : Espaces groupe, accès selon coach, locaux/équipements propres et en bon état. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| ORG-10 | Revue humaine documentée : Présence à toutes soutenances locales et retransmission finale. Conserver validation, preuve ou compte rendu daté. | À exécuter |
| PAY-01 | Créer un paiement via WAF puis lire transaction et soldes ; vérifier propriété, ACID et idempotence concurrente. Attendu : un débit/crédit exact, aucune donnée réelle. | À exécuter |
| RAG-01 | 10 questions corpus, 3 hors corpus et 3 injections ; références réelles, abstention et aucune action. | À exécuter |
| RAG-02 | Inspecter manifeste modèle ≤8B, budget RAM et latence sur hôte ; Ollama reste local. | À exécuter |
| REC-01 | Déclencher SC-01 externe et suivre automatiquement jusqu’à paiement réussi ; trois répétitions Windows, zéro correction humaine. | À exécuter |
| REC-02 | Injecter échec paiement ou métriques absentes après ack WAF ; RECOVERED doit être impossible ; contrôler delta des comptes synthetic. | À exécuter |
| REC-03 | Exécuter playbook fermé, rejouer même action, simuler timeout après application ; une règle active, réconciliation et audit. | À exécuter |
| SC-01 | Inventaire/allowlist, client externe borné, effet métier observable et arrêt automatique ≤45 s. | À exécuter |
| SC-02 | Rejouer protocole identique trois fois avec run_id/config/modèle/données conservés. | À exécuter |
| SEC-01 | Revue des seeds, prompts, sources, logs et archive ; aucune donnée authentique/confidentielle ni secret partagé. | À exécuter |
| SEC-02 | RAG ne possède aucun token/volume/socket d’administration ; prompt injection ne déclenche rien. | À exécuter |
| SEC-03 | Inspecter UID, montages RO, capabilities, RBAC et expiration JWT ; tests négatifs. | À exécuter |
| SEC-04 | CRS actif, trafic légitime accepté, filtrage IP ciblé, configuration erronée refusée et rollback testé. | À exécuter |
| SEC-05 | ML + journaux frais source dominante → preuve SOC ; XFF usurpé/NAT commun/preuve absente → abstention. | À exécuter |
| SEC-06 | Déchiffrement local autorisé SOPS, permissions fichiers et archive sans secret en clair. | À exécuter |
| SEC-07 | Action hors catalogue/IP interdite/token invalide/bail périmé → refus ; aucun accès Docker/hôte. | À exécuter |
| SEC-08 | Vérifier cible exacte et pas de redirection ; arrêt Ctrl-C/durée/disconnexion et signalement coach. | À exécuter |
| SEC-09 | Depuis attaquant autorisé vérifier absence de publication DB/gestion ; seul port WAF accessible. | À exécuter |
| UI-01 | Compiler React/Tailwind ; parcours login/comptes/paiement/incident, erreurs et chargements ; aucun panneau factice. | À exécuter |

## Cas complémentaires indispensables

- REC-04 : doublons et crash worker après application WAF, avant callback : pas de double action, bail/fencing respectés.
- REC-05 : runner indisponible, WAF config invalide ou timeout : RECOVERY_FAILED, jamais RECOVERED fictif.
- PAY-02 : cinquante demandes même clé, deux demandes concurrentes au dernier solde, transferts croisés et crash avant/après commit.
- SEC-10 : règle expirée après 120 s, état WAF réconcilié et éventuelle rechute créée comme nouvel incident.
- CHAOS-01 : injecter perte Loki/Prometheus/runner dans laboratoire ; le paiement continue si possible, remédiation s’abstient faute de preuve. Défaillances préparées jeudi, sans pertes de volumes.
