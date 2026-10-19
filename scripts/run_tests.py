#!/usr/bin/env python3
"""Build an isolated PostgreSQL/API test project; never reset the demo database."""

import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compose = [
    "docker",
    "compose",
    "-p",
    "resilience-alpha-test",
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.test.yml",
]
commands = [
    ["build", "auth-service", "payment-api", "db-tools"],
    ["up", "-d", "--wait", "postgres"],
    ["run", "--rm", "db-tools", "python", "scripts/stage_secrets.py"],
    ["run", "--rm", "db-tools", "python", "-m", "database.bootstrap"],
    ["run", "--rm", "db-tools", "alembic", "upgrade", "head"],
    ["run", "--rm", "db-tools", "python", "-m", "database.seeds.demo"],
    ["up", "-d", "--wait", "auth-service", "payment-api"],
    [
        "run",
        "--rm",
        "db-tools",
        "pytest",
        "tests/unit",
        "tests/integration",
        "-q",
        "-p",
        "no:cacheprovider",
    ],
]
for command in commands:
    subprocess.run([*compose, *command], cwd=root, check=True)
