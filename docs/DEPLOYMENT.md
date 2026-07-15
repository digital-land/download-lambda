# Deployment Guide

This guide covers deploying the Lambda function using Terraform with IAM credentials.

## Prerequisites

- Python 3.12+
- AWS CLI configured
- IAM credentials with Lambda and ECR permissions
- Terraform (if deploying infrastructure)
- S3 bucket for datasets
- An Amazon ECR repository per environment (created by Terraform) to hold the built container images

## Architecture Overview

This repository contains the **Lambda function code only**. The infrastructure is managed separately in your Terraform repository. The Lambda function runs as a **container image**, not a zip package.

```
┌─────────────────────────┐
│ This Repository         │
│ (Lambda Code)           │
│                         │
│ - Application code      │
│   (application/)        │
│ - Tests (tests/)        │
│ - Dockerfile             │
│ - GitHub Actions        │
└────────┬────────────────┘
         │ Builds & pushes
         │ container image
         ▼
┌─────────────────────────┐
│ Amazon ECR Repository   │
│ (per environment)       │
│                         │
│ {environment}-download- │
│ lambda:{tag}            │
└────────┬────────────────┘
         │ GitHub Actions updates
         │ the Lambda function's
         │ code directly
         ▼
┌─────────────────────────┐
│ Lambda Function          │
│ (created/managed by     │
│ your Terraform repo)    │
│                         │
│ - Lambda resource       │
│ - IAM roles             │
│ - ECR repository        │
│ - Function URL          │
│ - CloudFront (optional) │
└─────────────────────────┘
```

Note the key difference from a zip-based setup: Terraform still owns the Lambda function, IAM roles, and ECR repository, but **this repository's CI/CD updates the running function's code directly** (via `UpdateFunctionCode` with the new image) after each build — it doesn't wait for a separate `terraform apply` to pick up a new artifact.

## GitHub Repository Secrets

Configure these secrets per GitHub Environment (Settings → Environments), since deployments are per-environment (development/staging/production):

### Required Secrets

```
DEPLOY_AWS_ACCESS_KEY_ID       - IAM access key for deployment
DEPLOY_AWS_SECRET_ACCESS_KEY   - IAM secret key for deployment
DEPLOY_DOCKER_REPOSITORY       - ECR repository URI to push the built image to
```

### Setting Up Secrets

