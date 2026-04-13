PYTHON ?= python

.PHONY: install-dev lint format test validate-configs ci release-check docker-build

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m black .

test:
	$(PYTHON) -m pytest

validate-configs:
	PYTHONPATH=src $(PYTHON) -m scripts.validate_configs

ci: validate-configs lint test

docker-build:
	docker build -t etl_marinadaggdjur_dwc:latest .

release-check: validate-configs lint test docker-build
