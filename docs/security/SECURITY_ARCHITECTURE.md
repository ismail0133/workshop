# Architecture de sécurité

Références EPSI p.5–6 et p.11. SC-01 est une dégradation de disponibilité maîtrisée ; il ne prétend pas remédier à une exfiltration ou à une compromission. Toutes les opérations resteront sur des machines explicitement autorisées du groupe.

## Frontières et privilèges

WAF seul point d’entrée 8443 sur l’IP du PA. PostgreSQL/Loki/Prometheus et API internes ne sont jamais publiés ; Grafana uniquement loopback hôte. WAF bloque `/internal/`, `/metrics` et toute route inconnue. Ne pas se fier au seul cloisonnement réseau pour les accès internes : tokens distincts ML/runner, vérifiés en temps constant, droits séparés, rotation après chaque démonstration. Aucun token interne dans le frontend.

JWT RS256 TTL 15 min, iss=resilience-alpha-auth, aud=resilience-alpha, sub UUID et role. Algorithme fixé, aucune acceptation de `none`, validation exp/iss/aud. Auth seul détient la clé privée ; API ont la clé publique montée RO. MVP sans refresh token ; nouvelle authentification à expiration. Désactivation de compte effective au plus tard à expiration (limite documentée). Argon2id pour mots de passe fictifs, essais login limités 5/min/source et réponse générique 401. L’opérateur ne peut pas émettre une commande de remédiation via l’API publique. CORS même origine, CSP restrictive, aucune insertion HTML de réponse RAG.

RBAC : USER → ses comptes et transactions ; OPERATOR → incidents et assistant ; VALIDATOR → uniquement ses deux comptes synthetic. Interdire l’énumération : compte ou paiement hors périmètre renvoie 404. GET incidents réservé OPERATOR. Les tokens internes utilisent un schéma séparé ; aucun JWT utilisateur accepté en remplacement.

## WAF et durcissement

ModSecurity + OWASP CRS, règles activées après test de faux positifs sur login/paiements. Limite corps 16 KiB, timeouts bornés, règles SQLi/XSS, TLS local, en-têtes sûrs. SC-01 utilise une surcharge de requêtes valides qui n’est pas automatiquement corrigée par CRS : le blocage de source décidé par le moteur est observable. Ne pas désactiver le WAF pour provoquer artificiellement l’incident. Un plafond de sécurité global protège le poste ; calibrer l’API pour que la dégradation soit mesurable avant ce plafond.

Images figées par digest après validation ARM64/AMD64, non-root pour services applicatifs, rootfs RO, tmpfs /tmp, cap_drop ALL, no-new-privileges, quotas CPU/RAM/PIDs, aucune API d’administration publique. Les exceptions de l’image PostgreSQL ou WAF seront documentées et testées, pas copiées aveuglément. Dépendances verrouillées et auditées au gel du code. Rétention limitée ; aucun password/JWT/body sensible dans les journaux.

## SOPS

Chiffrer les secrets YAML avec SOPS/age ; clé age gardée hors dépôt et hors archive. Fichiers déchiffrés dans `infrastructure/secrets/runtime/` ignoré par Git, droits 0700 répertoire/0600 fichiers. Compose secrets sont des fichiers montés : ils ne constituent pas un chiffrement au repos. Variables `*_FILE` pour DB/Grafana/JWT/tokens. Aucune valeur par défaut exploitable dans `.env.example`. `.sops.yaml.example` attend les destinataires réels, aucun destinataire inventé. Contrôle d’archive avant livraison : pas de `.env`, clés, runtime, dumps réels ni logs de credentials.

## Fonction SOC intégrée

Loki stocke, Grafana visualise ; cela ne suffit pas à constituer une corrélation SOC. Le module SOC d’Incident Service exécute une requête bornée sur les événements WAF/application, groupe par IP et fenêtre, joint request_id, conserve les références de preuve et la version de règle. Liste de règles dans `security/siem/README.md`. Montrer sur Security Events le signal, la source, les preuves et le motif de décision ; ne pas afficher des événements simulés comme réels.

Menaces principales : falsification X-Forwarded-For (écrasement et IP TCP), vol token ML (corrélation indépendante et catalogue fermé), injection dans playbook (types et templates constants), prompt injection (RAG sans outils), compromission runner (socket WAF seulement), perte DB (point unique, sauvegardes testées hors SC-01), falsification logs (volumes producteurs séparés, export des preuves).

Les tests attendus et les règles d’arrêt figurent dans [SC-01](../../security/attack-scenarios/SC-01.md) et [remédiation](REMEDIATION_DESIGN.md). Aucun trafic offensif ni scan réseau n’a été exécuté en phase 0.


Mise à jour phase 1 : rôles USER/OPERATOR/ADMIN (VALIDATOR technique conservé), paiement SUCCESS. Voir `docs/api/PHASE1_CONTRACT_CHANGES.md` depuis la racine. Les descriptions de phases futures restent des cibles.