1. Go to your GitHub repository
2. Navigate to Settings → Environments → select (or create) an environment
3. Click "Add secret" under Environment secrets
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
      "Resource": "arn:aws:lambda:*:*:function:*-download-lambda*"
    },
    {
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:CompleteLayerUpload",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "arn:aws:ecr:*:*:repository/*-download-lambda"
    }
  ]
}
```

## Deployment Methods

### Method 1: GitHub Actions (Recommended)

The GitHub Actions workflow automatically builds the container image, pushes it to ECR, and updates the Lambda function when you push to main.

**Workflow:**
1. Push code to `main` branch (or trigger `workflow_dispatch` for a specific environment)
2. GitHub Actions runs tests
3. Builds the Docker image and pushes it to the environment's ECR repository
4. Updates the Lambda function to use the newly pushed image, and waits for the update to complete

**What it does NOT do:**
- It does NOT run Terraform
- It does NOT create the Lambda function, IAM roles, or ECR repository — those must already exist (created by your Terraform repo)

### Method 2: Manual Build + Terraform

**Step 1: Build the Docker image**

```bash
# Clone this repository
git clone <repository-url>
cd download-lambda

# Install dev dependencies
make init

# Run tests
make test

# Build the image
docker build --platform linux/amd64 -t download-lambda:latest .
```

**Step 2: Copy to your Terraform repository**

```bash
# Copy the Terraform example
cp -r terraform-example /path/to/your/terraform-repo/modules/download-lambda
```

**Step 3: Configure Terraform**

In your Terraform repository, create a module:

```hcl
module "download_lambda" {
  source = "./modules/download-lambda"

  function_name       = "download-lambda"
  dataset_bucket_name = "my-datasets-bucket"
  package_type        = "Image"
  image_uri           = "<account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest"

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

If the Lambda function already exists, you can push a new image and update just the code:

```bash
# Build and push the image
docker build --platform linux/amd64 -t <account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest .
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest

# Update function
aws lambda update-function-code \
  --function-name download-lambda \
  --image-uri <account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest

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
│       └── outputs.tf
└── main.tf  (your root module)
```

### Variables to Configure

Edit `terraform.tfvars` or pass via command line:

```hcl
dataset_bucket_name = "your-datasets-bucket"  # REQUIRED
function_name       = "download-lambda"
package_type        = "Image"
image_uri           = "<account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest"
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
- On main branch (or manual dispatch): builds the Docker image, pushes it to each environment's ECR repository, and updates that environment's Lambda function directly

**2. Terraform Repository (your infra repo):**
- Owns the Lambda function, IAM roles, ECR repository, and Function URL/CloudFront resources
- Run separately (and less frequently) to change infrastructure, not to ship code changes

### Complete CI/CD Pipeline

```yaml
# In this repo: .github/workflows/deploy.yml
# Builds and pushes the image to ECR, then updates the Lambda function's code directly

# In Terraform repo: .github/workflows/terraform.yml (if you have one)
# Applies infrastructure changes (Lambda resource, IAM, ECR repo, etc.) - independent of code deploys
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

### Using the Previous Image Tag

Every image is tagged with a release tag (timestamp + short SHA) and the branch/ref name — see the `Build and publish Docker image` step in `.github/workflows/deploy.yml`. To roll back, point the function at a previous tag:

```bash
# Find previous image tags in ECR
aws ecr describe-images \
  --repository-name download-lambda \
  --query 'sort_by(imageDetails,& imagePushedAt)[*].imageTags' \
  --output table

# Roll back to a specific tag
aws lambda update-function-code \
  --function-name download-lambda \
  --image-uri <account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:<previous-tag>

aws lambda wait function-updated --function-name download-lambda
```

### Using ECR Image Immutability

If your ECR repository has tag immutability enabled, previous tags can never be overwritten, so rolling back is always just a matter of re-pointing the function at an older, known-good tag as above.

## Troubleshooting

### Build fails on GitHub Actions

Check:
- Python version matches (3.12)
- All dependencies in `requirements.txt` / `requirements-dev.txt` are resolvable
- Tests are passing locally
- The Docker image builds locally: `docker build --platform linux/amd64 -t download-lambda:test .`

### Cannot push to ECR

Check:
- `DEPLOY_DOCKER_REPOSITORY` secret is set for the target environment
- IAM credentials have the ECR permissions listed above
- The ECR repository exists and is in the correct region

### Lambda function not updating

Check:
- Function name is correct
- IAM credentials have `lambda:UpdateFunctionCode` permission
- The function exists in the same region

### Terraform plan shows no changes

This is expected if only the Lambda code changed — GitHub Actions updates the running function's image directly, so Terraform won't see a diff unless the image URI/tag is itself part of your Terraform configuration (e.g. if you pin an explicit tag in `image_uri` rather than always deploying `:latest` via CI).

## Security Best Practices

1. **IAM Credentials:**
   - Use separate IAM users for CI/CD
   - Rotate credentials regularly
   - Apply least-privilege permissions

2. **Secrets Management:**
   - Store AWS credentials in GitHub Environment secrets
   - Never commit credentials to repository
   - Use environment-specific secrets

3. **Lambda Security:**
   - Use Function URL with IAM auth in production
   - Enable VPC for private access (optional)
   - Configure resource-based policies

4. **Container Registry (ECR):**
   - Enable image scanning on push
   - Enable tag immutability
   - Set lifecycle policies to expire old images

## Support

For issues with:
- **Lambda code**: Open issue in this repository
- **Infrastructure**: Check your Terraform repository
- **AWS services**: Contact AWS Support
