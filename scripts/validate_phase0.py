#!/usr/bin/env python3
"""Validate phase-0 design artifacts without running services or SQL."""

import csv
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
    from openapi_spec_validator import validate
    from pglast import parse_sql
except ImportError as exc:
    sys.exit(f"Missing validator: {exc}. See scripts/requirements-phase0.txt")

ROOT = Path(__file__).resolve().parents[1]
checks = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    checks.append(message)


required = [
    "docs/architecture/ARCHITECTURE.md",
    "docs/architecture/DIAGRAMS.md",
    "docs/architecture/DATA_FLOWS.md",
    "docs/architecture/SERVICE_CATALOG.md",
    "docs/database/DATABASE_DESIGN.md",
    "docs/api/API_CONTRACTS.md",
    "docs/ml/ML_DESIGN.md",
    "docs/security/SECURITY_ARCHITECTURE.md",
    "docs/FEASIBILITY_STUDY.md",
    "docs/REQUIREMENTS_TRACEABILITY.md",
    "docs/IMPLEMENTATION_PLAN.md",
    "README.md",
    "PHASE_0_REPORT.md",
]
check(
    all((ROOT / p).is_file() and (ROOT / p).stat().st_size > 100 for p in required),
    "13 documents demandés présents et non vides",
)
for p in ROOT.rglob("*.json"):
    json.loads(p.read_text())
checks.append("Tous les fichiers JSON sont lisibles")
for p in ROOT.rglob("*.yml"):
    yaml.safe_load(p.read_text())
yaml.safe_load((ROOT / "infrastructure/secrets/.sops.yaml.example").read_text())
tomllib.loads((ROOT / "pyproject.toml").read_text())
checks.append("YAML et TOML : syntaxe valide")
spec = json.loads((ROOT / "docs/api/openapi.json").read_text())
validate(spec)
checks.append("OpenAPI 3.1 validée par openapi-spec-validator")
events = json.loads((ROOT / "docs/api/events.schema.json").read_text())
Draft202012Validator.check_schema(events)
Draft202012Validator(events, format_checker=FormatChecker()).validate(
    json.loads((ROOT / "docs/api/anomaly.example.json").read_text())
)
checks.append("JSON Schema 2020-12 et exemple anomalie validés, formats inclus")
parsed = parse_sql((ROOT / "docs/database/initial_schema.sql").read_text())
tables = {stmt.stmt.relation.relname for stmt in parsed if type(stmt.stmt).__name__ == "CreateStmt"}
check(
    tables
    == {"users", "accounts", "transactions", "incidents", "incident_events", "remediation_actions"},
    "SQL parsé par pglast : six tables attendues, aucune exécution",
)
# Verify the API data fields map to actual columns; DTO-only models excluded intentionally.
columns = {
    stmt.stmt.relation.relname: {
        entry.colname for entry in stmt.stmt.tableElts if hasattr(entry, "colname")
    }
    for stmt in parsed
    if type(stmt.stmt).__name__ == "CreateStmt"
}
for dto, table in {
    "User": "users",
    "Account": "accounts",
    "Payment": "transactions",
    "Incident": "incidents",
    "IncidentEvent": "incident_events",
    "Action": "remediation_actions",
}.items():
    check(
        set(spec["components"]["schemas"][dto]["properties"]) <= columns[table],
        f"Champs {dto} compatibles avec colonnes {table}",
    )
text = (ROOT / "docs/architecture/DIAGRAMS.md").read_text()
blocks = re.findall(r"```mermaid\n(.*?)```", text, re.S)
check(len(blocks) == 11, "Onze blocs Mermaid présents")
for i, block in enumerate(blocks, 1):
    check(
        (ROOT / f"docs/architecture/diagram-{i:02}.mmd").read_text().strip() == block.strip(),
        f"Diagramme {i:02} identique à sa source Markdown",
    )
check(all(table + " {" in blocks[-1] for table in tables), "ER couvre les six tables SQL")
expected = {
    "DETECTED",
    "ANALYZING",
    "CONFIRMED",
    "REJECTED",
    "REMEDIATING",
    "VALIDATING",
    "RECOVERED",
    "RECOVERY_FAILED",
}
check(
    set(spec["components"]["schemas"]["Incident"]["properties"]["status"]["enum"]) == expected
    and all(state in blocks[7] for state in expected),
    "États incidents cohérents OpenAPI et Mermaid",
)
with (ROOT / "docs/requirements.csv").open() as f:
    requirements = list(csv.DictReader(f))
check(
    len(requirements) == 80 and len({row["Identifiant"] for row in requirements}) == 80,
    "Traçabilité : 80 identifiants uniques",
)
test_plan = (ROOT / "tests/TEST_PLAN.md").read_text()
check(
    all(row["Test associé"] in test_plan for row in requirements),
    "Chaque ligne EPSI possède un protocole de test/revue",
)
check(
    all(all(1 <= int(p) <= 12 for p in row["Page source"].split(",")) for row in requirements),
    "Toutes les pages sources sont dans le PDF 12 pages",
)
# Only existing relative Markdown file links; URLs and anchors are ignored.
for p in ROOT.rglob("*.md"):
    for target in re.findall(r"\]\(([^)]+)\)", p.read_text()):
        target = target.strip("<>").split("#")[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        check((p.parent / target).exists(), f"Lien local valide : {p.relative_to(ROOT)} → {target}")
compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
expected_services = {
    "frontend",
    "payment-api",
    "auth-service",
    "incident-service",
    "ml-detector",
    "rag-service",
    "postgres",
    "prometheus",
    "grafana",
    "loki",
    "waf",
    "ollama",
    "alloy",
    "remediation-runner",
}
check(
    set(compose["services"]) | set(compose["x-planned-services"]) == expected_services,
    "Cible Compose : 14 composants, dont 5 services de socle et 9 planifiés",
)
check(
    all(s.get("profiles") == ["foundation"] for s in compose["services"].values()),
    "Services du socle sous profil explicite foundation",
)
check(
    "docker.sock" not in (ROOT / "docker-compose.yml").read_text(),
    "Aucun socket Docker dans Compose",
)
check(
    not list((ROOT / "database/migrations").glob("*.py")),
    "Aucune migration applicative créée ou exécutée",
)
result = subprocess.run(
    ["docker", "compose", "--profile", "foundation", "config", "--quiet"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    timeout=30,
)
check(
    result.returncode == 0,
    "Docker Compose config validé sans contacter le daemon : " + (result.stderr.strip() or "OK"),
)
print(
    f"PASS — {len(checks)} contrôles documentaires ; {len(spec['paths'])} chemins OpenAPI ; {len(parsed)} instructions SQL parsées."
)
for message in checks:
    print("PASS", message)
print(
    "Limites : pas de rendu/parser Mermaid, ni tests runtime, migrations, images, modèle ML ou reprise."
)
