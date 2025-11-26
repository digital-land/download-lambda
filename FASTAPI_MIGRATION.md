# FastAPI Migration Guide

This document explains the migration from custom Lambda response streaming to FastAPI with AWS Lambda Web Adapter.

## Overview

The application has been converted from a custom Lambda streaming handler to a FastAPI application that runs inside Lambda using the AWS Lambda Web Adapter. This provides:

- ✅ **Standard web framework** - FastAPI is industry-standard and well-documented
- ✅ **Better development experience** - Run locally with `uvicorn`, get automatic API docs
- ✅ **Simpler code** - Removed 100+ lines of custom event parsing
- ✅ **Response streaming** - Still supported via FastAPI's StreamingResponse
- ✅ **Portability** - Same code runs in Lambda, Docker, or any ASGI server

## Architecture Changes

### Before (Custom Lambda Streaming)

```
Lambda Function URL (RESPONSE_STREAM mode)
    ↓
lambda_function.lambda_handler(event, response_stream, context)
    ↓
Custom event parsing (CloudFront/Function URL formats)
    ↓
Manual response_stream.write() + response_stream.end()
```

### After (FastAPI with Web Adapter)

```
Lambda Function URL
    ↓
AWS Lambda Web Adapter (translates Lambda events → HTTP)
    ↓
Uvicorn (ASGI server running FastAPI)
    ↓
FastAPI routes with automatic validation
    ↓
StreamingResponse (standard HTTP streaming)
```

## What Changed

### New Files Created

1. **`application/main.py`** - FastAPI application entry point
2. **`application/api/routes.py`** - Route handlers (replaces custom streaming logic)
3. **`application/api/dependencies.py`** - Dependency injection for config
4. **`Dockerfile`** - Docker image with Lambda Web Adapter
5. **`scripts/build-docker.sh`** - Docker build script

### Files Modified

1. **`application/utils.py`** - Removed custom event parsing (100+ lines removed)
2. **`requirements.txt`** - Added `fastapi` and `uvicorn`
3. **`.github/workflows/deploy.yml`** - Changed to Docker/ECR deployment
4. **`requirements-dev.txt`** - Added `httpx` for testing

### Files Unchanged

1. **`application/models.py`** - Pydantic models work perfectly with FastAPI
2. **`application/data_processor.py`** - Core streaming logic unchanged
3. **Test fixtures** - Can be reused with FastAPI TestClient

## Infrastructure Changes Required

### 1. Create ECR Repositories

You need to create ECR repositories for each environment:

```bash
# For staging
aws ecr create-repository \
  --repository-name staging-download-lambda \
  --region eu-west-2

# For production
aws ecr create-repository \
  --repository-name production-download-lambda \
  --region eu-west-2
```

### 2. Update Lambda Function Configuration

**IMPORTANT:** Your Lambda functions need to be updated to use container images instead of zip files.

#### Option A: Update Existing Functions via Terraform

If you're using Terraform, update your Lambda function configuration:

```hcl
resource "aws_lambda_function" "download_lambda" {
  function_name = "${var.environment}-download-lambda"
  role          = aws_iam_role.lambda_role.arn

  # Change from Zip to Image
  package_type = "Image"
  image_uri    = "${var.ecr_registry}/${var.environment}-download-lambda:latest"

  # Remove these (not used with container images):
  # filename = ...
  # handler = ...
  # runtime = ...

  timeout     = 300
  memory_size = 3008

  environment {
    variables = {
      DATASET_BUCKET = var.dataset_bucket_name
      # Optional: Enable docs in development
      ENVIRONMENT = var.environment == "staging" ? "development" : "production"
    }
  }
}
```

#### Option B: Update via AWS Console

1. Go to AWS Lambda Console
2. Select your function
3. Go to **Code** tab
4. Click **Image** → **Deploy new image**
5. Select your ECR repository and tag
6. Click **Save**

#### Option C: Recreate Functions

If updating in-place is complex, you can recreate the functions:

1. Delete old Lambda functions (zip-based)
2. Create new Lambda functions with container image type
3. Point to ECR repository
4. Configure environment variables, IAM roles, etc.

### 3. Lambda Function URL Configuration

The Function URL configuration **remains the same**:

- **InvokeMode**: `RESPONSE_STREAM` ✅ Still required
- **Auth**: Same as before
- **CORS**: Same as before

The Lambda Web Adapter handles translating the streaming response.

## Local Development

### Running Locally with Docker

```bash
# Build the Docker image
./scripts/build-docker.sh

# Run locally
docker run -p 8000:8000 \
  -e DATASET_BUCKET=your-test-bucket \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_REGION=eu-west-2 \
  -e ENVIRONMENT=development \
  download-lambda:latest

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/docs  # API documentation
curl http://localhost:8000/test-dataset.csv
curl "http://localhost:8000/test-dataset.csv?organisation-entity=org-1"
```

### Running Locally with Uvicorn (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATASET_BUCKET=your-test-bucket
export AWS_PROFILE=your-profile
export ENVIRONMENT=development

# Run with auto-reload
uvicorn application.main:app --reload --port 8000

