# Revue de durcissement à exécuter avant démonstration

Vérifier depuis le PC Attaquant que seul WAF:8443 est accessible ; les API, DB, métriques, Loki, Grafana, Ollama et runner ne doivent pas répondre directement. Depuis l’hôte, confirmer Grafana loopback. Inspecter les montages, UID, capabilities, rootfs, secrets et ports avec la configuration résolue Compose. Ne pas monter le socket Docker dans les workloads.

Tests d’autorisation : accès aux comptes d’autrui, JWT expiré/mauvaise audience/algorithme, token utilisateur sur endpoint interne, runner avec token ML, commande inconnue, IP hors inventaire, règle visant passerelle, retrait d’une règle étrangère. Tous doivent être refusés et tracés sans fuite de secret. Tester le WAF avec requêtes de test locales autorisées et les parcours légitimes pour les faux positifs.

Ces contrôles sont prévus, pas réalisés en phase 0. Les scanners et tests actifs seront bornés au laboratoire autorisé.
