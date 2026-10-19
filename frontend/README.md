# Frontend RESILIENCE-ALPHA

React / TypeScript / Vite / Tailwind. Démarrage depuis ce dossier avec Node 24 : `npm ci`, puis `npm run dev`. Les API doivent être démarrées selon le [README racine](../README.md). Le proxy Vite évite les requêtes cross-origin du navigateur.

`npm test` exécute Vitest ; `npm run typecheck` vérifie TypeScript ; `npm run build` produit dist/. `npm run test:e2e` nécessite le frontend Docker et les services réels sur le port 8088, Docker accessible depuis l’hôte et Chromium Playwright installé.

[Architecture](../docs/frontend/FRONTEND_ARCHITECTURE.md) · [Design System](../docs/frontend/DESIGN_SYSTEM.md) · [Rapport](../PHASE_2_REPORT.md).
