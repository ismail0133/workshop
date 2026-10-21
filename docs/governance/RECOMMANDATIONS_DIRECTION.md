# Note de conseil à la direction — arbitrages, recommandations, feuille de route

Version 1.0 — 21 octobre 2026. Destinataire : la direction de « Alpha Paiements » (entreprise fictive) et le commanditaire fictif. Chaque affirmation renvoie à un élément vérifiable du dépôt ; ce qui n'est pas encore mesuré est dit.

## 1. Le message en trois points

1. **Le paiement est le seul service que nous protégeons à tout prix** (RTO visé 60 s, aucune transaction confirmée perdue). L'assistant IA, le tableau de bord et Grafana sont secondaires : leur panne ne doit jamais retarder la reprise.
2. **La reprise autonome est bornée volontairement** : deux actions possibles, une seule adresse, 120 s, preuves corroborées. Nous préférons ne rien faire plutôt que de couper des clients légitimes.
3. **Le prototype démontre une chaîne crédible, pas une conformité.** Il reste un point unique de défaillance (PostgreSQL), une visibilité de la source incomplète sous Docker Desktop, et une gestion des identités sans MFA. Nous recommandons de financer ces trois points avant toute industrialisation.

## 2. Ce que nous avons choisi de protéger, et pourquoi

| Priorité | Service | Raison | Coût d'un arrêt |
|---|---|---|---|
| 1 | Paiement et sa base | Cœur du métier ; erreur = perte financière | `λ × T × (c_retard + c_support) + pénalités` ; 60 tentatives par minute à 1/s, 6 000 à 100/s |
| 2 | Authentification | Sans elle, aucun nouveau paiement | Idem, pour les nouvelles sessions |
| 3 | Détection et reprise | Réduit la durée de l'arrêt 1 | Allonge T si elle tombe |
| 4 | Supervision et assistant | Confort et explication | Négligeable sur la disponibilité |

Le commanditaire doit fixer `c_retard`. Tant qu'il ne l'a pas fait, nous ne chiffrons pas en euros.

## 3. Registre des arbitrages

