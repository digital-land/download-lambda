#!/bin/bash
# LocalStack initialization script for S3 bucket
# This runs automatically when LocalStack starts

set -e

echo "==========================================="
echo "Initializing LocalStack S3"
echo "==========================================="

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
until awslocal s3 ls > /dev/null 2>&1; do
    echo "  Waiting for S3 service..."
    sleep 2
done

echo "✓ LocalStack is ready"

# Create S3 bucket
BUCKET_NAME="test-datasets"
echo "Creating S3 bucket: ${BUCKET_NAME}..."
awslocal s3 mb s3://${BUCKET_NAME} || echo "  Bucket already exists"

echo "✓ S3 bucket created"

# Check if test data exists in the mounted directory
if [ -f "/etc/localstack/init/ready.d/test-data/test-dataset.parquet" ]; then
    echo "Uploading test data to S3..."
    awslocal s3 cp /etc/localstack/init/ready.d/test-data/test-dataset.parquet s3://${BUCKET_NAME}/dataset/test-dataset.parquet
    awslocal s3 cp /etc/localstack/init/ready.d/test-data/sales-data.parquet s3://${BUCKET_NAME}/dataset/sales-data.parquet 2>/dev/null || echo "  sales-data.parquet not found, skipping"
    awslocal s3 cp /etc/localstack/init/ready.d/test-data/users-data.parquet s3://${BUCKET_NAME}/dataset/users-data.parquet 2>/dev/null || echo "  users-data.parquet not found, skipping"

    echo "✓ Test data uploaded"

    # List bucket contents to verify
    echo ""
    echo "S3 bucket contents:"
    awslocal s3 ls s3://${BUCKET_NAME}/dataset/ --recursive
else
    echo "⚠️  No test data found in /etc/localstack/init/ready.d/test-data/"
    echo "   Run 'python docker/localstack/generate_test_data.py' to create test data"
fi

echo ""
echo "==========================================="
echo "LocalStack S3 initialization complete!"
echo "==========================================="
echo ""
echo "Bucket: ${BUCKET_NAME}"
echo "Endpoint: http://localhost:4566"
echo ""
echo "To generate and upload test data:"
echo "  1. python docker/localstack/generate_test_data.py"
echo "  2. make dev-upload-data"
echo ""
echo "Test the API:"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:8000/test-dataset.csv"
echo ""
