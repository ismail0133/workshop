#!/usr/bin/env python3
"""Host-side functional restart verification, no Docker socket in application containers."""

import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compose = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"]


def run(*args):
    result = subprocess.run(
        [*compose, *args], cwd=root, check=True, capture_output=True, text=True, timeout=90
    )
    return result.stdout


before = json.loads(run("run", "--rm", "db-tools", "python", "scripts/validate_demo.py"))
run("restart", "postgres", "auth-service", "payment-api")
run("up", "-d", "--wait", "postgres", "auth-service", "payment-api")
after = json.loads(run("run", "--rm", "db-tools", "python", "scripts/validate_demo.py"))
assert before["transaction_id"] == after["transaction_id"]
assert after["before_minor"] == after["after_minor"] == before["after_minor"]
assert after["first_http"] == 200 and after["matching_database_rows"] == 1
print(
    json.dumps({"persistence": "PASS", "before_restart": before, "after_restart": after}, indent=2)
)
