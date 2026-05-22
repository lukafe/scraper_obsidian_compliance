PY := python3.12
VENV := .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTHON := $(BIN)/python

.PHONY: help install install-browser test seed seed-br run run-dry clean clean-vault

help:
	@echo "Crypto LawMap — common ops"
	@echo ""
	@echo "  make install         create .venv and install requirements"
	@echo "  make install-browser also install playwright chromium (JS fallback)"
	@echo "  make test            run pytest suite (no API calls, no network)"
	@echo ""
	@echo "  make seed-br         seed only Brazil (needs ANTHROPIC_API_KEY)"
	@echo "  make seed C=US,SG    seed only the given countries"
	@echo "  make run             full loop on every country in config.yaml"
	@echo "  make run-dry         dry-run (no API calls, no vault writes)"
	@echo ""
	@echo "  make clean           remove venv + caches + __pycache__"
	@echo "  make clean-vault     wipe the vault contents (irreversible)"

install:
	$(PY) -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -r requirements.txt

install-browser: install
	$(BIN)/playwright install chromium

test:
	$(PYTHON) -m pytest -q tests/

seed-br:
	$(PYTHON) -m src.orchestrator --seed-only --countries BR

seed:
	$(PYTHON) -m src.orchestrator --seed-only --countries $(C)

run:
	$(PYTHON) -m src.orchestrator

run-dry:
	$(PYTHON) -m src.orchestrator --dry-run

clean:
	rm -rf $(VENV) cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

clean-vault:
	rm -rf vault/*
