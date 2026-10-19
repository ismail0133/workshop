# Étude de faisabilité

## Conclusion conditionnelle

Le périmètre est réalisable comme démonstrateur en quatre jours **avec cinq personnes travaillant en parallèle**, une machine Windows disponible dès le lundi et un scénario validé tôt. Ce n’est pas une promesse de production industrielle. Le chemin critique est : visibilité IP → dégradation réelle → collecte exploitable → ML → corrélation → action WAF → paiement de validation. L’intégration WAF/runner est le risque le plus élevé ; réserver du temps avant de perfectionner l’interface.

Six composants applicatifs et huit composants techniques au maximum, dont un runner et un collecteur ajoutés explicitement. Le SOC reste un module d’Incident Service ; aucune file externe, Elastic Stack, cluster ou orchestrateur supplémentaire. Le RAG reste obligatoire, même s’il est hors chemin de reprise.

## Capacité mémoire et disque

| Groupe | Plafond initial |
|---|---:|
| Frontend + cinq services applicatifs | 2 304 MiB |
| Postgres + Prometheus + Grafana + Loki | 2 176 MiB |
| WAF + Alloy + runner | 1 024 MiB |
| Ollama | 3 072 MiB |
| Total composants | 8 576 MiB (~8.38 Gio) |

Sur Mac : proposition VM Docker 7 Gio pour composants hors Ollama (5.38 Gio de plafonds), Ollama natif jusqu’à 3 Gio ; il reste environ 6 Gio pour macOS/IDE et marges. Le surcoût VM, les caches, les buffers et les charges de compilation rendent cette estimation incertaine. Sur Windows 16 Go : VM jusqu’à 10 Gio si Ollama local, marge hôte réduite ; délestage IA facultatif à préférer si saturation mesurée. Ne pas considérer la somme des limites comme une mesure RSS ni comme un gage de stabilité. Pas de modèle 7/8B par défaut.

Disque Mac réellement observé : volume 926 Gio, 743 Gio disponibles au contrôle (valeurs df arrondies). Réserver 20–30 Gio images/cache/datasets/modèles et borner rétention. Le PC Hôte doit respecter au moins 50 Go libres, 4 cœurs et 16 Go (EPSI p.6), non vérifiés ici.

## Compatibilité et portabilité

Mac M5 ARM64 vérifié ; Python installé 3.14.3 ne correspond pas à cible 3.12. Utiliser un environnement 3.12 dédié ou image Python 3.12, sans modifier Python système. Node 25.9 présent ; manifeste cible Node 24 LTS. Docker Desktop/Compose présents mais daemon inaccessible : aucune image n’a été démarrée. Ollama/Ansible non trouvés dans PATH. Voir `architecture/TECHNOLOGY_VALIDATION.md` et audit JSON pour versions.

Windows : choisir une version encore prise en charge par Docker Desktop, confirmer WSL2 et virtualisation. Le sujet autorise Windows 10/11 mais cela ne garantit pas le support de toute édition/build Windows 10 par la version actuelle de Docker. Préférence Windows 11 supporté. Sources et scripts dans filesystem Linux WSL, chemins relatifs, LF, noms sensibles à la casse. Ansible tourne dans conteneur Linux ; pas de dépendance à un contrôleur Windows natif. Pas de volumes absolus Mac dans les configurations.

FAISS/scikit-learn : wheels ARM64/AMD64 et Python 3.12 à vérifier sur les versions résolues ; le catalogue PyPI montre des builds multiarchitecture, sans prouver notre ensemble de dépendances. Utiliser Debian slim plutôt qu’Alpine pour réduire les complications binaires. WAF officiel fournit une piste multiarch ; le manifeste exact et l’adaptateur doivent être construits/testés. `requirements.in` et package.json ne sont pas des lockfiles.

## Risques priorisés

| Risque | Probabilité / impact / criticité | Réduction / propriétaire / échéance |
|---|---|---|
| Pas de PC Windows/PA autorisé | Inconnue / bloquant / critique | Inventaire réel + coach lundi ; le Mac ne remplace pas implicitement ce poste ; infra |
| IP clients masquées par Docker | Moyenne / blocage ciblé impossible / critique | Test deux clients lundi ; diagnostic ingress autorisé, ne pas bloquer passerelle ; cyber/infra |
| Contrôleur WAF non prêt | Moyenne / aucune action autonome / critique | Prototype socket + Ansible + config testée lundi/mardi ; cyber/infra |
| Charge sans dégradation ou filtre inefficace | Moyenne / live échoue / critique | Calibration bornée dès lundi sur prototype ; pas d’augmentation illimitée ; dev/cyber |
| Temps d’intégration sous-estimé | Élevée / livraison partielle / critique | API figées, chaîne minimale mercredi, gel jeudi ; coordinateur |
| Mémoire saturée | Moyenne / services instables / élevée | Plafonds, 1.5B, modèle à la demande, PC IA si nécessaire ; infra/IA |
| ML peu fiable ou données pauvres | Moyenne / FP/FN / élevée | Sessions distinctes, charge normale variée, validation puis test gelé ; IA |
| Dépendances/images incompatibles | Moyenne / démarrage impossible / élevée | Résoudre sous 3.12 et Node24, lockfiles/digests, smoke ARM64/AMD64 ; chaque responsable |
| Remédiation double ou mal ciblée | Faible à moyenne / interruption légitime / élevée | Déduplication, bail/fencing, allowlist, TTL, rollback ; incident/cyber |
| RAG français insuffisant ou lent | Moyenne / critère IA incomplet / moyenne | 10 questions, références et abstention, index préalable ; IA |
| Perte PostgreSQL ou volume | Faible / données perdues / élevée | Volume durable + sauvegarde/restauration testée hors SC-01 ; infra |
| Livrables ou gouvernance négligés | Moyenne / points perdus / élevée | Responsable dédié, rédaction continue, revue 4 fichiers jeudi ; gouvernance |

## Minimum conforme et compromis

Conserver un seul parcours EUR, trois rôles, un scénario SC-01, une politique + compensation, 8 features, un modèle ML, un assistant à questions indépendantes, un SOC déterministe, cinq vues techniques et un dashboard React simple. Pas de refresh tokens, temps réel WebSocket, historique RAG, multi-devise ou deuxième attaque. Ces retraits concernent des extensions non imposées ; **aucun des cinq piliers ni aucune technologie EPSI n’est supprimé**.

Critères de passage à l’implémentation : architecture et contrats disponibles (phase 0), validation utilisateur pour phase 1 ; les risques de plateforme sont ensuite des jalons bloquants de démonstration. Si lundi soir PC/PA ou scénario restent impossibles, prévenir le coach et consigner l’écart ; ne pas prétendre à la conformité.
