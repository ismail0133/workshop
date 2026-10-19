# Secrets locaux — phase 1

Depuis la racine : `python3 scripts/prepare_secrets.py`. Le script génère des valeurs aléatoires et une paire RSA dans runtime/, sans afficher ni remplacer les valeurs existantes. Ce dossier est ignoré par Git et Docker build : permissions 0700, fichiers privés 0600. Ne jamais le publier ni le partager dans une archive du projet.

`docker compose run --rm db-tools python scripts/stage_secrets.py` copie les secrets nécessaires dans des volumes distincts pour Auth et Payment, avec propriétaire UID 10001 et permissions 0400. Payment ne reçoit pas la clé JWT privée. Les API utilisent des rôles PostgreSQL restreints ; les identifiants administratifs restent réservés au bootstrap et aux migrations.

Les secrets Compose sont des fichiers, pas un coffre chiffré. La conception future SOPS/age nécessite les destinataires de l’équipe ; .sops.yaml.example reste un modèle non opérationnel. Ne jamais versionner une clé privée age.

Les mots de passe des comptes fictifs sont dans runtime/demo_<nom>_password. Chaque environnement génère ses propres valeurs. Voir le README racine pour l’ordre de démarrage et le seed idempotent.
