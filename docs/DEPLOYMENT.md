# Deployment Guide

This guide covers deploying the Lambda function using Terraform with IAM credentials.

## Prerequisites

- Python 3.11+
- AWS CLI configured
- IAM credentials with Lambda and S3 permissions
- Terraform (if deploying infrastructure)
- S3 bucket for datasets
- S3 bucket for deployment artifacts (optional)

## Architecture Overview

This repository contains the **Lambda function code only**. The infrastructure is managed separately in your Terraform repository.

```
┌─────────────────────────┐
│ This Repository         │
│ (Lambda Code)           │
│                         │
│ - Source code (src/)    │
│ - Tests (tests/)        │
│ - Build script          │
│ - GitHub Actions        │
└────────┬────────────────┘
         │ Builds
         │ lambda.zip
         ▼
┌─────────────────────────┐
│ S3 Deployment Bucket    │
│ (Optional)              │
│                         │
│ lambda-latest.zip       │
└────────┬────────────────┘
         │ Referenced by
         ▼
┌─────────────────────────┐
│ Terraform Repository    │
│ (Infrastructure)        │
│                         │
│ - Lambda resource       │
│ - IAM roles             │
│ - Function URL          │
│ - CloudFront (optional) │
└─────────────────────────┘
```

## GitHub Repository Secrets

Configure these secrets in your GitHub repository settings:

### Required Secrets

```
AWS_ACCESS_KEY_ID          - IAM access key for deployment
AWS_SECRET_ACCESS_KEY      - IAM secret key for deployment
AWS_REGION                 - AWS region (e.g., us-east-1)
```

### Optional Secrets

```
DEPLOYMENT_BUCKET          - S3 bucket for storing Lambda packages
LAMBDA_FUNCTION_NAME       - Name of the Lambda function (for updates)
```

### Setting Up Secrets

1. Go to your GitHub repository
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret with its value

## IAM Permissions Required

The IAM user/role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:GetFunctionUrlConfig"
      ],
      "Resource": "arn:aws:lambda:*:*:function:download-lambda*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-deployment-bucket/*"
    }
  ]
}
```

## Deployment Methods

### Method 1: GitHub Actions (Recommended)

The GitHub Actions workflow automatically builds and uploads the Lambda package when you push to main.

**Workflow:**
1. Push code to `main` branch
2. GitHub Actions runs tests
3. Builds Lambda package (`lambda.zip`)
4. Uploads to S3 (if configured)
5. Creates artifact for download

**What it does NOT do:**
- It does NOT run Terraform
- It does NOT update the Lambda function directly
- You must run Terraform in your infrastructure repo to deploy

### Method 2: Manual Build + Terraform

**Step 1: Build the Lambda package**

```bash
# Clone this repository
git clone <repository-url>
cd download-lambda

# Install dev dependencies
make install-dev

# Run tests
make test

# Build Lambda package
make build
```

This creates `dist/lambda.zip`.

**Step 2: Copy to your Terraform repository**

```bash
# Copy the Terraform example
cp -r terraform-example /path/to/your/terraform-repo/modules/download-lambda

# Copy the Lambda package
cp dist/lambda.zip /path/to/your/terraform-repo/modules/download-lambda/
```

**Step 3: Configure Terraform**

In your Terraform repository, create a module:

```hcl
module "download_lambda" {
  source = "./modules/download-lambda"

  function_name       = "download-lambda"
  dataset_bucket_name = "my-datasets-bucket"
  lambda_zip_path     = "./modules/download-lambda/lambda.zip"

  timeout      = 60
  memory_size  = 512
  auth_type    = "NONE"

  create_cloudfront = true

  tags = {
    Environment = "production"
    Project     = "data-downloads"
  }
}

output "lambda_function_url" {
  value = module.download_lambda.lambda_function_url
}
```

**Step 4: Deploy with Terraform**

```bash
cd /path/to/your/terraform-repo

# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply
```

### Method 3: Direct AWS CLI Update

If the Lambda function already exists, you can update just the code:

```bash
# Build package
make build

# Update function
aws lambda update-function-code \
  --function-name download-lambda \
  --zip-file fileb://dist/lambda.zip

# Wait for update to complete
aws lambda wait function-updated \
  --function-name download-lambda

# Test
FUNCTION_URL=$(aws lambda get-function-url-config \
  --function-name download-lambda \
  --query 'FunctionUrl' \
  --output text)

curl "${FUNCTION_URL}/test-dataset.csv"
```

## Terraform Configuration

### Minimal Configuration

Copy the files from [terraform-example/](terraform-example/) to your Terraform repository:

```
your-terraform-repo/
├── modules/
│   └── download-lambda/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── lambda.zip
└── main.tf  (your root module)
```

### Variables to Configure

Edit `terraform.tfvars` or pass via command line:

```hcl
dataset_bucket_name = "your-datasets-bucket"  # REQUIRED
function_name       = "download-lambda"
lambda_zip_path     = "./modules/download-lambda/lambda.zip"
timeout             = 60
memory_size         = 512
```

### First-Time Terraform Deployment

```bash
# In your Terraform repository
cd /path/to/terraform-repo

# Initialize
terraform init

