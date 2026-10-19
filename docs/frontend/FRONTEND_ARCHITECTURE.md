# Architecture frontend — phase 2

## Périmètre réellement livré

SPA React 19 / TypeScript stricte, Vite 7 et Tailwind 4. React Router 7 gère la navigation, TanStack Query 5 les lectures et invalidations, React Hook Form + Zod 4 les formulaires, Recharts 3 les graphiques, Lucide les icônes. Les versions exactes sont dans frontend/package-lock.json. Node 24 LTS est la référence Docker ; aucune modification du Node système.

Le projet existant est conservé. Aucun changement du code des API ou du schéma bancaire n’est requis. Les contrats exportés auth.openapi.json et payment.openapi.json ont été lus et confrontés aux routes réelles. Les schémas Zod de frontière HTTP reprennent leurs champs, unités et enums ; aucune route hypothétique de phase 0 n’est appelée.

## Organisation

- src/main.tsx : providers Query/Auth/Toast/Router.
- src/App.tsx : routes publiques, garde d’authentification et garde de rôles bancaires.
- src/components/ui : boutons, champs, cartes, badges, alertes, skeleton, empty/error, modal natif et notifications.
- src/components/layout : sidebar responsive, topbar, utilisateur, breadcrumbs.
- src/components/charts : graphique des montants réellement chargés, groupés par jour UTC.
- src/features/auth, dashboard, accounts, payments, transactions, monitoring, security, ai, recovery : pages et composants métier.
- src/hooks/useData.ts : listes paginées et santé des API.
- src/services/http.ts et api.ts : HTTP centralisé, DTO validés, timeout et adaptation d’erreurs.
- src/types/api.ts : types dérivés de schémas Zod ; src/utils/money.ts : conversion stricte en centimes et formatage.
- src/styles/global.css : tokens visuels et composants ; tests colocalisés et e2e/ pour Playwright réel.

## API et proxy

| URL navigateur | Destination effective |
|---|---|
| /api/auth/login, /api/auth/me | Auth Service, chemin conservé |
| /api/accounts et /api/accounts/{id} | Payment API, chemin conservé |
| /api/payments et /api/payments/{id} | Payment API, chemin conservé |
| /status/auth | Auth /health |
| /status/payment | Payment /health/ready |
| /health | Santé statique du serveur frontend |

Nginx et Vite utilisent la même correspondance. Les aliases /status appartiennent au proxy, pas à de nouveaux endpoints backend. Les routes /internal et /metrics ne sont pas relayées. Nginx désactive les retries upstream, les access logs et le cache des réponses. Timeout client 12 s ; timeout proxy 15 s. Une réponse JSON incompatible produit une erreur explicite, pas une carte alimentée avec des valeurs inventées.

VITE_API_BASE_URL configure le préfixe navigateur à la compilation, vide par défaut. AUTH_UPSTREAM/PAYMENT_UPSTREAM configurent le proxy Vite via l’environnement du processus ; FRONTEND_AUTH_UPSTREAM/FRONTEND_PAYMENT_UPSTREAM alimentent le proxy Nginx via Compose à l’exécution. Nginx résout les noms Docker périodiquement pour supporter la recréation des conteneurs API. Les valeurs upstream sont une configuration d’infrastructure de confiance, jamais une entrée utilisateur. Aucune clé n’est embarquée dans les variables VITE_.

## Identité et autorisations

Login JSON puis GET /api/auth/me obligatoire avant ouverture de la session. JWT bearer en mémoire, jamais localStorage/sessionStorage/cookie. Expiration après 900 s, vérification lors du retour de focus, HTTP 401 déclenchant déconnexion et effacement du cache. Le backend reste l’autorité sur les droits ; le frontend ajoute uniquement des gardes d’UX.

USER et VALIDATOR peuvent ouvrir les vues bancaires ; les données retournées sont filtrées par le backend. ADMIN et OPERATOR voient une vue générale de supervision, sans agrégation de comptes d’autrui. Aucun annuaire de destinataires n’existe : l’UUID doit être fourni explicitement. VALIDATOR conserve l’isolation des comptes synthétiques.

