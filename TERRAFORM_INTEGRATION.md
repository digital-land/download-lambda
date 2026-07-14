# Terraform Integration Guide

This guide shows how to integrate the Lambda function into your existing Terraform infrastructure.

## Overview

The Lambda function code lives in this repository and runs as a **container image**, while your infrastructure (Lambda resource, IAM roles, ECR repository, etc.) is managed in your separate Terraform repository.

## Step-by-Step Integration

### 1. Build the Docker Image

In this repository:

```bash
# Run tests
make test

# Build the image
docker build --platform linux/amd64 -t download-lambda:latest .
```

Push it to your environment's ECR repository (this is handled automatically by `.github/workflows/deploy.yml` in normal use — see [DEPLOYMENT.md](docs/DEPLOYMENT.md)):

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker tag download-lambda:latest <account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/download-lambda:latest
```

### 2. Copy Terraform Configuration

Copy the example Terraform files to your infrastructure repository:

```bash
cp -r terraform-example/ /path/to/your/terraform-repo/modules/download-lambda/
```

### 3. Add to Your Terraform Configuration

In your Terraform repository's main configuration:

```hcl
# main.tf or lambda.tf

module "download_lambda" {
  source = "./modules/download-lambda"

  function_name       = "download-lambda-${var.environment}"
  dataset_bucket_name = var.dataset_bucket_name
  package_type        = "Image"
  image_uri           = "${aws_ecr_repository.download_lambda.repository_url}:latest"

  timeout      = 60
  memory_size  = 512
  auth_type    = "NONE"  # or "AWS_IAM" for authenticated access

  create_cloudfront = var.environment == "production"

  tags = {
    Environment = var.environment
    Project     = "data-downloads"
    ManagedBy   = "Terraform"
  }
}

# ECR repository this repo's CI/CD pushes images to
resource "aws_ecr_repository" "download_lambda" {
  name                 = "download-lambda-${var.environment}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Outputs
output "download_lambda_url" {
  description = "Lambda Function URL"
  value       = module.download_lambda.lambda_function_url
}

output "download_cloudfront_url" {
  description = "CloudFront URL (if enabled)"
  value       = module.download_lambda.cloudfront_url
}
```

### 4. Configure Variables

Create or update `terraform.tfvars`:

```hcl
environment         = "production"
dataset_bucket_name = "my-datasets-bucket"
```

### 5. Deploy

```bash
cd /path/to/your/terraform-repo

terraform init
terraform plan
terraform apply
```

Once the Lambda function and ECR repository exist, this repository's GitHub Actions workflow takes over routine code deploys — pushing new images and calling `UpdateFunctionCode` directly, without needing a `terraform apply` for every code change.

## Using with Existing S3 Bucket

If you already have an S3 bucket in Terraform:

```hcl
# Your existing bucket
resource "aws_s3_bucket" "datasets" {
  bucket = "my-datasets-bucket"
  # ... your configuration
}

# Use it with the Lambda module
module "download_lambda" {
  source = "./modules/download-lambda"

  dataset_bucket_name = aws_s3_bucket.datasets.id
  # ... other configuration
}
```

## Customizing the Terraform Module

### Adding VPC Configuration

Edit `terraform-example/main.tf`:

```hcl
resource "aws_lambda_function" "download_function" {
  # ... existing configuration

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }
}
```

Add to `variables.tf`:

```hcl
variable "subnet_ids" {
  description = "VPC subnet IDs for Lambda"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "Security group IDs for Lambda"
  type        = list(string)
  default     = []
}
```

### Adding Custom IAM Policies

Edit `terraform-example/main.tf`:

```hcl
resource "aws_iam_role_policy" "custom_policy" {
  name = "${var.function_name}-custom-policy"
  role = aws_iam_role.download_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"  # Example: if S3 uses KMS encryption
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}
```

### Adding CloudWatch Alarms

```hcl
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Lambda function error rate"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.download_function.function_name
  }
}
```

## Multi-Environment Setup

### Using Terraform Workspaces

```bash
# Create environments
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

# Deploy to dev
terraform workspace select dev
terraform apply -var-file="env/dev.tfvars"

# Deploy to prod
terraform workspace select prod
terraform apply -var-file="env/prod.tfvars"
```

### Environment-Specific Configuration

```
terraform-repo/
├── modules/
│   └── download-lambda/
├── env/
│   ├── dev.tfvars
│   ├── staging.tfvars
│   └── prod.tfvars
└── main.tf
```

**env/dev.tfvars:**
```hcl
environment         = "dev"
dataset_bucket_name = "datasets-dev"
memory_size         = 512
timeout             = 30
create_cloudfront   = false
auth_type           = "NONE"
```

**env/prod.tfvars:**
```hcl
environment         = "prod"
dataset_bucket_name = "datasets-prod"
memory_size         = 1024
timeout             = 60
create_cloudfront   = true
auth_type           = "AWS_IAM"
```

## Referencing the Latest Image From ECR

For CI/CD workflows, this repository's GitHub Actions already updates the function's code directly after every push — but if you want Terraform itself to track the current image (e.g. to detect drift), reference the ECR repository as a data source:

```hcl
data "aws_ecr_image" "download_lambda" {
  repository_name = "download-lambda-${var.environment}"
  most_recent     = true
}

