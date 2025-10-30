#!/bin/bash
# Build script for creating Lambda deployment package

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
DIST_DIR="${SCRIPT_DIR}/dist"

echo "==================================="
echo "Building Lambda deployment package"
echo "==================================="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

# Copy source files
echo "Copying source files..."
cp -r "${SCRIPT_DIR}/src/"* "${BUILD_DIR}/"

# Install dependencies
echo "Installing dependencies..."
pip install -r "${SCRIPT_DIR}/requirements.txt" -t "${BUILD_DIR}/" --upgrade

# Remove unnecessary files to reduce package size
echo "Cleaning up unnecessary files..."
cd "${BUILD_DIR}"
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

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
