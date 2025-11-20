.PHONY: install test test-unit test-integration test-acceptance test-coverage lint format build deploy clean

install-dev:
	pip install -e .
	pip install -r requirements-dev.txt

# Run all tests
test:
	pytest -v

# Run only unit tests (fast)
test-unit:
	python -m pytest tests/unit/ -v

# Run only integration tests
test-integration:
	python -m pytest tests/integration/ -v

# Run only acceptance tests
test-acceptance:
	python -m pytest tests/acceptance/ -v

# Run tests with detailed coverage report
test-coverage:
	pytest --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

# Run tests for CI (with XML coverage for codecov)
test-ci:
	pytest --cov=src --cov-report=xml --cov-report=term

lint:
	black --check src/ tests/
	flake8 src/ tests/

format:
	black src/ tests/

build:
	./scripts/build.sh

clean:
	rm -rf build/ dist/ htmlcov/ .coverage .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

