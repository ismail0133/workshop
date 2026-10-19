# Plan d’implémentation — après validation de phase 0

Aucune phase ci-dessous n’a commencé. Les numéros ordonnent les dépendances logiques ; plusieurs domaines avancent en parallèle. Estimation : cinq personnes × quatre journées de 7 h ≈140 heures-personne ; allocation ci-dessous 124 h, marge 16 h. Il ne s’agit pas d’un engagement de résultat. Les noms des membres et le groupe sont à renseigner.

## Phases et critères

| Phase | Objectifs / fichiers à créer | Dépendances | Tests et acceptation | Risques / résultat / effort |
|---|---|---|---|---|
| 1 Backend et PostgreSQL | app/main.py, routers/models/schemas dans auth/payment ; Alembic env + migrations initiale/grants ; seeds fictifs ; Dockerfiles | Phase 0 validée, Python3.12, Docker actif | PAY-01/02, API-01, droits DB ; paiement ACID et replay identique | Concurrence/secrets ; socle auth/transfert réel ; 18 h |
| 2 Frontend React | src/main.tsx, routes login/comptes/paiement/incidents/assistant, client API, vite.config.ts, CSS Tailwind | Contrats phase 0 ; API phase 1 pour intégration | UI-01, Vitest parcours/erreurs, build ; affichage données réelles | Scope UI trop large ; banque et supervision minimale ; 12 h |
| 3 Observabilité | Instrumentation middleware, logs JSONL, compléter scrapes/Alloy, 5 JSON dashboards Grafana | Services phase 1 et logs WAF préliminaires | OBS-01/02/03 ; métriques/latences/logs corrélables | Unités/labels/absence logs ; données utilisables par ML ; 10 h |
| 4 Détection ML | collect.py, train.py, evaluate.py, detector.py, manifestes datasets/modèle, outbox | Prometheus réel phase 3 ; scénario calibré | ML-01/02/03 ; splits temporels et résultats publiés | Pas assez de données/dérive ; anomalie réelle versionnée ; 12 h |
| 5 Incident et remédiation | incident manager/soc/policy/worker/validator ; runner Dockerfile/worker ; playbooks block/remove ; contrôleur WAF socket | Contrats0, DB1, télémétrie3, événement4 ; WAF6 développé en parallèle | REC-01..05, SEC-07 ; refus arbitraire, idempotence, paiement prouve reprise | Chemin critique ; chaîne autonome bornée ; 20 h |
| 6 Cybersécurité | WAF Dockerfile dérivé/config/routes/CRS ; scénario borné sur attaquant ; inventaire réseau ; secrets SOPS ; durcissement | Réseau Windows dès lundi ; phases1/3/5 | SC-01/02, SEC-01..10, DEP-03/06 ; IP distinctes et filtrage efficace | NAT/charge/privilèges ; laboratoire défensif et scénario réel ; 14 h |
| 7 Ollama et RAG | ingestion/retrieval/chat, index manifest/metadata JSON, modèle local, routes API | Docs0 ; auth1 ; Ollama disponible | RAG-01/02 ; réponses citées et abstention, aucune action | Mémoire/français ; assistant documentaire ; 8 h |
| 8 Intégration | Compose complet, overlays Mac/Windows/IA, lockfiles/digests, scripts setup/relaunch, config pare-feu documentée | 1–7 | DEP-01/02/04/05 ; recette sur hôte final propre | ARM64/AMD64/chemins ; système reproductible ; 8 h |
| 9 Tests | pytest unit/integration/recovery, Vitest, e2e, scripts chaos bornés, preuves run_id | Intégration8 ; tests unitaires démarrent dès1 | Catalogue tests, trois REC-01 Windows, RTO/RPO/erreurs, contrôles secrets | Instabilité et temps ; résultats reproductibles ; 10 h |
| 10 Livraison | Dossier.pdf, Pres.pptx, VidChrono.mp4, Code.zip nommés ; contribution de chacun ; finaliser EBIOS/PCA/NIS2-DORA | Preuves9 ; rédaction gouvernance dès lundi | DEL-01..08, GOV-01..05, contrôle archive et vidéo ≤60 s | Dossier générique/secret oublié ; quatre rendus + live ; 12 h |

