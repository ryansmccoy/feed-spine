.PHONY: install lint test docs build docker-build docker-run clean

# Package name
PACKAGE := feedspine

install:
	uv sync --dev

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

test-cov:
	uv run pytest --cov=src/ --cov-report=html --cov-report=term

docs:
	uv run mkdocs build

docs-serve:
	uv run mkdocs serve

build:
	uv build

docker-build:
	docker build -t $(PACKAGE):latest -f docker/Dockerfile .

docker-run:
	docker compose up -d

clean:
	rm -rf dist/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Generate ecosystem docs
ecosystem:
	cd .. && python scripts/generate_ecosystem_docs.py -o ECOSYSTEM.md

# Extract TODOs
todos:
	cd .. && python scripts/extract_todos.py --project feedspine --output feedspine/docs/TODO.md
