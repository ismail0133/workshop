# Images vérifiées au registre le 19 octobre 2026

- Python `3.12-slim-bookworm`, index sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 : linux/amd64 et linux/arm64/v8 présents ; Python3.12.15 effectivement exécuté dans conteneur ARM64.
- PostgreSQL `17-bookworm`, index sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826 : linux/amd64 et linux/arm64/v8 présents ; version de manifeste17.11.

Commandes : `docker buildx imagetools inspect <image>` et `--raw`. Présence manifeste AMD64 ne constitue pas un test Windows. Le Dockerfile et Compose figent les index multiarchitecture, sans forcer émulation AMD64 sur Mac.
