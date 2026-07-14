# Download Lambda

A high-performance Lambda function that streams filtered dataset downloads from S3 Parquet files using DuckDB.

## Features

- **DuckDB-Powered**: Ultra-efficient S3 Parquet processing with filter pushdown
- **FastAPI-style Parameter Validation**: Uses Pydantic models for path and query parameter validation
- **Direct S3 Streaming**: Reads only necessary data from S3, no full file downloads
- **Column Selection**: Select specific columns to reduce download size and bandwidth
- **Multiple Output Formats**: Supports CSV, JSON, and Parquet output formats
- **CloudFront Integration**: Built to work with Lambda Function URLs and CloudFront CDN
- **Path Traversal Protection**: Validates dataset names to prevent security vulnerabilities
- **Memory Efficient**: ~30MB peak memory usage vs 240MB with traditional approaches


## URL Format

```
GET /{dataset}.{extension}?organisation-entity={value}&quality={value}&field={column1}&field={column2}
```

### Path Parameters

- `{dataset}`: Name of the dataset (without extension). Maps to `{dataset}.parquet` in S3.
- `{extension}`: Output format - `csv`, `json`, or `parquet`

### Query Parameters

- `organisation-entity` (optional): Filter data by organisation entity value
- `quality` (optional): Filter data by quality value. Allowed values: `""` (empty string), `"some"`, `"authoritative"`
- `field` (optional): Select specific columns to include in output. Can be specified multiple times for multiple columns (e.g., `?field=id&field=name`)

Multiple filters can be combined and will be applied with AND logic.

### Examples

```bash
# Download full dataset as CSV
GET /conservation-area.csv

# Download filtered dataset by organisation
GET /conservation-area.json?organisation-entity=122

# Download filtered dataset by quality
GET /conservation-area.csv?quality=some

# Download with multiple filters (AND logic)
GET /conservation-area.parquet?organisation-entity=122&quality=authoritative

# Select specific columns only
GET /conservation-area.csv?field=entity&field=name&field=geometry

# Combine row filtering and column selection
GET /conservation-area.json?organisation-entity=122&field=entity&field=reference&field=name
```

## Project Structure

```
download-lambda/
├── application/                     # FastAPI app, runs in Lambda via the Lambda Web Adapter
│   ├── main.py                      # App setup, health check, startup validation
│   ├── routers.py                   # Download endpoint
│   ├── dependencies.py              # Dependency-injected services
│   ├── utils.py                     # Request parsing utilities
│   └── services/
│       ├── s3_service.py            # S3 access
│       └── data_stream_service.py   # DuckDB/Arrow streaming + format conversion
├── tests/                           # unit, integration, and acceptance tests (pytest)
├── scripts/                         # helper scripts (local Docker builds, test data, etc.)
├── docker/                          # local dev Dockerfiles / LocalStack helpers
├── Dockerfile                       # Container image deployed to Lambda
├── requirements.in / requirements.txt          # Production dependencies (pip-tools)
├── requirements-dev.in / requirements-dev.txt  # Development dependencies (pip-tools)
└── Makefile                         # Convenience commands
```

## Quick Start

### Prerequisites

- Python 3.12+
- a python virtualenv (repo is set up to use pyenv with the `.python-version` file)

## Deployment

**Note:** This repository contains the Lambda function code. Infrastructure (the Lambda resource, IAM roles, ECR repository, etc.) is managed separately using Terraform — see [TERRAFORM_INTEGRATION.md](TERRAFORM_INTEGRATION.md).

The Lambda function runs as a **container image** (via the [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter), see the [Dockerfile](Dockerfile)), not a traditional zip package. Deployment builds the image, pushes it to Amazon ECR, and points the Lambda function at the new image — there's no `lambda.zip` to build or upload.

### Build the Docker Image

```bash
docker build --platform linux/amd64 -t download-lambda:latest .
```

Or use the helper script:
```bash
./scripts/build-docker.sh
```

### Deploying

Deployment is handled entirely by CI/CD (see below) — push to `main`, or trigger `workflow_dispatch` for a specific environment. There's no manual deployment step for normal use; the workflow builds the image, pushes it to ECR, and updates the target Lambda function's code for you.

## CI/CD

The included GitHub Actions workflows (`.github/workflows/test.yml` and `deploy.yml`):
- Run the full test suite on PRs and pushes
- On push to `main` (or manual `workflow_dispatch`), build a Docker image per environment (development/staging/production, based on configured GitHub Environments), tag it, and push it to Amazon ECR
- Update the target Lambda function to use the newly pushed image

### Required GitHub Secrets

Configured per GitHub Environment (Settings → Environments):

```
DEPLOY_AWS_ACCESS_KEY_ID       - IAM access key for the deploy role
DEPLOY_AWS_SECRET_ACCESS_KEY   - IAM secret key for the deploy role
DEPLOY_DOCKER_REPOSITORY       - ECR repository URI to push the built image to
```

## Development Setup

### Install Dependencies

```bash
# Development environment (default - includes testcontainers, pytest, etc.)
# Also builds Lambda Docker image for integration testing
make init

# Production environment only (no test dependencies, no Docker build)
make init ENV=prod
```

The `ENV` variable controls which requirements are installed:
- `ENV=local` (default):
  - Installs `requirements.txt` and `requirements-dev.txt` (includes testcontainers, pytest, black, etc.)
  - Builds Lambda Docker image (`download-lambda:test`) for integration tests
  - Sets up pre-commit hooks
- `ENV=prod`: Installs `requirements.txt` only (production dependencies)

