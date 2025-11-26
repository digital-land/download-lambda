# Local Development with Docker Compose

This directory contains Docker Compose configuration for local development with LocalStack.

## Quick Start

```bash
# Start the stack (test data is included)
make dev-up

# View logs
make dev-logs

# Stop the stack
make dev-down
```

Test data is pre-generated and included in `docker/test-data/`, so the stack works immediately without any setup!

## Services

- **LocalStack**: Mock AWS S3 service running on port 4566
- **FastAPI App**: Download API running on port 8000 with hot-reload

## Test Data

Pre-generated test data is included in `docker/test-data/`:
- `test-dataset.parquet` - 100 rows with 5 organizations (org-1 to org-5)
- `sales-data.parquet` - 200 rows with 10 organizations (org-1 to org-10)

### Regenerating Test Data

If you need to regenerate the test data:

```bash
# Regenerate test data (uses .venv if available)
make dev-gen-data

# Restart LocalStack to upload the new data
docker-compose restart localstack
```

## Testing the API

```bash
# Health check
curl http://localhost:8000/health

# Download test dataset as CSV
curl http://localhost:8000/test-dataset.csv

# Download with filtering by organization
curl "http://localhost:8000/test-dataset.csv?organisation-entity=org-1"

# Download as JSON
curl http://localhost:8000/sales-data.json

# API documentation
open http://localhost:8000/docs
```

## Troubleshooting

### App container crashes

Check logs:
```bash
docker logs download-lambda-app
```

Common issues:
- Missing DATASET_BUCKET environment variable (check docker-compose.yml)
- LocalStack not healthy (wait for it to start)

### LocalStack initialization fails

Check LocalStack logs:
```bash
docker logs download-lambda-localstack
```

The bucket `test-datasets` should be created automatically.

## File Structure

```
docker/
├── Dockerfile.dev          # Development Dockerfile with hot-reload
├── localstack/
│   ├── 01-init-s3.sh      # S3 bucket initialization script
│   └── generate_test_data.py  # Test Parquet data generator
└── test-data/              # Generated test files (gitignored)
    ├── test-dataset.parquet
    └── sales-data.parquet
```
