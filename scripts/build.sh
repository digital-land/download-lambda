#!/bin/bash
# Build script for creating Lambda deployment package

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/build"
DIST_DIR="${REPO_ROOT}/dist"
SRC_DIR="${REPO_ROOT}/src"
REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"

echo "==================================="
echo "Building Lambda deployment package"
echo "==================================="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

# Copy source files as a package
echo "Copying source files as src package..."
mkdir -p "${BUILD_DIR}/src"
cp -r "${SRC_DIR}/." "${BUILD_DIR}/src/"

# Install dependencies
echo "Installing dependencies..."
pip install \
  -r "${REQUIREMENTS_FILE}" \
  -t "${BUILD_DIR}/" \
  --upgrade

# Remove unnecessary files to reduce package size
echo "Cleaning up unnecessary files..."
cd "${BUILD_DIR}"
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Aggressive size reduction for large libraries
echo "Removing large unnecessary files..."
rm -rf boto3/examples 2>/dev/null || true
rm -rf botocore/data/*/*/examples 2>/dev/null || true
rm -rf botocore/data/*/*/paginators-1.json 2>/dev/null || true
rm -rf botocore/data/*/*/waiters-2.json 2>/dev/null || true
rm -rf pyarrow/include 2>/dev/null || true
rm -rf pyarrow/*.pxd 2>/dev/null || true
rm -rf pyarrow/tests 2>/dev/null || true
rm -rf duckdb/tests 2>/dev/null || true
rm -rf numpy/tests 2>/dev/null || true
rm -rf pandas/tests 2>/dev/null || true
find . -name "*.so" -exec strip {} \; 2>/dev/null || true

# Create zip file
echo "Creating deployment package..."
cd "${BUILD_DIR}"
zip -r "${DIST_DIR}/lambda.zip" . -q

# Get file size
FILESIZE=$(du -h "${DIST_DIR}/lambda.zip" | cut -f1)

echo ""
echo "==================================="
echo "Build completed successfully!"
echo "==================================="
echo "Package: ${DIST_DIR}/lambda.zip"
echo "Size: ${FILESIZE}"
echo ""
echo "You can now deploy this package using:"
echo "  - Terraform: terraform apply"
echo "  - AWS CLI: aws lambda update-function-code --function-name download-lambda --zip-file fileb://dist/lambda.zip"
echo ""
echo "Note: Lambda handler should be configured as: src.lambda_function.lambda_handler"
echo ""