**Note**: `make init` will build the Docker image automatically if Docker is available. This enables you to run integration tests immediately after setup.

## Testing

This project follows [Digital Land testing guidance](https://digital-land.github.io/technical-documentation/development/testing-guidance/) with comprehensive unit, integration, and acceptance tests.

### Run All Tests

```bash
make test
```

### Run Specific Test Types

```bash
# Unit tests only (fast, isolated)
make test-unit

# Integration tests (with mocked AWS services)
make test-integration

# Acceptance tests (user scenarios)
make test-acceptance

# Test Lambda container locally with Docker (simulates actual Lambda environment)
make test-lambda

# With coverage report
make test-coverage
```

### Test Structure

```
tests/
├── unit/                    # Fast, isolated tests
├── integration/             # Tests with mocked S3 and Lambda containers
└── acceptance/              # End-to-end user scenarios
```

### Lambda Container Testing

Test the actual Lambda Docker image with Web Adapter locally:

```bash
# Quick test with shell script (recommended)
make test-lambda

# Or use Docker Compose directly
docker-compose -f docker-compose.test.yml up --build
curl -o test.csv "http://localhost:9000/conservation-area.csv"
python scripts/compare_entities.py test-data/conservation-area.parquet test.csv

# Or use Python integration tests with testcontainers
pytest tests/integration/test_lambda_streaming.py -v
```

This simulates the actual Lambda environment with:
- Lambda Web Adapter in response streaming mode
- LocalStack for S3 emulation
- Real Parquet file streaming from S3
- Entity-level verification to detect data corruption

See [tests/integration/README.md](tests/integration/README.md) for detailed Lambda testing documentation.

See [TESTING.md](TESTING.md) for comprehensive testing documentation.

### Local Testing

```bash
# Install dependencies
make init

# Run specific test file
pytest tests/unit/test_s3_service.py -v

# Run tests matching pattern
pytest -k "filter" -v
```

## Data Format

### Input: Parquet Files

Parquet files in S3 should be named `{dataset}.parquet` and contain:

- A column named `organisation-entity` (if using filtering)
- Any other columns needed for your datasets

Example structure:
```
s3://my-datasets-bucket/
  ├── customers.parquet
  ├── transactions.parquet
  └── large-dataset.parquet
```

### Output Formats

**CSV**: Standard comma-separated values with headers

**JSON**: Array of objects with streaming support
```json
[
  {"id": 1, "name": "Record 1", "organisation-entity": "org-1"},
  {"id": 2, "name": "Record 2", "organisation-entity": "org-2"}
]
```

**Parquet**: Binary Parquet format (useful for filtered downloads)

## How It Works

### DuckDB Advantages

1. **Filter Pushdown**: WHERE clauses are applied at Parquet row group level using metadata
2. **Direct S3 Streaming**: Uses HTTP range requests to read only necessary row groups
3. **No Pandas Overhead**: Streams Arrow RecordBatches directly, no conversion needed
4. **Parallel Reading**: Leverages multiple cores for concurrent row group processing

### Configuration

- **Chunk Size**: Default 10,000 rows per batch. Configurable in [data_stream_service.py](application/services/data_stream_service.py)
- **Memory**: 256MB Lambda memory is sufficient for most datasets
- **Timeout**: 30-60 seconds depending on dataset size
- **Streaming**: Supports Lambda Function URL response streaming for large files

### Architecture

```
Request → Lambda → DuckDB → S3 Parquet (via httpfs)
                     ↓
              Filter Pushdown (reads only matching row groups)
                     ↓
              Arrow RecordBatch streaming
                     ↓
              Format conversion (CSV/JSON/Parquet)
                     ↓
              Streaming response to client
```

## Security

- **Path Traversal Protection**: Dataset names are validated to prevent `../` attacks
- **IAM Authentication**: Function URL uses AWS_IAM authentication
- **Bucket Permissions**: Lambda has read-only access to the dataset bucket
- **Input Validation**: All parameters validated with Pydantic

## Monitoring

View Lambda logs in CloudWatch (replace `{environment}` with `development`, `staging`, `production`, etc.):

```bash
aws logs tail /aws/lambda/{environment}-download-lambda --follow
```

## Development

### Code Formatting

```bash
make format
```

### Linting

```bash
make lint
```

### Clean Build Artifacts

```bash
make clean
```

## Environment Variables

- `DATASET_BUCKET`: S3 bucket containing Parquet datasets (required)

## Troubleshooting

### "Dataset not found" Error

- Verify the Parquet file exists in S3: `{dataset}.parquet`
- Check Lambda has read permissions to the bucket
- Confirm bucket name is correct in environment variables

### Timeout Errors

- Increase the Lambda function's timeout in Terraform (this repo doesn't manage infrastructure — see [TERRAFORM_INTEGRATION.md](TERRAFORM_INTEGRATION.md))
- Reduce chunk size in [data_stream_service.py](application/services/data_stream_service.py)
- Consider pagination for very large results

### Memory Errors

- Increase the Lambda function's memory in Terraform
- Reduce chunk size to process fewer rows at once

## License

See [LICENSE](LICENSE) file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Additional Documentation

- [TERRAFORM_INTEGRATION.md](TERRAFORM_INTEGRATION.md) - how this repository's image fits into your Terraform-managed infrastructure
- [TESTING.md](TESTING.md) - full testing guide
- [DEVELOPMENT.md](DEVELOPMENT.md) - local development setup
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - detailed architecture notes
- [docs/QUICKSTART.md](docs/QUICKSTART.md) - quick start guide
