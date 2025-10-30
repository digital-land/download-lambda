.PHONY: install test test-unit test-integration test-acceptance test-coverage lint format build deploy clean

install-dev:
	pip install -r requirements-dev.txt

# Run all tests
test:
	pytest -v

# Run only unit tests (fast)
test-unit:
	pytest tests/unit/ -v

# Run only integration tests
test-integration:
	pytest tests/integration/ -v

# Run only acceptance tests
test-acceptance:
	pytest tests/acceptance/ -v

# Run tests with detailed coverage report
test-coverage:
	pytest --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

# Run tests for CI (with XML coverage for codecov)
test-ci:
	pytest --cov=src --cov-report=xml --cov-report=term

lint:
	ruff check src/ tests/
	black --check src/ tests/
	mypy src/

format:
	black src/ tests/
	ruff check --fix src/ tests/

build:
	./build.sh

clean:
	rm -rf build/ dist/ htmlcov/ .coverage .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

