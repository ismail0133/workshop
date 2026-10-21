# Limites connues — gouvernance, reprise et conformité

Version 1.0 — 21 octobre 2026. À présenter telle quelle au jury : ce qui n'est pas prouvé est dit.

## 1. Environnement et réseau

- **IP source masquée.** Docker Desktop/WSL2 masque l'adresse source : le WAF voit `client_ip` en 172.x. Le blocage actuel porte sur le User-Agent, qu'un attaquant change trivialement. Le filtrage par IP, prévu par la politique SC-01, n'est démontré qu'après test avec deux clients réels.
- **Limite de connexion partagée.** Pour la même raison, la limite de login de Nginx est commune à tous les clients ; la limite du backend a été relevée (`AUTH_LOGIN_RATE_LIMIT`).
- **Disque externe.** Un disque externe déconnecté empêche Docker et PostgreSQL de redémarrer : Docker est installé sur le SSD interne pour la démonstration.


## 2. Reprise et continuité

- Point unique de défaillance : un seul PostgreSQL, sans réplication ni site de secours.
- RTO ≤ 60 s : objectif non mesuré sur le PC Hôte ; le budget théorique des délais maximaux va de 52 à 67 s.
- La restauration de base n'a été répétée que sur deux instances PostgreSQL 16 locales avec des données synthétiques.
- Une attaque distribuée, derrière un NAT commun, ou la compromission d'une identité ne sont pas couvertes par la reprise automatique.


## 4. Sécurité et conformité

- Pas de MFA ; le JWT, conservé en mémoire côté navigateur, reste exposé à un script XSS.
- Aucun audit indépendant ; pas de TLPT ; pas de registre des prestataires TIC.
- La plateforme n'envoie aucune notification d'incident à une autorité et n'applique pas les seuils de classification de DORA.
- Les cotations de risque sont qualitatives et attendent la validation du coach.

