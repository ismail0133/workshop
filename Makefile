.PHONY: help test demo persistence compose-config
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
