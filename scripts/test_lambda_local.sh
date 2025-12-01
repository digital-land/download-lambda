#!/bin/bash
#
# Test Lambda function locally with Docker and Lambda Web Adapter
#
# This script simulates the actual Lambda environment locally:
# 1. Starts LocalStack for S3 emulation
# 2. Uploads test data to S3
# 3. Builds and runs Lambda container with Web Adapter
# 4. Downloads CSV and compares with source
#
# Usage:
#   ./scripts/test_lambda_local.sh

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Testing Lambda function locally with Docker${NC}"
echo ""

# Check if test data exists
if [ ! -f "test-data/conservation-area.parquet" ]; then
    echo -e "${RED}❌ Test data not found: test-data/conservation-area.parquet${NC}"
    echo "Download it first or run the tests with actual S3 data"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

# Clean up function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up containers...${NC}"
    docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
}

# Set trap to cleanup on exit
trap cleanup EXIT

echo -e "${YELLOW}📦 Building Docker image...${NC}"
docker build -t download-lambda:test . --platform linux/amd64

echo -e "\n${YELLOW}🔧 Starting LocalStack and Lambda containers...${NC}"
docker-compose -f docker-compose.test.yml up -d

echo -e "\n${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Wait for LocalStack health check
echo "Waiting for LocalStack S3..."
for i in {1..30}; do
    if curl -f http://localhost:4566/_localstack/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ LocalStack ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ LocalStack failed to start${NC}"
        docker-compose -f docker-compose.test.yml logs localstack
        exit 1
    fi
    sleep 1
done

# Upload test data to S3
echo -e "\n${YELLOW}📤 Uploading test data to LocalStack S3...${NC}"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws \
    --endpoint-url=http://localhost:4566 \
    s3 mb s3://test-bucket 2>/dev/null || true

AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws \
    --endpoint-url=http://localhost:4566 \
    s3 cp test-data/conservation-area.parquet s3://test-bucket/dataset/conservation-area.parquet

echo -e "${GREEN}✅ Test data uploaded${NC}"

# Wait for Lambda container health check
echo -e "\n${YELLOW}⏳ Waiting for Lambda container...${NC}"
for i in {1..30}; do
    if curl -f http://localhost:9000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Lambda container ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Lambda container failed to start${NC}"
        docker-compose -f docker-compose.test.yml logs lambda
        exit 1
    fi
    sleep 1
done

echo -e "\n${GREEN}🌐 Lambda function is running at: http://localhost:9000${NC}"
echo ""

# Test CSV download
echo -e "${YELLOW}📥 Testing CSV download...${NC}"
curl -f -o /tmp/lambda-test-download.csv "http://localhost:9000/conservation-area.csv"

if [ ! -f /tmp/lambda-test-download.csv ]; then
    echo -e "${RED}❌ Failed to download CSV${NC}"
    exit 1
fi

echo -e "${GREEN}✅ CSV downloaded successfully${NC}"

# Count rows
CSV_ROWS=$(wc -l < /tmp/lambda-test-download.csv)
echo "  CSV rows (including header): $CSV_ROWS"

# Compare with source using comparison script
echo -e "\n${YELLOW}🔍 Comparing entities with source Parquet...${NC}"

if [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
elif command -v python3 &> /dev/null; then
    PYTHON=python3
else
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

$PYTHON scripts/compare_entities.py test-data/conservation-area.parquet /tmp/lambda-test-download.csv

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ SUCCESS: Lambda streaming test passed!${NC}"
    echo -e "${GREEN}   All entities present and correct${NC}"
else
    echo -e "\n${RED}❌ FAILURE: Lambda streaming has data corruption${NC}"
    echo -e "${RED}   See comparison output above${NC}"

    # Show container logs for debugging
    echo -e "\n${YELLOW}📋 Lambda container logs:${NC}"
    docker-compose -f docker-compose.test.yml logs --tail=50 lambda

    exit 1
fi

# Test JSON download
echo -e "\n${YELLOW}📥 Testing JSON download...${NC}"
curl -f -o /tmp/lambda-test-download.json "http://localhost:9000/conservation-area.json"

if [ ! -f /tmp/lambda-test-download.json ]; then
    echo -e "${RED}❌ Failed to download JSON${NC}"
    exit 1
fi

echo -e "${GREEN}✅ JSON downloaded successfully${NC}"

# Count JSON rows
JSON_ROWS=$($PYTHON -c "import json; data = json.load(open('/tmp/lambda-test-download.json')); print(len(data))")
echo "  JSON rows: $JSON_ROWS"

# Test filtered download
echo -e "\n${YELLOW}📥 Testing filtered CSV download...${NC}"
curl -f -o /tmp/lambda-test-filtered.csv "http://localhost:9000/conservation-area.csv?organisation-entity=242"

if [ ! -f /tmp/lambda-test-filtered.csv ]; then
    echo -e "${RED}❌ Failed to download filtered CSV${NC}"
    exit 1
fi

FILTERED_ROWS=$(wc -l < /tmp/lambda-test-filtered.csv)
echo -e "${GREEN}✅ Filtered CSV downloaded successfully${NC}"
echo "  Filtered rows (including header): $FILTERED_ROWS"

echo -e "\n${GREEN}🎉 All tests passed!${NC}"
echo ""
echo "Test files saved to:"
echo "  - /tmp/lambda-test-download.csv"
echo "  - /tmp/lambda-test-download.json"
echo "  - /tmp/lambda-test-filtered.csv"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.test.yml logs"
echo ""
echo "To stop containers:"
echo "  docker-compose -f docker-compose.test.yml down"