# Plan (review changes)
terraform plan \
  -var="dataset_bucket_name=your-bucket" \
  -out=tfplan

# Apply
terraform apply tfplan

# Get outputs
terraform output lambda_function_url
```

## CI/CD Workflow

### Recommended Workflow

**1. Code Repository (this repo):**
- Developers push code changes
- GitHub Actions runs tests
- On main branch: builds `lambda.zip`
- Uploads to S3 deployment bucket

**2. Terraform Repository (your infra repo):**
- Reference Lambda package from S3
- Or trigger Terraform via GitHub Actions
- Apply infrastructure changes

### Complete CI/CD Pipeline

**Option A: Separate Repositories**

```yaml
# In this repo: .github/workflows/deploy.yml
# Builds and uploads lambda.zip to S3

# In Terraform repo: .github/workflows/terraform.yml
# Downloads lambda.zip from S3 and runs terraform apply
```

**Option B: Terraform Cloud/Enterprise**

Configure Terraform Cloud to:
1. Watch your Terraform repository
2. Auto-plan on changes
3. Manual approval for apply

Reference the Lambda package from S3:

```hcl
data "aws_s3_object" "lambda_package" {
  bucket = "deployment-bucket"
  key    = "lambda-builds/lambda-latest.zip"
}

resource "aws_lambda_function" "download_function" {
  s3_bucket = data.aws_s3_object.lambda_package.bucket
  s3_key    = data.aws_s3_object.lambda_package.key
  # ... other config
}
```

## Environment Configuration

### Lambda Environment Variables

Set these in your Terraform configuration:

```hcl
environment {
  variables = {
    DATASET_BUCKET = "your-datasets-bucket"
  }
}
```

Or via AWS CLI:

```bash
aws lambda update-function-configuration \
  --function-name download-lambda \
  --environment "Variables={DATASET_BUCKET=your-bucket}"
```

## Testing the Deployment

### 1. Check Function Status

```bash
aws lambda get-function --function-name download-lambda
```

### 2. Get Function URL

```bash
aws lambda get-function-url-config \
  --function-name download-lambda \
  --query 'FunctionUrl' \
  --output text
```

### 3. Test Endpoints

```bash
FUNCTION_URL="<your-function-url>"

# Test CSV download
curl "${FUNCTION_URL}/test-dataset.csv" | head

# Test JSON with filter
curl "${FUNCTION_URL}/test-dataset.json?organisation-entity=org-1" | jq '.[0:3]'

# Test error handling
curl -i "${FUNCTION_URL}/nonexistent.csv"  # Should return 404
curl -i "${FUNCTION_URL}/test.invalid"     # Should return 400
```

## Monitoring

### CloudWatch Logs

```bash
# Tail logs
aws logs tail /aws/lambda/download-lambda --follow

# Get recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/download-lambda \
  --filter-pattern "ERROR" \
  --max-items 10
```

### CloudWatch Metrics

View in AWS Console or use CLI:

```bash
# Get invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=download-lambda \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Rollback

If you need to rollback to a previous version:

### Using Terraform

```bash
# Revert to previous lambda.zip
git checkout HEAD~1 dist/lambda.zip

# Update Lambda
aws lambda update-function-code \
  --function-name download-lambda \
  --zip-file fileb://dist/lambda.zip
```

### Using S3 Versioning

If your deployment bucket has versioning:

```bash
# List versions
aws s3api list-object-versions \
  --bucket deployment-bucket \
  --prefix lambda-builds/

# Get specific version
aws s3api get-object \
  --bucket deployment-bucket \
  --key lambda-builds/lambda-latest.zip \
  --version-id <version-id> \
  lambda-rollback.zip

# Deploy
aws lambda update-function-code \
  --function-name download-lambda \
  --zip-file fileb://lambda-rollback.zip
```

## Troubleshooting

### Build fails on GitHub Actions

Check:
- Python version matches (3.11)
- All dependencies in `requirements.txt`
- Tests are passing locally

### Cannot upload to S3

Check:
- `DEPLOYMENT_BUCKET` secret is set
- IAM credentials have S3 PutObject permission
- Bucket exists and is in the correct region

### Lambda function not updating

Check:
- Function name is correct
- IAM credentials have `lambda:UpdateFunctionCode` permission
- The function exists in the same region

### Terraform plan shows no changes

This is expected if only the Lambda code changed. Terraform needs to detect the change:

```hcl
# Force update by using source_code_hash
source_code_hash = filebase64sha256(var.lambda_zip_path)
```

## Security Best Practices

1. **IAM Credentials:**
   - Use separate IAM users for CI/CD
   - Rotate credentials regularly
   - Apply least-privilege permissions

2. **Secrets Management:**
   - Store AWS credentials in GitHub Secrets
   - Never commit credentials to repository
   - Use environment-specific secrets

3. **Lambda Security:**
   - Use Function URL with IAM auth in production
   - Enable VPC for private access (optional)
   - Configure resource-based policies

4. **Deployment Bucket:**
   - Enable versioning
   - Enable encryption
   - Set lifecycle policies

## Support

For issues with:
- **Lambda code**: Open issue in this repository
- **Infrastructure**: Check your Terraform repository
- **AWS services**: Contact AWS Support
