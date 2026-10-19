# Vérification de stack et environnement

Distinguer quatre niveaux : **exécutable vérifié localement**, **support documenté**, **choix de conception**, **essai encore nécessaire**. Aucune compatibilité globale du projet n’est déclarée après une simple commande --version.

## Audit local réellement réalisé

| Élément | Résultat | Conséquence |
|---|---|---|
| Architecture/macOS | arm64, macOS26.6.2 build25G83 | Cible développement ARM64 |
| CPU/RAM | Apple M5, 17179869184 octets (16 Gio), sysctl après autorisation | Confirmé ; budget serré |
| Disque | df : volume926 Gio, 743 Gio disponibles | Espace local suffisant au contrôle ; pas audit SSD Windows |
| Python | 3.14.3 /opt/homebrew/bin/python3 ; python3.12 non trouvé | Installer ultérieurement 3.12 dédié ou conteneur après autorisation applicable |
| Node/npm | 25.9.0 / 11.12.1 | Manifeste cible Node24 ; pas de build effectué |
| Docker Desktop | app4.69.0, CLI29.4.0, Compose5.1.1 | Moteur inaccessible (socket absent) ; aucun déploiement testé |
| Git | 2.50.1 Apple Git155 | Disponible ; dépôt non initialisé dans phase 0 |
| Ollama/Ansible | Exécutables non trouvés dans PATH | Pas de version ni test ; absence globale non affirmée |

Sorties brutes : `docs/ENVIRONMENT_AUDIT.json`. Un environnement **de validation documentaire** `.venv-phase0` a été créé à côté du projet avec Python3.14 existant ; il ne constitue pas le runtime Python3.12 cible. Seuls validateurs JSON/YAML/OpenAPI/SQL y ont été installés après autorisation réseau, aucune installation système.

## Sources primaires et décisions

| Élément | Vérification documentaire / décision | Validation restante |
|---|---|---|
| Docker Mac | [Docker Mac](https://docs.docker.com/desktop/setup/install/mac-install/) propose Apple Silicon | Démarrage moteur, quotas et images natives |
| Windows | [Docker Windows](https://docs.docker.com/desktop/setup/install/windows-install/) et [WSL2](https://docs.docker.com/desktop/features/wsl/) | Version Windows supportée, PA, pare-feu, conservation IP |
| Node | [Node releases](https://nodejs.org/en/about/previous-releases) ; Node24 LTS retenu plutôt que version locale25 | Résolution npm et lockfile sur cible |
| Frontend | [Vite](https://vite.dev/guide/), [Tailwind Vite](https://tailwindcss.com/docs/installation/using-vite) | Vite7/Tailwind4/React19 candidats ; ne pas mélanger recette Tailwind3 ; build/test requis |
| Python/FastAPI/SQLAlchemy | Python3.12 demandé, stack cohérente REST/ORM | Résoudre requirements sous3.12, Alembic et tests concurrents |
| Ansible | [Documentation officielle](https://docs.ansible.com/projects/ansible/latest/os_guide/intro_windows.html) : contrôleur non natif Windows, conteneur Linux retenu | Image runner, playbooks et contrôleur Unix à développer/tester |
| WAF | [Image officielle CRS](https://github.com/coreruleset/modsecurity-crs-docker) fournit Nginx/ModSecurity et parcours multiarch | Tag/digest, UID, logs, contrôleur et IP non vérifiés |
| ML | [IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html) retenu, score bas atypique | Entraînement/test réel ; aucun F1 connu |
| FAISS | [Wheels PyPI](https://pypi.org/project/faiss-cpu/1.15.1/) montrent distributions plusieurs plateformes | Résolution de versions exactes sous Python3.12 ARM64/AMD64 |
| Ollama | [FAQ officielle](https://docs.ollama.com/faq) : GPU Docker macOS non disponible ; natif Mac retenu | Inférence et RAM ; PC IA option si surcharge |
| RAG | [qwen2.5:1.5b](https://ollama.com/library/qwen2.5:1.5b), [embedding](https://ollama.com/library/nomic-embed-text) | Corpus français, qualité et latence testés ultérieurement |
| Logs | [Alloy fichiers](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/) ; [Loki](https://grafana.com/docs/loki/latest/setup/install/) | Parsing logs WAF, permissions et rétention à tester |

Sources consultées le 19 octobre 2026. Les images du Compose sont des **références candidates**, pas « dernières versions sécurisées » ni digests validés. Ne pas tirer de conclusion de sécurité de leurs numéros. Avant livraison : sélectionner patchs supportés, résoudre dépendances, audit, figer lockfiles et digests puis recette des deux architectures. Les dépendances Python peuvent évoluer ensemble (LangChain notamment) : requirements.in indique des plages, sans prétendre qu’elles ont été résolues.

## Alternatives cohérentes EPSI

SOC Python intégré plutôt qu’un SIEM lourd : explicitement admis p.5, conserve corrélation réelle. SOPS plutôt que Vault : alternative EPSI autorisée. Modèle1.5B plutôt que8B : respecte plafond et réduit RAM. Ollama sur PC IA plutôt que supprimer RAG : option matérielle EPSI. Si WAF Nginx est trop difficile, image Apache ModSecurity CRS multiarch à examiner avec adaptation documentée ; **ne pas remplacer le WAF par un simple proxy**. Aucune alternative ne supprime Compose, Ansible, Prometheus/Grafana/Loki, React/Tailwind, ML, Ollama/LangChain/RAG ou gouvernance.
