# Remédiation autonome SC-01

Objectif de conception : reprise en moins de 60 s depuis la première dégradation mesurée. Ce délai n’est ni une exigence chiffrée EPSI ni une performance acquise. Le Clip Chrono EPSI doit durer au plus 60 s ; prévoir une marge et mesurer la chaîne tôt.

## Machine à états

| Origine → destination | Condition et effet atomique | Délai maximal |
|---|---|---|
| DETECTED → ANALYZING | Anomalie persistée, worker prend le verrou incident | 2 s |
| ANALYZING → CONFIRMED | Politique SC-01 satisfaite, preuves horodatées persistées | 8 s |
| ANALYZING → REJECTED | Preuves insuffisantes, source ambiguë, faux positif ou métriques absentes ; raison conservée | 8 s |
| CONFIRMED → REMEDIATING | Action autorisée persistée dans la file ; policy_version figée | 2 s |
| CONFIRMED → RECOVERY_FAILED | Configuration invalide, file indisponible après reprise DB ou deadline | 5 s |
| REMEDIATING → VALIDATING | Ack SUCCEEDED du contrôleur WAF + résultat runner authentifié | 15 s par essai |
| REMEDIATING → RECOVERY_FAILED | 2 essais épuisés, action interdite ou deadline globale dépassée | 35 s |
| VALIDATING → RECOVERED | Tous les critères métier et télémétriques ci-dessous sont acquis | 15 s nominal |
| VALIDATING → RECOVERY_FAILED | Paiement incohérent/échec, télémétrie périmée, timeout | 20 s |

États terminaux : REJECTED, RECOVERED, RECOVERY_FAILED. Aucune réouverture ; nouvelle anomalie crée un nouvel incident (lien parent), après cooldown de 60 s si même source déjà filtrée. Un incident actif supprimé par erreur n’est jamais recréé silencieusement. Deadline globale incident : 60 s après DETECTED ; le RTO métier inclut aussi le délai précédant la détection. Un retry peut faire dépasser l’objectif RTO : consigner l’échec de cible, ne pas changer le chronomètre.

## Politique SC-01 v1

Conditions **toutes** nécessaires : anomalie ML versionnée sur au moins 2 évaluations consécutives ; données collectées depuis moins de 10 s ; erreurs 5xx > 5 % ou p95 > 500 ms sur la fenêtre 15 s (seuils de laboratoire à calibrer) ; au moins 20 requêtes WAF dans cette fenêtre ; source IPv4 unique représentant au moins 70 % des requêtes vers les routes Payment ; au moins 10 request_id de cette source corrélables avec les logs applicatifs et au moins un statut 5xx ou durée > 500 ms ; IP présente dans l’inventaire des machines d’essai autorisées, distincte des IP hôte/passerelle/client légitime/IA ; preuve que l’IP TCP est préservée, horloges synchronisées à ±1 s.

Le ML déclenche l’investigation ; ces règles qualifient la cause et bornent l’action. Aucun diagnostic certain n’est inféré du score seul. IP ambiguë, exposition externe ou preuves manquantes : REJECTED avec motif, aucune action. L’authenticité du token interne est obligatoire, elle ne suffit pas à autoriser la remédiation.

## Catalogue fermé et exécuteur

| Action | Autorisation | Paramètres | Effet |
|---|---|---|---|
| BLOCK_SOURCE_IP | Policy Engine SC-01 uniquement | action_id, target_ip /32, ttl_seconds=120, policy_version, fencing_token, request_hash | Bloquer cette source sur routes Payment, conserver les autres clients |
| REMOVE_SOURCE_BLOCK | Compensation de règle incorrecte attestée par validation ou expiration gérée localement | même identité d’action de retrait, référence blocage, IP | Retirer uniquement la règle créée par le système ; ne pas vider toutes les protections |

Le worker ne reçoit jamais de nom de playbook, commande shell, chemin ou template de l’utilisateur/LLM. Le runner mappe les deux enums vers deux playbooks locaux RO. Exécution Ansible avec argument array, `extra_vars` JSON typé, pas de shell interpolé. IP validée par parseur, appartenance à l’inventaire exact et exclusions ; pas de CIDR large. Le contrôleur WAF répète les validations : ne pas faire confiance au runner seul.

