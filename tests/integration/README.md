# Integration Testing with Lambda Web Adapter

This directory contains integration tests that simulate the actual Lambda environment locally using Docker and testcontainers.

## Quick Start

### Option 1: Shell Script (Easiest)

```bash
# Run the complete test suite with Docker Compose
./scripts/test_lambda_local.sh
```

This script will:
1. Build the Lambda Docker image
2. Start LocalStack for S3 emulation
3. Upload test data to LocalStack S3
4. Start the Lambda container with Web Adapter
5. Download CSV/JSON from the Lambda endpoint
6. Compare downloaded data with source Parquet
7. Report any data corruption or missing rows

### Option 2: Docker Compose (Manual)

```bash
# Start all services (LocalStack + Lambda + setup)
docker-compose -f docker-compose.test.yml up --build

# In another terminal, test the endpoints
curl -o test-download.csv "http://localhost:9000/conservation-area.csv"
curl -o test-download.json "http://localhost:9000/conservation-area.json"

# Compare with source
python scripts/compare_entities.py test-data/conservation-area.parquet test-download.csv

# Clean up
docker-compose -f docker-compose.test.yml down
```

### Option 3: Python Integration Tests (testcontainers)

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run integration tests (Docker image is built automatically!)
pytest tests/integration/test_lambda_streaming.py -v

# Run with output
pytest tests/integration/test_lambda_streaming.py -v -s
```

**Note**: The integration test dependencies are in `requirements-dev.txt`:
- `testcontainers==4.8.2` - For spinning up Docker containers in tests
- `requests==2.32.3` - For HTTP requests to the Lambda container
- `pytest==8.3.0` - Already included for unit tests

**How it works**:
- testcontainers **automatically builds** the Docker image from your Dockerfile
- No need to run `docker build` manually
- First run will be slower (building image), subsequent runs use cached image
- Image is tagged as `download-lambda:test` and reused

**Important**: These tests require:
1. Docker running on your machine
2. Test data file at `test-data/conservation-area.parquet`

That's it! testcontainers handles the Docker image build automatically.

For the easiest testing experience, use Option 1 (`./scripts/test_lambda_local.sh`) which handles all setup automatically.

## What Gets Tested

The integration tests verify:

1. **Data Completeness**: All rows from the source Parquet file are present in the downloaded CSV
2. **No Data Corruption**: No missing entities, no unexpected entities
3. **Specific Entity Test**: Entity 44008914 (previously missing) is present
4. **JSON Streaming**: JSON format returns complete data
5. **Response Headers**: Correct Content-Disposition, X-Dataset, X-Format headers
6. **Filtered Streaming**: organisation-entity filter works correctly

## Test Environment

The Docker Compose setup creates:

- **LocalStack**: S3 emulation on port 4566
- **Lambda Container**: Your actual Docker image with Lambda Web Adapter on port 9000
- **Setup Container**: One-time container to upload test data to LocalStack S3

This closely mirrors the actual Lambda environment:
- Same Docker image that gets deployed to Lambda
- Same Lambda Web Adapter configuration (response_stream mode)
- Same environment variables
- Same S3 access patterns (via DuckDB httpfs)

## Debugging

### View Lambda Logs

```bash
docker-compose -f docker-compose.test.yml logs lambda
```

### View LocalStack Logs

```bash
docker-compose -f docker-compose.test.yml logs localstack
```

### Interactive Testing

```bash
# Start services in background
docker-compose -f docker-compose.test.yml up -d

# Test different endpoints
curl "http://localhost:9000/health"
curl "http://localhost:9000/conservation-area.csv" | head -20
curl "http://localhost:9000/conservation-area.json" | jq '.[0]'
curl "http://localhost:9000/conservation-area.csv?organisation-entity=242"

# Stop services
docker-compose -f docker-compose.test.yml down
```

### Check S3 Data in LocalStack

```bash
# List buckets
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws \
    --endpoint-url=http://localhost:4566 \
    s3 ls

# List objects
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws \
    --endpoint-url=http://localhost:4566 \
    s3 ls s3://test-bucket/dataset/

# Download from S3
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws \
    --endpoint-url=http://localhost:4566 \
    s3 cp s3://test-bucket/dataset/conservation-area.parquet /tmp/test.parquet
```

## Known Issues

### Data Corruption (FIXED)

**Issue**: Lambda streaming was returning 213 fewer rows than expected, with scattered missing entities and unexpected entities appearing.

**Root Cause**: `await asyncio.sleep(0)` in the streaming wrapper was causing chunk reordering in Lambda Web Adapter.

**Fix**: Removed the asyncio.sleep(0) call. See [LAMBDA_STREAMING_FIX.md](../../LAMBDA_STREAMING_FIX.md) for details.

**Verification**: Run `./scripts/test_lambda_local.sh` to verify all entities are present.

## Test Data

Tests use `test-data/conservation-area.parquet`:
- 11,766 rows
- 9.6 MB file size
- Real planning data from planning.data.gov.uk

This file is large enough to test streaming behavior but small enough for quick local testing.

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run Lambda integration tests
  run: |
    docker-compose -f docker-compose.test.yml up -d
    sleep 10
    ./scripts/test_lambda_local.sh
    docker-compose -f docker-compose.test.yml down
```

## Requirements

- Docker Desktop (or Docker Engine + Docker Compose)
- Python 3.12+ (for comparison scripts)
- AWS CLI (for LocalStack S3 operations)
- curl (for HTTP requests)

Optional:
- testcontainers-python (for Python integration tests)
- pytest (for running test suite)