Tests unitaires pertinents : paiements montants/ownership/idempotence/concurrence, transitions et baux, règles interdites, validateur faux succès, features manquantes, abstention RAG. Ne pas attendre phase 9 pour ces invariants. Gouvernance a son propre fil de travail transversal, pas une tâche abandonnée au dernier soir.

## Répartition parallèle proposée

DEV : auth/payment/DB puis React ; INFRA : Compose/observabilité/runner ; IA : collecte/ML puis RAG ; CYBER : WAF/scénario/SOC avec responsable incident ; GOUV/INTÉGRATION : Incident Service, contrats, EBIOS/PCA et dossier. Le responsable IA aide au frontend assistant une fois l’inférence stable. Chaque interface a un propriétaire producteur et consommateur ; revue quotidienne des contrats à midi et intégration commune à 16 h. Cette répartition est une proposition à confirmer selon compétences, pas une affectation de personnes non connues.

## Sprint EPSI (lundi–jeudi, soutenance vendredi)

| Jour | Matin | Après-midi | Jalon de fin |
|---|---|---|---|
| Lundi | Groupe/RACI, audit Windows/PA, validation architecture/interfaces et risques par coach | phase 1, premiers métriques ; prototype ingress/WAF/Ansible ; démontrer IP distinctes et faisabilité charge bornée | Contrats figés, paiement minimal, hypothèse SC-01 testable ; signaler blocages coach |
| Mardi | Backend/frontend, Compose/observabilité, collecte train ; cybersécurité et scripts bornés | Modèle initial + validation ; runner/action WAF ; RAG minimal ; dossier NIS2/DORA | Chaque composant testable, logs et événements communs |
| Mercredi | Intégrer ML→SOC→policy→Ansible→WAF→validator ; dashboard | Premier REC-01 complet, corriger, tester Windows, RAG et risques résiduels | Chaîne autonome réelle et première preuve ; pas seulement endpoints isolés |
| Jeudi | Recette, chaos engineering borné, trois répétitions, RTO/RPO, mémoire, archive propre | Capture Clip, dossier/PPT, répétition ; **gel code 17 h**, vérification finale et remise **avant 23 h 59** | Quatre fichiers + démonstrateur stables |
| Vendredi matin | 5 min présentation/live + 5 min questions | Présence à toutes soutenances et résultats | Aucun développement pendant soutenance |

Dates calendaires à confirmer : le PDF dit octobre 2026 et lundi–vendredi, sans date précise. La semaine du 19 octobre ne doit pas être affirmée comme échéance officielle sans confirmation campus. Finale si sélection : environ trois semaines plus tard, Teams, cinq minutes (1 démarche/introductions anglaises, 1 clip, 3 live).

## Livraison et contribution

Dossier `Workshop2026-M2-G<n>/` : `Workshop2026-M2-G<n>-Dossier.pdf`, `Workshop2026-M2-G<n>-Pres.pptx`, `Workshop2026-M2-G<n>-VidChrono.mp4`, `Workshop2026-M2-G<n>-Code.zip`. PDF conseillé 8–12 pages hors annexes, pas quota. Dossier final couvre architecture/flux/rôles/incident/ML/remédiation/tests/sécurité/EBIOS/PCA-PRA/NIS2-DORA/arbitrages et contributions individuelles. ZIP inclut code/config/scripts ML et attaque bornée/tests/API/README ; exclut secrets en clair. Aucun de ces rendus finaux n’est prétendu produit en phase 0.

Tenir journal individuel : date, auteur, domaine, contribution, commit ou preuve, problème résolu, revue reçue. Edusign dans les 15 premières minutes de chaque demi-journée, respect espaces/équipements et présence aux soutenances/retransmission finale (EPSI p.11).
