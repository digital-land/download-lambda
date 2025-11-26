#!/bin/bash
# Build script for Docker-based Lambda deployment with FastAPI
# This script builds a Docker image that includes the Lambda Web Adapter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-download-lambda}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "============================================"
echo "Building Docker image for Lambda deployment"
echo "============================================"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

cd "${REPO_ROOT}"

# Build Docker image
echo "Building Docker image..."
docker build \
  --platform linux/amd64 \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  -f Dockerfile \
  .

echo ""
echo "============================================"
echo "Docker build completed successfully!"
echo "============================================"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "To test locally:"
echo "  docker run -p 8000:8000 \\"
echo "    -e DATASET_BUCKET=your-bucket \\"
echo "    -e AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID \\"
echo "    -e AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY \\"
echo "    ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "To push to ECR:"
echo "  aws ecr get-login-password --region eu-west-2 | \\"
echo "    docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-2.amazonaws.com"
echo "  docker tag ${IMAGE_NAME}:${IMAGE_TAG} <account-id>.dkr.ecr.eu-west-2.amazonaws.com/${IMAGE_NAME}:${IMAGE_TAG}"
echo "  docker push <account-id>.dkr.ecr.eu-west-2.amazonaws.com/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
