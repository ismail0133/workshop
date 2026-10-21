.PHONY: help test test-ai demo persistence compose-config
PYTHON ?= python3
help:
	@echo "Phase 1 : test, demo, persistence, compose-config. Démarrage : voir README.md."
test:
	$(PYTHON) scripts/run_tests.py
demo:
	docker compose run --rm db-tools python scripts/validate_demo.py
persistence:
	$(PYTHON) scripts/check_persistence.py
compose-config:
	docker compose --profile foundation --profile tools config --quiet

test-ai:
	cd services/ml-detector && PYTHONPATH=. python3 -m pytest tests -q --confcutdir=. -p no:cacheprovider
	cd services/rag-service && PYTHONPATH=. python3 -m pytest tests -q --confcutdir=. -p no:cacheprovider