Le rechargement déconnecte volontairement. Pas de refresh token ni de cookie HttpOnly fictif. Le stockage en mémoire n’est pas une défense absolue contre XSS. CSP self pour scripts/connections, frame-ancestors none, X-Frame-Options DENY, nosniff et Referrer-Policy no-referrer sont servis par Nginx. Les styles inline restent permis pour les graphiques. TLS et WAF ne sont pas implémentés dans cette phase.

## Paiements

L’entrée décimale française/anglaise est analysée comme chaîne, décomposée en euros et centimes, puis validée entre 1 et 10^12 centimes. Les booléens, exponentielles, négatifs, zéros et fractions à plus de deux décimales sont refusés. Le corps API contient un entier amount_minor et EUR ; aucun arrondi implicite.

Une nouvelle intention obtient crypto.randomUUID. Son corps immuable et sa clé sont stockés par utilisateur dans sessionStorage avant envoi. Un stockage indisponible bloque l’envoi plutôt que de perdre la capacité de reprise. Une Map de promesses déduplique les appels simultanés ; le bouton est bloqué pendant l’envoi. Aucun retry automatique de mutation.

Une interruption laisse le résultat inconnu et conserve la même intention, y compris après navigation/reconnexion dans le même onglet. Un succès ou rejet métier validé supprime l’intention locale et invalide comptes/historique/détail de compte. Le backend assure l’idempotence durable. Une fermeture d’onglet perd le stockage local ; aucune garantie de déduplication entre deux intentions indépendantes de deux onglets. L’UI demande de vérifier l’historique avant tout abandon d’opération incertaine. Aucun statut bancaire PENDING/FAILED n’est inventé : seulement SUCCESS/REJECTED.

## Données et observabilité

Les listes utilisent limit=20 et le curseur opaque next_cursor. Les pages supplémentaires se chargent explicitement. Les KPI et graphiques agrègent seulement les pages récupérées et l’indiquent ; pas de total global supposé, pas de filtre serveur inventé. Le graphique compte chaque transaction visible une fois et ne représente pas un historique de solde. Les erreurs ne sont pas remplacées par de faux zéros.

Health checks polling 30 s ; PostgreSQL seulement indirect via readiness des API. Aucun CPU/RAM affiché sans source. Security, Detection, Recovery et Assistant sont des interfaces préparées : NOT CONFIGURED, valeurs absentes, pas d’alertes simulées. Timeline typée pour huit états ; historique et références du chat ont des composants réutilisables mais pas de données ni d’appel RAG.

## Conteneurisation et validation

Docker multi-stage : Node 24 bookworm-slim, puis nginx-unprivileged stable-alpine. Digests multiarch figés ; ARM64 exécuté, AMD64/Windows non exécutés. Nginx UID 101, racine RO, tmpfs /tmp, capacités supprimées, 128 MiB et 0,25 CPU. Le template runtime est rendu dans /tmp pour rester compatible avec le filesystem RO. Le frontend rejoint edge/app, sans accès au réseau data. Le port 8088 est publié uniquement dans l’overlay dev sur loopback.

Vitest couvre frontières HTTP, argent, intention, formulaires, rôles, expiration, pagination et navigation. Playwright interagit avec le vrai React derrière Nginx, perd volontairement la réponse d’un paiement réellement committé, réessaie et vérifie SQL. Captures desktop 1440 px et mobile 390 px inspectées visuellement ; test d’absence de débordement global. Traces/vidéos désactivées pour éviter d’enregistrer les identifiants de connexion. Voir le rapport pour les résultats exacts.

Références techniques consultées : [Vite](https://vite.dev/guide/), [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview), [Tailwind Vite](https://tailwindcss.com/docs/installation/using-vite). Les versions réellement installées et leur build priment sur une supposition de compatibilité.
