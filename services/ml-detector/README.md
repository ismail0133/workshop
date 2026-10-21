# ml-detector

Détecteur d'anomalies Isolation Forest (port 8003, sans API métier : `/health/live`, `/health/ready`, `/metrics`).

- Conception : `docs/ml/ML_DESIGN.md`. Résultats et limites : `docs/ml/ML_REPORT.md`.
- Tests : `PYTHONPATH=. python3 -m pytest tests -q --confcutdir=. -p no:cacheprovider` (52 tests, sans Prometheus).
- CLI : `python -m ml_app.cli synth|collect|label|train|evaluate`. `synth` produit des données synthétiques, `train --synthetic` marque le modèle comme non probant.
- Sans `INCIDENT_URL`, le détecteur journalise les anomalies sans les envoyer (dry-run).
- Image Docker : écrite, **non construite** (pas de démon Docker pendant le développement).

## Détecteur par User-Agent sur les journaux du WAF (`ml_app/waf/`)

Lit `access.jsonl`, calcule des fenêtres de 10 s par User-Agent, détecte un comportement atypique (Isolation Forest + règle de 3 fenêtres) et peut écrire `ua:Token` dans `infrastructure/waf/blocklist/blocklist.txt`. **Résultats réels et limites : `docs/ml/ML_REPORT.md` §7.**

```bash
cd services/ml-detector
# 1. résumé d'un journal exporté du WAF
PYTHONPATH=. python -m ml_app.waf profile --log ../../access.jsonl
# 2. entraîner, calibrer sur la validation, évaluer sur le test (lire les mises en garde du rapport)
PYTHONPATH=. python -m ml_app.waf train --log ../../access.jsonl --splits ../../docs/ml/data/waf-2026-10-21.splits.json --out ../../ml_model/waf-1 --version waf-1
# 3. rejouer le journal : SIMULATION par défaut, rien n'est écrit
PYTHONPATH=. python -m ml_app.waf replay --log ../../access.jsonl --model ../../ml_model/waf-1 --blocklist ../../infrastructure/waf/blocklist/blocklist.txt
# 4. suivre un flux en direct (le fichier est dans un volume Docker) ; --apply écrit réellement
docker compose -f docker-compose.yml -f docker-compose.edge.yml exec -T waf tail -n0 -F /var/log/resilience/waf/access.jsonl \
  | PYTHONPATH=. python -m ml_app.waf watch --log - --model ../../ml_model/waf-1 --blocklist ../../infrastructure/waf/blocklist/blocklist.txt \
      --never-block python-httpx --audit ../../ml_model/waf-1/audit.jsonl
```

Garde-fous : jeton refusé s'il correspond à un navigateur (même liste que le WAF), à un User-Agent vu en trafic normal ou à `--never-block` ; plafond de 20 entrées posées par le détecteur ; écriture atomique ; **pas d'écriture sans `--apply`**. Le modèle est vérifié par empreinte avant chargement (`--pinned-sha256`). Ne commitez ni `ml_model/` ni `access.jsonl`.