| ID | Question | Options examinées | Choix | Pourquoi (élément vérifiable) | Dans un contexte industriel |
|---|---|---|---|---|---|
| D1 | Que reprend-on ? | Disponibilité seule ; disponibilité + compromission | **Disponibilité** (SC-01) | EPSI p.3 : ne pas confondre restauration et correction d'une compromission ; PCA/PRA S4 | Ajouter un processus de réponse à compromission avec forensique |
| D2 | Qui agit ? | Humain valide ; automate libre ; automate borné | **Automate borné** | Catalogue fermé de 2 actions, 1 IP /32, TTL 120 s, fencing token (REMEDIATION_DESIGN) | Approbation humaine pour toute action à large effet ; automatisme réservé aux actions réversibles |
| D3 | Comment détecter ? | Seuil sur CPU ; ML ; ML + corrélation SOC | **ML (Isolation Forest) puis corroboration SOC** | Le ML ne décide pas seul : 8 caractéristiques, 2 fenêtres consécutives, puis ≥ 20 requêtes, IP dominante ≥ 70 %, ≥ 10 request_id joints | Données réelles de production, évaluation continue et plan de réentraînement |
| D4 | Quel rôle pour l'IA générative ? | Dans la boucle de décision ; hors boucle | **Hors boucle** | Le RAG n'a ni outil, ni SQL, ni secret ; il lit et cite (tests : aucune route d'exécution, rôle OPERATOR) | Revue de sécurité du modèle et des prompts avant toute délégation d'action |
| D5 | Sur quoi bloque-t-on ? | IP ; User-Agent | **User-Agent aujourd'hui, IP en cible** | Docker Desktop/WSL2 masque l'IP source (`client_ip` en 172.x) ; blocage UA : 200→403 en ~2 s, mais **trivial à contourner** | IP réelle préservée de bout en bout (équilibreur, proxy protocol) |
| D6 | Combien de bases ? | Une seule ; réplication | **Une seule** | Budget RAM de l'hôte (768 Mio) ; sauvegarde + restauration vers instance distincte répétée | Réplication synchrone, archivage continu, site de secours |
| D7 | Gestion des secrets | Vault ; SOPS + age | **SOPS + age** (ADR-11) | Autorisé par le sujet ; plus léger en quatre jours | Coffre géré avec rotation et audit |
| D8 | Orchestration | Docker Compose ; Kubernetes | **Compose** | Imposé par le sujet ; reproductible par script | Orchestrateur avec politiques réseau et déploiement progressif |
| D9 | Taille du modèle de langage | 1,5 G ; 7–8 G paramètres | **`qwen2.5:1.5b`** | Mémoire de l'hôte ; plafond du sujet 8 G ; qualité en français **à mesurer** (recette de 10 questions) | Modèle plus grand sur matériel dédié, évalué sur un jeu de questions métier |
| D10 | Observabilité | Elastic ; Prometheus + Loki + Grafana | **Prom/Loki/Grafana** | Imposé et plus léger | SIEM d'entreprise et astreinte |
| D11 | Données | Réelles ; synthétiques | **Synthétiques uniquement** | EPSI p.2/p.7 ; aucune donnée bancaire réelle | Données réelles sous gouvernance, minimisation et conservation |

## 4. Critères de décision vérifiables (go / no-go)

Nous recommandons à la direction de n'engager l'industrialisation que si, sur le PC Hôte et sur trois répétitions indépendantes :

| Critère | Seuil | Source de la preuve | Statut |
|---|---|---|---|
| Reprise sans intervention humaine | 3 essais sur 3 | Journal d'essai, vidéo continue | À produire |
| RTO | ≤ 60 s sur chaque essai | t0 → t3 | À produire (budget théorique 52 à 67 s, PCA/PRA §6) |
| Transactions confirmées perdues | 0 | Contrôle avant/après | À produire |
| Détection : rappel et précision | ≥ 0,8 chacun sur le test gelé (cible expérimentale) | `ml_app evaluate` sur données réelles | À produire (les chiffres synthétiques ne comptent pas) |
| Fausses alertes en trafic normal | ≤ 1 par 10 min | Validation | À produire |
| Restauration de base | Contrôle comptable identique, 3 fois | `scripts/pra_backup_restore.sh` | Logique répétée ; PC Hôte à produire |

Si un critère n'est pas atteint, nous le disons et nous réduisons la revendication, nous ne changeons pas la mesure.

## 5. Gouvernance des composants d'IA

- **Provenance** : modèles publics exécutés en local (Isolation Forest entraîné par l'équipe ; `qwen2.5:1.5b` et `nomic-embed-text` via Ollama). Aucun envoi de données hors du poste ; aucune donnée personnelle réelle.
- **Intégrité** : modèle ML signé par SHA-256 (manifeste + empreinte épinglée), refus de charger un artefact modifié, version de bibliothèque vérifiée ; index documentaire vérifié par hachage.
- **Supervision humaine** : le ML déclenche une investigation, la politique est déterministe ; le LLM n'agit jamais. Les réponses citent leurs sources et s'abstiennent sous seuil.
- **Confidentialité** : les questions posées à l'assistant ne sont pas journalisées (longueur et empreinte courte seulement) ; aucun secret dans le corpus (liste blanche + détection de motifs).
- **Qualité** : évaluation avant mise en service (jeu de test gelé pour le ML, recette de 10 questions pour le RAG) et alerte si les données manquent. Un modèle entraîné sur une machine n'est pas valable sur une autre sans contrôle.
- **Responsabilité** : l'automate agit sous une politique versionnée dont chaque décision est tracée ; une intervention humaine invalide la prétention d'autonomie.
- **Réglementation** : la qualification vis-à-vis du règlement européen sur l'IA n'est pas traitée dans ce dossier ; à examiner avant industrialisation.

## 6. Feuille de route de transformation

| Horizon | Actions | Effort | Risque traité |
|---|---|---|---|
| 0 à 3 mois | Visibilité de l'IP source ; trois restaurations de base sur l'hôte cible ; MFA et révocation de jeton ; registre des fournisseurs ; qualification juridique de l'entité | M | R1, R5, R7, R9 |
| 3 à 12 mois | Réplication PostgreSQL et archivage continu ; SIEM et astreinte ; processus de notification (4 h / 72 h / 1 mois) ; test indépendant ; formation ; évaluation continue du modèle ML | L | R5, R11, art. 17 à 19 DORA |
| 12 mois et plus | Site de secours ; TLPT si l'entité est désignée ; revue annuelle EBIOS ; stratégies de sortie des prestataires | L | Concentration, art. 26 et 28 à 30 |

## 7. Pilotage : indicateurs

RTO mesuré (médiane, maximum) ; délai de détection ; fausses alertes par heure ; nombre d'interventions humaines par incident ; transactions incohérentes après reprise (cible 0) ; durée de restauration et écart comptable ; fraîcheur des fenêtres de données du détecteur ; taux d'abstention de l'assistant.

## 8. Contribution et traçabilité

La répartition des rôles et le journal individuel des contributions de l'équipe sont à renseigner dans le dossier final (EPSI §7.1). Les décisions D1 à D11 sont reliées aux ADR de `docs/architecture/ARCHITECTURE.md`, à l'analyse EBIOS (`docs/ebios/EBIOS_RM.md`) et au PCA/PRA (`docs/pca-pra/PCA_PRA.md`).