Contrôleur WAF à implémenter dans le conteneur WAF : socket Unix 0660 groupe dédié, aucune écoute TCP. `PUT /v1/blocks/{action_id}` reçoit l’IP/TTL/fencing_token/hash, `GET /v1/actions/{action_id}` réconcilie un résultat, `DELETE /v1/blocks/{block_action_id}` retire la règle avec identité propre de compensation (X-Action-ID) et fencing token de cette action. Le job de retrait porte `related_action_id`, FK vers le blocage du même incident ; le contrôleur vérifie ce lien et conserve un tombstone du blocage retiré/expiré pour empêcher sa réactivation par un ancien retry. Fencing monotone par action. Journal durable de résultats, même action+hash = même résultat ; même id/différent hash = 409 ; token inférieur = 409. Générer uniquement un fragment issu d’un template constant, tester `nginx -t`, remplacer atomiquement puis signaler le processus maître du **même conteneur**. Le contrôle n’a aucun droit sur les autres conteneurs ni sur l’hôte.

Nginx non-root utilise ports hauts ; UID contrôleur distinct lorsque possible, droit de signal limité au maître du WAF. Les chemins de config modifiables, socket et journal sont des volumes propres au WAF. Aucun montage `/`, `/var/run/docker.sock`, PID hôte, mode privileged ou accès sudo général. Si l’image officielle ne permet pas ce montage contrôlé, produire une image dérivée testée en phase 5 ; c’est un travail identifié, pas une fonctionnalité supposée de l’image CRS.

## Réessais, erreurs et traçabilité

Au plus 2 tentatives par action ; backoff 2 s puis réconciliation avant nouvel essai. Retry uniquement transport/timeout ; 400/401/403/409 de validation = arrêt sans répéter. Bail 15 s, exécution 10 s, un job à la fois. En cas de crash, Incident Service recherche les baux expirés et le runner interroge le contrôleur avant mutation. Les actions sont idempotentes par UUID/hash ; le fencing token empêche un ancien worker de réappliquer une commande après reprise.

Stocker policy_version, model_version, features, evidence refs, anciens/nouveaux états, timestamps, IP, action_id, SHA256 config avant/après, code Ansible, durée et résultat de paiement. Masquer les secrets dans stdout/stderr et borner à 16 KiB. L’échec du stockage de preuve empêche la clôture. Les événements sont append-only pour le rôle d’exploitation.

## Validation fonctionnelle

Après ack WAF, attendre deux scrapes post-action. Dans une fenêtre de 10 s **entièrement post-action**, readiness 200, p95 < 500 ms et 5xx < 1 %, au moins 5 requêtes légitimes. L’absence de requêtes n’est pas un taux d’erreur nul. Effectuer un nouveau paiement de 1 centime entre deux comptes synthetic dédiés, key `recovery-<incident_uuid>` ; consulter sa transaction SUCCEEDED via l’API, lire les deux soldes avant/après et vérifier débit/crédit exact et somme inchangée. Aucun autre processus ne touche ces comptes pendant la validation. Le compte validator ne paie jamais vers un compte customer.

Si le paiement est déjà committé mais la réponse est perdue, rejouer la même clé ; la preuve conserve la transaction initiale de validation, jamais un second débit. RECOVERED exige readiness, mesures, reçu WAF et référence transaction réussie. Le validateur passe par HTTPS WAF avec CA connue ; pas de `verify=false`.

Si une nouvelle règle bloque les clients légitimes : compensation REMOVE_SOURCE_BLOCK une fois, incident RECOVERY_FAILED (pas RECOVERED après simple rollback). TTL expire automatiquement même si runner est arrêté ; vérifier paiement après expiration et signaler une rechute dans un nouvel incident. L’arrêt de sécurité humain reste possible, mais invalide une prétention de reprise autonome pour cet essai.
