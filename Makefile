PYTHON ?= python3

.PHONY: lint format test check ci-docker
lint:
	$(PYTHON) -m black --check experiments tests
	$(PYTHON) -m isort --check-only experiments tests
	$(PYTHON) -m flake8 experiments tests

format:
	$(PYTHON) -m black experiments tests
	$(PYTHON) -m isort experiments tests

test:
	$(PYTHON) -m unittest discover -s tests -v

check: lint test

ci-docker:
	docker run --rm -v "$(CURDIR):/work:ro" -w /work python:3.14-slim sh -c 'pip install -r requirements-dev.txt && python -m black --check experiments tests && python -m isort --check-only experiments tests && python -m flake8 experiments tests && python -m unittest discover -s tests -v'
