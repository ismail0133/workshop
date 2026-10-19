# RESILIENCE-ALPHA — Rapport de phase 2

## 1. Bilan et statuts

Le frontend React est développé, connecté aux services de phase 1, conteneurisé et testé. Il est accessible sur **http://127.0.0.1:8088**. Les critères de phase 2 sont validés sur le Mac ARM64. La phase 3 n’a pas commencé.

| Statut | Périmètre |
|---|---|
| IMPLEMENTED | Neuf pages, connexion, session, gardes, design system, comptes/détails, formulaire de virement, historique/détails, graphiques de données chargées, santé, proxy et Docker |
| TESTED | 32 tests Vitest, 2 tests Playwright réels, build Node 24, TypeScript, rendu desktop/mobile, 45 tests backend de non-régression |
| NOT TESTED | Exécution native AMD64/Windows-WSL2, Firefox/Safari, audit WCAG complet, charge prolongée, TLS/WAF et intégrations des phases suivantes |
| BLOCKED | Aucun critère de phase 2 bloqué dans l’environnement local disponible |

**Résultat final : 34 tests frontend réussis, 0 échoué ; 45 tests backend de non-régression réussis, 0 échoué.** Les exécutions répétées ne sont pas additionnées pour gonfler le nombre de tests.

## 2. Fonctionnalités et pages réalisées

| Page | État réel |
|---|---|
| Login | POST auth/login, puis GET auth/me ; erreurs, validation et chargement ; connexion réelle |
| Overview | Soldes/comptes autorisés, transactions chargées, réussites, activité par jour UTC et état Payment API |
| Accounts | Liste paginée, solde/devise/statut, détail via endpoint réel |
| Payments | Validation stricte EUR/centimes/UUID, confirmation, clé d’idempotence, résultat et invalidation des données |
| Transactions | Historique paginé par curseur, statuts SUCCESS/REJECTED, montants, dates et détail |
| Infrastructure | Readiness Auth/Payment réelles ; Prometheus/Grafana/Loki explicitement non connectés |
| Security Center | Structure WAF/SIEM/alertes, NOT CONFIGURED ; aucun événement inventé |
| AI Detection | Emplacements scores/version/historique sans valeurs ; NOT CONFIGURED |
| Autonomous Recovery | Timeline réutilisable, huit états de référence explicitement non observés ; aucun moteur |
| AI Assistant | Structure conversation/références/loading/error, saisie désactivée, aucune fausse réponse |

Les neuf entrées de navigation sont complétées par la page Login et les vues de détail. OPERATOR/ADMIN disposent des vues de supervision mais pas des routes bancaires. Les autorisations de propriété restent appliquées par les API.

## 3. Architecture frontend

Code dans frontend/src : providers et routes dans main.tsx/App.tsx ; composants UI/layout/charts ; features auth, dashboard, accounts, payments, transactions, monitoring, security, ai, recovery ; hooks de requêtes ; client HTTP centralisé ; DTO Zod ; utilitaires monétaires et styles. Architecture détaillée dans docs/frontend/FRONTEND_ARCHITECTURE.md.

Versions installées et verrouillées : React 19.3.1, TypeScript 5.9.3, Vite 7.3.7, Tailwind 4.3.3, React Router 7.18.4, TanStack Query 5.104.4, React Hook Form 7.90.0, Zod 4.6.7, Recharts 3.10.1, Lucide 0.468.0, Vitest 4.1.12 et Playwright 1.64.1. Node 24.22.0 exécuté dans l’image de build. Aucune modification des sources backend, modèles SQL ou migrations validés en phase 1.

## 4. Design System

Bleu nuit, anthracite, cyan et typographie système sans dépendance à une police distante. Tokens Tailwind, composants réutilisables, états loading/empty/error, confirmations modales, notifications, tables et indicateurs textuels de statut. Sidebar mobile, menu utilisateur, breadcrumbs, focus visible et respect des préférences de mouvement réduit.

Captures desktop 1440 px et mobile 390 px réellement produites puis inspectées : login-desktop.png, overview-desktop.png, overview-mobile.png, payment-success.png dans docs/evidence/phase2. Le tableau peut défiler dans son conteneur sur mobile, sans débordement global de page. Voir docs/frontend/DESIGN_SYSTEM.md. Une certification d’accessibilité exhaustive n’est pas revendiquée.

## 5. Intégration API et sécurité de session

Les schémas OpenAPI exportés et le code réel des routes ont été lus. Le client HTTP applique un timeout de 12 s, validation des réponses avec Zod, messages d’erreur adaptés, bearer en mémoire, expiration et déconnexion sur 401. GET auth/me valide l’identité après login. Le cache Query est effacé à la déconnexion ; aucun JWT ni mot de passe dans localStorage/sessionStorage. Recharger la page impose de se reconnecter.