# Access API docs
open http://localhost:8000/docs
```

## Testing

### Unit Tests with FastAPI TestClient

FastAPI provides a test client that doesn't require a running server:

```python
from fastapi.testclient import TestClient
from application.main import app

def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "download-lambda"}

def test_download_csv(monkeypatch):
    monkeypatch.setenv("DATASET_BUCKET", "test-bucket")
    client = TestClient(app)

    # TestClient automatically handles streaming responses
    response = client.get("/test-dataset.csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv"
```

### Integration Tests

Your existing integration tests with moto can be updated to use TestClient instead of mocking Lambda events.

## Deployment

### First Deployment

1. **Push code to main branch** - This triggers the CI/CD workflow

2. **Workflow will**:
   - Run tests
   - Build Docker image
   - Push to ECR
   - Update Lambda function

3. **Verify deployment**:
   ```bash
   # Check Lambda function
   aws lambda get-function \
     --function-name staging-download-lambda \
     --region eu-west-2

   # Test the function URL
   curl https://your-function-url.lambda-url.eu-west-2.on.aws/health
   ```

### Subsequent Deployments

Just push to main - the CI/CD pipeline handles everything automatically.

## Monitoring

### CloudWatch Logs

Logs now include:
- **Uvicorn logs** - HTTP request/response logs
- **FastAPI logs** - Application-level logging
- **Your application logs** - Same as before

Example log output:
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     2024-01-15 - application.main - INFO - Starting Download Lambda FastAPI application
INFO:     2024-01-15 - application.main - INFO - Dataset bucket: my-bucket
INFO:     Application startup complete.
INFO:     172.31.0.1:45678 - "GET /health HTTP/1.1" 200 OK
INFO:     172.31.0.1:45679 - "GET /test-dataset.csv HTTP/1.1" 200 OK
```

### Metrics to Watch

Same as before:
- **Duration** - Should be similar to old implementation
- **Memory** - Might be slightly higher due to uvicorn overhead (~50-100MB)
- **Errors** - Watch for 500 errors in CloudWatch
- **Concurrent executions** - Same as before

## Rollback Plan

If you need to rollback:

### Option 1: Revert to Previous Image

```bash
aws lambda update-function-code \
  --function-name staging-download-lambda \
  --image-uri <account-id>.dkr.ecr.eu-west-2.amazonaws.com/staging-download-lambda:previous-tag
```

### Option 2: Revert Git Commit

```bash
git revert <commit-hash>
git push origin main
```

The CI/CD will automatically deploy the reverted code.

## FAQ

### Q: Does streaming still work?

**A:** Yes! FastAPI's `StreamingResponse` provides the same chunked streaming behavior. The Lambda Web Adapter translates it to Lambda's response streaming format.

### Q: What about performance?

**A:** Performance is essentially the same:
- **Cold start**: ~200-500ms (slightly higher due to uvicorn startup)
- **Warm requests**: Same as before
- **Streaming**: No overhead, same DuckDB streaming

### Q: Can I still use the old lambda_function.py?

**A:** The old file still exists but is not used. The Docker CMD runs uvicorn directly. You can delete `lambda_function.py` after migration is complete.

### Q: What happens to environment variables?

**A:** They work the same way. Set them in Terraform/CloudFormation or via AWS Console.

### Q: Do I need to change my Function URL?

**A:** No, the Function URL stays the same. Clients don't need any changes.

### Q: What if I want to add CORS?

**A:** Add FastAPI CORS middleware:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

### Q: Can I add authentication?

**A:** Yes, use FastAPI dependencies:
```python
from fastapi import Depends, HTTPException, Header

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@router.get("/{dataset}.{extension}", dependencies=[Depends(verify_api_key)])
async def download_dataset(...):
    ...
```

### Q: What about rate limiting?

**A:** Use FastAPI middleware like `slowapi`:
```bash
pip install slowapi
```

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.get("/{dataset}.{extension}")
@limiter.limit("10/minute")
async def download_dataset(...):
    ...
```

## Troubleshooting

### Issue: Function returns 500 errors

**Check:**
1. CloudWatch logs for Python errors
2. Environment variables are set correctly
3. ECR image is accessible by Lambda role

### Issue: Streaming doesn't work

**Check:**
1. Lambda Function URL has `InvokeMode: RESPONSE_STREAM`
2. Lambda timeout is high enough (300s recommended)
3. CloudWatch logs don't show truncation

### Issue: Docker build fails

**Check:**
1. Docker daemon is running
2. You have internet access (to pull base images)
3. requirements.txt is valid

### Issue: ECR push fails

**Check:**
1. ECR repository exists
2. AWS credentials have ECR permissions
3. You're logged in to ECR: `aws ecr get-login-password | docker login ...`

## Next Steps

1. ✅ Merge FastAPI changes to main branch
2. ✅ Create ECR repositories
3. ✅ First deployment (staging)
4. ✅ Test streaming endpoints
5. ✅ Monitor metrics for 24-48 hours
6. ✅ Deploy to production
7. ✅ Delete old `lambda_function.py` (optional cleanup)

## Support

For issues or questions:
- Check CloudWatch logs first
- Review FastAPI docs: https://fastapi.tiangolo.com
- Review Lambda Web Adapter: https://github.com/awslabs/aws-lambda-web-adapter
- File issue in this repository
