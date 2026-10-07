# Architecture Diagram Generator — developer workflow targets.
#
# Usage:
#   make venv      # create .venv and install the package + dev deps
#   make test      # run the pytest suite
#   make run SPEC=outputs/acme-orders/acme-orders.spec.yaml
#   make regen     # regenerate every outputs/**/*.spec.yaml
#   make build     # build sdist + wheel
#   make clean     # remove build artifacts and caches

PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
PY     := $(BIN)/python
PIP    := $(BIN)/pip
SCRIPT := .kiro/scripts/arch-diagram/generate_diagram.py

.DEFAULT_GOAL := help

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(VENV):  ## Create the virtual environment
	$(PYTHON) -m venv $(VENV)

.PHONY: venv
venv: $(VENV)  ## Create venv and install the package (editable) + dev deps
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"

.PHONY: test
test:  ## Run the test suite
	$(PY) -m pytest -q

.PHONY: run
run:  ## Generate one diagram: make run SPEC=path/to/x.spec.yaml
	@test -n "$(SPEC)" || (echo "error: set SPEC=path/to/spec.yaml" >&2; exit 2)
	$(PY) $(SCRIPT) --input "$(SPEC)"

.PHONY: png
png:  ## Generate one diagram WITH PNG previews: make png SPEC=path/to/x.spec.yaml
	@test -n "$(SPEC)" || (echo "error: set SPEC=path/to/spec.yaml" >&2; exit 2)
	$(PY) $(SCRIPT) --input "$(SPEC)" --png

.PHONY: regen
regen:  ## Regenerate every spec under outputs/
	@set -e; find outputs -name '*.spec.yaml' | while read -r spec; do \
		echo "generating $$spec"; \
		$(PY) $(SCRIPT) --input "$$spec"; \
	done

.PHONY: build
build:  ## Build sdist + wheel into dist/
	$(PY) -m pip install -U build
	$(PY) -m build

.PHONY: clean
clean:  ## Remove build artifacts and caches
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