resource "aws_lambda_function" "download_function" {
  function_name = var.function_name
  role          = aws_iam_role.download_lambda_role.arn
  package_type  = "Image"

  image_uri = "${data.aws_ecr_repository.download_lambda.repository_url}@${data.aws_ecr_image.download_lambda.image_digest}"

  # ... rest of configuration
}
```

Note: since this repo's CI updates the function directly with `UpdateFunctionCode`, Terraform tracking the image this way will show drift after every deploy unless you re-run `terraform apply` (or import the new digest) afterwards. Most teams leave image updates to CI and let Terraform only manage the function's non-image configuration.

## Terraform Remote Backend

Configure remote state for team collaboration:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "download-lambda/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

## Integration with Existing CloudFront

If you already have a CloudFront distribution:

```hcl
# Your existing CloudFront distribution
resource "aws_cloudfront_distribution" "main" {
  # ... existing configuration

  # Add Lambda as a new origin
  origin {
    domain_name = replace(module.download_lambda.lambda_function_url, "https://", "")
    origin_id   = "download-lambda"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Add cache behavior for download paths
  ordered_cache_behavior {
    path_pattern     = "/downloads/*"
    target_origin_id = "download-lambda"
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]

    forwarded_values {
      query_string = true
      headers      = ["Accept"]
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }
}
```

## Module Version Management

### Using Git Tags

Tag releases in this repository:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Reference in Terraform:

```hcl
module "download_lambda" {
  source = "git::https://github.com/your-org/download-lambda.git//terraform-example?ref=v1.0.0"

  # ... configuration
}
```

### Using Terraform Registry

Publish to your private Terraform registry and reference:

```hcl
module "download_lambda" {
  source  = "app.terraform.io/your-org/download-lambda/aws"
  version = "1.0.0"

  # ... configuration
}
```

## Complete Example

Here's a complete example integrating everything:

```hcl
# Provider configuration
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "my-terraform-state"
    key    = "download-lambda/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "environment" {
  description = "Environment name"
  type        = string
}

variable "dataset_bucket_name" {
  description = "S3 bucket with datasets"
  type        = string
}

# Existing resources
data "aws_s3_bucket" "datasets" {
  bucket = var.dataset_bucket_name
}

# ECR repository for this repo's CI/CD to push images to
resource "aws_ecr_repository" "download_lambda" {
  name                 = "download-lambda-${var.environment}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Lambda module
module "download_lambda" {
  source = "./modules/download-lambda"

  function_name       = "download-lambda-${var.environment}"
  dataset_bucket_name = data.aws_s3_bucket.datasets.id
  package_type        = "Image"
  image_uri           = "${aws_ecr_repository.download_lambda.repository_url}:latest"

  timeout      = var.environment == "prod" ? 90 : 60
  memory_size  = var.environment == "prod" ? 1024 : 512
  auth_type    = var.environment == "prod" ? "AWS_IAM" : "NONE"

  create_cloudfront = var.environment == "prod"

  tags = {
    Environment = var.environment
    Project     = "data-platform"
    ManagedBy   = "Terraform"
  }
}

# CloudWatch alarm
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count = var.environment == "prod" ? 1 : 0

  alarm_name          = "download-lambda-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10

  dimensions = {
    FunctionName = module.download_lambda.lambda_function_name
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
}

# Outputs
output "lambda_function_url" {
  description = "Lambda Function URL"
  value       = module.download_lambda.lambda_function_url
}

output "api_endpoint" {
  description = "API endpoint for downloads"
  value       = var.environment == "prod" ? module.download_lambda.cloudfront_url : module.download_lambda.lambda_function_url
}
```

## Testing Terraform Changes

```bash
# Validate configuration
terraform validate

# Format code
terraform fmt -recursive

# Check what will change
terraform plan -out=tfplan

# Review plan
terraform show tfplan

# Apply if looks good
terraform apply tfplan
```

## Common Issues

### Issue: Lambda not updating after code change

**Problem:** You expected `terraform apply` to deploy a code change, but nothing happened

**Solution:** Routine code changes are deployed by this repository's GitHub Actions workflow, which calls `UpdateFunctionCode` directly with the new image — not by Terraform. `terraform apply` only needs to run when infrastructure changes (memory, timeout, IAM, VPC config, etc.), not for every code push. If you do want Terraform to track and force an update to the image, use `most_recent = true` on an `aws_ecr_image` data source (see above) and re-apply.

### Issue: Cannot reference S3 bucket

**Problem:** Bucket in different Terraform state

**Solution:** Use data source:

```hcl
data "aws_s3_bucket" "datasets" {
  bucket = "my-datasets-bucket"
}
```

Or use Terraform remote state:

```hcl
data "terraform_remote_state" "shared" {
  backend = "s3"
  config = {
    bucket = "terraform-state"
    key    = "shared/terraform.tfstate"
    region = "us-east-1"
  }
}

# Reference outputs
dataset_bucket_name = data.terraform_remote_state.shared.outputs.dataset_bucket_name
```

## Next Steps

1. Copy Terraform files to your infrastructure repository
2. Customize variables for your environment
3. Run `terraform plan` to preview changes
4. Apply with `terraform apply`
5. Test the deployed function
6. Set up CI/CD pipeline (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md))
