# Quick Start Guide

Get your Lambda function up and running in 10 minutes.

## Prerequisites

```bash
# Install Python dependencies
pip install -r requirements-dev.txt

# Ensure AWS CLI is configured
aws sts get-caller-identity
```

## Step 1: Create Sample Data

```bash
# Generate sample Parquet files
python scripts/create_sample_data.py
```

This creates several test datasets in `sample-data/`:
- `test-dataset.parquet` (1,000 rows)
- `large-dataset.parquet` (10,000 rows)
- `customers.parquet` (5,000 rows)
- `transactions.parquet` (50,000 rows)

## Step 2: Create S3 Bucket

```bash
# Create bucket (replace with your bucket name)
aws s3 mb s3://my-datasets-bucket

# Upload sample data
aws s3 cp sample-data/ s3://my-datasets-bucket/ --recursive

# Verify upload
aws s3 ls s3://my-datasets-bucket/
```

## Step 3: Build Lambda Package

```bash
# Run tests
make test

# Build deployment package
make build
```

This creates `dist/lambda.zip` ready for deployment.

## Step 4: Deploy with Terraform

Copy Terraform files to your infrastructure repository:

```bash
cp -r terraform-example /path/to/your/terraform-repo/modules/download-lambda
cp dist/lambda.zip /path/to/your/terraform-repo/modules/download-lambda/
```

In your Terraform repository, create or update your configuration:

```hcl
module "download_lambda" {
  source = "./modules/download-lambda"

  function_name       = "download-lambda"
  dataset_bucket_name = "my-datasets-bucket"
  lambda_zip_path     = "./modules/download-lambda/lambda.zip"
}

output "function_url" {
  value = module.download_lambda.lambda_function_url
}
```

Deploy:
```bash
terraform init
terraform plan
terraform apply
```

See [TERRAFORM_INTEGRATION.md](TERRAFORM_INTEGRATION.md) for more deployment options.

## Step 5: Test the Function

```bash
# Get Function URL
FUNCTION_URL=$(terraform output -raw function_url)

# Test CSV download
curl -o output.csv "${FUNCTION_URL}/test-dataset.csv"

# Test JSON with filter
curl "${FUNCTION_URL}/customers.json?organisation-entity=org-5" | jq '.[0:3]'

# Test error handling
curl -i "${FUNCTION_URL}/nonexistent.csv"  # Returns 404
```

## Troubleshooting

**Dataset not found:**
```bash
aws s3 ls s3://my-datasets-bucket/
```

**Permission issues:**
Check IAM role has S3 read permissions

**Timeout:**
Increase timeout in Terraform configuration

See full troubleshooting in [README.md](README.md#troubleshooting)

## Next Steps

- Set up CI/CD: [DEPLOYMENT.md](DEPLOYMENT.md)
- Add CloudFront CDN
- Customize filtering logic
- Add more datasets
