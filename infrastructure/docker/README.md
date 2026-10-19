# Conteneurisation — phase 1

`backend.Dockerfile` fournit les cibles auth, payment et tools avec une base Python 3.12 figée par digest multiarchitecture. Les dépendances utilisent requirements.lock. Auth et Payment s’exécutent avec UID 10001 ; tools réalise les opérations administratives ponctuelles.

Le Compose racine démarre PostgreSQL et les deux API sur réseaux internes, avec health checks et volumes persistants. L’overlay dev ajoute uniquement les ports loopback des API et un réseau bridge permettant leur accès depuis le Mac. L’overlay test s’utilise dans le projet Compose distinct resilience-alpha-test. PostgreSQL ne publie aucun port.

Les configurations d’observabilité préparées restent sous profil foundation ; les autres services prévus sont documentés dans x-planned-services. Elles ne constituent pas une intégration complète déjà testée. Voir le README racine et PHASE_1_REPORT.md pour les commandes et preuves.
