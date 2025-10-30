# Download Lambda

A high-performance Lambda function that streams filtered dataset downloads from S3 Parquet files using DuckDB.

## Features

- **DuckDB-Powered**: Ultra-efficient S3 Parquet processing with filter pushdown
- **FastAPI-style Parameter Validation**: Uses Pydantic models for path and query parameter validation
- **Direct S3 Streaming**: Reads only necessary data from S3, no full file downloads
- **Multiple Output Formats**: Supports CSV, JSON, and Parquet output formats
- **CloudFront Integration**: Built to work with Lambda Function URLs and CloudFront CDN
- **Path Traversal Protection**: Validates dataset names to prevent security vulnerabilities
- **Memory Efficient**: ~30MB peak memory usage vs 240MB with traditional approaches


## URL Format

```
GET /{dataset}.{extension}?organisation-entity={value}
```

### Path Parameters

- `{dataset}`: Name of the dataset (without extension). Maps to `{dataset}.parquet` in S3.
- `{extension}`: Output format - `csv`, `json`, or `parquet`

### Query Parameters

- `organisation-entity` (optional): Filter data by organisation entity value

### Examples

```bash
# Download full dataset as CSV
GET /conservation-area.csv

# Download filtered dataset as JSON
GET /conservation-area.json?organisation-entity=122

# Download filtered dataset as Parquet
GET /conservation-area.parquet?organisation-entity=122
```

## Project Structure

```
download-lambda/
├── src/                       ## all python code in here
│   ├── lambda_function.py     # Main Lambda handler
│   ├── models.py              # Pydantic validation models
│   ├── utils.py               # Request parsing utilities
│   └── data_processor.py      # DuckDB-based Parquet processing
├── tests/                     ## all pytest based tests
│   └── ...                  
├── scripts/                   ## helper scripts 
│   └── build.ssh              # script to build the lambda function for upload
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
└── Makefile                   # Convenience commands
```

## Quick Start

### Prerequisites

- Python 3.11+
- a python virtualenv

## Deployment

**Note:** This repository contains the Lambda function code. Infrastructure is managed separately using Terraform.

### Build Lambda Package

```bash
# Run tests
make test

# Build deployment package
make build
```

This creates `dist/lambda.zip`. which can be uploaded to AWS.

**Quick version:**

1. Copy Terraform files to your infrastructure repository:
```bash
cp -r terraform-example/ /path/to/your/terraform-repo/modules/download-lambda/
cp dist/lambda.zip /path/to/your/terraform-repo/modules/download-lambda/
```

2. In your Terraform repository:
```hcl
module "download_lambda" {
  source = "./modules/download-lambda"

  function_name       = "download-lambda"
  dataset_bucket_name = "my-datasets-bucket"
  lambda_zip_path     = "./modules/download-lambda/lambda.zip"
}
```

3. Deploy:
```bash
terraform init
terraform plan
terraform apply
```

### Alternative: Direct AWS CLI Deployment

If the Lambda function already exists:

```bash
aws lambda update-function-code \
  --function-name download-lambda \
  --zip-file fileb://dist/lambda.zip
```

## CI/CD

The included GitHub Actions workflow:
- Runs tests on PRs
- Builds Lambda package on push to main
- Uploads to S3 for Terraform to reference

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete CI/CD setup.

### Required GitHub Secrets

```
AWS_ACCESS_KEY_ID          - IAM access key
AWS_SECRET_ACCESS_KEY      - IAM secret key
DEPLOYMENT_BUCKET          - S3 bucket for Lambda packages (optional)
LAMBDA_FUNCTION_NAME       - Function name (optional)
```

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

# With coverage report
make test-coverage
```

### Test Structure

```
tests/
├── unit/                    # Fast, isolated tests
├── integration/             # Tests with mocked S3
└── acceptance/              # End-to-end user scenarios
```

See [TESTING.md](TESTING.md) for comprehensive testing documentation.

### Local Testing

```bash
# Install dependencies
make install-dev

# Run specific test file
pytest tests/unit/test_models.py -v

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

- **Chunk Size**: Default 10,000 rows per batch. Configurable in `data_processor.py`
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

View Lambda logs in CloudWatch:

```bash
aws logs tail /aws/lambda/download-lambda-stack-DownloadFunction --follow
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

- Increase Lambda timeout in [template.yaml](template.yaml)
- Reduce chunk size in [data_processor.py](src/data_processor.py)
- Consider pagination for very large results

### Memory Errors

- Increase Lambda memory in [template.yaml](template.yaml)
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


## Architecture

```
User Request → CloudFront/Function URL → Lambda Function → S3 Parquet Files → Streaming Response
```