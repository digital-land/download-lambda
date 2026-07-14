.PHONY: init test test-unit test-integration test-acceptance test-coverage test-lambda lint format build deploy clean dev-up dev-down dev-logs dev-restart dev-rebuild dev-gen-data dev-clean

# Environment variable to control which requirements to install
# ENV=prod will install only production requirements
# ENV=local (default) will install development requirements
ENV ?= local

init:
ifeq ($(ENV),prod)
	@echo "📦 Installing production requirements only..."
	pip install -r requirements.txt
else
	@echo "📦 Installing development requirements (includes testcontainers, pytest, etc.)..."
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install
	@echo ""
	@echo "🐳 Building Lambda Docker image for local testing..."
	@echo "   (testcontainers can also build this automatically, but pre-building speeds up first test run)"
	@if command -v docker >/dev/null 2>&1; then \
		docker build -t download-lambda:test . --platform linux/amd64 && \
		echo "✅ Lambda Docker image built successfully"; \
	else \
		echo "⚠️  Docker not found. Skipping Lambda image build."; \
		echo "   testcontainers will build the image automatically when running tests."; \
	fi
	@echo ""
	@echo "✅ Development environment ready!"
	@echo "   - Run tests: make test"
	@echo "   - Run integration tests: make test-integration"
	@echo "   - Test Lambda locally: make test-lambda"
endif

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
	python -m pytest --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

# Run tests for CI (with XML coverage for codecov)
test-ci:
	python -m pytest --cov=src --cov-report=xml --cov-report=term

# Test Lambda container locally with Docker (simulates actual Lambda environment)
test-lambda:
	@echo "🐳 Testing Lambda container with Web Adapter..."
	@echo ""
	./scripts/test_lambda_local.sh

lint:
	black --check application/ tests/
	flake8 application/ tests/

format:
	black application/ tests/

build:
	./scripts/build.sh

# Docker Compose targets for local development
dev-gen-data:
	@echo "Generating test Parquet data..."
	@if [ -d ".venv" ]; then \
		.venv/bin/python docker/localstack/generate_test_data.py; \
	else \
		python3 docker/localstack/generate_test_data.py || ( \
			echo ""; \
			echo "⚠️  PyArrow not installed. Install with: pip install -r requirements.txt"; \
			exit 1 \
		); \
	fi
	@echo ""
	@echo "✓ Test data generated in docker/test-data/"

dev-up:
	docker-compose up -d
	@echo ""
	@echo "✅ Local development stack started!"
	@echo "📦 LocalStack S3: http://localhost:4566"
	@echo "🚀 FastAPI app: http://localhost:8000"
	@echo "📖 API docs: http://localhost:8000/docs"
	@echo ""
	@echo "Test with: curl http://localhost:8000/test-dataset.csv"

dev-down:
	docker-compose down

dev-logs:
	docker-compose logs -f

dev-restart:
	docker-compose restart app

dev-rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo ""
	@echo "✅ Development stack rebuilt and started!"

dev-clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker-compose down -v --remove-orphans
	@echo "Removing download-lambda images..."
	@docker images | grep download-lambda | awk '{print $$3}' | xargs -r docker rmi -f 2>/dev/null || true
	@echo "Removing dangling images..."
	@docker image prune -f
	@echo ""
	@echo "✅ Docker cleanup complete!"
	@echo ""
	@echo "To rebuild from scratch, run: make dev-rebuild"

clean:
	rm -rf build/ dist/ htmlcov/ .coverage .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
