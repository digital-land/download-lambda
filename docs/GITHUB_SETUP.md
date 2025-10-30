# GitHub Repository Setup

This guide explains how to configure GitHub repository secrets for CI/CD deployment.

## Required Secrets

Navigate to your GitHub repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

### AWS Credentials

These are required for the GitHub Actions workflow to build and deploy your Lambda function.

#### AWS_ACCESS_KEY_ID
- **Description:** IAM access key for AWS deployment
- **How to get:**
  ```bash
  # Create IAM user for CI/CD
  aws iam create-user --user-name github-actions-download-lambda

  # Create access key
  aws iam create-access-key --user-name github-actions-download-lambda
  ```
- **Value format:** `AKIAIOSFODNN7EXAMPLE`

#### AWS_SECRET_ACCESS_KEY
- **Description:** IAM secret key for AWS deployment
- **How to get:** Obtained from the `create-access-key` command above
- **Value format:** `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

### Optional Secrets

#### DEPLOYMENT_BUCKET
- **Description:** S3 bucket where Lambda packages are uploaded
- **When to use:** If you want GitHub Actions to upload built packages to S3 for Terraform to reference
- **How to create:**
  ```bash
  aws s3 mb s3://my-deployment-bucket
  aws s3api put-bucket-versioning \
    --bucket my-deployment-bucket \
    --versioning-configuration Status=Enabled
  ```
- **Value format:** `my-deployment-bucket` (bucket name only, no s3:// prefix)

#### LAMBDA_FUNCTION_NAME
- **Description:** Name of your Lambda function
- **When to use:** If you want the workflow to display the Function URL in the summary
- **Value format:** `download-lambda` or `download-lambda-production`

## IAM Permissions

The IAM user needs these permissions:

### Minimal Permissions (No S3 Upload)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaReadAccess",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction",
        "lambda:GetFunctionUrlConfig"
      ],
      "Resource": "arn:aws:lambda:*:*:function:download-lambda*"
    }
  ]
}
```

### Full Permissions (With S3 Upload)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Upload",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::YOUR-DEPLOYMENT-BUCKET/*"
    },
    {
      "Sid": "LambdaReadAccess",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction",
        "lambda:GetFunctionUrlConfig"
      ],
      "Resource": "arn:aws:lambda:*:*:function:download-lambda*"
    }
  ]
}
```

### Apply Permissions

```bash
# Save policy to file
cat > github-actions-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Upload",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:PutObjectAcl"],
      "Resource": "arn:aws:s3:::YOUR-DEPLOYMENT-BUCKET/*"
    },
    {
      "Sid": "LambdaReadAccess",
      "Effect": "Allow",
      "Action": ["lambda:GetFunction", "lambda:GetFunctionUrlConfig"],
      "Resource": "arn:aws:lambda:*:*:function:download-lambda*"
    }
  ]
}
EOF

# Create policy
aws iam create-policy \
  --policy-name GitHubActionsDownloadLambda \
  --policy-document file://github-actions-policy.json

# Get policy ARN
POLICY_ARN=$(aws iam list-policies \
  --query "Policies[?PolicyName=='GitHubActionsDownloadLambda'].Arn" \
  --output text)

# Attach to user
aws iam attach-user-policy \
  --user-name github-actions-download-lambda \
  --policy-arn $POLICY_ARN
```

## Step-by-Step Setup

### 1. Create IAM User and Access Key

```bash
# Create user
aws iam create-user --user-name github-actions-download-lambda

# Create policy (replace YOUR-DEPLOYMENT-BUCKET)
aws iam create-policy \
  --policy-name GitHubActionsDownloadLambda \
  --policy-document file://github-actions-policy.json

# Attach policy
POLICY_ARN=$(aws iam list-policies \
  --query "Policies[?PolicyName=='GitHubActionsDownloadLambda'].Arn" \
  --output text)

aws iam attach-user-policy \
  --user-name github-actions-download-lambda \
  --policy-arn $POLICY_ARN

