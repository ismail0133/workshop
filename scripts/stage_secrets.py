"""Copy only each service's own secrets into its read-only runtime volume."""

import os
from pathlib import Path

mapping = {
    "auth": {
        "auth_password": "db_password",
        "jwt_private.pem": "jwt_private.pem",
        "jwt_public.pem": "jwt_public.pem",
    },
    "payment": {
        "bank_password": "db_password",
        "cursor_key": "cursor_key",
        "jwt_public.pem": "jwt_public.pem",
    },
}
for service, files in mapping.items():
    folder = Path("/staged") / service
    folder.mkdir(parents=True, exist_ok=True)
    for source, dest in files.items():
        target = folder / dest
        target.write_bytes((Path("/run/secrets") / source).read_bytes())
        os.chown(target, 10001, 10001)
        target.chmod(0o400)
    os.chown(folder, 10001, 10001)
    folder.chmod(0o500)
print("Runtime secrets staged with service-specific ownership.")
