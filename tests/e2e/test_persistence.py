"""Host-side pytest: deliberately controls only this project's Docker containers.
Run on a host with pytest installed; the alternative standalone entry point is
scripts/check_persistence.py.
"""

# This host-only file is excluded from the container unit/integration invocation.
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"]


def command(*args):
    completed = subprocess.run(
        [*COMPOSE, *args], cwd=ROOT, text=True, capture_output=True, timeout=90, check=True
    )
    return completed.stdout


def test_persistence_after_database_and_api_restart():
    first = json.loads(command("run", "--rm", "db-tools", "python", "scripts/validate_demo.py"))
    command("restart", "postgres", "auth-service", "payment-api")
    command("up", "-d", "--wait", "postgres", "auth-service", "payment-api")
    second = json.loads(command("run", "--rm", "db-tools", "python", "scripts/validate_demo.py"))
    assert second["transaction_id"] == first["transaction_id"]
    assert second["before_minor"] == second["after_minor"] == first["after_minor"]
    assert second["first_http"] == 200 and second["matching_database_rows"] == 1
