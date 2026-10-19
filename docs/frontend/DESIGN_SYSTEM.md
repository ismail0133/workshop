# Design System — RESILIENCE-ALPHA

## Direction

Console SaaS sombre : fond bleu nuit #080e1b, panneaux #101a2b, bordures #223047, accent cyan #38c7df. Texte principal clair, texte secondaire bleu grisé. Le vert exprime un résultat disponible/réussi ; le rouge un rejet/erreur ; le gris une indisponibilité. Les statuts sont toujours écrits, jamais exprimés seulement par la couleur.

Typographie système Inter/Segoe UI/Arial, sans téléchargement externe ; titres à espacement resserré, libellés compacts et valeurs monétaires tabulaires par contexte. Tokens Tailwind via @theme dans src/styles/global.css ; classes de composants pour conserver des pages lisibles. Espacements de 8–24 px, cartes arrondies 11 px, boutons 7 px, transitions brèves et désactivation via prefers-reduced-motion.

## Composants réutilisables

| Composant | Usage |
|---|---|
| Button | primary/secondary/ghost, disabled natif, type explicite dans formulaires |
| Input / champs select | labels associés, erreurs de validation, autoComplete de connexion |
| Card / PageTitle | structure de section et hiérarchie de page |
| Badge | neutral/good/bad/cyan, indicateur plus libellé |
| Alert / ErrorState | role alert, erreur explicite, action de réessai |
| Skeleton / Empty | chargement identifié, absence de données honnête |
| Modal | dialog natif modal : focus contenu, fermeture Échap sauf envoi en cours |
| ToastProvider | notification role status, fermeture manuelle et expiration 5 s |
| TransactionTable | tableau sémantique, statut, montant, date et lien détail |
| ActivityChart | Recharts interactif, montants par jour UTC, légende et périmètre chargé |
| Layout | sidebar, navigation active, topbar, menu utilisateur, footer et lien d’évitement |
| Timeline | événements d’incidents typés et horodatés, vide si backend absent |
| MessageList | messages/références, chargement et erreur, aucune réponse préremplie |

Les modales de détail et de confirmation partagent le même composant. L’abandon d’une intention incertaine conserve une confirmation native supplémentaire. Les graphiques ne décorent pas les écrans d’infrastructure avec des données fictives.

## Responsive et accessibilité

Sidebar fixe sur desktop, volet mobile avec backdrop, bouton d’ouverture/fermeture et fermeture lors de navigation. KPI quatre puis deux colonnes ; formulaires et cartes empilés sur petits écrans. Tables défilables horizontalement dans leur conteneur ; aucun débordement horizontal de la page dans le test 390 px. La carte secondaire de synthèse plateforme est masquée sur écrans étroits ; les health checks restent accessibles dans Infrastructure et la topbar.

Focus visible cyan, labels et boutons iconiques nommés, headings structurés, tableaux natifs, champs numériques en inputMode decimal. Le dialogue natif gère le focus ; pas d’animation décorative persistante. Captures de référence dans docs/evidence/phase2. Une certification WCAG exhaustive, une recette lecteur d’écran et Safari/Firefox ne sont pas revendiquées.
