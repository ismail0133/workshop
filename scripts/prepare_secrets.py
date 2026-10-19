#!/usr/bin/env python3
"""Create local demo credentials without printing them or replacing existing files."""

import os
import secrets
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "infrastructure/secrets/runtime"
root.mkdir(parents=True, exist_ok=True, mode=0o700)
root.chmod(0o700)
for name in (
    "postgres_password",
    "migrator_password",
    "auth_password",
    "bank_password",
    "ops_password",
    "grafana_password",
    "cursor_key",
    "demo_alice_password",
    "demo_bob_password",
    "demo_operator_password",
    "demo_admin_password",
    "demo_validator_password",
):
    path = root / name
    if not path.exists():
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(32) + "\n")
    path.chmod(0o600)
private, public = root / "jwt_private.pem", root / "jwt_public.pem"
if not private.exists():
    if public.exists():
        raise SystemExit("Public key exists without private key; refusing implicit rotation")
    old_umask = os.umask(0o077)
    try:
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:3072",
                "-out",
                str(private),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        os.umask(old_umask)
if not public.exists():
    subprocess.run(
        ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
        check=True,
        capture_output=True,
    )
private.chmod(0o600)
public.chmod(0o644)
print("Local fictional credentials prepared; no values printed. Never commit runtime/.")