# Create access key
aws iam create-access-key --user-name github-actions-download-lambda
```

**Save the output!** You'll need both `AccessKeyId` and `SecretAccessKey`.

### 2. Create Deployment Bucket (Optional)

```bash
# Create bucket
aws s3 mb s3://my-deployment-bucket

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket my-deployment-bucket \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket my-deployment-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### 3. Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret:

| Name | Value | Example |
|------|-------|---------|
| `AWS_ACCESS_KEY_ID` | From step 1 | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | From step 1 | `wJalrXUt...` |
| `DEPLOYMENT_BUCKET` | Bucket name | `my-deployment-bucket` |
| `LAMBDA_FUNCTION_NAME` | Function name | `download-lambda` |

### 4. Verify Setup

Push a commit to trigger the workflow:

```bash
git add .
git commit -m "Test CI/CD setup"
git push origin main
```

Go to **Actions** tab in GitHub to see the workflow run.

## Security Best Practices

### 1. Use Least Privilege

Only grant the minimum required permissions:
- Read-only Lambda access if you only need function URL
- S3 write access only to specific bucket prefix

### 2. Rotate Access Keys Regularly

```bash
# Create new key
aws iam create-access-key --user-name github-actions-download-lambda

# Update GitHub secrets with new key

# Delete old key
aws iam delete-access-key \
  --user-name github-actions-download-lambda \
  --access-key-id OLD_ACCESS_KEY_ID
```

### 3. Use Separate Users per Environment

```bash
# Production
aws iam create-user --user-name github-actions-download-lambda-prod

# Staging
aws iam create-user --user-name github-actions-download-lambda-staging
```

Store in environment-specific secrets:
- `AWS_ACCESS_KEY_ID_PROD`
- `AWS_ACCESS_KEY_ID_STAGING`

### 4. Enable CloudTrail Logging

Monitor IAM user activity:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=github-actions-download-lambda \
  --max-results 10
```

## Troubleshooting

### Error: "Access Denied" in GitHub Actions

**Check:**
1. IAM user exists and has correct policy attached
2. Access key is active (not deleted)
3. Secret names match exactly in workflow file
4. IAM policy has correct resource ARNs

**Debug:**
```bash
# Test credentials locally
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Try the same commands as workflow
aws s3 ls s3://deployment-bucket/
aws lambda get-function --function-name download-lambda
```

### Error: "Invalid credentials"

**Causes:**
- Incorrect access key or secret
- Key has been deleted/deactivated
- Copy-paste error in GitHub secrets

**Fix:**
1. Verify credentials locally
2. Re-create access key if needed
3. Update GitHub secrets

### Workflow succeeds but doesn't upload to S3

**Check:**
- `DEPLOYMENT_BUCKET` secret is set
- IAM user has `s3:PutObject` permission
- Bucket exists and is accessible

**Test manually:**
```bash
aws s3 cp dist/lambda.zip s3://your-bucket/test.zip
```

## Environment Variables vs Secrets

### Secrets (Encrypted)
Use for sensitive data:
- AWS credentials
- API keys
- Passwords

### Variables (Plain text)
Use for non-sensitive config:
- AWS region
- Function name patterns
- Build settings

**To add variables:**
Settings → Secrets and variables → Actions → Variables tab → New repository variable

## Using with GitHub Environments

For multiple environments (dev/staging/prod):

1. Go to Settings → Environments
2. Create environment (e.g., "production")
3. Add environment-specific secrets
4. Update workflow:

```yaml
jobs:
  deploy:
    environment: production
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Alternative: OIDC (Recommended for Production)

Instead of long-lived access keys, use OpenID Connect:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::ACCOUNT:role/GitHubActionsRole
    aws-region: us-east-1
```

See [AWS documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) for setup.

## Support

If you encounter issues:
1. Check GitHub Actions logs for detailed error messages
2. Test IAM permissions locally with same credentials
3. Verify all secret names match the workflow file
4. Review [DEPLOYMENT.md](DEPLOYMENT.md) for more context
