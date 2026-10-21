#!/usr/bin/env python3
"""Crée le jeton interne ML → incident-service (scope anomaly:write), sans l'afficher.

Le même secret doit être monté, en lecture seule, par incident-service pour valider X-Service-Token.
Jamais réutilisé pour le runner (jeton distinct). Ne remplace pas un fichier existant (rotation explicite).
"""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "infrastructure/secrets/runtime"
root.mkdir(parents=True, exist_ok=True, mode=0o700)
path = root / "ml_anomaly_token"
if path.exists():
    path.chmod(0o600)
    print("ml_anomaly_token existe déjà : conservé (supprimer le fichier pour une rotation).")
else:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(secrets.token_urlsafe(48) + "\n")
    print("ml_anomaly_token créé (valeur non affichée).")