Le proxy Nginx sert la SPA et relaie seulement les routes Auth/Payment nécessaires. /status/auth et /status/payment sont des aliases de health checks existants ; ni metrics ni internal ne sont relayés. CSP, nosniff, interdiction d’iframe et no-referrer sont configurés. Pas de CORS wildcard ni de faux cookie HttpOnly. Les tokens en mémoire restent exposables à un script XSS compromis ; TLS/WAF restent hors phase 2.

Les listes chargent 20 éléments par page et utilisent next_cursor opaque. Les KPI/graphiques indiquent qu’ils portent sur les données chargées ; aucune exhaustivité supposée ni filtre non supporté. Les erreurs ne sont pas remplacées par des zéros fictifs.

## 6. Paiement et idempotence côté client

La saisie décimale est décomposée en euros/centimes sans arrondi ; montant entier positif, plafond conforme à l’API, EUR et deux UUID distincts. Une intention possède un corps immuable et une clé crypto.randomUUID. Cette paire est conservée par utilisateur dans sessionStorage de l’onglet, sans credential, avant tout envoi. Une Map de promesses et le verrou de bouton évitent les soumissions simultanées.

Après une interruption, la même opération et la même clé sont reprises. Aucun retry automatique de POST. Après un résultat métier validé, l’intention est supprimée et comptes/historique sont invalidés. Les statuts affichés sont uniquement SUCCESS et REJECTED. Un résultat réseau inconnu est présenté comme tel, jamais comme FAILED/PENDING bancaire.

L’utilisateur doit vérifier l’historique avant d’abandonner une opération incertaine. Fermer l’onglet/effacer sessionStorage perd l’intention locale ; deux intentions créées séparément dans deux onglets restent distinctes. L’idempotence durable est assurée par PostgreSQL et le backend.

## 7. Configuration Docker

Build multi-stage Node 24 bookworm-slim puis nginx-unprivileged stable-alpine (Nginx 1.30.6), digests d’index figés. Manifestes AMD64/ARM64 vérifiés ; seule exécution ARM64 testée. Runtime UID 101, racine en lecture seule, tmpfs /tmp, capacités supprimées, no-new-privileges, limite 128 MiB/0,25 CPU, healthcheck /health et restart unless-stopped.

Frontend sur réseaux edge/app, sans accès direct au réseau data. PostgreSQL garde son absence de port hôte. Le frontend est publié uniquement sur 127.0.0.1:8088 via l’overlay dev ; FRONTEND_PORT configurable. Les quatre services sont healthy. Les profils foundation et futurs services sont préservés.

Les cibles proxy sont configurables à l’exécution par FRONTEND_AUTH_UPSTREAM et FRONTEND_PAYMENT_UPSTREAM. Le template est rendu dans /tmp afin de fonctionner avec le système de fichiers RO ; DNS Docker réévalué périodiquement. Vite possède un proxy équivalent pour le développement.

## 8. Tests exécutés

| Contrôle | Résultat final | Preuve |
|---|---|---|
| Vitest : 4 fichiers, 32 tests | 32 passed, 0 failed, Node 24 | vitest-node24.txt |
| Même suite sur le Mac Node 25 avec webstorage expérimental désactivé | 32 passed | vitest-host.txt |
| Playwright Chromium ARM64 contre Nginx/API/PostgreSQL | 2 passed, 0 failed | playwright.txt |
| TypeScript strict | Code retour 0 | typecheck.txt |
| Vite production sous Node 24 | Build réussi | build.txt |
| Formatage Prettier | Vérification réussie | format.txt |
| npm audit après mise à jour | 0 vulnérabilité connue signalée | npm-audit.txt |
| pytest backend, projet isolé resilience-alpha-test | 45 passed, 0 failed | backend-regression.txt |
| Docker Compose | 4 services healthy, config valide | compose-status.txt |

Vitest couvre conversions exactes/rejets des montants, JWT uniquement en mémoire, 401, réponse invalide, réseau/timeout, nouvelles clés et conservation/retry, déduplication simultanée, validation du formulaire, garde de route, login/me, paiement confirmé, historique, pagination, navigation, déconnexion, expiration au retour de focus et modules indisponibles. Les réponses HTTP de Vitest sont explicitement des mocks, distinctes de la recette réelle Playwright.

Le test Playwright bancaire vérifie aussi le double clic, le résultat perdu après commit, le retour à Payments après navigation, le rejeu de la même clé, les soldes affichés, la consultation du détail, l’historique et les données PostgreSQL. L’autre test vérifie qu’un rechargement impose une reconnexion. Traces/vidéos désactivées, aucune capture des mots de passe.

## 9. Résultat du scénario E2E réel

Recette utilisant le compte fictif VALIDATOR et ses comptes V1/V2, distincts des comptes A/B de validation historique. Chaque exécution crée une nouvelle intention de 1,25 €, sans reset de données. Deux exécutions bancaires ont été réalisées ; ci-dessous la dernière.

