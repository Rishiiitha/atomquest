.PHONY: setup quick data full reproduce demo test

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
else
PYTHON := .venv/bin/python
endif

setup:
	python -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt
	corepack pnpm --dir web install --node-linker=hoisted --package-import-method=copy
	$(PYTHON) scripts/export_openapi.py
	corepack pnpm --dir web gen:api
	$(PYTHON) -m data.pipeline --quick

quick:
	$(PYTHON) -m data.pipeline --quick

data:
	$(PYTHON) -m data.generate --quick

full:
	$(PYTHON) -m data.pipeline --full

reproduce:
	$(PYTHON) -m data.pipeline --full

demo:
	$(PYTHON) -m api.launch

test:
	$(PYTHON) -m pytest -q

