# Images phase 2

Manifestes linux/amd64 et linux/arm64 vérifiés avec docker buildx imagetools inspect. Build et exécution réellement effectués sur ARM64 uniquement.

- node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5
- nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

Ces index multiarch permettent de sélectionner l’architecture native. La disponibilité du manifeste ne constitue pas une recette AMD64/Windows.