- Avant : V1 = **98,75 €**, V2 = **101,25 €**.
- Paiement React : **1,25 €**, réponse backend **201**, statut SUCCESS.
- La réponse est interrompue volontairement après le commit réel ; l’interface affiche l’incertitude.
- Nouvelle tentative depuis l’interface : **même clé**, réponse **200**, même transaction.
- Après : V1 = **97,50 €**, V2 = **102,50 €** ; somme conservée à **200 €**.
- Vérification directe PostgreSQL : **une seule ligne pour cette clé**, aucun double débit/crédit.
- Comptes A/B historiques : **inchangés**, 800 €/700 €.
- Erreurs JavaScript du navigateur pendant le parcours : **0**.

Transaction : `2601e24c-5a83-4e97-a6cf-d34a28df3f82`. Clé : `4dee7bb4-d1d1-44ef-ad2c-db10d6687bb8`. Données exactes : docs/evidence/phase2/e2e-payment.json. La recette montre une persistance en base réelle ; un nouveau test de redémarrage PostgreSQL n’est pas revendiqué pour la phase 2 (celui de phase 1 reste documenté).

## 10. Problèmes rencontrés et corrections

1. Installation initiale : trois alertes de dépendances dans Vitest/tinypool/mocker. Mise à jour Vitest 4.1.12 ; audit final à zéro alerte connue.
2. Une première exécution de tests a chevauché la mise à jour des dépendances et échoué au chargement des modules. Exécution relancée une fois l’installation terminée.
3. Node 25 local expose un localStorage expérimental incompatible avec jsdom : deux assertions ont échoué sur ce runtime. La suite de référence passe sous Node 24 ; l’option --no-experimental-webstorage permet aussi la recette locale sans modifier Node système.
4. Port 8080 déjà occupé : port hôte frontend changé à 8088, configurable, sans interrompre le service existant.
5. Bundle initial volumineux : séparation du graphe Recharts dans un chunk dédié, supprimant l’avertissement de taille du build final.
6. Captures initiales trop précoces après clic : ajout d’attentes sur le titre et fermeture du volet mobile ; captures finales inspectées.
7. Option exact de Playwright utilisée par erreur dans un test Testing Library : retirée ; contrôle TypeScript final réussi.
8. Runtime Nginx RO : template rendu dans /tmp et configuration principale dédiée, avec cibles configurables et résolution DNS Docker.

Les avertissements de commentaires de tree-shaking issus de Zod sont non bloquants. L’avertissement pytest sur une clé HMAC volontairement invalide appartient au test de rejet d’algorithme, pas à la signature JWT RSA réelle.

## 11. Fichiers et documentation livrés

frontend/ : package.json et lockfile, tsconfig, Vite, HTML, sources React/CSS/types/services, tests Vitest/Playwright, Dockerfile, .dockerignore, exemple environnement, Nginx template/config/entrypoint, README. Racine : Compose/dev, .env.example, .gitignore, README et ce rapport. Documentation : architecture frontend, Design System, organisation du projet, plan/catalogue mis à jour, preuves phase2.

Les secrets, node_modules, dist, caches, traces et résultats bruts non sélectionnés restent exclus de Git. Les preuves sélectionnées ne contiennent pas de token ni de mot de passe. Les sources backend de phase 1 n’ont pas été modifiées.

Commandes principales depuis la racine :

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build --wait frontend
npm run typecheck --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
python3 scripts/run_tests.py
```

Node 24 requis pour les commandes npm de référence ; variante locale Node 25 documentée dans README. Les secrets/migrations/seeds doivent avoir été initialisés selon le README avant le premier démarrage. Les tests E2E nécessitent Docker accessible depuis l’hôte et Chromium Playwright installé.

## 12. Limites restantes

Démonstrateur bancaire fictif, sans promesse de production. Session perdue au rechargement par choix de stockage en mémoire ; pas de refresh token. Le quota de login backend est partagé par les requêtes proxifiées (5/min/source), adapté au laboratoire mono-instance. Pas d’annuaire de destinataires, pas de recherche/filtre ou total global non supportés par l’API. Les intentions conservées localement ne constituent pas un journal bancaire durable.

Health checks réels, mais aucune télémétrie CPU/RAM ou logs centralisés intégrés. Les pages Security/AI/Recovery/Assistant sont préparées, sans moteurs opérationnels. AMD64/Windows, autres navigateurs, audit exhaustif de sécurité/accessibilité et performances prolongées restent NOT TESTED. L’audit npm ponctuel n’est pas une garantie d’absence de vulnérabilités.

## 13. Préparation de la phase 3

Le shell, les cartes de services, les indicateurs, les vues d’erreur/chargement, la timeline et les schémas d’interface sont prêts pour de futures intégrations. Les fonctions bancaires et leurs contrats sont opérationnels et testés ; aucune donnée de supervision fictive ne masque les interfaces manquantes. La phase 2 s’arrête ici et attend la validation utilisateur avant la phase 3.
